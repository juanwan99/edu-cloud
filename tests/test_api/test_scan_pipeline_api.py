"""扫描流水线 API 测试。"""
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def scan_seed(client, db, tmp_path):
    """创建扫描测试种子数据 + 假扫描目录。"""
    school = School(id="scan_s1", name="扫描测试校", code="SCAN01")
    db.add(school)
    await db.flush()

    user = User(id="scan_u1", username="scan_user", display_name="扫描用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id="scan_u1", role="principal", school_id="scan_s1", is_primary=True))
    await db.commit()

    exam = Exam(id="scan_e1", name="扫描测试考试", school_id="scan_s1")
    db.add(exam)
    await db.flush()

    subject = Subject(id="scan_sub1", exam_id="scan_e1", name="地理", code="DL", school_id="scan_s1")
    db.add(subject)
    await db.commit()

    # 创建假扫描图
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    for i in range(3):
        img = Image.new("RGB", (200, 150), (240, 240, 240))
        img.save(scan_dir / f"STU{i + 1:03d}A.png")

    token = create_access_token({"sub": "scan_u1", "role": "principal", "active_role_id": "dummy"})
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "headers": headers,
        "scan_dir": str(scan_dir),
        "subject_id": "scan_sub1",
        "exam_id": "scan_e1",
    }


class TestPipelineProgress:
    async def test_progress_idle(self, client, scan_seed):
        resp = await client.get("/api/v1/scan/pipeline/progress", headers=scan_seed["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("idle", "completed")

    async def test_start_no_template(self, client, scan_seed, tmp_path, monkeypatch):
        from edu_cloud.config import settings
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

        resp = await client.post("/api/v1/scan/pipeline/start", json={
            "subject_id": scan_seed["subject_id"],
            "side": "A",
            "image_dir": scan_seed["scan_dir"],
        }, headers=scan_seed["headers"])
        assert resp.status_code == 404
        assert "模板不存在" in resp.json()["detail"]

    async def test_start_nonexistent_dir(self, client, scan_seed):
        resp = await client.post("/api/v1/scan/pipeline/start", json={
            "subject_id": scan_seed["subject_id"],
            "side": "A",
            "image_dir": "/nonexistent/dir",
        }, headers=scan_seed["headers"])
        assert resp.status_code == 403


class TestUploadScanFolder:
    async def test_upload_normalizes_jingyan_page_names(self, client, scan_seed, db, tmp_path, monkeypatch):
        from edu_cloud.config import settings

        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))

        resp = await client.post(
            "/api/v1/scan/pipeline/upload-folder",
            data={"exam_id": scan_seed["exam_id"]},
            files=[
                ("files", ("语文/2025001_00_1_0.PNG", BytesIO(b"a"), "image/png")),
                ("files", ("语文/2025001_00_2_1.PNG", BytesIO(b"b"), "image/png")),
            ],
            headers=scan_seed["headers"],
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["saved"] == 2
        assert data["normalized"] == 2

        subject_dir = Path(data["dir_path"]) / "语文"
        assert (subject_dir / "2025001A.png").exists()
        assert (subject_dir / "2025001B.png").exists()
        assert not (subject_dir / "2025001_00_1_0.PNG").exists()

        scan_resp = await client.post(
            "/api/v1/scan/pipeline/scan-dir",
            json={"dir_path": data["dir_path"]},
            headers=scan_seed["headers"],
        )
        assert scan_resp.status_code == 200
        assert scan_resp.json()["subjects"][0]["student_count"] == 1
        assert scan_resp.json()["created_subjects"] == 1

        rows = (await db.execute(
            select(Subject).where(Subject.exam_id == scan_seed["exam_id"])
        )).scalars().all()
        assert any(s.name == subject_dir.name and s.code == "YW" for s in rows)


class TestSaveCVTemplate:
    async def test_save_cv_template_syncs_existing_questions_and_ignores_barcode(self, client, scan_seed, db):
        db.add_all([
            Question(
                id="scan_q2",
                subject_id=scan_seed["subject_id"],
                name="2",
                question_type="choice",
                max_score=2,
                school_id="scan_s1",
            ),
        ])
        await db.commit()

        resp = await client.post(
            "/api/v1/scan/pipeline/save-cv-template",
            json={
                "subject_id": scan_seed["subject_id"],
                "side": "A",
                "width": 100,
                "height": 100,
                "regions": [
                    {"id": "BC", "type": "barcode", "qno": 3, "score": 0},
                    {"id": "R15", "type": "choice_group", "start_no": 1, "rows": 3, "score": 3},
                    {"id": "R02", "type": "subjective", "qno": 2, "question_type": "essay", "score": 6},
                ],
            },
            headers=scan_seed["headers"],
        )

        assert resp.status_code == 200

        q2 = (await db.execute(
            select(Question).where(Question.id == "scan_q2")
        )).scalar_one()
        assert q2.question_type == "essay"
        assert q2.max_score == 6

        q1 = (await db.execute(
            select(Question).where(
                Question.subject_id == scan_seed["subject_id"],
                Question.name == "1",
            )
        )).scalar_one()
        assert q1.question_type == "choice"
        assert q1.max_score == 3

        tpl = (await db.execute(
            select(Template).where(
                Template.subject_id == scan_seed["subject_id"],
                Template.side == "A",
            )
        )).scalar_one()
        by_id = {r["id"]: r for r in tpl.regions}
        assert "question_id" not in by_id["BC"]
        assert "question_ids" not in by_id["R15"]
        assert by_id["R02"]["question_id"] == "scan_q2"


class TestVerifyTemplate:
    async def test_expands_choice_group_and_prefers_explicit_subjective_region(self, client, scan_seed, db):
        db.add_all([
            Question(
                id="verify_q1",
                subject_id=scan_seed["subject_id"],
                name="1",
                question_type="choice",
                max_score=3,
                school_id="scan_s1",
            ),
            Question(
                id="verify_q2",
                subject_id=scan_seed["subject_id"],
                name="2",
                question_type="essay",
                max_score=6,
                school_id="scan_s1",
            ),
            Question(
                id="verify_q3",
                subject_id=scan_seed["subject_id"],
                name="3",
                question_type="choice",
                max_score=3,
                school_id="scan_s1",
            ),
            Question(
                id="verify_q4",
                subject_id=scan_seed["subject_id"],
                name="4",
                question_type="choice",
                max_score=3,
                school_id="scan_s1",
            ),
        ])
        db.add(Template(
            subject_id=scan_seed["subject_id"],
            side="A",
            regions=[
                {"id": "BC", "type": "barcode", "qno": 3, "score": 0},
                {"id": "R15", "type": "choice_group", "qno": 24, "start_no": 1, "rows": 3, "score": 3},
                {
                    "id": "R02",
                    "type": "subjective",
                    "qno": "2",
                    "question_type": "essay",
                    "score": 6,
                    "question_id": "verify_q2",
                },
                {"id": "R05", "type": "subjective", "qno": "5", "question_type": "essay", "score": 4},
            ],
            image_width=100,
            image_height=100,
            school_id="scan_s1",
        ))
        await db.commit()

        resp = await client.get(
            "/api/v1/scan/pipeline/verify-template",
            params={"subject_id": scan_seed["subject_id"]},
            headers=scan_seed["headers"],
        )

        assert resp.status_code == 200
        by_qno = {item["qno"]: item for item in resp.json()["items"]}
        assert "24" not in by_qno
        assert by_qno["1"]["status"] == "match"
        assert by_qno["1"]["template"]["type"] == "choice_group"
        assert by_qno["2"]["status"] == "match"
        assert by_qno["2"]["template"]["type"] == "subjective"
        assert by_qno["2"]["template"]["region_ids"] == ["R02"]
        assert by_qno["3"]["status"] == "match"
        assert by_qno["4"]["status"] == "missing_template"
        assert by_qno["5"]["status"] == "missing_question"


class TestPipelineFilenamePairing:
    def test_allows_explicit_student_number_pairs_without_db_students(self, tmp_path):
        from edu_cloud.modules.scan import pipeline_service

        (tmp_path / "2025001A.png").write_bytes(b"a")
        (tmp_path / "2025001B.png").write_bytes(b"b")

        ok, info = pipeline_service.can_use_filename_pairing_for_b_side(str(tmp_path), set())

        assert ok is True
        assert info["reason"] == "paired_explicit_filenames"

    def test_rejects_short_sequence_pairs_without_db_students(self, tmp_path):
        from edu_cloud.modules.scan import pipeline_service

        (tmp_path / "0001A.png").write_bytes(b"a")
        (tmp_path / "0001B.png").write_bytes(b"b")

        ok, info = pipeline_service.can_use_filename_pairing_for_b_side(str(tmp_path), set())

        assert ok is False
        assert info["reason"] == "paired_stems_look_like_sequence_numbers"

    def test_allows_explicit_filename_student_ids(self, tmp_path):
        from edu_cloud.modules.scan import pipeline_service

        (tmp_path / "2025001A.png").write_bytes(b"a")
        (tmp_path / "2025002A.png").write_bytes(b"b")

        ok, info = pipeline_service.can_use_filename_student_ids(str(tmp_path), "A")

        assert ok is True
        assert info["reason"] == "explicit_filename_student_numbers"

    def test_rejects_short_sequence_filename_student_ids(self, tmp_path):
        from edu_cloud.modules.scan import pipeline_service

        (tmp_path / "0001A.png").write_bytes(b"a")
        (tmp_path / "0002A.png").write_bytes(b"b")

        ok, info = pipeline_service.can_use_filename_student_ids(str(tmp_path), "A")

        assert ok is False
        assert info["reason"] == "filenames_not_explicit_student_numbers"

    def test_requires_known_student_numbers_when_db_students_exist(self, tmp_path):
        from edu_cloud.modules.scan import pipeline_service

        (tmp_path / "2025001A.png").write_bytes(b"a")
        (tmp_path / "2025001B.png").write_bytes(b"b")

        ok, info = pipeline_service.can_use_filename_pairing_for_b_side(
            str(tmp_path), {"2025001"}
        )

        assert ok is True
        assert info["reason"] == "paired_known_student_numbers"


class TestImportTpl:
    @pytest.mark.skipif(
        not __import__("os").path.exists(r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl"),
        reason="Real tpl file not available",
    )
    async def test_import_real_tpl(self, client, scan_seed):
        resp = await client.post("/api/v1/scan/pipeline/import-tpl", json={
            "tpl_path": r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl",
            "subject_id": scan_seed["subject_id"],
            "side": "A",
        }, headers=scan_seed["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["regions"] == 14  # 10 subjective + 4 choice_groups
        assert data["anchors"] == 4
