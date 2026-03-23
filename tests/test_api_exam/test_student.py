"""Student/Class API + 权限过滤测试。"""
import pytest
from httpx import AsyncClient
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.student import Class, Student
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def school_setup(db):
    """创建学校 + 班级 + 学生 + 多角色用户。"""
    school = School(id="s1", name="测试学校", code="PERM01")
    db.add(school)
    await db.commit()

    c1 = Class(id="c1", name="高二(1)班", grade="高二", school_id="s1")
    c2 = Class(id="c2", name="高二(2)班", grade="高二", school_id="s1")
    db.add_all([c1, c2])
    await db.commit()

    db.add_all([
        Student(name="张三", student_number="A001", class_id="c1", school_id="s1"),
        Student(name="李四", student_number="A002", class_id="c1", school_id="s1"),
        Student(name="王五", student_number="A003", class_id="c2", school_id="s1"),
    ])
    await db.commit()

    # Admin: 全校全科
    admin = User(id="u_admin", username="admin", display_name="管理员")
    admin.set_password("p")
    # Teacher: 语文, 只看 c1
    teacher_yw = User(id="u_tyw", username="teacher_yw", display_name="语文教师")
    teacher_yw.set_password("p")
    # Head teacher: 班主任, 看 c1 全科
    head = User(id="u_head", username="head", display_name="班主任")
    head.set_password("p")
    # Teacher without subject_code (misconfigured)
    bare_teacher = User(id="u_bare", username="bare", display_name="裸教师")
    bare_teacher.set_password("p")
    db.add_all([admin, teacher_yw, head, bare_teacher])
    await db.flush()
    db.add_all([
        UserRole(user_id="u_admin", role="admin", school_id="s1", is_primary=True),
        UserRole(user_id="u_tyw", role="teacher", school_id="s1", is_primary=True, subject_codes=["YW"], class_ids=["c1"]),
        UserRole(user_id="u_head", role="head_teacher", school_id="s1", is_primary=True, class_ids=["c1"]),
        UserRole(user_id="u_bare", role="teacher", school_id="s1", is_primary=True),
    ])
    await db.commit()

    def token_for(user_id, role):
        return create_access_token({"sub": user_id, "school_id": "s1", "role": role})

    return {
        "admin": {"Authorization": f"Bearer {token_for('u_admin', 'admin')}"},
        "teacher_yw": {"Authorization": f"Bearer {token_for('u_tyw', 'teacher')}"},
        "head": {"Authorization": f"Bearer {token_for('u_head', 'head_teacher')}"},
        "bare": {"Authorization": f"Bearer {token_for('u_bare', 'teacher')}"},
    }


class TestListClasses:
    async def test_admin_sees_all(self, client: AsyncClient, school_setup):
        resp = await client.get("/api/v1/classes", headers=school_setup["admin"])
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_teacher_sees_own_classes(self, client: AsyncClient, school_setup):
        """teacher with class_ids=[c1] should only see c1."""
        resp = await client.get("/api/v1/classes", headers=school_setup["teacher_yw"])
        assert resp.status_code == 200
        classes = resp.json()
        assert len(classes) == 1
        assert classes[0]["id"] == "c1"

    async def test_head_teacher_sees_own_class(self, client: AsyncClient, school_setup):
        resp = await client.get("/api/v1/classes", headers=school_setup["head"])
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["id"] == "c1"

    async def test_bare_teacher_sees_nothing(self, client: AsyncClient, school_setup):
        """Teacher without class_ids should see empty list."""
        resp = await client.get("/api/v1/classes", headers=school_setup["bare"])
        assert resp.status_code == 200
        assert resp.json() == []


class TestListStudents:
    async def test_admin_sees_all(self, client: AsyncClient, school_setup):
        resp = await client.get("/api/v1/students", headers=school_setup["admin"])
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    async def test_teacher_sees_own_class_students(self, client: AsyncClient, school_setup):
        resp = await client.get("/api/v1/students", headers=school_setup["teacher_yw"])
        assert resp.status_code == 200
        students = resp.json()
        assert len(students) == 2  # only c1 students
        assert all(s["class_id"] == "c1" for s in students)

    async def test_teacher_filter_by_own_class(self, client: AsyncClient, school_setup):
        resp = await client.get("/api/v1/students?class_id=c1", headers=school_setup["teacher_yw"])
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_teacher_filter_by_other_class_returns_empty(self, client: AsyncClient, school_setup):
        """Teacher with class_ids=[c1] filtering by c2 should get empty."""
        resp = await client.get("/api/v1/students?class_id=c2", headers=school_setup["teacher_yw"])
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_bare_teacher_sees_nothing(self, client: AsyncClient, school_setup):
        resp = await client.get("/api/v1/students", headers=school_setup["bare"])
        assert resp.status_code == 200
        assert resp.json() == []


class TestImportStudents:
    def _make_xlsx(self, tmp_path, rows):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        fp = tmp_path / "students.xlsx"
        wb.save(fp)
        return fp

    async def test_import_success(self, client: AsyncClient, school_setup, tmp_path):
        fp = self._make_xlsx(tmp_path, [["姓名", "准考证号"], ["赵六", "B001"]])
        with open(fp, "rb") as f:
            resp = await client.post(
                "/api/v1/students/import",
                files={"file": ("s.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"class_id": "c1"},
                headers=school_setup["admin"],
            )
        assert resp.status_code == 201
        assert resp.json()["created"] == 1

    async def test_import_missing_class_id(self, client: AsyncClient, school_setup, tmp_path):
        fp = self._make_xlsx(tmp_path, [["姓名", "准考证号"], ["赵六", "B002"]])
        with open(fp, "rb") as f:
            resp = await client.post(
                "/api/v1/students/import",
                files={"file": ("s.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers=school_setup["admin"],
            )
        assert resp.status_code == 422  # edu-cloud: ValidationError → 422

    async def test_import_invalid_class_id(self, client: AsyncClient, school_setup, tmp_path):
        fp = self._make_xlsx(tmp_path, [["姓名", "准考证号"], ["赵六", "B003"]])
        with open(fp, "rb") as f:
            resp = await client.post(
                "/api/v1/students/import",
                files={"file": ("s.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"class_id": "nonexistent"},
                headers=school_setup["admin"],
            )
        assert resp.status_code == 404

    async def test_import_duplicate_skipped(self, client: AsyncClient, school_setup, tmp_path):
        """Import student with existing student_number should skip."""
        fp = self._make_xlsx(tmp_path, [["姓名", "准考证号"], ["张三重复", "A001"]])
        with open(fp, "rb") as f:
            resp = await client.post(
                "/api/v1/students/import",
                files={"file": ("s.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"class_id": "c1"},
                headers=school_setup["admin"],
            )
        assert resp.status_code == 201
        assert resp.json()["created"] == 0
        assert resp.json()["skipped"] == 1

    async def test_import_empty_excel(self, client: AsyncClient, school_setup, tmp_path):
        fp = self._make_xlsx(tmp_path, [["姓名", "准考证号"]])
        with open(fp, "rb") as f:
            resp = await client.post(
                "/api/v1/students/import",
                files={"file": ("s.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"class_id": "c1"},
                headers=school_setup["admin"],
            )
        assert resp.status_code == 422  # edu-cloud: ValidationError → 422

    async def test_import_missing_columns(self, client: AsyncClient, school_setup, tmp_path):
        fp = self._make_xlsx(tmp_path, [["名字", "编号"], ["赵六", "B004"]])
        with open(fp, "rb") as f:
            resp = await client.post(
                "/api/v1/students/import",
                files={"file": ("s.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"class_id": "c1"},
                headers=school_setup["admin"],
            )
        assert resp.status_code == 422  # edu-cloud: ValidationError → 422

    async def test_import_teacher_cannot_import_to_other_class(self, client: AsyncClient, school_setup, tmp_path):
        """Teacher with class_ids=[c1] cannot import students to c2."""
        fp = self._make_xlsx(tmp_path, [["姓名", "准考证号"], ["越权学生", "X001"]])
        with open(fp, "rb") as f:
            resp = await client.post(
                "/api/v1/students/import",
                files={"file": ("s.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"class_id": "c2"},
                headers=school_setup["teacher_yw"],
            )
        assert resp.status_code == 403
