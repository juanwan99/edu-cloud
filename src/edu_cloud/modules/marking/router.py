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
from edu_cloud.modules.grading.models import GradingAssignment
from edu_cloud.api.permissions import get_visible_subject_codes, is_school_admin

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


class FlagRequest(BaseModel):
    anomaly_type: str | None = None


class ScoreRequest(BaseModel):
    answer_id: str
    score: float
    comment: str | None = None


class AssignRequest(BaseModel):
    exam_id: str
    question_id: str
    teacher_id: str
    answer_count: int = 0


def _has_question_assigned(assignment: GradingAssignment, question_id: str) -> bool:
    qids = assignment.question_ids or []
    return question_id in qids


def _flatten_assignment(a: GradingAssignment) -> list[dict]:
    """一条块级分配 → 多条题级响应（前端契约保持题级）。"""
    return [
        {
            "id": a.id, "exam_id": a.exam_id, "question_id": qid,
            "teacher_id": a.assigned_to, "status": a.status,
            "answer_count": a.total_count, "graded_count": a.graded_count,
        }
        for qid in (a.question_ids or [])
    ]


# ---------- Assignment ----------

@router.post("/assign", status_code=201)
async def assign_question(
    req: AssignRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员将题目分配给指定教师阅卷（单题 → 块级分配 question_ids=[qid]）。"""
    if not is_school_admin(current["current_role"]):
        raise HTTPException(403, "仅管理员可分配阅卷任务")

    school_id = current["current_role"].school_id

    exam = (await db.execute(
        select(Exam).where(Exam.id == req.exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "考试不存在")

    question = (await db.execute(
        select(Question).where(Question.id == req.question_id, Question.school_id == school_id)
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "题目不存在")

    subject = (await db.execute(
        select(Subject).where(Subject.id == question.subject_id, Subject.exam_id == req.exam_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(400, "题目不属于该考试")

    teacher_role = (await db.execute(
        select(UserRole).where(UserRole.user_id == req.teacher_id, UserRole.school_id == school_id)
    )).scalars().first()
    if not teacher_role:
        raise HTTPException(404, "教师不存在")

    # 同教师+同题冲突检测
    existing_list = (await db.execute(
        select(GradingAssignment).where(
            GradingAssignment.exam_id == req.exam_id,
            GradingAssignment.subject_id == subject.id,
            GradingAssignment.assigned_to == req.teacher_id,
            GradingAssignment.school_id == school_id,
            GradingAssignment.is_second_grading.is_(False),
        )
    )).scalars().all()

    for a in existing_list:
        if _has_question_assigned(a, req.question_id):
            raise HTTPException(409, "该教师已被分配此题")

    # 每次创建独立行（一题一教师）
    a = GradingAssignment(
        exam_id=req.exam_id, subject_id=subject.id,
        question_ids=[req.question_id],
        assigned_to=req.teacher_id, school_id=school_id,
        total_count=req.answer_count,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)

    logger.info("assign_question: exam=%s, question=%s, teacher=%s",
                req.exam_id, req.question_id, req.teacher_id)
    return {
        "id": a.id, "exam_id": a.exam_id,
        "question_id": req.question_id, "teacher_id": a.assigned_to,
        "status": a.status,
    }


@router.get("/my-assignments")
async def my_assignments(
    exam_id: str | None = None,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """教师获取自己的阅卷任务列表（块级 → 题级展平）。"""
    query = select(GradingAssignment).where(
        GradingAssignment.assigned_to == current["user"].id,
        GradingAssignment.school_id == current["current_role"].school_id,
    )
    if exam_id:
        query = query.where(GradingAssignment.exam_id == exam_id)
    result = await db.execute(query)
    assignments = result.scalars().all()
    flat = []
    for a in assignments:
        flat.extend(_flatten_assignment(a))
    return flat


@router.get("/assignments")
async def list_all_assignments(
    exam_id: str | None = None,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看全部分配情况（块级 → 题级展平）。"""
    if not is_school_admin(current["current_role"]):
        raise HTTPException(403, "仅管理员可查看全部分配")
    query = select(GradingAssignment).where(
        GradingAssignment.school_id == current["current_role"].school_id,
    )
    if exam_id:
        query = query.where(GradingAssignment.exam_id == exam_id)
    result = await db.execute(query)
    assignments = result.scalars().all()
    flat = []
    for a in assignments:
        flat.extend(_flatten_assignment(a))
    return flat


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: str,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除阅卷分配。"""
    if not is_school_admin(current["current_role"]):
        raise HTTPException(403, "仅管理员可删除阅卷分配")
    school_id = current["current_role"].school_id
    assignment = (await db.execute(
        select(GradingAssignment).where(
            GradingAssignment.id == assignment_id,
            GradingAssignment.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not assignment:
        raise HTTPException(404, "分配记录不存在")
    await db.delete(assignment)
    await db.commit()
    return {"ok": True}


@router.get("/teachers")
async def list_teachers(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取本校教师列表（供分配使用）。"""
    if not is_school_admin(current["current_role"]):
        raise HTTPException(403, "仅管理员可查看教师列表")
    result = await db.execute(
        select(User, UserRole).join(UserRole, UserRole.user_id == User.id).where(
            UserRole.school_id == current["current_role"].school_id,
            UserRole.role.in_(["teacher", "subject_teacher", "subject_leader", "head_teacher", "homeroom_teacher"]),
        )
    )
    rows = result.all()
    seen: dict = {}
    for u, r in rows:
        if u.id not in seen:
            seen[u.id] = {
                "id": u.id, "username": u.username, "display_name": u.display_name,
                "role": r.role, "subject_codes": list(r.subject_codes or []),
            }
        else:
            for code in (r.subject_codes or []):
                if code not in seen[u.id]["subject_codes"]:
                    seen[u.id]["subject_codes"].append(code)
    return list(seen.values())


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
    visible_codes = get_visible_subject_codes(current["current_role"])
    return await get_subjects_with_progress(
        db, exam_id, current["current_role"].school_id, visible_codes=visible_codes,
    )


# ---------- Grading flow ----------

@router.get("/next")
async def next_answer(
    question_id: str,
    mode: str = "ungraded",
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取某题下一个答卷。

    mode:
      - ungraded: 未批改的答卷（默认）
      - ai_review: AI 已评但未确认的答卷（复核模式）
    """
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

    # Permission check 2: assignment-level access (ai_review skips assignment check)
    if mode == "ai_review":
        pass
    elif not is_school_admin(current["current_role"]):
        all_assign = (await db.execute(
            select(GradingAssignment).where(
                GradingAssignment.school_id == current["current_role"].school_id,
            )
        )).scalars().all()
        has_any = any(_has_question_assigned(a, question_id) for a in all_assign)
        if has_any:
            mine = any(
                _has_question_assigned(a, question_id)
                and a.assigned_to == current["user"].id
                for a in all_assign
            )
            if not mine:
                raise HTTPException(403, "该题目未分配给您")

    from edu_cloud.modules.marking.scorer import get_next_answer
    result = await get_next_answer(
        db, question_id, current["current_role"].school_id,
        teacher_id=current["user"].id,
        mode=mode,
    )
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
    """提交评分，并返回下一份未批改的答卷。

    统一写入 GradingResult：
    - 若已有 AI 预评 → 升级为 confirmed（source=ai 或 ai_override）
    - 若无预评 → 新建 source=manual, status=confirmed
    """
    from edu_cloud.modules.marking.scorer import submit_score, get_next_answer, update_assignment_progress

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
            current["user"].id, current["current_role"].school_id,
            req.score, question.max_score, req.comment,
        )
    except ValueError as e:
        raise HTTPException(409, str(e))

    await update_assignment_progress(db, answer.question_id, current["user"].id, current["current_role"].school_id)

    next_ans = await get_next_answer(
        db, answer.question_id, current["current_role"].school_id,
        teacher_id=current["user"].id,
    )
    return {
        "ok": True,
        "next": {"done": False, "answer": next_ans} if next_ans else {"done": True, "answer": None},
    }


# ---------- Browse (prev/next) ----------

@router.get("/answer-at")
async def get_answer_at_endpoint(
    question_id: str,
    offset: int = 0,
    mode: str = "ungraded",
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按索引获取某题的第 offset 份答卷（0-based），支持前后翻页。"""
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

    if mode not in ("ai_review", "reviewed") and not is_school_admin(current["current_role"]):
        all_assign = (await db.execute(
            select(GradingAssignment).where(
                GradingAssignment.school_id == current["current_role"].school_id,
            )
        )).scalars().all()
        has_any = any(_has_question_assigned(a, question_id) for a in all_assign)
        if has_any:
            mine = any(
                _has_question_assigned(a, question_id)
                and a.assigned_to == current["user"].id
                for a in all_assign
            )
            if not mine:
                raise HTTPException(403, "该题目未分配给您")

    from edu_cloud.modules.marking.scorer import get_answer_at
    result = await get_answer_at(db, question_id, current["current_role"].school_id, offset, mode=mode)
    if not result:
        raise HTTPException(404, "无更多答卷")
    return result


# ---------- Anomaly flag ----------

ANOMALY_TYPES = ["scan_error", "blank", "illegible", "wrong_question", "suspected_cheating", "other"]


@router.patch("/answer/{answer_id}/flag")
async def flag_answer(
    answer_id: str,
    req: FlagRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记/取消标记答卷异常。anomaly_type=null 时清除标记。"""
    answer = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.id == answer_id,
            StudentAnswer.school_id == current["current_role"].school_id,
        )
    )).scalar_one_or_none()
    if not answer:
        raise HTTPException(404, "答卷不存在")

    if req.anomaly_type is not None and req.anomaly_type not in ANOMALY_TYPES:
        raise HTTPException(400, f"无效的异常类型，可选: {', '.join(ANOMALY_TYPES)}")

    answer.is_anomaly = req.anomaly_type is not None
    answer.anomaly_type = req.anomaly_type
    await db.commit()

    logger.info("flag_answer: answer=%s, anomaly_type=%s, by=%s",
                answer_id, req.anomaly_type, current["user"].id)
    return {"ok": True, "is_anomaly": answer.is_anomaly, "anomaly_type": answer.anomaly_type}


# ---------- Progress ----------

@router.get("/progress")
async def get_progress_endpoint(
    exam_id: str,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取考试的整体阅卷进度。"""
    from edu_cloud.modules.marking.scorer import get_progress
    visible_codes = get_visible_subject_codes(current["current_role"])
    return await get_progress(
        db, exam_id, current["current_role"].school_id, visible_codes=visible_codes,
    )


# ---------- Export ----------

@router.get("/export")
async def export_csv(
    exam_id: str,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出考试成绩 CSV。"""
    from edu_cloud.modules.marking.exporter import export_scores_csv
    visible_codes = get_visible_subject_codes(current["current_role"])
    csv_content = await export_scores_csv(
        db, exam_id, current["current_role"].school_id, visible_codes=visible_codes,
    )
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=scores_{exam_id[:8]}.csv"},
    )
