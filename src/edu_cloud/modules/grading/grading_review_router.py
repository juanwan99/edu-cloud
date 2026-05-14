"""阅卷审核/调度状态子路由。"""
import logging
from pathlib import Path
from typing import Literal
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.config import settings
from edu_cloud.modules.exam.models import Exam, Question, Subject, QUESTION_TYPES_SUBJECTIVE
from edu_cloud.modules.exam.question_order import question_sort_key
from edu_cloud.modules.grading.models import Rubric, GradingTask, GradingResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.card.models import Template
from edu_cloud.logging_config import business_event

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Result schemas ---

def _result_response(r: GradingResult) -> dict:
    return {
        "id": r.id,
        "task_id": r.ai_task_id,
        "answer_id": r.answer_id,
        "question_id": r.question_id,
        "ai_score": r.ai_score,
        "final_score": r.final_score,
        "max_score": r.max_score,
        "ai_feedback": r.ai_feedback,
        "ai_confidence": r.ai_confidence,
        "status": r.status,
        "source": r.source,
        "reviewer_id": r.reviewer_id,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "review_comment": r.review_comment,
        "version": r.version,
    }


# --- Result routes ---

@router.get("/results")
async def list_results(
    task_id: str | None = None,
    question_id: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    base = select(GradingResult).where(GradingResult.school_id == current["current_role"].school_id)
    if task_id:
        base = base.where(GradingResult.ai_task_id == task_id)
    if question_id:
        base = base.where(GradingResult.question_id == question_id)
    if status:
        base = base.where(GradingResult.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(GradingResult.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    logger.debug("list_results: filters={task=%s, question=%s, status=%s}, total=%d, page=%d",
                 task_id, question_id, status, total, page)
    return {"total": total, "page": page, "page_size": page_size, "items": [_result_response(r) for r in rows]}


@router.get("/review/pending")
async def list_pending_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    """返回 AI 已评但待教师确认的记录（status='ai_done'），分页。"""
    base = select(GradingResult).where(
        GradingResult.school_id == current["current_role"].school_id,
        GradingResult.status == "ai_done",
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(GradingResult.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    logger.debug("list_pending_reviews: total=%d, page=%d", total, page)
    return {"total": total, "page": page, "page_size": page_size, "items": [_result_response(r) for r in rows]}


@router.get("/results/{result_id}")
async def get_result(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    result = await db.execute(
        select(GradingResult).where(
            GradingResult.id == result_id,
            GradingResult.school_id == current["current_role"].school_id,
        )
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Result not found")
    return _result_response(r)


# --- Review schemas ---

class ReviewCreate(BaseModel):
    action: Literal["approve", "override"]
    adjusted_score: float | None = None
    comment: str | None = None


# --- Review routes ---

@router.post("/review/{result_id}")
async def submit_review(
    result_id: str,
    req: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """教师对 AI 评分进行 approve / override 确认。

    approve  → status=confirmed, source=ai, final_score=ai_score
    override → status=confirmed, source=ai_override, final_score=adjusted_score
    """
    result = await db.execute(
        select(GradingResult).where(
            GradingResult.id == result_id,
            GradingResult.school_id == current["current_role"].school_id,
        ).with_for_update()
    )
    gr = result.scalar_one_or_none()
    if not gr:
        raise HTTPException(404, "Result not found")

    if gr.status == "confirmed":
        logger.warning("submit_review: already confirmed, result=%s, source=%s",
                       result_id, gr.source)
        raise HTTPException(409, "Already reviewed")
    if gr.status != "ai_done":
        raise HTTPException(400, f"Cannot review result in status '{gr.status}'")

    if req.action == "override" and req.adjusted_score is None:
        raise HTTPException(400, "adjusted_score is required for override")

    now = datetime.now(timezone.utc)
    if req.action == "approve":
        gr.source = "ai"
        gr.final_score = gr.ai_score
    else:
        gr.source = "ai_override"
        gr.final_score = req.adjusted_score
    gr.status = "confirmed"
    gr.reviewer_id = current["user"].id
    gr.reviewed_at = now
    gr.review_comment = req.comment
    gr.version = gr.version + 1

    await db.commit()
    await db.refresh(gr)

    logger.info("submit_review: result=%s, action=%s, reviewer=%s, ai_score=%s, final_score=%s",
                result_id, req.action, current["user"].username, gr.ai_score, gr.final_score)

    return _result_response(gr)


@router.get("/dispatch/status")
async def get_dispatch_status(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """聚合该考试所有科目的阅卷调度状态。"""
    school_id = current["current_role"].school_id
    role = current["current_role"].role

    # 验证考试归属（platform_admin/district_admin 可跨校）
    q = select(Exam).where(Exam.id == exam_id)
    if school_id:
        q = q.where(Exam.school_id == school_id)
    exam = (await db.execute(q)).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")

    effective_school_id = exam.school_id

    # 获取所有科目
    subjects = (await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == effective_school_id)
    )).scalars().all()

    from edu_cloud.modules.scan import pipeline_service

    # 一次性扫描根目录，构建科目→图片数映射（兼容新旧存储布局）
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    scan_root = upload_root / effective_school_id / "scan-input" / exam_id
    if not scan_root.is_dir():
        scan_root = upload_root / "scan-input" / exam_id
    scan_dir_map = {}
    if scan_root.is_dir():
        for sub in scan_root.iterdir():
            if sub.is_dir():
                a_count = sum(
                    1 for f in sub.iterdir()
                    if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".bmp") and f.stem.endswith("A")
                )
                if a_count > 0:
                    scan_dir_map[sub.name] = a_count

    # 批量查 Template
    tpl_rows = (await db.execute(
        select(Template.subject_id).where(
            Template.subject_id.in_([s.id for s in subjects]),
            Template.side == "A",
            Template.school_id == effective_school_id,
        )
    )).scalars().all()
    tpl_set = set(tpl_rows)

    subject_ids = [s.id for s in subjects]

    # --- BQ1: StudentAnswer 聚合 per subject_id ---
    sa_stats_rows = (await db.execute(
        select(
            StudentAnswer.subject_id,
            func.count(StudentAnswer.id).label("answer_count"),
            func.count(StudentAnswer.id).filter(
                StudentAnswer.detected_answer.isnot(None)
            ).label("objective_graded"),
            func.count(StudentAnswer.id).filter(
                StudentAnswer.image_path.isnot(None)
            ).label("subjective_total"),
        ).where(
            StudentAnswer.subject_id.in_(subject_ids),
            StudentAnswer.school_id == effective_school_id,
        ).group_by(StudentAnswer.subject_id)
    )).all()
    sa_stats_map = {
        row[0]: {"answer_count": row[1], "objective_graded": row[2], "subjective_total": row[3]}
        for row in sa_stats_rows
    }

    # --- BQ2: GradingTask 全量（Python 侧取每科最新） ---
    all_tasks = (await db.execute(
        select(GradingTask).where(
            GradingTask.subject_id.in_(subject_ids),
            GradingTask.school_id == effective_school_id,
        ).order_by(GradingTask.created_at.desc())
    )).scalars().all()
    latest_task_map: dict[str, GradingTask] = {}
    for t in all_tasks:
        if t.subject_id not in latest_task_map:
            latest_task_map[t.subject_id] = t

    # --- BQ3: 主观题 Question 全量 ---
    all_subj_questions = (await db.execute(
        select(Question).where(
            Question.subject_id.in_(subject_ids),
            Question.school_id == effective_school_id,
            Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
        )
    )).scalars().all()
    subj_q_by_subject: dict[str, list] = {}
    all_subj_q_ids: list[str] = []
    q_to_subject: dict[str, str] = {}
    for q in all_subj_questions:
        subj_q_by_subject.setdefault(q.subject_id, []).append(q)
        all_subj_q_ids.append(q.id)
        q_to_subject[q.id] = q.subject_id

    # --- BQ4: GradingResult 统计 per question_id ---
    gr_stats_map: dict[str, dict] = {}
    if all_subj_q_ids:
        gr_stats_rows = (await db.execute(
            select(
                GradingResult.question_id,
                func.count(GradingResult.id).filter(
                    GradingResult.source.in_(["ai", "ai_override"]),
                ).label("ai_scored"),
                func.count(GradingResult.id).filter(
                    (GradingResult.status == "confirmed") | ((GradingResult.source == "manual") & (GradingResult.final_score.isnot(None))),
                ).label("confirmed"),
                func.count(GradingResult.id).filter(
                    GradingResult.source == "manual",
                    GradingResult.final_score.isnot(None),
                ).label("manual_only"),
            ).where(
                GradingResult.question_id.in_(all_subj_q_ids),
                GradingResult.school_id == effective_school_id,
            ).group_by(GradingResult.question_id)
        )).all()
        gr_stats_map = {row[0]: {"ai_scored": row[1], "confirmed": row[2], "manual_only": row[3]} for row in gr_stats_rows}

    # --- BQ5: AI pending 聚合 per subject_id ---
    pending_rows = (await db.execute(
        select(
            GradingTask.subject_id,
            func.coalesce(func.sum(GradingTask.total), 0),
            func.coalesce(func.sum(GradingTask.completed), 0),
            func.coalesce(func.sum(GradingTask.failed), 0),
        ).where(
            GradingTask.subject_id.in_(subject_ids),
            GradingTask.school_id == effective_school_id,
            GradingTask.status.in_(["pending", "processing"]),
        ).group_by(GradingTask.subject_id)
    )).all()
    pending_map = {
        row[0]: max(0, row[1] - row[2] - row[3])
        for row in pending_rows
    }

    # --- BQ6: Rubric 全量 per question_id ---
    all_rubric_map: dict[str, Rubric] = {}
    if all_subj_q_ids:
        all_rubrics = (await db.execute(
            select(Rubric).where(
                Rubric.question_id.in_(all_subj_q_ids),
                Rubric.school_id == effective_school_id,
            )
        )).scalars().all()
        all_rubric_map = {r.question_id: r for r in all_rubrics}

    # --- BQ7: StudentAnswer counts per question_id (for questions_info) ---
    ans_count_by_q: dict[str, int] = {}
    if all_subj_q_ids:
        ans_q_rows = (await db.execute(
            select(
                StudentAnswer.question_id,
                func.count(StudentAnswer.id),
            ).where(
                StudentAnswer.question_id.in_(all_subj_q_ids),
                StudentAnswer.school_id == effective_school_id,
            ).group_by(StudentAnswer.question_id)
        )).all()
        ans_count_by_q = {row[0]: row[1] for row in ans_q_rows}

    # --- 聚合 GradingResult 统计到 subject 级别 ---
    def _subject_gr_stats(sid: str) -> tuple[int, int, int]:
        q_ids = [q.id for q in subj_q_by_subject.get(sid, [])]
        ai_scored = sum(gr_stats_map.get(qid, {}).get("ai_scored", 0) for qid in q_ids)
        confirmed = sum(gr_stats_map.get(qid, {}).get("confirmed", 0) for qid in q_ids)
        manual = sum(gr_stats_map.get(qid, {}).get("manual_only", 0) for qid in q_ids)
        return ai_scored, confirmed, manual

    result = []
    for subj in subjects:
        sa = sa_stats_map.get(subj.id, {"answer_count": 0, "objective_graded": 0, "subjective_total": 0})
        answer_count = sa["answer_count"]
        objective_graded = sa["objective_graded"]
        subjective_total = sa["subjective_total"]

        grading_task = latest_task_map.get(subj.id)
        grading_task_id = grading_task.id if grading_task else None
        ai_failed = grading_task.failed if grading_task else 0

        ai_scored_count, confirmed_total, manual_confirmed_count = _subject_gr_stats(subj.id)
        ai_pending_count = pending_map.get(subj.id, 0)

        ai_graded = ai_scored_count
        reviewed = confirmed_total

        subjective_q_ids = [q.id for q in subj_q_by_subject.get(subj.id, [])]
        has_subjective_answers = subjective_total > 0
        has_rubric = any(qid in all_rubric_map for qid in subjective_q_ids)
        can_ai_grade = has_subjective_answers and has_rubric and len(subjective_q_ids) > 0

        questions_info = []
        if subjective_q_ids:
            subj_questions = sorted(subj_q_by_subject[subj.id], key=question_sort_key)
            for q in subj_questions:
                q_rubric = all_rubric_map.get(q.id)
                q_stats = gr_stats_map.get(q.id, {"ai_scored": 0, "confirmed": 0, "manual_only": 0})
                content_imgs = q.content_images or []
                ref_imgs = q.reference_answer_images or []
                questions_info.append({
                    "question_id": q.id,
                    "name": q.name,
                    "question_type": q.question_type,
                    "max_score": q.max_score,
                    "has_content": bool(q.content or content_imgs),
                    "has_answer": bool(q.reference_answer or ref_imgs),
                    "content_image_count": len(content_imgs),
                    "answer_image_count": len(ref_imgs),
                    "has_rubric": q_rubric is not None,
                    "rubric_source": q_rubric.source if q_rubric else None,
                    "answer_count": ans_count_by_q.get(q.id, 0),
                    "graded_count": q_stats["confirmed"],
                    "ai_scored_count": q_stats["ai_scored"],
                    "manual_confirmed_count": q_stats["manual_only"],
                    "parent_id": q.parent_id,
                })

        has_scan_dir = subj.name in scan_dir_map
        has_template = subj.id in tpl_set

        is_cutting = (
            pipeline_service.is_running()
            and pipeline_service.get_progress().get("current_subject_id") == subj.id
        )

        # stage 推导：idle → pending_detect → pending_cut → cutting → ready → ai_grading → reviewing → done
        if is_cutting:
            stage = "cutting"
        elif answer_count == 0 and not has_scan_dir:
            stage = "idle"
        elif answer_count == 0 and has_scan_dir and not has_template:
            stage = "pending_detect"
        elif answer_count == 0 and has_scan_dir and has_template:
            stage = "pending_cut"
        elif not grading_task and can_ai_grade:
            stage = "ready"
        elif not grading_task and answer_count > 0 and any(q.get("has_rubric") for q in questions_info):
            stage = "ready"
        elif not grading_task and answer_count > 0 and subjective_total > 0:
            stage = "ready"
        elif not grading_task:
            stage = "pending_cut" if has_template else "idle"
        elif grading_task.status == "failed":
            stage = "failed"
        elif grading_task.status in ("pending", "processing"):
            stage = "ai_grading"
        elif ai_scored_count > confirmed_total:
            stage = "reviewing"
        elif grading_task.status == "completed":
            stage = "done"
        else:
            stage = "ready"

        scan_image_count = scan_dir_map.get(subj.name, 0)

        result.append({
            "subject_id": subj.id,
            "subject_name": subj.name,
            "subject_code": subj.code,
            "stage": stage,
            "scan_images": scan_image_count,
            "has_scan_dir": has_scan_dir,
            "has_template": has_template,
            "answer_count": answer_count,
            "objective_total": objective_graded,
            "objective_graded": objective_graded,
            "subjective_total": subjective_total,
            "ai_scored_count": ai_scored_count,
            "manual_confirmed_count": manual_confirmed_count,
            "confirmed_total": confirmed_total,
            "ai_pending_count": ai_pending_count,
            "ai_graded": ai_graded,
            "ai_failed": ai_failed,
            "reviewed": reviewed,
            "grading_task_id": grading_task_id,
            "questions": questions_info,
        })

    return result


# --- Annotation API ---

class AnnotationItem(BaseModel):
    target: Literal["ocr", "score"]
    blankNo: str | None = None
    comment: str
    suggested_score: float | None = None


@router.patch("/results/{result_id}/annotations")
async def save_annotations(
    result_id: str,
    items: list[AnnotationItem],
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    school_id = current["current_role"].school_id
    gr = (await db.execute(
        select(GradingResult).where(
            GradingResult.id == result_id,
            GradingResult.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not gr:
        raise HTTPException(404, "评分记录不存在")

    teacher_id = current["user"].id
    annotations = [
        {**item.model_dump(exclude_none=True), "teacher_id": teacher_id}
        for item in items
    ]
    gr.annotations = annotations
    await db.commit()
    business_event(
        "annotation_save", "grading_result", result_id,
        fields_changed={"annotation_count": len(annotations)},
        exam_id=gr.question_id,
    )
    return {"ok": True, "count": len(annotations)}


@router.get("/annotations/summary")
async def get_annotation_summary(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    school_id = current["current_role"].school_id
    results = (await db.execute(
        select(GradingResult).where(
            GradingResult.question_id == question_id,
            GradingResult.school_id == school_id,
            GradingResult.annotations.is_not(None),
        )
    )).scalars().all()

    by_blank: dict[str, list] = {}
    for gr in results:
        for ann in (gr.annotations or []):
            key = ann.get("blankNo") or "_overall"
            by_blank.setdefault(key, []).append({
                "target": ann.get("target"),
                "comment": ann.get("comment"),
                "suggested_score": ann.get("suggested_score"),
                "teacher_id": ann.get("teacher_id"),
                "answer_id": gr.answer_id,
                "ai_score": gr.ai_score,
            })

    summary = []
    for blank_no, anns in sorted(by_blank.items()):
        suggested = [a["suggested_score"] for a in anns if a.get("suggested_score") is not None]
        summary.append({
            "blankNo": blank_no,
            "annotation_count": len(anns),
            "suggested_score_avg": round(sum(suggested) / len(suggested), 2) if suggested else None,
            "annotations": anns,
        })
    return {"question_id": question_id, "total_annotated": len(results), "by_blank": summary}
