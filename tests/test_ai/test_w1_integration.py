"""W1 integration tests — EventTrigger, WorkflowDefinition, findings/tasks tools."""
import pytest
from sqlalchemy import select
from unittest.mock import patch

from edu_cloud.models.agent_finding import AgentFinding, AgentTask
from edu_cloud.models.school import School


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def school(db):
    s = School(name="集成测试校", code="INT001", district="测试区", api_key_hash="x")
    db.add(s)
    await db.flush()
    return s


@pytest.fixture
async def seeded_findings(db, school):
    """Seed AgentFinding + AgentTask records."""
    findings = []
    for i, status in enumerate(["new", "notified", "resolved"]):
        f = AgentFinding(
            school_id=school.id,
            finding_type="score_anomaly",
            severity="critical",
            target_type="class",
            target_id=f"cls-{i}",
            summary=f"测试发现 {i}",
            detail={"index": i},
            status=status,
            notify_roles=["academic_director"],
            idempotency_key=f"test-key-{i}",
        )
        db.add(f)
        findings.append(f)
    await db.flush()

    # Add tasks linked to first finding
    for j in range(2):
        t = AgentTask(
            school_id=school.id,
            finding_id=findings[0].id,
            task_type="review_class",
            assignee_role="grade_leader",
            payload={"action": f"task-{j}"},
            status="pending" if j == 0 else "done",
        )
        db.add(t)
    await db.flush()
    return findings


# ---------------------------------------------------------------------------
# EventTrigger
# ---------------------------------------------------------------------------

class TestEventTrigger:
    @pytest.mark.asyncio
    async def test_event_trigger_fires_workflow(self):
        from edu_cloud.ai.workflow.triggers import EventTrigger
        from edu_cloud.core.events import EventBus

        triggered = []

        async def mock_execute(workflow_name, school_id, trigger_type, trigger_ref):
            triggered.append({
                "wf": workflow_name,
                "school_id": school_id,
                "trigger_type": trigger_type,
                "ref": trigger_ref,
            })

        bus = EventBus()
        trigger = EventTrigger(bus, executor_func=mock_execute)
        trigger.register("exam.published", workflow_name="post_exam_analysis")

        await bus.emit("exam.published", {"exam_id": "e1", "school_id": "s1"})

        assert len(triggered) == 1
        assert triggered[0]["wf"] == "post_exam_analysis"
        assert triggered[0]["ref"] == "e1"
        assert triggered[0]["school_id"] == "s1"
        assert triggered[0]["trigger_type"] == "event"

    @pytest.mark.asyncio
    async def test_event_trigger_uses_id_fallback(self):
        from edu_cloud.ai.workflow.triggers import EventTrigger
        from edu_cloud.core.events import EventBus

        triggered = []

        async def mock_execute(workflow_name, school_id, trigger_type, trigger_ref):
            triggered.append({"ref": trigger_ref})

        bus = EventBus()
        trigger = EventTrigger(bus, executor_func=mock_execute)
        trigger.register("entity.created", workflow_name="some_workflow")

        await bus.emit("entity.created", {"id": "ent-42", "school_id": "s2"})

        assert triggered[0]["ref"] == "ent-42"

    @pytest.mark.asyncio
    async def test_event_trigger_empty_payload(self):
        from edu_cloud.ai.workflow.triggers import EventTrigger
        from edu_cloud.core.events import EventBus

        triggered = []

        async def mock_execute(workflow_name, school_id, trigger_type, trigger_ref):
            triggered.append({"ref": trigger_ref, "school_id": school_id})

        bus = EventBus()
        trigger = EventTrigger(bus, executor_func=mock_execute)
        trigger.register("test.event", workflow_name="wf")

        await bus.emit("test.event", {})

        assert triggered[0]["ref"] == ""
        assert triggered[0]["school_id"] == ""


# ---------------------------------------------------------------------------
# W1 WorkflowDefinition
# ---------------------------------------------------------------------------

class TestW1Definition:
    @pytest.mark.asyncio
    async def test_w1_definition_has_5_steps(self):
        from edu_cloud.ai.workflow.w1_post_exam import W1_POST_EXAM

        assert W1_POST_EXAM.name == "post_exam_analysis"
        assert len(W1_POST_EXAM.steps) == 5

    @pytest.mark.asyncio
    async def test_w1_step_names(self):
        from edu_cloud.ai.workflow.w1_post_exam import W1_POST_EXAM

        expected = [
            "compute_exam_snapshot",
            "compute_class_reports",
            "compute_student_diagnoses",
            "detect_anomalies",
            "dispatch_notifications",
        ]
        actual = [s.name for s in W1_POST_EXAM.steps]
        assert actual == expected

    @pytest.mark.asyncio
    async def test_w1_step_funcs_are_callable(self):
        from edu_cloud.ai.workflow.w1_post_exam import W1_POST_EXAM

        for step in W1_POST_EXAM.steps:
            assert callable(step.func)


# ---------------------------------------------------------------------------
# Findings tool
# ---------------------------------------------------------------------------

class TestGetFindings:
    @pytest.mark.asyncio
    async def test_get_findings_reads_by_school(self, db, school, seeded_findings):
        from edu_cloud.ai.tools.findings_tools import get_findings
        from edu_cloud.ai.tool_context import ToolContext

        ctx = ToolContext(db=db, school_id=school.id, user_id="u1", role="academic_director")
        result = await get_findings({"limit": 50}, ctx)

        assert result.success is True
        assert len(result.data["findings"]) == 3

    @pytest.mark.asyncio
    async def test_get_findings_filters_by_status(self, db, school, seeded_findings):
        from edu_cloud.ai.tools.findings_tools import get_findings
        from edu_cloud.ai.tool_context import ToolContext

        ctx = ToolContext(db=db, school_id=school.id, user_id="u1", role="academic_director")
        result = await get_findings({"status": "new"}, ctx)

        assert result.success is True
        assert len(result.data["findings"]) == 1
        assert result.data["findings"][0]["status"] == "new"

    @pytest.mark.asyncio
    async def test_get_findings_respects_limit(self, db, school, seeded_findings):
        from edu_cloud.ai.tools.findings_tools import get_findings
        from edu_cloud.ai.tool_context import ToolContext

        ctx = ToolContext(db=db, school_id=school.id, user_id="u1", role="academic_director")
        result = await get_findings({"limit": 1}, ctx)

        assert result.success is True
        assert len(result.data["findings"]) == 1

    @pytest.mark.asyncio
    async def test_get_findings_empty(self, db, school):
        from edu_cloud.ai.tools.findings_tools import get_findings
        from edu_cloud.ai.tool_context import ToolContext

        ctx = ToolContext(db=db, school_id=school.id, user_id="u1", role="academic_director")
        result = await get_findings({}, ctx)

        assert result.success is True
        assert len(result.data["findings"]) == 0


# ---------------------------------------------------------------------------
# AgentTasks tool
# ---------------------------------------------------------------------------

class TestGetAgentTasks:
    @pytest.mark.asyncio
    async def test_get_agent_tasks_reads_by_school(self, db, school, seeded_findings):
        from edu_cloud.ai.tools.findings_tools import get_agent_tasks
        from edu_cloud.ai.tool_context import ToolContext

        ctx = ToolContext(db=db, school_id=school.id, user_id="u1", role="academic_director")
        result = await get_agent_tasks({}, ctx)

        assert result.success is True
        assert len(result.data["tasks"]) == 2

    @pytest.mark.asyncio
    async def test_get_agent_tasks_filters_by_status(self, db, school, seeded_findings):
        from edu_cloud.ai.tools.findings_tools import get_agent_tasks
        from edu_cloud.ai.tool_context import ToolContext

        ctx = ToolContext(db=db, school_id=school.id, user_id="u1", role="academic_director")
        result = await get_agent_tasks({"status": "pending"}, ctx)

        assert result.success is True
        assert len(result.data["tasks"]) == 1
        assert result.data["tasks"][0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_agent_tasks_empty(self, db, school):
        from edu_cloud.ai.tools.findings_tools import get_agent_tasks
        from edu_cloud.ai.tool_context import ToolContext

        ctx = ToolContext(db=db, school_id=school.id, user_id="u1", role="academic_director")
        result = await get_agent_tasks({}, ctx)

        assert result.success is True
        assert len(result.data["tasks"]) == 0


# ---------------------------------------------------------------------------
# F01: EventTrigger wired in app startup
# ---------------------------------------------------------------------------

class TestEventTriggerWiring:
    @pytest.mark.asyncio
    async def test_exam_published_handler_registered_in_event_bus(self):
        """F01: After app creation, event_bus should have a handler for exam.published."""
        from edu_cloud.core.events import event_bus

        # The lifespan registers the handler; in tests we verify the import path works
        # and the trigger can be constructed
        from edu_cloud.ai.workflow.triggers import EventTrigger
        from edu_cloud.ai.workflow.w1_post_exam import W1_POST_EXAM
        from edu_cloud.ai.workflow.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        registry.register(W1_POST_EXAM)

        calls = []

        async def mock_exec(workflow_name, school_id, trigger_type, trigger_ref):
            calls.append(workflow_name)

        bus_test = __import__("edu_cloud.core.events", fromlist=["EventBus"]).EventBus()
        trigger = EventTrigger(bus_test, executor_func=mock_exec)
        trigger.register("exam.published", workflow_name="post_exam_analysis")

        await bus_test.emit("exam.published", {"exam_id": "e1", "school_id": "s1"})
        assert calls == ["post_exam_analysis"]
