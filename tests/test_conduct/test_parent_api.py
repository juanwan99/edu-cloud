"""Parent registration/login/bind API tests."""
import pytest
from datetime import date

from edu_cloud.models.user import User
from edu_cloud.modules.conduct.models import (
    ConductRecord, ConductRuleCategory, ConductRuleItem, StudentProfile,
)
from edu_cloud.modules.conduct.crypto import encrypt


@pytest.mark.anyio
async def test_invite_code_info(client, db, conduct_config, school_class_student):
    """GET /invite/TEST01/info returns class_name and verify_code_type."""
    resp = await client.get("/api/v1/conduct/invite/TEST01/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["class_name"] == "高一(1)班"
    assert data["verify_code_type"] == "custom"
    assert "school_name" in data


@pytest.mark.anyio
async def test_invite_code_invalid(client, db, conduct_config):
    """GET /invite/BADCODE/info returns 404."""
    resp = await client.get("/api/v1/conduct/invite/BADCODE/info")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_parent_register_and_login(client, db, conduct_config):
    """Register → login → GET /parent/me returns empty children."""
    # Register
    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "TEST01",
        "display_name": "李妈妈",
        "phone": "13800000001",
        "password": "abc123",
    })
    assert resp.status_code == 200
    token1 = resp.json()["access_token"]
    assert token1

    # Login
    resp = await client.post("/api/v1/conduct/parent/login", json={
        "phone": "13800000001",
        "password": "abc123",
    })
    assert resp.status_code == 200
    token2 = resp.json()["access_token"]
    assert token2

    # GET /parent/me
    headers = {"Authorization": f"Bearer {token2}"}
    resp = await client.get("/api/v1/conduct/parent/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "李妈妈"
    assert data["children"] == []


@pytest.mark.anyio
async def test_parent_register_duplicate_phone(client, db, conduct_config):
    """Duplicate phone → 422 (ValidationError)."""
    payload = {
        "invite_code": "TEST01",
        "display_name": "王爸爸",
        "phone": "13800000002",
        "password": "abc123",
    }
    resp = await client.post("/api/v1/conduct/parent/register", json=payload)
    assert resp.status_code == 200

    # Second registration with same phone
    payload["display_name"] = "王爸爸2号"
    resp = await client.post("/api/v1/conduct/parent/register", json=payload)
    assert resp.status_code == 422
    assert "已注册" in resp.json()["detail"]


@pytest.mark.anyio
async def test_parent_bind_child(client, db, conduct_config, school_class_student):
    """Register → set verify_code → bind → GET /parent/children returns 1 child."""
    school, cls, student = school_class_student

    # Set up StudentProfile with encrypted verify_code
    profile = StudentProfile(
        student_id=student.id,
        verify_code=encrypt("VCODE1"),
    )
    db.add(profile)
    await db.commit()

    # Register parent
    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "TEST01",
        "display_name": "绑定家长",
        "phone": "13800000003",
        "password": "abc123",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Bind child
    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": "VCODE1",
        "relationship": "mother",
    })
    assert resp.status_code == 200
    assert resp.json()["student_name"] == "张三"

    # GET /parent/children
    resp = await client.get("/api/v1/conduct/parent/children", headers=headers)
    assert resp.status_code == 200
    children = resp.json()
    assert len(children) == 1
    assert children[0]["student_name"] == "张三"
    assert children[0]["relationship"] == "mother"
    assert children[0]["total_points"] == 0


@pytest.mark.anyio
async def test_parent_bind_wrong_code(client, db, conduct_config, school_class_student):
    """Bind with wrong code → 422."""
    school, cls, student = school_class_student

    # Set up StudentProfile with encrypted verify_code
    profile = StudentProfile(
        student_id=student.id,
        verify_code=encrypt("CORRECT"),
    )
    db.add(profile)
    await db.commit()

    # Register parent
    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "TEST01",
        "display_name": "验证码错家长",
        "phone": "13800000004",
        "password": "abc123",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Bind with wrong verify code
    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": "WRONG",
    })
    assert resp.status_code == 422
    assert "验证码错误" in resp.json()["detail"]


# ── Helper: register + bind parent, return (token, headers, student) ──

async def _register_and_bind(client, db, school_class_student, phone, name="测试家长"):
    """Register a parent, bind to student, return (token, headers, student)."""
    school, cls, student = school_class_student

    # Ensure StudentProfile with verify_code exists
    from sqlalchemy import select
    existing = (await db.execute(
        select(StudentProfile).where(StudentProfile.student_id == student.id)
    )).scalar_one_or_none()
    if not existing:
        profile = StudentProfile(student_id=student.id, verify_code=encrypt("BIND01"))
        db.add(profile)
        await db.commit()

    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "TEST01",
        "display_name": name,
        "phone": phone,
        "password": "abc123",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": "BIND01",
    })
    assert resp.status_code == 200
    return token, headers, student


# ── Task 5: Parent query API tests ──


@pytest.mark.anyio
async def test_parent_get_child_records(client, db, conduct_config, school_class_student):
    """Bind child, add a ConductRecord, GET records returns 1 item."""
    school, cls, student = school_class_student
    token, headers, student = await _register_and_bind(
        client, db, school_class_student, "13800100001",
    )

    # Create an operator user for the record
    operator = User(username="op_teacher", display_name="王老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()

    record = ConductRecord(
        student_id=student.id,
        class_id=cls.id,
        points=5,
        reason="课堂表现优秀",
        date=date(2026, 4, 10),
        operator_id=operator.id,
    )
    db.add(record)
    await db.commit()

    resp = await client.get(
        f"/api/v1/conduct/parent/children/{student.id}/records",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["points"] == 5
    assert data["items"][0]["operator_name"] == "王老师"
    assert data["items"][0]["reason"] == "课堂表现优秀"


@pytest.mark.anyio
async def test_parent_get_unbound_child_records_forbidden(
    client, db, conduct_config, school_class_student,
):
    """GET records for unbound student returns 403."""
    school, cls, student = school_class_student

    # Register parent but do NOT bind
    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "TEST01",
        "display_name": "未绑定家长",
        "phone": "13800200001",
        "password": "abc123",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"/api/v1/conduct/parent/children/{student.id}/records",
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_parent_get_rankings(client, db, conduct_config, school_class_student):
    """Add records for multiple students, GET rankings returns sorted list."""
    school, cls, student = school_class_student
    token, headers, student = await _register_and_bind(
        client, db, school_class_student, "13800300001",
    )

    # Create a second student in same class
    from edu_cloud.modules.student.models import Student
    student2 = Student(
        name="李四", student_number="2026002", class_id=cls.id, school_id=school.id,
    )
    db.add(student2)
    await db.flush()

    # Create operator
    operator = User(username="op_rank", display_name="排名老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()

    # 张三 gets 10 points, 李四 gets 20 points
    db.add(ConductRecord(
        student_id=student.id, class_id=cls.id, points=10,
        reason="a", date=date(2026, 4, 10), operator_id=operator.id,
    ))
    db.add(ConductRecord(
        student_id=student2.id, class_id=cls.id, points=20,
        reason="b", date=date(2026, 4, 10), operator_id=operator.id,
    ))
    await db.commit()

    resp = await client.get(
        f"/api/v1/conduct/parent/children/{student.id}/rankings",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # 李四 (20) should be rank 1, 张三 (10) rank 2
    assert data[0]["student_name"] == "李四"
    assert data[0]["total_points"] == 20
    assert data[0]["rank"] == 1
    assert data[1]["student_name"] == "张三"
    assert data[1]["is_self"] is True
    assert data[1]["rank"] == 2


@pytest.mark.anyio
async def test_parent_get_class_rules(client, db, conduct_config, school_class_student):
    """Create ConductRuleCategory + items, GET rules returns nested structure."""
    school, cls, student = school_class_student
    token, headers, _ = await _register_and_bind(
        client, db, school_class_student, "13800400001",
    )

    # Create a rule category with items
    cat = ConductRuleCategory(
        name="课堂纪律", class_id=cls.id, scope="class", sort_order=1,
    )
    db.add(cat)
    await db.flush()

    item1 = ConductRuleItem(name="迟到", points=-2, category_id=cat.id, sort_order=1)
    item2 = ConductRuleItem(name="积极发言", points=3, category_id=cat.id, sort_order=2)
    db.add_all([item1, item2])
    await db.commit()

    resp = await client.get(
        f"/api/v1/conduct/parent/classes/{cls.id}/rules",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "课堂纪律"
    assert len(data[0]["items"]) == 2
    assert data[0]["items"][0]["name"] == "迟到"
    assert data[0]["items"][0]["points"] == -2
    assert data[0]["items"][1]["name"] == "积极发言"
    assert data[0]["items"][1]["points"] == 3


@pytest.mark.anyio
async def test_parent_get_class_rules_rejects_unbound_class(
    client, db, conduct_config, school_class_student,
):
    """Guardian bound to class A must NOT read class B rules (grading-dispatch F003).

    Reverse-proof: removing `_verify_guardian_class` call returns 200 instead of 403,
    so this test actually fails under the buggy implementation.
    """
    from edu_cloud.modules.student.models import Class

    school, cls_a, _ = school_class_student
    token, headers, _ = await _register_and_bind(
        client, db, school_class_student, "13800700001",
    )

    # Create a second class B in the same school; guardian has no binding to it
    cls_b = Class(name="高一(2)班", grade="高一", grade_number=1, school_id=school.id)
    db.add(cls_b)
    await db.commit()

    # Bound class A still works → 200
    resp_a = await client.get(
        f"/api/v1/conduct/parent/classes/{cls_a.id}/rules", headers=headers,
    )
    assert resp_a.status_code == 200

    # Unbound class B rejected → 403
    resp_b = await client.get(
        f"/api/v1/conduct/parent/classes/{cls_b.id}/rules", headers=headers,
    )
    assert resp_b.status_code == 403


@pytest.mark.anyio
async def test_parent_change_password(client, db, conduct_config, school_class_student):
    """Change password, then login with new password succeeds."""
    token, headers, _ = await _register_and_bind(
        client, db, school_class_student, "13800500001", name="改密家长",
    )

    # Change password
    resp = await client.put("/api/v1/conduct/parent/password", headers=headers, json={
        "old_password": "abc123",
        "new_password": "newpass789",
    })
    assert resp.status_code == 200
    assert "成功" in resp.json()["message"]

    # Login with new password
    resp = await client.post("/api/v1/conduct/parent/login", json={
        "phone": "13800500001",
        "password": "newpass789",
    })
    assert resp.status_code == 200
    assert resp.json()["access_token"]

    # Old password should fail
    resp = await client.post("/api/v1/conduct/parent/login", json={
        "phone": "13800500001",
        "password": "abc123",
    })
    assert resp.status_code == 422


# ── F006: 补入口级红测 — phone / id_card 绑定模式 ──

@pytest.mark.anyio
async def test_parent_bind_phone_mode(client, db, school_class_student):
    """F006: phone 模式下绑定通过 profile.verify_code 验证（与 custom 共享存储路径）."""
    school, cls, student = school_class_student
    from edu_cloud.modules.conduct.models import ConductClassConfig
    # 切换班级到 phone 验证模式
    config = ConductClassConfig(class_id=cls.id, invite_code="PHN001", verify_code_type="phone")
    db.add(config)
    # 班主任为学生预设手机号（存入 verify_code 字段，加密）
    profile = StudentProfile(student_id=student.id, verify_code=encrypt("13912345678"))
    db.add(profile)
    await db.commit()

    # 注册家长
    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "PHN001",
        "display_name": "手机家长",
        "phone": "13800006001",
        "password": "abc123",
    })
    assert resp.status_code == 200
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # 正确手机号 → 绑定成功
    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": "13912345678",
        "relationship": "father",
    })
    assert resp.status_code == 200, f"phone 模式绑定失败: {resp.json()}"
    assert resp.json()["student_name"] == "张三"


@pytest.mark.anyio
async def test_parent_bind_phone_mode_wrong_code(client, db, school_class_student):
    """F006: phone 模式错误手机号 → 422 + 提示'手机号验证失败'."""
    school, cls, student = school_class_student
    from edu_cloud.modules.conduct.models import ConductClassConfig
    config = ConductClassConfig(class_id=cls.id, invite_code="PHN002", verify_code_type="phone")
    db.add(config)
    profile = StudentProfile(student_id=student.id, verify_code=encrypt("13912345678"))
    db.add(profile)
    await db.commit()

    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "PHN002",
        "display_name": "错手机家长",
        "phone": "13800006002",
        "password": "abc123",
    })
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": "13900000000",  # wrong
    })
    assert resp.status_code == 422
    assert "手机号验证失败" in resp.json()["detail"]


@pytest.mark.anyio
async def test_parent_bind_id_card_mode(client, db, school_class_student):
    """N001/F005 Option A: id_card 模式比对身份证号后 6 位（锁定契约）."""
    school, cls, student = school_class_student
    from edu_cloud.modules.conduct.models import ConductClassConfig
    config = ConductClassConfig(class_id=cls.id, invite_code="IDC001", verify_code_type="id_card")
    db.add(config)
    # 服务端存全串加密；客户端仅提交后 6 位（Option A）
    id_full = "310101200801011234"
    id_last6 = id_full[-6:]  # "011234"
    profile = StudentProfile(student_id=student.id, id_card_number=encrypt(id_full))
    db.add(profile)
    await db.commit()

    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "IDC001",
        "display_name": "身份证家长",
        "phone": "13800006003",
        "password": "abc123",
    })
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # 后 6 位绑定成功
    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": id_last6,
    })
    assert resp.status_code == 200, f"id_card 后 6 位绑定失败: {resp.json()}"


@pytest.mark.anyio
async def test_parent_bind_id_card_full_string_rejected(client, db, school_class_student):
    """N001 回归防线: 客户端传完整 18 位身份证号 → 拒绝（防 Round 2 整串相等契约复活）."""
    school, cls, student = school_class_student
    from edu_cloud.modules.conduct.models import ConductClassConfig
    config = ConductClassConfig(class_id=cls.id, invite_code="IDC003", verify_code_type="id_card")
    db.add(config)
    id_full = "310101200801011234"
    profile = StudentProfile(student_id=student.id, id_card_number=encrypt(id_full))
    db.add(profile)
    await db.commit()

    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "IDC003",
        "display_name": "整串家长",
        "phone": "13800006005",
        "password": "abc123",
    })
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # 18 位完整身份证号 → 后 6 位对比自然失败（整串 ≠ 后 6 位）
    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": id_full,
    })
    assert resp.status_code == 422, f"整串身份证号未被拒绝: {resp.status_code} {resp.text[:200]}"
    assert "身份证号验证失败" in resp.json()["detail"]


@pytest.mark.anyio
async def test_parent_bind_id_card_wrong_6_digits(client, db, school_class_student):
    """N001 反向边界: 错误的后 6 位 → 拒绝."""
    school, cls, student = school_class_student
    from edu_cloud.modules.conduct.models import ConductClassConfig
    config = ConductClassConfig(class_id=cls.id, invite_code="IDC004", verify_code_type="id_card")
    db.add(config)
    id_full = "310101200801011234"  # 正确后 6 位: 011234
    profile = StudentProfile(student_id=student.id, id_card_number=encrypt(id_full))
    db.add(profile)
    await db.commit()

    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "IDC004",
        "display_name": "错6位家长",
        "phone": "13800006006",
        "password": "abc123",
    })
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": "999999",  # 错误 6 位
    })
    assert resp.status_code == 422
    assert "身份证号验证失败" in resp.json()["detail"]


@pytest.mark.anyio
async def test_parent_bind_id_card_mode_wrong(client, db, school_class_student):
    """F006: id_card 模式错误身份证 → 422 + 提示'身份证号验证失败'."""
    school, cls, student = school_class_student
    from edu_cloud.modules.conduct.models import ConductClassConfig
    config = ConductClassConfig(class_id=cls.id, invite_code="IDC002", verify_code_type="id_card")
    db.add(config)
    profile = StudentProfile(student_id=student.id, id_card_number=encrypt("310101200801011234"))
    db.add(profile)
    await db.commit()

    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "IDC002",
        "display_name": "错身份证家长",
        "phone": "13800006004",
        "password": "abc123",
    })
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": "999999999999999999",
    })
    assert resp.status_code == 422
    assert "身份证号验证失败" in resp.json()["detail"]


# ── F004: get_children 返回 class_id ──

@pytest.mark.anyio
async def test_get_children_returns_class_id(client, db, conduct_config, school_class_student):
    """F004: GET /parent/children 必须返回 class_id 以便前端班规页请求."""
    token, headers, student = await _register_and_bind(
        client, db, school_class_student, "13800006005", name="F004 家长",
    )
    resp = await client.get("/api/v1/conduct/parent/children", headers=headers)
    assert resp.status_code == 200
    children = resp.json()
    assert len(children) == 1
    # 关键断言：class_id 字段必须存在且非空
    assert "class_id" in children[0], "get_children 必须返回 class_id (F004)"
    assert children[0]["class_id"], "class_id 不能为空字符串"


# ── Phase 3: behavior-summary endpoint ──

@pytest.mark.anyio
async def test_parent_behavior_summary(client, db, conduct_config, school_class_student):
    """GET /parent/children/{id}/behavior-summary returns structured behavior data."""
    school, cls, student = school_class_student
    token, headers, student = await _register_and_bind(
        client, db, school_class_student, "13800800001",
    )

    # Create some conduct records to analyze
    operator = User(username="op_behavior", display_name="行为老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()

    db.add(ConductRecord(
        student_id=student.id, class_id=cls.id, points=5,
        reason="表现优秀", date=date.today(), operator_id=operator.id,
    ))
    db.add(ConductRecord(
        student_id=student.id, class_id=cls.id, points=-2,
        reason="迟到", date=date.today(), operator_id=operator.id,
    ))
    await db.commit()

    resp = await client.get(
        f"/api/v1/conduct/parent/children/{student.id}/behavior-summary",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_name"] == "张三"
    assert data["trend"] in ("improving", "declining", "stable")
    assert data["trend_label"] in ("进步中", "需关注", "保持稳定")
    assert data["total_points"] == 3  # 5 + (-2)
    assert data["positive_count"] == 1
    assert data["negative_count"] == 1
    assert isinstance(data["top_issues"], list)
    assert isinstance(data["positive_streak_days"], int)


@pytest.mark.anyio
async def test_parent_behavior_summary_unbound_rejected(
    client, db, conduct_config, school_class_student,
):
    """GET behavior-summary for unbound student → 403."""
    school, cls, student = school_class_student

    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "TEST01",
        "display_name": "未绑定行为家长",
        "phone": "13800800002",
        "password": "abc123",
    })
    assert resp.status_code == 200
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = await client.get(
        f"/api/v1/conduct/parent/children/{student.id}/behavior-summary",
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_parent_behavior_summary_empty_records(
    client, db, conduct_config, school_class_student,
):
    """GET behavior-summary with no records returns stable/zero."""
    token, headers, student = await _register_and_bind(
        client, db, school_class_student, "13800800003",
    )

    resp = await client.get(
        f"/api/v1/conduct/parent/children/{student.id}/behavior-summary",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trend"] == "stable"
    assert data["trend_label"] == "保持稳定"
    assert data["total_points"] == 0
    assert data["positive_count"] == 0
    assert data["negative_count"] == 0
    assert data["top_issues"] == []
    assert data["positive_streak_days"] == 0
