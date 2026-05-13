"""Homework tools — Pydantic AI native (migrated from ai/tools/homework.py)."""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_HW_READ_ROLES = frozenset({
    "platform_admin", "district_admin", "principal",
    "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher", "parent",
})
_HW_WRITE_ROLES = frozenset({
    "platform_admin", "academic_director",
    "homeroom_teacher", "subject_teacher",
})
_HW_READ_CAP = frozenset({("homework", "read")})
_HW_WRITE_CAP = frozenset({("homework", "write")})


@edu_tool(
    name="list_homework_tasks", module_code="homework", domain="homework",
    allowed_roles=_HW_READ_ROLES, sensitivity="school", requires_capabilities=_HW_READ_CAP,
)
async def list_homework_tasks(
    ctx: RunContext[AgentDeps], class_id: str | None = None, subject_code: str | None = None, status: str | None = None,
) -> str:
    """List homework tasks. Filter by class, subject, status."""
    from edu_cloud.modules.homework.service import HomeworkTaskService
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        tasks = await HomeworkTaskService.list_tasks(
            db, school_id=scope.school_id, class_id=class_id, subject_code=subject_code, status=status,
        )
    return json.dumps({"tasks": [
        {"id": t.id, "title": t.title, "type": t.task_type, "status": t.status, "subject": t.subject_code}
        for t in tasks[:20]
    ]}, ensure_ascii=False, default=str)


@edu_tool(
    name="get_homework_stats", module_code="homework", domain="homework",
    allowed_roles=_HW_READ_ROLES, sensitivity="school", requires_capabilities=_HW_READ_CAP,
)
async def get_homework_stats(ctx: RunContext[AgentDeps], task_id: str) -> str:
    """Get submission stats for a homework task: total/submitted/graded/rate/avg."""
    from edu_cloud.modules.homework.service import HomeworkTaskService, HomeworkSubmissionService
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        task = await HomeworkTaskService.get_task(db, task_id=task_id, school_id=scope.school_id)
        if not task:
            return json.dumps({"error": "作业不存在"})
        stats = await HomeworkSubmissionService.get_task_stats(db, task_id=task_id)
    return json.dumps({"task_id": task_id, "title": task.title, **stats}, ensure_ascii=False, default=str)


@edu_tool(
    name="get_submission_details", module_code="homework", domain="homework",
    allowed_roles=_HW_READ_ROLES, sensitivity="school", requires_capabilities=_HW_READ_CAP,
)
async def get_submission_details(ctx: RunContext[AgentDeps], task_id: str, status: str | None = None) -> str:
    """Get submission list for a homework task."""
    from edu_cloud.modules.homework.service import HomeworkTaskService, HomeworkSubmissionService
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        task = await HomeworkTaskService.get_task(db, task_id=task_id, school_id=scope.school_id)
        if not task:
            return json.dumps({"error": "作业不存在"})
        submissions = await HomeworkSubmissionService.list_submissions(db, task_id=task_id, school_id=scope.school_id, status=status)
    return json.dumps({"task_id": task_id, "submissions": [
        {"id": s.id, "student_id": s.student_id, "status": s.status, "score": s.score}
        for s in submissions
    ]}, ensure_ascii=False, default=str)


@edu_tool(
    name="assign_homework", module_code="homework", domain="homework",
    allowed_roles=_HW_WRITE_ROLES, risk_level="medium", is_read_only=False,
    sensitivity="school", requires_capabilities=_HW_WRITE_CAP,
)
async def assign_homework(
    ctx: RunContext[AgentDeps], title: str, class_id: str, subject_code: str,
    content: str = "", task_type: str = "regular",
) -> str:
    """Create and publish a homework task."""
    from edu_cloud.modules.homework.service import HomeworkTaskService
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        task = await HomeworkTaskService.create_task(
            db, school_id=scope.school_id, title=title, class_id=class_id,
            subject_code=subject_code, content=content, task_type=task_type,
            assigned_by=ctx.deps.user_id,
        )
        await HomeworkTaskService.transition_status(db, task_id=task.id, action="publish")
    return json.dumps({"status": "ok", "task_id": task.id, "title": title}, ensure_ascii=False)


@edu_tool(
    name="recommend_remedial", module_code="homework", domain="homework",
    allowed_roles=_HW_WRITE_ROLES, sensitivity="school", requires_capabilities=_HW_READ_CAP,
)
async def recommend_remedial(ctx: RunContext[AgentDeps], class_id: str, subject_code: str) -> str:
    """Recommend remedial exercises based on class weakness analysis."""
    return json.dumps({"message": "补救练习推荐功能开发中", "class_id": class_id, "subject_code": subject_code})


@edu_tool(
    name="assign_remedial_homework", module_code="homework", domain="homework",
    allowed_roles=_HW_WRITE_ROLES, risk_level="medium", is_read_only=False,
    sensitivity="school", requires_capabilities=_HW_WRITE_CAP,
)
async def assign_remedial_homework(
    ctx: RunContext[AgentDeps],
    exam_id: str,
    subject_id: str,
    score_threshold: float,
    homework_title: str,
    homework_content: str = "",
) -> str:
    """为低于阈值的学生批量布置补救作业。查询成绩→预览学生→创建作业+提交记录。"""
    from sqlalchemy import select
    from edu_cloud.modules.exam.models import ExamResult, Subject
    from edu_cloud.modules.student.models import Student
    from edu_cloud.modules.homework.service import HomeworkTaskService

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        subj = (await db.execute(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.exam_id == exam_id,
                Subject.school_id == scope.school_id,
            )
        )).scalar_one_or_none()
        if not subj:
            return json.dumps({"error": "科目不存在或不属于该考试"})

        stmt = (
            select(ExamResult, Student)
            .join(Student, ExamResult.student_id == Student.id)
            .where(ExamResult.exam_id == exam_id)
            .where(ExamResult.school_id == scope.school_id)
            .where(ExamResult.total_score < score_threshold)
        )
        if scope.visible_class_ids is not None:
            stmt = stmt.where(Student.class_id.in_(scope.visible_class_ids))

        rows = (await db.execute(stmt)).all()
        if not rows:
            return json.dumps({"message": f"没有低于 {score_threshold} 分的学生", "count": 0})

        student_names = [r.Student.name for r in rows[:20]]
        preview = {
            "count": len(rows),
            "students_preview": student_names,
            "threshold": score_threshold,
            "title": homework_title,
        }

        by_class: dict[str, list] = {}
        for sa, student in rows:
            cid = student.class_id
            if cid:
                by_class.setdefault(cid, []).append(student)

        if not by_class:
            return json.dumps({"error": "学生未分配班级，无法创建作业"})

        from edu_cloud.modules.homework.models import HomeworkSubmission
        task_ids = []
        for class_id, students_in_class in by_class.items():
            task = await HomeworkTaskService.create_task(
                db, school_id=scope.school_id, title=homework_title,
                task_type="post_exam", subject_code=subj.code,
                class_id=class_id, assigned_by=ctx.deps.user_id,
                exam_id=exam_id, content=homework_content,
            )
            for student in students_in_class:
                db.add(HomeworkSubmission(
                    task_id=task.id, student_id=student.id, status="pending",
                ))
            task_ids.append(task.id)
        await db.flush()
        await db.commit()

    return json.dumps({
        "status": "ok",
        "task_ids": task_ids,
        "title": homework_title,
        **preview,
        "classes": len(by_class),
        "message": f"已为 {len(rows)} 名低于 {score_threshold} 分的学生创建补救作业「{homework_title}」（{len(by_class)} 个班级）",
    }, ensure_ascii=False, default=str)


ALL_TOOLS = [
    list_homework_tasks, get_homework_stats, get_submission_details,
    assign_homework, recommend_remedial, assign_remedial_homework,
]
