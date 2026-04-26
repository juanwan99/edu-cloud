<!-- pre-takeover: archived for history, not active spec -->
# Phase 2: 跨会话记忆 + 项目状态持久化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 edu-cloud Agent 添加跨会话记忆系统——EntityMemory（实体画像）、ProjectState（项目进度）、Episodic Memory（历史摘要），使 Agent 能记住学生轨迹、教师偏好、跨会话任务进度。

**Architecture:** 两张新 PostgreSQL 表（entity_memory + project_state），MemoryStore 提供 CRUD + 冲突合并，MemoryExtractor 在会话结束时 LLM 提取并持久化，MemoryInjector 在会话开始时加载相关记忆注入 system prompt，memory_read/memory_write 作为 Agent 工具供主动调用。Episodic Memory 复用 EntityMemory 表（entity_type="session_episode"）。

**Tech Stack:** SQLAlchemy 2.0 async + asyncpg + Alembic + existing LLM adapter + existing ToolRegistry

**Design doc:** `docs/plans/2026-04-05-agent-evolution-design.md` §3

**依赖:** Phase 1 多 Agent 编排引擎（已完成）

---

## 文件结构

| 文件 | 类型 | 职责 |
|------|------|------|
| `src/edu_cloud/models/memory.py` | 新增 | EntityMemory + ProjectState ORM 模型 |
| `alembic/versions/*_add_entity_memory_project_state.py` | 新增 | 2 张新表迁移 |
| `src/edu_cloud/ai/memory_store.py` | 新增 | MemoryStore CRUD + 冲突合并 + LRU 淘汰 |
| `src/edu_cloud/ai/memory_extractor.py` | 新增 | 重写 session_memory.py，持久化到 EntityMemory |
| `src/edu_cloud/ai/memory_injector.py` | 新增 | 会话启动时加载记忆，注入 system prompt |
| `src/edu_cloud/ai/tools/memory_tools.py` | 新增 | memory_read / memory_write 工具 |
| `src/edu_cloud/ai/tools/__init__.py` | 修改 | 注册 memory_tools |
| `src/edu_cloud/ai/supervisor.py` | 修改 | 接受 MemoryInjector，会话后调用 MemoryExtractor |
| `src/edu_cloud/api/ai.py` | 修改 | 创建 Injector/Extractor，传入 Supervisor |
| `tests/test_ai/test_memory_models.py` | 新增 | ORM 模型单测 |
| `tests/test_ai/test_memory_store.py` | 新增 | MemoryStore CRUD 单测 |
| `tests/test_ai/test_memory_extractor.py` | 新增 | Extractor 单测 |
| `tests/test_ai/test_memory_injector.py` | 新增 | Injector 单测 |
| `tests/test_ai/test_memory_tools.py` | 新增 | memory_read/write 工具单测 |
| `tests/test_ai/test_memory_integration.py` | 新增 | 端到端集成 |

> **Note (F007):** 设计文档 §3 使用概括性路径 `ai/tools/system_tools.py`，本计划细化为 `ai/tools/memory_tools.py`（独立职责文件）。以本计划为准。

---

### Task 1: EntityMemory + ProjectState 数据模型

**Files:**
- Create: `src/edu_cloud/models/memory.py`
- Test: `tests/test_ai/test_memory_models.py`

**测试契约:**
1. EntityMemory 模型创建与字段
   - 入口: `EntityMemory(entity_type="student", entity_id="s1", school_id="sch1", facts={"math": 0.4})`
   - 反例: 错误实现允许 facts 为非 dict 类型
   - 边界: facts={} / entity_type 未知值 / school_id=None
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_models.py -v`
2. ProjectState 模型创建与字段
   - 入口: `ProjectState(project_type="paper", project_id="p1", owner_id="u1", school_id="sch1", state={}, status="active")`
   - 反例: 错误实现允许非法 status 值
   - 边界: state={} / checkpoints=[] / status 取值枚举
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_models.py -v`

**审查清单:**
- ✓ EntityMemory 继承 Base + IdMixin + TimestampMixin
- ✓ facts 字段用 JSON 类型（PostgreSQL JSONB）
- ✓ school_id + entity_type + entity_id 有联合索引
- ✓ ProjectState 的 status 限定枚举值
- ✗ 不与现有 agent_memories 表冲突（新表独立）

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_memory_models.py
import pytest
from sqlalchemy import inspect

from edu_cloud.models.memory import EntityMemory, ProjectState


class TestEntityMemory:
    def test_create_instance(self):
        m = EntityMemory(
            entity_type="student",
            entity_id="stu-001",
            school_id="sch-001",
            facts={"math_mastery": 0.4, "weakness": "函数图像"},
        )
        assert m.entity_type == "student"
        assert m.entity_id == "stu-001"
        assert m.school_id == "sch-001"
        assert m.facts["math_mastery"] == 0.4

    def test_tablename(self):
        assert EntityMemory.__tablename__ == "entity_memory"

    def test_empty_facts(self):
        m = EntityMemory(
            entity_type="teacher",
            entity_id="t-001",
            school_id="sch-001",
            facts={},
        )
        assert m.facts == {}

    def test_episodic_memory_type(self):
        """Episodic memory uses entity_type='session_episode'."""
        m = EntityMemory(
            entity_type="session_episode",
            entity_id="sess-001",
            school_id="sch-001",
            facts={"decision": "用户偏好图表而非表格"},
        )
        assert m.entity_type == "session_episode"

    def test_has_indexes(self):
        mapper = inspect(EntityMemory)
        col_names = [c.name for c in mapper.columns]
        assert "school_id" in col_names
        assert "entity_type" in col_names
        assert "entity_id" in col_names


class TestProjectState:
    def test_create_instance(self):
        p = ProjectState(
            project_type="paper",
            project_id="paper-001",
            owner_id="user-001",
            school_id="sch-001",
            state={"topic": "深度学习在教育中的应用", "checkpoint": "outline"},
            status="active",
        )
        assert p.project_type == "paper"
        assert p.status == "active"
        assert p.state["topic"] == "深度学习在教育中的应用"

    def test_tablename(self):
        assert ProjectState.__tablename__ == "project_state"

    def test_default_status(self):
        p = ProjectState(
            project_type="courseware",
            project_id="cw-001",
            owner_id="user-001",
            school_id="sch-001",
            state={},
        )
        assert p.status == "active"

    def test_checkpoints_default_empty(self):
        p = ProjectState(
            project_type="paper",
            project_id="p1",
            owner_id="u1",
            school_id="s1",
            state={},
        )
        assert p.checkpoints == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.models.memory'`

- [ ] **Step 3: Implement models**

```python
# src/edu_cloud/models/memory.py
"""Cross-session memory models: EntityMemory + ProjectState."""

from __future__ import annotations

from sqlalchemy import JSON, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class EntityMemory(Base, IdMixin, TimestampMixin):
    """Persistent entity profile (student/teacher/class/session_episode).

    Episodic memory uses entity_type='session_episode'.
    """

    __tablename__ = "entity_memory"

    entity_type: Mapped[str] = mapped_column(String(30))  # student|teacher|class|session_episode
    entity_id: Mapped[str] = mapped_column(String(36))
    school_id: Mapped[str] = mapped_column(String(36))
    facts: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_entity_memory_lookup", "school_id", "entity_type", "entity_id"),
    )


class ProjectState(Base, IdMixin, TimestampMixin):
    """Multi-session project progress (paper writing, courseware generation)."""

    __tablename__ = "project_state"

    project_type: Mapped[str] = mapped_column(String(30))  # paper|courseware
    project_id: Mapped[str] = mapped_column(String(36))
    owner_id: Mapped[str] = mapped_column(String(36))
    school_id: Mapped[str] = mapped_column(String(36))
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    checkpoints: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|paused|completed

    __table_args__ = (
        Index("ix_project_state_owner", "owner_id", "school_id"),
        Index("ix_project_state_lookup", "project_type", "project_id"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_models.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Create Alembic migration**

```bash
cd ~/edu-cloud
# Add import to alembic/env.py
# Then generate migration
python -m alembic revision --autogenerate -m "add entity_memory and project_state tables"
```

After generating, verify the migration file creates both tables with correct columns and indexes.

- [ ] **Step 5.5: Add model imports to metadata assembly paths**

Add `from edu_cloud.models import memory  # noqa: F401` to:
1. `src/edu_cloud/api/app.py` — in the lifespan() model imports block
2. `tests/conftest.py` — in the model imports section
3. `tests/test_alembic_migration.py` — in the model imports section

- [ ] **Step 6: Run migration (dev database)**

```bash
cd ~/edu-cloud && python -m alembic upgrade head
```

- [ ] **Step 7: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/models/memory.py tests/test_ai/test_memory_models.py alembic/
git commit -m "feat(memory): add EntityMemory + ProjectState models + migration"
```

---

### Task 2: MemoryStore CRUD + 冲突合并

**Files:**
- Create: `src/edu_cloud/ai/memory_store.py`
- Test: `tests/test_ai/test_memory_store.py`

**测试契约:**
1. upsert_entity 创建或更新实体记忆
   - 入口: `await store.upsert_entity(db, school_id, entity_type, entity_id, facts)`
   - 反例: 错误实现每次都创建新行而不更新已有行
   - 边界: 空 facts / 已有记忆追加新 fact / 覆盖已有 fact
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_store.py::TestUpsertEntity -v`
2. get_entities 按 DataScope 过滤
   - 入口: `await store.get_entities(db, school_id, entity_type, entity_ids)`
   - 反例: 错误实现返回其他学校的记忆
   - 边界: entity_ids=None（全部）/ entity_ids=[]（空）/ 不存在的 id
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_store.py::TestGetEntities -v`
3. save_project / get_project / update_project_status（租户隔离）
   - 入口: `await store.save_project(db, ...)` / `await store.get_project(db, project_id, owner_id, school_id)`
   - 反例: update_project_status 不更新 updated_at / get_project 不校验 owner_id 导致串读
   - 边界: get 不存在的 project / status 非法值 / get_project with wrong owner_id returns None
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_store.py::TestProjectState -v`
4. cleanup_episodes LRU 淘汰
   - 入口: `await store.cleanup_episodes(db, school_id, max_count=50)`
   - 反例: 错误实现删除最新的而不是最旧的
   - 边界: 记忆数 < max_count（不删除）/ 正好 = max_count
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_store.py::TestCleanup -v`

**审查清单:**
- ✓ upsert 用 school_id + entity_type + entity_id 查重
- ✓ 冲突合并：新 facts 与旧 facts 做 dict merge（新值覆盖旧值，旧值保留）
- ✓ get_entities 强制 school_id 过滤（数据隔离）
- ✓ cleanup_episodes 按 updated_at ASC 删除最旧的
- ✗ 不提供跨 school 查询（fail-closed）

**边界条件:**
- upsert 并发写同一 entity → 期望: 后写覆盖（timestamp 更新）
- facts merge 嵌套 dict → 期望: 浅合并（顶层 key 覆盖）
- cleanup 时无 episode 记忆 → 期望: 不报错，返回 0

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_memory_store.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.models.memory import EntityMemory, ProjectState


@pytest_asyncio.fixture
async def store():
    return MemoryStore()


class TestUpsertEntity:
    @pytest.mark.asyncio
    async def test_create_new(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-1", facts={"math": 0.4},
            )
            assert result.facts["math"] == 0.4

    @pytest.mark.asyncio
    async def test_update_existing_merges_facts(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-1", facts={"math": 0.4},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-1", facts={"english": 0.8},
            )
            assert result.facts["math"] == 0.4  # preserved
            assert result.facts["english"] == 0.8  # added

    @pytest.mark.asyncio
    async def test_update_overwrites_existing_key(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-1", facts={"math": 0.4},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-1", facts={"math": 0.7},
            )
            assert result.facts["math"] == 0.7

    @pytest.mark.asyncio
    async def test_empty_facts(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="teacher",
                entity_id="t-1", facts={},
            )
            assert result.facts == {}


class TestGetEntities:
    @pytest.mark.asyncio
    async def test_get_by_type(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(db, "sch-1", "student", "s1", {"a": 1})
            await store.upsert_entity(db, "sch-1", "student", "s2", {"b": 2})
            await store.upsert_entity(db, "sch-1", "teacher", "t1", {"c": 3})

            results = await store.get_entities(db, "sch-1", "student")
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_school_isolation(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(db, "sch-1", "student", "s1", {"a": 1})
            await store.upsert_entity(db, "sch-2", "student", "s1", {"b": 2})

            results = await store.get_entities(db, "sch-1", "student")
            assert len(results) == 1
            assert results[0].facts["a"] == 1

    @pytest.mark.asyncio
    async def test_get_specific_ids(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(db, "sch-1", "student", "s1", {"a": 1})
            await store.upsert_entity(db, "sch-1", "student", "s2", {"b": 2})
            await store.upsert_entity(db, "sch-1", "student", "s3", {"c": 3})

            results = await store.get_entities(db, "sch-1", "student", entity_ids=["s1", "s3"])
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_empty_ids(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(db, "sch-1", "student", "s1", {"a": 1})
            results = await store.get_entities(db, "sch-1", "student", entity_ids=[])
            assert results == []

    @pytest.mark.asyncio
    async def test_scope_filtering_student(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(db, "sch-1", "student", "s1", {"a": 1})
            await store.upsert_entity(db, "sch-1", "student", "s2", {"b": 2})
            await store.upsert_entity(db, "sch-1", "student", "s3", {"c": 3})
            # Only s1 and s2 visible via DataScope
            results = await store.get_entities(db, "sch-1", "student", visible_student_ids=["s1", "s2"])
            assert len(results) == 2


class TestProjectState:
    @pytest.mark.asyncio
    async def test_save_and_get(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.save_project(
                db, project_type="paper", project_id="p1",
                owner_id="u1", school_id="sch-1",
                state={"topic": "AI教育", "checkpoint": "outline"},
            )
            result = await store.get_project(db, "p1", "u1", "sch-1")
            assert result is not None
            assert result.state["topic"] == "AI教育"
            assert result.status == "active"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            result = await store.get_project(db, "nonexistent", "u1", "sch-1")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_project_wrong_owner(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.save_project(
                db, project_type="paper", project_id="p1",
                owner_id="u1", school_id="sch-1",
                state={"topic": "AI教育"},
            )
            # Different owner should not see the project
            result = await store.get_project(db, "p1", "u2", "sch-1")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_project_wrong_school(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.save_project(
                db, project_type="paper", project_id="p1",
                owner_id="u1", school_id="sch-1", state={},
            )
            result = await store.get_project(db, "p1", "u1", "sch-2")
            assert result is None

    @pytest.mark.asyncio
    async def test_update_status(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.save_project(
                db, project_type="paper", project_id="p1",
                owner_id="u1", school_id="sch-1", state={},
            )
            await store.update_project_status(db, "p1", "u1", "sch-1", "completed")
            result = await store.get_project(db, "p1", "u1", "sch-1")
            assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_update_state(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.save_project(
                db, project_type="paper", project_id="p1",
                owner_id="u1", school_id="sch-1",
                state={"checkpoint": "research"},
            )
            await store.update_project_state(db, "p1", "u1", "sch-1", {"checkpoint": "writing", "sections": 3})
            result = await store.get_project(db, "p1", "u1", "sch-1")
            assert result.state["checkpoint"] == "writing"
            assert result.state["sections"] == 3

    @pytest.mark.asyncio
    async def test_get_active_projects(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.save_project(db, "paper", "p1", "u1", "sch-1", {})
            await store.save_project(db, "paper", "p2", "u1", "sch-1", {})
            await store.update_project_status(db, "p2", "u1", "sch-1", "completed")

            results = await store.get_active_projects(db, "u1", "sch-1")
            assert len(results) == 1
            assert results[0].project_id == "p1"


class TestCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_oldest(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            for i in range(5):
                await store.upsert_entity(
                    db, "sch-1", "session_episode", f"ep-{i}",
                    {"note": f"episode {i}"},
                )
            deleted = await store.cleanup_episodes(db, "sch-1", max_count=3)
            assert deleted == 2
            remaining = await store.get_entities(db, "sch-1", "session_episode")
            assert len(remaining) == 3

    @pytest.mark.asyncio
    async def test_cleanup_under_limit(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(db, "sch-1", "session_episode", "ep-1", {"a": 1})
            deleted = await store.cleanup_episodes(db, "sch-1", max_count=50)
            assert deleted == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement MemoryStore**

```python
# src/edu_cloud/ai/memory_store.py
"""MemoryStore: CRUD + conflict merge for cross-session memory."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.memory import EntityMemory, ProjectState

logger = logging.getLogger(__name__)


class MemoryStore:
    """Persistent memory operations with school-level data isolation."""

    # ── EntityMemory ──

    async def upsert_entity(
        self,
        db: AsyncSession,
        school_id: str,
        entity_type: str,
        entity_id: str,
        facts: dict[str, Any],
    ) -> EntityMemory:
        """Create or update entity memory. New facts merge with existing (shallow)."""
        stmt = select(EntityMemory).where(
            EntityMemory.school_id == school_id,
            EntityMemory.entity_type == entity_type,
            EntityMemory.entity_id == entity_id,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            merged = {**existing.facts, **facts}
            existing.facts = merged
            await db.flush()
            return existing

        mem = EntityMemory(
            entity_type=entity_type,
            entity_id=entity_id,
            school_id=school_id,
            facts=facts,
        )
        db.add(mem)
        await db.flush()
        return mem

    async def get_entities(
        self,
        db: AsyncSession,
        school_id: str,
        entity_type: str,
        entity_ids: list[str] | None = None,
        visible_student_ids: list[str] | None = None,
    ) -> list[EntityMemory]:
        """Get entity memories, filtered by school (mandatory) and optionally by IDs.

        When entity_type="student" and visible_student_ids is provided,
        only entities whose entity_id is in visible_student_ids are returned
        (DataScope filtering).
        """
        if entity_ids is not None and not entity_ids:
            return []

        # DataScope filtering for student entities
        if entity_type == "student" and visible_student_ids is not None:
            if not visible_student_ids:
                return []  # deny-all
            if entity_ids is not None:
                entity_ids = [eid for eid in entity_ids if eid in set(visible_student_ids)]
            else:
                entity_ids = visible_student_ids

        stmt = select(EntityMemory).where(
            EntityMemory.school_id == school_id,
            EntityMemory.entity_type == entity_type,
        )
        if entity_ids is not None:
            stmt = stmt.where(EntityMemory.entity_id.in_(entity_ids))

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def cleanup_episodes(
        self,
        db: AsyncSession,
        school_id: str,
        max_count: int = 50,
    ) -> int:
        """Remove oldest episodic memories exceeding max_count. Returns count deleted."""
        stmt = select(EntityMemory).where(
            EntityMemory.school_id == school_id,
            EntityMemory.entity_type == "session_episode",
        ).order_by(EntityMemory.updated_at.desc())

        result = await db.execute(stmt)
        all_episodes = list(result.scalars().all())

        if len(all_episodes) <= max_count:
            return 0

        to_delete = all_episodes[max_count:]
        ids_to_delete = [e.id for e in to_delete]
        await db.execute(
            delete(EntityMemory).where(EntityMemory.id.in_(ids_to_delete))
        )
        await db.flush()
        return len(ids_to_delete)

    # ── ProjectState ──

    async def save_project(
        self,
        db: AsyncSession,
        project_type: str,
        project_id: str,
        owner_id: str,
        school_id: str,
        state: dict[str, Any],
        status: str = "active",
    ) -> ProjectState:
        proj = ProjectState(
            project_type=project_type,
            project_id=project_id,
            owner_id=owner_id,
            school_id=school_id,
            state=state,
            status=status,
        )
        db.add(proj)
        await db.flush()
        return proj

    async def get_project(
        self,
        db: AsyncSession,
        project_id: str,
        owner_id: str,
        school_id: str,
    ) -> ProjectState | None:
        stmt = select(ProjectState).where(
            ProjectState.project_id == project_id,
            ProjectState.owner_id == owner_id,
            ProjectState.school_id == school_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_project_status(
        self,
        db: AsyncSession,
        project_id: str,
        owner_id: str,
        school_id: str,
        status: str,
    ) -> None:
        stmt = (
            update(ProjectState)
            .where(
                ProjectState.project_id == project_id,
                ProjectState.owner_id == owner_id,
                ProjectState.school_id == school_id,
            )
            .values(status=status)
        )
        await db.execute(stmt)
        await db.flush()

    async def update_project_state(
        self,
        db: AsyncSession,
        project_id: str,
        owner_id: str,
        school_id: str,
        state_updates: dict[str, Any],
    ) -> None:
        proj = await self.get_project(db, project_id, owner_id, school_id)
        if proj is not None:
            merged = {**proj.state, **state_updates}
            proj.state = merged
            await db.flush()

    async def get_active_projects(
        self,
        db: AsyncSession,
        owner_id: str,
        school_id: str,
    ) -> list[ProjectState]:
        stmt = select(ProjectState).where(
            ProjectState.owner_id == owner_id,
            ProjectState.school_id == school_id,
            ProjectState.status == "active",
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_store.py -v`
Expected: All 15 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/memory_store.py tests/test_ai/test_memory_store.py
git commit -m "feat(memory): add MemoryStore with CRUD + conflict merge + LRU cleanup"
```

---

### Task 3: MemoryExtractor（会话结束持久化）

**Files:**
- Create: `src/edu_cloud/ai/memory_extractor.py`
- Test: `tests/test_ai/test_memory_extractor.py`

**测试契约:**
1. extract_and_persist 从会话历史提取并存储记忆
   - 入口: `await extractor.extract_and_persist(db, messages, adapter, school_id, user_id, session_id)`
   - 反例: 错误实现只提取不持久化（现有 session_memory.py 的问题）
   - 边界: messages=[] / LLM 返回无效 JSON / Tier 3 应跳过
   - 回归: 现有 SessionMemoryExtractor 行为保持可用
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_extractor.py -v`

**审查清单:**
- ✓ LLM 提取后调用 MemoryStore.upsert_entity 持久化
- ✓ entity 类型记忆写入 EntityMemory 表
- ✓ 会话摘要写入 entity_type="session_episode"
- ✓ LLM 提取失败时不崩溃（graceful degradation）
- ✗ 不阻塞 SSE 响应（extraction 在 finally 块异步执行）

**边界条件:**
- messages=[]（空对话）→ 期望: 直接返回，不调用 LLM
- LLM 返回非 JSON / 空字符串 → 期望: 不崩溃，不持久化任何记忆
- LLM 返回含 markdown code block 的 JSON → 期望: 正确剥离 ``` 后解析

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_memory_extractor.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from edu_cloud.ai.memory_extractor import MemoryExtractor
from edu_cloud.ai.llm_adapter import LLMResponse, TokenUsage
from edu_cloud.ai.schemas import Message
from edu_cloud.ai.memory_store import MemoryStore


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content='[{"type": "entity", "entity_type": "student", "entity_id": "stu-1", '
                '"facts": {"math_mastery": 0.4}}, '
                '{"type": "episode", "summary": "讨论了学生数学成绩"}]',
        stop_reason="end_turn",
        usage=TokenUsage(100, 50),
    ))
    return adapter


@pytest.fixture
def mock_store():
    store = MagicMock(spec=MemoryStore)
    store.upsert_entity = AsyncMock()
    store.cleanup_episodes = AsyncMock(return_value=0)
    return store


class TestMemoryExtractor:
    @pytest.mark.asyncio
    async def test_extract_and_persist(self, mock_adapter, mock_store):
        extractor = MemoryExtractor(store=mock_store)
        messages = [
            Message(role="user", content="张三的数学成绩怎么样？"),
            Message(role="assistant", content="张三数学掌握率 40%，建议加强函数图像"),
        ]
        await extractor.extract_and_persist(
            db=MagicMock(), messages=messages, adapter=mock_adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        # Should persist entity memory
        assert mock_store.upsert_entity.call_count >= 1
        # Should persist episodic memory
        calls = mock_store.upsert_entity.call_args_list
        entity_types = [c.kwargs.get("entity_type") or c.args[2] for c in calls]
        assert "student" in entity_types or "session_episode" in entity_types

    @pytest.mark.asyncio
    async def test_empty_messages_skips(self, mock_adapter, mock_store):
        extractor = MemoryExtractor(store=mock_store)
        await extractor.extract_and_persist(
            db=MagicMock(), messages=[], adapter=mock_adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        mock_adapter.chat.assert_not_called()
        mock_store.upsert_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self, mock_store):
        adapter = MagicMock()
        adapter.chat = AsyncMock(side_effect=Exception("LLM unavailable"))
        extractor = MemoryExtractor(store=mock_store)
        # Should not raise
        await extractor.extract_and_persist(
            db=MagicMock(),
            messages=[Message(role="user", content="test")],
            adapter=adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        mock_store.upsert_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_json_graceful(self, mock_store):
        adapter = MagicMock()
        adapter.chat = AsyncMock(return_value=LLMResponse(
            content="not valid json",
            stop_reason="end_turn",
            usage=TokenUsage(100, 50),
        ))
        extractor = MemoryExtractor(store=mock_store)
        await extractor.extract_and_persist(
            db=MagicMock(),
            messages=[Message(role="user", content="test")],
            adapter=adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        mock_store.upsert_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_called(self, mock_adapter, mock_store):
        extractor = MemoryExtractor(store=mock_store)
        await extractor.extract_and_persist(
            db=MagicMock(),
            messages=[Message(role="user", content="test")],
            adapter=mock_adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        mock_store.cleanup_episodes.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement MemoryExtractor**

```python
# src/edu_cloud/ai/memory_extractor.py
"""MemoryExtractor: extract + persist cross-session memories from conversation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """\
你是记忆提取器。从以下对话中提取值得跨会话保存的信息。

提取两类：
1. entity — 关于特定实体（学生/教师/班级）的事实
2. episode — 本次会话的关键决策或发现摘要

回复 JSON 数组，每项格式：
- entity: {"type": "entity", "entity_type": "student|teacher|class", "entity_id": "ID", "facts": {"key": "value"}}
- episode: {"type": "episode", "summary": "一句话摘要"}

如果没有值得保存的信息，回复 []。只回复 JSON，不要其他内容。
"""

_MAX_EPISODES = 50


class MemoryExtractor:
    """Extract memories from conversation and persist via MemoryStore."""

    def __init__(self, store: MemoryStore | None = None):
        self._store = store or MemoryStore()

    async def extract_and_persist(
        self,
        db: AsyncSession,
        messages: list[Message],
        adapter: LLMProxyAdapter,
        school_id: str,
        user_id: str,
        session_id: str,
    ) -> None:
        """Extract memories from messages and persist to database.

        Gracefully handles all failures — never raises.
        """
        if not messages:
            return

        try:
            entries = await self._extract(messages, adapter)
            if not entries:
                return
            await self._persist(db, entries, school_id, user_id, session_id)
            await self._store.cleanup_episodes(db, school_id, max_count=_MAX_EPISODES)
            await db.commit()
        except Exception:
            logger.exception("Memory extraction failed (non-blocking)")

    async def _extract(
        self,
        messages: list[Message],
        adapter: LLMProxyAdapter,
    ) -> list[dict[str, Any]]:
        """Use LLM to extract memory entries from conversation."""
        conversation = "\n".join(
            f"{m.role}: {m.content}" for m in messages
            if m.role in ("user", "assistant") and m.content
        )
        if not conversation.strip():
            return []

        resp = await adapter.chat(LLMRequest(
            messages=[
                Message(role="system", content=_EXTRACT_PROMPT),
                Message(role="user", content=conversation[-6000:]),  # limit context
            ],
            max_tokens=1000,
            stream=False,
        ))

        return self._parse(resp.content or "")

    @staticmethod
    def _parse(text: str) -> list[dict[str, Any]]:
        """Parse LLM response into memory entries."""
        text = text.strip()
        # Strip markdown code block if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        try:
            data = json.loads(text)
            if not isinstance(data, list):
                return []
            return [e for e in data if isinstance(e, dict) and "type" in e]
        except (json.JSONDecodeError, ValueError):
            return []

    async def _persist(
        self,
        db: AsyncSession,
        entries: list[dict[str, Any]],
        school_id: str,
        user_id: str,
        session_id: str,
    ) -> None:
        """Write extracted entries to database via MemoryStore."""
        for entry in entries:
            entry_type = entry.get("type")

            if entry_type == "entity":
                entity_type = entry.get("entity_type", "")
                entity_id = entry.get("entity_id", "")
                facts = entry.get("facts", {})
                if entity_type and entity_id and facts:
                    await self._store.upsert_entity(
                        db, school_id=school_id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        facts=facts,
                    )

            elif entry_type == "episode":
                summary = entry.get("summary", "")
                if summary:
                    await self._store.upsert_entity(
                        db, school_id=school_id,
                        entity_type="session_episode",
                        entity_id=session_id,
                        facts={"summary": summary, "user_id": user_id},
                    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_extractor.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/memory_extractor.py tests/test_ai/test_memory_extractor.py
git commit -m "feat(memory): add MemoryExtractor with LLM extraction + DB persistence"
```

---

### Task 4: MemoryInjector（会话启动加载）

**Files:**
- Create: `src/edu_cloud/ai/memory_injector.py`
- Test: `tests/test_ai/test_memory_injector.py`

**测试契约:**
1. build_context 加载相关记忆并格式化
   - 入口: `context = await injector.build_context(db, school_id, user_id, role, class_ids)`
   - 反例: 错误实现不过滤 school_id，加载其他学校的记忆
   - 边界: 无记忆 / 记忆超 token 预算 / role=parent 只看自己孩子
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_injector.py -v`

**审查清单:**
- ✓ 按 DataScope 过滤（school_id 强制，class_ids/student_ids 可选）
- ✓ Token 预算控制：记忆总长度不超过 context_window 的 15%
- ✓ 返回格式化文本（可直接拼入 system prompt）
- ✓ 加载 active projects 供 Agent 感知进行中的任务
- ✗ 不加载 entity_type="session_episode" 超过 5 条

**边界条件:**
- 无记忆（空数据库）→ 期望: 返回空字符串，不影响 system prompt
- 记忆超 token 预算 → 期望: 截断到预算以内，末尾标注"已截断"
- episodic memory > 5 条 → 期望: 只注入最近 5 条
- role=subject_teacher（有 class_ids 无 student_ids）→ 期望: 跳过 student 记忆注入（安全默认），教师可通过 memory_read 工具主动查询

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_memory_injector.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from edu_cloud.ai.memory_injector import MemoryInjector
from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.models.memory import EntityMemory, ProjectState


@pytest.fixture
def mock_store():
    store = MagicMock(spec=MemoryStore)
    store.get_entities = AsyncMock(return_value=[])
    store.get_active_projects = AsyncMock(return_value=[])
    return store


class TestMemoryInjector:
    @pytest.mark.asyncio
    async def test_no_memory_returns_empty(self, mock_store):
        injector = MemoryInjector(store=mock_store, max_tokens=2000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="teacher", class_ids=["c1"],
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_entity_memory_formatted(self, mock_store):
        mem = MagicMock(spec=EntityMemory)
        mem.entity_type = "student"
        mem.entity_id = "stu-1"
        mem.facts = {"math_mastery": 0.4, "weakness": "函数图像"}
        mock_store.get_entities = AsyncMock(return_value=[mem])

        injector = MemoryInjector(store=mock_store, max_tokens=2000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="teacher", class_ids=["c1"],
        )
        assert "student" in result
        assert "stu-1" in result
        assert "函数图像" in result

    @pytest.mark.asyncio
    async def test_project_state_included(self, mock_store):
        proj = MagicMock(spec=ProjectState)
        proj.project_type = "paper"
        proj.project_id = "p1"
        proj.state = {"topic": "深度学习", "checkpoint": "writing"}
        proj.status = "active"
        mock_store.get_active_projects = AsyncMock(return_value=[proj])

        injector = MemoryInjector(store=mock_store, max_tokens=2000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="teacher",
        )
        assert "paper" in result
        assert "深度学习" in result

    @pytest.mark.asyncio
    async def test_token_budget_truncation(self, mock_store):
        # Create many memories that exceed budget
        mems = []
        for i in range(50):
            m = MagicMock(spec=EntityMemory)
            m.entity_type = "student"
            m.entity_id = f"s-{i}"
            m.facts = {"detail": f"这是一段很长的描述内容用来测试token预算控制机制第{i}条" * 5}
            mems.append(m)
        mock_store.get_entities = AsyncMock(return_value=mems)

        injector = MemoryInjector(store=mock_store, max_tokens=500)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="teacher",
        )
        # Should be truncated, not include all 50
        assert len(result) < 500 * 4  # rough char estimate

    @pytest.mark.asyncio
    async def test_episodes_limited(self, mock_store):
        episodes = []
        for i in range(10):
            m = MagicMock(spec=EntityMemory)
            m.entity_type = "session_episode"
            m.entity_id = f"ep-{i}"
            m.facts = {"summary": f"Episode {i}"}
            episodes.append(m)
        mock_store.get_entities = AsyncMock(return_value=episodes)

        injector = MemoryInjector(store=mock_store, max_tokens=5000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="teacher",
        )
        # Should only include last 5 episodes
        assert result.count("Episode") <= 5

    @pytest.mark.asyncio
    async def test_teacher_scope_skips_student_injection(self, mock_store):
        """Teachers with class_ids but no student_ids should skip student memory injection (R3-F002)."""
        # Use side_effect to return different results per entity_type call
        async def mock_get_entities(db, school_id, entity_type, **kwargs):
            if entity_type == "student":
                m = MagicMock(spec=EntityMemory)
                m.entity_type = "student"
                m.entity_id = "stu-1"
                m.facts = {"math": 0.4}
                return [m]
            return []  # no teacher/class/episode memories

        mock_store.get_entities = AsyncMock(side_effect=mock_get_entities)

        injector = MemoryInjector(store=mock_store, max_tokens=2000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="subject_teacher", class_ids=["c1"],  # has class scope
            # student_ids=None — teacher doesn't have student-level scope
        )
        # Student entity type should be skipped entirely (continue branch)
        # so get_entities should never be called with entity_type="student"
        student_calls = [c for c in mock_store.get_entities.call_args_list
                        if c.args[2] == "student" or c.kwargs.get("entity_type") == "student"]
        assert len(student_calls) == 0, "Should skip student query when teacher has class_ids but no student_ids"
        assert "stu-1" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_injector.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement MemoryInjector**

```python
# src/edu_cloud/ai/memory_injector.py
"""MemoryInjector: load relevant memories at session start for system prompt."""

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.memory_store import MemoryStore

logger = logging.getLogger(__name__)

_MAX_EPISODES = 5


class MemoryInjector:
    """Loads cross-session memories and formats for system prompt injection."""

    def __init__(
        self,
        store: MemoryStore | None = None,
        max_tokens: int = 2000,
    ):
        self._store = store or MemoryStore()
        self._max_tokens = max_tokens

    async def build_context(
        self,
        db: AsyncSession,
        school_id: str,
        user_id: str,
        role: str | None = None,
        class_ids: list[str] | None = None,
        student_ids: list[str] | None = None,
    ) -> str:
        """Build memory context string for system prompt injection.

        Returns empty string if no relevant memories found.
        Token budget: self._max_tokens (rough estimate: 1 token ≈ 2 chars Chinese).
        """
        sections: list[str] = []
        char_budget = self._max_tokens * 2  # rough token→char conversion

        try:
            # Entity memories (students in scope)
            for etype in ("student", "teacher", "class"):
                eids = None
                if etype == "student":
                    if student_ids is not None:
                        # Parent or explicit scope: filter by student_ids
                        eids = student_ids
                    elif class_ids is not None:
                        # Teacher: has class scope but not student scope
                        # Skip student memories in passive injection (safe default)
                        # Teachers can use memory_read tool for active queries
                        continue
                    # else: full school access (principal/admin), load all
                entities = await self._store.get_entities(db, school_id, etype, entity_ids=eids, visible_student_ids=student_ids)
                if entities:
                    lines = [f"[{etype}] {e.entity_id}: {json.dumps(e.facts, ensure_ascii=False)}"
                             for e in entities]
                    sections.append("\n".join(lines))

            # Episodic memories (last N)
            episodes = await self._store.get_entities(db, school_id, "session_episode")
            if episodes:
                recent = episodes[-_MAX_EPISODES:]
                lines = [f"[历史] {e.facts.get('summary', '')}" for e in recent]
                sections.append("\n".join(lines))

            # Active projects
            projects = await self._store.get_active_projects(db, user_id, school_id)
            if projects:
                lines = []
                for p in projects:
                    checkpoint = p.state.get("checkpoint", "unknown")
                    topic = p.state.get("topic", p.project_id)
                    lines.append(f"[进行中/{p.project_type}] {topic} — 当前阶段: {checkpoint}")
                sections.append("\n".join(lines))

        except Exception:
            logger.exception("Memory injection failed (non-blocking)")
            return ""

        if not sections:
            return ""

        full_text = "\n\n".join(sections)

        # Truncate to budget
        if len(full_text) > char_budget:
            full_text = full_text[:char_budget] + "\n... (记忆已截断)"

        return f"\n\n【已知上下文（跨会话记忆）】\n{full_text}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_injector.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/memory_injector.py tests/test_ai/test_memory_injector.py
git commit -m "feat(memory): add MemoryInjector for session-start memory loading"
```

---

### Task 5: memory_read / memory_write 工具

**Files:**
- Create: `src/edu_cloud/ai/tools/memory_tools.py`
- Modify: `src/edu_cloud/ai/tools/__init__.py`
- Test: `tests/test_ai/test_memory_tools.py`

**测试契约:**
1. memory_read 查询实体记忆
   - 入口: `POST /api/v1/ai/chat` → Agent 调用 memory_read tool
   - 反例: 错误实现不过滤 school_id
   - 边界: 查询不存在的 entity / entity_type 非法
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_tools.py -v`
2. memory_write 写入实体记忆
   - 入口: Agent 调用 memory_write tool
   - 反例: 错误实现覆盖而非合并 facts
   - 边界: facts={} / 写入已有 entity
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_tools.py -v`

**审查清单:**
- ✓ 工具注册时声明 domain="system", sensitivity="school"
- ✓ allowed_roles 限制为 subject_teacher/homeroom_teacher/grade_leader/academic_director/principal
- ✓ memory_write 的 is_read_only=False
- ✓ 使用 ctx.school_id 强制数据隔离
- ✗ 不提供删除工具（防误删）

**边界条件:**
- memory_read 查询不存在的 entity → 期望: 返回 success=True, data=[]
- memory_write facts 为空 dict → 期望: 返回 success=False, error 包含"空"
- memory_read entity_type 为 session_episode → 期望: 正常返回历史摘要

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_memory_tools.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.tool_context import ToolContext, ToolResult


class TestMemoryReadTool:
    @pytest.mark.asyncio
    async def test_read_entity(self):
        from edu_cloud.ai.tools.memory_tools import memory_read

        ctx = MagicMock(spec=ToolContext)
        ctx.school_id = "sch-1"
        ctx.db = MagicMock()
        ctx.data_scope = MagicMock()
        ctx.data_scope.visible_student_ids = ["stu-1", "stu-2"]

        with patch("edu_cloud.ai.tools.memory_tools._store") as mock_store:
            mock_entity = MagicMock()
            mock_entity.entity_id = "stu-1"
            mock_entity.facts = {"math": 0.4}
            mock_store.get_entities = AsyncMock(return_value=[mock_entity])

            result = await memory_read(
                {"entity_type": "student", "entity_ids": ["stu-1"]},
                ctx,
            )
            assert result.success
            assert len(result.data) == 1
            mock_store.get_entities.assert_called_once_with(
                ctx.db, "sch-1", "student", entity_ids=["stu-1"],
                visible_student_ids=["stu-1", "stu-2"],
            )

    @pytest.mark.asyncio
    async def test_read_all_of_type(self):
        from edu_cloud.ai.tools.memory_tools import memory_read

        ctx = MagicMock(spec=ToolContext)
        ctx.school_id = "sch-1"
        ctx.db = MagicMock()
        ctx.data_scope = MagicMock()
        ctx.data_scope.visible_student_ids = None

        with patch("edu_cloud.ai.tools.memory_tools._store") as mock_store:
            mock_store.get_entities = AsyncMock(return_value=[])
            result = await memory_read({"entity_type": "student"}, ctx)
            assert result.success
            mock_store.get_entities.assert_called_once_with(
                ctx.db, "sch-1", "student", entity_ids=None,
                visible_student_ids=None,
            )


class TestMemoryWriteTool:
    @pytest.mark.asyncio
    async def test_write_entity(self):
        from edu_cloud.ai.tools.memory_tools import memory_write

        ctx = MagicMock(spec=ToolContext)
        ctx.school_id = "sch-1"
        ctx.db = MagicMock()

        with patch("edu_cloud.ai.tools.memory_tools._store") as mock_store:
            mock_result = MagicMock()
            mock_result.entity_id = "stu-1"
            mock_result.facts = {"math": 0.7}
            mock_store.upsert_entity = AsyncMock(return_value=mock_result)

            result = await memory_write(
                {"entity_type": "student", "entity_id": "stu-1",
                 "facts": {"math": 0.7}},
                ctx,
            )
            assert result.success
            mock_store.upsert_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_empty_facts(self):
        from edu_cloud.ai.tools.memory_tools import memory_write

        ctx = MagicMock(spec=ToolContext)
        ctx.school_id = "sch-1"
        ctx.db = MagicMock()

        result = await memory_write(
            {"entity_type": "student", "entity_id": "stu-1", "facts": {}},
            ctx,
        )
        assert not result.success
        assert "空" in result.error


class TestToolRegistration:
    def test_tools_registered(self):
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        assert tools.get("memory_read") is not None
        assert tools.get("memory_write") is not None

    def test_memory_write_not_readonly(self):
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        spec = tools.get("memory_write")
        assert not spec.is_read_only

    def test_tools_have_capabilities(self):
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        read_spec = tools.get("memory_read")
        write_spec = tools.get("memory_write")
        assert ("system", "read") in read_spec.requires_capabilities
        assert ("system", "write") in write_spec.requires_capabilities
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_tools.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement memory tools**

```python
# src/edu_cloud/ai/tools/memory_tools.py
"""Agent tools for reading/writing cross-session memory."""

from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult

_store = MemoryStore()


@tools.register(
    name="memory_read",
    description="查询跨会话记忆：学生画像、教师偏好、历史会话摘要。"
                "参数: entity_type (student/teacher/class/session_episode), "
                "entity_ids (可选，不传则返回全部)。",
    parameters={
        "type": "object",
        "properties": {
            "entity_type": {
                "type": "string",
                "enum": ["student", "teacher", "class", "session_episode"],
                "description": "实体类型",
            },
            "entity_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "实体 ID 列表（可选，不传返回全部）",
            },
        },
        "required": ["entity_type"],
    },
    domain="system",
    sensitivity="school",
    allowed_roles=["subject_teacher", "homeroom_teacher", "grade_leader", "academic_director", "principal"],
    requires_capabilities=[("system", "read")],
    is_read_only=True,
)
async def memory_read(input_data: dict, ctx: ToolContext) -> ToolResult:
    entity_type = input_data["entity_type"]
    entity_ids = input_data.get("entity_ids")

    # DataScope filtering for student entities
    visible_student_ids = None
    if entity_type == "student" and ctx.data_scope:
        visible_student_ids = ctx.data_scope.visible_student_ids

    entities = await _store.get_entities(
        ctx.db, ctx.school_id, entity_type, entity_ids=entity_ids,
        visible_student_ids=visible_student_ids,
    )

    data = [
        {"entity_id": e.entity_id, "facts": e.facts}
        for e in entities
    ]
    return ToolResult(success=True, data=data)


@tools.register(
    name="memory_write",
    description="写入跨会话记忆：保存学生学情发现、教师偏好等。"
                "新 facts 与已有 facts 合并（不覆盖）。"
                "参数: entity_type, entity_id, facts (dict)。",
    parameters={
        "type": "object",
        "properties": {
            "entity_type": {
                "type": "string",
                "enum": ["student", "teacher", "class"],
                "description": "实体类型",
            },
            "entity_id": {
                "type": "string",
                "description": "实体 ID",
            },
            "facts": {
                "type": "object",
                "description": "要保存的事实键值对",
            },
        },
        "required": ["entity_type", "entity_id", "facts"],
    },
    domain="system",
    sensitivity="school",
    allowed_roles=["subject_teacher", "homeroom_teacher", "grade_leader", "academic_director", "principal"],
    requires_capabilities=[("system", "write")],
    is_read_only=False,
)
async def memory_write(input_data: dict, ctx: ToolContext) -> ToolResult:
    entity_type = input_data["entity_type"]
    entity_id = input_data["entity_id"]
    facts = input_data.get("facts", {})

    if not facts:
        return ToolResult(success=False, error="facts 不能为空")

    result = await _store.upsert_entity(
        ctx.db, school_id=ctx.school_id,
        entity_type=entity_type,
        entity_id=entity_id,
        facts=facts,
    )
    return ToolResult(
        success=True,
        data={"entity_id": result.entity_id, "facts": result.facts},
    )
```

Add import to `src/edu_cloud/ai/tools/__init__.py`:

```python
from edu_cloud.ai.tools import memory_tools       # noqa: F401
```

- [ ] **Step 3.5: Update DEFAULT_CAPABILITIES for memory access**

In `src/edu_cloud/services/capability_service.py`, add `("system", {"read": True})` to the role templates that should access memory tools:

- `grade_leader`: add `("system", {"read": True})` to its domain list
- `homeroom_teacher`: add `("system", {"read": True})` to its domain list
- `subject_teacher`: add `("system", {"read": True})` to its domain list

This enables memory_read for all teacher roles. memory_write requires `("system", "write")` which only principal has by default (academic_director has system.read but not system.write). Schools can enable/disable per role via capability API.

Add test in `tests/test_ai/test_memory_tools.py`:

```python
class TestToolAccessIntegration:
    def test_subject_teacher_can_read_memory(self):
        """Verify ToolAccessResolver allows subject_teacher to use memory_read."""
        from edu_cloud.ai.tool_access import ToolAccessResolver
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        resolver = ToolAccessResolver()
        spec = tools.get("memory_read")
        # subject_teacher with system.read capability
        caps = {("system", "read"): True}
        allowed = resolver._check_capabilities(spec.requires_capabilities, caps)
        assert allowed

    def test_subject_teacher_denied_write_without_cap(self):
        """Verify ToolAccessResolver denies memory_write without system.write."""
        from edu_cloud.ai.tool_access import ToolAccessResolver
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        resolver = ToolAccessResolver()
        spec = tools.get("memory_write")
        # subject_teacher only has system.read
        caps = {("system", "read"): True}
        allowed = resolver._check_capabilities(spec.requires_capabilities, caps)
        assert not allowed


class TestDefaultCapabilitiesIntegration:
    """Verify DEFAULT_CAPABILITIES actually includes system.read for teacher roles (R3-F001)."""

    @pytest.mark.asyncio
    async def test_init_creates_system_read_for_teachers(self, db_engine):
        """After init_school_capabilities, subject_teacher/homeroom_teacher/grade_leader have system.read."""
        from edu_cloud.services.capability_service import init_school_capabilities, DEFAULT_CAPABILITIES

        for role in ("subject_teacher", "homeroom_teacher", "grade_leader"):
            caps = DEFAULT_CAPABILITIES.get(role, {})
            assert "system" in caps, f"{role} missing 'system' domain in DEFAULT_CAPABILITIES"
            assert caps["system"].get("read") is True, f"{role} missing system.read"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_tools.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/tools/memory_tools.py src/edu_cloud/ai/tools/__init__.py src/edu_cloud/services/capability_service.py tests/test_ai/test_memory_tools.py
git commit -m "feat(memory): add memory_read + memory_write agent tools + DEFAULT_CAPABILITIES update"
```

---

### Task 6: Supervisor + API 集成

**Files:**
- Modify: `src/edu_cloud/ai/supervisor.py`
- Modify: `src/edu_cloud/api/ai.py`
- Test: `tests/test_ai/test_memory_integration.py`

**测试契约:**
1. Supervisor 接受 memory_extractor 并在会话后调用
   - 入口: `Supervisor(registry, adapter, strategy, memory_extractor=extractor)`
   - 反例: 错误实现不调用 extractor
   - 边界: memory_extractor=None（跳过）/ Tier 3（跳过）
   - 回归: 现有 Supervisor 行为不变
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_integration.py -v`
2. API 端点注入记忆上下文到 system prompt
   - 入口: `POST /api/v1/ai/chat`
   - 反例: 不调用 MemoryInjector
   - 边界: 无记忆时 system prompt 不变
   - 回归: 现有 1327 tests 全部通过
   - 命令: `cd ~/edu-cloud && python -m pytest --tb=short -q`

**审查清单:**
- ✓ Supervisor.__init__ 新增 memory_extractor 可选参数
- ✓ handle() 的 finally 块调用 extractor（Tier 1 only）
- ✓ api/ai.py 创建 MemoryInjector + MemoryExtractor 并传入 Supervisor
- ✓ memory context 拼在 system_prompt 后面
- ✗ 不修改 SSE 事件格式

**边界条件:**
- Supervisor memory_extractor=None → 期望: 完全跳过记忆提取，行为不变
- Tier 3 策略 → 期望: 跳过记忆提取（即使 extractor 不为 None）
- session_id=None → 期望: 跳过记忆提取

- [ ] **Step 1: Write integration tests**

```python
# tests/test_ai/test_memory_integration.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.supervisor import Supervisor
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.memory_extractor import MemoryExtractor
from edu_cloud.ai.memory_injector import MemoryInjector
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.tool_context import ToolContext


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=LLMProxyAdapter)
    adapter.context_window_size.return_value = 128_000
    adapter._base_url = "http://localhost:8100"
    adapter._context_window = 128_000
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="回答",
        stop_reason="end_turn",
        usage=TokenUsage(100, 50),
    ))
    adapter.close = AsyncMock()
    return adapter


class TestSupervisorMemoryIntegration:
    @pytest.mark.asyncio
    async def test_extractor_called_after_run(self, mock_adapter):
        extractor = MagicMock(spec=MemoryExtractor)
        extractor.extract_and_persist = AsyncMock()

        reg = ToolRegistry()
        supervisor = Supervisor(
            registry=reg,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(1),
            memory_extractor=extractor,
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = MagicMock()
        ctx.school_id = "sch-1"
        ctx.user_id = "u-1"
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        async for _ in supervisor.handle(
            message="test",
            ctx=ctx,
            tool_specs=[],
            system_prompt="",
            session_id="sess-1",
        ):
            pass

        extractor.extract_and_persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_extractor_skipped_tier3(self, mock_adapter):
        extractor = MagicMock(spec=MemoryExtractor)
        extractor.extract_and_persist = AsyncMock()

        reg = ToolRegistry()
        supervisor = Supervisor(
            registry=reg,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(3),
            memory_extractor=extractor,
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = MagicMock()
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        async for _ in supervisor.handle(
            message="test", ctx=ctx, tool_specs=[], system_prompt="",
        ):
            pass

        extractor.extract_and_persist.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_extractor_no_error(self, mock_adapter):
        reg = ToolRegistry()
        supervisor = Supervisor(
            registry=reg,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(1),
            memory_extractor=None,
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = MagicMock()
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        events = []
        async for event in supervisor.handle(
            message="test", ctx=ctx, tool_specs=[], system_prompt="",
        ):
            events.append(event)
        assert len(events) > 0


class TestMemoryInjectorIntegration:
    @pytest.mark.asyncio
    async def test_injector_appends_to_prompt(self):
        injector = MagicMock(spec=MemoryInjector)
        injector.build_context = AsyncMock(
            return_value="\n\n【已知上下文】\n[student] stu-1: {\"math\": 0.4}"
        )

        ctx = MagicMock()
        ctx.db = MagicMock()
        ctx.school_id = "sch-1"
        ctx.user_id = "u-1"

        context = await injector.build_context(
            db=ctx.db, school_id="sch-1", user_id="u-1", role="teacher",
        )
        system_prompt = "你是教育助手" + context
        assert "已知上下文" in system_prompt
        assert "math" in system_prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_integration.py -v`
Expected: FAIL (Supervisor doesn't accept memory_extractor yet)

- [ ] **Step 3: Modify Supervisor to accept memory_extractor**

In `src/edu_cloud/ai/supervisor.py`, modify `__init__` to add:

```python
    def __init__(
        self,
        registry: ToolRegistry,
        adapter: LLMProxyAdapter,
        strategy: LoopStrategy,
        team_registry: TeamRegistry | None = None,
        sensitivity_router: SensitivityRouter | None = None,
        memory_extractor: "MemoryExtractor | None" = None,
    ):
        # ... existing assignments ...
        self._memory_extractor = memory_extractor
```

Add import at top:
```python
from edu_cloud.ai.memory_extractor import MemoryExtractor
```

At the end of `handle()`, add memory extraction in the finally block after yielding all events. Modify handle() to accept `session_id`:

```python
    async def handle(
        self,
        message: str,
        ctx: ToolContext,
        *,
        tool_specs: list[ToolSpec],
        system_prompt: str = "",
        history: list[Message] | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
```

After the main logic completes (before the final return), add:

```python
        # Post-run: extract and persist memory (Tier 1 only, non-blocking)
        if (
            self._memory_extractor
            and self._strategy.tier == 1
            and self._history
            and session_id
        ):
            try:
                await self._memory_extractor.extract_and_persist(
                    db=ctx.db,
                    messages=self._history,
                    adapter=self._adapter,
                    school_id=ctx.school_id,
                    user_id=ctx.user_id,
                    session_id=session_id,
                )
            except Exception:
                logger.exception("Memory extraction failed (non-blocking)")
```

- [ ] **Step 4: Modify api/ai.py to use Injector + Extractor**

In `src/edu_cloud/api/ai.py`, add imports:

```python
from edu_cloud.ai.memory_injector import MemoryInjector
from edu_cloud.ai.memory_extractor import MemoryExtractor
from edu_cloud.ai.memory_store import MemoryStore
```

Before Supervisor creation (around line 240), add memory injection:

```python
    # Memory injection
    memory_store = MemoryStore()
    memory_injector = MemoryInjector(store=memory_store)
    memory_context = ""
    if strategy.tier <= 2:
        try:
            memory_context = await memory_injector.build_context(
                db=db, school_id=school_id, user_id=str(user.id),
                role=role,
                class_ids=class_ids,
            )
        except Exception:
            logger.exception("Memory injection failed (non-blocking)")

    memory_extractor = MemoryExtractor(store=memory_store) if strategy.tier == 1 else None
```

Pass to Supervisor:

```python
    supervisor = Supervisor(
        registry=tools,
        adapter=primary_adapter,
        strategy=strategy,
        team_registry=team_registry,
        sensitivity_router=sensitivity_router,
        memory_extractor=memory_extractor,
    )
```

Append memory context to system prompt:

```python
    full_system_prompt = system_prompt + memory_context
```

Pass session_id to supervisor.handle():

```python
    async for event in supervisor.handle(
        message=message,
        ctx=tool_ctx,
        tool_specs=available_tools,
        system_prompt=full_system_prompt,
        history=session_state.history,
        session_id=session_id,
    ):
```

- [ ] **Step 5: Run integration tests**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_integration.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Run full test suite for regression**

Run: `cd ~/edu-cloud && python -m pytest --tb=short -q`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/supervisor.py src/edu_cloud/api/ai.py tests/test_ai/test_memory_integration.py
git commit -m "feat(memory): integrate MemoryExtractor + MemoryInjector into Supervisor + API"
```

---

### Task 7: 全量回归 + 验证

**Files:** 无新文件

- [ ] **Step 1: Run full backend test suite**

Run: `cd ~/edu-cloud && python -m pytest --tb=short -q`
Expected: All tests PASS (1327+ existing + ~40 new)

- [ ] **Step 2: Run AI-specific tests**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/ -v --tb=short`
Expected: All PASS

- [ ] **Step 3: Count new Phase 2 tests**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_memory_models.py tests/test_ai/test_memory_store.py tests/test_ai/test_memory_extractor.py tests/test_ai/test_memory_injector.py tests/test_ai/test_memory_tools.py tests/test_ai/test_memory_integration.py -v 2>&1 | tail -5`
Expected: ~40 new tests PASS

- [ ] **Step 4: Verify Alembic migration**

Run: `cd ~/edu-cloud && python -m alembic upgrade head && python -m alembic downgrade -1 && python -m alembic upgrade head`
Expected: Migration up/down/up succeeds without error

- [ ] **Step 5: Verify git diff**

Run: `cd ~/edu-cloud && git diff --stat HEAD~6`
Expected: ~600 LOC new across listed files

- [ ] **Step 6: Tag**

```bash
cd ~/edu-cloud && git tag -a v0.10.0-memory-system -m "Phase 2: Cross-session memory system"
```

---

## Contract Pack

```yaml
contract_pack:
  invariants:
    - id: INV-001
      description: "EntityMemory 数据隔离：get_entities 查询必须强制 school_id 过滤，student 类型必须受 DataScope.visible_student_ids 约束"
      verification: pending_test
      test_ref: "tests/test_ai/test_memory_store.py::TestGetEntities::test_school_isolation, test_scope_filtering_student"
    - id: INV-002
      description: "ProjectState 租户隔离：所有 ProjectState 读写必须同时校验 owner_id + school_id"
      verification: pending_test
      test_ref: "tests/test_ai/test_memory_store.py::TestProjectState::test_get_project_wrong_owner, test_get_project_wrong_school"
    - id: INV-003
      description: "memory_read/write 工具访问控制：必须声明 requires_capabilities 并经 tool_access.py capability 过滤"
      verification: pending_test
      test_ref: "tests/test_ai/test_memory_tools.py::TestToolRegistration::test_tools_have_capabilities, TestToolAccessIntegration::test_subject_teacher_can_read_memory, test_subject_teacher_denied_write_without_cap"
    - id: INV-004
      description: "MemoryExtractor 故障隔离：LLM 提取失败不影响正常对话响应"
      verification: pending_test
      test_ref: "tests/test_ai/test_memory_extractor.py::TestMemoryExtractor::test_llm_failure_graceful"
    - id: INV-005
      description: "向后兼容：不传 memory_extractor 时 Supervisor 行为完全不变"
      verification: pending_test
      test_ref: "tests/test_ai/test_memory_integration.py::TestSupervisorMemoryIntegration::test_no_extractor_no_error"

  counter_examples:
    - id: CE-001
      description: "跨校读取记忆：school A 的教师读到 school B 的学生画像"
      tests_that_still_pass: "test_school_isolation 会失败"
      mitigation: "get_entities 强制 school_id WHERE 过滤"
    - id: CE-002
      description: "scope 外读取：科任教师读到非自己班级学生画像"
      tests_that_still_pass: "test_scope_filtering_student 会失败"
      mitigation: "memory_read 工具通过 ctx.data_scope.visible_student_ids 过滤"
    - id: CE-003
      description: "ProjectState 串读：用户 A 读到用户 B 的项目状态"
      tests_that_still_pass: "test_get_project_wrong_owner 会失败"
      mitigation: "get_project 强制 owner_id + school_id WHERE 过滤"
    - id: CE-004
      description: "被动注入泄漏：科任教师的 system prompt 被注入非自己班级的学生画像"
      tests_that_still_pass: "test_teacher_scope_skips_student_injection 会失败"
      mitigation: "MemoryInjector 对有 class_ids 但无 student_ids 的教师跳过 student 记忆注入"

  risk_modules:
    - module: "src/edu_cloud/ai/memory_store.py"
      risk: "数据隔离核心模块，所有 CRUD 必须受 school_id/owner_id 约束"
      mitigated_by: "INV-001, INV-002"
    - module: "src/edu_cloud/ai/tools/memory_tools.py"
      risk: "Agent 工具直接暴露记忆读写，必须经 capability + DataScope 双重过滤"
      mitigated_by: "INV-003, CE-002"
    - module: "src/edu_cloud/ai/memory_injector.py"
      risk: "被动注入路径可能泄漏超出 DataScope 的学生记忆"
      mitigated_by: "INV-001, CE-002, CE-004"
    - module: "src/edu_cloud/ai/memory_extractor.py"
      risk: "LLM 调用可能失败，必须不影响主流程"
      mitigated_by: "INV-004"

  test_debt:
    - id: TD-001
      description: "memory_read/write 工具的 API 级集成测试（通过 POST /api/v1/ai/chat 端到端验证）"
      reason: "需要完整 SSE + Agent loop mock，超出本 Phase 范围"
      deadline: "Phase 3 API 集成测试批次"
```

---

## 审查清单（全局）

- ✓ 数据隔离：所有查询强制 school_id 过滤
- ✓ EntityMemory 合并不覆盖：upsert 用 dict merge（新值覆盖旧值，旧值保留）
- ✓ LRU 淘汰：episodic memory 超 50 条删最旧
- ✓ Token 预算：注入记忆不超过 context_window 15%
- ✓ Graceful degradation：LLM 提取失败不影响正常对话
- ✓ Tier 分级：Tier 1 完整提取+注入，Tier 2 只注入不提取，Tier 3 全跳过
- ✓ 向后兼容：不传 memory_extractor 时 Supervisor 行为不变
- ✓ 工具权限：memory_read/write 限定 teacher 及以上角色
- ✗ ProjectState 的 checkpoint 恢复逻辑留待 Phase 3（课件/论文 Team 使用时实现）
- ✗ 现有 agent_memories 表保留不删除（session_memory.py 仍可用）
