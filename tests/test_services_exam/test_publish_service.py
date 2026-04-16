"""F003 publish_service 单元测试 — upsert_questions / upsert_template / publish_card_atomic."""
import pytest
from sqlalchemy import select

from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject, Question


@pytest.fixture
async def empty_subject(db):
    """创建空 subject（无任何 Question），返回 school/exam/subject ids。"""
    school = School(name="PSTest", code="PS01")
    db.add(school)
    await db.commit()
    exam = Exam(name="PSExam", school_id=school.id, status="draft")
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject)
    await db.commit()
    return {"school_id": school.id, "exam_id": exam.id, "subject_id": subject.id}


def _build_skeleton(objective_groups=None, slots=None):
    """构造最小 skeleton dict（模拟 extract_skeleton 的输出形状）。"""
    return {
        "objective_groups": objective_groups or [],
        "slots": slots or [],
        "image_width": 1587,
        "image_height": 1123,
        "anchors": [],
    }


async def test_S2_upsert_questions_from_skeleton_new_subject(db, empty_subject):
    """S2: 空 Subject 首次 publish，skeleton 含 12 选择题 + 3 主观题 → 创建 15 条 Question。

    反例：错误实现只创建 subjective 或只创建 objective group 合并为 1 条。
    """
    from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton

    skeleton = _build_skeleton(
        objective_groups=[
            {"group_id": "obj1", "start_no": 1, "count": 12, "options": 4,
             "symbols": "A,B,C,D", "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}
        ],
        slots=[
            {"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
                {"id": "essay-14", "name": "14", "score": 15, "rect": {"x1": 0, "y1": 200, "x2": 100, "y2": 300}},
                {"id": "essay-15", "name": "15", "score": 20, "rect": {"x1": 0, "y1": 300, "x2": 100, "y2": 400}},
            ]}
        ],
    )

    q_map = await upsert_questions_from_skeleton(
        db,
        subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"],
        skeleton=skeleton,
    )
    await db.commit()

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    names = sorted([q.name for q in qs], key=lambda s: int(s) if s.isdigit() else 999)
    assert len(qs) == 15
    assert names[:12] == [str(i) for i in range(1, 13)]
    assert names[12:] == ["13", "14", "15"]

    assert set(q_map.keys()) == set(names)
    assert all(q_map[q.name] == q.id for q in qs)

    types = {q.name: q.question_type for q in qs}
    for i in range(1, 13):
        assert types[str(i)] == "choice"
    for n in ["13", "14", "15"]:
        assert types[n] == "essay"


async def test_S3_upsert_questions_idempotent(db, empty_subject):
    """S3: 同 skeleton 连续调用两次，Question 数量不变（幂等）。"""
    from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton

    skeleton = _build_skeleton(
        slots=[{"sub_regions": [
            {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        ]}],
    )

    await upsert_questions_from_skeleton(db, **{
        "subject_id": empty_subject["subject_id"],
        "school_id": empty_subject["school_id"],
        "skeleton": skeleton,
    })
    await db.commit()

    skeleton["slots"][0]["sub_regions"][0]["score"] = 12
    q_map2 = await upsert_questions_from_skeleton(db, **{
        "subject_id": empty_subject["subject_id"],
        "school_id": empty_subject["school_id"],
        "skeleton": skeleton,
    })
    await db.commit()

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 1, f"幂等失败，Question 数量 {len(qs)} != 1"
    assert qs[0].max_score == 12.0, f"分值未更新，实际 {qs[0].max_score}"


async def test_S4_upsert_preserves_orphan(db, empty_subject):
    """S4: 首次 publish 有题目 13/14/15，二次 publish 只有 13/14（老师删了 15）→ DB 仍 3 条。"""
    from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton

    skel1 = _build_skeleton(slots=[{"sub_regions": [
        {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        {"id": "essay-14", "name": "14", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
        {"id": "essay-15", "name": "15", "score": 10, "rect": {"x1": 0, "y1": 200, "x2": 100, "y2": 300}},
    ]}])
    await upsert_questions_from_skeleton(db, subject_id=empty_subject["subject_id"],
                                          school_id=empty_subject["school_id"], skeleton=skel1)
    await db.commit()

    skel2 = _build_skeleton(slots=[{"sub_regions": [
        {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        {"id": "essay-14", "name": "14", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
    ]}])
    await upsert_questions_from_skeleton(db, subject_id=empty_subject["subject_id"],
                                          school_id=empty_subject["school_id"], skeleton=skel2)
    await db.commit()

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 3, f"孤儿保留失败，Question 数量 {len(qs)} != 3"
    names = {q.name for q in qs}
    assert names == {"13", "14", "15"}


async def test_S5_upsert_template_both_sides(db, empty_subject):
    """S5: skeleton 含 A/B 双面 region → upsert 后 Template 表有 2 条记录 (A 面 + B 面)。"""
    from edu_cloud.modules.card.publish_service import (
        upsert_questions_from_skeleton, upsert_template_both_sides,
    )
    from edu_cloud.modules.card.models import Template

    skeleton = {
        "image_width": 1587, "image_height": 1123, "anchors": [],
        "objective_groups": [],
        "slots": [{"sub_regions": [
            {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            {"id": "essay-14", "name": "14", "score": 10, "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
        ]}],
        "regions": [
            {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
             "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            {"id": "essay-14", "type": "subjective", "qno": 14, "side": "B",
             "rect": {"x1": 0, "y1": 100, "x2": 100, "y2": 200}},
        ],
    }

    q_map = await upsert_questions_from_skeleton(
        db, subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"], skeleton=skeleton,
    )

    tpl_a, tpl_b = await upsert_template_both_sides(
        db,
        subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"],
        skeleton=skeleton,
        question_map=q_map,
    )
    await db.commit()

    assert tpl_a is not None and tpl_a.side == "A"
    assert tpl_b is not None and tpl_b.side == "B"

    a_region_ids = {r["id"] for r in tpl_a.regions}
    b_region_ids = {r["id"] for r in tpl_b.regions}
    assert a_region_ids == {"essay-13"}, f"A 面应只含 essay-13，实际 {a_region_ids}"
    assert b_region_ids == {"essay-14"}, f"B 面应只含 essay-14，实际 {b_region_ids}"

    templates = (await db.execute(
        select(Template).where(Template.subject_id == empty_subject["subject_id"])
    )).scalars().all()
    assert len(templates) == 2
    sides = {t.side for t in templates}
    assert sides == {"A", "B"}


async def test_S5b_single_side_only_A(db, empty_subject):
    """S5b: skeleton 只有 A 面 region → 仅 A 面 Template，B 面返回 None。"""
    from edu_cloud.modules.card.publish_service import (
        upsert_questions_from_skeleton, upsert_template_both_sides,
    )
    from edu_cloud.modules.card.models import Template

    skeleton = {
        "image_width": 1587, "image_height": 1123, "anchors": [],
        "objective_groups": [],
        "slots": [{"sub_regions": [
            {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        ]}],
        "regions": [
            {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
             "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        ],
    }
    q_map = await upsert_questions_from_skeleton(
        db, subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"], skeleton=skeleton,
    )
    tpl_a, tpl_b = await upsert_template_both_sides(
        db, subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"], skeleton=skeleton, question_map=q_map,
    )
    await db.commit()
    assert tpl_a is not None and tpl_a.side == "A"
    assert tpl_b is None

    a_region_ids = {r["id"] for r in tpl_a.regions}
    assert a_region_ids == {"essay-13"}, f"A 面应只含 essay-13，实际 {a_region_ids}"


async def test_S5c_only_B_side_raises_400(db, empty_subject):
    """S5c: B-only publish → raise HTTPException(400) 含 'A 面'。"""
    from fastapi import HTTPException
    from edu_cloud.modules.card.publish_service import (
        upsert_questions_from_skeleton, upsert_template_both_sides,
    )

    skeleton = {
        "image_width": 1587, "image_height": 1123, "anchors": [],
        "objective_groups": [], "slots": [],
        "regions": [
            {"id": "essay-13", "type": "subjective", "qno": 13, "side": "B",
             "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
        ],
    }
    q_map = await upsert_questions_from_skeleton(
        db, subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"], skeleton=skeleton,
    )

    with pytest.raises(HTTPException) as exc_info:
        await upsert_template_both_sides(
            db, subject_id=empty_subject["subject_id"],
            school_id=empty_subject["school_id"], skeleton=skeleton, question_map=q_map,
        )
    assert exc_info.value.status_code == 400
    assert "A 面" in exc_info.value.detail


async def test_INV001_empty_skeleton(db, empty_subject):
    """INV-001: 空 skeleton（无 objective_groups 无 slots）返回空字典 {}，不抛异常。"""
    from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton

    q_map = await upsert_questions_from_skeleton(
        db,
        subject_id=empty_subject["subject_id"],
        school_id=empty_subject["school_id"],
        skeleton={"objective_groups": [], "slots": []},
    )
    assert q_map == {}, f"空 skeleton 应返回空 dict，实际 {q_map}"


from unittest.mock import patch
from sqlalchemy.exc import IntegrityError as SAIntegrityError


async def test_S7a_savepoint_semantics_preserves_outer_tx(db, empty_subject):
    """S7a: 纯 SAVEPOINT 语义——子事务 rollback 不破坏外层事务中其他对象。"""
    subject_id = empty_subject["subject_id"]
    school_id = empty_subject["school_id"]

    q_13 = Question(
        subject_id=subject_id, school_id=school_id,
        name="13", question_type="essay", max_score=10.0,
    )
    db.add(q_13)
    await db.flush()

    try:
        async with db.begin_nested():
            q_14 = Question(
                subject_id=subject_id, school_id=school_id,
                name="14", question_type="essay", max_score=12.0,
            )
            db.add(q_14)
            raise SAIntegrityError("simulated flush race", params=None, orig=Exception("race"))
    except SAIntegrityError:
        pass

    q_15 = Question(
        subject_id=subject_id, school_id=school_id,
        name="15", question_type="essay", max_score=15.0,
    )
    db.add(q_15)
    await db.flush()

    await db.commit()

    qs = (await db.execute(
        select(Question).where(Question.subject_id == subject_id).order_by(Question.name)
    )).scalars().all()
    names = [q.name for q in qs]
    assert names == ["13", "15"], (
        f"外层事务应保留 '13' 和 '15'（SAVEPOINT 回滚 '14'），实际 {names}"
    )


async def test_S7b_upsert_questions_existing_fast_path(db, empty_subject):
    """S7b: 预插入 rival '14' → SELECT 命中 → existing update 分支。"""
    from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton

    subject_id = empty_subject["subject_id"]
    school_id = empty_subject["school_id"]

    rival = Question(
        subject_id=subject_id, school_id=school_id,
        name="14", question_type="essay", max_score=5.0,
    )
    db.add(rival)
    await db.commit()
    rival_id = rival.id

    skeleton = _build_skeleton(slots=[{"sub_regions": [
        {"id": "essay-13", "name": "13", "score": 10, "rect": {"x1": 0, "y1": 0, "x2": 50, "y2": 50}},
        {"id": "essay-14", "name": "14", "score": 12, "rect": {"x1": 0, "y1": 50, "x2": 50, "y2": 100}},
        {"id": "essay-15", "name": "15", "score": 15, "rect": {"x1": 0, "y1": 100, "x2": 50, "y2": 150}},
    ]}])

    q_map = await upsert_questions_from_skeleton(
        db, subject_id=subject_id, school_id=school_id, skeleton=skeleton,
    )
    await db.commit()

    qs = (await db.execute(
        select(Question).where(Question.subject_id == subject_id).order_by(Question.name)
    )).scalars().all()
    names = [q.name for q in qs]
    assert names == ["13", "14", "15"], f"应有 3 题，实际 {names}"

    q14 = next(q for q in qs if q.name == "14")
    assert q14.id == rival_id, "'14' 应命中 rival existing 记录"
    assert q14.max_score == 12.0, f"existing update: max_score 应 12，实际 {q14.max_score}"

    assert set(q_map.keys()) == {"13", "14", "15"}
    assert q_map["14"] == rival_id


async def test_S6_publish_card_atomic_rollback_on_template_fail(db, empty_subject):
    """S6: publish_card_atomic 内 Template upsert 失败 → Question 和 exam.status 都回滚。"""
    from edu_cloud.modules.card.publish_service import publish_card_atomic
    from edu_cloud.modules.exam.models import Exam
    from edu_cloud.modules.card.models import Template

    async def fake_pdf(html, paper_size):
        return b"%PDF-fake"

    async def fake_extract(html):
        return {
            "image_width": 1587, "image_height": 1123, "anchors": [],
            "objective_groups": [],
            "slots": [{"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 10,
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ]}],
            "regions": [
                {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ],
        }

    async def boom(*args, **kwargs):
        raise RuntimeError("Template upsert simulation failure")

    with patch("edu_cloud.modules.card.publish_service.html_to_pdf", side_effect=fake_pdf), \
         patch("edu_cloud.modules.card.publish_service.extract_skeleton", side_effect=fake_extract), \
         patch("edu_cloud.modules.card.publish_service.upsert_template_both_sides", side_effect=boom):
        with pytest.raises(RuntimeError, match="Template upsert"):
            await publish_card_atomic(
                db,
                html="<html/>",
                subject_id=empty_subject["subject_id"],
                exam_id=empty_subject["exam_id"],
                school_id=empty_subject["school_id"],
                paper_size="A3",
            )

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 0, f"Question 应回滚，实际残留 {len(qs)} 条"

    exam = (await db.execute(select(Exam).where(Exam.id == empty_subject["exam_id"]))).scalar_one()
    assert exam.status == "draft", f"exam.status 应保持 draft，实际 {exam.status}"

    tpls = (await db.execute(select(Template).where(Template.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(tpls) == 0


async def test_S6b_publish_card_atomic_success_path(db, empty_subject):
    """S6b: publish_card_atomic 正常走完全链路 → PDF + Question + Template + exam.status=scanning。"""
    from edu_cloud.modules.card.publish_service import publish_card_atomic
    from edu_cloud.modules.exam.models import Exam
    from edu_cloud.modules.card.models import Template

    async def fake_pdf(html, paper_size):
        return b"%PDF-fake-success"

    async def fake_extract(html):
        return {
            "image_width": 1587, "image_height": 1123, "anchors": [],
            "objective_groups": [],
            "slots": [{"sub_regions": [
                {"id": "essay-13", "name": "13", "score": 10,
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ]}],
            "regions": [
                {"id": "essay-13", "type": "subjective", "qno": 13, "side": "A",
                 "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
            ],
        }

    with patch("edu_cloud.modules.card.publish_service.html_to_pdf", side_effect=fake_pdf), \
         patch("edu_cloud.modules.card.publish_service.extract_skeleton", side_effect=fake_extract):
        pdf_bytes = await publish_card_atomic(
            db,
            html="<html/>",
            subject_id=empty_subject["subject_id"],
            exam_id=empty_subject["exam_id"],
            school_id=empty_subject["school_id"],
            paper_size="A3",
        )

    assert pdf_bytes == b"%PDF-fake-success"

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 1
    assert qs[0].name == "13"

    tpls = (await db.execute(select(Template).where(Template.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(tpls) == 1 and tpls[0].side == "A"

    exam = (await db.execute(select(Exam).where(Exam.id == empty_subject["exam_id"]))).scalar_one()
    assert exam.status == "scanning"


async def test_publish_card_atomic_exam_not_found(db, empty_subject):
    """F003 失败路径：exam 不存在 → 404，无副作用。"""
    from edu_cloud.modules.card.publish_service import publish_card_atomic
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await publish_card_atomic(
            db, html="<html/>", subject_id=empty_subject["subject_id"],
            exam_id="nonexistent-exam-id", school_id=empty_subject["school_id"],
            paper_size="A3",
        )
    assert exc_info.value.status_code == 404

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 0


async def test_publish_card_atomic_subject_wrong_exam(db, empty_subject):
    """F003 失败路径：subject 不属于 exam → 400，无副作用。"""
    from edu_cloud.modules.card.publish_service import publish_card_atomic
    from edu_cloud.models.school import School
    from fastapi import HTTPException

    other_exam = Exam(name="Other", school_id=empty_subject["school_id"], status="draft")
    db.add(other_exam)
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await publish_card_atomic(
            db, html="<html/>", subject_id=empty_subject["subject_id"],
            exam_id=other_exam.id, school_id=empty_subject["school_id"],
            paper_size="A3",
        )
    assert exc_info.value.status_code == 400
    assert "不属于" in exc_info.value.detail

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 0, f"Question 应无副作用，实际残留 {len(qs)} 条"
    from edu_cloud.modules.card.models import Template
    tpls = (await db.execute(select(Template).where(Template.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(tpls) == 0, f"Template 应无副作用，实际残留 {len(tpls)} 条"


async def test_publish_card_atomic_exam_completed(db, empty_subject):
    """F003 失败路径：exam.status='completed' → 400，无副作用。"""
    from edu_cloud.modules.card.publish_service import publish_card_atomic
    from fastapi import HTTPException

    exam = (await db.execute(select(Exam).where(Exam.id == empty_subject["exam_id"]))).scalar_one()
    exam.status = "completed"
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await publish_card_atomic(
            db, html="<html/>", subject_id=empty_subject["subject_id"],
            exam_id=empty_subject["exam_id"], school_id=empty_subject["school_id"],
            paper_size="A3",
        )
    assert exc_info.value.status_code == 400
    assert "completed" in exc_info.value.detail

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 0, f"Question 应无副作用，实际残留 {len(qs)} 条"
    exam_after = (await db.execute(select(Exam).where(Exam.id == empty_subject["exam_id"]))).scalar_one()
    assert exam_after.status == "completed", f"exam.status 应保持 completed，实际 {exam_after.status}"


async def test_publish_card_atomic_empty_html(db, empty_subject):
    """F003 失败路径：HTML 为空 → 400，无副作用。"""
    from edu_cloud.modules.card.publish_service import publish_card_atomic
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await publish_card_atomic(
            db, html="   ", subject_id=empty_subject["subject_id"],
            exam_id=empty_subject["exam_id"], school_id=empty_subject["school_id"],
            paper_size="A3",
        )
    assert exc_info.value.status_code == 400

    qs = (await db.execute(select(Question).where(Question.subject_id == empty_subject["subject_id"]))).scalars().all()
    assert len(qs) == 0, f"Question 应无副作用，实际残留 {len(qs)} 条"
    exam_after = (await db.execute(select(Exam).where(Exam.id == empty_subject["exam_id"]))).scalar_one()
    assert exam_after.status == "draft", f"exam.status 应保持 draft，实际 {exam_after.status}"
