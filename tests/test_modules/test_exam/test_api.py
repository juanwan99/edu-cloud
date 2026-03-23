"""Exam/Question 路由 API 测试 — 多租户隔离验证。"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_exams(client: AsyncClient, teacher_headers):
    """成功路径：创建考试 + 列表查询。"""
    resp = await client.post("/api/v1/exams", json={"name": "期中考", "card_title": "CT"},
                             headers=teacher_headers)
    assert resp.status_code == 201
    exam_id = resp.json()["id"]
    assert resp.json()["name"] == "期中考"

    resp = await client.get("/api/v1/exams", headers=teacher_headers)
    assert resp.status_code == 200
    assert any(e["id"] == exam_id for e in resp.json())


@pytest.mark.asyncio
async def test_get_exam_not_found(client: AsyncClient, teacher_headers):
    """资源不存在 → 404。"""
    resp = await client.get("/api/v1/exams/nonexistent", headers=teacher_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_school_isolation(client: AsyncClient, teacher_headers, admin_headers):
    """跨 school 越权隔离：teacher 创建的考试 admin（无 school_id）看不到。"""
    resp = await client.post("/api/v1/exams", json={"name": "隔离测试", "card_title": "IS"},
                             headers=teacher_headers)
    assert resp.status_code == 201

    # admin (platform_admin, school_id=None) should not see it
    resp = await client.get("/api/v1/exams", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_create_subject_and_list(client: AsyncClient, teacher_headers):
    """创建科目 + 列表。"""
    resp = await client.post("/api/v1/exams", json={"name": "科目测试", "card_title": "ST"},
                             headers=teacher_headers)
    exam_id = resp.json()["id"]
    resp = await client.post(f"/api/v1/exams/{exam_id}/subjects",
                             json={"name": "语文", "code": "YW"}, headers=teacher_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "语文"

    resp = await client.get(f"/api/v1/exams/{exam_id}/subjects", headers=teacher_headers)
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_question_crud(client: AsyncClient, teacher_headers):
    """题目 CRUD 完整流程。"""
    resp = await client.post("/api/v1/exams", json={"name": "题目测试", "card_title": "QT"},
                             headers=teacher_headers)
    exam_id = resp.json()["id"]
    resp = await client.post(f"/api/v1/exams/{exam_id}/subjects",
                             json={"name": "数学", "code": "SX"}, headers=teacher_headers)
    subject_id = resp.json()["id"]

    resp = await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "题1", "question_type": "objective", "max_score": 5,
    }, headers=teacher_headers)
    assert resp.status_code == 201
    qid = resp.json()["id"]

    resp = await client.get(f"/api/v1/questions?subject_id={subject_id}", headers=teacher_headers)
    assert len(resp.json()) == 1

    resp = await client.patch(f"/api/v1/questions/{qid}", json={"max_score": 10},
                              headers=teacher_headers)
    assert resp.json()["max_score"] == 10

    resp = await client.delete(f"/api/v1/questions/{qid}", headers=teacher_headers)
    assert resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_no_auth_returns_401(client: AsyncClient):
    """无 JWT → 401/403。"""
    resp = await client.get("/api/v1/exams")
    assert resp.status_code in (401, 403)
