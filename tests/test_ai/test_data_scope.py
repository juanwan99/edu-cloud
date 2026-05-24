"""Tests for DataScope + DataScopeBuilder — 8-role derivation with fail-closed."""
import pytest
from sqlalchemy import select

from edu_cloud.ai.data_scope import DataScope, DataScopeBuilder, DataScopeBuildError
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.models.guardian import GuardianStudentLink
from edu_cloud.models.teacher_assignment import TeacherAssignment
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.school_settings import SchoolSetting


# ── T1: frozen dataclass ──────────────────────────────────────────


def test_data_scope_is_frozen():
    """DataScope is immutable — assignment raises FrozenInstanceError."""
    scope = DataScope(
        user_id="u1",
        school_id="s1",
        role="platform_admin",
        visible_class_ids=None,
        visible_subject_codes=None,
        visible_grade_ids=None,
        visible_student_ids=None,
        district_ids=None,
        can_write=True,
        can_see_rankings=True,
        can_cross_school=True,
        persona="admin_analyst",
        version=1,
    )
    with pytest.raises(AttributeError):
        scope.can_write = False  # type: ignore[misc]


# ── T2: platform_admin ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_scope_platform_admin(db, admin_user):
    """platform_admin → all None limits, can_cross_school, persona=admin_analyst."""
    # admin_user fixture creates user + UserRole(platform_admin)
    role = (await db.execute(
        select(UserRole).where(UserRole.user_id == admin_user.id)
    )).scalars().first()
    assert role is not None

    builder = DataScopeBuilder(db)
    scope = await builder.build(admin_user.id, role.id)

    assert scope.role == "platform_admin"
    assert scope.persona == "admin_analyst"
    assert scope.can_cross_school is True
    assert scope.can_write is True
    assert scope.can_see_rankings is True
    assert scope.visible_class_ids is None
    assert scope.visible_subject_codes is None
    assert scope.visible_grade_ids is None
    assert scope.visible_student_ids is None
    assert scope.version == 1
    assert scope.computed_at is not None


# ── T3: subject_teacher ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_scope_subject_teacher(db):
    """subject_teacher → visible_class_ids + visible_subject_codes from TeacherAssignment."""
    # Create user
    user = User(username="teacher_scope", display_name="Scope Teacher")
    user.set_password("x")
    db.add(user)
    await db.flush()

    # Create school
    school = School(name="Scope校", code="SCOPE01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    # Create class (needed for FK)
    cls = ClassGroup(name="八年级1班", grade="八年级", grade_number=8, school_id=school.id)
    db.add(cls)
    await db.flush()

    # UserRole
    role = UserRole(
        user_id=user.id,
        role="subject_teacher",
        school_id=school.id,
        is_primary=True,
    )
    db.add(role)
    await db.flush()

    # TeacherAssignment
    db.add(TeacherAssignment(
        user_id=user.id,
        class_id=cls.id,
        subject_code="SX",
        semester="2025-2026-2",
        school_id=school.id,
        is_active=True,
    ))
    await db.commit()

    builder = DataScopeBuilder(db)
    scope = await builder.build(user.id, role.id)

    assert scope.role == "subject_teacher"
    assert scope.persona == "teacher_assistant"
    assert scope.visible_class_ids == [cls.id]
    assert scope.visible_subject_codes == ["SX"]
    assert scope.can_write is True
    assert scope.can_cross_school is False


# ── T4: parent ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_scope_parent(db):
    """parent → visible_student_ids from GuardianStudentLink, can_write=False."""
    user = User(username="parent_scope", display_name="家长A")
    user.set_password("x")
    db.add(user)
    await db.flush()

    school = School(name="家长校", code="PARENT01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    role = UserRole(
        user_id=user.id,
        role="parent",
        school_id=school.id,
        is_primary=True,
    )
    db.add(role)
    await db.flush()

    child_id = "student-001"
    db.add(GuardianStudentLink(
        guardian_user_id=user.id,
        student_id=child_id,
        relationship="father",
        school_id=school.id,
        is_primary=True,
    ))
    await db.commit()

    builder = DataScopeBuilder(db)
    scope = await builder.build(user.id, role.id)

    assert scope.role == "parent"
    assert scope.persona == "parent_advisor"
    assert scope.visible_student_ids == [child_id]
    assert scope.can_write is False
    assert scope.can_see_rankings is False
    assert scope.can_cross_school is False


# ── T5: fail-closed unknown role ──────────────────────────────────


@pytest.mark.asyncio
async def test_build_scope_fail_closed_unknown_role(db):
    """Unknown role_id → DataScopeBuildError."""
    builder = DataScopeBuilder(db)
    with pytest.raises(DataScopeBuildError):
        await builder.build("nonexistent-user", "nonexistent-role")


@pytest.mark.asyncio
async def test_build_scope_fail_closed_unrecognized_role_string(db):
    """Role string not in PERSONA_MAP → DataScopeBuildError (fail-closed)."""
    user = User(username="alien_role", display_name="Alien")
    user.set_password("x")
    db.add(user)
    await db.flush()

    school = School(name="异常校", code="ALIEN01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    role = UserRole(
        user_id=user.id,
        role="unknown_role_xyz",
        school_id=school.id,
        is_primary=True,
    )
    db.add(role)
    await db.commit()

    builder = DataScopeBuilder(db)
    with pytest.raises(DataScopeBuildError, match="unknown_role_xyz"):
        await builder.build(user.id, role.id)


# ── T6: user_id mismatch ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_scope_user_id_mismatch(db, admin_user):
    """role_id exists but belongs to different user → DataScopeBuildError."""
    role = (await db.execute(
        select(UserRole).where(UserRole.user_id == admin_user.id)
    )).scalars().first()

    builder = DataScopeBuilder(db)
    with pytest.raises(DataScopeBuildError, match="mismatch"):
        await builder.build("wrong-user-id", role.id)


# ── T7: homeroom_teacher ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_scope_homeroom_teacher(db):
    """homeroom_teacher → class_ids from UserRole UNION TeacherAssignment."""
    user = User(username="hr_teacher", display_name="班主任")
    user.set_password("x")
    db.add(user)
    await db.flush()

    school = School(name="班主任校", code="HR01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls1 = ClassGroup(name="七年级1班", grade="七年级", grade_number=7, school_id=school.id)
    cls2 = ClassGroup(name="七年级2班", grade="七年级", grade_number=7, school_id=school.id)
    db.add_all([cls1, cls2])
    await db.flush()

    role = UserRole(
        user_id=user.id,
        role="homeroom_teacher",
        school_id=school.id,
        class_ids=[cls1.id],
        is_primary=True,
    )
    db.add(role)
    await db.flush()

    # Also assigned to cls2 via TeacherAssignment
    db.add(TeacherAssignment(
        user_id=user.id,
        class_id=cls2.id,
        subject_code="YW",
        semester="2025-2026-2",
        school_id=school.id,
        is_active=True,
    ))
    await db.commit()

    builder = DataScopeBuilder(db)
    scope = await builder.build(user.id, role.id)

    assert scope.role == "homeroom_teacher"
    assert scope.persona == "teacher_assistant"
    assert set(scope.visible_class_ids) == {cls1.id, cls2.id}
    assert scope.visible_subject_codes == ["YW"]
    assert scope.can_write is True


# ── T8: grade_leader ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_scope_grade_leader(db):
    """grade_leader → visible_grade_ids from UserRole, visible_class_ids=None."""
    user = User(username="gl_test", display_name="年级组长")
    user.set_password("x")
    db.add(user)
    await db.flush()

    school = School(name="组长校", code="GL01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    role = UserRole(
        user_id=user.id,
        role="grade_leader",
        school_id=school.id,
        grade_ids=["grade-7", "grade-8"],
        is_primary=True,
    )
    db.add(role)
    await db.commit()

    builder = DataScopeBuilder(db)
    scope = await builder.build(user.id, role.id)

    assert scope.role == "grade_leader"
    assert scope.persona == "teacher_assistant"
    assert scope.visible_grade_ids == ["grade-7", "grade-8"]
    assert scope.visible_class_ids is None  # all classes in those grades
    assert scope.can_write is True


# ── T9: principal ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_scope_principal(db):
    """principal → all None (school-wide), can_write=True."""
    user = User(username="principal_test", display_name="校长")
    user.set_password("x")
    db.add(user)
    await db.flush()

    school = School(name="校长校", code="PRINC01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    role = UserRole(
        user_id=user.id,
        role="principal",
        school_id=school.id,
        is_primary=True,
    )
    db.add(role)
    await db.commit()

    builder = DataScopeBuilder(db)
    scope = await builder.build(user.id, role.id)

    assert scope.role == "principal"
    assert scope.persona == "school_leader"
    assert scope.can_write is True
    assert scope.can_see_rankings is True
    assert scope.can_cross_school is False
    assert scope.visible_class_ids is None
    assert scope.visible_grade_ids is None


# ── T10: parent with school setting for rankings ─────────────────


@pytest.mark.asyncio
async def test_build_scope_parent_can_see_ranking_setting(db):
    """parent + school setting parent_can_see_ranking=true → can_see_rankings=True."""
    user = User(username="parent_rank", display_name="家长B")
    user.set_password("x")
    db.add(user)
    await db.flush()

    school = School(name="排名校", code="RANK01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    role = UserRole(
        user_id=user.id,
        role="parent",
        school_id=school.id,
        is_primary=True,
    )
    db.add(role)
    await db.flush()

    db.add(GuardianStudentLink(
        guardian_user_id=user.id,
        student_id="student-rank-1",
        relationship="mother",
        school_id=school.id,
        is_primary=True,
    ))
    # Enable ranking for parents at this school
    db.add(SchoolSetting(
        school_id=school.id,
        category="privacy",
        key="parent_can_see_ranking",
        value="true",
    ))
    await db.commit()

    builder = DataScopeBuilder(db)
    scope = await builder.build(user.id, role.id)

    assert scope.can_see_rankings is True


# ── T11: parent cross-school isolation (F001 regression) ─────────


@pytest.mark.asyncio
async def test_build_scope_parent_cross_school_isolation(db):
    """F001 regression: parent with children in TWO schools → scope for school A
    must only contain school A's child, not school B's."""
    user = User(username="parent_cross", display_name="跨校家长")
    user.set_password("x")
    db.add(user)
    await db.flush()

    school_a = School(name="学校A", code="XSCHA01", district="测试区", api_key_hash="x")
    school_b = School(name="学校B", code="XSCHB01", district="测试区", api_key_hash="x")
    db.add_all([school_a, school_b])
    await db.flush()

    # Role in school A
    role_a = UserRole(
        user_id=user.id,
        role="parent",
        school_id=school_a.id,
        is_primary=True,
    )
    db.add(role_a)
    await db.flush()

    # Child in school A
    child_a = "student-school-a"
    db.add(GuardianStudentLink(
        guardian_user_id=user.id,
        student_id=child_a,
        relationship="father",
        school_id=school_a.id,
        is_primary=True,
    ))
    # Child in school B — must NOT appear in school A scope
    child_b = "student-school-b"
    db.add(GuardianStudentLink(
        guardian_user_id=user.id,
        student_id=child_b,
        relationship="father",
        school_id=school_b.id,
        is_primary=False,
    ))
    await db.commit()

    builder = DataScopeBuilder(db)
    scope = await builder.build(user.id, role_a.id)

    assert scope.visible_student_ids == [child_a], (
        f"Expected only school A child, got {scope.visible_student_ids}"
    )
    assert child_b not in (scope.visible_student_ids or [])


@pytest.mark.asyncio
async def test_build_scope_teaching_research_leader_uses_subject_scope(db):
    """teaching_research_leader -> subject scope across school, no class narrowing."""
    user = User(username="trl_scope", display_name="教研组长")
    user.set_password("x")
    db.add(user)
    await db.flush()

    school = School(name="教研校", code="TRL01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    role = UserRole(
        user_id=user.id,
        role="teaching_research_leader",
        school_id=school.id,
        subject_codes=["SX"],
        is_primary=True,
    )
    db.add(role)
    await db.commit()

    builder = DataScopeBuilder(db)
    scope = await builder.build(user.id, role.id)

    assert scope.role == "teaching_research_leader"
    assert scope.visible_subject_codes == ["SX"]
    assert scope.visible_class_ids is None
    assert scope.visible_grade_ids is None
    assert scope.can_write is True


@pytest.mark.asyncio
async def test_build_scope_lesson_prep_leader_uses_grade_and_subject_scope(db):
    """lesson_prep_leader -> grade + subject scope for same-grade same-subject work."""
    user = User(username="lpl_scope", display_name="备课组长")
    user.set_password("x")
    db.add(user)
    await db.flush()

    school = School(name="备课校", code="LPL01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    role = UserRole(
        user_id=user.id,
        role="lesson_prep_leader",
        school_id=school.id,
        grade_ids=["7"],
        subject_codes=["SX"],
        is_primary=True,
    )
    db.add(role)
    await db.commit()

    builder = DataScopeBuilder(db)
    scope = await builder.build(user.id, role.id)

    assert scope.role == "lesson_prep_leader"
    assert scope.visible_grade_ids == ["7"]
    assert scope.visible_subject_codes == ["SX"]
    assert scope.visible_class_ids is None
    assert scope.can_write is True
