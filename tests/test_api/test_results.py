import pytest

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def results_setup(client, admin_headers, db):
    """Full setup: 2 schools + exam + distributed + scores — via direct DB."""
    from edu_cloud.models.joint_exam import JointExam, JointExamParticipant, JointExamStudentResult

    r1 = await client.post("/api/v1/schools", json={
        "name": "排名出题校", "code": "RK_CR", "district": "X",
    }, headers=admin_headers)
    r2 = await client.post("/api/v1/schools", json={
        "name": "排名参与校", "code": "RK_PT", "district": "X",
    }, headers=admin_headers)
    s1_id = r1.json()["id"]
    s2_id = r2.json()["id"]

    user = User(username="rk_director", display_name="排名主任")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(
        user_id=user.id, role="academic_director",
        school_id=s1_id, is_primary=True,
    )
    db.add(role)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": user.id, "active_role_id": role.id})
    director_headers = {"Authorization": f"Bearer {token}"}

    er = await client.post("/api/v1/joint-exams", json={
        "name": "排名测试联考",
        "subjects": [{"code": "YW", "name": "语文", "max_score": 150}],
    }, headers=director_headers)
    exam_id = er.json()["id"]

    await client.post(f"/api/v1/joint-exams/{exam_id}/participants",
        json={"school_id": s2_id}, headers=admin_headers)

    # 直接设置 template_uploaded + distribute
    from sqlalchemy import select
    je = (await db.execute(select(JointExam).where(JointExam.id == exam_id))).scalar_one()
    je.subjects = [{"code": "YW", "name": "语文", "max_score": 150, "template_uploaded": True}]
    await db.commit()
    await client.post(f"/api/v1/joint-exams/{exam_id}/distribute", headers=admin_headers)

    # 直接插入成绩
    for school_id, prefix in [(s1_id, "S1"), (s2_id, "S2")]:
        for i in range(1, 4):
            db.add(JointExamStudentResult(
                joint_exam_id=exam_id, school_id=school_id, subject_code="YW",
                student_name=f"{prefix}_学生{i}", student_number=f"{prefix}_{i:03d}",
                total_score=60 + i * 10, detail_scores=[],
            ))
    await db.commit()

    return {"exam_id": exam_id}


@pytest.mark.asyncio
async def test_rankings_api(client, admin_headers, results_setup):
    s = results_setup
    resp = await client.get(
        f"/api/v1/joint-exams/{s['exam_id']}/results?subject_code=YW",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    rankings = resp.json()
    assert len(rankings) == 6
    scores = [r["total_score"] for r in rankings]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_school_comparison_api(client, admin_headers, results_setup):
    s = results_setup
    resp = await client.get(
        f"/api/v1/joint-exams/{s['exam_id']}/results/by-school",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    comparison = resp.json()
    assert len(comparison) == 2
    for entry in comparison:
        assert "avg_score" in entry
        assert "median_score" in entry


@pytest.mark.asyncio
async def test_student_detail_api(client, admin_headers, results_setup):
    s = results_setup
    resp = await client.get(
        f"/api/v1/joint-exams/{s['exam_id']}/results/students/S1_001",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["student_name"] == "S1_学生1"
    assert len(detail["subjects"]) == 1
