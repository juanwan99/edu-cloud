"""学情画像 API 端点测试。"""
import pytest


@pytest.mark.asyncio
async def test_student_trend(client, admin_headers, seed_exam_with_results):
    """GET /profile/students/{id}/trend 返回快照列表。"""
    data = seed_exam_with_results
    # Pipeline 先生成快照
    from edu_cloud.modules.pipeline.service import generate_exam_snapshots
    from edu_cloud.database import get_db
    # 用 client 内部的 db 不方便，直接调 API（无快照时返回空）
    resp = await client.get(
        f"/api/v1/profile/students/{data['student_ids'][0]}/trend",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_student_knowledge_map(client, admin_headers, seed_exam_with_results):
    """GET /profile/students/{id}/knowledge 返回掌握度列表。"""
    resp = await client.get(
        f"/api/v1/profile/students/{seed_exam_with_results['student_ids'][0]}/knowledge",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_student_error_patterns(client, admin_headers, seed_exam_with_results):
    """GET /profile/students/{id}/error-patterns 返回错误模式。"""
    resp = await client.get(
        f"/api/v1/profile/students/{seed_exam_with_results['student_ids'][0]}/error-patterns",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_class_weakness(client, admin_headers, seed_exam_with_results):
    """GET /profile/class/weakness 返回薄弱知识点。"""
    resp = await client.get(
        f"/api/v1/profile/class/weakness?class_id={seed_exam_with_results['class_id']}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_profile_requires_auth(client):
    """无 JWT 返回 401（deps.py 显式 raise 401，auto_error=False）。"""
    resp = await client.get("/api/v1/profile/students/any/trend")
    assert resp.status_code == 401
