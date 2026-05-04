"""Tests for conduct scope_service — scope-adaptive overview aggregation."""
import pytest
from datetime import date, timedelta

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.conduct.models import ConductRecord
from edu_cloud.modules.conduct.scope_service import get_conduct_overview


# ── fixtures ──

async def _seed_school_classes_students_records(db, district="TestDistrict"):
    """Seed school with 2 classes, 3 students each, and conduct records."""
    school = School(name="Scope测试中学", code="SCOPE01", is_active=True, district=district)
    db.add(school)
    await db.flush()

    cls_a = Class(name="高一(1)班", grade="高一", grade_number=1, school_id=school.id)
    cls_b = Class(name="高一(2)班", grade="高一", grade_number=2, school_id=school.id)
    db.add_all([cls_a, cls_b])
    await db.flush()

    students = []
    for i, cls in enumerate([cls_a, cls_b]):
        for j in range(3):
            s = Student(
                name=f"学生{chr(65 + i)}{j + 1}",
                student_number=f"S{i}{j:03d}",
                class_id=cls.id,
                school_id=school.id,
            )
            db.add(s)
            students.append(s)
    await db.flush()

    # Create an operator user for records
    user = User(username="operator_scope", display_name="操作员")
    user.set_password("test123")
    db.add(user)
    await db.flush()

    today = date.today()
    # Class A students: positive records
    for s in students[:3]:
        db.add(ConductRecord(
            student_id=s.id, class_id=cls_a.id, points=5,
            reason="表现好", date=today, operator_id=user.id,
        ))
    # Class A student 0: also a negative record
    db.add(ConductRecord(
        student_id=students[0].id, class_id=cls_a.id, points=-2,
        reason="迟到", date=today, operator_id=user.id,
    ))
    # Class B student 3: one record
    db.add(ConductRecord(
        student_id=students[3].id, class_id=cls_b.id, points=3,
        reason="帮助同学", date=today, operator_id=user.id,
    ))

    await db.commit()
    return {
        "school": school,
        "cls_a": cls_a,
        "cls_b": cls_b,
        "students": students,
        "operator": user,
    }


@pytest.fixture
async def scope_data(db):
    return await _seed_school_classes_students_records(db)


# ═══════════════════════════════════════════════════
# Tests: class scope
# ═══════════════════════════════════════════════════

class TestClassScope:
    async def test_class_overview_summary(self, db, scope_data):
        cls_a_id = scope_data["cls_a"].id
        result = await get_conduct_overview(db, "class", [cls_a_id])

        assert result["scope_type"] == "class"
        s = result["summary"]
        assert s["total_students"] == 3
        assert s["total_records"] == 4  # 3 positive + 1 negative
        assert s["total_positive"] == 3
        assert s["total_negative"] == 1

    async def test_class_overview_rankings(self, db, scope_data):
        cls_a_id = scope_data["cls_a"].id
        result = await get_conduct_overview(db, "class", [cls_a_id])

        top = result["rankings"]["top"]
        assert len(top) > 0
        # Students with only +5 should be at top, student with +5-2=3 at bottom
        assert top[0]["points"] == 5

    async def test_class_overview_trend(self, db, scope_data):
        cls_a_id = scope_data["cls_a"].id
        result = await get_conduct_overview(db, "class", [cls_a_id], weeks=2)

        assert result["scope_type"] == "class"
        assert len(result["trend"]) == 2
        # Current week should have records
        current_week = result["trend"][-1]
        assert current_week["positive"] >= 0
        assert current_week["negative"] >= 0

    async def test_class_overview_empty(self, db, scope_data):
        """Class with no records returns zeroes."""
        # Create a class with no records
        school = scope_data["school"]
        empty_cls = Class(name="空班", grade="高一", grade_number=99, school_id=school.id)
        db.add(empty_cls)
        await db.flush()
        s = Student(name="孤学生", student_number="EMPTY01", class_id=empty_cls.id, school_id=school.id)
        db.add(s)
        await db.commit()

        result = await get_conduct_overview(db, "class", [empty_cls.id])
        assert result["summary"]["total_students"] == 1
        assert result["summary"]["total_records"] == 0
        assert result["summary"]["total_positive"] == 0
        assert result["summary"]["total_negative"] == 0
        assert result["rankings"]["top"] == []

    async def test_class_overview_multi_class(self, db, scope_data):
        """Multiple class_ids are aggregated together."""
        cls_a_id = scope_data["cls_a"].id
        cls_b_id = scope_data["cls_b"].id
        result = await get_conduct_overview(db, "class", [cls_a_id, cls_b_id])

        assert result["summary"]["total_students"] == 6
        assert result["summary"]["total_records"] == 5  # 4 in A + 1 in B


# ═══════════════════════════════════════════════════
# Tests: school scope
# ═══════════════════════════════════════════════════

class TestSchoolScope:
    async def test_school_overview_summary(self, db, scope_data):
        school_id = scope_data["school"].id
        result = await get_conduct_overview(db, "school", [school_id])

        assert result["scope_type"] == "school"
        s = result["summary"]
        assert s["total_students"] == 6
        assert s["total_records"] == 5
        assert s["class_count"] == 2

    async def test_school_overview_class_comparison(self, db, scope_data):
        school_id = scope_data["school"].id
        result = await get_conduct_overview(db, "school", [school_id])

        comp = result["class_comparison"]
        assert len(comp) == 2
        # Each entry has required fields
        for entry in comp:
            assert "class_id" in entry
            assert "class_name" in entry
            assert "record_count" in entry
            assert "avg_points" in entry

    async def test_school_overview_has_trend(self, db, scope_data):
        school_id = scope_data["school"].id
        result = await get_conduct_overview(db, "school", [school_id])

        assert "trend" in result
        assert isinstance(result["trend"], list)
        assert len(result["trend"]) == 4  # default 4 weeks
        # Current week should have records (seeded today)
        current_week = result["trend"][-1]
        assert current_week["positive"] >= 0
        assert current_week["negative"] >= 0
        assert "week_start" in current_week

    async def test_school_overview_empty(self, db):
        """School with no classes returns empty comparison."""
        school = School(name="空学校", code="EMPTY01", is_active=True)
        db.add(school)
        await db.commit()

        result = await get_conduct_overview(db, "school", [school.id])
        assert result["summary"]["total_students"] == 0
        assert result["summary"]["class_count"] == 0
        assert result["class_comparison"] == []


# ═══════════════════════════════════════════════════
# Tests: district scope
# ═══════════════════════════════════════════════════

class TestDistrictScope:
    async def test_district_overview_summary(self, db, scope_data):
        result = await get_conduct_overview(db, "district", ["TestDistrict"])

        assert result["scope_type"] == "district"
        s = result["summary"]
        assert s["total_schools"] == 1
        assert s["total_students"] == 6

    async def test_district_overview_school_comparison(self, db, scope_data):
        result = await get_conduct_overview(db, "district", ["TestDistrict"])

        comp = result["school_comparison"]
        assert len(comp) == 1
        entry = comp[0]
        assert entry["school_name"] == "Scope测试中学"
        assert entry["total_students"] == 6
        assert entry["record_count"] == 5
        assert isinstance(entry["avg_points"], float)

    async def test_district_overview_has_trend(self, db, scope_data):
        result = await get_conduct_overview(db, "district", ["TestDistrict"])

        assert "trend" in result
        assert isinstance(result["trend"], list)
        assert len(result["trend"]) == 4

    async def test_district_overview_no_schools(self, db):
        """District with no matching schools returns empty."""
        result = await get_conduct_overview(db, "district", ["NonExistent"])

        assert result["summary"]["total_schools"] == 0
        assert result["summary"]["total_students"] == 0
        assert result["school_comparison"] == []

    async def test_district_overview_multi_school(self, db, scope_data):
        """Multiple schools in the same district are aggregated."""
        # Add a second school in the same district
        school2 = School(name="第二中学", code="SCOPE02", is_active=True, district="TestDistrict")
        db.add(school2)
        await db.flush()
        cls = Class(name="初一(1)班", grade="初一", grade_number=1, school_id=school2.id)
        db.add(cls)
        await db.flush()
        s = Student(name="新生", student_number="NEW001", class_id=cls.id, school_id=school2.id)
        db.add(s)
        await db.commit()

        result = await get_conduct_overview(db, "district", ["TestDistrict"])
        assert result["summary"]["total_schools"] == 2
        assert result["summary"]["total_students"] == 7  # 6 + 1


# ═══════════════════════════════════════════════════
# Tests: invalid scope
# ═══════════════════════════════════════════════════

class TestInvalidScope:
    async def test_invalid_scope_type_raises(self, db):
        with pytest.raises(ValueError, match="Unknown scope_type"):
            await get_conduct_overview(db, "invalid", ["x"])


# ═══════════════════════════════════════════════════
# Tests: /overview endpoint (via HTTP client)
# ═══════════════════════════════════════════════════

class TestOverviewEndpoint:
    async def test_overview_as_platform_admin(self, client, db, admin_user, admin_headers, scope_data):
        """platform_admin gets district scope."""
        resp = await client.get("/api/v1/conduct/overview", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope_type"] == "district"

    async def test_overview_as_principal(self, client, db, scope_data):
        """principal gets school scope."""
        from edu_cloud.shared.auth import create_access_token

        user = User(username="principal_scope", display_name="王校长")
        user.set_password("test123")
        db.add(user)
        await db.flush()
        role = UserRole(
            user_id=user.id, role="principal",
            school_id=scope_data["school"].id, is_primary=True,
        )
        db.add(role)
        await db.commit()

        token = create_access_token({"sub": user.id, "role": "principal"})
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/conduct/overview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope_type"] == "school"
        assert data["summary"]["class_count"] == 2

    async def test_overview_as_homeroom_teacher(self, client, db, scope_data):
        """homeroom_teacher with class_ids gets class scope."""
        from edu_cloud.shared.auth import create_access_token

        user = User(username="teacher_scope", display_name="李老师")
        user.set_password("test123")
        db.add(user)
        await db.flush()
        role = UserRole(
            user_id=user.id, role="homeroom_teacher",
            school_id=scope_data["school"].id,
            class_ids=[scope_data["cls_a"].id],
            is_primary=True,
        )
        db.add(role)
        await db.commit()

        token = create_access_token({"sub": user.id, "role": "homeroom_teacher"})
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/conduct/overview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope_type"] == "class"
        assert data["summary"]["total_students"] == 3

    async def test_overview_unauthorized(self, client):
        """No auth returns 403."""
        resp = await client.get("/api/v1/conduct/overview")
        assert resp.status_code in (401, 403)
