import pytest
import io


@pytest.fixture
async def results_setup(client, admin_headers):
    """Full setup: 2 schools + exam + template + distributed + scores submitted."""
    r1 = await client.post("/api/v1/schools", json={
        "name": "排名出题校", "code": "RK_CR", "district": "X",
    }, headers=admin_headers)
    r2 = await client.post("/api/v1/schools", json={
        "name": "排名参与校", "code": "RK_PT", "district": "X",
    }, headers=admin_headers)
    s1_key = r1.json()["api_key"]
    s2_key = r2.json()["api_key"]

    er = await client.post("/api/v1/joint-exams", json={
        "name": "排名测试联考",
        "subjects": [{"code": "YW", "name": "语文", "max_score": 150}],
        "creator_school_id": r1.json()["id"],
    }, headers=admin_headers)
    exam_id = er.json()["id"]

    # Add participant
    await client.post(f"/api/v1/joint-exams/{exam_id}/participants",
        json={"school_id": r2.json()["id"]}, headers=admin_headers)

    # Upload template + distribute
    await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF"), "application/pdf"),
    }, data={
        "joint_exam_id": exam_id, "subject_code": "YW",
        "answer_schema": '[]',
    }, headers={"X-API-Key": s1_key})
    await client.post(f"/api/v1/joint-exams/{exam_id}/distribute", headers=admin_headers)

    # Upload scores from both schools
    for key, prefix in [(s1_key, "S1"), (s2_key, "S2")]:
        students = [
            {"student_name": f"{prefix}_学生{i}", "student_number": f"{prefix}_{i:03d}",
             "total_score": 60 + i * 10, "detail_scores": []}
            for i in range(1, 4)
        ]
        await client.post("/api/v1/sync/scores", json={
            "joint_exam_id": exam_id, "subject_code": "YW",
            "student_results": students,
        }, headers={"X-API-Key": key})

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
    assert len(rankings) == 6  # 3 students × 2 schools
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
