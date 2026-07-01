import pytest
from httpx import AsyncClient

from edu_cloud.ai.ref_types import REF_TYPES, RefType, RefItem


def test_ref_types_registry():
    assert len(REF_TYPES) >= 5
    codes = [t.type_code for t in REF_TYPES]
    assert "exam" in codes
    assert "class" in codes
    assert "student" in codes


def test_exam_has_children_type():
    exam = next(t for t in REF_TYPES if t.type_code == "exam")
    assert exam.children_type == "subject"


def test_ref_item_to_dict():
    item = RefItem(id="abc", label="Test", subtitle="sub", children_type="subject")
    d = item.to_dict()
    assert d == {"id": "abc", "label": "Test", "subtitle": "sub", "children_type": "subject"}


def test_ref_item_minimal():
    item = RefItem(id="x", label="Y")
    d = item.to_dict()
    assert d["children_type"] is None
    assert d["subtitle"] is None


@pytest.mark.asyncio
async def test_ai_ref_resolver_delegates_exam_data_access(monkeypatch):
    from edu_cloud.ai import ref_resolvers
    from edu_cloud.services import ai_ref_resolvers as service_refs

    calls = []

    async def fake_resolve_exam(db, school_id, search, parent_id, limit):
        calls.append((db, school_id, search, parent_id, limit))
        return [
            service_refs.RefRecord(
                id="exam-1",
                label="Exam 1",
                subtitle="draft",
                children_type="subject",
            )
        ]

    monkeypatch.setattr(service_refs, "resolve_exam", fake_resolve_exam)
    db = object()

    items = await ref_resolvers.resolve_exam(db, "school-1", "Exam", None, 3)

    assert calls == [(db, "school-1", "Exam", None, 3)]
    assert [item.to_dict() for item in items] == [
        {"id": "exam-1", "label": "Exam 1", "subtitle": "draft", "children_type": "subject"}
    ]


@pytest.mark.asyncio
async def test_ref_types_endpoint(client: AsyncClient, admin_headers):
    resp = await client.get("/api/v1/ai/ref-types", headers=admin_headers)
    assert resp.status_code == 200
    types = resp.json()
    assert isinstance(types, list)
    codes = [t["type_code"] for t in types]
    assert "exam" in codes
    assert "class" in codes


@pytest.mark.asyncio
async def test_refs_exam(client: AsyncClient, admin_headers, seed_exam_with_results):
    resp = await client.get(
        "/api/v1/ai/refs", params={"type": "exam"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_refs_unknown_type(client: AsyncClient, admin_headers):
    resp = await client.get(
        "/api/v1/ai/refs", params={"type": "nonexistent"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refs_class(client: AsyncClient, admin_headers, seed_exam_with_results):
    resp = await client.get(
        "/api/v1/ai/refs", params={"type": "class"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_refs_student_with_parent(client: AsyncClient, admin_headers, seed_exam_with_results):
    # First get a class
    cls_resp = await client.get(
        "/api/v1/ai/refs", params={"type": "class"},
        headers=admin_headers,
    )
    classes = cls_resp.json()["items"]
    if classes:
        class_id = classes[0]["id"]
        resp = await client.get(
            "/api/v1/ai/refs",
            params={"type": "student", "parent_id": class_id},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "items" in resp.json()
