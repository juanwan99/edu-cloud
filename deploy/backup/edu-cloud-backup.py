#!/usr/bin/env python3
"""Local edu-cloud database backup helper.

This script is intentionally local-only. It reads DATABASE_URL from the
environment or CLI, writes to an already-created local target directory, and
fails loudly when required configuration or local tools are missing.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


POSTGRES_SCHEMES = {"postgres", "postgresql"}
SQLITE_SCHEME_PREFIX = "sqlite"
TIMESTAMP_PATTERN = re.compile(r"^\d{8}T\d{6}Z$")


class BackupError(RuntimeError):
    """Configuration or backup execution failed."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a local edu-cloud database backup.")
    parser.add_argument(
        "--target-dir",
        default=os.environ.get("EDU_CLOUD_BACKUP_DIR") or os.environ.get("BACKUP_DIR"),
        help="Existing local directory where backup files are written.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Database URL. Defaults to DATABASE_URL from the environment.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "sqlite", "postgresql"),
        default=os.environ.get("EDU_CLOUD_BACKUP_MODE", "auto"),
        help="Backup backend. auto infers from DATABASE_URL.",
    )
    parser.add_argument(
        "--pg-dump-bin",
        default=os.environ.get("PG_DUMP_BIN", "pg_dump"),
        help="pg_dump executable for PostgreSQL backups.",
    )
    parser.add_argument(
        "--timestamp",
        help="UTC timestamp for deterministic filenames, formatted as YYYYMMDDTHHMMSSZ.",
    )
    return parser


def run_backup(args: argparse.Namespace) -> list[Path]:
    target_dir = _resolve_target_dir(args.target_dir)
    database_url = _require_database_url(args.database_url)
    timestamp = _resolve_timestamp(args.timestamp)
    backend = _resolve_backend(database_url, args.mode)

    if backend == "sqlite":
        source = _sqlite_path_from_url(database_url)
        return _backup_sqlite(source, target_dir, timestamp)

    pg_dump_url = _pg_dump_url(database_url)
    return [_backup_postgresql(pg_dump_url, target_dir, timestamp, args.pg_dump_bin)]


def _resolve_target_dir(value: str | None) -> Path:
    if not value:
        raise BackupError("backup target directory is required; pass --target-dir or EDU_CLOUD_BACKUP_DIR")
    target_dir = Path(value).expanduser()
    if not target_dir.exists():
        raise BackupError(f"backup target directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise BackupError(f"backup target path is not a directory: {target_dir}")
    return target_dir


def _require_database_url(value: str | None) -> str:
    if not value:
        raise BackupError("DATABASE_URL is required; pass --database-url or set DATABASE_URL")
    return value.strip()


def _resolve_timestamp(value: str | None) -> str:
    if value:
        if not TIMESTAMP_PATTERN.match(value):
            raise BackupError("timestamp must be formatted as YYYYMMDDTHHMMSSZ")
        return value
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _resolve_backend(database_url: str, mode: str) -> str:
    scheme = urlsplit(database_url).scheme
    inferred: str
    if scheme.startswith(SQLITE_SCHEME_PREFIX):
        inferred = "sqlite"
    elif _base_scheme(scheme) in POSTGRES_SCHEMES:
        inferred = "postgresql"
    else:
        raise BackupError(f"unsupported DATABASE_URL scheme: {scheme or '<missing>'}")

    if mode != "auto" and mode != inferred:
        raise BackupError(f"--mode {mode} does not match DATABASE_URL backend {inferred}")
    return inferred


def _sqlite_path_from_url(database_url: str) -> Path:
    scheme, sep, rest = database_url.partition(":")
    if not sep or not scheme.startswith(SQLITE_SCHEME_PREFIX):
        raise BackupError("SQLite backup requires a sqlite:/// file DATABASE_URL")
    if not rest.startswith("///"):
        raise BackupError("SQLite backup requires a sqlite:/// file DATABASE_URL")

    raw_path = rest[3:].split("?", 1)[0].split("#", 1)[0]
    if not raw_path or raw_path == ":memory:":
        raise BackupError("SQLite backup requires a file path; in-memory databases are not supported")

    source = Path(raw_path).expanduser()
    if not source.is_absolute():
        source = Path.cwd() / source
    return source


def _backup_sqlite(source: Path, target_dir: Path, timestamp: str) -> list[Path]:
    if not source.exists():
        raise BackupError(f"SQLite database file does not exist: {source}")
    if not source.is_file():
        raise BackupError(f"SQLite database path is not a file: {source}")

    backup_path = target_dir / f"{_safe_name(source.stem)}-{timestamp}.sqlite"
    _copy_file_atomic(source, backup_path)

    copied = [backup_path]
    for sidecar_suffix in ("-wal", "-shm"):
        sidecar = Path(str(source) + sidecar_suffix)
        if sidecar.exists():
            sidecar_target = target_dir / f"{backup_path.name}{sidecar_suffix}"
            _copy_file_atomic(sidecar, sidecar_target)
            copied.append(sidecar_target)
    return copied


def _copy_file_atomic(source: Path, target: Path) -> None:
    if target.exists():
        raise BackupError(f"backup file already exists: {target}")
    temp_target = target.with_name(target.name + ".tmp")
    try:
        shutil.copy2(source, temp_target)
        os.replace(temp_target, target)
    except OSError as exc:
        raise BackupError(f"failed to copy backup file to {target}: {exc}") from exc
    finally:
        if temp_target.exists():
            temp_target.unlink()


def _pg_dump_url(database_url: str) -> str:
    scheme, sep, rest = database_url.partition("://")
    if not sep:
        raise BackupError("PostgreSQL backup requires a URL DATABASE_URL")
    base = _base_scheme(scheme)
    if base not in POSTGRES_SCHEMES:
        raise BackupError("PostgreSQL backup requires a postgres:// or postgresql:// DATABASE_URL")
    return f"{base}://{rest}"


def _backup_postgresql(database_url: str, target_dir: Path, timestamp: str, pg_dump_bin: str) -> Path:
    pg_dump = _resolve_pg_dump(pg_dump_bin)
    database_name = _postgres_database_name(database_url)
    backup_path = target_dir / f"{_safe_name(database_name)}-{timestamp}.dump"
    if backup_path.exists():
        raise BackupError(f"backup file already exists: {backup_path}")

    temp_path = backup_path.with_name(backup_path.name + ".tmp")
    command = [
        pg_dump,
        "--format=custom",
        "--no-owner",
        "--file",
        str(temp_path),
        database_url,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise BackupError("pg_dump timed out after 300 seconds") from exc
    except OSError as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise BackupError(f"failed to execute pg_dump: {exc}") from exc

    if result.returncode != 0:
        if temp_path.exists():
            temp_path.unlink()
        stderr = _sanitize(result.stderr.strip(), database_url)
        detail = f": {stderr}" if stderr else ""
        raise BackupError(f"pg_dump failed with exit code {result.returncode}{detail}")
    if not temp_path.exists():
        raise BackupError("pg_dump completed without creating the expected backup file")

    os.replace(temp_path, backup_path)
    return backup_path


def _resolve_pg_dump(pg_dump_bin: str) -> str:
    candidate = Path(pg_dump_bin)
    if candidate.is_absolute() or candidate.parent != Path("."):
        if not candidate.exists():
            raise BackupError(f"pg_dump executable not found: {pg_dump_bin}")
        return str(candidate)

    resolved = shutil.which(pg_dump_bin)
    if not resolved:
        raise BackupError(f"pg_dump executable not found on PATH: {pg_dump_bin}")
    return resolved


def _postgres_database_name(database_url: str) -> str:
    parsed = urlsplit(database_url)
    name = parsed.path.rsplit("/", 1)[-1]
    return name or "postgresql"


def _base_scheme(scheme: str) -> str:
    return scheme.split("+", 1)[0]


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return cleaned or "database"


def _sanitize(value: str, database_url: str) -> str:
    if not value:
        return value
    redacted = value.replace(database_url, "<DATABASE_URL>")
    parsed = urlsplit(database_url)
    if parsed.password:
        redacted = redacted.replace(parsed.password, "<redacted>")
    return redacted


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        created = run_backup(args)
    except BackupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for path in created:
        print(f"backup created: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
