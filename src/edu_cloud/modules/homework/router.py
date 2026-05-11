"""作业模块 API 路由。"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.core.tenant import get_school_id
from edu_cloud.modules.homework.service import HomeworkTaskService, HomeworkSubmissionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/homework", tags=["homework"])


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    task_type: str = "regular"
    subject_code: str
    class_id: str | None = None
    exam_id: str | None = None
    deadline: datetime | None = None
    content: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    deadline: datetime | None = None
    class_id: str | None = None


class RemedialFromExamRequest(BaseModel):
    exam_id: str
    class_id: str


class SubmitRequest(BaseModel):
    content: str | None = None


class GradeSingleRequest(BaseModel):
    score: float
    feedback: str | None = None


class GradeBatchRequest(BaseModel):
    grades: list[dict]


def _school_id(current: dict) -> str:
    """D4: Deprecated — use get_school_id() for fail-closed tenant isolation."""
    return get_school_id(current)


def _task_response(t) -> dict:
    return {
        "id": t.id, "school_id": t.school_id, "title": t.title,
        "task_type": t.task_type, "subject_code": t.subject_code,
        "class_id": t.class_id, "assigned_by": t.assigned_by,
        "exam_id": t.exam_id, "deadline": str(t.deadline) if t.deadline else None,
        "status": t.status, "content": t.content,
        "grading_mode": t.grading_mode,
        "created_at": str(t.created_at) if t.created_at else None,
    }


def _submission_response(s) -> dict:
    return {
        "id": s.id, "task_id": s.task_id, "student_id": s.student_id,
        "status": s.status, "score": s.score, "feedback": s.feedback,
        "submit_time": str(s.submit_time) if s.submit_time else None,
        "graded_by": s.graded_by,
        "graded_at": str(s.graded_at) if s.graded_at else None,
    }


# ── Task CRUD ─────────────────────────────────────────────

@router.post("/tasks", status_code=201)
async def create_task(
    req: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_HOMEWORK)),
):
    school_id = _school_id(current)
    task = await HomeworkTaskService.create_task(
        db, school_id=school_id, title=req.title,
        task_type=req.task_type, subject_code=req.subject_code,
        class_id=req.class_id, assigned_by=current["user"].id,
        exam_id=req.exam_id, deadline=req.deadline, content=req.content,
    )
    await db.commit()
    return _task_response(task)


@router.get("/tasks")
async def list_tasks(
    class_id: str | None = Query(None),
    subject_code: str | None = Query(None),
    status: str | None = Query(None),
    task_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_HOMEWORK)),
):
    role = current["current_role"]
    # F-03: ScopeFilter — subject_teacher 只看自己布置的
    assigned_by = None
    if role.role == "subject_teacher":
        assigned_by = current["user"].id
    # homeroom_teacher 强制限定本班
    scope_class_id = class_id
    if role.role == "homeroom_teacher" and role.class_ids:
        if class_id and class_id not in role.class_ids:
            from edu_cloud.services.exceptions import PermissionDeniedError
            raise PermissionDeniedError("无权查看该班级的作业")
        elif not class_id:
            scope_class_id = role.class_ids[0] if len(role.class_ids) == 1 else None
    tasks = await HomeworkTaskService.list_tasks(
        db, school_id=_school_id(current),
        class_id=scope_class_id, subject_code=subject_code,
        status=status, task_type=task_type, assigned_by=assigned_by,
    )
    return [_task_response(t) for t in tasks]


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_HOMEWORK)),
):
    task = await HomeworkTaskService.get_task(
        db, task_id=task_id, school_id=_school_id(current),
    )
    result = _task_response(task)
    result["stats"] = await HomeworkSubmissionService.get_task_stats(db, task_id=task_id)
    return result


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: str, req: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_HOMEWORK)),
):
    task = await HomeworkTaskService.update_task(
        db, task_id=task_id, school_id=_school_id(current),
        title=req.title, content=req.content,
        deadline=req.deadline, class_id=req.class_id,
    )
    await db.commit()
    return _task_response(task)


@router.post("/tasks/{task_id}/publish")
async def publish_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_HOMEWORK)),
):
    task = await HomeworkTaskService.transition_status(
        db, task_id=task_id, school_id=_school_id(current), action="publish",
    )
    await db.commit()
    return _task_response(task)


@router.post("/tasks/{task_id}/close")
async def close_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_HOMEWORK)),
):
    task = await HomeworkTaskService.transition_status(
        db, task_id=task_id, school_id=_school_id(current), action="close",
    )
    await db.commit()
    return _task_response(task)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_HOMEWORK)),
):
    await HomeworkTaskService.delete_task(
        db, task_id=task_id, school_id=_school_id(current),
    )
    await db.commit()


# ── 考后推送 + 内容增强 (WP-C) ──────────────────────────

@router.post("/tasks/from-exam", status_code=201)
async def create_remedial_from_exam(
    req: RemedialFromExamRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_HOMEWORK)),
):
    """从考试分析数据自动生成补救作业。"""
    task = await HomeworkTaskService.create_remedial_task(
        db,
        exam_id=req.exam_id,
        class_id=req.class_id,
        school_id=_school_id(current),
        created_by=current["user"].id,
    )
    await db.commit()
    return _task_response(task)


@router.get("/tasks/{task_id}/content-detail")
async def get_task_content_detail(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_HOMEWORK)),
):
    """获取作业内容详情（解析 content JSON 中的题目 ID，返回完整题目信息）。"""
    return await HomeworkTaskService.get_task_content_detail(
        db, task_id=task_id, school_id=_school_id(current),
    )


# ── Submissions ──────────────────────────────────────────

@router.get("/tasks/{task_id}/submissions")
async def list_submissions(
    task_id: str,
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_HOMEWORK)),
):
    school_id = _school_id(current)
    # 先验证 task 存在且属于本校
    await HomeworkTaskService.get_task(db, task_id=task_id, school_id=school_id)
    subs = await HomeworkSubmissionService.list_submissions(
        db, task_id=task_id, school_id=school_id, status=status,
    )
    return [_submission_response(s) for s in subs]


@router.post("/tasks/{task_id}/submissions/{sub_id}/submit")
async def submit_homework(
    task_id: str, sub_id: str, req: SubmitRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_HOMEWORK)),
):
    school_id = _school_id(current)
    await HomeworkTaskService.get_task(db, task_id=task_id, school_id=school_id)
    sub = await HomeworkSubmissionService.submit(
        db, task_id=task_id, submission_id=sub_id,
        school_id=school_id, content=req.content,
    )
    await db.commit()
    return _submission_response(sub)


@router.post("/tasks/{task_id}/submissions/{sub_id}/grade")
async def grade_single(
    task_id: str, sub_id: str, req: GradeSingleRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_HOMEWORK)),
):
    school_id = _school_id(current)
    await HomeworkTaskService.get_task(db, task_id=task_id, school_id=school_id)
    sub = await HomeworkSubmissionService.grade_single(
        db, task_id=task_id, submission_id=sub_id,
        school_id=school_id, score=req.score,
        feedback=req.feedback, graded_by=current["user"].id,
    )
    await db.commit()
    return _submission_response(sub)


@router.post("/tasks/{task_id}/grade-batch")
async def grade_batch(
    task_id: str, req: GradeBatchRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_HOMEWORK)),
):
    school_id = _school_id(current)
    await HomeworkTaskService.get_task(db, task_id=task_id, school_id=school_id)
    count = await HomeworkSubmissionService.grade_batch(
        db, task_id=task_id, school_id=school_id,
        grades=req.grades, graded_by=current["user"].id,
    )
    await db.commit()
    return {"graded_count": count}


@router.get("/tasks/{task_id}/stats")
async def get_stats(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_HOMEWORK)),
):
    await HomeworkTaskService.get_task(db, task_id=task_id, school_id=_school_id(current))
    return await HomeworkSubmissionService.get_task_stats(db, task_id=task_id)
