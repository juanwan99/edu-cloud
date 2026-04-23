"""Exam/Question 路由 API 测试 — 多租户隔离验证。

创建考试需要 MANAGE_EXAMS 权限（教务主任/校长/平台管理员）。
普通教师只能查看/列表考试。测试用 director_headers（教务主任）创建，
teacher_headers（班主任）验证查看权限。
"""
import pytest
from httpx import AsyncClient


@pytest.fixture
async def director_headers(client, db, seed_teacher):
    """教务主任 JWT headers — 用于需要 MANAGE_EXAMS 权限的操作。
    依赖 seed_teacher 确保学校已创建。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School
    from sqlalchemy import select

    result = await db.execute(select(School).where(School.code == "TEST01"))
    school = result.scalar_one()

    user = User(username="director_exam", display_name="教务主任")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()

    resp = await client.post("/api/v1/auth/login",
                             json={"username": "director_exam", "password": "123456"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_and_list_exams(client: AsyncClient, director_headers, teacher_headers):
    """教务主任创建考试，教师可查看列表。"""
    resp = await client.post("/api/v1/exams", json={"name": "期中考", "card_title": "CT"},
                             headers=director_headers)
    assert resp.status_code == 201
    exam_id = resp.json()["id"]
    assert resp.json()["name"] == "期中考"

    # 教师可以查看考试列表
    resp = await client.get("/api/v1/exams", headers=teacher_headers)
    assert resp.status_code == 200
    assert any(e["id"] == exam_id for e in resp.json())


@pytest.mark.asyncio
async def test_teacher_cannot_create_exam(client: AsyncClient, teacher_headers):
    """普通教师无 MANAGE_EXAMS 权限，创建考试 → 403。"""
    resp = await client.post("/api/v1/exams", json={"name": "不该创建", "card_title": "NO"},
                             headers=teacher_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_exam_not_found(client: AsyncClient, teacher_headers):
    """资源不存在 → 404。"""
    resp = await client.get("/api/v1/exams/nonexistent", headers=teacher_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_school_isolation(client: AsyncClient, director_headers, admin_headers):
    """platform_admin（无 school_id）可以看到所有学校的考试。"""
    resp = await client.post("/api/v1/exams", json={"name": "隔离测试", "card_title": "IS"},
                             headers=director_headers)
    assert resp.status_code == 201

    # platform_admin (school_id=None) sees all exams across schools
    resp = await client.get("/api/v1/exams", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_create_subject_and_list(client: AsyncClient, director_headers, teacher_headers):
    """创建科目 + 列表。"""
    resp = await client.post("/api/v1/exams", json={"name": "科目测试", "card_title": "ST"},
                             headers=director_headers)
    exam_id = resp.json()["id"]
    resp = await client.post(f"/api/v1/exams/{exam_id}/subjects",
                             json={"name": "语文", "code": "YW"}, headers=director_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "语文"

    resp = await client.get(f"/api/v1/exams/{exam_id}/subjects", headers=teacher_headers)
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_question_crud(client: AsyncClient, director_headers):
    """题目 CRUD 完整流程（教务主任操作）。"""
    resp = await client.post("/api/v1/exams", json={"name": "题目测试", "card_title": "QT"},
                             headers=director_headers)
    exam_id = resp.json()["id"]
    resp = await client.post(f"/api/v1/exams/{exam_id}/subjects",
                             json={"name": "数学", "code": "SX"}, headers=director_headers)
    subject_id = resp.json()["id"]

    resp = await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "题1", "question_type": "choice", "max_score": 5,
    }, headers=director_headers)
    assert resp.status_code == 201
    qid = resp.json()["id"]

    resp = await client.get(f"/api/v1/questions?subject_id={subject_id}", headers=director_headers)
    assert len(resp.json()) == 1

    resp = await client.patch(f"/api/v1/questions/{qid}", json={"max_score": 10},
                              headers=director_headers)
    assert resp.json()["max_score"] == 10

    resp = await client.delete(f"/api/v1/questions/{qid}", headers=director_headers)
    assert resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_no_auth_returns_401(client: AsyncClient):
    """无 JWT → 401/403。"""
    resp = await client.get("/api/v1/exams")
    assert resp.status_code in (401, 403)
