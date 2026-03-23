"""路由可达 smoke tests — 验证所有 Batch 3 模块端点挂载正确 + sync 删除回归。"""
import pytest
from httpx import AsyncClient


# ── TG-002: sync 删除回归 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_heartbeat_deleted(client: AsyncClient):
    """POST /api/v1/sync/heartbeat → 严格 404。"""
    resp = await client.post("/api/v1/sync/heartbeat", json={})
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_sync_joint_exams_deleted(client: AsyncClient):
    """GET /api/v1/sync/joint-exams → 严格 404。"""
    resp = await client.get("/api/v1/sync/joint-exams")
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_sync_templates_deleted(client: AsyncClient):
    """POST /api/v1/sync/templates → 严格 404。"""
    resp = await client.post("/api/v1/sync/templates")
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_sync_scores_deleted(client: AsyncClient):
    """POST /api/v1/sync/scores → 严格 404。"""
    resp = await client.post("/api/v1/sync/scores", json={})
    assert resp.status_code == 404


# ── Student 模块 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_student_list_classes(client: AsyncClient, teacher_headers):
    resp = await client.get("/api/v1/classes", headers=teacher_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_student_list_students(client: AsyncClient, teacher_headers):
    resp = await client.get("/api/v1/students", headers=teacher_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_student_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/classes")
    assert resp.status_code in (401, 403)


# ── Card 模块 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_card_skeleton_list(client: AsyncClient, teacher_headers):
    """Card: 骨架列表 — 成功路径（空列表）。"""
    resp = await client.get("/api/v1/card/skeleton/list", headers=teacher_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_card_skeleton_not_found(client: AsyncClient, teacher_headers):
    """Card: 不存在的骨架 → 404。"""
    resp = await client.get("/api/v1/card/skeleton/NONEXIST", headers=teacher_headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_card_builtin_templates(client: AsyncClient, teacher_headers):
    """Card: 内置模板列表。"""
    resp = await client.get("/api/v1/card/templates/builtin", headers=teacher_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_card_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/card/skeleton/list")
    assert resp.status_code in (401, 403)


# ── Template 模块 ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_template_not_found(client: AsyncClient, teacher_headers):
    resp = await client.get("/api/v1/templates/nonexistent/A", headers=teacher_headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_template_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/templates/any/A")
    assert resp.status_code in (401, 403)


# ── Scan 模块 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_get_task_not_found(client: AsyncClient, teacher_headers):
    """Scan: 不存在的扫描任务 → 404。"""
    resp = await client.get("/api/v1/scan/tasks/nonexistent", headers=teacher_headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_scan_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/scan/tasks/any")
    assert resp.status_code in (401, 403)


# ── Grading 模块 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_grading_list_tasks(client: AsyncClient, teacher_headers):
    """Grading: 任务列表 — 成功路径（空列表）。"""
    resp = await client.get("/api/v1/grading/tasks", headers=teacher_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_grading_rubric_not_found(client: AsyncClient, teacher_headers):
    """Grading: 不存在的评分规则 → 404。"""
    resp = await client.get("/api/v1/grading/rubrics/nonexistent", headers=teacher_headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_grading_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/grading/tasks")
    assert resp.status_code in (401, 403)


# ── Marking 模块 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_marking_assignments(client: AsyncClient, teacher_headers):
    """Marking: 我的任务 — 成功路径（空列表）。"""
    resp = await client.get("/api/v1/marking/my-assignments", headers=teacher_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_marking_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/marking/my-assignments")
    assert resp.status_code in (401, 403)


# ── Analytics 模块 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_summary_not_found(client: AsyncClient, teacher_headers):
    resp = await client.get("/api/v1/analytics/exam/nonexistent/summary", headers=teacher_headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_analytics_distribution_not_found(client: AsyncClient, teacher_headers):
    resp = await client.get("/api/v1/analytics/exam/nonexistent/distribution", headers=teacher_headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_analytics_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/analytics/exam/x/summary")
    assert resp.status_code in (401, 403)


# ── Knowledge 模块 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_knowledge_list_empty(client: AsyncClient, teacher_headers):
    resp = await client.get("/api/v1/knowledge/points?course_code=NONEXIST", headers=teacher_headers)
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_knowledge_point_not_found(client: AsyncClient, teacher_headers):
    resp = await client.get("/api/v1/knowledge/points/nonexistent", headers=teacher_headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_knowledge_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/knowledge/points?course_code=X")
    assert resp.status_code in (401, 403)


# ── Pipeline 模块 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_trigger_forbidden(client: AsyncClient, teacher_headers):
    """Pipeline: 非管理员 → 403。"""
    resp = await client.post("/api/v1/pipeline/run/nonexistent", headers=teacher_headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_pipeline_no_auth(client: AsyncClient):
    resp = await client.post("/api/v1/pipeline/run/any")
    assert resp.status_code in (401, 403)


# ── LLM Config 模块 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_config_list_slots(client: AsyncClient, teacher_headers):
    resp = await client.get("/api/v1/llm-config/slots", headers=teacher_headers)
    assert resp.status_code == 200
    assert "slots" in resp.json()

@pytest.mark.asyncio
async def test_llm_config_delete_nonexistent(client: AsyncClient, teacher_headers):
    """LLM Config: homeroom_teacher → 403（非管理员）。"""
    resp = await client.delete("/api/v1/llm-config/slots/99", headers=teacher_headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_llm_config_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/llm-config/slots")
    assert resp.status_code in (401, 403)


# ── Question 模块 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_question_create_invalid_subject(client: AsyncClient, teacher_headers):
    resp = await client.post("/api/v1/questions", json={
        "subject_id": "nonexistent", "name": "题1",
        "question_type": "objective", "max_score": 5,
    }, headers=teacher_headers)
    assert resp.status_code == 404
