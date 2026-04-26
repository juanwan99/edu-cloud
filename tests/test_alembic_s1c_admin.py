"""S1-C admin migration smoke tests.

覆盖 ORC-S1C-001（linear chain 第 2 环）/ ORC-S1C-002（守旧字段不动）
    / ORC-S1C-003（teaching_plans FK 限定）/ ORC-S1C-004（FK 类型统一）
    / ORC-S1C-005（ORM 注册零 __init__.py 依赖）。

R2 Executor 修复侧（L017 + manual_override 授权范围）：
  - R2-F001: test_orm_registration_three_entry_points 扩 TeachingPlan 三入口断言（env/app/conftest）
  - R2-F002 INV-S1C-001: test_grades_table_created_with_expected_schema 补 school_id FK 断言 + sort_order default=0 断言
  - R2-F002 INV-S1C-002: test_teaching_plans_fk_targets_are_existing_tables 拆 schools/grades/users 三个独立断言
  - R2-F002 INV-S1C-008: __init__.py 字节级 SHA256 对比（非 "0 非空行"，避免 BOM/空白字符漂移假绿）
  - R1 F003: 回滚判定全程用 alembic current（DB revision），不用 alembic heads（脚本目录）

refs: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md Task 5
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# R2-F002 INV-S1C-008: models/__init__.py 必须保持空文件的字节级锚点
# e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 = SHA256 of empty bytes
EMPTY_FILE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


@pytest.fixture()
def sqlite_db(tmp_path):
    """Per-test SQLite file DB（文件路径便于 alembic subprocess 访问）."""
    db_file = tmp_path / 's1c_admin.db'
    yield f'sqlite:///{db_file}'


def _run_alembic(cmd_args: list[str], db_url: str) -> subprocess.CompletedProcess:
    """运行 alembic CLI（async URL 对 alembic async env 必须）."""
    async_url = db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
    return subprocess.run(
        [sys.executable, '-m', 'alembic', *cmd_args],
        cwd=PROJECT_ROOT,
        env={**os.environ, 'DATABASE_URL': async_url},
        capture_output=True,
        text=True,
    )


# ───────────────── 静态文件断言（无需 DB） ─────────────────


def test_migration_file_down_revision_matches_prev_head():
    """INV-S1C-006 + ORC-S1C-001: S1-C migration 文件 head 处 down_revision 是 S1-A slug 'a88094ee4ea6'.

    实施前 Task 4 Step 4.1 实测 head，若已漂移需同步更新本断言。
    本 test 对 plan 契约机械化——写错立即 fail。
    """
    versions_dir = os.path.join(PROJECT_ROOT, 'alembic', 'versions')
    matches = [f for f in os.listdir(versions_dir) if 's1c_admin_schema' in f]
    assert len(matches) == 1, f"Expected exactly 1 S1-C migration file, got {matches}"

    with open(os.path.join(versions_dir, matches[0])) as fp:
        content = fp.read()
    # 精确字符串匹配 down_revision
    assert "down_revision: Union[str, Sequence[str], None] = 'a88094ee4ea6'" in content, \
        "ORC-S1C-001 违反：down_revision 必须是 'a88094ee4ea6'（S1-A T2 slug）"


def test_orm_registration_three_entry_points():
    """ORC-S1C-005 + INV-S1C-008（R1 F001 + R2-F001 + R2-F002 修正）:
    env.py + api/app.py + tests/conftest.py 三处都含 Grade import 且都含 TeachingPlan import；
    models/__init__.py 字节级 SHA256 等于空文件哈希（非"0 非空行"，防空白/BOM 漂移假绿）。
    """
    # 1) alembic/env.py 含 Grade + TeachingPlan import
    env_path = os.path.join(PROJECT_ROOT, 'alembic', 'env.py')
    with open(env_path) as fp:
        env_content = fp.read()
    assert "from edu_cloud.models.grade import Grade" in env_content, \
        "alembic/env.py 缺 Grade import（ORC-S1C-005 入口 1/3）"
    assert "from edu_cloud.models.teaching_plan import TeachingPlan" in env_content, \
        "alembic/env.py 缺 TeachingPlan import（R2-F001 修复：canonical 挪到 models/teaching_plan.py 后 env.py 必须独立 import）"

    # 2) api/app.py 含 Grade + TeachingPlan import
    app_path = os.path.join(PROJECT_ROOT, 'src', 'edu_cloud', 'api', 'app.py')
    with open(app_path) as fp:
        app_content = fp.read()
    assert "import edu_cloud.models.grade" in app_content, \
        "api/app.py 缺 Grade import（ORC-S1C-005 入口 2/3）"
    assert "import edu_cloud.models.teaching_plan" in app_content, \
        "api/app.py 缺 TeachingPlan import（R2-F001 修复：canonical 挪到 models/teaching_plan.py 后 app.py 必须独立 import）"

    # 3) tests/conftest.py 含 Grade + TeachingPlan import（R1 F001 修正：Base.metadata.create_all 独立入口）
    conftest_path = os.path.join(PROJECT_ROOT, 'tests', 'conftest.py')
    with open(conftest_path) as fp:
        conftest_content = fp.read()
    assert "import edu_cloud.models.grade" in conftest_content, \
        "tests/conftest.py 缺 Grade import（R1 F001 根因，ORC-S1C-005 入口 3/3）"
    assert "import edu_cloud.models.teaching_plan" in conftest_content, \
        "tests/conftest.py 缺 TeachingPlan import（R2-F001 修复：TeachingPlan 测试期注册走独立 canonical）"

    # 4) models/__init__.py 字节级 SHA256 与空文件一致（R2-F002 INV-S1C-008 升级：
    #    原 "0 非空行" 会被加空白字符 / 空行 / 尾随空格 / BOM 等漂移绕过）
    init_path = os.path.join(PROJECT_ROOT, 'src', 'edu_cloud', 'models', '__init__.py')
    with open(init_path, 'rb') as fp:
        init_bytes = fp.read()
    actual_sha = hashlib.sha256(init_bytes).hexdigest()
    assert actual_sha == EMPTY_FILE_SHA256, (
        f"ORC-S1C-005 违反：models/__init__.py SHA256 与空文件不一致。\n"
        f"  期望: {EMPTY_FILE_SHA256} (empty file)\n"
        f"  实际: {actual_sha}\n"
        f"  文件字节数: {len(init_bytes)}"
    )


# ───────────────── 结构断言（需 upgrade） ─────────────────


def test_migration_chain_head_is_single(sqlite_db):
    """INV-S1C-007 上半段: upgrade 后脚本目录 `alembic heads` 恰好 1 行（linear chain 无分叉）.

    这里用 heads 是对的——heads 反映脚本目录（alembic/versions/*.py）的 DAG 终点，
    linear chain 应始终返回单个 head slug。与 DB revision 无关。
    R1 F003 教训：回滚检测必须用 `alembic current`（见 test_downgrade_restores_s1a_revision）。
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0, f"upgrade failed: {r.stderr}"

    r = _run_alembic(['heads'], sqlite_db)
    assert r.returncode == 0
    non_empty_lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(non_empty_lines) == 1, f"Expected 1 head, got {len(non_empty_lines)}: {r.stdout}"


def test_downgrade_restores_s1a_revision(sqlite_db):
    """INV-S1C-007 下半段: downgrade -1 后 DB current revision 回到 'a88094ee4ea6'.

    R1 F003 修正：`alembic heads` 是脚本目录的 head 列表（跟脚本打包绝对无关数据库状态），
    downgrade 后 heads 永远不变；只有 `alembic current` 反映 DB 当前 revision。
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0
    r = _run_alembic(['downgrade', 'a88094ee4ea6'], sqlite_db)
    assert r.returncode == 0

    # 用 alembic current 读 DB alembic_version 表
    r = _run_alembic(['current'], sqlite_db)
    assert r.returncode == 0, f"alembic current failed: {r.stderr}"
    current_rev = r.stdout.strip().split()[0] if r.stdout.strip() else ''
    assert current_rev == 'a88094ee4ea6', \
        f"Expected DB current revision a88094ee4ea6 after downgrade, got {current_rev!r} (raw: {r.stdout!r})"


def test_grades_table_created_with_expected_schema(sqlite_db):
    """INV-S1C-001 上半段（R2-F002 补 FK 断言 + default 断言）:
    upgrade 后 grades 表存在 + 列集合完整 + 类型/nullability 精确
    + school_id FK→schools.id + sort_order server_default='0'.
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    assert 'grades' in insp.get_table_names()

    cols = {c['name']: c for c in insp.get_columns('grades')}
    expected = {'id', 'school_id', 'name', 'grade_level', 'xueduan', 'sort_order', 'created_at', 'updated_at'}
    assert expected.issubset(set(cols.keys())), f"Missing cols: {expected - set(cols.keys())}"

    # 精确类型断言（F006 反镜像）
    id_type = str(cols['id']['type']).upper()
    assert 'VARCHAR(36)' in id_type or 'STRING(36)' in id_type, f"grades.id 类型必须 VARCHAR(36)，实际 {id_type}"
    assert cols['school_id']['nullable'] is False
    assert cols['name']['nullable'] is False

    # R2-F002 INV-S1C-001 补：school_id FK→schools.id
    fks = insp.get_foreign_keys('grades')
    school_fk = [fk for fk in fks if 'school_id' in fk['constrained_columns']]
    assert len(school_fk) == 1, f"grades.school_id 必须有 1 个 FK，实际 {len(school_fk)}"
    assert school_fk[0]['referred_table'] == 'schools'
    assert school_fk[0]['referred_columns'] == ['id']

    # R2-F002 INV-S1C-001 补：sort_order server_default='0'
    sort_default = cols['sort_order'].get('default')
    # SQLite 返回形如 "'0'" 或 "0"；Postgres 返回形如 "0" 或 "0::integer"
    assert sort_default is not None, "sort_order 必须有 server_default（migration 层）"
    sort_default_str = str(sort_default).strip().strip("'").strip('"')
    assert sort_default_str.startswith('0'), \
        f"sort_order server_default 必须为 0，实际 {sort_default!r}"


def test_grades_unique_constraint(sqlite_db):
    """INV-S1C-001 下半段（R1 F005 修正）: grades 表含 UniqueConstraint(school_id, name).

    无此 test 则 migration 即使漏写 UniqueConstraint 也能在 Gate G1 假绿。
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    uqs = insp.get_unique_constraints('grades')
    uq_col_sets = [frozenset(u['column_names']) for u in uqs]
    assert frozenset({'school_id', 'name'}) in uq_col_sets, \
        f"grades 缺 UniqueConstraint(school_id, name)，实际 unique_constraints: {uqs}"


# ──── R2-F002 INV-S1C-002 拆分：teaching_plans 三个 FK 独立断言 ────


def _teaching_plans_fks(db_url: str) -> list[dict]:
    engine = create_engine(db_url)
    insp = inspect(engine)
    return insp.get_foreign_keys('teaching_plans')


def test_teaching_plans_schools_fk_exists(sqlite_db):
    """R2-F002 INV-S1C-002a: teaching_plans.school_id → schools.id FK 独立断言."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    fks = _teaching_plans_fks(sqlite_db)
    matches = [fk for fk in fks
               if 'school_id' in fk['constrained_columns']
               and fk['referred_table'] == 'schools']
    assert len(matches) == 1, \
        f"INV-S1C-002a 违反：teaching_plans.school_id → schools.id FK 必须存在，实际 FK 集合 {fks}"


def test_teaching_plans_grades_fk_exists(sqlite_db):
    """R2-F002 INV-S1C-002b: teaching_plans.grade_id → grades.id FK 独立断言."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    fks = _teaching_plans_fks(sqlite_db)
    matches = [fk for fk in fks
               if 'grade_id' in fk['constrained_columns']
               and fk['referred_table'] == 'grades']
    assert len(matches) == 1, \
        f"INV-S1C-002b 违反：teaching_plans.grade_id → grades.id FK 必须存在，实际 FK 集合 {fks}"


def test_teaching_plans_users_fk_exists(sqlite_db):
    """R2-F002 INV-S1C-002c: teaching_plans.created_by → users.id FK 独立断言（R2 核心——原 '子集断言' 会漏此条）."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    fks = _teaching_plans_fks(sqlite_db)
    matches = [fk for fk in fks
               if 'created_by' in fk['constrained_columns']
               and fk['referred_table'] == 'users']
    assert len(matches) == 1, \
        f"INV-S1C-002c 违反：teaching_plans.created_by → users.id FK 必须存在，实际 FK 集合 {fks}"


def test_teaching_plans_table_schema_complete(sqlite_db):
    """ORC-S1C-003 综合断言：列完整 + FK 目标 ⊂ {schools/grades/users}，禁 lesson_plans 等未建表 FK."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    assert 'teaching_plans' in insp.get_table_names()

    cols = {c['name']: c for c in insp.get_columns('teaching_plans')}
    expected = {'id', 'school_id', 'subject_code', 'grade_id', 'semester',
                'weeks_json', 'created_by', 'created_at', 'updated_at'}
    assert expected.issubset(set(cols.keys())), f"Missing cols: {expected - set(cols.keys())}"

    fks = _teaching_plans_fks(sqlite_db)
    referred = {fk['referred_table'] for fk in fks}
    excess = referred - {'schools', 'grades', 'users'}
    assert not excess, \
        f"ORC-S1C-003 违反：teaching_plans FK 目标含未建表 {excess}"


def test_teaching_plans_unique_constraint(sqlite_db):
    """INV-S1C-002 下半段: teaching_plans 含 UniqueConstraint(school_id, subject_code, grade_id, semester)."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    uqs = insp.get_unique_constraints('teaching_plans')
    uq_col_sets = [frozenset(u['column_names']) for u in uqs]
    expected_uq = frozenset({'school_id', 'subject_code', 'grade_id', 'semester'})
    assert expected_uq in uq_col_sets, \
        f"teaching_plans 缺 UniqueConstraint(school_id, subject_code, grade_id, semester)，实际 unique_constraints: {uqs}"


def test_classes_grade_id_added_legacy_unchanged(sqlite_db):
    """INV-S1C-003 + ORC-S1C-002: classes 新增 grade_id；守旧 grade/grade_number 类型不变."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name']: c for c in insp.get_columns('classes')}

    # 新增
    assert 'grade_id' in cols, "classes 必须新增 grade_id 列"
    grade_id_type = str(cols['grade_id']['type']).upper()
    assert 'VARCHAR(36)' in grade_id_type or 'STRING(36)' in grade_id_type, \
        f"classes.grade_id 必须 VARCHAR(36)，实际 {grade_id_type}"
    assert cols['grade_id']['nullable'] is True

    # FK 指向 grades.id
    fks = insp.get_foreign_keys('classes')
    fk_targets = {(fk['referred_table'], tuple(fk['referred_columns'])) for fk in fks}
    assert ('grades', ('id',)) in fk_targets, f"classes.grade_id 必须 FK→grades.id，实际 FK {fk_targets}"

    # 守旧字段不动（ORC-S1C-002 机械化）
    grade_type = str(cols['grade']['type']).upper()
    assert 'VARCHAR(50)' in grade_type or 'STRING(50)' in grade_type, \
        f"守旧 classes.grade 必须 VARCHAR(50)，实际 {grade_type}"
    assert cols['grade']['nullable'] is False, "守旧 classes.grade 必须 NOT NULL"

    assert 'grade_number' in cols
    gn_type = str(cols['grade_number']['type']).upper()
    assert 'INTEGER' in gn_type, f"守旧 classes.grade_number 必须 INTEGER，实际 {gn_type}"


def test_bank_questions_grade_id_is_string36_with_fk(sqlite_db):
    """INV-S1C-004 + ORC-S1C-004: bank_questions.grade_id 类型 VARCHAR(36) + FK→grades.id (闭环 TD-S1A-002)."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name']: c for c in insp.get_columns('bank_questions')}

    assert 'grade_id' in cols
    grade_id_type = str(cols['grade_id']['type']).upper()
    assert 'VARCHAR(36)' in grade_id_type or 'STRING(36)' in grade_id_type, \
        f"bank_questions.grade_id 必须 VARCHAR(36)（TD-S1A-002 闭环），实际 {grade_id_type}"
    assert cols['grade_id']['nullable'] is True

    # FK 指向 grades.id
    fks = insp.get_foreign_keys('bank_questions')
    grade_fk = [fk for fk in fks if 'grade_id' in fk['constrained_columns']]
    assert len(grade_fk) == 1, f"bank_questions.grade_id 必须有 1 个 FK，实际 {len(grade_fk)}"
    assert grade_fk[0]['referred_table'] == 'grades'
    assert grade_fk[0]['referred_columns'] == ['id']


def test_all_grade_id_fks_are_string36(sqlite_db):
    """ORC-S1C-004 扩展：遍历所有 grade_id 字段类型一致（classes/teaching_plans/bank_questions 三张表）."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)

    for table in ('classes', 'teaching_plans', 'bank_questions'):
        cols = {c['name']: c for c in insp.get_columns(table)}
        assert 'grade_id' in cols, f"{table} 必须有 grade_id 列"
        type_str = str(cols['grade_id']['type']).upper()
        assert 'VARCHAR(36)' in type_str or 'STRING(36)' in type_str, \
            f"{table}.grade_id 必须 VARCHAR(36)，实际 {type_str}"


def test_existing_data_preserved_through_s1c_migration(sqlite_db):
    """R1 F004 修正：类型迁移 bank_questions.grade_id Integer→String(36) 的数据保全验证.

    流程（参 tests/test_alembic_s1a_bank.py::test_existing_data_preserved_through_migration 样板）：
      1. alembic upgrade a88094ee4ea6（到 S1-A head，pre-S1-C schema 就位）
      2. INSERT 若干 classes / bank_questions 行（带齐 NOT NULL 列；bank_questions.grade_id 故意留 NULL）
      3. alembic upgrade head（跑 S1-C）
      4. 校验：行数保持 + 关键列值保留；新列 classes.grade_id / teaching_plans 为 NULL
    """
    from datetime import datetime, timezone

    # Step 1: upgrade 到 S1-A head
    r = _run_alembic(['upgrade', 'a88094ee4ea6'], sqlite_db)
    assert r.returncode == 0, f"upgrade a88094ee4ea6 failed: {r.stderr}"

    engine = create_engine(sqlite_db)

    # Step 2: INSERT 测试数据（带齐 NOT NULL 列，F003 教训传承）
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO schools (id, code, name, is_active, created_at, updated_at)
            VALUES ('sch-s1c-smoke', 'S1C_SMOKE', '测试学校', 1, :now, :now)
        """), {'now': now})
        conn.execute(text("""
            INSERT INTO classes (id, name, grade, school_id, created_at, updated_at)
            VALUES ('cls-s1c-001', '高一1班', '高一', 'sch-s1c-smoke', :now, :now)
        """), {'now': now})
        conn.execute(text("""
            INSERT INTO bank_questions (id, question_type, max_score, sample_count, school_id, created_at, updated_at)
            VALUES ('bq-s1c-001', 'essay', 10.0, 0, 'sch-s1c-smoke', :now, :now)
        """), {'now': now})

    # Step 3: upgrade 到 S1-C head
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0, f"upgrade head (S1-C) failed: {r.stderr}"

    # Step 4: 校验数据保留 + 新列对齐
    with engine.connect() as conn:
        # classes 行保留，新 grade_id 列 NULL（ORC"只加不填"）
        row = conn.execute(text(
            "SELECT id, name, grade, grade_id FROM classes WHERE id='cls-s1c-001'"
        )).mappings().first()
        assert row is not None, "classes 行丢失（migration 破坏）"
        assert row['name'] == '高一1班'
        assert row['grade'] == '高一'
        assert row['grade_id'] is None, "classes.grade_id 应为 NULL（S1-C migration 不反向填充）"

        # bank_questions 行保留，grade_id 从 Integer NULL 迁移到 String(36) NULL
        row = conn.execute(text(
            "SELECT id, question_type, max_score, grade_id FROM bank_questions WHERE id='bq-s1c-001'"
        )).mappings().first()
        assert row is not None, "bank_questions 行丢失（migration 破坏）"
        assert row['question_type'] == 'essay'
        assert abs(row['max_score'] - 10.0) < 1e-6
        assert row['grade_id'] is None, \
            "bank_questions.grade_id 应为 NULL（S1-A NULL→S1-C NULL 安全迁移）"

        # teaching_plans 表新建但无数据（默认空）
        count = conn.execute(text("SELECT COUNT(*) FROM teaching_plans")).scalar()
        assert count == 0, f"teaching_plans 新表应为空，实际 {count} 行"

        # grades 表新建但无 seed 数据（见 test_debt #3）
        count = conn.execute(text("SELECT COUNT(*) FROM grades")).scalar()
        assert count == 0, f"grades 新表应为空（seed 归 test_debt #3），实际 {count} 行"
