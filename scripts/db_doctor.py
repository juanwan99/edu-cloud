#!/usr/bin/env python3
"""DB Doctor — ORM vs SQLite schema drift detector.

Usage:
    python scripts/db_doctor.py                 # startup mode (default)
    python scripts/db_doctor.py --strict        # strict mode (for migration wrapper)
    python scripts/db_doctor.py --json          # JSON output for truth doctor

Exit codes:
    0 = clean
    1 = hard failures found
    2 = warnings only (startup mode passes, strict mode fails)
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

ALLOWLIST_TABLES = {
    "alembic_version",
}

ALLOWLIST_TABLE_PATTERNS = [
    re.compile(r"^_backup_.*_\d{8}$"),
]


@dataclass
class Finding:
    severity: str  # HARD / WARN
    category: str  # missing_table / missing_column / orphan_table / orphan_column / alembic_mismatch
    table: str
    column: str = ""
    detail: str = ""


@dataclass
class Report:
    db_path: str = ""
    alembic_version: str = ""
    orm_tables: int = 0
    db_tables: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def hard_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "HARD")

    @property
    def warn_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "WARN")


def _is_allowlisted(table_name: str) -> bool:
    if table_name in ALLOWLIST_TABLES:
        return True
    return any(p.match(table_name) for p in ALLOWLIST_TABLE_PATTERNS)


def import_all_models():
    """Import all ORM models so Base.metadata is populated."""
    from edu_cloud.models.base import Base  # noqa: F401

    import_errors: list[str] = []

    models_dir = PROJECT_ROOT / "src" / "edu_cloud" / "modules"
    for models_py in models_dir.rglob("models.py"):
        rel = models_py.relative_to(PROJECT_ROOT / "src")
        mod_path = str(rel).replace(os.sep, ".").removesuffix(".py")
        try:
            importlib.import_module(mod_path)
        except Exception as e:
            import_errors.append(f"{mod_path}: {e}")

    # Also import AI and core models referenced in alembic/env.py
    for mod in [
        "edu_cloud.ai.models",
        "edu_cloud.models.school",
        "edu_cloud.models.user",
        "edu_cloud.models.user_role",
        "edu_cloud.models.document",
        "edu_cloud.models.approval",
        "edu_cloud.models.calendar",
        "edu_cloud.models.notification",
        "edu_cloud.models.llm_slot",
        "edu_cloud.models.agent_profile",
        "edu_cloud.models.agent_memory",
        "edu_cloud.models.guardian",
        "edu_cloud.models.workflow",
        "edu_cloud.models.agent_finding",
        "edu_cloud.models.agent_snapshot",
        "edu_cloud.models.scope_version",
        "edu_cloud.models.school_settings",
        "edu_cloud.models.teacher_assignment",
        "edu_cloud.models.subject_selection",
        "edu_cloud.models.capability",
        "edu_cloud.models.audit_log",
        "edu_cloud.models.memory",
        "edu_cloud.models.score_segment",
        "edu_cloud.models.grade",
        "edu_cloud.models.teaching_plan",
    ]:
        try:
            importlib.import_module(mod)
        except Exception as e:
            import_errors.append(f"{mod}: {e}")

    if import_errors:
        Base._doctor_import_errors = import_errors
    return Base


def get_db_schema(db_path: str) -> dict[str, set[str]]:
    """Return {table_name: {col_names}} from SQLite."""
    conn = sqlite3.connect(db_path)
    tables = {}
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info([{name}])").fetchall()}
        tables[name] = cols
    conn.close()
    return tables


def get_alembic_version(db_path: str) -> str:
    """Read alembic_version from DB."""
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


def get_orm_schema(base) -> dict[str, set[str]]:
    """Return {table_name: {col_names}} from ORM metadata."""
    tables = {}
    for table in base.metadata.tables.values():
        tables[table.name] = {c.name for c in table.columns}
    return tables


def run_doctor(db_path: str, strict: bool = False) -> Report:
    report = Report(db_path=db_path)

    Base = import_all_models()
    import_errors = getattr(Base, "_doctor_import_errors", [])
    for err in import_errors:
        report.findings.append(Finding(
            severity="HARD" if strict else "WARN",
            category="import_error",
            table="(model import)",
            detail=f"Failed to import ORM model: {err}",
        ))
    orm_schema = get_orm_schema(Base)
    db_schema = get_db_schema(db_path)

    report.orm_tables = len(orm_schema)
    report.db_tables = len(db_schema)
    report.alembic_version = get_alembic_version(db_path)

    # 1. ORM tables missing from DB → HARD (will cause 500)
    for table in sorted(set(orm_schema) - set(db_schema)):
        report.findings.append(Finding(
            severity="HARD",
            category="missing_table",
            table=table,
            detail=f"ORM declares table '{table}' ({len(orm_schema[table])} cols) but DB has no such table",
        ))

    # 2. ORM columns missing from DB → HARD (will cause 500)
    for table in sorted(set(orm_schema) & set(db_schema)):
        orm_cols = orm_schema[table]
        db_cols = db_schema[table]
        for col in sorted(orm_cols - db_cols):
            report.findings.append(Finding(
                severity="HARD",
                category="missing_column",
                table=table,
                column=col,
                detail=f"ORM declares '{table}.{col}' but DB table lacks this column",
            ))

    # 3. DB-only tables not in ORM
    for table in sorted(set(db_schema) - set(orm_schema)):
        if _is_allowlisted(table):
            continue
        report.findings.append(Finding(
            severity="WARN" if not strict else "HARD",
            category="orphan_table",
            table=table,
            detail=f"DB has table '{table}' ({len(db_schema[table])} cols) not declared in ORM",
        ))

    # 4. DB-only columns in shared tables
    for table in sorted(set(orm_schema) & set(db_schema)):
        orm_cols = orm_schema[table]
        db_cols = db_schema[table]
        for col in sorted(db_cols - orm_cols):
            report.findings.append(Finding(
                severity="WARN",
                category="orphan_column",
                table=table,
                column=col,
                detail=f"DB has '{table}.{col}' not declared in ORM (possible migration residue)",
            ))

    return report


def print_report(report: Report, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps({
            "db_path": report.db_path,
            "alembic_version": report.alembic_version,
            "orm_tables": report.orm_tables,
            "db_tables": report.db_tables,
            "hard": report.hard_count,
            "warn": report.warn_count,
            "findings": [
                {"severity": f.severity, "category": f.category,
                 "table": f.table, "column": f.column, "detail": f.detail}
                for f in report.findings
            ],
        }, indent=2, ensure_ascii=False))
        return

    print(f"DB Doctor — {report.db_path}")
    print(f"  Alembic version: {report.alembic_version}")
    print(f"  ORM tables: {report.orm_tables}, DB tables: {report.db_tables}")
    print()

    if not report.findings:
        print("  ✓ No drift detected")
        return

    for f in report.findings:
        icon = "✗" if f.severity == "HARD" else "?"
        loc = f"{f.table}.{f.column}" if f.column else f.table
        print(f"  {icon} [{f.severity}] {f.category}: {loc}")
        print(f"    {f.detail}")

    print()
    print(f"  Summary: {report.hard_count} HARD, {report.warn_count} WARN")


def main():
    parser = argparse.ArgumentParser(description="DB Doctor — ORM vs DB schema drift detector")
    parser.add_argument("--strict", action="store_true", help="Strict mode: orphan tables/columns also HARD fail")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--db", default=None, help="DB path (default: from .env / edu_cloud.db)")
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)

    db_path = args.db
    if not db_path:
        try:
            from edu_cloud.config import settings
            url = settings.DATABASE_URL
            if "sqlite" in url:
                db_path = url.split("///")[-1]
            else:
                print("ERROR: db_doctor only supports SQLite databases", file=sys.stderr)
                sys.exit(1)
        except Exception:
            db_path = "edu_cloud.db"

    if not os.path.exists(db_path):
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    report = run_doctor(db_path, strict=args.strict)
    print_report(report, as_json=args.json)

    if report.hard_count > 0:
        sys.exit(1)
    if args.strict and report.warn_count > 0:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
