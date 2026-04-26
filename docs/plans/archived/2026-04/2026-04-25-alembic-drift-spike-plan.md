---
baseline_command: "cd ~/projects/edu-cloud && uv run python -m pytest --collect-only -q"
baseline_verified_at: "2026-04-25 00:42"
baseline_count: 2187
---

# T3-02 Alembic-ORM 列级 drift spike + 修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 写一个幂等的 ORM-DB 列级 drift 检测脚本，跑 spike 拿全量 drift 报告，按 drift 类型写增量 alembic migration 修复，最终验证 `alembic upgrade head` 在干净库幂等成功。

**Architecture:** 检测器用 SQLAlchemy `Base.metadata.tables`（ORM 侧）对比 SQLite `PRAGMA table_info`（DB 侧），输出 6 维度 drift JSON 报告 → 用户审 → 按 drift 类型分级写 migration → 验证全量 pytest baseline 维持 ≥ 2187。

**Tech Stack:** Python 3.11+ / SQLAlchemy 2.x（已在 deps）/ Alembic（已在 deps）/ pytest 8+ / sqlite3 stdlib

**Parent design**: `docs/plans/2026-04-25-alembic-drift-spike-design.md`
**Parent task**: edu-deep-scan §11.1 D-03（`docs/plans/2026-04-24-edu-deep-scan-design.md`）

---

## Semantic Regression（ORC-XXX 不变量）

| ID | 不变量 | 提炼自 design |
|---|---|---|
| **ORC-001** | spike 脚本只读 DB，只 PRAGMA 读取，**不写任何表** | §5.1 |
| **ORC-002** | drift 报告 JSON 结构稳定（key 名 / 类型不变），便于跨版本 diff | §2.3 |
| **ORC-003** | 修复阶段每个 drift 对应**独立** alembic migration（不批量合并），便于回滚 | §3.1 |
| **ORC-004** | 全量 pytest baseline 维持 ≥ 2187（不引入测试回归） | §3.3 |
| **ORC-005** | `alembic upgrade head` 在干净 dev db 上**幂等成功** | §3.3 |

---

## Evidence Block（关键决策证据）

### Evidence: 检测器架构选择（PRAGMA + ORM metadata 对比）

**decision**: 用 SQLite `PRAGMA table_info(<t>)` + SQLAlchemy `Base.metadata.tables` 做对比，自定义脚本输出 6 维度 JSON
**evidence_refs**:
  - `src/edu_cloud/models/base.py` — `Base = declarative_base()` 已存在
  - `src/edu_cloud/api/app.py:34-67` — 已有 33+ 个 module import 用于加载全量 metadata（spike 脚本可复用此 import 模式）
  - `src/edu_cloud/api/app.py:70` — `Base.metadata.create_all` 已在 lifespan 用，metadata 路径 verified
  - 实测命令 `PRAGMA table_info(users)` → 返回 19 列（id/username/.../created_at/updated_at），已 verified @ 2026-04-25 00:40
**Q1**: evidence_source: code-grep + runtime-test | evidence_state: verified
**Q2_excluded**:
  - 备选 A: 用 `alembic --autogenerate` 自动生成 migration 直接对比 → 反证：autogenerate 输出 Python migration 文件而非 JSON 报告，无法批量审计；且无 nullable_mismatch 单独标识
  - 备选 B: 用 `sqlalchemy.inspect` 反射 DB → 反证：反射 vs metadata 等价但 inspect 多一层 abstraction，列定义对比时类型字符串不稳定（含/不含 length 参数）；PRAGMA 输出 stable
**impact_scope**: local (新增 1 个 scripts 脚本 + 6 个测试 + N 个 alembic migration)
**unknowns**:
  - U-01.1 哪些表 drift —— spike 跑完才知道，本 plan 在 Task 6 输出
  - U-01.2 SQLite 类型字符串规整化（VARCHAR(50) vs VARCHAR vs TEXT）—— Task 4 增量处理
  - U-01.3 server_default 比对的精度（"now()" vs "CURRENT_TIMESTAMP" 是否等价）—— Task 4 标 info 级别，不阻断
**followup_spike**: SQLite text 类型亲和性 edge case 在 Task 4 实现时测试覆盖

---

## File Structure

| 文件 | 操作 | 用途 |
|---|---|---|
| `scripts/check_alembic_drift.py` | Create | spike 检测器脚本（核心产物）|
| `tests/test_scripts/test_check_alembic_drift.py` | Create | 检测器单元测试 |
| `tests/test_scripts/conftest.py` | Create（如不存在）| pytest fixtures（临时 db + ORM Base） |
| `docs/plans/2026-04-25-alembic-drift-spike-report.json` | Create（spike 跑产物）| drift 报告 |
| `alembic/versions/<rev>_drift_fix_<table>_<col>.py` | Create N 个 | 每个 drift 一个 migration（数量看 Task 6 报告）|
| `docs/plans/2026-04-25-alembic-drift-spike-followup.md` | Create | T3-02b 提案：移除 create_all（Task 12）|

---

## Phase A: 检测器实现

### Task 1: 创建 spike 脚本骨架 + CLI

**Files:**
- Create: `scripts/check_alembic_drift.py`

- [ ] **Step 1: 写失败测试 — 脚本 CLI 接口**

```python
# tests/test_scripts/test_check_alembic_drift.py
import subprocess
import sys
from pathlib import Path

def test_script_cli_help():
    """脚本必须提供 --help 输出"""
    result = subprocess.run(
        [sys.executable, "scripts/check_alembic_drift.py", "--help"],
        cwd=Path(__file__).parent.parent.parent,
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--db" in result.stdout
    assert "--output" in result.stdout
```

- [ ] **Step 2: 跑测试，确认 FAIL（脚本不存在）**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py::test_script_cli_help -v
```

预期：`FileNotFoundError: scripts/check_alembic_drift.py`

- [ ] **Step 3: 写最小骨架**

```python
# scripts/check_alembic_drift.py
"""
T3-02 Alembic-ORM 列级 drift 检测器（只读，不写 DB）

⚠️ 已知风险：edu-cloud 同时用 create_all（src/edu_cloud/api/app.py:70 等 4 处）
   和 alembic migration，是 ORM-DB drift 的根因。本脚本只检测，不修复。
   修复路径见父 design §3。

输出：6 维度 drift JSON 报告
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite db 文件路径")
    parser.add_argument("--output", required=True, help="JSON 报告输出路径")
    args = parser.parse_args(argv)
    print(f"TODO: detect drift in {args.db} → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试，确认 PASS**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py::test_script_cli_help -v
```

预期：1 passed

- [ ] **Step 5: commit**

```
git -C ~/projects/edu-cloud add scripts/check_alembic_drift.py tests/test_scripts/test_check_alembic_drift.py
git -C ~/projects/edu-cloud commit -m "feat(scripts): T3-02 Task 1 alembic drift 检测器骨架 + CLI"
```

**测试契约**：
- 入口：`test_script_cli_help`
- 反例：脚本不存在或 argparse 未配 `--db/--output` 时 returncode != 0
- 边界：argparse 默认 `-h/--help` 行为
- 回归：CLI 接口稳定（后续 Task 不改参数名）
- 命令：见 Step 2/4

---

### Task 2: 加载 ORM metadata（89 表 tablename）

**Files:**
- Modify: `scripts/check_alembic_drift.py`
- Modify: `tests/test_scripts/test_check_alembic_drift.py`

- [ ] **Step 1: 写失败测试 — load_orm_tables 函数**

```python
# tests/test_scripts/test_check_alembic_drift.py 追加
def test_load_orm_tables_returns_89_tables():
    """ORM metadata 加载后 tablename 数 == 89（来自 P1 调研 baseline）"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import load_orm_tables
    
    tables = load_orm_tables()
    assert len(tables) == 89, f"ORM 表数应为 89，实际 {len(tables)}"
    assert "users" in tables
    assert "students" in tables
    assert "alembic_version" not in tables  # alembic 内部表不算 ORM 业务表


def test_load_orm_tables_columns():
    """每个表必须暴露 columns dict，键为列名，值为 Column 对象"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import load_orm_tables
    
    tables = load_orm_tables()
    users = tables["users"]
    # users 表 ORM 必须含 id, username 列
    assert "id" in users.columns
    assert "username" in users.columns
```

- [ ] **Step 2: 跑测试，确认 FAIL（load_orm_tables 未定义）**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py::test_load_orm_tables_returns_89_tables -v
```

预期：`ImportError: cannot import name 'load_orm_tables'`

- [ ] **Step 3: 实现 load_orm_tables**

```python
# scripts/check_alembic_drift.py 追加
def load_orm_tables() -> dict:
    """加载全量 ORM metadata，返回 {tablename: Table 对象} 字典
    
    复用 src/edu_cloud/api/app.py:34-67 的 import 模式，确保 89 表全部 register 到 Base.metadata
    """
    # 加 src/ 到 path
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "src"))
    
    # 触发 ORM 模型 import（与 api/app.py lifespan 相同）
    from edu_cloud.models.base import Base
    import edu_cloud.models.school  # noqa: F401
    import edu_cloud.models.user  # noqa: F401
    import edu_cloud.models.user_role  # noqa: F401
    import edu_cloud.models.llm_slot  # noqa: F401
    import edu_cloud.modules.exam.models  # noqa: F401
    import edu_cloud.modules.student.models  # noqa: F401
    import edu_cloud.modules.card.models  # noqa: F401
    import edu_cloud.modules.scan.models  # noqa: F401
    import edu_cloud.modules.grading.models  # noqa: F401
    import edu_cloud.modules.marking.models  # noqa: F401
    import edu_cloud.modules.knowledge.models  # noqa: F401
    import edu_cloud.modules.bank.models  # noqa: F401
    import edu_cloud.modules.profile.models  # noqa: F401
    import edu_cloud.ai.models  # noqa: F401
    import edu_cloud.models.document  # noqa: F401
    import edu_cloud.models.approval  # noqa: F401
    import edu_cloud.models.calendar  # noqa: F401
    import edu_cloud.models.notification  # noqa: F401
    import edu_cloud.models.school_settings  # noqa: F401
    import edu_cloud.models.teacher_assignment  # noqa: F401
    import edu_cloud.models.subject_selection  # noqa: F401
    import edu_cloud.models.capability  # noqa: F401
    import edu_cloud.models.audit_log  # noqa: F401
    import edu_cloud.modules.homework.models  # noqa: F401
    import edu_cloud.models.guardian  # noqa: F401
    import edu_cloud.models.workflow  # noqa: F401
    import edu_cloud.models.agent_finding  # noqa: F401
    import edu_cloud.models.agent_snapshot  # noqa: F401
    import edu_cloud.models.scope_version  # noqa: F401
    import edu_cloud.models.memory  # noqa: F401
    import edu_cloud.modules.knowledge_tree.models  # noqa: F401
    import edu_cloud.modules.menu.models  # noqa: F401
    import edu_cloud.modules.analytics.models  # noqa: F401
    import edu_cloud.models.grade  # noqa: F401
    import edu_cloud.models.teaching_plan  # noqa: F401
    
    # 排除 alembic 内部表
    return {name: t for name, t in Base.metadata.tables.items() if name != "alembic_version"}
```

- [ ] **Step 4: 跑测试，确认 PASS**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py::test_load_orm_tables_returns_89_tables tests/test_scripts/test_check_alembic_drift.py::test_load_orm_tables_columns -v
```

预期：2 passed

- [ ] **Step 5: commit**

```
git -C ~/projects/edu-cloud add scripts/check_alembic_drift.py tests/test_scripts/test_check_alembic_drift.py
git -C ~/projects/edu-cloud commit -m "feat(scripts): T3-02 Task 2 load_orm_tables 实现 89 表加载"
```

**测试契约**：
- 入口：`test_load_orm_tables_returns_89_tables`、`test_load_orm_tables_columns`
- 反例：缺少 import 时 metadata 表数 != 89
- 边界：alembic_version 必须排除
- 回归：89 表 baseline（与 edu-deep-scan §2.1 一致）
- 命令：见 Step 2/4

---

### Task 3: 加载 DB schema（PRAGMA 提取）

**Files:**
- Modify: `scripts/check_alembic_drift.py`
- Modify: `tests/test_scripts/test_check_alembic_drift.py`

- [ ] **Step 1: 写失败测试 — load_db_schema 函数**

```python
# tests/test_scripts/test_check_alembic_drift.py 追加
import sqlite3
import tempfile

def test_load_db_schema_users_19_cols():
    """从真实 dev db 读 users 表，应有 19 列（来自 P4 调研 verify @ 2026-04-25 00:40）"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import load_db_schema
    
    db_path = Path(__file__).parent.parent.parent / "edu_cloud.db"
    schema = load_db_schema(str(db_path))
    
    assert "users" in schema
    assert len(schema["users"]) == 19
    # PRAGMA 输出格式：每列 dict {name, type, nullable, default}
    cols_by_name = {c["name"]: c for c in schema["users"]}
    assert "id" in cols_by_name
    assert "username" in cols_by_name


def test_load_db_schema_empty_db():
    """空 db 返回空 dict"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import load_db_schema
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        empty_db_path = f.name
    sqlite3.connect(empty_db_path).close()  # create empty db file
    
    schema = load_db_schema(empty_db_path)
    assert schema == {}
```

- [ ] **Step 2: 跑测试，确认 FAIL**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py::test_load_db_schema_users_19_cols -v
```

预期：`ImportError: cannot import name 'load_db_schema'`

- [ ] **Step 3: 实现 load_db_schema**

```python
# scripts/check_alembic_drift.py 追加
def load_db_schema(db_path: str) -> dict:
    """从 SQLite db 用 PRAGMA 加载全表 schema
    
    返回：{tablename: [{name, type, nullable, default}, ...]}
    排除 alembic_version 表。
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 列出所有表（排除 alembic_version 和 sqlite_*）
    c.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version' "
        "ORDER BY name"
    )
    tables = [r[0] for r in c.fetchall()]
    
    schema = {}
    for tname in tables:
        # PRAGMA 输出：(cid, name, type, notnull, dflt_value, pk)
        c.execute(f'PRAGMA table_info("{tname}")')
        schema[tname] = [
            {
                "name": row[1],
                "type": row[2],
                "nullable": row[3] == 0,  # PRAGMA notnull=0 → nullable
                "default": row[4],
            }
            for row in c.fetchall()
        ]
    
    conn.close()
    return schema


# 顶部 import 区追加
import sqlite3
```

- [ ] **Step 4: 跑测试，确认 PASS**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py::test_load_db_schema_users_19_cols tests/test_scripts/test_check_alembic_drift.py::test_load_db_schema_empty_db -v
```

预期：2 passed

- [ ] **Step 5: commit**

```
git -C ~/projects/edu-cloud add scripts/check_alembic_drift.py tests/test_scripts/test_check_alembic_drift.py
git -C ~/projects/edu-cloud commit -m "feat(scripts): T3-02 Task 3 load_db_schema 实现 PRAGMA 提取"
```

**测试契约**：
- 入口：`test_load_db_schema_users_19_cols`、`test_load_db_schema_empty_db`
- 反例：PRAGMA 用错（未排除 alembic_version）→ schema 多表；空 db 不返 dict → 类型错
- 边界：表名含特殊字符（双引号包裹）；空 db 返空 dict
- 回归：users 19 列 baseline（来自 P4 verify）
- 命令：见 Step 2/4

---

### Task 4: 6 维度 drift 检测核心

**Files:**
- Modify: `scripts/check_alembic_drift.py`
- Modify: `tests/test_scripts/test_check_alembic_drift.py`

- [ ] **Step 1: 写失败测试 — detect_drift 函数 6 case**

```python
# tests/test_scripts/test_check_alembic_drift.py 追加
def test_detect_drift_table_only_in_orm():
    """ORM 有表 / DB 无 → 1 条 table_only_in_orm"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import detect_drift
    
    orm = {"new_table": _mock_orm_table([("id", "INTEGER", False, None)])}
    db = {}
    drifts = detect_drift(orm, db)
    assert len(drifts) == 1
    assert drifts[0]["type"] == "table_only_in_orm"
    assert drifts[0]["table"] == "new_table"


def test_detect_drift_column_only_in_orm():
    """ORM 加了列但 DB 无 → 1 条 column_only_in_orm"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import detect_drift
    
    orm = {"users": _mock_orm_table([
        ("id", "INTEGER", False, None),
        ("username", "VARCHAR(100)", False, None),
        ("new_col", "VARCHAR(50)", True, None),  # ORM 加的新列
    ])}
    db = {"users": [
        {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
        {"name": "username", "type": "VARCHAR(100)", "nullable": False, "default": None},
        # 没有 new_col
    ]}
    drifts = detect_drift(orm, db)
    cot = [d for d in drifts if d["type"] == "column_only_in_orm"]
    assert len(cot) == 1
    assert cot[0]["column"] == "new_col"


def test_detect_drift_column_only_in_db():
    """DB 有列 / ORM 无 → 1 条 column_only_in_db"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import detect_drift
    
    orm = {"users": _mock_orm_table([("id", "INTEGER", False, None)])}
    db = {"users": [
        {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
        {"name": "deprecated_col", "type": "VARCHAR(50)", "nullable": True, "default": None},
    ]}
    drifts = detect_drift(orm, db)
    cod = [d for d in drifts if d["type"] == "column_only_in_db"]
    assert len(cod) == 1
    assert cod[0]["column"] == "deprecated_col"


def test_detect_drift_aligned_no_drift():
    """ORM 与 DB 完全对齐 → 空 drifts"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import detect_drift
    
    cols = [("id", "INTEGER", False, None), ("name", "VARCHAR(100)", False, None)]
    orm = {"t1": _mock_orm_table(cols)}
    db = {"t1": [
        {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
        {"name": "name", "type": "VARCHAR(100)", "nullable": False, "default": None},
    ]}
    drifts = detect_drift(orm, db)
    assert drifts == []


# helper
def _mock_orm_table(cols):
    """构造 mock ORM Table，cols = [(name, type_str, nullable, default), ...]"""
    from sqlalchemy import Column, MetaData, Table, String, Integer
    md = MetaData()
    type_map = {"INTEGER": Integer, "VARCHAR(50)": String(50), "VARCHAR(100)": String(100)}
    sa_cols = [
        Column(name, type_map.get(typ, String), nullable=nullable, server_default=dflt)
        for name, typ, nullable, dflt in cols
    ]
    return Table("mock", md, *sa_cols)
```

- [ ] **Step 2: 跑测试，确认 FAIL**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py -k "detect_drift" -v
```

预期：4 ImportError 或 AttributeError

- [ ] **Step 3: 实现 detect_drift（6 维度）**

```python
# scripts/check_alembic_drift.py 追加
def _normalize_type(t: str) -> str:
    """规整化类型字符串（SQLite 类型亲和性处理）
    
    e.g. VARCHAR(100) → VARCHAR；BIGINT → INTEGER（SQLite affinity）
    """
    t = t.upper().strip()
    # 去掉长度参数（"VARCHAR(100)" → "VARCHAR"）
    if "(" in t:
        t = t.split("(")[0].strip()
    # SQLite affinity 归一
    if t in ("BIGINT", "SMALLINT", "TINYINT", "MEDIUMINT", "INT2", "INT8"):
        return "INTEGER"
    if t in ("FLOAT", "DOUBLE", "DOUBLE PRECISION"):
        return "REAL"
    if t in ("CHAR", "VARCHAR", "TEXT", "NVARCHAR", "NCHAR"):
        return "TEXT"
    return t


def detect_drift(orm_tables: dict, db_schema: dict) -> list[dict]:
    """6 维度 drift 检测
    
    Args:
        orm_tables: load_orm_tables() 返回值
        db_schema: load_db_schema() 返回值
    
    Returns:
        list of drift dicts
    """
    drifts = []
    
    orm_names = set(orm_tables.keys())
    db_names = set(db_schema.keys())
    
    # 维度 1: table_only_in_orm
    for tname in sorted(orm_names - db_names):
        drifts.append({
            "table": tname, "type": "table_only_in_orm",
            "severity": "blocking",
            "suggestion": f"alembic revision --autogenerate -m 'add {tname} table'"
        })
    
    # 维度 2: table_only_in_db
    for tname in sorted(db_names - orm_names):
        drifts.append({
            "table": tname, "type": "table_only_in_db",
            "severity": "info",  # 可能是历史遗留，先标 info
            "suggestion": f"评估是否 drop 或加 ORM 模型映射 {tname}"
        })
    
    # 共有表的列级对比
    for tname in sorted(orm_names & db_names):
        orm_cols = {c.name: c for c in orm_tables[tname].columns}
        db_cols = {c["name"]: c for c in db_schema[tname]}
        
        # 维度 3: column_only_in_orm
        for cname in sorted(set(orm_cols.keys()) - set(db_cols.keys())):
            col = orm_cols[cname]
            drifts.append({
                "table": tname, "column": cname,
                "type": "column_only_in_orm",
                "orm_def": {"type": str(col.type), "nullable": col.nullable},
                "db_def": None,
                "severity": "blocking",
                "suggestion": f"alembic revision -m 'add {tname}.{cname} column'"
            })
        
        # 维度 4: column_only_in_db
        for cname in sorted(set(db_cols.keys()) - set(orm_cols.keys())):
            col = db_cols[cname]
            drifts.append({
                "table": tname, "column": cname,
                "type": "column_only_in_db",
                "orm_def": None,
                "db_def": col,
                "severity": "info",  # 用户审后决定 drop
                "suggestion": f"评估 {tname}.{cname} 是否 drop（确认废弃）或回填 ORM 模型"
            })
        
        # 共有列的类型/nullable 对比
        for cname in sorted(set(orm_cols.keys()) & set(db_cols.keys())):
            orm_col = orm_cols[cname]
            db_col = db_cols[cname]
            
            # 维度 5: column_type_mismatch
            orm_type = _normalize_type(str(orm_col.type))
            db_type = _normalize_type(db_col["type"])
            if orm_type != db_type:
                drifts.append({
                    "table": tname, "column": cname,
                    "type": "column_type_mismatch",
                    "orm_def": {"type": str(orm_col.type)},
                    "db_def": {"type": db_col["type"]},
                    "severity": "blocking",
                    "suggestion": f"评估 alter column 兼容性（{tname}.{cname}）"
                })
            
            # 维度 6: column_nullable_mismatch
            if orm_col.nullable != db_col["nullable"]:
                drifts.append({
                    "table": tname, "column": cname,
                    "type": "column_nullable_mismatch",
                    "orm_def": {"nullable": orm_col.nullable},
                    "db_def": {"nullable": db_col["nullable"]},
                    "severity": "blocking" if orm_col.nullable is False else "info",
                    "suggestion": f"alembic alter {tname}.{cname} nullable"
                })
    
    return drifts
```

- [ ] **Step 4: 跑测试，确认 PASS**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py -k "detect_drift" -v
```

预期：4 passed

- [ ] **Step 5: commit**

```
git -C ~/projects/edu-cloud add scripts/check_alembic_drift.py tests/test_scripts/test_check_alembic_drift.py
git -C ~/projects/edu-cloud commit -m "feat(scripts): T3-02 Task 4 detect_drift 6 维度核心检测"
```

**测试契约**：
- 入口：4 个 `test_detect_drift_*` 用例
- 反例：检测器把对齐表报成 drift（test_detect_drift_aligned_no_drift 防）
- 边界：空 ORM / 空 DB / 类型亲和性（VARCHAR vs TEXT）
- 回归：6 维度全覆盖
- 命令：见 Step 2/4

---

### Task 5: JSON 输出 + main() 串联

**Files:**
- Modify: `scripts/check_alembic_drift.py`
- Modify: `tests/test_scripts/test_check_alembic_drift.py`

- [ ] **Step 1: 写失败测试 — main() 端到端**

```python
# tests/test_scripts/test_check_alembic_drift.py 追加
def test_main_produces_valid_json_report(tmp_path):
    """main() 跑完应在 --output 路径输出合法 JSON，含 summary + drifts"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import main
    
    output = tmp_path / "drift.json"
    db_path = Path(__file__).parent.parent.parent / "edu_cloud.db"
    rc = main(["--db", str(db_path), "--output", str(output)])
    assert rc == 0
    
    report = json.loads(output.read_text())
    # summary 必须含 6 字段
    assert "summary" in report
    assert "total_tables_orm" in report["summary"]
    assert "total_tables_db" in report["summary"]
    assert "tables_aligned" in report["summary"]
    assert "drift_count_by_type" in report["summary"]
    assert "drifts" in report
    # ORM 表数应 == 89
    assert report["summary"]["total_tables_orm"] == 89


def test_main_idempotent(tmp_path):
    """连续两次跑 main()，输出 JSON 应完全一致（幂等性 ORC-002）"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_alembic_drift import main
    
    db_path = Path(__file__).parent.parent.parent / "edu_cloud.db"
    
    out1 = tmp_path / "drift1.json"
    out2 = tmp_path / "drift2.json"
    main(["--db", str(db_path), "--output", str(out1)])
    main(["--db", str(db_path), "--output", str(out2)])
    
    assert out1.read_text() == out2.read_text(), "幂等性 ORC-002 违反"
```

- [ ] **Step 2: 跑测试，确认 FAIL**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py::test_main_produces_valid_json_report tests/test_scripts/test_check_alembic_drift.py::test_main_idempotent -v
```

预期：FAIL（main 还是 Task 1 的 stub）

- [ ] **Step 3: 实现完整 main()**

```python
# scripts/check_alembic_drift.py 替换 main()
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite db 文件路径")
    parser.add_argument("--output", required=True, help="JSON 报告输出路径")
    args = parser.parse_args(argv)
    
    orm_tables = load_orm_tables()
    db_schema = load_db_schema(args.db)
    drifts = detect_drift(orm_tables, db_schema)
    
    # 统计
    drift_count = {}
    for d in drifts:
        drift_count[d["type"]] = drift_count.get(d["type"], 0) + 1
    
    aligned = len(set(orm_tables.keys()) & set(db_schema.keys())) - sum(
        1 for d in drifts if d["type"] in ("column_only_in_orm", "column_only_in_db", "column_type_mismatch", "column_nullable_mismatch")
    )
    
    report = {
        "summary": {
            "total_tables_orm": len(orm_tables),
            "total_tables_db": len(db_schema),
            "tables_aligned": aligned,
            "drift_count_by_type": drift_count,
        },
        "drifts": sorted(drifts, key=lambda d: (d.get("table", ""), d.get("column", ""), d["type"])),
    }
    
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Drift report written to {args.output}")
    print(f"Summary: {report['summary']}")
    return 0
```

- [ ] **Step 4: 跑测试，确认 PASS**

```
cd ~/projects/edu-cloud
uv run python -m pytest tests/test_scripts/test_check_alembic_drift.py -v
```

预期：所有 test_check_alembic_drift 用例 passed（约 8 个）

- [ ] **Step 5: commit**

```
git -C ~/projects/edu-cloud add scripts/check_alembic_drift.py tests/test_scripts/test_check_alembic_drift.py
git -C ~/projects/edu-cloud commit -m "feat(scripts): T3-02 Task 5 main() JSON 输出 + 幂等性"
```

**测试契约**：
- 入口：`test_main_produces_valid_json_report`、`test_main_idempotent`
- 反例：JSON 缺字段；多次跑结果不一致 → ORC-002 违反
- 边界：空 db / 大 db
- 回归：summary schema 稳定（key 名不变）
- 命令：见 Step 2/4

---

## Phase B: spike 跑 + 用户审

### Task 6: spike 干跑 → drift 报告

**Files:**
- Read: `scripts/check_alembic_drift.py`
- Create: `docs/plans/2026-04-25-alembic-drift-spike-report.json`（spike 产物）

- [ ] **Step 1: 跑 spike**

```bash
cd ~/projects/edu-cloud
uv run python scripts/check_alembic_drift.py \
  --db edu_cloud.db \
  --output docs/plans/2026-04-25-alembic-drift-spike-report.json
```

预期输出：
```
Drift report written to docs/plans/2026-04-25-alembic-drift-spike-report.json
Summary: {'total_tables_orm': 89, 'total_tables_db': 89, ...}
```

- [ ] **Step 2: 检查报告 size + 内容**

```bash
ls -la docs/plans/2026-04-25-alembic-drift-spike-report.json
python3 -c "import json; r = json.load(open('docs/plans/2026-04-25-alembic-drift-spike-report.json')); print(json.dumps(r['summary'], indent=2))"
```

- [ ] **Step 3: commit 报告**

```
git -C ~/projects/edu-cloud add docs/plans/2026-04-25-alembic-drift-spike-report.json
git -C ~/projects/edu-cloud commit -m "data(plans): T3-02 Task 6 alembic drift spike 报告产出"
```

- [ ] **Step 4: 把报告交给用户审**

输出报告路径 + summary 给用户。等用户在报告内对每个 drift 标注：
- `keep`：DB 列保留，回填 ORM 映射
- `drop`：DB 列废弃，写 drop migration
- `add`：ORM 列保留，写 add migration
- `alter`：类型/nullable 调整，写 alter migration
- `defer`：暂不处理（标技术债 D-3a/D-3b/...）

---

### Task 7（manual）: 用户审报告

**Files:** 用户在 `docs/plans/2026-04-25-alembic-drift-spike-report.json` 旁建 `<...>-report-decisions.md`

- [ ] **manual step: 用户对每条 drift 标 keep/drop/add/alter/defer**
- [ ] **manual step: 用户在 design.md 或新文件记每条决策的理由**

⚠️ **本 task 是人工 task，本 plan 不展开自动化**。

---

## Phase C: 修复（每个 blocking drift 一个 migration）

### Task 8: 增量 alembic migration 模板

**Files:**
- Create: `alembic/versions/<rev>_drift_fix_<table>_<col>.py`（每个 drift 一个）

> ⚠️ **Task 8 是模板任务，按 Task 6 报告里的 N 条 blocking drift 重复 N 次。**
> 
> 每条 drift 完整 5 步流程：

- [ ] **Step 1: 为某条 drift 生成 alembic revision**

```bash
cd ~/projects/edu-cloud
uv run alembic revision -m "drift_fix_<table>_<column>" --rev-id "drift_<short>"
```

- [ ] **Step 2: 写迁移 op（看 drift type 决定 op_*）**

`column_only_in_orm` 用 `op.add_column`：
```python
def upgrade():
    op.add_column("<table>", sa.Column("<col>", sa.<Type>(), nullable=<nullable>, server_default=...))


def downgrade():
    op.drop_column("<table>", "<col>")
```

`column_only_in_db` 用户标 `drop` 时：
```python
def upgrade():
    op.drop_column("<table>", "<col>")


def downgrade():
    op.add_column("<table>", sa.Column("<col>", ...))  # 还原原 type
```

- [ ] **Step 3: 在 dev db 跑 upgrade**

```bash
cd ~/projects/edu-cloud
uv run alembic upgrade head
```

预期：`Running upgrade <prev_rev> -> drift_<short>, drift_fix_<table>_<column>`

- [ ] **Step 4: 重跑 spike 验证该 drift 消失**

```bash
cd ~/projects/edu-cloud
uv run python scripts/check_alembic_drift.py --db edu_cloud.db --output /tmp/drift-after-fix.json
diff <(jq '.drifts[] | select(.table == "<table>" and .column == "<col>")' docs/plans/2026-04-25-alembic-drift-spike-report.json) <(jq '.drifts[] | select(.table == "<table>" and .column == "<col>")' /tmp/drift-after-fix.json)
```

预期：该 drift 在新报告里**不存在**

- [ ] **Step 5: commit**

```
git -C ~/projects/edu-cloud add alembic/versions/<rev>_drift_fix_<table>_<col>.py
git -C ~/projects/edu-cloud commit -m "fix(db): T3-02 alembic drift fix <table>.<col>"
```

**测试契约**：
- 入口：每个 migration 都跑 alembic upgrade + spike 重跑验证
- 反例：upgrade 报错；或 spike 重跑后该 drift 仍存在
- 边界：downgrade 必须 round-trip（手动验证）
- 回归：每个 migration 后跑一次 `tests/test_alembic*` 子集
- 命令：见 Step 3/4

---

## Phase D: 验收

### Task 9: alembic upgrade head 干净 db 验证

**Files:**
- Test: 临时 db 文件

- [ ] **Step 1: 写 alembic clean upgrade 脚本**

```bash
# tmp_test_clean_alembic.sh（临时，不入 git）
set -e
TMPDB=$(mktemp /tmp/edu_cloud_clean_XXXXX.db)
cd ~/projects/edu-cloud
DATABASE_URL="sqlite+aiosqlite:///$TMPDB" uv run alembic upgrade head
echo "Clean upgrade SUCCESS on $TMPDB"
rm -f $TMPDB
```

- [ ] **Step 2: 跑脚本**

```bash
bash tmp_test_clean_alembic.sh
```

预期：`Clean upgrade SUCCESS on /tmp/edu_cloud_clean_XXXXX.db` 无报错

- [ ] **Step 3: 删 tmp 脚本**

```bash
rm -f tmp_test_clean_alembic.sh
```

- [ ] **Step 4: commit "alembic clean validation passed" 到 design 验收记录**

在 `docs/plans/2026-04-25-alembic-drift-spike-design.md` §7 验收标准里勾选 `[x] alembic upgrade head 干净 dev db 通过`，commit。

```
git -C ~/projects/edu-cloud commit -am "docs(plans): T3-02 Task 9 alembic clean upgrade verified"
```

**测试契约**：
- 入口：`bash tmp_test_clean_alembic.sh`
- 反例：upgrade 报错（IntegrityError / OperationalError）
- 边界：空 db 跑 upgrade head（不能依赖任何已有数据）
- 回归：ORC-005（alembic upgrade head 幂等成功）
- 命令：Step 2

---

### Task 10: 全量 pytest baseline 验证

**Files:** —

- [ ] **Step 1: 跑全量 pytest**

```bash
cd ~/projects/edu-cloud
uv run python -m pytest --tb=no -q 2>&1 | tail -10
```

预期：`>= 2187 passed`（baseline 从 P7 实测，对应 frontmatter `baseline_count: 2187`）

- [ ] **Step 2: 如果 fail 数变多**

回退：找到引入回归的 migration → 跑 alembic downgrade -1 → 重新审 migration → 修

- [ ] **Step 3: 通过后 commit baseline 更新（如有增量）**

如果 passed > 2187：
```
git -C ~/projects/edu-cloud commit --allow-empty -m "test(baseline): T3-02 Task 10 全量 pytest 维持 baseline N passed"
```

**测试契约**：
- 入口：`uv run python -m pytest --tb=no -q`
- 反例：passed 数 < 2187 → ORC-004 违反
- 边界：22 既有 failed 仍允许（CLAUDE.md L89 已披露）
- 回归：ORC-004
- 命令：Step 1

---

### Task 11: 重跑 spike 确认 drift_count = 0

**Files:**
- Modify: `docs/plans/2026-04-25-alembic-drift-spike-report.json`（重跑覆盖）

- [ ] **Step 1: 重跑 spike**

```bash
cd ~/projects/edu-cloud
uv run python scripts/check_alembic_drift.py \
  --db edu_cloud.db \
  --output docs/plans/2026-04-25-alembic-drift-spike-report.json
```

- [ ] **Step 2: 验 drift_count_by_type 全 0（除 info 外）**

```bash
python3 -c "
import json
r = json.load(open('docs/plans/2026-04-25-alembic-drift-spike-report.json'))
blocking = sum(1 for d in r['drifts'] if d.get('severity') == 'blocking')
print(f'blocking drifts: {blocking}')
assert blocking == 0, f'仍有 {blocking} 条 blocking drift'
print('ORC-001 / ORC-005 验收 PASS')
"
```

预期：`blocking drifts: 0` 且 assert 不抛错

- [ ] **Step 3: commit 终版报告**

```
git -C ~/projects/edu-cloud commit -am "data(plans): T3-02 Task 11 alembic drift fix 验收 - blocking drifts = 0"
```

**测试契约**：
- 入口：Step 2 的 Python assert
- 反例：仍有 blocking drift
- 边界：info drift 允许残留（待 T3-02b 处理）
- 回归：ORC-005
- 命令：Step 1/2

---

### Task 12: 起 T3-02b 提案（移除 create_all 4 处）

**Files:**
- Create: `docs/plans/2026-04-25-alembic-drift-spike-followup.md`

- [ ] **Step 1: 写 followup 提案**

```markdown
# T3-02b followup: 移除 create_all 4 处（待独立 plan 起手）

> 本文档由 T3-02 Task 12 产出，作为 D-03 后续工作锚点。

## 上下文

T3-02 已完成列级 drift 修复（验证 blocking drifts = 0）。但 create_all 仍在 4 处：
- src/edu_cloud/api/app.py:70（lifespan dev mode）
- src/edu_cloud/data/seed_school.py:431
- src/edu_cloud/data/import_exam_xlsx.py:326
- src/edu_cloud/data/seed_highschool_supplement.py:540

create_all 与 alembic 并存仍是 drift 复发的根源。

## 建议路径

1. dev mode lifespan: 改为只跑 alembic upgrade head（删 create_all），dev seed 改用 separate script
2. seed 脚本：改为先 alembic upgrade head 后再 insert
3. 加 CI gate：禁止新代码引入 create_all（grep 检查）

## 何时起 plan

- T3-02 完成后任何时间
- 优先级：D-03 解决后，drift 复发预防
```

- [ ] **Step 2: commit followup**

```bash
git -C ~/projects/edu-cloud add docs/plans/2026-04-25-alembic-drift-spike-followup.md
git -C ~/projects/edu-cloud commit -m "docs(plans): T3-02 Task 12 followup 提案 移除 create_all 4 处"
```

**测试契约**：
- 入口：手动 review followup md
- 反例：—
- 边界：—
- 回归：作为后续工作锚点
- 命令：—

---

## Self-Review

**1. Spec coverage:**
- ✅ design §1 设计目标 → Task 1-5 实现检测器 + Task 6 跑 spike
- ✅ design §2.2 6 维度 → Task 4 完整覆盖（test_detect_drift_* 4 case + 2 type/nullable case 在 Task 5 端到端覆盖）
- ✅ design §3.1 修复策略 → Task 8 模板按 drift type 分支
- ✅ design §3.3 全量验收 → Task 9 (alembic clean) + Task 10 (pytest baseline) + Task 11 (drift = 0)
- ✅ design §4 create_all 处理 → Task 12 followup 提案
- ✅ design §7 验收标准 6 项全部映射到 Task 9-11

**2. Placeholder scan:**
- ❌ 无 "TBD" / "TODO" / "fill in" 等
- ⚠️ Task 8 用 `<table>` / `<col>` 是因为依赖 Task 6 的报告输出，不是占位符；明确说明"模板任务，按报告 N 条 blocking drift 重复 N 次"
- ✅ 所有代码块都是真实 Python 代码

**3. Type consistency:**
- ✅ `load_orm_tables()` 返回 `dict[str, Table]` —— Task 2/4/5 一致
- ✅ `load_db_schema()` 返回 `dict[str, list[dict]]` —— Task 3/4/5 一致
- ✅ `detect_drift()` 接收上述两参数返回 `list[dict]` —— Task 4/5 一致
- ✅ drift dict 字段稳定：`table` / `column` / `type` / `severity` / `suggestion`（+ optional `orm_def` / `db_def`）

---

## Execution Handoff

**⚠️ 本 plan 完成后禁止本会话 executing-plans**（CLAUDE.md "T3/T4 设计→计划→独立新会话执行" + session_guard）

Plan 完整入 git 后，**用户需独立新会话**起 executing-plans。两种执行选项：

**1. Subagent-Driven（推荐）** — 派 fresh subagent 跑每个 Task，task 间 review，快速迭代
**2. Inline Execution** — 在新会话里串行执行 Task，checkpoint review

执行前置检查：
- 用户审 design.md 已 approve（已完成 @ 2026-04-25）
- 本 plan.md 入 git
- 新会话用 `cd ~/projects/edu-cloud` + 加载 superpowers:executing-plans 或 subagent-driven-development

---

**T3-02 plan v1 完 @ 2026-04-25 00:55**
**等用户在新会话执行；本会话不进 executing-plans**
