import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def auth_and_subject(client, db):
    school = School(name="Test School", code="TP01")
    db.add(school)
    await db.commit()
    user = User(username="teacher", display_name="T")
    user.set_password("pass")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="期中", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    db.add(subject)
    await db.commit()
    return headers, school.id, subject.id


SAMPLE_TEMPLATE = {
    "image_width": 2480,
    "image_height": 3508,
    "anchors": [
        {"id": "tl", "cx": 100, "cy": 100, "x": 80, "y": 80, "w": 40, "h": 40},
        {"id": "tr", "cx": 2380, "cy": 100, "x": 2360, "y": 80, "w": 40, "h": 40},
        {"id": "bl", "cx": 100, "cy": 3408, "x": 80, "y": 3388, "w": 40, "h": 40},
    ],
    "regions": [
        {"id": "q1", "name": "第1题", "type": "subjective", "rect": {"x1": 200, "y1": 300, "x2": 2200, "y2": 800}, "score": 10},
        {"id": "q2", "name": "第2题", "type": "subjective", "rect": {"x1": 200, "y1": 850, "x2": 2200, "y2": 1400}, "score": 15},
    ],
}


async def test_put_template(client, auth_and_subject):
    headers, _, subject_id = auth_and_subject
    resp = await client.put(
        f"/api/v1/templates/{subject_id}/A",
        json=SAMPLE_TEMPLATE,
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject_id"] == subject_id
    assert data["side"] == "A"
    assert len(data["regions"]) == 2


async def test_put_template_upsert(client, auth_and_subject):
    headers, _, subject_id = auth_and_subject
    await client.put(f"/api/v1/templates/{subject_id}/A", json=SAMPLE_TEMPLATE, headers=headers)
    updated = {**SAMPLE_TEMPLATE, "regions": SAMPLE_TEMPLATE["regions"][:1]}
    resp = await client.put(f"/api/v1/templates/{subject_id}/A", json=updated, headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["regions"]) == 1


async def test_get_template(client, auth_and_subject):
    headers, _, subject_id = auth_and_subject
    await client.put(f"/api/v1/templates/{subject_id}/A", json=SAMPLE_TEMPLATE, headers=headers)
    resp = await client.get(f"/api/v1/templates/{subject_id}/A", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["image_width"] == 2480


async def test_get_template_not_found(client, auth_and_subject):
    headers, _, subject_id = auth_and_subject
    resp = await client.get(f"/api/v1/templates/{subject_id}/A", headers=headers)
    assert resp.status_code == 404


async def test_get_all_templates_for_subject(client, auth_and_subject):
    headers, _, subject_id = auth_and_subject
    await client.put(f"/api/v1/templates/{subject_id}/A", json=SAMPLE_TEMPLATE, headers=headers)
    await client.put(f"/api/v1/templates/{subject_id}/B", json=SAMPLE_TEMPLATE, headers=headers)
    resp = await client.get(f"/api/v1/templates/{subject_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_put_template_invalid_side(client, auth_and_subject):
    headers, _, subject_id = auth_and_subject
    resp = await client.put(
        f"/api/v1/templates/{subject_id}/X",
        json=SAMPLE_TEMPLATE,
        headers=headers,
    )
    assert resp.status_code == 422
