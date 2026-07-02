"""Fail-loud coverage for the DB migration wrapper."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_db_migrate_postgresql_url_fails_loud_before_sqlite_fallback(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": "postgresql://edu_cloud:secret@127.0.0.1:5432/edu_cloud",
            "SECRET_KEY": "test-secret-key",
            "ENCRYPTION_KEY": "test-encryption-key",
        }
    )

    if os.name == "nt":
        shim_dir = tmp_path / "pyshim"
        shim_dir.mkdir()
        (shim_dir / "fcntl.py").write_text(
            "LOCK_EX = 2\n"
            "LOCK_NB = 4\n"
            "LOCK_UN = 8\n\n"
            "def flock(fd, op):\n"
            "    return None\n",
            encoding="utf-8",
        )
        pythonpath = [str(shim_dir)]
        if env.get("PYTHONPATH"):
            pythonpath.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "db_migrate"), "head"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "PostgreSQL" in output
    assert "pg_dump" in output
    assert "DB not found: edu_cloud.db" not in output
    assert "Backing up" not in output
