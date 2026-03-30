"""题库 + 错题本 API 端点测试。"""
import pytest


@pytest.mark.asyncio
async def test_list_bank_questions(client, admin_headers):
    """GET /bank/questions 返回列表。"""
    resp = await client.get("/api/v1/bank/questions", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_bank_question_not_found(client, admin_headers):
    """GET /bank/questions/{id} 不存在返回 404。"""
    resp = await client.get("/api/v1/bank/questions/nonexistent", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_error_book(client, admin_headers, seed_exam_with_results):
    """GET /bank/error-book/{student_id} 返回列表。"""
    resp = await client.get(
        f"/api/v1/bank/error-book/{seed_exam_with_results['student_ids'][0]}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_error_book_stats(client, admin_headers, seed_exam_with_results):
    """GET /bank/error-book/{student_id}/stats 返回统计。"""
    resp = await client.get(
        f"/api/v1/bank/error-book/{seed_exam_with_results['student_ids'][0]}/stats",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "unmastered" in data


@pytest.mark.asyncio
async def test_bank_requires_auth(client):
    """无 JWT 返回 403。"""
    resp = await client.get("/api/v1/bank/questions")
    assert resp.status_code == 403
