"""Governance coverage for local backup automation."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import sys

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = PROJECT_ROOT / "deploy" / "backup" / "edu-cloud-backup.py"
SERVICE_FILE = PROJECT_ROOT / "deploy" / "systemd" / "edu-cloud-backup.service"
TIMER_FILE = PROJECT_ROOT / "deploy" / "systemd" / "edu-cloud-backup.timer"
SCOPE_FILE = PROJECT_ROOT / "control" / "steward" / "scopes" / "keel-backup-automation-2026-07-02.yml"


EXPECTED_ALLOWED_PATHS = [
    "deploy/backup/edu-cloud-backup.py",
    "deploy/backup/README.md",
    "deploy/systemd/edu-cloud-backup.service",
    "deploy/systemd/edu-cloud-backup.timer",
    "tests/governance/test_backup_automation.py",
    "control/steward/scopes/keel-backup-automation-2026-07-02.yml",
]


def _run_backup(args: list[str], *, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("DATABASE_URL", "EDU_CLOUD_BACKUP_DIR", "BACKUP_DIR", "EDU_CLOUD_BACKUP_MODE", "PG_DUMP_BIN"):
        env.pop(key, None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(BACKUP_SCRIPT), *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def test_backup_script_exposes_expected_cli_arguments():
    result = _run_backup(["--help"])

    assert result.returncode == 0
    assert "--target-dir" in result.stdout
    assert "--database-url" in result.stdout
    assert "--mode" in result.stdout
    assert "--pg-dump-bin" in result.stdout


def test_backup_script_fails_loud_without_database_url(tmp_path: Path):
    result = _run_backup(["--target-dir", str(tmp_path)])

    assert result.returncode != 0
    assert "DATABASE_URL is required" in result.stderr


def test_backup_script_fails_loud_when_target_directory_is_missing(tmp_path: Path):
    db_file = tmp_path / "edu_cloud.db"
    db_file.write_bytes(b"sqlite database bytes")

    result = _run_backup(
        [
            "--database-url",
            _sqlite_url(db_file),
            "--target-dir",
            str(tmp_path / "missing-backups"),
        ]
    )

    assert result.returncode != 0
    assert "backup target directory does not exist" in result.stderr


def test_backup_script_copies_sqlite_file_without_real_database(tmp_path: Path):
    db_file = tmp_path / "edu_cloud.db"
    db_file.write_bytes(b"sqlite database bytes")
    target_dir = tmp_path / "backups"
    target_dir.mkdir()

    result = _run_backup(
        [
            "--database-url",
            _sqlite_url(db_file),
            "--target-dir",
            str(target_dir),
            "--timestamp",
            "20260702T000000Z",
        ]
    )

    backup_file = target_dir / "edu_cloud-20260702T000000Z.sqlite"
    assert result.returncode == 0, result.stderr
    assert backup_file.read_bytes() == b"sqlite database bytes"
    assert "backup created:" in result.stdout
    assert "DATABASE_URL" not in result.stdout


def test_backup_script_fails_loud_when_pg_dump_is_missing(tmp_path: Path):
    target_dir = tmp_path / "backups"
    target_dir.mkdir()

    result = _run_backup(
        [
            "--database-url",
            "postgresql://edu_cloud:pw-token@127.0.0.1:5432/edu_cloud",
            "--target-dir",
            str(target_dir),
            "--pg-dump-bin",
            str(tmp_path / "missing-pg-dump"),
        ]
    )

    assert result.returncode != 0
    assert "pg_dump executable not found" in result.stderr
    assert "pw-token" not in result.stderr


def test_backup_script_invokes_fake_pg_dump_without_real_database(tmp_path: Path):
    target_dir = tmp_path / "backups"
    target_dir.mkdir()
    fake_dir = tmp_path / "bin"
    fake_dir.mkdir()
    _write_fake_pg_dump(fake_dir)

    result = _run_backup(
        [
            "--database-url",
            "postgresql://edu_cloud:pw-token@127.0.0.1:5432/edu_cloud",
            "--target-dir",
            str(target_dir),
            "--timestamp",
            "20260702T000001Z",
        ],
        env_overrides={"PATH": str(fake_dir) + os.pathsep + os.environ.get("PATH", "")},
    )

    backup_file = target_dir / "edu_cloud-20260702T000001Z.dump"
    assert result.returncode == 0, result.stderr
    assert backup_file.read_text(encoding="utf-8").strip() == "fake pg_dump output"
    assert "pw-token" not in result.stdout
    assert "pw-token" not in result.stderr


def _write_fake_pg_dump(fake_dir: Path) -> None:
    if os.name == "nt":
        fake_py = fake_dir / "fake_pg_dump.py"
        fake_py.write_text(
            "from pathlib import Path\n"
            "import sys\n\n"
            "for index, arg in enumerate(sys.argv):\n"
            "    if arg == '--file' and index + 1 < len(sys.argv):\n"
            "        Path(sys.argv[index + 1]).write_text('fake pg_dump output\\n', encoding='utf-8')\n"
            "        raise SystemExit(0)\n"
            "raise SystemExit(3)\n",
            encoding="utf-8",
        )
        fake_pg_dump = fake_dir / "pg_dump.cmd"
        fake_pg_dump.write_text(
            "@echo off\r\n"
            f"\"{sys.executable}\" \"{fake_py}\" %*\r\n",
            encoding="utf-8",
        )
        return

    fake_pg_dump = fake_dir / "pg_dump"
    fake_pg_dump.write_text(
        "#!/bin/sh\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = \"--file\" ]; then\n"
        "    shift\n"
        "    printf 'fake pg_dump output\\n' > \"$1\"\n"
        "    exit 0\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "exit 3\n",
        encoding="utf-8",
    )
    fake_pg_dump.chmod(fake_pg_dump.stat().st_mode | stat.S_IXUSR)


def test_systemd_units_point_to_backup_script_and_timer_target():
    service = SERVICE_FILE.read_text(encoding="utf-8")
    timer = TIMER_FILE.read_text(encoding="utf-8")

    assert "EnvironmentFile=-/home/ops/projects/edu-cloud/.env" in service
    assert (
        "ExecStart=/home/ops/projects/edu-cloud/.venv/bin/python "
        "/home/ops/projects/edu-cloud/deploy/backup/edu-cloud-backup.py "
        "--target-dir /home/ops/backups/edu-cloud"
    ) in service
    assert "ReadWritePaths=/home/ops/backups/edu-cloud /home/ops/logs" in service
    assert "Unit=edu-cloud-backup.service" in timer
    assert "Persistent=true" in timer


def test_scope_allowed_paths_are_exact_and_forbidden_paths_stay_outside_scope():
    scope = yaml.safe_load(SCOPE_FILE.read_text(encoding="utf-8"))

    assert scope["scope_id"] == "keel-backup-automation-2026-07-02"
    assert scope["allowed_paths"] == EXPECTED_ALLOWED_PATHS
    forbidden_paths = set(scope["forbidden_paths"])
    for path in ("src/", "frontend/", "scripts/", ".github/", "docs/", "alembic/", "AGENTS.md", "CLAUDE.md"):
        assert path in forbidden_paths
    assert "deploy/backup/" not in forbidden_paths
    assert "tests/governance/test_backup_automation.py" not in forbidden_paths
