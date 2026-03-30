"""Alembic migration smoke test — 验证迁移文件可执行且表集合与 ORM 一致。

TG-02: 测试 conftest 用 Base.metadata.create_all() 建表完全绕过 Alembic，
无法验证迁移文件本身的正确性（FK 顺序、约束声明等）。
本测试用 subprocess 在空 SQLite 上执行 alembic upgrade head，然后对比表集合。
使用 subprocess 避免 settings.DATABASE_URL 缓存覆盖问题。
"""
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_alembic(db_path, *args):
    """Run alembic command via subprocess with SQLite DATABASE_URL override."""
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result


@pytest.fixture
def migration_db(tmp_path):
    """Run Alembic upgrade head on a fresh SQLite database, return engine."""
    db_path = tmp_path / "test_migration.db"
    _run_alembic(db_path, "upgrade", "head")

    engine = create_engine(f"sqlite:///{db_path}")
    yield engine
    engine.dispose()


def test_migration_creates_all_expected_tables(migration_db):
    """alembic upgrade head 应创建与 Base.metadata 一致的表集合。"""
    from edu_cloud.models.base import Base
    # Force all model imports (same as conftest.py)
    import edu_cloud.models.school  # noqa: F401
    import edu_cloud.models.user  # noqa: F401
    import edu_cloud.models.user_role  # noqa: F401
    import edu_cloud.models.joint_exam  # noqa: F401
    import edu_cloud.models.student  # noqa: F401
    import edu_cloud.models.class_group  # noqa: F401
    import edu_cloud.models.exam  # noqa: F401
    import edu_cloud.models.ai_session  # noqa: F401
    import edu_cloud.models.document  # noqa: F401
    import edu_cloud.models.approval  # noqa: F401
    import edu_cloud.models.calendar  # noqa: F401
    import edu_cloud.models.notification  # noqa: F401
    import edu_cloud.core.models.llm_slot  # noqa: F401
    import edu_cloud.modules.card.models  # noqa: F401
    import edu_cloud.modules.scan.models  # noqa: F401
    import edu_cloud.modules.grading.models  # noqa: F401
    import edu_cloud.modules.marking.models  # noqa: F401
    import edu_cloud.modules.knowledge.models  # noqa: F401
    import edu_cloud.modules.bank.models  # noqa: F401
    import edu_cloud.modules.profile.models  # noqa: F401
    import edu_cloud.models.school_settings  # noqa: F401
    import edu_cloud.models.teacher_assignment  # noqa: F401
    import edu_cloud.models.subject_selection  # noqa: F401
    import edu_cloud.models.capability  # noqa: F401
    import edu_cloud.models.audit_log  # noqa: F401

    inspector = inspect(migration_db)
    migration_tables = set(inspector.get_table_names())
    migration_tables.discard("alembic_version")

    orm_tables = set(Base.metadata.tables.keys())

    missing_in_migration = orm_tables - migration_tables
    extra_in_migration = migration_tables - orm_tables

    assert not missing_in_migration, (
        f"ORM 定义了但迁移未创建的表: {missing_in_migration}"
    )
    assert not extra_in_migration, (
        f"迁移创建了但 ORM 未定义的表: {extra_in_migration}"
    )


def test_migration_head_is_single():
    """确保只有一个 Alembic head（无分叉）。"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    ini_path = os.path.join(PROJECT_ROOT, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(PROJECT_ROOT, "alembic"))

    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected single head, got {len(heads)}: {heads}"


def test_migration_downgrade_is_clean(tmp_path):
    """alembic upgrade head → downgrade base 应清除所有表。"""
    db_path = tmp_path / "test_downgrade.db"
    _run_alembic(db_path, "upgrade", "head")
    _run_alembic(db_path, "downgrade", "base")

    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    remaining = set(inspector.get_table_names())
    remaining.discard("alembic_version")
    engine.dispose()

    assert not remaining, f"downgrade 后仍残留表: {remaining}"
