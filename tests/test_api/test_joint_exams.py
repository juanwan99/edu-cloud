import pytest


@pytest.fixture
async def exam_setup(client, admin_headers):
    """Create 2 schools + return their IDs for exam tests."""
    r1 = await client.post("/api/v1/schools", json={
        "name": "出题校", "code": "JE_CR", "district": "区1",
    }, headers=admin_headers)
    r2 = await client.post("/api/v1/schools", json={
        "name": "参与校", "code": "JE_PT", "district": "区1",
    }, headers=admin_headers)
    return {
        "creator_id": r1.json()["id"],
        "participant_id": r2.json()["id"],
        "creator_key": r1.json()["api_key"],
        "participant_key": r2.json()["api_key"],
    }


@pytest.mark.asyncio
async def test_create_joint_exam_api(client, admin_headers, exam_setup):
    setup = exam_setup
    resp = await client.post("/api/v1/joint-exams", json={
        "name": "春季联考",
        "subjects": [{"code": "YW", "name": "语文", "max_score": 150}],
        "creator_school_id": setup["creator_id"],
    }, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["creator_school_id"] == setup["creator_id"]


@pytest.mark.asyncio
async def test_add_participant_api(client, admin_headers, exam_setup):
    setup = exam_setup
    # Create exam
    er = await client.post("/api/v1/joint-exams", json={
        "name": "E", "subjects": [], "creator_school_id": setup["creator_id"],
    }, headers=admin_headers)
    exam_id = er.json()["id"]
    # Add participant
    resp = await client.post(
        f"/api/v1/joint-exams/{exam_id}/participants",
        json={"school_id": setup["participant_id"]},
        headers=admin_headers,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_distribute_api(client, admin_headers, exam_setup):
    setup = exam_setup
    er = await client.post("/api/v1/joint-exams", json={
        "name": "E",
        "subjects": [{"code": "YW", "name": "语文", "max_score": 150}],
        "creator_school_id": setup["creator_id"],
    }, headers=admin_headers)
    exam_id = er.json()["id"]
    # Upload template via sync endpoint (as creator school)
    import io
    resp = await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{"regions": []}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf"),
    }, data={
        "joint_exam_id": exam_id,
        "subject_code": "YW",
        "answer_schema": '[{"id": "q1", "max_score": 10}]',
    }, headers={"X-API-Key": setup["creator_key"]})
    assert resp.status_code == 200
    # Distribute
    resp = await client.post(
        f"/api/v1/joint-exams/{exam_id}/distribute", headers=admin_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_exams_api(client, admin_headers, exam_setup):
    setup = exam_setup
    await client.post("/api/v1/joint-exams", json={
        "name": "列表测试", "subjects": [], "creator_school_id": setup["creator_id"],
    }, headers=admin_headers)
    resp = await client.get("/api/v1/joint-exams", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_exam_detail_api(client, admin_headers, exam_setup):
    setup = exam_setup
    er = await client.post("/api/v1/joint-exams", json={
        "name": "详情测试", "subjects": [], "creator_school_id": setup["creator_id"],
    }, headers=admin_headers)
    exam_id = er.json()["id"]
    resp = await client.get(f"/api/v1/joint-exams/{exam_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "详情测试"
    assert "participants" in resp.json()
