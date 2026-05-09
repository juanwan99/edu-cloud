"""Permission decorator enforcement tests.

Task 7: Verify that student write endpoints require MANAGE_TEACHERS,
grading review GET endpoints require VIEW_GRADING, and assignment
POST validates teacher-school ownership.
"""
import pytest
from sqlalchemy import select

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.shared.auth import create_access_token


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def school_and_users(db):
    """Seed a school with an academic_director (has MANAGE_TEACHERS) and a
    subject_teacher (lacks MANAGE_TEACHERS)."""
    school = School(name="权限测试校", code="PERMTEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    # academic_director -- has MANAGE_TEACHERS
    director = User(username="perm_director", display_name="权限主任")
    director.set_password("test123")
    db.add(director)
    await db.flush()
    db.add(UserRole(user_id=director.id, role="academic_director",
                    school_id=school.id, is_primary=True))

    # subject_teacher -- lacks MANAGE_TEACHERS
    teacher = User(username="perm_teacher", display_name="普通教师")
    teacher.set_password("test123")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(user_id=teacher.id, role="subject_teacher",
                    school_id=school.id, is_primary=True))

    # observer -- lacks VIEW_GRADING
    observer = User(username="perm_observer", display_name="观察者")
    observer.set_password("test123")
    db.add(observer)
    await db.flush()
    db.add(UserRole(user_id=observer.id, role="observer", is_primary=True))

    await db.commit()
    for u in (director, teacher, observer):
        await db.refresh(u)
    return {
        "school": school,
        "director": director,
        "teacher": teacher,
        "observer": observer,
    }


def _headers(user: User) -> dict:
    token = create_access_token({"sub": user.id})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Student write endpoints -- require MANAGE_TEACHERS
# ---------------------------------------------------------------------------

class TestStudentWritePermissions:
    """Student POST/PATCH/DELETE/import must require MANAGE_TEACHERS."""

    @pytest.mark.asyncio
    async def test_create_student_allowed_for_director(self, client, school_and_users):
        resp = await client.post(
            "/api/v1/students",
            json={"name": "张三", "student_number": "S001"},
            headers=_headers(school_and_users["director"]),
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_student_denied_for_teacher(self, client, school_and_users):
        resp = await client.post(
            "/api/v1/students",
            json={"name": "张三", "student_number": "S001"},
            headers=_headers(school_and_users["teacher"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_student_denied_for_teacher(self, client, school_and_users):
        resp = await client.patch(
            "/api/v1/students/nonexistent",
            json={"name": "李四"},
            headers=_headers(school_and_users["teacher"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_student_denied_for_teacher(self, client, school_and_users):
        resp = await client.delete(
            "/api/v1/students/nonexistent",
            headers=_headers(school_and_users["teacher"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_import_student_denied_for_teacher(self, client, school_and_users):
        import io
        fake_file = io.BytesIO(b"fake xlsx content")
        resp = await client.post(
            "/api/v1/students/import",
            files={"file": ("test.xlsx", fake_file, "application/octet-stream")},
            data={"class_id": "", "grade": ""},
            headers=_headers(school_and_users["teacher"]),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Grading review GET endpoints -- require VIEW_GRADING
# ---------------------------------------------------------------------------

class TestGradingReviewPermissions:
    """Grading review GET endpoints must require VIEW_GRADING."""

    @pytest.mark.asyncio
    async def test_list_results_allowed_for_teacher(self, client, school_and_users):
        """subject_teacher has VIEW_GRADING in baseline permissions."""
        resp = await client.get(
            "/api/v1/grading/results",
            headers=_headers(school_and_users["teacher"]),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_results_denied_for_observer(self, client, school_and_users):
        """observer lacks VIEW_GRADING."""
        resp = await client.get(
            "/api/v1/grading/results",
            headers=_headers(school_and_users["observer"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_pending_reviews_denied_for_observer(self, client, school_and_users):
        resp = await client.get(
            "/api/v1/grading/review/pending",
            headers=_headers(school_and_users["observer"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_result_denied_for_observer(self, client, school_and_users):
        resp = await client.get(
            "/api/v1/grading/results/nonexistent",
            headers=_headers(school_and_users["observer"]),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Assignment POST -- teacher-school ownership
# ---------------------------------------------------------------------------

class TestAssignmentTeacherOwnership:
    """POST /grading/assignments must reject teacher not belonging to the school."""

    @pytest.mark.asyncio
    async def test_assignment_rejected_for_foreign_teacher(self, client, db, school_and_users):
        """Teacher without a role at the target school should be rejected."""
        school = school_and_users["school"]

        # Create a teacher in a *different* school
        other_school = School(name="他校", code="OTHER01", district="测试区", api_key_hash="x")
        db.add(other_school)
        await db.flush()

        foreign_teacher = User(username="foreign_teacher", display_name="外校老师")
        foreign_teacher.set_password("test123")
        db.add(foreign_teacher)
        await db.flush()
        db.add(UserRole(user_id=foreign_teacher.id, role="subject_teacher",
                        school_id=other_school.id, is_primary=True))
        await db.commit()

        resp = await client.post(
            "/api/v1/grading/assignments",
            json={
                "exam_id": "e1",
                "subject_id": "s1",
                "question_ids": ["q1"],
                "teacher_id": str(foreign_teacher.id),
                "school_id": str(school.id),
            },
            headers=_headers(school_and_users["director"]),
        )
        assert resp.status_code == 400
        assert "does not belong" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_assignment_accepted_for_local_teacher(self, client, school_and_users):
        """Teacher with a role at the target school should be accepted."""
        school = school_and_users["school"]
        teacher = school_and_users["teacher"]  # has role at school

        resp = await client.post(
            "/api/v1/grading/assignments",
            json={
                "exam_id": "e1",
                "subject_id": "s1",
                "question_ids": ["q1"],
                "teacher_id": str(teacher.id),
                "school_id": str(school.id),
            },
            headers=_headers(school_and_users["director"]),
        )
        assert resp.status_code == 201
