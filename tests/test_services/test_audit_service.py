import pytest
from edu_cloud.models.audit_log import AuditLog
from edu_cloud.logging_config import current_user_var, request_id_var


@pytest.mark.asyncio
async def test_audit_log_model(db, seed_school):
    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="audit_user", display_name="审计测试")
    user.set_password("test123")
    db.add(user)
    await db.flush()

    log = AuditLog(
        school_id=school.id,
        user_id=user.id,
        entity_type="school_setting",
        entity_id="fake-entity-id",
        action="create",
        before_data=None,
        after_data={"key": "test", "value": "hello"},
        request_id="req-12345",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    assert log.id is not None
    assert log.entity_type == "school_setting"
    assert log.after_data == {"key": "test", "value": "hello"}
    assert log.request_id == "req-12345"


@pytest.mark.asyncio
async def test_write_audit_log(db, seed_school):
    from edu_cloud.services.audit_service import write_audit_log

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="wal_user", display_name="写审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    await write_audit_log(
        db,
        school_id=school.id,
        user_id=user.id,
        entity_type="teacher_assignment",
        entity_id="ent-123",
        action="create",
        before_data=None,
        after_data={"user_id": "u1", "class_id": "c1"},
    )

    from sqlalchemy import select
    logs = (await db.execute(select(AuditLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "create"
    assert logs[0].after_data == {"user_id": "u1", "class_id": "c1"}


@pytest.mark.asyncio
async def test_list_audit_logs(db, seed_school):
    from edu_cloud.services.audit_service import write_audit_log, list_audit_logs

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="list_audit_user", display_name="列审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    await write_audit_log(
        db, school_id=school.id, user_id=user.id,
        entity_type="school_setting", entity_id="e1", action="create",
    )
    await write_audit_log(
        db, school_id=school.id, user_id=user.id,
        entity_type="teacher_assignment", entity_id="e2", action="delete",
    )

    logs = await list_audit_logs(db, school_id=school.id)
    assert len(logs) == 2

    logs = await list_audit_logs(db, school_id=school.id, entity_type="school_setting")
    assert len(logs) == 1
    assert logs[0].entity_type == "school_setting"

    logs = await list_audit_logs(db, school_id=school.id, action="delete")
    assert len(logs) == 1
    assert logs[0].action == "delete"

    logs = await list_audit_logs(db, school_id=school.id, user_id=user.id)
    assert len(logs) == 2


@pytest.mark.asyncio
async def test_list_audit_logs_pagination(db, seed_school):
    from edu_cloud.services.audit_service import write_audit_log, list_audit_logs

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="page_audit_user", display_name="分页审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    for i in range(5):
        await write_audit_log(
            db, school_id=school.id, user_id=user.id,
            entity_type="school_setting", entity_id=f"e{i}", action="create",
        )

    logs = await list_audit_logs(db, school_id=school.id, limit=2, offset=0)
    assert len(logs) == 2

    logs = await list_audit_logs(db, school_id=school.id, limit=2, offset=3)
    assert len(logs) == 2


@pytest.mark.asyncio
async def test_audited_decorator_create(db, seed_school):
    """@audited 装饰器: create 操作 → before=None, after=快照。"""
    from edu_cloud.services.audit_service import audited
    from sqlalchemy import select

    school, _ = seed_school

    from edu_cloud.models.user import User
    user = User(username="dec_create_user", display_name="装饰器创建")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    token_user = current_user_var.set(user.id)
    token_req = request_id_var.set("req-create-test")

    try:
        @audited("test_entity", action="create")
        async def fake_create(db, *, school_id, name):
            from edu_cloud.models.school_settings import SchoolSetting
            s = SchoolSetting(school_id=school_id, category="test", key=name, value="v1")
            db.add(s)
            await db.commit()
            await db.refresh(s)
            return s

        result = await fake_create(db, school_id=school.id, name="dec_test")
        assert result is not None

        logs = (await db.execute(select(AuditLog))).scalars().all()
        assert len(logs) == 1
        assert logs[0].action == "create"
        assert logs[0].before_data is None
        assert logs[0].after_data is not None
        assert logs[0].user_id == user.id
        assert logs[0].request_id == "req-create-test"
    finally:
        current_user_var.reset(token_user)
        request_id_var.reset(token_req)


@pytest.mark.asyncio
async def test_audited_decorator_delete(db, seed_school):
    """@audited 装饰器: delete 操作 → before=快照, after=None。"""
    from edu_cloud.services.audit_service import audited
    from edu_cloud.models.school_settings import SchoolSetting
    from sqlalchemy import select

    school, _ = seed_school

    from edu_cloud.models.user import User
    user = User(username="dec_delete_user", display_name="装饰器删除")
    user.set_password("test123")
    db.add(user)
    await db.flush()

    setting = SchoolSetting(school_id=school.id, category="test", key="del_key", value="v1")
    db.add(setting)
    await db.commit()
    await db.refresh(setting)

    token_user = current_user_var.set(user.id)
    token_req = request_id_var.set("req-delete-test")

    try:
        @audited("school_setting", action="delete", id_param="setting_id")
        async def fake_delete(db, *, school_id, setting_id):
            s = (await db.execute(
                select(SchoolSetting).where(SchoolSetting.id == setting_id)
            )).scalar_one()
            await db.delete(s)
            await db.commit()
            return None

        await fake_delete(db, school_id=school.id, setting_id=setting.id)

        logs = (await db.execute(select(AuditLog))).scalars().all()
        assert len(logs) == 1
        assert logs[0].action == "delete"
        assert logs[0].before_data is not None
        assert logs[0].after_data is None
        assert logs[0].entity_id == setting.id
    finally:
        current_user_var.reset(token_user)
        request_id_var.reset(token_req)


@pytest.mark.asyncio
async def test_audited_decorator_no_user_context(db, seed_school):
    """F-02: ContextVar 未设置时 user_id 为 None 但不崩溃。"""
    from edu_cloud.services.audit_service import audited
    from sqlalchemy import select

    school, _ = seed_school

    @audited("test_entity", action="create")
    async def fake_create_no_user(db, *, school_id):
        from edu_cloud.models.school_settings import SchoolSetting
        s = SchoolSetting(school_id=school_id, category="test", key="nouser", value="v1")
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return s

    result = await fake_create_no_user(db, school_id=school.id)
    assert result is not None

    logs = (await db.execute(select(AuditLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].user_id is None  # F-02: None, not "-"


# ── Integration tests: @audited on real services ──

from edu_cloud.services import school_settings_service
from edu_cloud.services import teacher_assignment_service
from edu_cloud.services import subject_selection_service


@pytest.mark.asyncio
async def test_audited_upsert_setting(db, seed_school):
    """F-04: upsert_setting create → action=create, update → action=update."""
    from sqlalchemy import select

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="audit_settings_user", display_name="Settings审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    token_user = current_user_var.set(user.id)
    try:
        # First call = create
        result = await school_settings_service.upsert_setting(
            db, school_id=school.id, category="test", key="audit_key", value="val1",
        )
        assert result.key == "audit_key"

        logs = (await db.execute(select(AuditLog))).scalars().all()
        setting_logs = [log for log in logs if log.entity_type == "school_setting"]
        assert len(setting_logs) >= 1
        assert setting_logs[0].action == "create"

        # Second call = update (F-04 fix)
        await school_settings_service.upsert_setting(
            db, school_id=school.id, category="test", key="audit_key", value="val2",
        )
        logs = (await db.execute(select(AuditLog))).scalars().all()
        setting_logs = [log for log in logs if log.entity_type == "school_setting"]
        assert len(setting_logs) >= 2
        update_logs = [log for log in setting_logs if log.action == "update"]
        assert len(update_logs) >= 1
    finally:
        current_user_var.reset(token_user)


@pytest.mark.asyncio
async def test_audited_create_assignments(db, seed_school):
    """create_assignments 加 @audited 后产生审计日志。"""
    from sqlalchemy import select
    from edu_cloud.models.user import User
    from edu_cloud.modules.student.models import Class

    school, _ = seed_school
    user = User(username="audit_assign_user", display_name="Assignment审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls = Class(name="审计测试班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls)
    await db.commit()

    token_user = current_user_var.set(user.id)
    try:
        count = await teacher_assignment_service.create_assignments(
            db, school_id=school.id, user_id=user.id,
            class_ids=[cls.id], subject_code="math", semester="2025-2026-2",
        )
        assert count == 1

        logs = (await db.execute(select(AuditLog))).scalars().all()
        assign_logs = [log for log in logs if log.entity_type == "teacher_assignment"]
        assert len(assign_logs) >= 1
        assert assign_logs[0].action == "create"
    finally:
        current_user_var.reset(token_user)


@pytest.mark.asyncio
async def test_audited_create_selection(db, seed_school):
    """create_selection 加 @audited 后产生审计日志。"""
    from sqlalchemy import select

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="audit_sel_user", display_name="Selection审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    token_user = current_user_var.set(user.id)
    try:
        sel = await subject_selection_service.create_selection(
            db, school_id=school.id, name="审计理化生",
            subject_codes=["physics", "chemistry", "biology"], mode="custom",
        )
        assert sel.name == "审计理化生"

        logs = (await db.execute(select(AuditLog))).scalars().all()
        sel_logs = [log for log in logs if log.entity_type == "subject_selection"]
        assert len(sel_logs) >= 1
        assert sel_logs[0].action == "create"
    finally:
        current_user_var.reset(token_user)


@pytest.mark.asyncio
async def test_existing_settings_tests_still_pass(db, seed_school):
    """确认 @audited 不影响原有 service 返回值。"""
    school, _ = seed_school
    result = await school_settings_service.upsert_setting(
        db, school_id=school.id, category="test", key="compat_key", value="compat_val",
    )
    assert result.key == "compat_key"
    assert result.value == "compat_val"
