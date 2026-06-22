"""F003 B1 新模块：publish 一站式原子操作的业务逻辑层。"""
from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.exc import IntegrityError
from edu_cloud.core.state_machine import validate_transition
from edu_cloud.services.card_workflow import Exam, Question, Subject
from edu_cloud.modules.card.export.html_export import html_to_pdf, extract_skeleton

logger = logging.getLogger(__name__)


async def upsert_questions_from_skeleton(
    db: AsyncSession,
    subject_id: str,
    school_id: str,
    skeleton: dict,
) -> dict[str, str]:
    """从 skeleton 扫描 regions + objective_groups，upsert Question 表，返回 {name: question_id} map。

    upsert 语义（决策 D4）:
      - 匹配 (subject_id, name)：存在 → UPDATE max_score/question_type；不存在 → INSERT
      - 孤儿（DB 有但 skeleton 没）→ 保留不动
    """
    items: list[tuple[str, str, float]] = []

    for group in skeleton.get("objective_groups", []) or []:
        start_no = group.get("start_no", 1)
        count = group.get("count", 0)
        per_score = group.get("per_score", 0) or 0
        is_multi = bool(group.get("multi_select"))
        qtype = "multi_choice" if is_multi else "choice"
        for i in range(count):
            qno = str(start_no + i)
            items.append((qno, qtype, float(per_score)))

    for slot in skeleton.get("slots", []) or []:
        for sr in slot.get("sub_regions", []) or []:
            name = sr.get("name")
            if not name:
                logger.warning(
                    "publish_service: skip anonymous slot sub_region id=%s",
                    sr.get("id"),
                )
                continue
            score = float(sr.get("score", 0) or 0)
            sub_qtype = sr.get("question_type")
            if sub_qtype not in ("fill_blank", "essay"):
                sub_qtype = "fill_blank" if sr.get("type") == "fill_blank" else "essay"
            items.append((str(name), sub_qtype, score))

    if not items:
        logger.info("upsert_questions: empty skeleton, nothing to upsert")
        return {}

    existing = (await db.execute(
        select(Question).where(
            Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )).scalars().all()
    existing_by_name = {q.name: q for q in existing}

    name_to_id: dict[str, str] = {}
    for name, qtype, max_score in items:
        if name in existing_by_name:
            q = existing_by_name[name]
            q.question_type = qtype
            q.max_score = max_score
            name_to_id[name] = q.id
        else:
            q = Question(
                subject_id=subject_id,
                school_id=school_id,
                name=name,
                question_type=qtype,
                max_score=max_score,
            )
            try:
                async with db.begin_nested():
                    db.add(q)
                    await db.flush()
                name_to_id[name] = q.id
            except IntegrityError:
                logger.warning(
                    "upsert_questions: concurrent INSERT race for (subject=%s, name=%s), re-selecting",
                    subject_id, name,
                )
                existing_q = (await db.execute(
                    select(Question).where(
                        Question.subject_id == subject_id,
                        Question.name == name,
                    )
                )).scalar_one()
                existing_q.question_type = qtype
                existing_q.max_score = max_score
                name_to_id[name] = existing_q.id

    logger.info(
        "upsert_questions: subject=%s upserted=%d orphans=%d",
        subject_id, len(items),
        len(existing) - len([q for q in existing if q.name in name_to_id]),
    )
    return name_to_id


async def upsert_template_both_sides(
    db: AsyncSession,
    subject_id: str,
    school_id: str,
    skeleton: dict,
    question_map: dict[str, str],
) -> tuple:
    """按 skeleton.regions[].side 分组，构建 A/B 面 Template，upsert 走 UniqueConstraint(subject_id, side)。

    返回 (tpl_a, tpl_b)。A 面必存，B 面可选（单面时 tpl_b=None）。
    B-only → raise HTTPException(400)。
    """
    from fastapi import HTTPException
    from edu_cloud.modules.card.export.export import skeleton_to_paperseg_json
    from edu_cloud.modules.card.models import Template

    regions_by_side: dict[str, list[dict]] = {"A": [], "B": []}
    for r in skeleton.get("regions", []) or []:
        side = r.get("side", "A")
        if side not in regions_by_side:
            side = "A"
        regions_by_side[side].append(r)

    if not regions_by_side["A"]:
        if regions_by_side["B"]:
            raise HTTPException(
                400,
                "发布失败：答题卡必须包含 A 面内容（B-only 不支持，"
                "下游扫描/阅卷默认按 A 面查 Template）",
            )
        raise HTTPException(400, "发布失败：答题卡为空（skeleton.regions 无内容）")

    result: list = [None, None]

    for idx, side in enumerate(("A", "B")):
        side_regions = regions_by_side[side]
        if not side_regions:
            continue

        side_region_ids = {r["id"] for r in side_regions}

        filtered_slots = []
        for slot in skeleton.get("slots", []) or []:
            filtered_srs = [
                sr for sr in slot.get("sub_regions", []) or []
                if sr.get("id") in side_region_ids
            ]
            if filtered_srs:
                filtered_slots.append({**slot, "sub_regions": filtered_srs})

        filtered_obj_groups = [
            g for g in (skeleton.get("objective_groups", []) or [])
            if g.get("group_id") in side_region_ids
        ]

        side_skeleton = {
            **skeleton,
            "regions": side_regions,
            "objective_groups": filtered_obj_groups,
        }
        tpl_data = skeleton_to_paperseg_json(
            side_skeleton,
            {"slots": filtered_slots},
            exam_id="",
            subject="",
            side=side,
            question_map=question_map,
        )

        existing_tpl = (await db.execute(
            select(Template).where(
                Template.subject_id == subject_id,
                Template.side == side,
            )
        )).scalar_one_or_none()

        values = {
            "image_width": tpl_data["image_size"]["width"],
            "image_height": tpl_data["image_size"]["height"],
            "anchors": tpl_data["anchors"],
            "regions": tpl_data["regions"],
        }

        if existing_tpl:
            for k, v in values.items():
                setattr(existing_tpl, k, v)
            result[idx] = existing_tpl
        else:
            tpl = Template(
                subject_id=subject_id,
                side=side,
                school_id=school_id,
                **values,
            )
            db.add(tpl)
            await db.flush()
            result[idx] = tpl

    return result[0], result[1]


async def publish_card_atomic(
    db: AsyncSession,
    html: str,
    subject_id: str,
    exam_id: str,
    school_id: str,
    paper_size: str,
) -> bytes:
    """publish 一站式原子操作。

    顺序：PDF/skeleton 在事务外，DB 写在事务内。任一 DB 步失败 → rollback → raise。
    """
    from fastapi import HTTPException

    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "考试不存在")
    if exam.status not in ("draft", "scanning"):
        raise HTTPException(400, f"考试状态为 {exam.status}，仅 draft/scanning 可发布")

    subject = (await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")
    if subject.exam_id != exam_id:
        raise HTTPException(400, "科目不属于该考试")

    if not html or not html.strip():
        raise HTTPException(400, "HTML 不能为空")

    pdf_bytes = await html_to_pdf(html, paper_size)
    skeleton = await extract_skeleton(html)

    try:
        async with db.begin_nested():
            question_map = await upsert_questions_from_skeleton(
                db, subject_id=subject_id, school_id=school_id, skeleton=skeleton,
            )
            await upsert_template_both_sides(
                db, subject_id=subject_id, school_id=school_id,
                skeleton=skeleton, question_map=question_map,
            )
            if exam.status == "draft":
                validate_transition("exam", exam.status, "scanning")
                exam.status = "scanning"
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    logger.info(
        "publish_card_atomic: exam=%s subject=%s questions=%d success",
        exam_id, subject_id, len(question_map),
    )
    return pdf_bytes
