"""exam-ai 兼容路由 — paper-seg 零改动对接。

Deprecation: 本模块计划于 SUNSET_DATE 退役（见 docs/plans/compat-router-deprecation.md）。
每次调用发出三层信号：DeprecationWarning / Response header (Deprecation/Sunset/Link) / 结构化日志。
"""
import logging
import warnings

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from edu_cloud.database import get_db
from edu_cloud.shared.auth import create_access_token
from edu_cloud.core.rate_limit import limiter

logger = logging.getLogger(__name__)

_DUMMY_HASH = bcrypt.hashpw(b"timing-defense", bcrypt.gensalt()).decode()

SUNSET_DATE = "2026-07-31"


def _emit_deprecation(endpoint: str, replacement: str, response: Response) -> None:
    """发出 compat 端点三层 deprecation 信号。契约见 docs/plans/compat-router-deprecation.md §4.1。"""
    warnings.warn(
        f"{endpoint} is deprecated; use {replacement}",
        DeprecationWarning,
        stacklevel=2,
    )
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = SUNSET_DATE
    response.headers["Link"] = f'<{replacement}>; rel="successor-version"'
    logger.warning(
        "deprecated_compat_call",
        extra={"endpoint": endpoint, "replacement": replacement, "sunset": SUNSET_DATE},
    )


router = APIRouter(prefix="/api", tags=["compat"])


class CompatLoginRequest(BaseModel):
    school_code: str = ""  # paper-seg 会传，兼容层忽略
    username: str
    password: str


@router.post("/auth/login")
@limiter.limit("5/minute")
async def compat_login(
    request: Request,
    req: CompatLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """兼容 exam-ai 登录协议。忽略 school_code，走 edu-cloud 标准登录。"""
    _emit_deprecation("/api/auth/login", "/api/v1/auth/login", response)
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user:
        bcrypt.checkpw(req.password.encode(), _DUMMY_HASH.encode())

    if not user or not user.verify_password(req.password):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(401, "User is inactive")

    roles_result = await db.execute(select(UserRole).where(UserRole.user_id == user.id))
    roles = roles_result.scalars().all()
    if not roles:
        raise HTTPException(403, "No role assigned")

    primary = next((r for r in roles if r.is_primary), roles[0])
    token = create_access_token({
        "sub": user.id,
        "role": primary.role,
        "active_role_id": primary.id,
    })
    logger.info("compat_login: user=%s, role=%s", req.username, primary.role)
    return {"access_token": token}


# ── 考试/科目列表 ──────────────────────────────────────────────

from edu_cloud.core.auth import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.models.exam import Exam, Subject


@router.get("/exams")
async def compat_list_exams(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """列出当前学校的考试（paper-seg 拉取考试列表）。"""
    _emit_deprecation("/api/exams", "/api/v1/exams", response)
    school_id = current["current_role"].school_id
    q = select(Exam).order_by(Exam.created_at.desc())
    if school_id:
        q = q.where(Exam.school_id == school_id)
    result = await db.execute(q)
    exams = result.scalars().all()
    return [{"id": e.id, "name": e.name, "status": e.status} for e in exams]


@router.get("/exams/{exam_id}/subjects")
async def compat_list_subjects(
    exam_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """列出考试的科目（paper-seg 拉取科目列表）。"""
    _emit_deprecation(
        "/api/exams/{exam_id}/subjects",
        "/api/v1/exams/{exam_id}/subjects",
        response,
    )
    school_id = current["current_role"].school_id
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")

    result = await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )
    subjects = result.scalars().all()
    return [{"id": s.id, "name": s.name, "code": s.code} for s in subjects]


# ── 模板拉取 ──────────────────────────────────────────────────

from edu_cloud.modules.card.models import Template


@router.get("/templates/{subject_id}/{side}")
async def compat_get_template(
    subject_id: str,
    side: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """返回 paper-seg 兼容格式的答题卡模板。"""
    _emit_deprecation(
        "/api/templates/{subject_id}/{side}",
        "/api/v1/templates/{subject_id}/{side}",
        response,
    )
    school_id = current["current_role"].school_id
    result = await db.execute(
        select(Template).where(
            Template.subject_id == subject_id,
            Template.side == side,
            Template.school_id == school_id,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "Template not found")

    return {
        "id": template.id,
        "subject_id": template.subject_id,
        "side": template.side,
        "image_size": {
            "width": template.image_width,
            "height": template.image_height,
        },
        "anchors": template.anchors or [],
        "regions": template.regions or [],
        "sample_image": template.sample_image,
    }


# ── 扫描上传 ──────────────────────────────────────────────────

from fastapi import UploadFile, File, Form
from edu_cloud.modules.scan.models import ScanTask, StudentAnswer
from edu_cloud.shared.storage import get_storage, StorageService
from edu_cloud.modules.exam.models import Question
from sqlalchemy.exc import IntegrityError


@router.post("/scan/tasks")
async def compat_create_scan_task(
    req: dict,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """创建扫描任务。"""
    _emit_deprecation("/api/scan/tasks", "/api/v1/scan/tasks", response)
    school_id = current["current_role"].school_id
    subject_id = req.get("subject_id")
    side = req.get("side", "A")
    total_images = req.get("total_images", 0)

    subject = (await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")

    task = ScanTask(
        subject_id=subject_id, side=side,
        total_images=total_images, school_id=school_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "status": task.status, "total_images": task.total_images}


@router.patch("/scan/tasks/{task_id}")
async def compat_update_scan_task(
    task_id: str,
    req: dict,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """更新扫描进度。"""
    _emit_deprecation(
        "/api/scan/tasks/{task_id}",
        "/api/v1/scan/tasks/{task_id}",
        response,
    )
    school_id = current["current_role"].school_id
    task = (await db.execute(
        select(ScanTask).where(ScanTask.id == task_id, ScanTask.school_id == school_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    if "processed" in req:
        task.processed = req["processed"]
    if "failed" in req:
        task.failed = req["failed"]
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "status": task.status, "processed": task.processed, "failed": task.failed}


@router.post("/scan/upload", status_code=201)
async def compat_upload_image(
    response: Response,
    exam_id: str = Form(...),
    subject_id: str = Form(...),
    student_id: str = Form(...),
    question_id: str = Form(...),
    image: UploadFile = File(...),
    question_type: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
    storage: StorageService = Depends(get_storage),
):
    """接收 paper-seg 上传的切图。字段名与 exam-ai 完全一致。

    Phase 1-C: paper-seg 可携带 question_type（choice/multi_choice/fill_blank/essay），
    供 AI 阅卷选 prompt；为空时回落到 Question.question_type。
    """
    _emit_deprecation("/api/scan/upload", "/api/v1/scan/upload", response)
    school_id = current["current_role"].school_id

    # F003 fix: ownership validation (align with exam-ai)
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")
    subject = (await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.exam_id == exam_id, Subject.school_id == school_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")
    question = (await db.execute(
        select(Question).where(
            Question.id == question_id, Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    from edu_cloud.config import settings as _settings
    max_bytes = _settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    data = await image.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"文件过大，上限 {_settings.MAX_UPLOAD_SIZE_MB}MB")
    from edu_cloud.shared.upload_validation import detect_image_type
    if detect_image_type(data[:32]) is None:
        raise HTTPException(400, "不支持的图片格式")
    path = await storage.save(
        school_id=school_id, exam_id=exam_id, subject_id=subject_id,
        question_id=question_id, student_id=student_id, data=data,
    )
    answer = StudentAnswer(
        exam_id=exam_id, subject_id=subject_id, student_id=student_id,
        question_id=question_id, image_path=path, school_id=school_id,
        question_type=question_type,
    )
    db.add(answer)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Answer already exists")
    await db.refresh(answer)
    return {"id": answer.id, "image_path": answer.image_path}


class CompatObjectiveAnswer(BaseModel):
    question_id: str
    detected_answer: str
    fill_ratios: dict = {}
    anomaly: bool = False


class CompatUploadObjectiveRequest(BaseModel):
    exam_id: str
    subject_id: str
    student_id: str
    is_absent: bool = False
    answers: list[CompatObjectiveAnswer] = []


@router.post("/scan/upload-objective")
async def compat_upload_objective(
    req: CompatUploadObjectiveRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """接收 paper-seg 上传的选择题识别结果。"""
    _emit_deprecation(
        "/api/scan/upload-objective",
        "/api/v1/scan/upload-objective",
        response,
    )
    school_id = current["current_role"].school_id

    # 验证 exam + subject
    exam = (await db.execute(
        select(Exam).where(Exam.id == req.exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")

    subject = (await db.execute(
        select(Subject).where(
            Subject.id == req.subject_id, Subject.exam_id == req.exam_id,
            Subject.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")

    # F002 fix: handle is_absent path (align with exam-ai)
    if req.is_absent:
        # 缺考：为该科目所有题落 0 分，标记 is_absent
        all_questions = (await db.execute(
            select(Question).where(Question.subject_id == req.subject_id, Question.school_id == school_id)
        )).scalars().all()
        for q in all_questions:
            db.add(StudentAnswer(
                exam_id=req.exam_id, subject_id=req.subject_id,
                student_id=req.student_id, question_id=q.id,
                detected_answer="", score=0, is_absent=True,
                school_id=school_id,
            ))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "Answers already exist")
        return {"is_absent": True, "results": [], "total_score": 0}

    # 正常路径
    total_score = 0
    results = []
    for ans in req.answers:
        q = (await db.execute(
            select(Question).where(Question.id == ans.question_id, Question.school_id == school_id)
        )).scalar_one_or_none()
        from edu_cloud.modules.scan.objective_grading import grade_objective_answer
        if q and q.correct_answer:
            score, is_correct = grade_objective_answer(ans.detected_answer, q.correct_answer, q.max_score)
        else:
            score, is_correct = 0, False
        total_score += score

        db.add(StudentAnswer(
            exam_id=req.exam_id, subject_id=req.subject_id,
            student_id=req.student_id, question_id=ans.question_id,
            detected_answer=ans.detected_answer, score=score,
            is_anomaly=ans.anomaly, fill_ratios=ans.fill_ratios or None,
            school_id=school_id,
        ))
        results.append({
            "question_id": ans.question_id,
            "detected_answer": ans.detected_answer,
            "is_correct": is_correct,
            "score": score,
        })

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Answers already exist")
    return {"is_absent": False, "results": results, "total_score": total_score}
