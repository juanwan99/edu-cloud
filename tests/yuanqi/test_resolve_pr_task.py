import json
import subprocess
import sys


def test_resolve_pr_task_reads_task_id_from_pr_body(tmp_path):
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "pull_request": {
                    "body": (
                        "Summary\n"
                        "Yuanqi-Task: yq-20260625-fixgate-01\n"
                        "More details\n"
                    )
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/yuanqi/resolve_pr_task.py",
            "--event",
            str(event_path),
            "--head-ref",
            "feat/fixgate",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "yq-20260625-fixgate-01"


def test_resolve_pr_task_fails_without_task_line(tmp_path):
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps({"pull_request": {"body": "Summary only\n"}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/yuanqi/resolve_pr_task.py",
            "--event",
            str(event_path),
            "--head-ref",
            "feat/fixgate",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "PR 必须声明 Yuanqi-Task: <id>" in result.stderr
