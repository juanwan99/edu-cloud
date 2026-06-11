"""答题卡生成 API 测试。"""
import copy
import json

import pytest
from httpx import AsyncClient
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
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

    async def test_get_layout_returns_subject_default_when_missing(self, client: AsyncClient, seed_subject):
        """无保存布局 → 返回学科默认布局（found=True, source=default），不再 found=False。"""
        headers, _, subject_id = seed_subject
        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"
        expected = get_default_layout("生物")
        assert data["layout"]["paper"] == expected["paper"]
        assert data["config"]["choiceCount"] == expected["config"]["choiceCount"]
        assert data["config"]["subjectTitle"] == "生物"
        assert data["choices"] == []

    async def test_save_and_load_layout(self, client: AsyncClient, seed_subject):
        """Save canonical-compatible layout metadata -> load returns it."""
        headers, _, subject_id = seed_subject
        layout = copy.deepcopy(get_default_layout("生物"))
        config = {"examTitle": "测试考试"}
        choices = [{"qno": 1, "options": 4}]

        resp = await client.put(f"/api/v1/card/editor-layout/{subject_id}", json={
            "layout": layout, "config": config, "choices": choices,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "saved"
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
        """Saving canonical-compatible layout twice overwrites metadata."""
        headers, _, subject_id = seed_subject
        layout = copy.deepcopy(get_default_layout("生物"))

        resp = await client.put(f"/api/v1/card/editor-layout/{subject_id}", json={
            "layout": layout, "config": {"examTitle": "v1"}, "choices": [],
        }, headers=headers)
        assert resp.status_code == 200

        layout2 = copy.deepcopy(get_default_layout("生物"))
        resp = await client.put(f"/api/v1/card/editor-layout/{subject_id}", json={
            "layout": layout2, "config": {"examTitle": "v2"}, "choices": [{"qno": 1, "options": 4}],
        }, headers=headers)
        assert resp.status_code == 200

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

        # Save different layouts for each subject. Final subjects require canonical structure;
        # unknown subject names keep the old arbitrary-layout behavior.
        layout1 = copy.deepcopy(get_default_layout("生物"))
        layout1["tag"] = "exam1"
        resp = await client.put(f"/api/v1/card/editor-layout/{subject_id_1}", json={
            "layout": layout1, "config": {}, "choices": [],
        }, headers=headers)
        assert resp.status_code == 200
        resp = await client.put("/api/v1/card/editor-layout/sub2", json={
            "layout": {"paper": "A3", "tag": "exam2"}, "config": {}, "choices": [],
        }, headers=headers)
        assert resp.status_code == 200

        # Each should return its own layout, not the other's
        resp1 = await client.get(f"/api/v1/card/editor-layout/{subject_id_1}", headers=headers)
        resp2 = await client.get("/api/v1/card/editor-layout/sub2", headers=headers)

        assert resp1.json()["layout"]["tag"] == "exam1"
        assert resp1.json()["layout"]["paper"] == "A3"
        assert resp2.json()["layout"]["tag"] == "exam2"
        assert resp2.json()["layout"]["paper"] == "A3"

    async def test_english_returns_subject_default_without_saved_layout(self, client: AsyncClient, seed_subject, db):
        """英语科目无保存布局 → 返回英语学科默认布局（paper/choiceCount 与 subject_defaults 一致）。"""
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
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"
        expected = get_default_layout("英语")
        assert data["layout"]["paper"] == expected["paper"]
        assert data["config"]["choiceCount"] == expected["config"]["choiceCount"]
        assert data["config"]["choiceGroups"] == expected["config"]["choiceGroups"]

    async def test_chemistry_returns_subject_default_without_saved_layout(self, client: AsyncClient, seed_subject, db):
        """化学科目无保存布局 → 返回化学学科默认布局。"""
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
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"
        expected = get_default_layout("化学")
        assert data["layout"]["paper"] == expected["paper"]
        assert data["config"]["choiceCount"] == expected["config"]["choiceCount"]

    async def test_math_returns_subject_default_without_saved_layout(self, client: AsyncClient, seed_subject, db):
        """数学科目无保存布局 → 返回数学学科默认布局。"""
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
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"
        expected = get_default_layout("数学")
        assert data["layout"]["paper"] == expected["paper"]
        assert data["config"]["choiceCount"] == expected["config"]["choiceCount"]

    async def test_corrupt_layout_file_falls_back_to_default(self, client: AsyncClient, seed_subject, tmp_path):
        """保存文件损坏（非法 JSON）→ 回退学科默认布局，不 500 也不 found=False。"""
        headers, _, subject_id = seed_subject
        (tmp_path / f"s1_{subject_id}.json").write_text("{not valid json", encoding="utf-8")

        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"
        assert data["layout"]["paper"] == get_default_layout("生物")["paper"]

    async def test_non_dict_layout_falls_back_to_default(self, client: AsyncClient, seed_subject, tmp_path):
        """保存数据 layout 字段非 dict → 回退学科默认布局。"""
        headers, _, subject_id = seed_subject
        (tmp_path / f"s1_{subject_id}.json").write_text(
            '{"layout": [1, 2], "config": {}, "choices": []}', encoding="utf-8"
        )

        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"

    async def test_non_dict_top_level_falls_back_to_default(self, client: AsyncClient, seed_subject, tmp_path):
        """保存数据顶层非 dict（JSON 数组）→ 回退学科默认布局，不 500。"""
        headers, _, subject_id = seed_subject
        (tmp_path / f"s1_{subject_id}.json").write_text("[1, 2, 3]", encoding="utf-8")

        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"

    # ── canonical 默认布局 API 契约（2026-06-11 cardtpl-pack1）──
    # 显式编码纸张/列结构/qcols/题量，不与 get_default_layout 输出做 snapshot 等价，
    # 防止"默认布局本身退化"时测试跟着退化。

    @staticmethod
    def _essay_qnos_by_col(layout: dict, side_idx: int) -> list[list]:
        return [
            [r["qno"] for r in col["regions"] if r.get("type") == "essay"]
            for col in layout["sides"][side_idx]["columns"]
        ]

    async def test_chemistry_default_layout_is_canonical_a4_multicolumn(self, client: AsyncClient, seed_subject, db):
        """化学无保存布局 → canonical A4 多栏 [3,1]，Q15-18 按列分布，14选择/0填空/4解答。"""
        headers, exam_id, _ = seed_subject
        chem = Subject(exam_id=exam_id, name="化学", code="HX", school_id="s1")
        db.add(chem)
        await db.commit()
        await db.refresh(chem)

        resp = await client.get(f"/api/v1/card/editor-layout/{chem.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"
        layout = data["layout"]
        assert layout["paper"] == "A4"
        assert [len(s["columns"]) for s in layout["sides"]] == [3, 1]
        assert self._essay_qnos_by_col(layout, 0) == [[15], [16], [17, 18]]
        assert data["config"]["choiceCount"] == 14
        assert data["config"]["fillCount"] == 0
        assert data["config"]["essayCount"] == 4

    async def test_biology_default_layout_is_canonical_a3_not_generic(self, client: AsyncClient, seed_subject):
        """生物无保存布局 → canonical A3 [3,3] Q17-21，绝不能再退化为 generic A4 11/3/5。"""
        headers, _, subject_id = seed_subject
        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"
        layout = data["layout"]
        assert layout["paper"] == "A3"
        assert [len(s["columns"]) for s in layout["sides"]] == [3, 3]
        assert self._essay_qnos_by_col(layout, 0) == [[17], [18, 19], [20, 21]]
        assert data["config"]["choiceCount"] == 16
        assert data["config"]["fillCount"] == 0
        assert data["config"]["essayCount"] == 5
        # generic 污染指纹（前端 createDefaultLayout 默认 11选择/3填空）必须为假
        assert not (data["config"]["choiceCount"] == 11 and data["config"]["fillCount"] == 3)

    async def test_english_default_layout_is_canonical_a4(self, client: AsyncClient, seed_subject, db):
        """英语无保存布局 → canonical A4 [1,1]，55选择 + 填空56-65 + 写作两节。"""
        headers, exam_id, _ = seed_subject
        eng = Subject(exam_id=exam_id, name="英语", code="YY", school_id="s1")
        db.add(eng)
        await db.commit()
        await db.refresh(eng)

        resp = await client.get(f"/api/v1/card/editor-layout/{eng.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default"
        layout = data["layout"]
        assert layout["paper"] == "A4"
        assert [len(s["columns"]) for s in layout["sides"]] == [1, 1]
        assert data["config"]["choiceCount"] == 55
        assert data["config"]["fillCount"] == 10
        assert data["config"]["essayCount"] == 2
        a_regions = layout["sides"][0]["columns"][0]["regions"]
        fill_qnos = [r["qno"] for r in a_regions if r.get("type") == "fill"]
        assert fill_qnos == list(range(56, 66))

    # ── canonical fail-closed API 契约（2026-06-11 cardtpl-pack3）──
    # 已知 canonical 学科资产缺失/损坏时 GET 默认布局必须 500 fail-closed，
    # 禁止把 TQL/SUBJECT_CONFIGS 泛化模板当学科默认返回给编辑器。

    async def test_biology_canonical_missing_get_default_fails_closed_500(
        self, client: AsyncClient, seed_subject, tmp_path, monkeypatch,
    ):
        """生物 canonical 资产缺失且无保存布局 → GET 500，不返回泛化默认。"""
        import edu_cloud.modules.card.rendering.subject_defaults as sd
        monkeypatch.setattr(sd, "_LAYOUT_CACHE", {})
        monkeypatch.setattr(sd, "_CANONICAL_DIR", tmp_path / "empty_canonical")

        headers, _, subject_id = seed_subject
        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 500
        assert "canonical" in resp.json()["detail"]

    async def test_biology_canonical_corrupt_auto_layout_fails_closed_500(
        self, client: AsyncClient, seed_subject, tmp_path, monkeypatch,
    ):
        """生物 canonical 资产损坏 → auto-layout 500 fail-closed，不基于泛化模板排版回写。"""
        import edu_cloud.modules.card.layout_helpers as lh
        import edu_cloud.modules.card.rendering.subject_defaults as sd
        monkeypatch.setattr(lh, "_EDITOR_LAYOUT_DIR", tmp_path)
        canonical_dir = tmp_path / "broken_canonical"
        canonical_dir.mkdir()
        (canonical_dir / "canonical_biology.json").write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(sd, "_LAYOUT_CACHE", {})
        monkeypatch.setattr(sd, "_CANONICAL_DIR", canonical_dir)

        headers, _, subject_id = seed_subject
        resp = await client.post(f"/api/v1/card/auto-layout/{subject_id}", json={
            "parsed_questions": [
                {"qno": 17, "total_score": 12,
                 "subs": [{"sub": 1, "answers": ["光合作用产生氧气"]}]},
            ],
        }, headers=headers)
        assert resp.status_code == 500
        assert not (tmp_path / f"s1_{subject_id}.json").exists(), "fail-closed 后不得写入布局文件"

    async def test_biology_polluted_saved_layout_falls_back_to_default(self, client: AsyncClient, seed_subject, tmp_path):
        """生物 saved layout 命中 generic 污染指纹（A4 [1,1] 11选择/3填空）→
        不得作为 source=saved 返回，fail-closed 回退学科默认。"""
        headers, _, subject_id = seed_subject
        polluted = {
            "layout": {
                "paper": "A4",
                "config": {"subjectTitle": "生物", "paperSize": "A4",
                           "choiceCount": 11, "fillCount": 3, "essayCount": 5},
                "sides": [
                    {"side": "A", "columns": [{"col": 0, "regions": []}]},
                    {"side": "B", "columns": [{"col": 0, "regions": []}]},
                ],
            },
            "config": {"subjectTitle": "生物", "paperSize": "A4",
                       "choiceCount": 11, "fillCount": 3, "essayCount": 5},
            "choices": [],
        }
        (tmp_path / f"s1_{subject_id}.json").write_text(
            json.dumps(polluted, ensure_ascii=False), encoding="utf-8"
        )

        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["source"] == "default", "污染指纹 saved 不得以 source=saved 返回"
        assert data["layout"]["paper"] == "A3"
        assert data["config"]["choiceCount"] == 16
        assert data["config"]["fillCount"] == 0

    async def test_biology_structural_drift_saved_layout_falls_back_to_default(self, client: AsyncClient, seed_subject, tmp_path):
        """Saved layout that is not the final canonical structure must not be returned as saved."""
        headers, _, subject_id = seed_subject
        drifted = {
            "layout": {
                "paper": "A4",
                "config": {"subjectTitle": "生物", "paperSize": "A4",
                           "choiceCount": 16, "fillCount": 0, "essayCount": 5},
                "sides": [
                    {"side": "A", "columns": [{"col": 0, "regions": []}]},
                    {"side": "B", "columns": [{"col": 0, "regions": []}]},
                ],
            },
            "config": {"subjectTitle": "生物", "paperSize": "A4",
                       "choiceCount": 16, "fillCount": 0, "essayCount": 5},
            "choices": [],
        }
        (tmp_path / f"s1_{subject_id}.json").write_text(
            json.dumps(drifted, ensure_ascii=False), encoding="utf-8"
        )

        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "default"
        assert data["layout"]["paper"] == "A3"
        assert [len(s["columns"]) for s in data["layout"]["sides"]] == [3, 3]

    @staticmethod
    def _polluted_body() -> dict:
        """前端 createDefaultLayout 兜底形状：A4 双面各 1 列，11选择/3填空。"""
        config = {"subjectTitle": "生物", "paperSize": "A4",
                  "choiceCount": 11, "fillCount": 3, "essayCount": 5}
        return {
            "layout": {
                "paper": "A4",
                "config": dict(config),
                "sides": [
                    {"side": "A", "columns": [{"col": 0, "regions": []}]},
                    {"side": "B", "columns": [{"col": 0, "regions": []}]},
                ],
            },
            "config": dict(config),
            "choices": [],
        }

    @staticmethod
    def _canonical_biology_body() -> dict:
        layout = copy.deepcopy(get_default_layout("生物"))
        return {"layout": layout, "config": dict(layout["config"]), "choices": []}

    async def test_put_polluted_biology_layout_rejected_not_written(self, client: AsyncClient, seed_subject, tmp_path):
        """PUT 命中生物 generic 污染指纹 → 422 拒绝，editor_layouts 不写入。"""
        headers, _, subject_id = seed_subject
        resp = await client.put(
            f"/api/v1/card/editor-layout/{subject_id}",
            json=self._polluted_body(), headers=headers,
        )
        assert resp.status_code == 422
        assert "污染指纹" in resp.json()["detail"]
        assert not (tmp_path / f"s1_{subject_id}.json").exists(), "拒绝后不得写入布局文件"

    async def test_put_polluted_biology_layout_does_not_overwrite_existing(self, client: AsyncClient, seed_subject, tmp_path):
        """已有合法 saved 布局时，污染 PUT 被拒且原文件内容不变。"""
        headers, _, subject_id = seed_subject
        existing = json.dumps({
            "layout": {"paper": "A3", "tag": "legit", "sides": []},
            "config": {"examTitle": "原布局"}, "choices": [],
        }, ensure_ascii=False)
        path = tmp_path / f"s1_{subject_id}.json"
        path.write_text(existing, encoding="utf-8")

        resp = await client.put(
            f"/api/v1/card/editor-layout/{subject_id}",
            json=self._polluted_body(), headers=headers,
        )
        assert resp.status_code == 422
        assert path.read_text(encoding="utf-8") == existing, "污染 PUT 不得覆盖已有合法布局"

    async def test_put_final_canonical_biology_layout_accepted(self, client: AsyncClient, seed_subject, tmp_path):
        """Only the final canonical biology structure is accepted for saved layouts."""
        headers, _, subject_id = seed_subject
        body = self._canonical_biology_body()

        resp = await client.put(
            f"/api/v1/card/editor-layout/{subject_id}", json=body, headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert (tmp_path / f"s1_{subject_id}.json").exists()

    async def test_put_structural_drift_biology_layout_rejected(self, client: AsyncClient, seed_subject, tmp_path):
        """Non-canonical structure is rejected even when it does not match the old pollution fingerprint."""
        headers, _, subject_id = seed_subject
        body = self._polluted_body()
        body["layout"]["config"].update({"choiceCount": 16, "fillCount": 0})
        body["config"].update({"choiceCount": 16, "fillCount": 0})

        resp = await client.put(
            f"/api/v1/card/editor-layout/{subject_id}", json=body, headers=headers,
        )
        assert resp.status_code == 422
        assert "canonical" in resp.json()["detail"]
        assert not (tmp_path / f"s1_{subject_id}.json").exists()

    async def test_put_layout_sanitizes_runtime_fields_before_persistence(
        self, client: AsyncClient, seed_subject, tmp_path,
    ):
        """PUT 布局含前端渲染注入的 _side/_col/_sideIdx → 200 保存，
        落盘文件递归无任何下划线前缀 key，合法字段原样保留。"""
        headers, _, subject_id = seed_subject
        body = self._canonical_biology_body()
        regions = body["layout"]["sides"][0]["columns"][0]["regions"]
        regions[0].update({"_side": "A", "_col": 0, "_sideIdx": 0})
        next(r for r in regions if r.get("qno") == 17).update(
            {"_side": "A", "_col": 0, "_sideIdx": 0, "_height_mm": 42.5}
        )

        resp = await client.put(
            f"/api/v1/card/editor-layout/{subject_id}", json=body, headers=headers,
        )
        assert resp.status_code == 200

        saved = json.loads((tmp_path / f"s1_{subject_id}.json").read_text(encoding="utf-8"))

        def underscore_keys(value, path=""):
            found = []
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(k, str) and k.startswith("_"):
                        found.append(f"{path}/{k}")
                    found.extend(underscore_keys(v, f"{path}/{k}"))
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    found.extend(underscore_keys(v, f"{path}[{i}]"))
            return found

        assert underscore_keys(saved) == [], "运行时字段不得持久化"
        regions = saved["layout"]["sides"][0]["columns"][0]["regions"]
        assert regions[0]["id"] == "header"
        essay17 = next(r for r in regions if r.get("qno") == 17)
        assert essay17["score"] == 12

    async def test_auto_layout_api_polluted_saved_uses_canonical_base(self, client: AsyncClient, seed_subject, tmp_path, monkeypatch):
        """auto-layout 端点：saved 文件命中污染指纹 → _load_layout 回退 canonical，
        排版回写结果基于 A3 canonical 而非 generic A4。"""
        import edu_cloud.modules.card.layout_helpers as lh
        monkeypatch.setattr(lh, "_EDITOR_LAYOUT_DIR", tmp_path)

        headers, _, subject_id = seed_subject
        path = tmp_path / f"s1_{subject_id}.json"
        path.write_text(json.dumps(self._polluted_body(), ensure_ascii=False), encoding="utf-8")

        resp = await client.post(f"/api/v1/card/auto-layout/{subject_id}", json={
            "parsed_questions": [
                {"qno": 17, "total_score": 12,
                 "subs": [{"sub": 1, "answers": ["光合作用产生氧气"]}]},
            ],
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["applied"] is True

        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["layout"]["paper"] == "A3", "generic A4 形状不得在 auto-layout 回写后存活"
        assert saved["config"]["choiceCount"] == 16
        assert saved["config"]["fillCount"] == 0

    def test_default_layout_response_is_deepcopy(self):
        """_default_layout_response 必须 deepcopy——污染返回值不得影响 subject_defaults 模块级缓存。"""
        from edu_cloud.modules.card.router import _default_layout_response

        baseline = copy.deepcopy(get_default_layout("数学"))

        first = _default_layout_response("数学")
        first["layout"]["config"]["choiceCount"] = -999
        first["layout"]["sides"][0]["columns"][0]["regions"].clear()

        second = _default_layout_response("数学")
        assert second["layout"]["config"]["choiceCount"] == baseline["config"]["choiceCount"]
        assert second["layout"]["sides"][0]["columns"][0]["regions"] == baseline["sides"][0]["columns"][0]["regions"]


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
