"""S8d: HTTP 入口级装配测试 — start_pipeline 调 build_pipeline_save_answer_fn + identity 透传。"""
import asyncio
import pytest
from unittest.mock import patch
from PIL import Image


async def test_S8d_start_pipeline_tracks_factory_and_asserts_identity(
    client, db, tmp_path, pipeline_fixture, monkeypatch
):
    """S8d: tracked_factory + identity 断言（DB 分支）。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.scan import pipeline_router as pr_mod
    from edu_cloud.config import settings

    fx = pipeline_fixture
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    scan_dir = tmp_path / str(fx["school"].id) / "scan"
    scan_dir.mkdir(parents=True)
    for i in range(2):
        Image.new("RGB", (200, 150), (255, 255, 255)).save(scan_dir / f"S{i:04d}A.png")

    admin = User(username="s8d_admin", display_name="S8d"); admin.set_password("p")
    db.add(admin); await db.commit()
    db.add(UserRole(user_id=admin.id, role="admin", school_id=fx["school"].id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": admin.id, "school_id": fx["school"].id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    captured_kwargs = {}

    async def fake_run_pipeline(**kwargs):
        captured_kwargs.update(kwargs)

    original_factory = pr_mod.build_pipeline_save_answer_fn
    factory_returns = []

    def tracked_factory(**kwargs):
        result = original_factory(**kwargs)
        factory_returns.append(result)
        return result

    with patch.object(pr_mod, "build_pipeline_save_answer_fn", side_effect=tracked_factory) as spy_factory, \
         patch("edu_cloud.modules.scan.pipeline_service.is_running", return_value=False), \
         patch("edu_cloud.modules.scan.pipeline_service.list_scan_images",
               return_value=[scan_dir / "S0000A.png"]), \
         patch("edu_cloud.modules.scan.pipeline_service.run_pipeline", side_effect=fake_run_pipeline):
        resp = await client.post(
            "/api/v1/scan/pipeline/start",
            json={"subject_id": fx["subject"].id, "side": "A", "image_dir": str(scan_dir)},
            headers=headers,
        )
        await asyncio.sleep(0.05)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert spy_factory.called
    assert len(factory_returns) == 1

    call_kwargs = spy_factory.call_args.kwargs
    assert isinstance(call_kwargs["regions"], list)
    assert len(call_kwargs["regions"]) == 2

    assert "save_answer_fn" in captured_kwargs
    assert captured_kwargs["save_answer_fn"] is factory_returns[0]


async def test_start_pipeline_wires_save_objective_fn(client, db, tmp_path, pipeline_objective_fixture, monkeypatch):
    """Gate 2 R1 F002 回归：start_pipeline 必须装配 save_objective_fn。
    反例：如果 start_pipeline 漏掉 save_objective_fn 装配，captured_kwargs 中该键为 None。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.scan import pipeline_router as pr_mod
    from edu_cloud.config import settings

    fx = pipeline_objective_fixture
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    scan_dir = tmp_path / str(fx["school"].id) / "scan_obj"
    scan_dir.mkdir(parents=True)
    Image.new("RGB", (200, 150), (255, 255, 255)).save(scan_dir / "S0001A.png")

    admin = User(username="obj_wire_admin", display_name="ObjWire"); admin.set_password("p")
    db.add(admin); await db.commit()
    db.add(UserRole(user_id=admin.id, role="admin", school_id=fx["school"].id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": admin.id, "school_id": fx["school"].id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    captured_kwargs = {}
    captured_item = {}

    async def fake_run_pipeline(**kwargs):
        captured_kwargs.update(kwargs)

    def fake_enqueue(**kwargs):
        captured_item.update(kwargs)
        return 1

    with patch.object(pr_mod, "build_pipeline_save_objective_fn", wraps=pr_mod.build_pipeline_save_objective_fn) as spy_obj, \
         patch("edu_cloud.modules.scan.pipeline_service.is_running", return_value=False), \
         patch("edu_cloud.modules.scan.pipeline_service.list_scan_images",
               return_value=[scan_dir / "S0001A.png"]), \
         patch("edu_cloud.modules.scan.pipeline_service.enqueue_pipeline", side_effect=fake_enqueue), \
         patch("edu_cloud.modules.scan.pipeline_service.run_queue", side_effect=fake_run_pipeline):
        resp = await client.post(
            "/api/v1/scan/pipeline/start",
            json={"subject_id": fx["subject"].id, "side": "A", "image_dir": str(scan_dir)},
            headers=headers,
        )
        await asyncio.sleep(0.05)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    # F002 关键断言：build_pipeline_save_objective_fn 被调用
    assert spy_obj.called, "start_pipeline 必须调用 build_pipeline_save_objective_fn"
    # INV-002: questions_by_group 通过 region.question_ids 显式关联
    call_kwargs = spy_obj.call_args.kwargs
    assert "questions_by_group" in call_kwargs
    qbg = call_kwargs["questions_by_group"]
    assert "OBJ01" in qbg, f"Expected OBJ01 in questions_by_group, got {list(qbg.keys())}"
    # enqueue 必须收到非 None 的 save_objective_fn
    assert captured_item.get("save_objective_fn") is not None, \
        "save_objective_fn 必须入队，不能是 None"


async def test_S8d_tpl_path_branch_wiring(client, db, tmp_path, pipeline_fixture, monkeypatch):
    """S8d-b: tpl_path 分支也调工厂 + identity 透传。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.scan import pipeline_router as pr_mod
    from edu_cloud.config import settings
    from PIL import Image
    import json

    fx = pipeline_fixture
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    tpl_file = tmp_path / "test.tpl"
    tpl_file.write_text(json.dumps({
        "image_size": {"width": 200, "height": 150},
        "anchors": [],
        "regions": [],
    }))

    scan_dir = tmp_path / str(fx["school"].id) / "scan_tpl"
    scan_dir.mkdir(parents=True)
    Image.new("RGB", (200, 150), (255, 255, 255)).save(scan_dir / "S0001A.png")

    admin = User(username="s8d_tpl_admin", display_name="S8d Tpl"); admin.set_password("p")
    db.add(admin); await db.commit()
    db.add(UserRole(user_id=admin.id, role="admin", school_id=fx["school"].id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": admin.id, "school_id": fx["school"].id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    captured_kwargs = {}

    async def fake_run_pipeline(**kwargs):
        captured_kwargs.update(kwargs)

    original_factory = pr_mod.build_pipeline_save_answer_fn
    factory_returns = []

    def tracked_factory(**kwargs):
        result = original_factory(**kwargs)
        factory_returns.append(result)
        return result

    with patch.object(pr_mod, "build_pipeline_save_answer_fn", side_effect=tracked_factory) as spy_factory, \
         patch("edu_cloud.modules.scan.pipeline_service.is_running", return_value=False), \
         patch("edu_cloud.modules.scan.pipeline_service.list_scan_images",
               return_value=[scan_dir / "S0001A.png"]), \
         patch("edu_cloud.modules.scan.pipeline_service.run_pipeline", side_effect=fake_run_pipeline):
        resp = await client.post(
            "/api/v1/scan/pipeline/start",
            json={
                "subject_id": fx["subject"].id, "side": "A",
                "image_dir": str(scan_dir), "tpl_path": str(tpl_file),
            },
            headers=headers,
        )
        await asyncio.sleep(0.05)

    assert resp.status_code == 200, f"tpl_path 分支应 200, got {resp.status_code}: {resp.text}"
    assert spy_factory.called, "tpl_path 分支也必须调工厂"
    assert len(factory_returns) == 1

    call_kwargs = spy_factory.call_args.kwargs
    assert isinstance(call_kwargs["regions"], list)
    assert call_kwargs["regions"] == []  # tpl 文件 regions 为空

    assert "save_answer_fn" in captured_kwargs
    assert captured_kwargs["save_answer_fn"] is factory_returns[0]


@pytest.fixture
async def pipeline_fixture(db):
    """S8d fixture — reuse from test_pipeline_save_answer pattern."""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.exam.models import Exam, Subject, Question
    from edu_cloud.modules.card.models import Template

    school = School(name="S8dSch", code="S8DSCH")
    db.add(school); await db.commit()

    exam = Exam(name="S8d 考试", school_id=school.id, status="scanning")
    db.add(exam); await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject); await db.commit()
    q1 = Question(subject_id=subject.id, school_id=school.id, name="13",
                  question_type="essay", max_score=10.0)
    db.add(q1); await db.commit()

    tpl_a = Template(
        subject_id=subject.id, side="A", school_id=school.id,
        image_width=200, image_height=150, anchors=[],
        regions=[
            {"id": "essay-13", "name": "13", "type": "subjective",
             "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}, "question_id": q1.id},
            {"id": "essay-99", "name": "99", "type": "subjective",
             "rect": {"x1": 10, "y1": 80, "x2": 90, "y2": 140}},
        ],
    )
    db.add(tpl_a); await db.commit()

    return {"school": school, "exam": exam, "subject": subject, "question": q1, "tpl_a": tpl_a}


async def test_tpl_path_branch_fallback_wires_save_objective_fn(client, db, tmp_path, pipeline_objective_fixture, monkeypatch):
    """Gate 2 R2 F005 回归：tpl_path 分支也必须装配 save_objective_fn。
    tpl_parser 不会写 question_ids，必须走 fallback（按 qg_indexno 顺序映射）。
    反例：若 tpl_path 分支跳过 objective 装配，enqueue 收到 save_objective_fn=None。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.scan import pipeline_router as pr_mod
    from edu_cloud.config import settings
    import json

    fx = pipeline_objective_fixture
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    # 写 tpl 文件（模拟月小二 .tpl 格式）—— 含 1 个 choice_group，2 行
    tpl_file = tmp_path / "obj.tpl"
    tpl_file.write_text(json.dumps({
        "tplInfo": {"iwidth": 200, "iheight": 150, "tpl_name": "obj_tpl"},
        "datas": {
            "tplLocsList": [],
            "tplSubqueList": [],
            "tplObjqueGList": [
                {"qg_name": "选择题组1", "location": "(100,10)-(190,70)",
                 "opt_symbol": "A,B,C,D", "opt_count": 4, "que_count": 2,
                 "opt_type": "单选", "qg_indexno": 1, "inpage": 0, "busing": True},
            ],
            "MbNoBarCodeList": [],
        },
    }))

    scan_dir = tmp_path / str(fx["school"].id) / "scan_tpl_obj"
    scan_dir.mkdir(parents=True)
    Image.new("RGB", (200, 150), (255, 255, 255)).save(scan_dir / "S0001A.png")

    admin = User(username="tpl_obj_admin", display_name="TplObj"); admin.set_password("p")
    db.add(admin); await db.commit()
    db.add(UserRole(user_id=admin.id, role="admin", school_id=fx["school"].id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": admin.id, "school_id": fx["school"].id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    captured_item = {}

    def fake_enqueue(**kwargs):
        captured_item.update(kwargs)
        return 1

    async def fake_run_queue():
        pass

    with patch.object(pr_mod, "build_pipeline_save_objective_fn",
                      wraps=pr_mod.build_pipeline_save_objective_fn) as spy_obj, \
         patch("edu_cloud.modules.scan.pipeline_service.is_running", return_value=False), \
         patch("edu_cloud.modules.scan.pipeline_service.list_scan_images",
               return_value=[scan_dir / "S0001A.png"]), \
         patch("edu_cloud.modules.scan.pipeline_service.enqueue_pipeline", side_effect=fake_enqueue), \
         patch("edu_cloud.modules.scan.pipeline_service.run_queue", side_effect=fake_run_queue):
        resp = await client.post(
            "/api/v1/scan/pipeline/start",
            json={
                "subject_id": fx["subject"].id, "side": "A",
                "image_dir": str(scan_dir), "tpl_path": str(tpl_file),
            },
            headers=headers,
        )
        await asyncio.sleep(0.05)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    # F005 核心断言：tpl_path 分支也必须调用 build_pipeline_save_objective_fn
    assert spy_obj.called, "tpl_path 分支必须装配 save_objective_fn（fallback 映射）"
    call_kwargs = spy_obj.call_args.kwargs
    qbg = call_kwargs["questions_by_group"]
    # fallback 应把 2 道 objective Question 映射进 tpl 解析出的 choice_group
    assert len(qbg) == 1, f"Expected 1 group, got {len(qbg)}"
    group_qs = list(qbg.values())[0]
    assert len(group_qs) == 2, f"Expected 2 questions in group, got {len(group_qs)}"
    # enqueue 必须收到非 None 的 save_objective_fn
    assert captured_item.get("save_objective_fn") is not None, \
        "tpl_path 分支 save_objective_fn 不能是 None"


async def test_tpl_path_fallback_maps_by_question_number_not_creation_order(client, db, tmp_path, monkeypatch):
    """Gate 2 R3 F005 回归：fallback 必须按题号（Question.name）映射，不能按 created_at。
    反例场景：Question 倒序创建（名 '3' 先创建，名 '1' 后创建），
    如果用 created_at 消费则第 1 行绑到题号 3，顺序错乱。"""
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.exam.models import Exam, Subject, Question
    from edu_cloud.modules.scan import pipeline_router as pr_mod
    from edu_cloud.config import settings
    import json

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    # Setup: 倒序创建 Question（题号 3 先于题号 1）
    school = School(name="F005Sch", code="F005SCH")
    db.add(school); await db.commit()
    exam = Exam(name="F005 考试", school_id=school.id, status="scanning")
    db.add(exam); await db.commit()
    subject = Subject(exam_id=exam.id, name="英语", code="EN", school_id=school.id)
    db.add(subject); await db.commit()
    # 先建题号 3, 再建 2, 最后 1
    q3 = Question(subject_id=subject.id, school_id=school.id, name="3",
                  question_type="choice", max_score=3.0, correct_answer="C")
    db.add(q3); await db.commit()
    q2 = Question(subject_id=subject.id, school_id=school.id, name="2",
                  question_type="choice", max_score=3.0, correct_answer="B")
    db.add(q2); await db.commit()
    q1 = Question(subject_id=subject.id, school_id=school.id, name="1",
                  question_type="choice", max_score=3.0, correct_answer="A")
    db.add(q1); await db.commit()

    tpl_file = tmp_path / "f005.tpl"
    tpl_file.write_text(json.dumps({
        "tplInfo": {"iwidth": 200, "iheight": 150},
        "datas": {
            "tplLocsList": [], "tplSubqueList": [],
            "tplObjqueGList": [
                {"qg_name": "组1", "location": "(100,10)-(190,70)",
                 "opt_symbol": "A,B,C,D", "opt_count": 4, "que_count": 3,
                 "opt_type": "单选", "qg_indexno": 1, "inpage": 0, "busing": True},
            ],
            "MbNoBarCodeList": [],
        },
    }))

    scan_dir = tmp_path / str(school.id) / "scan_f005"
    scan_dir.mkdir(parents=True)
    Image.new("RGB", (200, 150), (255, 255, 255)).save(scan_dir / "S0001A.png")

    admin = User(username="f005_admin", display_name="F005"); admin.set_password("p")
    db.add(admin); await db.commit()
    role = UserRole(user_id=admin.id, role="admin", school_id=school.id, is_primary=True)
    db.add(role); await db.commit()
    token = create_access_token({"sub": admin.id, "school_id": school.id, "role": "admin", "active_role_id": role.id})
    headers = {"Authorization": f"Bearer {token}"}

    captured_kwargs = {}

    with patch.object(pr_mod, "build_pipeline_save_objective_fn",
                      wraps=pr_mod.build_pipeline_save_objective_fn) as spy_obj, \
         patch("edu_cloud.modules.scan.pipeline_service.is_running", return_value=False), \
         patch("edu_cloud.modules.scan.pipeline_service.list_scan_images",
               return_value=[scan_dir / "S0001A.png"]), \
         patch("edu_cloud.modules.scan.pipeline_service.enqueue_pipeline"), \
         patch("edu_cloud.modules.scan.pipeline_service.run_queue"):
        resp = await client.post(
            "/api/v1/scan/pipeline/start",
            json={"subject_id": subject.id, "side": "A",
                  "image_dir": str(scan_dir), "tpl_path": str(tpl_file)},
            headers=headers,
        )
        await asyncio.sleep(0.05)

    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text}"
    assert spy_obj.called
    qbg = spy_obj.call_args.kwargs["questions_by_group"]
    group_qs = list(qbg.values())[0]
    # 关键断言：row 1 → 题号 1 (q1)，row 2 → 题号 2 (q2)，row 3 → 题号 3 (q3)
    # 而非按 created_at：row 1→q3, row 2→q2, row 3→q1
    by_row = {gq["row_index"]: gq for gq in group_qs}
    assert by_row[1]["id"] == q1.id, \
        f"row 1 应绑题号 1 (q1={q1.id})，实际 {by_row[1]['id']}"
    assert by_row[2]["id"] == q2.id, \
        f"row 2 应绑题号 2 (q2={q2.id})，实际 {by_row[2]['id']}"
    assert by_row[3]["id"] == q3.id, \
        f"row 3 应绑题号 3 (q3={q3.id})，实际 {by_row[3]['id']}"


@pytest.fixture
async def pipeline_objective_fixture(db):
    """F002 回归 fixture — 带 choice_group region 和 objective questions。"""
    from edu_cloud.models.school import School
    from edu_cloud.modules.exam.models import Exam, Subject, Question
    from edu_cloud.modules.card.models import Template

    school = School(name="ObjSch", code="OBJSCH")
    db.add(school); await db.commit()

    exam = Exam(name="Obj 考试", school_id=school.id, status="scanning")
    db.add(exam); await db.commit()
    subject = Subject(exam_id=exam.id, name="英语", code="EN", school_id=school.id)
    db.add(subject); await db.commit()
    # 选择题 Question
    q1 = Question(subject_id=subject.id, school_id=school.id, name="1",
                  question_type="choice", max_score=3.0, correct_answer="A")
    q2 = Question(subject_id=subject.id, school_id=school.id, name="2",
                  question_type="choice", max_score=3.0, correct_answer="B")
    db.add_all([q1, q2]); await db.commit()

    # Template 带 choice_group + question_ids
    tpl = Template(
        subject_id=subject.id, side="A", school_id=school.id,
        image_width=200, image_height=150, anchors=[],
        regions=[
            {"id": "OBJ01", "type": "choice_group",
             "rect": {"x1": 100, "y1": 10, "x2": 190, "y2": 70},
             "rows": 2, "cols": 4, "labels": ["A", "B", "C", "D"],
             "multi_select": False, "qg_indexno": 1,
             "question_ids": [q1.id, q2.id]},
        ],
    )
    db.add(tpl); await db.commit()

    return {"school": school, "exam": exam, "subject": subject,
            "q1": q1, "q2": q2, "tpl": tpl}
