"""exam-ai 兼容层测试 — paper-seg 对接端点。"""
import pytest
from httpx import AsyncClient
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.modules.card.models import Template
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def compat_seed(client: AsyncClient, db):
    """创建兼容层测试所需的学校+用户+考试+科目。"""
    school = School(id="cs1", name="兼容测试校", code="COMPAT01")
    db.add(school)
    await db.commit()

    user = User(id="cu1", username="compat_user", display_name="兼容用户")
    user.set_password("pass123")
    db.add(user)
    await db.commit()

    role = UserRole(user_id="cu1", role="principal", school_id="cs1", is_primary=True)
    db.add(role)
    await db.commit()

    exam = Exam(id="ce1", name="兼容测试考试", school_id="cs1")
    db.add(exam)
    await db.commit()

    subject = Subject(id="csub1", exam_id="ce1", name="数学", code="SX", school_id="cs1")
    db.add(subject)
    await db.commit()

    tpl = Template(
        subject_id="csub1", side="A", school_id="cs1",
        image_width=3308, image_height=2308,
        anchors=[{"id": "TL", "cx": 102, "cy": 97}],
        regions=[{"id": "Q01", "type": "subjective", "rect": {"x1": 100, "y1": 200, "x2": 500, "y2": 600}, "question_id": "q1"}],
    )
    db.add(tpl)
    await db.commit()

    return {"school_id": "cs1", "user_id": "cu1", "exam_id": "ce1", "subject_id": "csub1"}


class TestCompatLogin:
    async def test_login_with_school_code(self, client: AsyncClient, compat_seed):
        """paper-seg 传 school_code，兼容层忽略并正常返回 JWT。"""
        resp = await client.post("/api/auth/login", json={
            "school_code": "COMPAT01",
            "username": "compat_user",
            "password": "pass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_login_wrong_password(self, client: AsyncClient, compat_seed):
        resp = await client.post("/api/auth/login", json={
            "school_code": "COMPAT01",
            "username": "compat_user",
            "password": "wrong",
        })
        assert resp.status_code == 401


class TestCompatExams:
    async def _login(self, client: AsyncClient) -> dict:
        resp = await client.post("/api/auth/login", json={
            "school_code": "COMPAT01",
            "username": "compat_user",
            "password": "pass123",
        })
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_list_exams(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/exams", headers=headers)
        assert resp.status_code == 200
        exams = resp.json()
        assert len(exams) == 1
        assert exams[0]["id"] == "ce1"
        assert exams[0]["name"] == "兼容测试考试"

    async def test_list_subjects(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/exams/ce1/subjects", headers=headers)
        assert resp.status_code == 200
        subjects = resp.json()
        assert len(subjects) == 1
        assert subjects[0]["name"] == "数学"

    async def test_list_subjects_wrong_exam(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/exams/nonexist/subjects", headers=headers)
        assert resp.status_code == 404


class TestCompatTemplate:
    async def _login(self, client: AsyncClient) -> dict:
        resp = await client.post("/api/auth/login", json={
            "school_code": "X", "username": "compat_user", "password": "pass123",
        })
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    async def test_get_template(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/templates/csub1/A", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["image_size"]["width"] == 3308
        assert data["image_size"]["height"] == 2308
        assert len(data["anchors"]) == 1
        assert data["anchors"][0]["id"] == "TL"
        assert len(data["regions"]) == 1
        assert data["regions"][0]["type"] == "subjective"

    async def test_get_template_not_found(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.get("/api/templates/csub1/B", headers=headers)
        assert resp.status_code == 404


from edu_cloud.modules.exam.models import Question


class TestCompatScan:
    async def _login(self, client: AsyncClient) -> dict:
        resp = await client.post("/api/auth/login", json={
            "school_code": "X", "username": "compat_user", "password": "pass123",
        })
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    async def test_create_scan_task(self, client: AsyncClient, compat_seed):
        headers = await self._login(client)
        resp = await client.post("/api/scan/tasks", json={
            "subject_id": "csub1", "side": "A", "total_images": 30,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_images"] == 30
        assert "id" in data

    async def test_upload_image(self, client: AsyncClient, compat_seed, db):
        q = Question(id="cq1", subject_id="csub1", name="17", question_type="essay", max_score=10, school_id="cs1")
        db.add(q)
        await db.commit()

        headers = await self._login(client)
        resp = await client.post("/api/scan/upload",
            data={"exam_id": "ce1", "subject_id": "csub1", "student_id": "STU001", "question_id": "cq1"},
            files={"image": ("crop.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")},
            headers=headers,
        )
        assert resp.status_code == 201
        assert "image_path" in resp.json()

    async def test_upload_image_invalid_exam(self, client: AsyncClient, compat_seed, db):
        """F003: 不存在的 exam_id 返回 404。"""
        q = Question(id="cq1", subject_id="csub1", name="17", question_type="essay", max_score=10, school_id="cs1")
        db.add(q)
        await db.commit()

        headers = await self._login(client)
        resp = await client.post("/api/scan/upload",
            data={"exam_id": "nonexist", "subject_id": "csub1", "student_id": "STU001", "question_id": "cq1"},
            files={"image": ("crop.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_upload_image_cross_subject_question(self, client: AsyncClient, compat_seed, db):
        """F003-R2: 跨科目的 question_id 返回 404（归属链校验）。"""
        # cq_other 属于另一个 subject，不应通过 csub1 的校验
        other_sub = Subject(id="csub_other", exam_id="ce1", name="英语", code="YY", school_id="cs1")
        db.add(other_sub)
        await db.commit()
        q_other = Question(id="cq_other", subject_id="csub_other", name="1", question_type="essay", max_score=5, school_id="cs1")
        db.add(q_other)
        await db.commit()

        headers = await self._login(client)
        resp = await client.post("/api/scan/upload",
            data={"exam_id": "ce1", "subject_id": "csub1", "student_id": "STU001", "question_id": "cq_other"},
            files={"image": ("crop.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_upload_objective(self, client: AsyncClient, compat_seed, db):
        q = Question(id="cq2", subject_id="csub1", name="1", question_type="choice",
                     max_score=3, correct_answer="B", school_id="cs1")
        db.add(q)
        await db.commit()

        headers = await self._login(client)
        resp = await client.post("/api/scan/upload-objective", json={
            "exam_id": "ce1", "subject_id": "csub1", "student_id": "STU002",
            "is_absent": False,
            "answers": [{"question_id": "cq2", "detected_answer": "B", "fill_ratios": {"A": 0.1, "B": 0.9}, "anomaly": True}],
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_score"] == 3
        assert data["is_absent"] is False
        assert len(data["results"]) == 1
        assert data["results"][0]["is_correct"] is True

        # F002-R2: verify DB persistence of anomaly/fill_ratios
        from edu_cloud.modules.scan.models import StudentAnswer
        from sqlalchemy import select as sa_select
        row = (await db.execute(
            sa_select(StudentAnswer).where(
                StudentAnswer.student_id == "STU002", StudentAnswer.question_id == "cq2"
            )
        )).scalar_one()
        assert row.is_anomaly is True
        assert row.fill_ratios == {"A": 0.1, "B": 0.9}
        assert row.score == 3

    async def test_upload_objective_absent(self, client: AsyncClient, compat_seed, db):
        """F002: 缺考路径 — is_absent=True 为所有题落 0 分。"""
        q = Question(id="cq3", subject_id="csub1", name="2", question_type="choice",
                     max_score=3, correct_answer="A", school_id="cs1")
        db.add(q)
        await db.commit()

        headers = await self._login(client)
        resp = await client.post("/api/scan/upload-objective", json={
            "exam_id": "ce1", "subject_id": "csub1", "student_id": "STU003",
            "is_absent": True, "answers": [],
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_absent"] is True
        assert data["results"] == []
        assert data["total_score"] == 0

        # F002-R2: verify DB persistence of is_absent
        from edu_cloud.modules.scan.models import StudentAnswer
        from sqlalchemy import select as sa_select
        rows = (await db.execute(
            sa_select(StudentAnswer).where(StudentAnswer.student_id == "STU003")
        )).scalars().all()
        assert len(rows) == 1  # one question in this subject
        assert rows[0].is_absent is True
        assert rows[0].score == 0

    async def test_upload_objective_wrong_answer(self, client: AsyncClient, compat_seed, db):
        """选择题答错 → score=0。"""
        q = Question(id="cq4", subject_id="csub1", name="3", question_type="choice",
                     max_score=5, correct_answer="C", school_id="cs1")
        db.add(q)
        await db.commit()

        headers = await self._login(client)
        resp = await client.post("/api/scan/upload-objective", json={
            "exam_id": "ce1", "subject_id": "csub1", "student_id": "STU004",
            "is_absent": False,
            "answers": [{"question_id": "cq4", "detected_answer": "A"}],
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_score"] == 0
        assert data["results"][0]["is_correct"] is False


class TestPublishStatus:
    """F004: publish 端点 status 限制回归测试。"""

    async def _setup_publish_data(self, client, db):
        """创建 publish 所需的完整数据链。"""
        school = School(id="ps1", name="发布测试校", code="PUB01")
        db.add(school)
        await db.commit()

        user = User(id="pu1", username="pub_user", display_name="发布用户")
        user.set_password("pass123")
        db.add(user)
        await db.commit()

        role = UserRole(user_id="pu1", role="principal", school_id="ps1", is_primary=True)
        db.add(role)
        await db.commit()

        exam = Exam(id="pe1", name="发布测试考试", school_id="ps1")
        db.add(exam)
        await db.commit()

        subject = Subject(id="psub1", exam_id="pe1", name="语文", code="YW", school_id="ps1")
        db.add(subject)
        await db.commit()

        # Login
        resp = await client.post("/api/auth/login", json={
            "school_code": "X", "username": "pub_user", "password": "pass123",
        })
        headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        return exam, headers

    async def test_grading_status_rejects_publish(self, client: AsyncClient, db):
        """grading/completed 状态拒绝发布。"""
        exam, headers = await self._setup_publish_data(client, db)
        exam.status = "grading"
        await db.commit()

        resp = await client.post("/api/v1/card/publish", json={
            "exam_id": "pe1", "subject_id": "psub1",
            "html": "<html></html>", "paper_size": "A3",
        }, headers=headers)
        assert resp.status_code == 400
        assert "grading" in resp.json()["detail"]

    async def test_completed_status_rejects_publish(self, client: AsyncClient, db):
        """completed 状态拒绝发布。"""
        exam, headers = await self._setup_publish_data(client, db)
        exam.status = "completed"
        await db.commit()

        resp = await client.post("/api/v1/card/publish", json={
            "exam_id": "pe1", "subject_id": "psub1",
            "html": "<html></html>", "paper_size": "A3",
        }, headers=headers)
        assert resp.status_code == 400
        assert "completed" in resp.json()["detail"]
