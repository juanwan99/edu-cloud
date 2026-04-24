"""S1-A bank_question extension migration smoke tests.

覆盖 ORC-S1A-001（linear chain 首环）/ ORC-S1A-003（只加不改）/ ORC-S1A-004（双方言）。
refs: docs/plans/2026-04-24-haofenshu-s1-bank-plan.md Task 3
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _alembic_env(db_url: str) -> dict:
    env = os.environ.copy()
    env['DATABASE_URL'] = db_url
    return env


@pytest.fixture()
def sqlite_db(tmp_path):
    """Per-test SQLite file DB（需要文件路径以便 alembic subprocess 访问）."""
    db_file = tmp_path / 's1a_bank.db'
    yield f'sqlite:///{db_file}'


def _run_alembic(cmd_args: list[str], db_url: str) -> subprocess.CompletedProcess:
    """运行 alembic CLI（用 sync URL 简化）."""
    return subprocess.run(
        [sys.executable, '-m', 'alembic', *cmd_args],
        cwd=PROJECT_ROOT,
        env={**os.environ, 'DATABASE_URL': db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')},
        capture_output=True,
        text=True,
    )


def test_migration_file_exists_and_down_revision_is_conduct_head():
    """INV-S1A-002 机械化：打开 S1-A migration 文件，直接读 down_revision 字符串.

    2026-04-24 R2 后基线漂移修正：head 从 '36e25241e55d'（plan R1/R2 时点实测）
    上移到 'a8c7d2e4f135'（conduct updated_at + FK indexes migration，commit 1716bfe 引入）。
    """
    versions_dir = os.path.join(PROJECT_ROOT, 'alembic', 'versions')
    matches = [f for f in os.listdir(versions_dir) if 's1a_bank_question_extension' in f]
    assert len(matches) == 1, f"Expected exactly 1 S1-A migration file, got {matches}"

    with open(os.path.join(versions_dir, matches[0])) as fp:
        content = fp.read()
    assert "down_revision: Union[str, Sequence[str], None] = 'a8c7d2e4f135'" in content, \
        "ORC-S1A-001 违反：down_revision 必须是 'a8c7d2e4f135'"


def test_migration_chain_head_is_single(sqlite_db):
    """INV-S1A-003 机械化：upgrade 到 head 后 alembic heads 仍返回 1 行."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0, f"upgrade failed: {r.stderr}"

    r = _run_alembic(['heads'], sqlite_db)
    assert r.returncode == 0
    # heads 输出形如 "{slug} (head)\n"；过滤空行后应只有 1 行
    non_empty_lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(non_empty_lines) == 1, f"Expected 1 head, got {len(non_empty_lines)}: {r.stdout}"


def test_new_columns_added_and_nullable(sqlite_db):
    """INV-S1A-001 机械化：upgrade 后 5 新列存在且 is_nullable=True."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name']: c for c in insp.get_columns('bank_questions')}

    for name in ('source', 'explanation', 'knowledge_point_ids', 'difficulty_level', 'grade_id'):
        assert name in cols, f"Missing new column: {name}"
        assert cols[name]['nullable'] is True, f"Column {name} must be nullable"


def test_existing_columns_unchanged_after_upgrade(sqlite_db):
    """ORC-S1A-003 机械化：tags 仍是 JSON 类型，bloom_level 仍是精确 VARCHAR(20)。

    R1 F-S1A-03 修正：bloom_level 断言从宽松 substring 匹配改为精确 length==20，
    错误的 VARCHAR(10)/VARCHAR(255) 不再漏过。
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name']: c for c in insp.get_columns('bank_questions')}

    assert 'tags' in cols, "tags 列被移除"
    assert 'bloom_level' in cols, "bloom_level 列被移除"

    # tags: SQLAlchemy inspect 对 SQLite 下 JSON 列返回 JSON type 或 TEXT 基类；
    # 取 .__class__.__name__ 做稳定断言
    tags_type_name = cols['tags']['type'].__class__.__name__.upper()
    assert 'JSON' in tags_type_name, \
        f"tags type changed from JSON to {cols['tags']['type']!r}"

    # bloom_level: 精确锁定 VARCHAR(20) —— 读 SQLAlchemy Type 的 .length 属性
    # initial_merged_schema.py:514 是 Column('bloom_level', String(length=20)...)
    bloom_type = cols['bloom_level']['type']
    bloom_length = getattr(bloom_type, 'length', None)
    assert bloom_length == 20, \
        f"bloom_level type.length changed: expected 20, got {bloom_length!r} (full type={bloom_type!r})"
    # 类型类名也要是 String/VARCHAR 家族（不是 Enum/Integer/其他）
    bloom_class = bloom_type.__class__.__name__.upper()
    assert 'STRING' in bloom_class or 'VARCHAR' in bloom_class, \
        f"bloom_level type class changed: expected String/VARCHAR, got {bloom_class!r}"


def test_existing_data_preserved_through_migration(sqlite_db):
    """F003 修正核心：INSERT 带齐必填列 → upgrade → 数据保留 + 新列默认 NULL."""
    # 1) upgrade 到 head 之前一个 revision（conduct updated_at + FK indexes 引入点 a8c7d2e4f135）
    #    注：S1-A 前 head 是 a8c7d2e4f135（2026-04-24 R2 后基线漂移修正），
    #    所以先 upgrade 到 head 之前的一环；a8c7d2e4f135 的 upstream 是 36e25241e55d
    r = _run_alembic(['upgrade', 'a8c7d2e4f135'], sqlite_db)
    assert r.returncode == 0, f"upgrade to a8c7d2e4f135 failed: {r.stderr}"

    # 2) 预置数据（F003：INSERT 必填列全齐）
    engine = create_engine(sqlite_db)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO bank_questions (
                id, school_id, question_type, max_score, sample_count,
                tags, bloom_level, created_at, updated_at
            ) VALUES (
                :id, :school_id, :qtype, :mscore, :scount,
                :tags, :bloom, :created, :updated
            )
        """), {
            'id': str(uuid.uuid4()),
            'school_id': 'test-school-uuid',
            'qtype': 'essay',
            'mscore': 10.0,
            'scount': 0,
            'tags': '[]',
            'bloom': 'apply',
            'created': datetime.now(timezone.utc).isoformat(),
            'updated': datetime.now(timezone.utc).isoformat(),
        })

    # 3) upgrade 到 S1-A new head
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0, f"upgrade to S1-A head failed: {r.stderr}"

    # 4) 验证数据保留 + 5 新列 NULL
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT question_type, max_score, sample_count, tags, bloom_level,
                   source, explanation, knowledge_point_ids, difficulty_level, grade_id
            FROM bank_questions LIMIT 1
        """)).fetchone()

    assert row is not None, "预置数据丢失"
    assert row.question_type == 'essay'
    assert row.max_score == 10.0
    assert row.sample_count == 0
    assert row.source is None
    assert row.explanation is None
    assert row.knowledge_point_ids is None
    assert row.difficulty_level is None
    assert row.grade_id is None


def test_upgrade_then_downgrade_is_clean(sqlite_db):
    """INV-S1A-003 配对：downgrade 后 5 新列消失且不破坏现有列."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    r = _run_alembic(['downgrade', '-1'], sqlite_db)
    assert r.returncode == 0, f"downgrade failed: {r.stderr}"

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name'] for c in insp.get_columns('bank_questions')}

    for removed in ('source', 'explanation', 'knowledge_point_ids', 'difficulty_level', 'grade_id'):
        assert removed not in cols, f"Column {removed} still present after downgrade"
    # 原字段仍在
    for kept in ('tags', 'bloom_level', 'sample_count', 'school_id'):
        assert kept in cols, f"Existing column {kept} missing after downgrade"
