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


class TestUniqueConstraints:
    def test_entity_memory_unique_constraint(self):
        """EntityMemory should have unique constraint on (school_id, entity_type, entity_id)."""
        table = EntityMemory.__table__
        unique_constraints = [c for c in table.constraints if hasattr(c, 'columns') and len(c.columns) > 1]
        assert any(
            set(col.name for col in c.columns) == {"school_id", "entity_type", "entity_id"}
            for c in unique_constraints
        ), "Missing unique constraint on (school_id, entity_type, entity_id)"

    def test_project_state_unique_constraint(self):
        """ProjectState should have unique constraint on (project_type, project_id)."""
        table = ProjectState.__table__
        unique_constraints = [c for c in table.constraints if hasattr(c, 'columns') and len(c.columns) > 1]
        assert any(
            set(col.name for col in c.columns) == {"project_type", "project_id"}
            for c in unique_constraints
        ), "Missing unique constraint on (project_type, project_id)"
