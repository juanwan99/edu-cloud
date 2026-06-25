from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_PATH = PROJECT_ROOT / "scripts" / "governance" / "live_fact_collector.py"


def load_collector():
    spec = importlib.util.spec_from_file_location(
        "live_fact_collector_under_test",
        COLLECTOR_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "frontend" / "dist").mkdir(parents=True)
    (project / "frontend" / "dist" / "index.html").write_text("<main></main>", encoding="utf-8")
    (project / "frontend" / "dist" / "version.json").write_text(
        json.dumps({"git_hash": "abc123", "built_at": "2026-06-25T09:00:00Z"}),
        encoding="utf-8",
    )
    (project / "scripts").mkdir()
    (project / "scripts" / "db_doctor.py").write_text("# test stub\n", encoding="utf-8")
    return project


def test_collect_live_facts_covers_port_ghost_dist_db_and_systemd(tmp_path):
    collector = load_collector()
    project = make_project(tmp_path)

    def runner(args, *, timeout=10, cwd=None):
        command = list(args)
        if command == ["ss", "-H", "-tlnp"]:
            return collector.CommandResult(
                0,
                "\n".join(
                    [
                        'LISTEN 0 4096 127.0.0.1:9000 0.0.0.0:* users:(("uvicorn",pid=100,fd=7))',
                        'LISTEN 0 4096 0.0.0.0:8100 0.0.0.0:* users:(("python",pid=300,fd=8))',
                    ]
                ),
                "",
            )
        if command == ["ps", "aux"]:
            return collector.CommandResult(
                0,
                "\n".join(
                    [
                        "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND",
                        "ops 200 0.0 0.1 1000 100 ? S 09:00 0:00 python -m uvicorn app --reload --port 9000",
                        "ops 201 0.0 0.1 1000 100 ? S 09:00 0:00 python -m http.server 8080",
                    ]
                ),
                "",
            )
        if command == ["ps", "-p", "100", "-o", "ppid=,command="]:
            return collector.CommandResult(0, "1 /srv/edu-cloud/.venv/bin/uvicorn edu_cloud.api.app:app\n", "")
        if command == ["ps", "-p", "300", "-o", "ppid=,command="]:
            return collector.CommandResult(0, "1 /srv/edu-cloud/.venv/bin/python -m llm_proxy.app\n", "")
        if command == ["ps", "-p", "200", "-o", "ppid=,command="]:
            return collector.CommandResult(0, "1 python -m uvicorn app --reload --port 9000\n", "")
        if command == ["ps", "-p", "201", "-o", "ppid=,command="]:
            return collector.CommandResult(0, "900 python -m http.server 8080\n", "")
        if command[:2] == ["systemctl", "is-active"]:
            service = command[2]
            active = service in {"edu-cloud", "llm-proxy", "edu-cloud-guardian"}
            return collector.CommandResult(0 if active else 3, "active\n" if active else "inactive\n", "")
        if command[:2] == ["systemctl", "show"]:
            service = command[2]
            main_pids = {"edu-cloud": 100, "llm-proxy": 300, "edu-cloud-worker": 0, "edu-cloud-guardian": 444}
            active = service != "edu-cloud-worker"
            return collector.CommandResult(
                0,
                "\n".join(
                    [
                        f"MainPID={main_pids[service]}",
                        f"ActiveState={'active' if active else 'inactive'}",
                        f"SubState={'running' if active else 'dead'}",
                        "LoadState=loaded",
                    ]
                ),
                "",
            )
        if command[-2:] == ["scripts/db_doctor.py", "--json"]:
            assert cwd == project
            return collector.CommandResult(
                0,
                json.dumps(
                    {
                        "hard": 0,
                        "warn": 1,
                        "alembic_version": "202606250900",
                        "orm_tables": 7,
                        "db_tables": 7,
                    }
                ),
                "",
            )
        raise AssertionError(f"unexpected command: {command}")

    facts = collector.collect_live_facts(
        project_root=project,
        runner=runner,
        now=lambda: "2026-06-25T09:00:00Z",
    )

    assert facts["schema"] == "governance.live_facts.v1"
    assert facts["generated_at"] == "2026-06-25T09:00:00Z"
    assert facts["project_root"] == str(project)

    assert facts["ports"]["status"] == "ok"
    assert facts["ports"]["expected"]["9000"]["present"] is True
    assert facts["ports"]["expected"]["8100"]["public_bind"] is True
    assert facts["ports"]["listeners"][0]["service"] == "edu-cloud"

    assert facts["ghost_processes"]["status"] == "ok"
    assert [process["pid"] for process in facts["ghost_processes"]["suspects"]] == [200]

    assert facts["dist"]["status"] == "ok"
    assert facts["dist"]["version"]["git_hash"] == "abc123"

    assert facts["db"]["status"] == "ok"
    assert facts["db"]["hard"] == 0
    assert facts["db"]["warn"] == 1
    assert facts["db"]["alembic_version"] == "202606250900"

    assert facts["systemd"]["status"] == "ok"
    assert facts["systemd"]["services"]["edu-cloud"]["active"] is True
    assert facts["systemd"]["services"]["edu-cloud-worker"]["main_pid"] is None
    assert facts["systemd"]["main_pids"] == {"100": "edu-cloud", "300": "llm-proxy", "444": "edu-cloud-guardian"}


def test_parse_ss_listeners_handles_ipv6_and_process_metadata():
    collector = load_collector()

    listeners = collector.parse_ss_listeners(
        "\n".join(
            [
                'LISTEN 0 4096 [::]:8080 [::]:* users:(("node",pid=77,fd=18))',
                'LISTEN 0 4096 127.0.0.1:9000 0.0.0.0:* users:(("uvicorn",pid=88,fd=7))',
            ]
        )
    )

    assert listeners == [
        {
            "bind": "[::]",
            "port": 8080,
            "pid": 77,
            "process": "node",
            "public_bind": True,
            "raw": 'LISTEN 0 4096 [::]:8080 [::]:* users:(("node",pid=77,fd=18))',
        },
        {
            "bind": "127.0.0.1",
            "port": 9000,
            "pid": 88,
            "process": "uvicorn",
            "public_bind": False,
            "raw": 'LISTEN 0 4096 127.0.0.1:9000 0.0.0.0:* users:(("uvicorn",pid=88,fd=7))',
        },
    ]


def test_collect_live_facts_degrades_when_runtime_commands_are_unavailable(tmp_path):
    collector = load_collector()
    project = tmp_path / "project"
    project.mkdir()

    def runner(args, *, timeout=10, cwd=None):
        return collector.CommandResult(127, "", "command missing")

    facts = collector.collect_live_facts(
        project_root=project,
        runner=runner,
        now=lambda: "2026-06-25T09:30:00Z",
    )

    assert facts["ports"]["status"] == "failed"
    assert facts["ports"]["listeners"] == []
    assert facts["ghost_processes"]["status"] == "failed"
    assert facts["dist"]["status"] == "missing"
    assert facts["db"]["status"] == "doctor_missing"
    assert facts["systemd"]["status"] == "failed"
