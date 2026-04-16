import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def task_setup(client, db):
    school = School(name="Test", code="TK01")
    db.add(school)
    await db.commit()
    user = User(username="t", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    exam = Exam(name="E", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="Math", code="math", school_id=school.id)
    db.add(subject)
    await db.commit()
    return headers, subject.id


async def test_create_scan_task(client, task_setup):
    headers, subject_id = task_setup
    resp = await client.post(
        "/api/v1/scan/tasks",
        json={"subject_id": subject_id, "side": "A", "total_images": 30},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["total_images"] == 30


async def test_update_scan_task(client, task_setup):
    headers, subject_id = task_setup
    create_resp = await client.post(
        "/api/v1/scan/tasks",
        json={"subject_id": subject_id, "side": "A", "total_images": 10},
        headers=headers,
    )
    task_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/scan/tasks/{task_id}",
        json={"processed": 5, "failed": 1, "status": "processing"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["processed"] == 5
    assert resp.json()["failed"] == 1


async def test_get_scan_task(client, task_setup):
    headers, subject_id = task_setup
    create_resp = await client.post(
        "/api/v1/scan/tasks",
        json={"subject_id": subject_id, "side": "A", "total_images": 20},
        headers=headers,
    )
    task_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/scan/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


async def test_create_scan_task_invalid_side(client, task_setup):
    headers, subject_id = task_setup
    resp = await client.post(
        "/api/v1/scan/tasks",
        json={"subject_id": subject_id, "side": "X", "total_images": 10},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_update_scan_task_invalid_status(client, task_setup):
    headers, subject_id = task_setup
    create_resp = await client.post(
        "/api/v1/scan/tasks",
        json={"subject_id": subject_id, "side": "A", "total_images": 10},
        headers=headers,
    )
    task_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/scan/tasks/{task_id}",
        json={"status": "invalid_status"},
        headers=headers,
    )
    assert resp.status_code == 422
