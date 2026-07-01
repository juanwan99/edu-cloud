"""扫描流水线 API 测试。"""
from io import BytesIO
from pathlib import Path
from types import ModuleType
import sys

import pytest
from PIL import Image
from sqlalchemy import select
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Student
from edu_cloud.shared.auth import create_access_token

pytest_plugins = ("pytest_asyncio.plugin",)


@pytest.fixture(autouse=True)
def _stub_pyzbar_for_scan_pipeline_api(monkeypatch):
    fake_pyzbar = ModuleType("pyzbar.pyzbar")
    fake_pyzbar.decode = lambda *_args, **_kwargs: []
    fake_package = ModuleType("pyzbar")
    fake_package.pyzbar = fake_pyzbar
    monkeypatch.setitem(sys.modules, "pyzbar", fake_package)
    monkeypatch.setitem(sys.modules, "pyzbar.pyzbar", fake_pyzbar)


@pytest.fixture
async def scan_seed(client, db, tmp_path, monkeypatch):
    """创建扫描测试种子数据 + 假扫描目录。"""
    from edu_cloud.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    school = School(id="scan_s1", name="扫描测试校", code="SCAN01")
    db.add(school)
    await db.flush()

    user = User(id="scan_u1", username="scan_user", display_name="扫描用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    role = UserRole(user_id="scan_u1", role="principal", school_id="scan_s1", is_primary=True)
    db.add(role)
    await db.commit()

    exam = Exam(id="scan_e1", name="扫描测试考试", school_id="scan_s1")
    db.add(exam)
    await db.flush()

    subject = Subject(id="scan_sub1", exam_id="scan_e1", name="地理", code="DL", school_id="scan_s1")
    db.add(subject)
    await db.commit()

    # 创建假扫描图
    scan_dir = tmp_path / "scan_s1" / "scans"
    scan_dir.mkdir(parents=True)
    for i in range(3):
        img = Image.new("RGB", (200, 150), (240, 240, 240))
        img.save(scan_dir / f"STU{i + 1:03d}A.png")

    token = create_access_token({
        "sub": "scan_u1",
        "role": "principal",
        "school_id": "scan_s1",
        "active_role_id": role.id,
    })
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


class TestPipelineIdentityFailClosed:
    async def _start_and_run_identity_case(
        self,
        client,
        scan_seed,
        db,
        tmp_path,
        monkeypatch,
        *,
        file_stem: str,
        raw_student_number: str,
        barcode_status: str = "fallback_none",
        roster_query_fails: bool = False,
    ) -> dict:
        from unittest.mock import patch
        from edu_cloud.config import settings
        from edu_cloud.modules.scan import pipeline_service

        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
        pipeline_service._queue.clear()
        pipeline_service._progress.clear()

        case_dir = tmp_path / "scan_s1" / "identity"
        case_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (200, 150), (240, 240, 240)).save(case_dir / f"{file_stem}A.png")

        db.add(Question(
            id="scan_identity_q1",
            subject_id=scan_seed["subject_id"],
            name="1",
            question_type="essay",
            max_score=10,
            school_id="scan_s1",
        ))
        db.add(Template(
            subject_id=scan_seed["subject_id"],
            side="A",
            image_width=200,
            image_height=150,
            anchors=[],
            regions=[
                {"id": "BC", "type": "barcode", "rect": {"x1": 0, "y1": 0, "x2": 20, "y2": 20}},
                {
                    "id": "R01",
                    "type": "subjective",
                    "rect": {"x1": 20, "y1": 20, "x2": 120, "y2": 100},
                    "question_id": "scan_identity_q1",
                },
            ],
            school_id="scan_s1",
        ))
        await db.commit()

        def fake_process_one_image(*_args, **_kwargs):
            return {
                "file": f"{file_stem}A.png",
                "student_id": raw_student_number,
                "crops": [{"region_id": "R01", "path": f"/tmp/{file_stem}_R01.png"}],
                "objective_results": [],
                "errors": [],
                "barcode_status": barcode_status,
            }

        roster_patch = patch.object(
            pipeline_service,
            "_load_student_number_map",
            side_effect=RuntimeError("student roster query failed"),
        ) if roster_query_fails else patch.object(
            pipeline_service,
            "_load_student_number_map",
            wraps=pipeline_service._load_student_number_map,
        )

        with patch.object(pipeline_service, "ensure_queue_running", lambda: None), \
             patch.object(pipeline_service, "process_one_image", side_effect=fake_process_one_image), \
             roster_patch:
            resp = await client.post("/api/v1/scan/pipeline/start", json={
                "subject_id": scan_seed["subject_id"],
                "side": "A",
                "image_dir": str(case_dir),
            }, headers=scan_seed["headers"])
            assert resp.status_code == 200, resp.text
            results = await pipeline_service.run_queue()

        assert len(results) == 1
        return results[0]

    async def test_start_fails_closed_when_student_roster_query_fails(
        self, client, scan_seed, db, tmp_path, monkeypatch
    ):
        result = await self._start_and_run_identity_case(
            client,
            scan_seed,
            db,
            tmp_path,
            monkeypatch,
            file_stem="ROSTERDOWN001",
            raw_student_number="ROSTERDOWN001",
            roster_query_fails=True,
        )

        rows = (await db.execute(select(StudentAnswer))).scalars().all()
        assert rows == []
        assert result["processed"] == 0
        assert result["failed"] == 1

    async def test_start_skips_save_when_filename_student_number_not_in_roster(
        self, client, scan_seed, db, tmp_path, monkeypatch
    ):
        db.add(Student(
            id="scan_student_other",
            name="Other Student",
            student_number="OTHER001",
            school_id="scan_s1",
        ))
        await db.commit()

        result = await self._start_and_run_identity_case(
            client,
            scan_seed,
            db,
            tmp_path,
            monkeypatch,
            file_stem="UNKNOWN001",
            raw_student_number="UNKNOWN001",
        )

        rows = (await db.execute(select(StudentAnswer))).scalars().all()
        assert rows == []
        assert result["processed"] == 0
        assert result["failed"] == 1
        assert result["unmatched_student_files"] == [{
            "file": "UNKNOWN001A.png",
            "student_number": "UNKNOWN001",
        }]

    async def test_start_skips_save_when_student_roster_is_empty(
        self, client, scan_seed, db, tmp_path, monkeypatch
    ):
        result = await self._start_and_run_identity_case(
            client,
            scan_seed,
            db,
            tmp_path,
            monkeypatch,
            file_stem="LEGACY001",
            raw_student_number="LEGACY001",
        )

        rows = (await db.execute(select(StudentAnswer))).scalars().all()
        assert rows == []
        assert result["processed"] == 0
        assert result["failed"] == 1
        assert result["students"] == []
        assert result["unmatched_student_files"] == [{
            "file": "LEGACY001A.png",
            "student_number": "LEGACY001",
        }]

    async def test_start_skips_save_when_barcode_fallback_matches_known_student_number(
        self, client, scan_seed, db, tmp_path, monkeypatch
    ):
        from edu_cloud.modules.scan import pipeline_service

        db.add(Student(
            id="scan_student_1",
            name="Student One",
            student_number="KNOWN001",
            school_id="scan_s1",
        ))
        await db.commit()

        result = await self._start_and_run_identity_case(
            client,
            scan_seed,
            db,
            tmp_path,
            monkeypatch,
            file_stem="KNOWN001",
            raw_student_number="KNOWN001",
            barcode_status="fallback_none",
        )

        rows = (await db.execute(select(StudentAnswer))).scalars().all()
        assert rows == []
        assert result["processed"] == 0
        assert result["failed"] == 1
        assert result["students"] == []
        assert result["barcode_failed"] == 1
        assert result["barcode_failed_files"] == [{
            "file": "KNOWN001A.png",
            "fallback_student_id": "KNOWN001",
            "status": "fallback_none",
        }]
        progress = pipeline_service.get_progress()
        assert progress["warnings"] == [{
            "file": "KNOWN001A.png",
            "message": (
                "barcode read failed with status fallback_none; "
                "refusing to save filename fallback result"
            ),
        }]

    async def test_start_saves_known_explicit_filename_student_number_as_student_uuid(
        self, client, scan_seed, db, tmp_path, monkeypatch
    ):
        db.add(Student(
            id="scan_student_1",
            name="Student One",
            student_number="KNOWN001",
            school_id="scan_s1",
        ))
        await db.commit()

        result = await self._start_and_run_identity_case(
            client,
            scan_seed,
            db,
            tmp_path,
            monkeypatch,
            file_stem="KNOWN001",
            raw_student_number="KNOWN001",
            barcode_status="filename_explicit",
        )

        rows = (await db.execute(select(StudentAnswer))).scalars().all()
        assert len(rows) == 1
        assert rows[0].student_id == "scan_student_1"
        assert result["processed"] == 1
        assert result["failed"] == 0
        assert result["students"] == ["scan_student_1"]


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


class TestPipelineObjectiveOwnershipChain:
    """F-002: /start 的 question_ids 模板分支必须按 subject_id 过滤，
    禁止把同校其他 subject 的 question 写入当前 subject（归属链）。
    """

    async def test_start_excludes_cross_subject_question_ids(
        self, client, scan_seed, db, monkeypatch
    ):
        from unittest.mock import patch
        from edu_cloud.config import settings
        from edu_cloud.modules.scan import pipeline_service

        monkeypatch.setattr(settings, "UPLOAD_DIR", str(Path(scan_seed["scan_dir"]).parents[1]))

        # 当前 subject（地理）的客观题
        q_own = Question(
            id="q_own_geo", subject_id=scan_seed["subject_id"], name="1",
            question_type="choice", max_score=3.0, correct_answer="A",
            school_id="scan_s1",
        )
        # 同校另一 subject 的客观题（跨 subject，应被排除）
        other_subject = Subject(
            id="scan_sub2", exam_id=scan_seed["exam_id"], name="历史",
            code="LS", school_id="scan_s1",
        )
        db.add_all([q_own, other_subject])
        await db.flush()
        q_other = Question(
            id="q_other_his", subject_id="scan_sub2", name="1",
            question_type="choice", max_score=3.0, correct_answer="B",
            school_id="scan_s1",
        )
        db.add(q_other)

        # 模板 region 显式引用两个 question（一个跨 subject）
        tpl = Template(
            subject_id=scan_seed["subject_id"], side="A",
            image_width=200, image_height=150, anchors=[],
            regions=[{
                "id": "OBJ01", "type": "choice_group",
                "rect": {"x1": 100, "y1": 10, "x2": 190, "y2": 70},
                "cols": 4, "rows": 2, "qg_indexno": 1,
                "question_ids": ["q_own_geo", "q_other_his"],
            }],
            school_id="scan_s1",
        )
        db.add(tpl)
        await db.commit()

        captured = {}

        def _capture_factory(*args, **kwargs):
            captured["questions_by_group"] = kwargs.get("questions_by_group")
            async def _noop(**_):
                return None
            return _noop

        with patch(
            "edu_cloud.modules.scan.pipeline_router.build_pipeline_save_objective_fn",
            side_effect=_capture_factory,
        ), patch.object(pipeline_service, "enqueue_pipeline", lambda **kw: None):
            resp = await client.post("/api/v1/scan/pipeline/start", json={
                "subject_id": scan_seed["subject_id"],
                "side": "A",
                "image_dir": scan_seed["scan_dir"],
            }, headers=scan_seed["headers"])

        assert resp.status_code == 200, resp.text
        qbg = captured.get("questions_by_group")
        assert qbg is not None, "build_pipeline_save_objective_fn 未被调用（本 subject 题目应非空）"
        all_qids = {q["id"] for group in qbg.values() for q in group}
        assert "q_own_geo" in all_qids
        assert "q_other_his" not in all_qids, "跨 subject 的 question 不得进入 questions_by_group"


# ---------- D-03L module boundary invariants ----------

def test_scan_module_has_no_direct_exam_card_student_imports():
    """D-03L invariant: scan must use the scan_workflow facade for
    exam/card/student data access instead of importing those modules directly.
    """
    import re
    from pathlib import Path

    scan_dir = (
        Path(__file__).resolve().parents[2]
        / "src" / "edu_cloud" / "modules" / "scan"
    )
    pattern = re.compile(
        r"(?:from|import)\s+edu_cloud\.modules\.(?:exam|card|student)\b"
    )
    offenders = []
    for py in sorted(scan_dir.rglob("*.py")):
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "scan must not import exam/card/student directly; use services.scan_workflow:\n"
        + "\n".join(offenders)
    )


def test_scan_workflow_facade_reexports_owner_objects():
    """D-03L invariant: scan_workflow is a pure re-export facade whose
    exported symbols are exactly the owner-module objects.
    """
    from edu_cloud.services import scan_workflow
    from edu_cloud.modules.card.models import Template
    from edu_cloud.modules.exam.models import Exam, Question, QUESTION_TYPES_OBJECTIVE, Subject
    from edu_cloud.modules.student.models import Student

    assert scan_workflow.Exam is Exam
    assert scan_workflow.Subject is Subject
    assert scan_workflow.Question is Question
    assert scan_workflow.QUESTION_TYPES_OBJECTIVE is QUESTION_TYPES_OBJECTIVE
    assert scan_workflow.Template is Template
    assert scan_workflow.Student is Student
