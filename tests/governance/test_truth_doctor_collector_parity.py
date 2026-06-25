from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRUTH_DOCTOR = PROJECT_ROOT / "scripts" / "truth-doctor.sh"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value)


def make_fake_project(tmp_path: Path) -> Path:
    project = tmp_path / "fake-project"
    (project / ".venv" / "bin").mkdir(parents=True)
    (project / "scripts").mkdir()
    (project / "frontend" / "dist").mkdir(parents=True)
    (project / "frontend" / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
    (project / "scripts" / "db_doctor.py").write_text("# fake db doctor target\n", encoding="utf-8")

    python_stub = project / ".venv" / "bin" / "python"
    python_stub.write_text(
        """#!/usr/bin/env python3
import json
import sys

if len(sys.argv) >= 3 and sys.argv[-2].endswith("scripts/db_doctor.py") and sys.argv[-1] == "--json":
    print(json.dumps({
        "hard": 0,
        "warn": 0,
        "orm_tables": 7,
        "db_tables": 7,
        "alembic_version": "test",
    }))
    raise SystemExit(0)

raise SystemExit(1)
""",
        encoding="utf-8",
    )
    python_stub.chmod(0o755)
    return project


def make_fake_collector(tmp_path: Path, marker: Path) -> Path:
    facts = {
        "schema": "governance.live_facts.v1",
        "ports": {
            "listeners": [
                {
                    "bind": "0.0.0.0",
                    "port": 9000,
                    "pid": 101,
                    "process": "uvicorn",
                    "public_bind": True,
                    "ppid": 1,
                    "command": "uvicorn edu_cloud.api.app:app --host 0.0.0.0 --port 9000",
                    "service": None,
                    "raw": "",
                },
                {
                    "bind": "127.0.0.1",
                    "port": 9000,
                    "pid": 202,
                    "process": "uvicorn",
                    "public_bind": False,
                    "ppid": 1,
                    "command": "uvicorn edu_cloud.api.app:app --host 127.0.0.1 --port 9000",
                    "service": "edu-cloud",
                    "raw": "",
                },
                {
                    "bind": "127.0.0.1",
                    "port": 8100,
                    "pid": 303,
                    "process": "python",
                    "public_bind": False,
                    "ppid": 1,
                    "command": "python -m llm_proxy",
                    "service": "llm-proxy",
                    "raw": "",
                },
            ],
            "expected": [
                {
                    "port": 9000,
                    "label": "edu-cloud API",
                    "service": "edu-cloud",
                    "required": True,
                    "present": True,
                    "listener_count": 2,
                    "public_bind": True,
                },
                {
                    "port": 8080,
                    "label": "Vite dev server",
                    "service": None,
                    "required": False,
                    "present": False,
                    "listener_count": 0,
                    "public_bind": False,
                },
                {
                    "port": 8100,
                    "label": "llm-proxy",
                    "service": "llm-proxy",
                    "required": False,
                    "present": True,
                    "listener_count": 1,
                    "public_bind": False,
                },
            ],
        },
        "ghost_processes": {
            "processes": [],
            "suspects": [
                {
                    "pid": 404,
                    "ppid": 1,
                    "command": "python -m uvicorn demo:app --reload --port 9001",
                    "service": None,
                    "raw": "ops 404 1 python -m uvicorn demo:app --reload --port 9001",
                }
            ],
        },
        "dist": {
            "status": "ok",
            "path": "/fake/frontend/dist",
            "index_exists": True,
            "index_readable": True,
            "version_path": "/fake/frontend/dist/version.json",
            "version": None,
            "version_error": "missing",
        },
        "db": {},
        "systemd": {
            "services": {
                "edu-cloud": {
                    "active": False,
                    "is_active": "inactive",
                    "main_pid": None,
                    "active_state": "inactive",
                    "sub_state": "dead",
                    "load_state": "loaded",
                    "main_pids": [],
                },
                "llm-proxy": {
                    "active": True,
                    "is_active": "active",
                    "main_pid": 303,
                    "active_state": "active",
                    "sub_state": "running",
                    "load_state": "loaded",
                    "main_pids": [303],
                },
                "edu-cloud-worker": {
                    "active": False,
                    "is_active": "failed",
                    "main_pid": None,
                    "active_state": "failed",
                    "sub_state": "failed",
                    "load_state": "loaded",
                    "main_pids": [],
                },
            }
        },
    }
    collector = tmp_path / "fake_live_fact_collector.py"
    collector.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "from pathlib import Path\n"
        f"FACTS = {json.dumps(facts, ensure_ascii=False)!r}\n"
        "Path(os.environ['COLLECTOR_MARKER']).write_text('called', encoding='utf-8')\n"
        "print(FACTS)\n",
        encoding="utf-8",
    )
    collector.chmod(0o755)
    marker.parent.mkdir(parents=True, exist_ok=True)
    return collector


def run_truth_doctor(project: Path, collector: Path, marker: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "TRUTH_DOCTOR_LIVE_FACT_COLLECTOR": str(collector),
        "TRUTH_DOCTOR_PYTHON": sys.executable,
        "COLLECTOR_MARKER": str(marker),
    }
    return subprocess.run(
        [str(TRUTH_DOCTOR), str(project), *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_truth_doctor_uses_live_fact_collector_and_keeps_db_gate() -> None:
    script = TRUTH_DOCTOR.read_text(encoding="utf-8")

    assert "governance/live_fact_collector.py" in script
    assert "TRUTH_DOCTOR_LIVE_FACT_COLLECTOR" in script
    assert 'db_doctor.py" --json' in script
    assert 'ss -tlnp "sport = :$port"' not in script
    assert 'ps aux | grep -E "$GHOST_PATTERNS"' not in script
    assert "systemctl is-active --quiet" not in script
    assert "pgrep -f 'uvicorn.*9000'" not in script


def test_truth_doctor_json_renders_collector_facts_without_regressing_db_gate(tmp_path: Path) -> None:
    project = make_fake_project(tmp_path)
    marker = tmp_path / "collector.marker"
    collector = make_fake_collector(tmp_path, marker)

    result = run_truth_doctor(project, collector, marker, "--json")

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == "called"

    payload = json.loads(result.stdout)
    summaries = [issue["summary"] for issue in payload["issues"]]

    assert payload["schema"] == "guardian.doctor.v1"
    assert "port 9000 (edu-cloud API) has 2 listeners" in summaries
    assert "port 9000 (edu-cloud API) is bound to 0.0.0.0" in summaries
    assert "port 9000 (edu-cloud API) listener PID=101 is an orphan" in summaries
    assert any(summary.startswith("ghost PID=404 (uvicorn") for summary in summaries)
    assert "frontend/dist/version.json missing" in summaries
    assert "edu-cloud.service inactive while uvicorn :9000 is running manually" in summaries
    assert not any(issue["issue_code"] == "DB_SCHEMA_DRIFT" for issue in payload["issues"])


def test_truth_doctor_text_renders_collector_facts_without_regressing_db_gate(tmp_path: Path) -> None:
    project = make_fake_project(tmp_path)
    marker = tmp_path / "collector.marker"
    collector = make_fake_collector(tmp_path, marker)

    result = run_truth_doctor(project, collector, marker)

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == "called"

    output = strip_ansi(result.stdout)
    assert "[Ports]" in output
    assert "port 9000 (edu-cloud API): 2 listeners detected (possible conflict)" in output
    assert "port 9000 (edu-cloud API): PID=101 bound to 0.0.0.0" in output
    assert "PID=101 is an orphan (PPID=1)" in output
    assert "port 8080 (Vite dev server): nobody listening" in output
    assert "ghost PID=404 (uvicorn" in output
    assert "dist/version.json missing" in output
    assert "edu-cloud.service: inactive" in output
    assert "but uvicorn :9000 is running manually" in output
    assert "ORM-DB aligned: 7 tables, alembic test" in output
