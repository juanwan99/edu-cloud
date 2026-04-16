"""Tests for MemoryStore CRUD + conflict merge."""
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
                owner_id="u1", school_id="sch-1", state={},
            )
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
    async def test_update_status_wrong_owner(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.save_project(
                db, project_type="paper", project_id="p1",
                owner_id="u1", school_id="sch-1", state={},
            )
            # Try to update with wrong owner — should be no-op
            await store.update_project_status(db, "p1", "u2", "sch-1", "completed")
            result = await store.get_project(db, "p1", "u1", "sch-1")
            assert result.status == "active"  # unchanged

    @pytest.mark.asyncio
    async def test_update_state_wrong_school(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.save_project(
                db, project_type="paper", project_id="p1",
                owner_id="u1", school_id="sch-1",
                state={"checkpoint": "research"},
            )
            await store.update_project_state(db, "p1", "u1", "sch-2", {"checkpoint": "writing"})
            result = await store.get_project(db, "p1", "u1", "sch-1")
            assert result.state["checkpoint"] == "research"  # unchanged

    @pytest.mark.asyncio
    async def test_get_active_projects(self, db_engine, store):
        async with AsyncSession(db_engine) as db:
            await store.save_project(db, "paper", "p1", "u1", "sch-1", {})
            await store.save_project(db, "paper", "p2", "u1", "sch-1", {})
            await store.update_project_status(db, "p2", "u1", "sch-1", "completed")
            results = await store.get_active_projects(db, "u1", "sch-1")
            assert len(results) == 1
            assert results[0].project_id == "p1"


class TestDeepMerge:
    """P0-3: nested dict merge must preserve existing nested fields."""

    @pytest.mark.asyncio
    async def test_nested_dict_preserved(self, db_engine, store):
        """Updating nested dict should deep-merge, not overwrite."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-dm", facts={"scores": {"math": 90, "english": 85}},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-dm", facts={"scores": {"math": 95}},
            )
            # math updated, english preserved
            assert result.facts["scores"]["math"] == 95
            assert result.facts["scores"]["english"] == 85

    @pytest.mark.asyncio
    async def test_deep_merge_three_levels(self, db_engine, store):
        """Three-level nesting should be recursively merged."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-3l", facts={"profile": {"scores": {"math": 90}}},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-3l", facts={"profile": {"scores": {"english": 85}}},
            )
            assert result.facts["profile"]["scores"]["math"] == 90
            assert result.facts["profile"]["scores"]["english"] == 85

    @pytest.mark.asyncio
    async def test_scalar_overwrite(self, db_engine, store):
        """Non-dict values should still overwrite."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-so", facts={"name": "张三", "grade": 3},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-so", facts={"grade": 4},
            )
            assert result.facts["name"] == "张三"
            assert result.facts["grade"] == 4

    @pytest.mark.asyncio
    async def test_list_replaces_not_merges(self, db_engine, store):
        """Lists should be replaced entirely, not merged."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-lr", facts={"tags": ["a", "b"]},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-lr", facts={"tags": ["c"]},
            )
            assert result.facts["tags"] == ["c"]

    @pytest.mark.asyncio
    async def test_none_value_overwrites(self, db_engine, store):
        """None update value should overwrite existing."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-nv", facts={"note": "old"},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-nv", facts={"note": None},
            )
            assert result.facts["note"] is None

    @pytest.mark.asyncio
    async def test_five_level_nesting(self, db_engine, store):
        """CE-002: 5-level nesting should be recursively merged."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-5l", facts={"a": {"b": {"c": {"d": {"e": 1}}}}},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-5l", facts={"a": {"b": {"c": {"d": {"f": 2}}}}},
            )
            assert result.facts["a"]["b"]["c"]["d"]["e"] == 1
            assert result.facts["a"]["b"]["c"]["d"]["f"] == 2

    @pytest.mark.asyncio
    async def test_depth_beyond_5_falls_back_to_overwrite(self, db_engine, store):
        """CE-002: beyond depth 5, nested dicts are overwritten (not merged)."""
        async with AsyncSession(db_engine) as db:
            # 6 nested levels: a.b.c.d.e.f — "f" is at depth 5 where recursion stops
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-6l", facts={"a": {"b": {"c": {"d": {"e": {"f": {"x": 1, "y": 2}}}}}}},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-6l", facts={"a": {"b": {"c": {"d": {"e": {"f": {"x": 99}}}}}}},
            )
            # At depth 5, "f" dict is overwritten entirely (not merged), so "y" is lost
            assert result.facts["a"]["b"]["c"]["d"]["e"]["f"] == {"x": 99}

    def test_deep_merge_direct_depth_limit(self):
        """CE-002: _deep_merge with circular-like deep nesting doesn't stack overflow."""
        from edu_cloud.ai.memory_store import _deep_merge
        # Build 10-level nested dict
        base = current = {}
        for i in range(10):
            current[f"l{i}"] = {}
            current = current[f"l{i}"]
        current["val"] = "deep"

        update = {"l0": {"l1": {"l2": {"new": "inserted"}}}}
        result = _deep_merge(base, update)
        # Merge works up to depth 5, beyond that overwrites
        assert result["l0"]["l1"]["l2"]["new"] == "inserted"


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
