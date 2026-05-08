"""答题卡生成 API 测试。"""
import pytest
from httpx import AsyncClient
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def seed_subject(client: AsyncClient, db):
    """创建测试学校/用户/考试/科目，返回 (headers, exam_id, subject_id)。"""
    school = School(id="s1", name="测试学校", code="TEST01")
    db.add(school)
    await db.commit()

    user = User(id="u1", username="admin", display_name="管理员")
    user.set_password("123456")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id="s1", is_primary=True))
    await db.flush()

    exam = Exam(id="e1", name="期中考试", school_id="s1")
    db.add(exam)
    await db.commit()

    subject = Subject(id="sub1", exam_id="e1", name="生物", code="SW", school_id="s1")
    db.add(subject)
    await db.commit()

    token = create_access_token({"sub": "u1", "school_id": "s1", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    return headers, "e1", "sub1"


class TestCardBarcode:
    async def test_barcode_upload(self, client: AsyncClient, seed_subject, tmp_path):
        headers, _, _ = seed_subject
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["准考证号", "姓名"])
        ws.append(["53437193", "张三"])
        ws.append(["53437173", "李四"])
        fp = tmp_path / "students.xlsx"
        wb.save(fp)

        with open(fp, "rb") as f:
            resp = await client.post(
                "/api/v1/card/barcode",
                files={"file": ("students.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"barcode_column": "准考证号", "name_column": "姓名"},
                headers=headers,
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"


def _make_tpl_json(tmp_path, name="test.tpl"):
    """创建最小 .tpl JSON 文件用于测试。"""
    import json
    tpl_data = {
        "tplInfo": {"iwidth": 1654, "iheight": 2283},
        "datas": {
            "tplLocsList": [
                {"loc_no": "0101", "location": "(114,92)-(178,123)"},
                {"loc_no": "0102", "location": "(1476,92)-(1540,123)"},
                {"loc_no": "0103", "location": "(1479,2185)-(1543,2216)"},
                {"loc_no": "0104", "location": "(114,2185)-(178,2216)"},
            ],
            "tplObjqueGList": [
                {
                    "qg_indexno": 1, "que_count": 5, "opt_count": 4,
                    "opt_symbol": "A,B,C,D", "opt_type": "单选",
                    "location": "(185,825)-(411,964)",
                },
            ],
            "tplSubqueList": [
                {"que_name": "17", "location": "(101,1048)-(1568,1749)", "inpage": 0, "score_val": "12"},
                {"que_name": "18", "location": "(101,1693)-(1562,2188)", "inpage": 0, "score_val": "12"},
            ],
        },
        "images": [],
    }
    fp = tmp_path / name
    fp.write_text(json.dumps(tpl_data), encoding="utf-8")
    return fp


class TestSkeletonAPI:
    async def test_import_tpl(self, client: AsyncClient, seed_subject, tmp_path):
        headers, _, _ = seed_subject
        fp = _make_tpl_json(tmp_path, "bio.tpl")
        with open(fp, "rb") as f:
            resp = await client.post(
                "/api/v1/card/skeleton/import",
                files={"file": ("bio.tpl", f, "application/octet-stream")},
                data={"subject_code": "SW"},
                headers=headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject_code"] == "SW"
        assert len(data["skeleton_data"]["anchors"]) == 4

    async def test_list_skeletons(self, client: AsyncClient, seed_subject, tmp_path):
        headers, _, _ = seed_subject
        fp = _make_tpl_json(tmp_path)
        with open(fp, "rb") as f:
            await client.post(
                "/api/v1/card/skeleton/import",
                files={"file": ("test.tpl", f, "application/octet-stream")},
                data={"subject_code": "YW"},
                headers=headers,
            )
        resp = await client.get("/api/v1/card/skeleton/list", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1

    async def test_get_skeleton(self, client: AsyncClient, seed_subject, tmp_path):
        headers, _, _ = seed_subject
        fp = _make_tpl_json(tmp_path)
        with open(fp, "rb") as f:
            await client.post(
                "/api/v1/card/skeleton/import",
                files={"file": ("test.tpl", f, "application/octet-stream")},
                data={"subject_code": "SX"},
                headers=headers,
            )
        resp = await client.get("/api/v1/card/skeleton/SX", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["subject_code"] == "SX"

    async def test_delete_skeleton(self, client: AsyncClient, seed_subject, tmp_path):
        headers, _, _ = seed_subject
        fp = _make_tpl_json(tmp_path)
        with open(fp, "rb") as f:
            await client.post(
                "/api/v1/card/skeleton/import",
                files={"file": ("test.tpl", f, "application/octet-stream")},
                data={"subject_code": "HX"},
                headers=headers,
            )
        resp = await client.delete("/api/v1/card/skeleton/HX", headers=headers)
        assert resp.status_code == 200
        resp = await client.get("/api/v1/card/skeleton/HX", headers=headers)
        assert resp.status_code == 404


class TestWordTemplateDownload:
    """GET /api/card/template/download?subject_id=xxx"""

    async def test_download_template(self, client: AsyncClient, seed_subject, db):
        """Should return a .docx file with #N. lines."""
        headers, exam_id, subject_id = seed_subject
        from edu_cloud.models.exam import Question
        for i in range(1, 4):
            q = Question(
                subject_id=subject_id,
                name=f"第{i}题",
                question_type="choice" if i <= 2 else "essay",
                max_score=5.0,
                school_id="s1",
            )
            db.add(q)
        await db.commit()

        resp = await client.get(
            f"/api/v1/card/template/download?subject_id={subject_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert "application/vnd.openxmlformats" in resp.headers["content-type"]

    async def test_no_questions_400(self, client: AsyncClient, seed_subject):
        """Should return 400 if subject has no questions."""
        headers, _, subject_id = seed_subject
        resp = await client.get(
            f"/api/v1/card/template/download?subject_id={subject_id}",
            headers=headers,
        )
        assert resp.status_code == 400


class TestCardGenerateV2:
    async def test_generate_v2_basic(self, client: AsyncClient, seed_subject, tmp_path, db):
        headers, exam_id, subject_id = seed_subject
        # 导入骨架
        fp = _make_tpl_json(tmp_path, "bio.tpl")
        with open(fp, "rb") as f:
            await client.post(
                "/api/v1/card/skeleton/import",
                files={"file": ("bio.tpl", f, "application/octet-stream")},
                data={"subject_code": "SW"},
                headers=headers,
            )

        # 布局 JSON（模拟 /plan 返回）
        layout = {
            "slots": [
                {
                    "slot_id": "Q17",
                    "final_rect": {"x1": 101, "y1": 1048, "x2": 1568, "y2": 1749},
                    "sub_regions": [
                        {"id": "Q17_1", "name": "17(1)", "score": 4,
                         "rect": {"x1": 101, "y1": 1068, "x2": 1568, "y2": 1400},
                         "blanks": [{"x": 350, "y": 1240, "width": 280}]},
                        {"id": "Q17_2", "name": "17(2)", "score": 8,
                         "rect": {"x1": 101, "y1": 1400, "x2": 1568, "y2": 1749},
                         "type": "essay"},
                    ],
                }
            ],
            "validation": {"all_fit": True, "warnings": []},
        }

        resp = await client.post("/api/v1/card/generate/v2", json={
            "subject_code": "SW",
            "exam_id": exam_id,
            "subject_id": subject_id,
            "layout": layout,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"
        assert resp.headers.get("X-Template-Saved") == "true"

    async def test_generate_v2_saves_template(self, client: AsyncClient, seed_subject, tmp_path, db):
        headers, exam_id, subject_id = seed_subject
        # 导入骨架
        fp = _make_tpl_json(tmp_path, "bio.tpl")
        with open(fp, "rb") as f:
            await client.post(
                "/api/v1/card/skeleton/import",
                files={"file": ("bio.tpl", f, "application/octet-stream")},
                data={"subject_code": "SW"},
                headers=headers,
            )

        layout = {
            "slots": [{"slot_id": "Q17",
                        "final_rect": {"x1": 101, "y1": 1048, "x2": 1568, "y2": 1749},
                        "sub_regions": [{"id": "Q17_1", "name": "17(1)", "score": 10,
                                          "rect": {"x1": 101, "y1": 1068, "x2": 1568, "y2": 1749},
                                          "type": "essay"}]}],
            "validation": {"all_fit": True, "warnings": []},
        }
        await client.post("/api/v1/card/generate/v2", json={
            "subject_code": "SW", "exam_id": exam_id, "subject_id": subject_id, "layout": layout,
        }, headers=headers)

        # 验证 Template 写入
        resp = await client.get(f"/api/v1/templates/{subject_id}/A", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # anchors 应转换为 300 DPI
        assert len(data["anchors"]) == 4
        # regions 粒度到 sub_region
        assert any(r.get("id") == "Q17_1" for r in data["regions"])

    async def test_preview_v2_no_template_save(self, client: AsyncClient, seed_subject, tmp_path, db):
        headers, exam_id, subject_id = seed_subject
        fp = _make_tpl_json(tmp_path, "bio.tpl")
        with open(fp, "rb") as f:
            await client.post(
                "/api/v1/card/skeleton/import",
                files={"file": ("bio.tpl", f, "application/octet-stream")},
                data={"subject_code": "SW"},
                headers=headers,
            )

        layout = {
            "slots": [{"slot_id": "Q17",
                        "final_rect": {"x1": 101, "y1": 1048, "x2": 1568, "y2": 1749},
                        "sub_regions": [{"id": "Q17_1", "name": "17(1)", "score": 10,
                                          "rect": {"x1": 101, "y1": 1068, "x2": 1568, "y2": 1749},
                                          "type": "essay"}]}],
            "validation": {"all_fit": True, "warnings": []},
        }
        resp = await client.post("/api/v1/card/preview/v2", json={
            "subject_code": "SW", "exam_id": exam_id, "subject_id": subject_id, "layout": layout,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

        # Template 不应写入
        resp = await client.get(f"/api/v1/templates/{subject_id}/A", headers=headers)
        assert resp.status_code == 404


# --- Editor Layout API tests (TG-002) ---


class TestEditorLayout:
    @pytest.fixture(autouse=True)
    def _isolate_layout_dir(self, tmp_path, monkeypatch):
        """Use temp directory for editor layouts to avoid cross-test pollution."""
        import edu_cloud.modules.card.router as cards_mod
        monkeypatch.setattr(cards_mod, "_EDITOR_LAYOUT_DIR", tmp_path)

    async def test_get_layout_not_found(self, client: AsyncClient, seed_subject):
        """No saved layout → returns found=False (no fallback)."""
        headers, _, subject_id = seed_subject
        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is False

    async def test_save_and_load_layout(self, client: AsyncClient, seed_subject):
        """Save layout → load returns it."""
        headers, _, subject_id = seed_subject
        layout = {"paper": "A3", "sides": [{"side": "A", "columns": []}]}
        config = {"examTitle": "测试考试"}
        choices = [{"qno": 1, "options": 4}]

        resp = await client.put(f"/api/v1/card/editor-layout/{subject_id}", json={
            "layout": layout, "config": config, "choices": choices,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Load it back
        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["layout"]["paper"] == "A3"
        assert data["config"]["examTitle"] == "测试考试"
        assert data["choices"] == [{"qno": 1, "options": 4}]

    async def test_save_layout_invalid_subject(self, client: AsyncClient, seed_subject):
        """Save layout for nonexistent subject → 404."""
        headers, _, _ = seed_subject
        resp = await client.put("/api/v1/card/editor-layout/nonexistent", json={
            "layout": {}, "config": {}, "choices": [],
        }, headers=headers)
        assert resp.status_code == 404

    async def test_layout_cross_tenant_isolation(self, client: AsyncClient, seed_subject, db):
        """School B cannot access School A's editor layout."""
        headers_a, _, subject_id = seed_subject

        # Save layout as school A
        await client.put(f"/api/v1/card/editor-layout/{subject_id}", json={
            "layout": {"paper": "A3", "sides": []}, "config": {}, "choices": [],
        }, headers=headers_a)

        # Create school B user
        school_b = School(id="s2", name="学校B", code="TEST02")
        db.add(school_b)
        await db.commit()
        user_b = User(id="u2", username="admin2", display_name="管理员2")
        user_b.set_password("123456")
        db.add(user_b)
        await db.commit()
        db.add(UserRole(user_id=user_b.id, role="admin", school_id="s2", is_primary=True))
        await db.flush()
        token_b = create_access_token({"sub": "u2", "school_id": "s2", "role": "admin"})
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # School B cannot see school A's subject
        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers_b)
        assert resp.status_code == 404

    async def test_save_layout_overwrites_existing(self, client: AsyncClient, seed_subject):
        """Saving layout twice overwrites the first."""
        headers, _, subject_id = seed_subject

        await client.put(f"/api/v1/card/editor-layout/{subject_id}", json={
            "layout": {"paper": "A4", "sides": []}, "config": {}, "choices": [],
        }, headers=headers)

        await client.put(f"/api/v1/card/editor-layout/{subject_id}", json={
            "layout": {"paper": "A3", "sides": [{"side": "A"}]}, "config": {"examTitle": "v2"}, "choices": [{"qno": 1, "options": 4}],
        }, headers=headers)

        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        data = resp.json()
        assert data["found"] is True
        assert data["layout"]["paper"] == "A3"
        assert data["config"]["examTitle"] == "v2"

    async def test_same_code_different_exams_no_collision(self, client: AsyncClient, seed_subject, db):
        """R2-001 regression: same school, different exams, same subject code must NOT collide."""
        headers, exam_id, subject_id_1 = seed_subject

        # Create a second exam with a subject that has the same code "SW"
        exam2 = Exam(id="e2", name="期末考试", school_id="s1")
        db.add(exam2)
        await db.commit()
        subject2 = Subject(id="sub2", exam_id="e2", name="生物2", code="SW", school_id="s1")
        db.add(subject2)
        await db.commit()

        # Save different layouts for each subject
        await client.put(f"/api/v1/card/editor-layout/{subject_id_1}", json={
            "layout": {"paper": "A4", "tag": "exam1"}, "config": {}, "choices": [],
        }, headers=headers)
        await client.put("/api/v1/card/editor-layout/sub2", json={
            "layout": {"paper": "A3", "tag": "exam2"}, "config": {}, "choices": [],
        }, headers=headers)

        # Each should return its own layout, not the other's
        resp1 = await client.get(f"/api/v1/card/editor-layout/{subject_id_1}", headers=headers)
        resp2 = await client.get("/api/v1/card/editor-layout/sub2", headers=headers)

        assert resp1.json()["layout"]["tag"] == "exam1"
        assert resp1.json()["layout"]["paper"] == "A4"
        assert resp2.json()["layout"]["tag"] == "exam2"
        assert resp2.json()["layout"]["paper"] == "A3"

    async def test_english_returns_not_found_without_saved_layout(self, client: AsyncClient, seed_subject, db):
        """英语科目无保存布局 → found=False（无 fallback）。"""
        headers, exam_id, _ = seed_subject
        eng = Subject(
            exam_id=exam_id, name="英语", code="english",
            school_id="s1",
        )
        db.add(eng)
        await db.commit()
        await db.refresh(eng)

        resp = await client.get(f"/api/v1/card/editor-layout/{eng.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["found"] is False

    async def test_chemistry_returns_not_found_without_saved_layout(self, client: AsyncClient, seed_subject, db):
        """化学科目无保存布局 → found=False（无 fallback）。"""
        headers, exam_id, _ = seed_subject
        chem = Subject(
            exam_id=exam_id, name="化学", code="chemistry",
            school_id="s1",
        )
        db.add(chem)
        await db.commit()
        await db.refresh(chem)

        resp = await client.get(f"/api/v1/card/editor-layout/{chem.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["found"] is False

    async def test_math_returns_not_found_without_saved_layout(self, client: AsyncClient, seed_subject, db):
        """数学科目无保存布局 → found=False（无 fallback）。"""
        headers, exam_id, _ = seed_subject
        math = Subject(
            exam_id=exam_id, name="数学", code="math",
            school_id="s1",
        )
        db.add(math)
        await db.commit()
        await db.refresh(math)

        resp = await client.get(f"/api/v1/card/editor-layout/{math.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["found"] is False


class TestParseAnswersMetadata:
    """parse-answers API 返回元数据 (parse_method / parse_time_ms) 断言。"""

    async def test_parse_answers_returns_metadata(self, client: AsyncClient, seed_subject, tmp_path, monkeypatch):
        """上传 Word 文件 → 响应包含 parse_method='text_llm' 和 parse_time_ms。"""
        from unittest.mock import AsyncMock
        import edu_cloud.modules.card.router as cards_mod

        headers, exam_id, subject_id = seed_subject

        fake_parsed = [{"number": 1, "answer_text": "A", "image_count": 0}]
        fake_standardized = [{"number": 1, "type": "single_choice", "answer": "A",
                              "options_count": 4, "sub_count": 1, "section": None,
                              "score": None, "confidence": 0.95, "warnings": []}]

        monkeypatch.setattr("edu_cloud.modules.card.parser.word_parser.parse_word_answers", lambda p: fake_parsed)
        monkeypatch.setattr("edu_cloud.modules.card.parser.answer_standardizer.standardize_answers",
                            AsyncMock(return_value=fake_standardized))

        docx_path = tmp_path / "answers.docx"
        docx_path.write_bytes(b"fake docx content")

        with open(docx_path, "rb") as f:
            resp = await client.post("/api/v1/card/parse-answers", data={
                "subject_id": subject_id, "exam_id": exam_id,
                "total_score": "100", "paper_size": "A3", "sides": "duplex",
            }, files={"file": ("answers.docx", f, "application/octet-stream")}, headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert "parse_method" in data
        assert data["parse_method"] == "text_llm"
        assert "parse_time_ms" in data
        assert isinstance(data["parse_time_ms"], int)
        assert data["parse_time_ms"] >= 0
