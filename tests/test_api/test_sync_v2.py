import pytest
import io


@pytest.fixture
async def sync_setup(client, admin_headers):
    """Full setup: 2 schools + exam + participant added."""
    r1 = await client.post("/api/v1/schools", json={
        "name": "出题校", "code": "SY_CR", "district": "X",
    }, headers=admin_headers)
    r2 = await client.post("/api/v1/schools", json={
        "name": "参与校", "code": "SY_PT", "district": "X",
    }, headers=admin_headers)
    creator_key = r1.json()["api_key"]
    participant_key = r2.json()["api_key"]

    er = await client.post("/api/v1/joint-exams", json={
        "name": "同步测试联考",
        "subjects": [{"code": "YW", "name": "语文", "max_score": 150}],
        "creator_school_id": r1.json()["id"],
    }, headers=admin_headers)
    exam_id = er.json()["id"]

    # Add participant
    await client.post(f"/api/v1/joint-exams/{exam_id}/participants",
        json={"school_id": r2.json()["id"]}, headers=admin_headers)

    return {
        "exam_id": exam_id, "creator_key": creator_key,
        "participant_key": participant_key,
        "creator_id": r1.json()["id"], "participant_id": r2.json()["id"],
    }


@pytest.mark.asyncio
async def test_upload_template_sync(client, sync_setup):
    s = sync_setup
    resp = await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{"regions": []}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf"),
    }, data={
        "joint_exam_id": s["exam_id"],
        "subject_code": "YW",
        "answer_schema": '[{"id": "q1", "max_score": 10}]',
    }, headers={"X-API-Key": s["creator_key"]})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pull_exams_with_template_url(client, admin_headers, sync_setup):
    s = sync_setup
    # Upload + distribute first
    await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF"), "application/pdf"),
    }, data={
        "joint_exam_id": s["exam_id"], "subject_code": "YW",
        "answer_schema": '[{"id": "q1", "max_score": 10}]',
    }, headers={"X-API-Key": s["creator_key"]})
    await client.post(f"/api/v1/joint-exams/{s['exam_id']}/distribute", headers=admin_headers)

    # Pull as participant
    resp = await client.get("/api/v1/sync/joint-exams",
        headers={"X-API-Key": s["participant_key"]})
    assert resp.status_code == 200
    exams = resp.json()["joint_exams"]
    assert len(exams) >= 1
    subj = exams[0]["subjects"][0]
    assert "template_url" in subj
    assert "/sync/templates/" in subj["template_url"]


@pytest.mark.asyncio
async def test_upload_scores_detail(client, admin_headers, sync_setup):
    s = sync_setup
    # Setup: upload template + distribute
    await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF"), "application/pdf"),
    }, data={
        "joint_exam_id": s["exam_id"], "subject_code": "YW",
        "answer_schema": '[]',
    }, headers={"X-API-Key": s["creator_key"]})
    await client.post(f"/api/v1/joint-exams/{s['exam_id']}/distribute", headers=admin_headers)

    # Upload scores with detail
    resp = await client.post("/api/v1/sync/scores", json={
        "joint_exam_id": s["exam_id"],
        "subject_code": "YW",
        "student_results": [
            {"student_name": "张三", "student_number": "001", "total_score": 85,
             "detail_scores": [{"question_id": "q1", "score": 8, "max_score": 10}]},
        ],
    }, headers={"X-API-Key": s["creator_key"]})
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.asyncio
async def test_non_creator_cannot_upload_template(client, admin_headers, sync_setup):
    """非出题校不能上传模板 → 403。"""
    s = sync_setup
    # participant_key is NOT the creator → 403
    resp = await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF"), "application/pdf"),
    }, data={
        "joint_exam_id": s["exam_id"], "subject_code": "YW",
        "answer_schema": '[]',
    }, headers={"X-API-Key": s["participant_key"]})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_participant_cannot_download_template(client, admin_headers, sync_setup):
    """非参与校不能下载模板 → 403。"""
    s = sync_setup
    # Upload template first (as creator)
    await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF"), "application/pdf"),
    }, data={
        "joint_exam_id": s["exam_id"], "subject_code": "YW",
        "answer_schema": '[]',
    }, headers={"X-API-Key": s["creator_key"]})

    # Create outsider school
    r3 = await client.post("/api/v1/schools", json={
        "name": "局外校DL", "code": "SY_DL", "district": "X",
    }, headers=admin_headers)
    outsider_key = r3.json()["api_key"]

    # Outsider tries to download → 403
    resp = await client.get(
        f"/api/v1/sync/templates/{s['exam_id']}/YW",
        headers={"X-API-Key": outsider_key},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_participant_scores_rejected(client, admin_headers, sync_setup):
    """非参与校调用 /sync/scores 应返回 403。"""
    s = sync_setup
    # Create a third school that is NOT a participant
    r3 = await client.post("/api/v1/schools", json={
        "name": "局外校", "code": "SY_OUT", "district": "X",
    }, headers=admin_headers)
    outsider_key = r3.json()["api_key"]

    # Upload template + distribute
    await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF"), "application/pdf"),
    }, data={
        "joint_exam_id": s["exam_id"], "subject_code": "YW",
        "answer_schema": '[]',
    }, headers={"X-API-Key": s["creator_key"]})
    await client.post(f"/api/v1/joint-exams/{s['exam_id']}/distribute", headers=admin_headers)

    # Non-participant tries to upload scores → 403
    resp = await client.post("/api/v1/sync/scores", json={
        "joint_exam_id": s["exam_id"],
        "subject_code": "YW",
        "student_results": [
            {"student_name": "X", "student_number": "001", "total_score": 50, "detail_scores": []},
        ],
    }, headers={"X-API-Key": outsider_key})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_inactive_school_rejected(client, admin_headers, sync_setup):
    """已停用学校的 API Key 应返回 401。"""
    s = sync_setup
    # Deactivate creator school
    await client.patch(f"/api/v1/schools/{s['creator_id']}",
        json={"is_active": False}, headers=admin_headers)
    # Try sync
    resp = await client.post("/api/v1/sync/heartbeat",
        json={"client_version": "1.0", "exam_ai_port": 8000},
        headers={"X-API-Key": s["creator_key"]})
    assert resp.status_code == 401
