"""H4: Pipeline progress/stop school_id isolation tests.

Verifies that:
- School B cannot stop School A's pipeline (403)
- School B sees idle progress when School A's pipeline is running
- School A can stop its own pipeline
- enqueue_pipeline records school_id into _pipeline_school_id
"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def pipeline_schools(db):
    s1 = School(name="扫描校A", code="PA", district="D", api_key_hash="x")
    s2 = School(name="扫描校B", code="PB", district="D", api_key_hash="x")
    db.add_all([s1, s2])
    await db.flush()

    users = {}
    for label, school in [("a", s1), ("b", s2)]:
        u = User(username=f"pipe_{label}", display_name=label.upper())
        u.set_password("test123")
        db.add(u)
        await db.flush()
        db.add(UserRole(user_id=u.id, role="academic_director",
                        school_id=school.id, is_primary=True))
        token = create_access_token({
            "sub": u.id, "role": "academic_director", "school_id": school.id,
        })
        users[label] = {"headers": {"Authorization": f"Bearer {token}"}, "school_id": school.id}
    await db.commit()
    return users


@pytest.mark.asyncio
async def test_stop_rejects_other_school(client, pipeline_schools):
    """B校用户不能停止 A校的 pipeline。"""
    from edu_cloud.modules.scan import pipeline_service
    pipeline_service._running = True
    pipeline_service._pipeline_school_id = pipeline_schools["a"]["school_id"]
    try:
        resp = await client.post(
            "/api/v1/scan/pipeline/stop",
            headers=pipeline_schools["b"]["headers"],
        )
        assert resp.status_code == 403
    finally:
        pipeline_service._running = False
        pipeline_service._pipeline_school_id = None


@pytest.mark.asyncio
async def test_progress_returns_empty_for_other_school(client, pipeline_schools):
    """B校用户查看 progress 时，如果运行的是 A校的 pipeline，返回 idle。"""
    from edu_cloud.modules.scan import pipeline_service
    pipeline_service._running = True
    pipeline_service._pipeline_school_id = pipeline_schools["a"]["school_id"]
    try:
        resp = await client.get(
            "/api/v1/scan/pipeline/progress",
            headers=pipeline_schools["b"]["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"
    finally:
        pipeline_service._running = False
        pipeline_service._pipeline_school_id = None


@pytest.mark.asyncio
async def test_stop_allows_own_school(client, pipeline_schools):
    """A校用户可以停止自己学校的 pipeline。"""
    from edu_cloud.modules.scan import pipeline_service
    pipeline_service._running = True
    pipeline_service._pipeline_school_id = pipeline_schools["a"]["school_id"]
    try:
        resp = await client.post(
            "/api/v1/scan/pipeline/stop",
            headers=pipeline_schools["a"]["headers"],
        )
        assert resp.status_code == 200
    finally:
        pipeline_service._running = False
        pipeline_service._pipeline_school_id = None


@pytest.mark.asyncio
async def test_enqueue_records_school_id(pipeline_schools):
    """enqueue_pipeline 应将 school_id 记录到 _pipeline_school_id。"""
    from edu_cloud.modules.scan import pipeline_service
    old_school_id = pipeline_service._pipeline_school_id
    try:
        pipeline_service._pipeline_school_id = None
        pipeline_service.enqueue_pipeline(
            school_id=pipeline_schools["a"]["school_id"],
            subject_id="test-subj", image_dir="/tmp/nonexistent", side="A",
            save_answer_fn=None, save_objective_fn=None,
        )
        assert pipeline_service._pipeline_school_id == pipeline_schools["a"]["school_id"]
    finally:
        pipeline_service._queue.clear()
        pipeline_service._pipeline_school_id = old_school_id


@pytest.mark.asyncio
async def test_enqueue_does_not_overwrite_running_owner(pipeline_schools):
    """F001: A校 pipeline 运行中，B校 enqueue 不应覆盖 _pipeline_school_id。"""
    from edu_cloud.modules.scan import pipeline_service
    pipeline_service._running = True
    pipeline_service._pipeline_school_id = pipeline_schools["a"]["school_id"]
    try:
        pipeline_service.enqueue_pipeline(
            school_id=pipeline_schools["b"]["school_id"],
            subject_id="test-subj", image_dir="/tmp/nonexistent", side="A",
            save_answer_fn=None, save_objective_fn=None,
        )
        assert pipeline_service._pipeline_school_id == pipeline_schools["a"]["school_id"], \
            "Running pipeline owner should not be overwritten by new enqueue"
    finally:
        pipeline_service._queue.clear()
        pipeline_service._running = False
        pipeline_service._pipeline_school_id = None
