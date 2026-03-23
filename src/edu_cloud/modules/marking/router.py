import io
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import get_current_user
from edu_cloud.database import get_db
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.exam.models import Exam, Question, Subject
from edu_cloud.modules.marking.models import MarkingAssignment
from edu_cloud.api.permissions import get_visible_subject_codes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/marking", tags=["marking"])


# ---------- Request / Response schemas ----------

class ImportRequest(BaseModel):
    exam_id: str
    folder_path: str


class ImportResponse(BaseModel):
    subjects_created: int
    questions_created: int
    answers_created: int
    answers_skipped: int


class ScoreRequest(BaseModel):
    answer_id: str
    score: float
    comment: str | None = None


class AssignRequest(BaseModel):
    exam_id: str
    question_id: str
    teacher_id: str


# ---------- Assignment ----------

@router.post("/assign", status_code=201)
async def assign_question(
    req: AssignRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员将题目分配给指定教师阅卷。"""
    if current["current_role"].role not in ("admin", "principal"):
        raise HTTPException(403, "仅管理员可分配阅卷任务")

    # Verify exam, question, teacher belong to school
    exam = (await db.execute(
        select(Exam).where(Exam.id == req.exam_id, Exam.school_id == current["current_role"].school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "考试不存在")

    question = (await db.execute(
        select(Question).where(Question.id == req.question_id, Question.school_id == current["current_role"].school_id)
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "题目不存在")

    # Verify question belongs to a subject of this exam
    subject = (await db.execute(
        select(Subject).where(Subject.id == question.subject_id, Subject.exam_id == req.exam_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(400, "题目不属于该考试")

    # Verify teacher exists and belongs to this school (via UserRole)
    teacher_role = (await db.execute(
        select(UserRole).where(UserRole.user_id == req.teacher_id, UserRole.school_id == current["current_role"].school_id)
    )).scalars().first()
    if not teacher_role:
        raise HTTPException(404, "教师不存在")

    # Check if already assigned
    existing = (await db.execute(
        select(MarkingAssignment).where(
            MarkingAssignment.question_id == req.question_id,
            MarkingAssignment.teacher_id == req.teacher_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "该教师已被分配此题")

    assignment = MarkingAssignment(
        exam_id=req.exam_id,
        question_id=req.question_id,
        teacher_id=req.teacher_id,
        school_id=current["current_role"].school_id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    logger.info("assign_question: exam=%s, question=%s, teacher=%s", req.exam_id, req.question_id, req.teacher_id)
    return {"id": assignment.id, "exam_id": assignment.exam_id,
            "question_id": assignment.question_id, "teacher_id": assignment.teacher_id,
            "status": assignment.status}


@router.get("/my-assignments")
async def my_assignments(
    exam_id: str | None = None,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """教师获取自己的阅卷任务列表。"""
    query = select(MarkingAssignment).where(
        MarkingAssignment.teacher_id == current["user"].id,
        MarkingAssignment.school_id == current["current_role"].school_id,
    )
    if exam_id:
        query = query.where(MarkingAssignment.exam_id == exam_id)
    result = await db.execute(query)
    assignments = result.scalars().all()
    return [
        {"id": a.id, "exam_id": a.exam_id, "question_id": a.question_id,
         "teacher_id": a.teacher_id, "status": a.status}
        for a in assignments
    ]


@router.get("/assignments")
async def list_all_assignments(
    exam_id: str | None = None,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看全部分配情况。"""
    if current["current_role"].role not in ("admin", "principal"):
        raise HTTPException(403, "仅管理员可查看全部分配")
    query = select(MarkingAssignment).where(MarkingAssignment.school_id == current["current_role"].school_id)
    if exam_id:
        query = query.where(MarkingAssignment.exam_id == exam_id)
    result = await db.execute(query)
    assignments = result.scalars().all()
    return [
        {"id": a.id, "exam_id": a.exam_id, "question_id": a.question_id,
         "teacher_id": a.teacher_id, "status": a.status}
        for a in assignments
    ]


@router.get("/teachers")
async def list_teachers(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取本校教师列表（供分配使用）。"""
    if current["current_role"].role not in ("admin", "principal"):
        raise HTTPException(403, "仅管理员可查看教师列表")
    # Join User+UserRole to find teachers in this school
    result = await db.execute(
        select(User, UserRole).join(UserRole, UserRole.user_id == User.id).where(
            UserRole.school_id == current["current_role"].school_id,
            UserRole.role.in_(["teacher", "subject_teacher", "subject_leader", "head_teacher", "homeroom_teacher"]),
        )
    )
    rows = result.all()
    return [
        {"id": u.id, "username": u.username, "display_name": u.display_name,
         "role": r.role, "subject_codes": r.subject_codes}
        for u, r in rows
    ]


# ---------- Import ----------

@router.post("/import", response_model=ImportResponse)
async def import_folder(
    req: ImportRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从文件夹导入切割好的答题图片。"""
    from edu_cloud.modules.marking.importer import import_from_folder
    try:
        stats = await import_from_folder(db, req.exam_id, req.folder_path, current["current_role"].school_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return stats


# ---------- Subject / Question listing ----------

@router.get("/subjects")
async def list_subjects(
    exam_id: str,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取考试下所有科目及题目的阅卷进度。"""
    from edu_cloud.modules.marking.scorer import get_subjects_with_progress
    return await get_subjects_with_progress(db, exam_id, current["current_role"].school_id)


# ---------- Grading flow ----------

@router.get("/next")
async def next_answer(
    question_id: str,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取某题下一个未批改的答卷。"""
    # Permission check 1: subject-level access
    visible_codes = get_visible_subject_codes(current["current_role"])
    if visible_codes is not None:
        question = (await db.execute(
            select(Question).where(Question.id == question_id)
        )).scalar_one_or_none()
        if question:
            subject = (await db.execute(
                select(Subject).where(Subject.id == question.subject_id)
            )).scalar_one_or_none()
            if subject and subject.code not in visible_codes:
                raise HTTPException(403, "无权访问该科目的题目")

    # Permission check 2: assignment-level access (if assignments exist for this question)
    if current["current_role"].role not in ("admin", "principal"):
        has_assignments = (await db.execute(
            select(MarkingAssignment.id).where(MarkingAssignment.question_id == question_id).limit(1)
        )).scalar_one_or_none()
        if has_assignments:
            my_assignment = (await db.execute(
                select(MarkingAssignment).where(
                    MarkingAssignment.question_id == question_id,
                    MarkingAssignment.teacher_id == current["user"].id,
                )
            )).scalar_one_or_none()
            if not my_assignment:
                raise HTTPException(403, "该题目未分配给您")

    from edu_cloud.modules.marking.scorer import get_next_answer
    result = await get_next_answer(db, question_id, current["current_role"].school_id)
    if not result:
        return {"done": True, "answer": None}
    return {"done": False, "answer": result}


@router.get("/answer/{answer_id}/image")
async def get_answer_image(
    answer_id: str,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回学生答题图片。"""
    answer = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.id == answer_id,
            StudentAnswer.school_id == current["current_role"].school_id,
        )
    )).scalar_one_or_none()

    if not answer or not answer.image_path:
        raise HTTPException(404, "答题图片不存在")

    if not os.path.isfile(answer.image_path):
        raise HTTPException(404, f"图片文件不存在: {answer.image_path}")

    ext = os.path.splitext(answer.image_path)[1].lower()
    content_types = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".tif": "image/tiff", ".tiff": "image/tiff",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    def iter_file():
        with open(answer.image_path, "rb") as f:
            yield from iter(lambda: f.read(65536), b"")

    return StreamingResponse(iter_file(), media_type=content_type)


@router.post("/score")
async def submit_score_endpoint(
    req: ScoreRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交评分，并返回下一份未批改的答卷。"""
    from edu_cloud.modules.marking.scorer import submit_score, get_next_answer

    answer = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.id == req.answer_id,
            StudentAnswer.school_id == current["current_role"].school_id,
        )
    )).scalar_one_or_none()
    if not answer:
        raise HTTPException(404, "答卷不存在")

    question = (await db.execute(
        select(Question).where(Question.id == answer.question_id)
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "题目不存在")

    # Permission check: verify user can score this question's subject
    visible_codes = get_visible_subject_codes(current["current_role"])
    if visible_codes is not None:
        subject = (await db.execute(
            select(Subject).where(Subject.id == question.subject_id)
        )).scalar_one_or_none()
        if subject and subject.code not in visible_codes:
            raise HTTPException(403, "无权评阅该科目的题目")

    if req.score < 0 or req.score > question.max_score:
        raise HTTPException(400, f"分数必须在 0-{question.max_score} 之间")

    try:
        await submit_score(
            db, req.answer_id, answer.question_id,
            current["user"].id, current["current_role"].school_id, req.score, question.max_score, req.comment,
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e) or "unique" in str(e).lower():
            raise HTTPException(409, "该答卷已评分")
        raise

    next_ans = await get_next_answer(db, answer.question_id, current["current_role"].school_id)
    return {
        "ok": True,
        "next": {"done": False, "answer": next_ans} if next_ans else {"done": True, "answer": None},
    }


# ---------- Progress ----------

@router.get("/progress")
async def get_progress_endpoint(
    exam_id: str,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取考试的整体阅卷进度。"""
    from edu_cloud.modules.marking.scorer import get_progress
    return await get_progress(db, exam_id, current["current_role"].school_id)


# ---------- Export ----------

@router.get("/export")
async def export_csv(
    exam_id: str,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出考试成绩 CSV。"""
    from edu_cloud.modules.marking.exporter import export_scores_csv
    csv_content = await export_scores_csv(db, exam_id, current["current_role"].school_id)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=scores_{exam_id[:8]}.csv"},
    )
