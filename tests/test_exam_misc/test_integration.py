"""集成测试：exam-ai ↔ paper-seg 接口兼容性。"""
import pytest
from edu_cloud.modules.card.export import skeleton_to_paperseg_json


def test_export_regions_have_question_id():
    """导出的 regions 中主观题应包含 question_id 字段（双 ID）"""
    skeleton = {
        "anchors": [{"id": "TL", "rect": {"x1": 0, "y1": 0, "x2": 50, "y2": 50}}],
        "objective_groups": [],
        "exam_number_area": None,
        "columns": [{"y1": 100, "y2": 800}],
        "paper_size": "A3",
        "image_width": 4960,
        "image_height": 3508,
    }
    layout = {
        "slots": [{
            "slot_id": "Q01",
            "final_rect": {"x1": 100, "y1": 200, "x2": 500, "y2": 600},
            "sub_regions": [
                {"id": "Q01", "name": "15", "score": 10,
                 "rect": {"x1": 100, "y1": 200, "x2": 500, "y2": 600}, "type": "essay"},
            ],
            "inpage": 0,
        }],
    }
    question_map = {"15": "uuid-q15"}
    result = skeleton_to_paperseg_json(skeleton, layout, exam_id="e1", subject="数学", question_map=question_map)
    subj_regions = [r for r in result["regions"] if r["type"] == "subjective"]
    assert len(subj_regions) > 0
    assert subj_regions[0].get("question_id") == "uuid-q15"
    # id 字段仍保留语义 ID
    assert subj_regions[0]["id"] == "Q01"


def test_export_regions_without_question_map():
    """无 question_map 时不应报错，question_id 字段不存在"""
    skeleton = {
        "anchors": [],
        "objective_groups": [],
        "exam_number_area": None,
        "image_width": 4960,
        "image_height": 3508,
    }
    layout = {
        "slots": [{
            "slot_id": "Q01",
            "sub_regions": [
                {"id": "Q01", "name": "15", "score": 10,
                 "rect": {"x1": 100, "y1": 200, "x2": 500, "y2": 600}, "type": "essay"},
            ],
            "inpage": 0,
        }],
    }
    result = skeleton_to_paperseg_json(skeleton, layout, exam_id="e1", subject="数学")
    subj_regions = [r for r in result["regions"] if r["type"] == "subjective"]
    assert len(subj_regions) > 0
    assert "question_id" not in subj_regions[0]


def test_scan_task_create_compat():
    """ScanTaskCreate 应兼容 total_pages 旧字段名"""
    from edu_cloud.modules.scan.router import ScanTaskCreate
    req = ScanTaskCreate(subject_id="s1", total_pages=42)
    assert req.total_images == 42


def test_scan_task_update_compat():
    """ScanTaskUpdate 应兼容 processed_pages/failed_pages 旧字段名"""
    from edu_cloud.modules.scan.router import ScanTaskUpdate
    req = ScanTaskUpdate(processed_pages=10, failed_pages=2)
    assert req.processed == 10
    assert req.failed == 2


async def test_scan_task_create_with_old_fields(client, db):
    """paper-seg 用旧字段名 total_pages 创建 ScanTask 应成功"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.exam import Exam, Subject
    from edu_cloud.shared.auth import create_access_token

    school = School(id="int_s1", name="集成测试校", code="INT01")
    db.add(school)
    await db.commit()
    user = User(id="int_u1", username="admin", display_name="管理员")
    exam = Exam(id="int_e1", name="集成考试", card_title="集成", school_id="int_s1", status="scanning")
    db.add(exam)
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id="int_s1", is_primary=True))
    await db.flush()
    subj = Subject(id="int_sub1", exam_id="int_e1", name="语文", code="YW", school_id="int_s1")
    db.add(subj)
    await db.commit()

    token = create_access_token({"sub": "int_u1", "school_id": "int_s1", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    # 用旧字段名 total_pages（paper-seg 当前发送的）
    resp = await client.post("/api/v1/scan/tasks", json={
        "subject_id": "int_sub1",
        "total_pages": 30,
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["total_images"] == 30

    # 用旧字段名 processed_pages 更新
    task_id = data["id"]
    resp = await client.patch(f"/api/v1/scan/tasks/{task_id}", json={
        "processed_pages": 15,
        "failed_pages": 2,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["processed"] == 15
    assert resp.json()["failed"] == 2


def test_export_objective_regions_have_per_question_ids():
    """选择题组应生成 question_ids 列表（每题独立 UUID）"""
    skeleton = {
        "anchors": [],
        "objective_groups": [{
            "group_id": "OBJ_1",
            "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100},
            "count": 3, "options": 4, "start_no": 1,
        }],
        "exam_number_area": None,
        "image_width": 4960,
        "image_height": 3508,
    }
    layout = {"slots": []}
    # question_map 用题号字符串作 key
    question_map = {"1": "uuid-q1", "2": "uuid-q2", "3": "uuid-q3"}
    result = skeleton_to_paperseg_json(skeleton, layout, exam_id="e1", subject="数学", question_map=question_map)
    choice_regions = [r for r in result["regions"] if r["type"] == "choice_group"]
    assert len(choice_regions) == 1
    assert choice_regions[0].get("question_ids") == ["uuid-q1", "uuid-q2", "uuid-q3"]
