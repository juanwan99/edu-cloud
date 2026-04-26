"""超管跨校创建学校管理账号 — POST /teachers 契约测试（ORC-001/ORC-002/ORC-004）。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def cross_school_setup(db):
    """两所学校 + 超管 / 景炎校长 / 景炎科任教师三种调用者。"""
    school_a = School(id="s_jy", name="景炎初级中学", code="JY001")
    school_b = School(id="s_yc", name="育才实验中学", code="YC001")
    db.add_all([school_a, school_b])
    await db.commit()

    admin = User(id="u_pa", username="pa_cross", display_name="平台超管")
    admin.set_password("p")
    principal_a = User(id="u_pri_a", username="pri_a", display_name="景炎校长")
    principal_a.set_password("p")
    teacher_a = User(id="u_t_a", username="t_a", display_name="景炎语文老师")
    teacher_a.set_password("p")
    db.add_all([admin, principal_a, teacher_a])
    await db.flush()

    db.add_all([
        UserRole(user_id="u_pa", role="platform_admin", school_id=None, is_primary=True),
        UserRole(user_id="u_pri_a", role="principal", school_id="s_jy", is_primary=True),
        UserRole(user_id="u_t_a", role="subject_teacher", school_id="s_jy",
                 is_primary=True, subject_codes=["YW"]),
    ])
    await db.commit()

    def _token(uid, role):
        return {"Authorization": f"Bearer {create_access_token({'sub': uid, 'role': role})}"}

    return {
        "school_a_id": "s_jy",
        "school_b_id": "s_yc",
        "admin": _token("u_pa", "platform_admin"),
        "principal_a": _token("u_pri_a", "principal"),
        "teacher_a": _token("u_t_a", "subject_teacher"),
    }


class TestCrossSchoolTeacherCreate:
    """ORC-001 / ORC-002 / ORC-004 契约锁。"""

    async def test_platform_admin_creates_principal_in_target_school(
        self, client: AsyncClient, cross_school_setup, db
    ):
        """超管传 school_id=景炎 + role=principal → 201，UserRole.school_id=景炎。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "new_principal_jy",
                "display_name": "景炎新校长",
                "roles": ["principal"],
                "school_id": cross_school_setup["school_a_id"],
            },
            headers=cross_school_setup["admin"],
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["roles"][0]["role"] == "principal"
        role_row = (await db.execute(
            select(UserRole).where(UserRole.user_id == body["id"])
        )).scalar_one()
        assert role_row.school_id == cross_school_setup["school_a_id"]

    async def test_platform_admin_creates_academic_director(
        self, client: AsyncClient, cross_school_setup, db
    ):
        """ORC-002：超管传 school_id + role=academic_director → 201，落库 school_id 正确。

        R1-F002 加强：断言 UserRole.school_id 而不只是 status_code，确保红灯基线成立。
        """
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "new_director_jy",
                "display_name": "景炎新教务",
                "roles": ["academic_director"],
                "school_id": cross_school_setup["school_a_id"],
            },
            headers=cross_school_setup["admin"],
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["roles"][0]["role"] == "academic_director"
        role_row = (await db.execute(
            select(UserRole).where(UserRole.user_id == body["id"])
        )).scalar_one()
        assert role_row.school_id == cross_school_setup["school_a_id"]

    async def test_platform_admin_creates_subject_teacher_cross_school(
        self, client: AsyncClient, cross_school_setup, db
    ):
        """ORC-004 后端契约锁（R1-F001）：超管跨校传 role=subject_teacher → 201。

        后端不做角色白名单收窄（保持 ALL_SCHOOL_ROLES 契约）；角色引导由前端 UI 完成。
        若此测试返回 403 或 422，说明实现误加了后端白名单，破坏既有 principal 在本校建
        subject_teacher 路径。
        """
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "cross_subject_teacher",
                "display_name": "跨校科任教师",
                "roles": ["subject_teacher"],
                "school_id": cross_school_setup["school_a_id"],
            },
            headers=cross_school_setup["admin"],
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["roles"][0]["role"] == "subject_teacher"
        role_row = (await db.execute(
            select(UserRole).where(UserRole.user_id == body["id"])
        )).scalar_one()
        assert role_row.role == "subject_teacher"
        assert role_row.school_id == cross_school_setup["school_a_id"]

    async def test_platform_admin_without_school_id_returns_422(
        self, client: AsyncClient, cross_school_setup
    ):
        """超管不传 school_id + current_role 也无 school_id → 422（ORC-001）。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "orphan_principal",
                "display_name": "孤儿校长",
                "roles": ["principal"],
            },
            headers=cross_school_setup["admin"],
        )
        assert resp.status_code == 422, resp.text

    async def test_subject_teacher_cross_school_returns_403(
        self, client: AsyncClient, cross_school_setup
    ):
        """科任教师（本校 s_jy）试图跨校向 s_yc 建账号 → 403（ORC-002）。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "evil_cross",
                "display_name": "跨校恶意",
                "roles": ["subject_teacher"],
                "school_id": cross_school_setup["school_b_id"],
            },
            headers=cross_school_setup["teacher_a"],
        )
        assert resp.status_code == 403, resp.text

    async def test_principal_same_school_passes(
        self, client: AsyncClient, cross_school_setup
    ):
        """景炎校长显式传本校 school_id → 走本校分支（is_cross_school=False），201。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "t_new_in_own_school",
                "display_name": "本校新科任",
                "roles": ["subject_teacher"],
                "school_id": cross_school_setup["school_a_id"],
            },
            headers=cross_school_setup["principal_a"],
        )
        assert resp.status_code == 201, resp.text

    async def test_principal_cross_school_returns_403(
        self, client: AsyncClient, cross_school_setup
    ):
        """景炎校长试图跨校向 s_yc 建账号 → 403（ORC-002）。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "cross_by_principal",
                "display_name": "跨校越权",
                "roles": ["principal"],
                "school_id": cross_school_setup["school_b_id"],
            },
            headers=cross_school_setup["principal_a"],
        )
        assert resp.status_code == 403, resp.text
