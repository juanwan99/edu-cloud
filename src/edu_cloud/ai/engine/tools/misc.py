"""Miscellaneous single-tool modules — Pydantic AI native.

Migrated from: adaptive.py, class_report_tool.py, exam_overview.py,
knowledge_tree.py, student_diagnosis.py, student_profile_tool.py,
findings_tools.py, knowledge_db.py, memory_tools.py, actions.py
"""
from __future__ import annotations

import json

from pydantic_ai import RunContext
from sqlalchemy import select

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_ALL_ROLES = frozenset({
    "platform_admin", "district_admin", "school_admin", "principal",
    "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher",
})
_TEACHER_ROLES = frozenset({
    "platform_admin", "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher",
})
_TEACHER_PLUS_PARENT = frozenset(_ALL_ROLES | {"parent"})
_RESEARCH_ROLES = frozenset({
    "platform_admin", "academic_director",
    "teaching_research_leader", "lesson_prep_leader", "subject_teacher",
})


# ── Adaptive ──

@edu_tool(name="diagnose_and_recommend", module_code="exam", domain="adaptive", allowed_roles=_ALL_ROLES, sensitivity="student")
async def diagnose_and_recommend(ctx: RunContext[AgentDeps], student_id: str) -> str:
    """Run adaptive learning diagnosis and get learning recommendations."""
    from edu_cloud.modules.adaptive.service import diagnose_and_recommend as svc
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        data = await svc(db, student_id=student_id, school_id=scope.school_id)
    return json.dumps(data, ensure_ascii=False, default=str)


# ── Class Report ──

@edu_tool(name="get_class_report", module_code="exam", domain="analytics", allowed_roles=_ALL_ROLES, sensitivity="school")
async def get_class_report(ctx: RunContext[AgentDeps], exam_id: str, class_id: str) -> str:
    """Get pre-computed class exam report."""
    from edu_cloud.models.agent_snapshot import ClassExamReport
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        report = (await db.execute(
            select(ClassExamReport).where(
                ClassExamReport.exam_id == exam_id,
                ClassExamReport.class_id == class_id,
                ClassExamReport.school_id == scope.school_id,
            )
        )).scalar_one_or_none()
    if not report:
        return json.dumps({"error": "未找到该班级的考试报告"})
    return json.dumps({
        "exam_id": exam_id, "class_id": class_id,
        "grade_rank": report.grade_rank, "class_avg": report.class_avg,
        "grade_avg": report.grade_avg, "metrics": report.metrics,
    }, ensure_ascii=False, default=str)


# ── Exam Overview ──

@edu_tool(name="get_exam_overview", module_code="exam", domain="analytics", allowed_roles=_ALL_ROLES, sensitivity="school")
async def get_exam_overview(ctx: RunContext[AgentDeps], exam_id: str) -> str:
    """Get pre-computed exam analysis snapshot."""
    from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        snapshots = (await db.execute(
            select(ExamAnalysisSnapshot).where(
                ExamAnalysisSnapshot.exam_id == exam_id,
                ExamAnalysisSnapshot.school_id == scope.school_id,
                ExamAnalysisSnapshot.status == "active",
            )
        )).scalars().all()
    data = [{"type": s.snapshot_type, "target_type": s.target_type, "metrics": s.metrics} for s in snapshots]
    return json.dumps({"exam_id": exam_id, "snapshots": data}, ensure_ascii=False, default=str)


# ── Student Diagnosis ──

@edu_tool(name="get_student_diagnosis", module_code="exam", domain="analytics", allowed_roles=_TEACHER_PLUS_PARENT, sensitivity="student")
async def get_student_diagnosis(ctx: RunContext[AgentDeps], student_id: str, exam_id: str | None = None) -> str:
    """Get AI diagnosis snapshots for a student."""
    from edu_cloud.modules.profile.models import StudentExamSnapshot
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        q = select(StudentExamSnapshot).where(
            StudentExamSnapshot.student_id == student_id,
            StudentExamSnapshot.school_id == scope.school_id,
        )
        if exam_id:
            q = q.where(StudentExamSnapshot.exam_id == exam_id)
        snapshots = (await db.execute(q)).scalars().all()
    data = [{"exam_id": s.exam_id, "subject_code": s.subject_code, "metrics": s.metrics} for s in snapshots]
    return json.dumps({"student_id": student_id, "snapshots": data}, ensure_ascii=False, default=str)


# ── Student Learning Profile ──

@edu_tool(name="get_student_learning_profile", module_code="exam", domain="profile", allowed_roles=_ALL_ROLES, sensitivity="student")
async def get_student_learning_profile(ctx: RunContext[AgentDeps], student_id: str, subject_code: str | None = None) -> str:
    """Get composite student learning profile (snapshots + mastery)."""
    from edu_cloud.modules.profile.models import StudentExamSnapshot, StudentKnowledgeMastery
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        snap_q = select(StudentExamSnapshot).where(
            StudentExamSnapshot.student_id == student_id, StudentExamSnapshot.school_id == scope.school_id,
        )
        if subject_code:
            snap_q = snap_q.where(StudentExamSnapshot.subject_code == subject_code)
        snapshots = (await db.execute(snap_q)).scalars().all()

        mastery_q = select(StudentKnowledgeMastery).where(
            StudentKnowledgeMastery.student_id == student_id, StudentKnowledgeMastery.school_id == scope.school_id,
        )
        masteries = (await db.execute(mastery_q)).scalars().all()

    return json.dumps({
        "student_id": student_id,
        "exam_snapshots": [{"exam_id": s.exam_id, "subject_code": s.subject_code, "metrics": s.metrics} for s in snapshots],
        "knowledge_mastery": [{"knowledge_point": m.knowledge_point_id, "mastery": m.mastery_level} for m in masteries],
    }, ensure_ascii=False, default=str)


# ── Knowledge DB ──

@edu_tool(name="get_knowledge_tree", module_code="research", domain="knowledge", allowed_roles=_ALL_ROLES, sensitivity="public")
async def get_knowledge_tree(ctx: RunContext[AgentDeps], course_code: str | None = None) -> str:
    """Get knowledge graph tree structure."""
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge
    async with ctx.deps.get_db() as db:
        node_q = select(ConceptGraphNode)
        if course_code:
            node_q = node_q.where(ConceptGraphNode.primary_module == course_code)
        nodes = (await db.execute(node_q)).scalars().all()
        edges = (await db.execute(
            select(ConceptGraphEdge).where(ConceptGraphEdge.relation_type == "contains")
        )).scalars().all()
    return json.dumps({
        "nodes": [{"id": n.id, "name": n.name, "level": n.knowledge_level, "module": n.primary_module} for n in nodes],
        "edges": [{"source": e.source_id, "target": e.target_id, "type": e.relation_type} for e in edges],
    }, ensure_ascii=False, default=str)


@edu_tool(name="get_question_knowledge_points", module_code="research", domain="knowledge", allowed_roles=_ALL_ROLES, sensitivity="public")
async def get_question_knowledge_points(ctx: RunContext[AgentDeps], question_id: str) -> str:
    """Get knowledge points linked to a question."""
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
    async with ctx.deps.get_db() as db:
        points = (await db.execute(
            select(ConceptGraphNode).join(
                QuestionKnowledgePoint, QuestionKnowledgePoint.knowledge_point_id == ConceptGraphNode.id
            ).where(QuestionKnowledgePoint.question_id == question_id)
        )).scalars().all()
    return json.dumps({
        "question_id": question_id,
        "knowledge_points": [{"id": p.id, "name": p.name, "module": p.primary_module} for p in points],
    }, ensure_ascii=False, default=str)


# ── Knowledge Tree Edit ──

@edu_tool(
    name="edit_knowledge_graph", module_code="research", domain="knowledge",
    allowed_roles=_RESEARCH_ROLES, risk_level="medium", is_read_only=False, sensitivity="school",
)
async def edit_knowledge_graph(ctx: RunContext[AgentDeps], operations: list[dict]) -> str:
    """Edit knowledge graph (add/remove/update nodes and edges)."""
    from edu_cloud.modules.knowledge_tree.service import apply_edits
    async with ctx.deps.get_db() as db:
        result = await apply_edits(db, operations)
    return json.dumps(result, ensure_ascii=False, default=str)


# ── Agent Findings ──

@edu_tool(name="get_findings", module_code="exam", domain="analytics", allowed_roles=_ALL_ROLES, sensitivity="school")
async def get_findings(ctx: RunContext[AgentDeps], status: str | None = None, severity: str | None = None) -> str:
    """Get agent patrol findings for this school."""
    from edu_cloud.models.agent_finding import AgentFinding
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        q = select(AgentFinding).where(AgentFinding.school_id == scope.school_id)
        if status:
            q = q.where(AgentFinding.status == status)
        if severity:
            q = q.where(AgentFinding.severity == severity)
        findings = (await db.execute(q.order_by(AgentFinding.created_at.desc()).limit(20))).scalars().all()
    return json.dumps({
        "findings": [{"id": f.id, "type": f.finding_type, "severity": f.severity, "summary": f.summary, "status": f.status} for f in findings]
    }, ensure_ascii=False, default=str)


@edu_tool(name="get_agent_tasks", module_code="exam", domain="analytics", allowed_roles=_ALL_ROLES, sensitivity="school")
async def get_agent_tasks(ctx: RunContext[AgentDeps], status: str | None = None) -> str:
    """Get agent-generated tasks for this school."""
    from edu_cloud.models.agent_finding import AgentTask
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        q = select(AgentTask).where(AgentTask.school_id == scope.school_id)
        if status:
            q = q.where(AgentTask.status == status)
        tasks = (await db.execute(q.order_by(AgentTask.created_at.desc()).limit(20))).scalars().all()
    return json.dumps({
        "tasks": [{"id": t.id, "type": t.task_type, "status": t.status, "assignee_role": t.assignee_role} for t in tasks]
    }, ensure_ascii=False, default=str)


# ── Memory ──

@edu_tool(
    name="memory_read", module_code="exam", domain="system",
    allowed_roles=_TEACHER_ROLES, sensitivity="school",
    requires_capabilities=frozenset({("system", "read")}),
)
async def memory_read(ctx: RunContext[AgentDeps], entity_type: str, entity_ids: list[str] | None = None) -> str:
    """Read cross-session entity memory (student/teacher/class/session)."""
    scope = ctx.deps.data_scope
    visible_student_ids = scope.visible_student_ids
    async with ctx.deps.get_db() as db:
        from edu_cloud.ai.memory_store import MemoryStore
        store = MemoryStore()
        data = await store.get_entities(db, scope.school_id, entity_type, entity_ids, visible_student_ids)
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(
    name="memory_write", module_code="exam", domain="system",
    allowed_roles=_TEACHER_ROLES, risk_level="medium", is_read_only=False, sensitivity="school",
    requires_capabilities=frozenset({("system", "write")}),
)
async def memory_write(ctx: RunContext[AgentDeps], entity_type: str, entity_id: str, facts: dict) -> str:
    """Write cross-session entity memory."""
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        from edu_cloud.ai.memory_store import MemoryStore
        store = MemoryStore()
        await store.upsert_entity(db, scope.school_id, entity_type, entity_id, facts)
    return json.dumps({"status": "ok", "entity_type": entity_type, "entity_id": entity_id})


ALL_TOOLS = [
    diagnose_and_recommend, get_class_report, get_exam_overview,
    get_student_diagnosis, get_student_learning_profile,
    get_knowledge_tree, get_question_knowledge_points, edit_knowledge_graph,
    get_findings, get_agent_tasks, memory_read, memory_write,
]
