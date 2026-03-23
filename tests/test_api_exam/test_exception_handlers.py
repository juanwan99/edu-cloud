"""验证全局异常处理器将 service 层异常正确映射为 HTTP 响应。"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def exc_setup(client, db):
    school = School(id="exc_s", name="ExcTest", code="EXC01")
    db.add(school)
    await db.commit()
    admin = User(id="exc_u", username="excadmin", display_name="A")
    admin.set_password("p")
    db.add(admin)
    await db.commit()
    db.add(UserRole(user_id=admin.id, role="admin", school_id="exc_s", is_primary=True))
    await db.flush()
    exam = Exam(id="exc_exam", name="考试", card_title="考试", school_id="exc_s", status="draft")
    db.add(exam)
    await db.commit()
    token = create_access_token({"sub": "exc_u", "school_id": "exc_s", "role": "admin"})
    return {"headers": {"Authorization": f"Bearer {token}"}}


async def test_not_found_error_returns_404(client, exc_setup):
    """NotFoundError → 404 with JSON detail."""
    resp = await client.get("/api/v1/exams/nonexistent-id-12345",
                            headers=exc_setup["headers"])
    assert resp.status_code == 404
    assert "detail" in resp.json()


async def test_permission_denied_returns_403(client, db, exc_setup):
    """PermissionDeniedError → 403. 使用 student import 触发权限拒绝。"""
    from edu_cloud.models.student import Class
    c = Class(id="exc_c1", name="1班", grade="高二", school_id="exc_s")
    db.add(c)
    await db.commit()
    # teacher with class_ids=["other"] cannot import to exc_c1
    teacher = User(id="exc_t", username="exct", display_name="T")
    teacher.set_password("p")
    db.add(teacher)
    await db.commit()
    db.add(UserRole(user_id=teacher.id, role="teacher", school_id="exc_s", is_primary=True, class_ids=["other_class"]))
    await db.flush()
    token = create_access_token({"sub": "exc_t", "school_id": "exc_s", "role": "teacher"})
    import openpyxl, io
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["姓名", "准考证号"])
    ws.append(["张三", "X001"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        "/api/v1/students/import",
        files={"file": ("s.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"class_id": "exc_c1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "detail" in resp.json()


async def test_validation_error_returns_422(client, exc_setup):
    """ValidationError → 422. 使用非法状态转换触发。"""
    resp = await client.patch(
        "/api/v1/exams/exc_exam",
        json={"status": "grading"},  # draft → grading 不合法
        headers=exc_setup["headers"],
    )
    assert resp.status_code == 422  # edu-cloud: SvcValidationError → 422
    assert "detail" in resp.json()
