import time
import pytest
import jwt
from edu_cloud.shared.auth import create_impersonation_token, decode_token
from edu_cloud.config import settings


def test_impersonation_token_has_required_claims():
    token = create_impersonation_token(
        impersonator_id="admin-uuid",
        effective_role="subject_teacher",
        effective_school_id="school-uuid",
        scope_override={
            "class_ids": ["c1", "c2"],
            "subject_codes": ["math"],
            "grade_ids": None,
        },
    )
    payload = decode_token(token)
    assert payload["sub"] == "admin-uuid"
    assert payload["is_impersonation"] is True
    assert payload["impersonator_id"] == "admin-uuid"
    assert payload["effective_role"] == "subject_teacher"
    assert payload["effective_school_id"] == "school-uuid"
    assert payload["scope_override"] == {
        "class_ids": ["c1", "c2"],
        "subject_codes": ["math"],
        "grade_ids": None,
    }


def test_impersonation_token_short_expiry():
    token = create_impersonation_token(
        impersonator_id="admin-uuid",
        effective_role="principal",
        effective_school_id="school-uuid",
        scope_override={},
    )
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    remaining = payload["exp"] - time.time()
    assert remaining < 35 * 60
    assert remaining > 25 * 60


@pytest.mark.asyncio
async def test_impersonation_token_on_protected_endpoint(client, admin_user):
    """Impersonation token should authenticate on protected endpoints."""
    from edu_cloud.shared.auth import create_impersonation_token

    imp_token = create_impersonation_token(
        impersonator_id=admin_user.id,
        effective_role="subject_teacher",
        effective_school_id="test-school-id",
        scope_override={"class_ids": ["c1"], "subject_codes": ["math"], "grade_ids": None},
    )
    resp = await client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {imp_token}"},
    )
    # Should authenticate successfully (200) — impersonation passes get_current_user
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_impersonation_malformed_token_rejected(client, admin_user):
    """Token missing required claims should be rejected."""
    from edu_cloud.shared.auth import create_access_token

    # Create a token with is_impersonation but missing effective_role
    bad_token = create_access_token({
        "sub": admin_user.id,
        "is_impersonation": True,
        # missing effective_role, effective_school_id, scope_override
    })
    resp = await client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {bad_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_impersonate_requires_admin(client, admin_user, db):
    """Non-admin cannot impersonate."""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    # Create a non-admin user
    teacher = User(username="teacher_test", display_name="Teacher")
    teacher.set_password("test123")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(user_id=teacher.id, role="subject_teacher", is_primary=True))

    # Create a school for the request
    school = School(name="Test School", code="TST001", district="Test")
    db.add(school)
    await db.commit()
    await db.refresh(teacher)
    await db.refresh(school)

    token = create_access_token({"sub": teacher.id, "role": "subject_teacher"})
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={"school_id": school.id, "role": "principal", "scope": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_impersonate_invalid_role(client, admin_user):
    """Invalid role name is rejected."""
    from edu_cloud.shared.auth import create_access_token

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={"school_id": "some-school", "role": "nonexistent_role", "scope": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_impersonate_success(client, admin_user, db):
    """Admin can impersonate a valid role in a valid school."""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.school import School

    school = School(name="Impersonate School", code="IMP001", district="Test")
    db.add(school)
    await db.commit()
    await db.refresh(school)

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={"school_id": school.id, "role": "principal", "scope": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_impersonation"] is True
    assert data["effective_role"] == "principal"
    assert data["effective_school_id"] == school.id
    assert "access_token" in data


@pytest.mark.asyncio
async def test_impersonate_exit(client, admin_user, db):
    """Exit impersonation returns a normal admin token."""
    from edu_cloud.shared.auth import create_access_token, create_impersonation_token
    from edu_cloud.models.school import School

    school = School(name="Exit School", code="EXT001", district="Test")
    db.add(school)
    await db.commit()
    await db.refresh(school)

    # Create an impersonation token
    imp_token = create_impersonation_token(
        impersonator_id=admin_user.id,
        effective_role="principal",
        effective_school_id=school.id,
        scope_override={"class_ids": None, "subject_codes": None, "grade_ids": None},
    )

    resp = await client.post(
        "/api/v1/auth/impersonate/exit",
        headers={"Authorization": f"Bearer {imp_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_impersonate_scope_required(client, admin_user, db):
    """Roles with required scope fields are rejected when scope is missing."""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.school import School

    school = School(name="Scope School", code="SCP001", district="Test")
    db.add(school)
    await db.commit()
    await db.refresh(school)

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    # subject_teacher requires class_ids and subject_codes
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={"school_id": school.id, "role": "subject_teacher", "scope": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "class_ids" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_impersonate_cross_school_grade_ids_rejected(client, admin_user, db):
    """SEC3: 跨校 grade_ids 应被拒绝。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.school import School
    from edu_cloud.models.grade import Grade

    school_a = School(name="School A", code="GRDA01", district="Test")
    school_b = School(name="School B", code="GRDB01", district="Test")
    db.add_all([school_a, school_b])
    await db.commit()
    await db.refresh(school_a)
    await db.refresh(school_b)

    grade_in_a = Grade(school_id=school_a.id, name="七年级")
    db.add(grade_in_a)
    await db.commit()
    await db.refresh(grade_in_a)

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": school_b.id,
            "role": "grade_leader",
            "scope": {"grade_ids": [grade_in_a.id]},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "Grades not in target school" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_impersonate_grade_ids_type_validation(client, admin_user, db):
    """SEC3: grade_ids 传非 list 类型应返回 422。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.school import School

    school = School(name="Type School", code="TYPS01", district="Test")
    db.add(school)
    await db.commit()
    await db.refresh(school)

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": school.id,
            "role": "grade_leader",
            "scope": {"grade_ids": "not-a-list"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "list" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_impersonate_optional_scope_type_validation(client, admin_user, db):
    """SEC3: 可选 scope 字段传非 list 真值应被 _clean_scope 拒绝为 422。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.school import School

    school = School(name="Clean School", code="CLN001", district="Test")
    db.add(school)
    await db.commit()
    await db.refresh(school)

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": school.id,
            "role": "principal",
            "scope": {"subject_codes": "math"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "list" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_impersonate_nonexistent_school(client, admin_user):
    """Impersonating into a non-existent school returns 404."""
    from edu_cloud.shared.auth import create_access_token

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={"school_id": "nonexistent-school-id", "role": "principal", "scope": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_data_scope_from_override():
    """build_from_override constructs scope without DB lookup."""
    from edu_cloud.ai.data_scope import DataScopeBuilder

    # build_from_override is sync, doesn't need a real db session
    builder = DataScopeBuilder(None)
    scope = builder.build_from_override(
        impersonator_id="admin-uuid",
        effective_role="subject_teacher",
        school_id="school-uuid",
        scope_override={
            "class_ids": ["c1", "c2"],
            "subject_codes": ["math"],
            "grade_ids": None,
        },
    )
    assert scope.role == "subject_teacher"
    assert scope.school_id == "school-uuid"
    assert scope.visible_class_ids == ["c1", "c2"]
    assert scope.visible_subject_codes == ["math"]
    assert scope.visible_grade_ids is None
    assert scope.can_write is True
    assert scope.persona == "teacher_assistant"
    assert scope.user_id == "admin-uuid"
    assert scope.can_cross_school is False


def test_data_scope_override_unknown_role():
    """Unknown role should raise DataScopeBuildError."""
    from edu_cloud.ai.data_scope import DataScopeBuilder, DataScopeBuildError

    builder = DataScopeBuilder(None)
    with pytest.raises(DataScopeBuildError, match="Cannot impersonate unknown role"):
        builder.build_from_override(
            impersonator_id="admin-uuid",
            effective_role="nonexistent_role",
            school_id="school-uuid",
            scope_override={},
        )


def test_data_scope_override_teaching_research_leader():
    """teaching_research_leader should be in PERSONA_MAP."""
    from edu_cloud.ai.data_scope import DataScopeBuilder

    builder = DataScopeBuilder(None)
    scope = builder.build_from_override(
        impersonator_id="admin-uuid",
        effective_role="teaching_research_leader",
        school_id="school-uuid",
        scope_override={"subject_codes": ["physics"], "class_ids": None, "grade_ids": None},
    )
    assert scope.role == "teaching_research_leader"
    assert scope.persona == "teacher_assistant"


@pytest.mark.asyncio
async def test_expired_impersonation_token_rejected(client, admin_user):
    """C-1: Expired impersonation token must be rejected with 401, same as normal expired tokens."""
    import time as _time
    from edu_cloud.config import settings

    # Create an already-expired impersonation token for a real admin user
    payload = {
        "sub": admin_user.id,
        "is_impersonation": True,
        "impersonator_id": admin_user.id,
        "effective_role": "subject_teacher",
        "effective_school_id": "school-uuid",
        "scope_override": {"class_ids": ["c1"], "subject_codes": ["math"], "grade_ids": None},
        "exp": int(_time.time()) - 60,  # expired 1 min ago
    }
    expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # Must get 401 on any endpoint, not succeed with impersonation permissions
    resp = await client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401, (
        f"Expired impersonation token should be rejected, got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_expired_impersonation_token_rejected_on_exit(client, admin_user):
    """C-1: Expired impersonation token must also be rejected on the exit endpoint."""
    import time as _time
    from edu_cloud.config import settings

    payload = {
        "sub": admin_user.id,
        "is_impersonation": True,
        "impersonator_id": admin_user.id,
        "effective_role": "principal",
        "effective_school_id": "school-uuid",
        "scope_override": {"class_ids": None, "subject_codes": None, "grade_ids": None},
        "exp": int(_time.time()) - 60,
    }
    expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    resp = await client.post(
        "/api/v1/auth/impersonate/exit",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_impersonate_cross_school_subject_codes_rejected(client, admin_user, db):
    """SEC3: 跨校 subject_codes 应被拒绝。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.school import School
    from edu_cloud.modules.exam.models import Subject, Exam

    school_a = School(name="Subject School A", code="SUBA01", district="Test")
    school_b = School(name="Subject School B", code="SUBB01", district="Test")
    db.add_all([school_a, school_b])
    await db.commit()
    await db.refresh(school_a)
    await db.refresh(school_b)

    exam = Exam(name="测试考试", school_id=school_a.id, subject_code="YW", subject_name="语文",
                max_score=150, semester="2025-2026-2")
    db.add(exam)
    await db.flush()
    subj = Subject(name="语文", code="YW", school_id=school_a.id, exam_id=exam.id)
    db.add(subj)
    await db.commit()

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": school_b.id,
            "role": "teaching_research_leader",
            "scope": {"subject_codes": ["YW"]},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "Subject codes not in target school" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_impersonate_valid_subject_codes_accepted(client, admin_user, db):
    """SEC3: 同校合法 subject_codes 应被接受。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.school import School
    from edu_cloud.modules.exam.models import Subject, Exam

    school = School(name="Valid Subject School", code="VSUB01", district="Test")
    db.add(school)
    await db.commit()
    await db.refresh(school)

    exam = Exam(name="数学期中", school_id=school.id, subject_code="SX", subject_name="数学",
                max_score=150, semester="2025-2026-2")
    db.add(exam)
    await db.flush()
    subj = Subject(name="数学", code="SX", school_id=school.id, exam_id=exam.id)
    db.add(subj)
    await db.commit()

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": school.id,
            "role": "teaching_research_leader",
            "scope": {"subject_codes": ["SX"]},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["effective_role"] == "teaching_research_leader"


@pytest.mark.asyncio
async def test_impersonate_scope_element_type_validation(client, admin_user, db):
    """F-001: scope 列表元素必须是字符串，非 hashable 类型应返回 422 而非 500。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.school import School

    school = School(name="Element Type School", code="ELT001", district="Test")
    db.add(school)
    await db.commit()
    await db.refresh(school)

    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})

    # grade_ids 含 dict 元素 → 应返回 422
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": school.id,
            "role": "grade_leader",
            "scope": {"grade_ids": [{}]},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "elements must be strings" in resp.json()["detail"]

    # class_ids 含 int 元素 → 应返回 422
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": school.id,
            "role": "subject_teacher",
            "scope": {"class_ids": [123], "subject_codes": ["SX"]},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "elements must be strings" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_impersonation_inherits_role_permissions(client, admin_user):
    """模拟登录继承目标角色的完整权限（含 USE_AI_CHAT 等）。"""
    from edu_cloud.core.permissions import Permission, ROLE_PERMISSIONS

    st_perms = ROLE_PERMISSIONS.get("subject_teacher", set())
    assert Permission.USE_AI_CHAT in st_perms
    assert Permission.MANAGE_GRADING not in st_perms
