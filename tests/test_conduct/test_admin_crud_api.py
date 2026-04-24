"""Admin CRUD API tests: points + rules + groups + semesters (Tasks 10-12)."""
import pytest

from edu_cloud.modules.conduct.models import (
    ConductRecord, ConductRuleCategory, ConductRuleItem,
    ConductGroup, ConductGroupMember, ConductSemester,
)
from edu_cloud.modules.student.models import Student


# ═══════════════════════════════════════════════════
# Task 10: Points CRUD
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_add_points(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Add +3 to a single student, verify record created."""
    _, cls, student = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={
            "student_ids": [student.id],
            "points": 3,
            "reason": "课堂表现优秀",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["created_ids"]) == 1


@pytest.mark.anyio
async def test_add_points_batch(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Add points to multiple students at once."""
    school, cls, student = school_class_student
    # Create a second student
    s2 = Student(name="李四", student_number="2026002", class_id=cls.id, school_id=school.id)
    db.add(s2)
    await db.commit()
    await db.refresh(s2)

    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records/batch",
        headers=homeroom_headers,
        json={
            "student_ids": [student.id, s2.id],
            "points": 5,
            "reason": "小组合作优秀",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["created_ids"]) == 2


@pytest.mark.anyio
async def test_get_records(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Add records then query, verify pagination fields."""
    _, cls, student = school_class_student
    # Add a record first
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={"student_ids": [student.id], "points": 2, "reason": "作业完成"},
    )

    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert data["page"] == 1
    assert data["size"] == 20
    # Verify record content
    item = data["items"][0]
    assert item["student_name"] == "张三"
    assert item["points"] == 2
    assert item["reason"] == "作业完成"


@pytest.mark.anyio
async def test_delete_record(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Create a record then delete it."""
    _, cls, student = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={"student_ids": [student.id], "points": 1, "reason": "临时"},
    )
    record_id = resp.json()["created_ids"][0]

    # Delete
    resp = await client.delete(
        f"/api/v1/conduct/classes/{cls.id}/records/{record_id}",
        headers=homeroom_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # Verify gone
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
    )
    assert resp.json()["total"] == 0


@pytest.mark.anyio
async def test_student_rankings(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Add varied points, verify sorted by total descending."""
    school, cls, student = school_class_student
    s2 = Student(name="李四", student_number="2026003", class_id=cls.id, school_id=school.id)
    db.add(s2)
    await db.commit()
    await db.refresh(s2)

    # Give 张三 +3, 李四 +5
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={"student_ids": [student.id], "points": 3, "reason": "a"},
    )
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={"student_ids": [s2.id], "points": 5, "reason": "b"},
    )

    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/rankings/students",
        headers=homeroom_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # 李四 should be rank 1 (5 > 3)
    assert data[0]["student_name"] == "李四"
    assert data[0]["total_points"] == 5
    assert data[0]["rank"] == 1
    assert data[1]["student_name"] == "张三"
    assert data[1]["total_points"] == 3
    assert data[1]["rank"] == 2


# ═══════════════════════════════════════════════════
# Task 11: Rules CRUD
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_create_rule_category(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Create a rule category, verify sort_order."""
    _, cls, _ = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/rules/categories",
        headers=homeroom_headers,
        json={"name": "课堂纪律", "sort_order": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "课堂纪律"
    assert data["sort_order"] == 1
    assert "id" in data


@pytest.mark.anyio
async def test_create_rule_item(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Create an item under a category."""
    _, cls, _ = school_class_student
    # Create category first
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/rules/categories",
        headers=homeroom_headers,
        json={"name": "卫生", "sort_order": 0},
    )
    cat_id = resp.json()["id"]

    # Create item
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/rules/categories/{cat_id}/items",
        headers=homeroom_headers,
        json={"name": "主动打扫", "points": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "主动打扫"
    assert data["points"] == 2
    assert data["category_id"] == cat_id


@pytest.mark.anyio
async def test_get_rules_nested(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Create cat + items, GET rules returns nested structure."""
    _, cls, _ = school_class_student
    # Create category
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/rules/categories",
        headers=homeroom_headers,
        json={"name": "学习习惯", "sort_order": 0},
    )
    cat_id = resp.json()["id"]

    # Create 2 items
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/rules/categories/{cat_id}/items",
        headers=homeroom_headers,
        json={"name": "按时交作业", "points": 1},
    )
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/rules/categories/{cat_id}/items",
        headers=homeroom_headers,
        json={"name": "不交作业", "points": -2},
    )

    # GET rules
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/rules",
        headers=homeroom_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    cat = next(c for c in data if c["id"] == cat_id)
    assert cat["name"] == "学习习惯"
    assert len(cat["items"]) == 2
    names = {item["name"] for item in cat["items"]}
    assert "按时交作业" in names
    assert "不交作业" in names


@pytest.mark.anyio
async def test_delete_category_cascades(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Delete a category, its items are also deleted."""
    _, cls, _ = school_class_student
    # Create category + item
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/rules/categories",
        headers=homeroom_headers,
        json={"name": "待删分类", "sort_order": 0},
    )
    cat_id = resp.json()["id"]
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/rules/categories/{cat_id}/items",
        headers=homeroom_headers,
        json={"name": "待删条目", "points": 1},
    )

    # Delete category
    resp = await client.delete(
        f"/api/v1/conduct/classes/{cls.id}/rules/categories/{cat_id}",
        headers=homeroom_headers,
    )
    assert resp.status_code == 200

    # Verify rules are empty for this class (no more categories)
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/rules",
        headers=homeroom_headers,
    )
    data = resp.json()
    assert all(c["id"] != cat_id for c in data)


# ═══════════════════════════════════════════════════
# Task 12: Groups & Semesters
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_create_group(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Create a group, verify name and avatar."""
    _, cls, _ = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/groups",
        headers=homeroom_headers,
        json={"name": "雄鹰组", "avatar": "🦅"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "雄鹰组"
    assert data["avatar"] == "🦅"
    assert "id" in data


@pytest.mark.anyio
async def test_add_group_members(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Add students to a group."""
    _, cls, student = school_class_student
    # Create group
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/groups",
        headers=homeroom_headers,
        json={"name": "飞龙组"},
    )
    group_id = resp.json()["id"]

    # Add member
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/groups/{group_id}/members",
        headers=homeroom_headers,
        json={"student_ids": [student.id]},
    )
    assert resp.status_code == 200
    assert resp.json()["added"] == 1

    # Verify via GET groups
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/groups",
        headers=homeroom_headers,
    )
    groups = resp.json()
    group = next(g for g in groups if g["id"] == group_id)
    assert len(group["members"]) == 1
    assert group["members"][0]["student_name"] == "张三"


@pytest.mark.anyio
async def test_group_rankings(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Groups with members, ranked by sum of points."""
    school, cls, student = school_class_student
    s2 = Student(name="王五", student_number="2026004", class_id=cls.id, school_id=school.id)
    db.add(s2)
    await db.commit()
    await db.refresh(s2)

    # Create two groups
    resp1 = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/groups",
        headers=homeroom_headers,
        json={"name": "A组"},
    )
    g1_id = resp1.json()["id"]

    resp2 = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/groups",
        headers=homeroom_headers,
        json={"name": "B组"},
    )
    g2_id = resp2.json()["id"]

    # A组 has student (张三), B组 has s2 (王五)
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/groups/{g1_id}/members",
        headers=homeroom_headers,
        json={"student_ids": [student.id]},
    )
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/groups/{g2_id}/members",
        headers=homeroom_headers,
        json={"student_ids": [s2.id]},
    )

    # Give 张三 +2, 王五 +5
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={"student_ids": [student.id], "points": 2, "reason": "a"},
    )
    await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={"student_ids": [s2.id], "points": 5, "reason": "b"},
    )

    # Get group rankings
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/rankings/groups",
        headers=homeroom_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # B组 should be rank 1 (5 > 2)
    assert data[0]["group_name"] == "B组"
    assert data[0]["total_points"] == 5
    assert data[0]["rank"] == 1
    assert data[1]["group_name"] == "A组"
    assert data[1]["total_points"] == 2
    assert data[1]["rank"] == 2


@pytest.mark.anyio
async def test_create_semester(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Create a semester for a class."""
    _, cls, _ = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/semesters",
        headers=homeroom_headers,
        json={
            "name": "2025-2026 第二学期",
            "start_date": "2026-02-20",
            "end_date": "2026-07-10",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "2025-2026 第二学期"
    assert data["start_date"] == "2026-02-20"
    assert data["end_date"] == "2026-07-10"
    assert data["is_current"] is False


@pytest.mark.anyio
async def test_activate_semester(client, db, school_class_student, homeroom_teacher, homeroom_headers):
    """Activate one semester, others become inactive."""
    _, cls, _ = school_class_student
    # Create two semesters
    resp1 = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/semesters",
        headers=homeroom_headers,
        json={"name": "学期1", "start_date": "2025-09-01", "end_date": "2026-01-15"},
    )
    sem1_id = resp1.json()["id"]

    resp2 = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/semesters",
        headers=homeroom_headers,
        json={"name": "学期2", "start_date": "2026-02-20", "end_date": "2026-07-10"},
    )
    sem2_id = resp2.json()["id"]

    # Activate semester 1
    resp = await client.put(
        f"/api/v1/conduct/classes/{cls.id}/semesters/{sem1_id}/activate",
        headers=homeroom_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_current"] is True

    # Activate semester 2 — semester 1 should become inactive
    resp = await client.put(
        f"/api/v1/conduct/classes/{cls.id}/semesters/{sem2_id}/activate",
        headers=homeroom_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_current"] is True

    # List semesters — only sem2 should be current
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/semesters",
        headers=homeroom_headers,
    )
    semesters = resp.json()
    for s in semesters:
        if s["id"] == sem2_id:
            assert s["is_current"] is True
        else:
            assert s["is_current"] is False


# ── T1 (R1-F006 入口级 + R5-F001 scope 隔离): ──

@pytest.mark.anyio
async def test_lesson_prep_leader_cannot_call_conduct_api(
    client, db, school_class_student,
):
    import uuid
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token

    school, cls, _ = school_class_student

    user = User(
        username=f"lpl_{uuid.uuid4().hex[:8]}",
        display_name="备课组长",
    )
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(
        user_id=user.id,
        role="lesson_prep_leader",
        school_id=school.id,
        is_primary=True,
        class_ids=[cls.id],
    )
    db.add(role)
    await db.commit()

    token = create_access_token({"sub": user.id, "role": "lesson_prep_leader"})
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/rankings/students",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_subject_teacher_with_same_scope_passes_rbac(
    client, db, school_class_student,
):
    import uuid
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token

    school, cls, _ = school_class_student

    user = User(
        username=f"st_{uuid.uuid4().hex[:8]}",
        display_name="科任教师对照组",
    )
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(
        user_id=user.id,
        role="subject_teacher",
        school_id=school.id,
        is_primary=True,
        class_ids=[cls.id],
    )
    db.add(role)
    await db.commit()

    token = create_access_token({"sub": user.id, "role": "subject_teacher"})
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/rankings/students",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


# ── T2 (2026-04-14): AddPointsRequest.date → record_date rename ──

@pytest.mark.anyio
async def test_add_points_with_record_date_field(
    client, db, school_class_student, homeroom_teacher, homeroom_headers,
):
    """T2: 传 record_date → 200 + DB Record.date == 传入值."""
    from sqlalchemy import select
    from edu_cloud.modules.conduct.models import ConductRecord

    school, cls, student = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={
            "student_ids": [student.id],
            "points": 5,
            "reason": "T2 record_date 测试",
            "record_date": "2026-04-10",
        },
    )
    assert resp.status_code == 200, resp.text
    created_ids = resp.json()["created_ids"]
    assert len(created_ids) == 1

    rec = (await db.execute(
        select(ConductRecord).where(ConductRecord.id == created_ids[0])
    )).scalar_one()
    assert str(rec.date) == "2026-04-10"


@pytest.mark.anyio
async def test_add_points_without_record_date_defaults_today(
    client, db, school_class_student, homeroom_teacher, homeroom_headers,
):
    """T2: 不传 record_date → 200 + DB Record.date == today."""
    from datetime import date as _date
    from sqlalchemy import select
    from edu_cloud.modules.conduct.models import ConductRecord

    school, cls, student = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={
            "student_ids": [student.id],
            "points": 5,
            "reason": "T2 默认日期测试",
        },
    )
    assert resp.status_code == 200, resp.text
    created_ids = resp.json()["created_ids"]

    rec = (await db.execute(
        select(ConductRecord).where(ConductRecord.id == created_ids[0])
    )).scalar_one()
    assert rec.date == _date.today()


@pytest.mark.anyio
async def test_add_points_with_record_date_null_defaults_today(
    client, db, school_class_student, homeroom_teacher, homeroom_headers,
):
    """T2: 显式 record_date=null → 200 + DB Record.date == today."""
    from datetime import date as _date
    from sqlalchemy import select
    from edu_cloud.modules.conduct.models import ConductRecord

    school, cls, student = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={
            "student_ids": [student.id],
            "points": 5,
            "reason": "T2 null 日期测试",
            "record_date": None,
        },
    )
    assert resp.status_code == 200, resp.text
    created_ids = resp.json()["created_ids"]

    rec = (await db.execute(
        select(ConductRecord).where(ConductRecord.id == created_ids[0])
    )).scalar_one()
    assert rec.date == _date.today()
