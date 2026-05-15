"""CV 检测 + 模板校验子路由（从 pipeline_router.py 拆出）。"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.core.tenant import get_school_id
from edu_cloud.modules.exam.models import Question, Subject, QUESTION_TYPES_OBJECTIVE
from edu_cloud.modules.card.models import Template
from edu_cloud.config import settings
from edu_cloud.modules.scan.auto_detect_cv import AutoDetectCVRequest, auto_detect_cv_regions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scan/pipeline", tags=["scan-pipeline"])


@router.post('/auto-detect-cv')
async def auto_detect_cv_api(
    req: AutoDetectCVRequest,
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    school_id = get_school_id(current)
    p = req.image_path.strip()
    if p.startswith("/uploads/"):
        upload_root = Path(settings.UPLOAD_DIR).resolve()
        resolved = (upload_root / p.split("/uploads/", 1)[1]).resolve()
        if not resolved.is_relative_to(upload_root):
            raise HTTPException(403, "路径越界")
        rel_parts = resolved.relative_to(upload_root).parts
        if school_id and rel_parts and rel_parts[0] != school_id:
            raise HTTPException(403, "只允许访问本校的上传文件")
    elif not p.startswith("/samples/"):
        raise HTTPException(400, "image_path 只允许 /uploads/ 或 /samples/ 前缀")
    return await auto_detect_cv_regions(req)


@router.get('/cv-template')
async def get_cv_template(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """查询某科目已有的 CV 检测 Template（A+B 面）。"""
    school_id = get_school_id(current)
    tpl_stmt = select(Template).where(Template.subject_id == subject_id)
    if school_id:
        tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
    rows = (await db.execute(tpl_stmt)).scalars().all()
    if not rows:
        raise HTTPException(404, "该科目尚无模板")
    result = {}
    for t in rows:
        result[t.side] = {
            "regions": t.regions or [],
            "width": t.image_width,
            "height": t.image_height,
        }
    return result


class SaveCVTemplateRequest(BaseModel):
    subject_id: str
    side: str = "A"
    regions: list[dict]
    width: int
    height: int


@router.post('/save-cv-template')
async def save_cv_template(
    req: SaveCVTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """将 CV 检测结果保存/更新为 Template（upsert）。"""
    school_id = get_school_id(current)

    q = select(Subject).where(Subject.id == req.subject_id)
    if school_id:
        q = q.where(Subject.school_id == school_id)
    subject = (await db.execute(q)).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")
    school_id = subject.school_id

    q_stmt = select(Question).where(Question.subject_id == req.subject_id)
    if school_id:
        q_stmt = q_stmt.where(Question.school_id == school_id)
    questions = (await db.execute(q_stmt)).scalars().all()
    qno_map = {}
    q_by_name = {str(q.name): q for q in questions}

    def _qno_keys(qno) -> tuple:
        keys = [str(qno)]
        try:
            keys.append(int(str(qno).strip()))
        except (ValueError, TypeError):
            pass
        return tuple(keys)

    def _remember_question(qno, question: Question) -> None:
        for key in _qno_keys(qno):
            qno_map[key] = str(question.id)

    for q in questions:
        _remember_question(q.name, q)

    def _region_to_qtype(r):
        if r.get("type") == "choice_group":
            return "choice"
        return r.get("question_type", "essay")

    explicit_subjective_qnos = {
        str(r.get("qno"))
        for r in req.regions
        if r.get("type") not in ("choice_group", "barcode", "not_a_region")
        and r.get("qno") not in (None, "")
    }

    for r in req.regions:
        region_type = r.get("type")
        if region_type in ("not_a_region", "barcode"):
            r.pop("question_id", None)
            r.pop("question_ids", None)
            continue
        qno = r.get("qno")

        if region_type == "choice_group":
            start = int(r.get("start_no", 1) or 1)
            rows = int(r.get("rows", 0) or 0)
            qnos = r.get("qnos") or list(range(start, start + rows))
            q_ids = []
            skipped = False
            for n in qnos:
                if str(n) in explicit_subjective_qnos:
                    skipped = True
                    continue

                existing_q = q_by_name.get(str(n))
                if not existing_q:
                    existing_q = (await db.execute(
                        select(Question).where(
                            Question.subject_id == req.subject_id,
                            Question.name == str(n),
                        )
                    )).scalar_one_or_none()
                    if existing_q:
                        q_by_name[str(n)] = existing_q

                if existing_q:
                    existing_q.question_type = "choice"
                    existing_q.max_score = r.get("score", 0)
                    _remember_question(n, existing_q)
                    q_ids.append(str(existing_q.id))
                else:
                    new_q = Question(
                            subject_id=req.subject_id,
                            name=str(n),
                            question_type="choice",
                            max_score=r.get("score", 0),
                            school_id=school_id,
                    )
                    db.add(new_q)
                    await db.flush()
                    q_by_name[str(n)] = new_q
                    _remember_question(n, new_q)
                    q_ids.append(str(new_q.id))
                    logger.info("auto_create_question: subject=%s qno=%s type=choice", subject.name, n)

            if not skipped and len(q_ids) == len(qnos):
                r["question_ids"] = q_ids
            else:
                r.pop("question_ids", None)
        else:
            if not qno:
                continue

            qtype = _region_to_qtype(r)
            score = r.get("score", 0)
            existing_q = q_by_name.get(str(qno))
            if not existing_q:
                existing_q = (await db.execute(
                    select(Question).where(
                        Question.subject_id == req.subject_id,
                        Question.name == str(qno),
                    )
                )).scalar_one_or_none()
                if existing_q:
                    q_by_name[str(qno)] = existing_q

            if existing_q:
                existing_q.question_type = qtype
                existing_q.max_score = score
                _remember_question(qno, existing_q)
                r["question_id"] = str(existing_q.id)
            else:
                try:
                    new_q = Question(
                        subject_id=req.subject_id,
                        name=str(qno),
                        question_type=qtype,
                        max_score=score,
                        school_id=school_id,
                    )
                    db.add(new_q)
                    await db.flush()
                    q_by_name[str(qno)] = new_q
                    _remember_question(qno, new_q)
                    r["question_id"] = str(new_q.id)
                    logger.info("auto_create_question: subject=%s qno=%s type=%s", subject.name, qno, new_q.question_type)
                except Exception:
                    await db.rollback()
                    existing_q = (await db.execute(
                        select(Question).where(
                            Question.subject_id == req.subject_id,
                            Question.name == str(qno),
                        )
                    )).scalar_one_or_none()
                    if existing_q:
                        q_by_name[str(qno)] = existing_q
                        existing_q.question_type = qtype
                        existing_q.max_score = score
                        _remember_question(qno, existing_q)
                        r["question_id"] = str(existing_q.id)

    regions = [r for r in req.regions if r.get("type") != "not_a_region"]

    tpl_stmt = select(Template).where(
        Template.subject_id == req.subject_id,
        Template.side == req.side,
    )
    if school_id:
        tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
    existing = (await db.execute(tpl_stmt)).scalar_one_or_none()

    if existing:
        existing.regions = regions
        existing.image_width = req.width
        existing.image_height = req.height
    else:
        existing = Template(
            subject_id=req.subject_id,
            side=req.side,
            regions=regions,
            image_width=req.width,
            image_height=req.height,
            school_id=school_id,
        )
        db.add(existing)

    await db.commit()
    logger.info("save_cv_template: subject=%s side=%s regions=%d",
                subject.name, req.side, len(regions))
    return {"id": str(existing.id), "regions": len(regions)}


@router.get("/verify-template")
async def verify_template(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """校对模板区域 vs 题目配置，返回不一致项。"""
    school_id = get_school_id(current)

    tpl_stmt = select(Template).where(Template.subject_id == subject_id)
    if school_id:
        tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
    templates = (await db.execute(tpl_stmt)).scalars().all()

    q_stmt = select(Question).where(Question.subject_id == subject_id)
    if school_id:
        q_stmt = q_stmt.where(Question.school_id == school_id)
    questions = (await db.execute(q_stmt)).scalars().all()

    question_by_id = {str(q.id): q for q in questions}

    def _qno_sort_key(qno: str) -> tuple[int, str]:
        return (int(qno) if qno.isdigit() else 999, qno)

    def _question_qno(region: dict) -> str | None:
        qno = region.get("qno")
        if qno not in (None, ""):
            return str(qno)
        question_id = region.get("question_id")
        question = question_by_id.get(str(question_id)) if question_id else None
        return str(question.name) if question else None

    def _choice_group_qnos(region: dict) -> list[str]:
        qnos = region.get("qnos")
        if qnos:
            return [str(qno) for qno in qnos if qno not in (None, "")]
        try:
            start = int(region.get("start_no") or 1)
            rows = int(region.get("rows") or 0)
        except (TypeError, ValueError):
            return []
        return [str(n) for n in range(start, start + rows)]

    def _template_display_type(region: dict) -> str:
        return "choice_group" if region.get("type") == "choice_group" else "subjective"

    def _template_compare_type(region: dict) -> str:
        if region.get("type") == "choice_group":
            return "choice"
        return region.get("question_type") or "essay"

    def _types_match(template_type: str, question_type: str | None) -> bool:
        if template_type == "choice":
            return question_type in QUESTION_TYPES_OBJECTIVE
        if template_type in ("essay", "subjective"):
            return question_type not in QUESTION_TYPES_OBJECTIVE
        return template_type == question_type

    def _add_template_item(items: dict, qno: str, region: dict, side: str) -> None:
        score = region.get("score", 0) or 0
        item = items.get(qno)
        if not item:
            items[qno] = {
                "qno": qno,
                "type": _template_display_type(region),
                "compare_type": _template_compare_type(region),
                "score": score,
                "side": side,
                "region_ids": [region.get("id")],
            }
            return

        if region.get("id") not in item["region_ids"]:
            item["region_ids"].append(region.get("id"))
        if item["type"] == "choice_group" and region.get("type") != "choice_group":
            item.update({
                "type": _template_display_type(region),
                "compare_type": _template_compare_type(region),
                "score": score,
                "side": side,
            })
        elif score > item["score"]:
            item["score"] = score

    explicit_region_qnos = set()
    for tpl in templates:
        for r in (tpl.regions or []):
            if r.get("type") in ("barcode", "not_a_region", "choice_group"):
                continue
            qno = _question_qno(r)
            if qno:
                explicit_region_qnos.add(qno)

    tpl_items = {}
    for tpl in templates:
        for r in (tpl.regions or []):
            if r.get("type") in ("barcode", "not_a_region"):
                continue
            if r.get("type") == "choice_group":
                for qno in _choice_group_qnos(r):
                    if qno in explicit_region_qnos:
                        continue
                    _add_template_item(tpl_items, qno, r, tpl.side)
            else:
                qno = _question_qno(r)
                if qno:
                    _add_template_item(tpl_items, qno, r, tpl.side)

    q_items = {}
    for q in questions:
        key = q.name
        if key in q_items:
            q_items[key]["ids"].append(str(q.id))
            continue
        q_items[key] = {
            "qno": key,
            "type": q.question_type,
            "max_score": q.max_score or 0,
            "ids": [str(q.id)],
        }

    all_qnos = sorted(set(list(tpl_items.keys()) + list(q_items.keys())), key=_qno_sort_key)

    results = []
    for qno in all_qnos:
        t = tpl_items.get(qno)
        q = q_items.get(qno)
        status = "match"
        issues = []

        if t and not q:
            status = "missing_question"
            issues.append("模板有此区域，但题目表中无此题")
        elif q and not t:
            status = "missing_template"
            issues.append("题目表有此题，但模板中无对应区域")
        elif t and q:
            if abs(t["score"] - q["max_score"]) > 0.01:
                status = "score_mismatch"
                issues.append(f'分值不一致：模板 {t["score"]} vs 题目 {q["max_score"]}')
            if not _types_match(t["compare_type"], q["type"]):
                status = "type_mismatch" if status == "match" else status
                issues.append(f'题型不一致：模板 {t["compare_type"]} vs 题目 {q["type"]}')

        if t:
            t = {k: v for k, v in t.items() if k != "compare_type"}

        results.append({
            "qno": qno,
            "template": t,
            "question": q,
            "status": status,
            "issues": issues,
        })

    matched = sum(1 for r in results if r["status"] == "match")
    total = len(results)
    return {
        "subject_id": subject_id,
        "total": total,
        "matched": matched,
        "mismatched": total - matched,
        "items": results,
    }


@router.delete("/orphan-questions")
async def delete_orphan_questions(
    subject_id: str,
    qnos: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """删除模板中不存在的多余题目。qnos 逗号分隔。"""
    school_id = get_school_id(current)
    qno_list = [q.strip() for q in qnos.split(",") if q.strip()]
    if not qno_list:
        return {"deleted": 0}

    del_stmt = select(Question).where(
        Question.subject_id == subject_id,
        Question.name.in_(qno_list),
    )
    if school_id:
        del_stmt = del_stmt.where(Question.school_id == school_id)
    to_delete = (await db.execute(del_stmt)).scalars().all()

    count = 0
    for q in to_delete:
        await db.delete(q)
        count += 1

    await db.commit()
    logger.info("delete_orphan_questions: subject=%s qnos=%s deleted=%d", subject_id, qnos, count)
    return {"deleted": count}
