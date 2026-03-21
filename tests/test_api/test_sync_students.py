"""学生/成绩同步端点集成测试 — TDD."""
import pytest


@pytest.mark.asyncio
async def test_sync_students(client, school_api_headers):
    resp = await client.post("/api/v1/sync/students", json={
        "students": [
            {"name": "张三", "student_number": "S001", "class_name": "七年级2班", "grade": "七年级", "gender": "男"},
            {"name": "李四", "student_number": "S002", "class_name": "七年级2班", "grade": "七年级", "gender": "女"},
        ]
    }, headers=school_api_headers)
    assert resp.status_code == 200
    assert resp.json()["synced_count"] == 2


@pytest.mark.asyncio
async def test_sync_students_upsert(client, school_api_headers):
    """二次同步同一学号应更新而非报错。"""
    payload = {"students": [{"name": "张三", "student_number": "S001", "grade": "七年级"}]}
    resp1 = await client.post("/api/v1/sync/students", json=payload, headers=school_api_headers)
    assert resp1.status_code == 200

    payload2 = {"students": [{"name": "张三新", "student_number": "S001", "grade": "七年级"}]}
    resp2 = await client.post("/api/v1/sync/students", json=payload2, headers=school_api_headers)
    assert resp2.status_code == 200
    assert resp2.json()["synced_count"] == 1


@pytest.mark.asyncio
async def test_sync_exam_results(client, school_api_headers):
    # First sync students
    await client.post("/api/v1/sync/students", json={
        "students": [{"name": "张三", "student_number": "S001", "class_name": "七年级2班", "grade": "七年级"}]
    }, headers=school_api_headers)

    resp = await client.post("/api/v1/sync/exam-results", json={
        "exam": {"name": "期中考试", "subject_code": "SX", "subject_name": "数学", "max_score": 150, "semester": "2025-2026-2"},
        "results": [
            {"student_number": "S001", "total_score": 135.0}
        ]
    }, headers=school_api_headers)
    assert resp.status_code == 200
    assert resp.json()["synced_count"] == 1


@pytest.mark.asyncio
async def test_sync_exam_results_unknown_student_skipped(client, school_api_headers):
    """未知学号的成绩应被跳过而非报错。"""
    resp = await client.post("/api/v1/sync/exam-results", json={
        "exam": {"name": "期末考试", "subject_code": "YW", "subject_name": "语文", "max_score": 150},
        "results": [
            {"student_number": "UNKNOWN_999", "total_score": 100.0}
        ]
    }, headers=school_api_headers)
    assert resp.status_code == 200
    assert resp.json()["synced_count"] == 0


@pytest.mark.asyncio
async def test_sync_exam_results_upsert(client, school_api_headers):
    """同一考试同一学生二次上报应更新成绩。"""
    await client.post("/api/v1/sync/students", json={
        "students": [{"name": "张三", "student_number": "S001", "grade": "七年级"}]
    }, headers=school_api_headers)

    exam_payload = {
        "exam": {"name": "期中考试", "subject_code": "SX"},
        "results": [{"student_number": "S001", "total_score": 120.0}],
    }
    resp1 = await client.post("/api/v1/sync/exam-results", json=exam_payload, headers=school_api_headers)
    assert resp1.status_code == 200

    exam_payload2 = {
        "exam": {"name": "期中考试", "subject_code": "SX"},
        "results": [{"student_number": "S001", "total_score": 135.0}],
    }
    resp2 = await client.post("/api/v1/sync/exam-results", json=exam_payload2, headers=school_api_headers)
    assert resp2.status_code == 200
    assert resp2.json()["synced_count"] == 1


@pytest.mark.asyncio
async def test_sync_students_requires_auth(client):
    """无 API Key 应返回 422（缺少必填 header）。"""
    resp = await client.post("/api/v1/sync/students", json={"students": []})
    assert resp.status_code == 422
