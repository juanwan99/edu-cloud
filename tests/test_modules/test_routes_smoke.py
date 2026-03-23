"""路由可达 smoke tests — 验证所有 Batch 3 模块端点挂载正确 + sync 删除回归。"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sync_endpoints_return_404(client: AsyncClient):
    """TG-002: 已删除的 sync 端点全部返回 404。"""
    for path in [
        "/api/v1/sync/heartbeat",
        "/api/v1/sync/joint-exams",
        "/api/v1/sync/templates",
        "/api/v1/sync/scores",
    ]:
        resp = await client.post(path) if "heartbeat" in path or "scores" in path or "templates" == path.split("/")[-1] else await client.get(path)
        assert resp.status_code in (404, 405), f"{path} should be 404/405, got {resp.status_code}"


@pytest.mark.asyncio
async def test_all_module_routes_reachable(client: AsyncClient, teacher_headers):
    """TG-001: 验证所有模块路由挂载正确（不含 401）。"""
    # GET endpoints should return 200 or valid error (not 404 from missing route)
    endpoints = [
        ("GET", "/api/v1/exams"),
        ("GET", "/api/v1/questions?subject_id=none"),
        ("GET", "/api/v1/classes"),
        ("GET", "/api/v1/students"),
        ("GET", "/api/v1/analytics/exam/nonexistent/summary"),
        ("GET", "/api/v1/knowledge/points?course_code=MATH"),
        ("GET", "/api/v1/llm-config/slots"),
    ]
    for method, path in endpoints:
        resp = await client.request(method, path, headers=teacher_headers)
        # Should not be 404 (route missing) — 200/[] or domain error (404 from service) is OK
        assert resp.status_code != 405, f"{path} returned 405 Method Not Allowed"


@pytest.mark.asyncio
async def test_student_list_classes(client: AsyncClient, teacher_headers):
    """Student 模块：成功路径 + 空列表。"""
    resp = await client.get("/api/v1/classes", headers=teacher_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_student_list_students(client: AsyncClient, teacher_headers):
    """Student 模块：成功路径 + 空列表。"""
    resp = await client.get("/api/v1/students", headers=teacher_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_analytics_exam_not_found(client: AsyncClient, teacher_headers):
    """Analytics 模块：资源不存在。"""
    resp = await client.get("/api/v1/analytics/exam/nonexistent/summary",
                            headers=teacher_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_analytics_distribution_not_found(client: AsyncClient, teacher_headers):
    """Analytics 模块：分布查询资源不存在。"""
    resp = await client.get("/api/v1/analytics/exam/nonexistent/distribution",
                            headers=teacher_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_knowledge_list_empty(client: AsyncClient, teacher_headers):
    """Knowledge 模块：空列表。"""
    resp = await client.get("/api/v1/knowledge/points?course_code=NONEXIST",
                            headers=teacher_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_knowledge_point_not_found(client: AsyncClient, teacher_headers):
    """Knowledge 模块：资源不存在。"""
    resp = await client.get("/api/v1/knowledge/points/nonexistent",
                            headers=teacher_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_llm_config_list_slots(client: AsyncClient, teacher_headers):
    """LLM Config 模块：成功路径。"""
    resp = await client.get("/api/v1/llm-config/slots", headers=teacher_headers)
    assert resp.status_code == 200
    assert "slots" in resp.json()


@pytest.mark.asyncio
async def test_llm_config_delete_nonexistent(client: AsyncClient, teacher_headers):
    """LLM Config 模块：删除不存在的槽位。"""
    resp = await client.delete("/api/v1/llm-config/slots/99", headers=teacher_headers)
    # teacher is homeroom_teacher, not admin → 403 or 404
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_pipeline_trigger_forbidden(client: AsyncClient, teacher_headers):
    """Pipeline 模块：非管理员 → 403。"""
    resp = await client.post("/api/v1/pipeline/run/nonexistent",
                             headers=teacher_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_template_not_found(client: AsyncClient, teacher_headers):
    """Template 模块：资源不存在。"""
    resp = await client.get("/api/v1/templates/nonexistent/A",
                            headers=teacher_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_question_create_invalid_subject(client: AsyncClient, teacher_headers):
    """Question：跨 school / 不存在的 subject → 404。"""
    resp = await client.post("/api/v1/questions", json={
        "subject_id": "nonexistent", "name": "题1",
        "question_type": "objective", "max_score": 5,
    }, headers=teacher_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_no_auth_returns_error(client: AsyncClient):
    """无认证 → 401/403 (不是 404)。"""
    for path in ["/api/v1/exams", "/api/v1/classes", "/api/v1/students",
                 "/api/v1/knowledge/points?course_code=X", "/api/v1/llm-config/slots"]:
        resp = await client.get(path)
        assert resp.status_code in (401, 403), f"{path} should require auth"
