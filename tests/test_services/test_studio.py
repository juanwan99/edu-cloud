import pytest
from edu_cloud.templates.document_templates import TEMPLATES, get_templates_for_role
from edu_cloud.services.studio_service import StudioService


def test_templates_have_required_keys():
    for key, tmpl in TEMPLATES.items():
        assert "name" in tmpl, f"{key} missing name"
        assert "sections" in tmpl, f"{key} missing sections"
        assert "available_roles" in tmpl, f"{key} missing available_roles"


def test_get_templates_for_homeroom_teacher():
    templates = get_templates_for_role("homeroom_teacher")
    keys = [t["key"] for t in templates]
    assert "class_report" in keys
    assert "student_comment" in keys


def test_get_templates_for_parent():
    templates = get_templates_for_role("parent")
    assert len(templates) == 0


@pytest.mark.asyncio
async def test_create_document(db, seed_teacher):
    from edu_cloud.models.user_role import UserRole
    from sqlalchemy import select

    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()

    svc = StudioService(db)
    doc = await svc.create_document(
        type="report",
        title="七年级2班期中分析",
        content_json={"overview": "全班表现良好"},
        school_id=role.school_id,
        created_by=seed_teacher.id,
        source_context={"exam_id": "e1", "class_id": "c1"},
    )
    assert doc.status == "draft"
    assert doc.version == 1


@pytest.mark.asyncio
async def test_update_document_creates_version(db, seed_teacher):
    from edu_cloud.models.user_role import UserRole
    from sqlalchemy import select

    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()

    svc = StudioService(db)
    doc = await svc.create_document(
        type="report",
        title="测试",
        content_json={"body": "v1"},
        school_id=role.school_id,
        created_by=seed_teacher.id,
    )
    updated = await svc.update_document(
        doc.id,
        content_json={"body": "v2"},
        edited_by=seed_teacher.id,
        change_summary="修改正文",
    )
    assert updated.version == 2
    assert updated.content_json["body"] == "v2"


@pytest.mark.asyncio
async def test_status_transition_draft_to_reviewed(db, seed_teacher):
    from edu_cloud.models.user_role import UserRole
    from sqlalchemy import select

    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()

    svc = StudioService(db)
    doc = await svc.create_document(
        type="report",
        title="测试",
        content_json={},
        school_id=role.school_id,
        created_by=seed_teacher.id,
    )
    doc = await svc.transition_status(doc.id, "reviewed")
    assert doc.status == "reviewed"


@pytest.mark.asyncio
async def test_invalid_status_transition(db, seed_teacher):
    from edu_cloud.models.user_role import UserRole
    from sqlalchemy import select

    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()

    svc = StudioService(db)
    doc = await svc.create_document(
        type="report",
        title="测试",
        content_json={},
        school_id=role.school_id,
        created_by=seed_teacher.id,
    )
    from edu_cloud.services.exceptions import StateError

    with pytest.raises(StateError):
        await svc.transition_status(doc.id, "approved")
