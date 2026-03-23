"""权限过滤集成测试 — 验证角色矩阵（R7 修复）。"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def perm_setup(client, db):
    """创建学校 + 两科 + 题目 + 答卷 + 多角色用户（含未知角色）。"""
    school = School(id="ps1", name="权限测试校", code="PERM02")
    db.add(school)
    await db.commit()

    exam = Exam(id="pe1", name="权限测试考试", card_title="权限测试", school_id="ps1", status="scanning")
    db.add(exam)
    await db.commit()

    yw = Subject(id="psyw", exam_id="pe1", name="语文", code="YW", school_id="ps1")
    sx = Subject(id="pssx", exam_id="pe1", name="数学", code="SX", school_id="ps1")
    db.add_all([yw, sx])
    await db.commit()

    q_yw = Question(id="pqyw", subject_id="psyw", name="语文1", question_type="subjective", max_score=10, school_id="ps1")
    q_sx = Question(id="pqsx", subject_id="pssx", name="数学1", question_type="subjective", max_score=10, school_id="ps1")
    db.add_all([q_yw, q_sx])
    await db.commit()

    # Answer for 数学
    ans = StudentAnswer(exam_id="pe1", subject_id="pssx", student_id="s1", question_id="pqsx",
                        image_path="/tmp/a.png", school_id="ps1")
    db.add(ans)
    await db.commit()

    # Users
    admin = User(id="pu_admin", username="padmin", display_name="管理员")
    admin.set_password("p")
    teacher_yw = User(id="pu_tyw", username="ptyw", display_name="语文教师")
    teacher_yw.set_password("p")
    teacher_sx = User(id="pu_tsx", username="ptsx", display_name="数学教师")
    teacher_sx.set_password("p")
    bare = User(id="pu_bare", username="pbare", display_name="裸教师")
    bare.set_password("p")
    unknown = User(id="pu_unknown", username="punknown", display_name="未知角色用户")
    unknown.set_password("p")
    db.add_all([admin, teacher_yw, teacher_sx, bare, unknown])
    await db.flush()
    db.add_all([
        UserRole(user_id="pu_admin", role="admin", school_id="ps1", is_primary=True),
        UserRole(user_id="pu_tyw", role="teacher", school_id="ps1", is_primary=True, subject_codes=["YW"]),
        UserRole(user_id="pu_tsx", role="teacher", school_id="ps1", is_primary=True, subject_codes=["SX"]),
        UserRole(user_id="pu_bare", role="teacher", school_id="ps1", is_primary=True),
        UserRole(user_id="pu_unknown", role="unknown_role", school_id="ps1", is_primary=True),
    ])
    await db.commit()

    def headers_for(uid, role):
        token = create_access_token({"sub": uid, "school_id": "ps1", "role": role})
        return {"Authorization": f"Bearer {token}"}

    return {
        "admin": headers_for("pu_admin", "admin"),
        "teacher_yw": headers_for("pu_tyw", "teacher"),
        "teacher_sx": headers_for("pu_tsx", "teacher"),
        "bare": headers_for("pu_bare", "teacher"),
        "unknown": headers_for("pu_unknown", "unknown_role"),
        "exam_id": "pe1",
        "q_yw_id": "pqyw",
        "q_sx_id": "pqsx",
    }


class TestAnalyticsPermissions:
    async def test_admin_sees_all_subjects(self, client, perm_setup):
        resp = await client.get(f"/api/v1/analytics/exam/{perm_setup['exam_id']}/summary", headers=perm_setup["admin"])
        assert resp.status_code == 200
        assert len(resp.json()["subjects"]) == 2

    async def test_teacher_yw_sees_only_yw(self, client, perm_setup):
        resp = await client.get(f"/api/v1/analytics/exam/{perm_setup['exam_id']}/summary", headers=perm_setup["teacher_yw"])
        assert resp.status_code == 200
        subjects = resp.json()["subjects"]
        assert len(subjects) == 1
        assert subjects[0]["subject_name"] == "语文"

    async def test_bare_teacher_sees_nothing(self, client, perm_setup):
        """Teacher without subject_code should see empty subjects."""
        resp = await client.get(f"/api/v1/analytics/exam/{perm_setup['exam_id']}/summary", headers=perm_setup["bare"])
        assert resp.status_code == 200
        assert resp.json()["subjects"] == []

    async def test_teacher_yw_cannot_see_sx_questions(self, client, perm_setup):
        """语文教师不能看数学的题目分析。"""
        resp = await client.get(f"/api/v1/analytics/subject/pssx/questions", headers=perm_setup["teacher_yw"])
        assert resp.status_code == 403

    async def test_teacher_sx_can_see_sx_questions(self, client, perm_setup):
        """数学教师可以看数学的题目分析。"""
        resp = await client.get(f"/api/v1/analytics/subject/pssx/questions", headers=perm_setup["teacher_sx"])
        assert resp.status_code == 200


class TestMarkingPermissions:
    async def test_teacher_yw_cannot_mark_sx(self, client, perm_setup):
        """语文教师不能批改数学题。"""
        resp = await client.get(f"/api/v1/marking/next?question_id={perm_setup['q_sx_id']}", headers=perm_setup["teacher_yw"])
        assert resp.status_code == 403

    async def test_teacher_sx_can_mark_sx(self, client, perm_setup):
        """数学教师可以批改数学题。"""
        resp = await client.get(f"/api/v1/marking/next?question_id={perm_setup['q_sx_id']}", headers=perm_setup["teacher_sx"])
        assert resp.status_code == 200

    async def test_admin_can_mark_any(self, client, perm_setup):
        """管理员可以批改任何题。"""
        resp = await client.get(f"/api/v1/marking/next?question_id={perm_setup['q_sx_id']}", headers=perm_setup["admin"])
        assert resp.status_code == 200


class TestUnknownRolePermissions:
    """未知角色边界测试 — 验证不在 RBAC 映射中的角色被正确限制。"""

    async def test_unknown_role_sees_empty_subjects(self, client, perm_setup):
        """未知角色查看考试分析应返回空学科列表。"""
        resp = await client.get(
            f"/api/v1/analytics/exam/{perm_setup['exam_id']}/summary",
            headers=perm_setup["unknown"],
        )
        assert resp.status_code == 200
        assert resp.json()["subjects"] == []

    async def test_unknown_role_cannot_see_subject_questions(self, client, perm_setup):
        """未知角色不能查看任何学科的题目分析。"""
        resp = await client.get(
            "/api/v1/analytics/subject/psyw/questions",
            headers=perm_setup["unknown"],
        )
        assert resp.status_code == 403

    async def test_unknown_role_cannot_mark(self, client, perm_setup):
        """未知角色不能批改任何题。"""
        resp = await client.get(
            f"/api/v1/marking/next?question_id={perm_setup['q_sx_id']}",
            headers=perm_setup["unknown"],
        )
        assert resp.status_code == 403
