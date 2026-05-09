"""Task 3 + Task 6: Card tenant path isolation and Template school_id filtering.

Tests confirm:
- render_doc_pages / get_doc_pages / get_doc_page_image enforce subject ownership
- Template queries in template_router, card_export_router, and router.py include school_id
"""
import pytest
from sqlalchemy import select

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.modules.card.models import Template
from edu_cloud.shared.auth import create_access_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_two_schools(db):
    """Create two schools, each with an exam/subject/template."""
    school_a = School(name="Card-Iso-A", code="CARDA")
    school_b = School(name="Card-Iso-B", code="CARDB")
    db.add_all([school_a, school_b])
    await db.flush()

    exam_a = Exam(name="Exam-A", card_title="Exam A", school_id=school_a.id, status="scanning")
    exam_b = Exam(name="Exam-B", card_title="Exam B", school_id=school_b.id, status="scanning")
    db.add_all([exam_a, exam_b])
    await db.flush()

    subj_a = Subject(exam_id=exam_a.id, name="Math-A", code="SX", school_id=school_a.id)
    subj_b = Subject(exam_id=exam_b.id, name="Math-B", code="SX", school_id=school_b.id)
    db.add_all([subj_a, subj_b])
    await db.flush()

    tpl_a = Template(
        subject_id=subj_a.id, side="A", school_id=school_a.id,
        image_width=2400, image_height=3400,
        anchors=[{"x": 0, "y": 0}],
        regions=[{"type": "essay", "qno": "1", "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}],
    )
    tpl_b = Template(
        subject_id=subj_b.id, side="A", school_id=school_b.id,
        image_width=2400, image_height=3400,
        anchors=[{"x": 0, "y": 0}],
        regions=[{"type": "essay", "qno": "1", "rect": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}],
    )
    db.add_all([tpl_a, tpl_b])
    await db.flush()

    # User A: academic_director in school A (has MANAGE_EXAMS + VIEW_EXAMS)
    user_a = User(username="card_iso_a", display_name="Director-A")
    user_a.set_password("123456")
    db.add(user_a)
    await db.flush()
    db.add(UserRole(user_id=user_a.id, role="academic_director", school_id=school_a.id, is_primary=True))

    # User B: academic_director in school B
    user_b = User(username="card_iso_b", display_name="Director-B")
    user_b.set_password("123456")
    db.add(user_b)
    await db.flush()
    db.add(UserRole(user_id=user_b.id, role="academic_director", school_id=school_b.id, is_primary=True))

    await db.commit()
    return {
        "school_a": school_a, "school_b": school_b,
        "exam_a": exam_a, "exam_b": exam_b,
        "subj_a": subj_a, "subj_b": subj_b,
        "tpl_a": tpl_a, "tpl_b": tpl_b,
        "user_a": user_a, "user_b": user_b,
    }


async def _login(client, username):
    resp = await client.post("/api/v1/auth/login", json={
        "username": username, "password": "123456",
    })
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Task 3: File path tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_doc_pages_rejects_other_school_subject(client, db):
    """get_doc_pages must reject subject_id from another school."""
    data = await _seed_two_schools(db)
    token = await _login(client, "card_iso_a")
    h = {"Authorization": f"Bearer {token}"}

    # User A tries to access school B's subject doc pages
    resp = await client.get(
        "/api/v1/card/doc-pages",
        params={"subject_id": data["subj_b"].id},
        headers=h,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_doc_pages_allows_own_school_subject(client, db):
    """get_doc_pages must allow subject_id from own school."""
    data = await _seed_two_schools(db)
    token = await _login(client, "card_iso_a")
    h = {"Authorization": f"Bearer {token}"}

    # User A accesses own school's subject doc pages (returns empty since no files)
    resp = await client.get(
        "/api/v1/card/doc-pages",
        params={"subject_id": data["subj_a"].id},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["pages"] == []


@pytest.mark.asyncio
async def test_doc_page_image_rejects_nonexistent_path(client, db):
    """get_doc_page_image returns 404 for non-existent file."""
    data = await _seed_two_schools(db)
    token = await _login(client, "card_iso_a")
    h = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        "/api/v1/card/doc-page-image",
        params={"path": "/uploads/doc-pages/nonexistent/page_1.png"},
        headers=h,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_doc_page_image_rejects_other_school_subject(client, db):
    """get_doc_page_image must reject paths referencing another school's subject."""
    import os
    from edu_cloud.config import settings

    data = await _seed_two_schools(db)
    token = await _login(client, "card_iso_a")
    h = {"Authorization": f"Bearer {token}"}

    # Create a fake file under school B's subject directory
    upload_root = settings.UPLOAD_DIR
    subj_b_dir = os.path.join(upload_root, "doc-pages", data["subj_b"].id)
    os.makedirs(subj_b_dir, exist_ok=True)
    fake_file = os.path.join(subj_b_dir, "page_1.png")
    with open(fake_file, "wb") as f:
        f.write(b"\x89PNG\r\n")  # minimal PNG header

    resp = await client.get(
        "/api/v1/card/doc-page-image",
        params={"path": f"/uploads/doc-pages/{data['subj_b'].id}/page_1.png"},
        headers=h,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Task 6: Template school_id filtering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_template_upsert_filters_by_school_id(client, db):
    """PUT /templates/{subject_id}/{side} must filter existing template by school_id."""
    data = await _seed_two_schools(db)
    token = await _login(client, "card_iso_a")
    h = {"Authorization": f"Bearer {token}"}

    # User A tries to upsert template for school B's subject: should fail (subject not found)
    resp = await client.put(
        f"/api/v1/templates/{data['subj_b'].id}/A",
        json={
            "image_width": 100, "image_height": 100,
            "anchors": [], "regions": [],
        },
        headers=h,
    )
    assert resp.status_code == 404

    # User A upserts own template: should succeed
    resp = await client.put(
        f"/api/v1/templates/{data['subj_a'].id}/A",
        json={
            "image_width": 999, "image_height": 999,
            "anchors": [{"x": 1}], "regions": [{"type": "choice"}],
        },
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["image_width"] == 999


@pytest.mark.asyncio
async def test_template_get_filters_by_school_id(client, db):
    """GET /templates/{subject_id}/{side} must not return other school's template."""
    data = await _seed_two_schools(db)
    token = await _login(client, "card_iso_a")
    h = {"Authorization": f"Bearer {token}"}

    # User A tries to get school B's template: should 404
    resp = await client.get(
        f"/api/v1/templates/{data['subj_b'].id}/A",
        headers=h,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_template_list_filters_by_school_id(client, db):
    """GET /templates/{subject_id} must not list other school's templates."""
    data = await _seed_two_schools(db)
    token = await _login(client, "card_iso_a")
    h = {"Authorization": f"Bearer {token}"}

    # User A lists templates for school B's subject: should be empty
    resp = await client.get(
        f"/api/v1/templates/{data['subj_b'].id}",
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_template_json_filters_by_school_id(client, db):
    """GET /card/template-json must filter Template by school_id."""
    data = await _seed_two_schools(db)
    token = await _login(client, "card_iso_a")
    h = {"Authorization": f"Bearer {token}"}

    # User A tries to export school B's template JSON: should 404 (subject not found)
    resp = await client.get(
        "/api/v1/card/template-json",
        params={"exam_id": data["exam_b"].id, "subject_id": data["subj_b"].id},
        headers=h,
    )
    assert resp.status_code == 404

    # User A exports own template JSON: should succeed
    resp = await client.get(
        "/api/v1/card/template-json",
        params={"exam_id": data["exam_a"].id, "subject_id": data["subj_a"].id},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["image_size"]["width"] == 2400
