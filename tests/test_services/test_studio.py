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


# ── F1 fix: DocumentVersion 持久化断言 + 连续编辑 ──────────────────


@pytest.mark.asyncio
async def test_update_document_persists_version_history(db, seed_teacher):
    """F1: 编辑文档时旧版本必须持久化到 document_versions 表"""
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.document import DocumentVersion
    from sqlalchemy import select

    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()

    svc = StudioService(db)
    doc = await svc.create_document(
        type="report", title="版本测试",
        content_json={"body": "original"},
        school_id=role.school_id, created_by=seed_teacher.id,
    )

    # 编辑 3 次
    for i in range(1, 4):
        await svc.update_document(
            doc.id, content_json={"body": f"v{i + 1}"},
            edited_by=seed_teacher.id, change_summary=f"edit {i}",
        )

    # 文档本体应为 v4
    assert doc.version == 4

    # document_versions 应有 3 条历史记录
    versions = (await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version)
    )).scalars().all()
    assert len(versions) == 3
    assert [v.version for v in versions] == [1, 2, 3]
    # 历史记录保存的是旧值，不是新值
    assert versions[0].content_json == {"body": "original"}
    assert versions[1].content_json == {"body": "v2"}
    assert versions[2].content_json == {"body": "v3"}


# ── F2 fix: 异常路径测试 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_nonexistent_document(db):
    """F2: 不存在的 doc_id → NotFoundError"""
    from edu_cloud.services.exceptions import NotFoundError

    svc = StudioService(db)
    with pytest.raises(NotFoundError):
        await svc.get_document("nonexistent-id")


@pytest.mark.asyncio
async def test_draft_cannot_transition_to_executed(db, seed_teacher):
    """F2: draft → executed 跳转不合法"""
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.services.exceptions import StateError
    from sqlalchemy import select

    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()

    svc = StudioService(db)
    doc = await svc.create_document(
        type="report", title="测试", content_json={},
        school_id=role.school_id, created_by=seed_teacher.id,
    )
    with pytest.raises(StateError):
        await svc.transition_status(doc.id, "executed")


@pytest.mark.asyncio
async def test_executed_document_cannot_transition(db, seed_teacher):
    """F2: executed 终态文档不能再转换"""
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.services.exceptions import StateError
    from sqlalchemy import select

    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()

    svc = StudioService(db)
    doc = await svc.create_document(
        type="report", title="测试", content_json={},
        school_id=role.school_id, created_by=seed_teacher.id,
    )
    # draft → reviewed → executed
    await svc.transition_status(doc.id, "reviewed")
    await svc.transition_status(doc.id, "executed")

    with pytest.raises(StateError):
        await svc.transition_status(doc.id, "draft")


# ── TG-002: assigned_to 可见性 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_documents_shows_assigned_to(db):
    """TG-002: assigned_to 教师能看到被指派的文档"""
    svc = StudioService(db)
    doc = await svc.create_document(
        type="notification", title="测试", content_json={},
        school_id="s1", created_by="creator1",
    )
    doc.assigned_to = "assignee1"
    await db.flush()
    await db.commit()

    # assignee 能看到文档
    docs = await svc.list_documents(school_id="s1", created_by="assignee1")
    assert len(docs) == 1
    assert docs[0].id == doc.id

    # 无关用户看不到
    docs2 = await svc.list_documents(school_id="s1", created_by="other_user")
    assert len(docs2) == 0
