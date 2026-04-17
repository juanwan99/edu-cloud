"""F003 Question 写入责任链 — integration tests for /api/v1/card/publish."""
import pytest


@pytest.fixture
def minimal_html_with_data_side():
    """构造含 data-side="A" 和 data-side="B" 的 .page DOM 的 HTML。"""
    return """<!DOCTYPE html>
<html><body>
  <div class="page" data-paper="A3" data-side="A" id="pageA">
    <div data-region-id="essay-Q12" data-region-type="subjective" data-qno="12">Q12</div>
  </div>
  <div class="page" data-paper="A3" data-side="B" id="pageB">
    <div data-region-id="essay-Q17" data-region-type="subjective" data-qno="17">Q17</div>
  </div>
</body></html>"""


@pytest.mark.asyncio
async def test_extract_skeleton_preserves_data_side(minimal_html_with_data_side):
    """Slice A2: extract_skeleton 的 JS eval 必须正确读取 data-side 并写入 skeleton.regions[].side。

    反例：render.js 未修时 closest('[data-side]') 返回 null，所有 region side fallback 'A'。
    本测试构造 B 面 region 并断言 side='B'。
    """
    from edu_cloud.modules.card.export.html_export import extract_skeleton

    skeleton = await extract_skeleton(minimal_html_with_data_side)

    regions = skeleton.get("regions", [])
    assert len(regions) == 2, f"应有 2 个 region，实际 {len(regions)}"

    by_id = {r["id"]: r for r in regions}
    assert "essay-Q12" in by_id and by_id["essay-Q12"]["side"] == "A"
    assert "essay-Q17" in by_id and by_id["essay-Q17"]["side"] == "B", (
        f"Q17 应在 B 面，实际 side={by_id.get('essay-Q17', {}).get('side')}"
    )


from unittest.mock import patch
from sqlalchemy import select


async def test_publish_endpoint_integration(client, db):
    """Slice F: POST /api/v1/card/publish 端到端（mock PDF/skeleton，验证 router 接入）。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.exam.models import Exam, Subject, Question
    from edu_cloud.modules.card.models import Template
    from edu_cloud.shared.auth import create_access_token

    school = School(name="FInt", code="FINT01")
    db.add(school)
    await db.commit()
    user = User(username="f_int", display_name="F")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="F考试", school_id=school.id, status="draft")
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject)
    await db.commit()
    subject_id = subject.id
    exam_id = exam.id

    async def fake_pdf(html, paper_size):
        return b"%PDF-F-integration"

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
        resp = await client.post(
            "/api/v1/card/publish",
            json={"html": "<html/>", "subject_id": subject_id, "exam_id": exam_id, "paper_size": "A3"},
            headers=headers,
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    db.expire_all()
    qs = (await db.execute(select(Question).where(Question.subject_id == subject_id))).scalars().all()
    assert len(qs) == 1

    tpls = (await db.execute(select(Template).where(Template.subject_id == subject_id))).scalars().all()
    assert len(tpls) == 1 and tpls[0].side == "A"

    exam_r = (await db.execute(select(Exam).where(Exam.id == exam_id))).scalar_one()
    assert exam_r.status == "scanning"
