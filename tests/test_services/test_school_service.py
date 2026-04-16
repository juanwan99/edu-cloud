import pytest
import bcrypt
from edu_cloud.services.school_service import SchoolService
from edu_cloud.services.exceptions import NotFoundError, ConflictError


@pytest.mark.asyncio
async def test_create_school_returns_plaintext_key(db):
    svc = SchoolService(db)
    school, plaintext_key = await svc.create_school(
        name="测试学校", code="TEST01", district="海淀区"
    )
    assert school.code == "TEST01"
    assert school.name == "测试学校"
    assert ":" in plaintext_key  # format: CODE:secret
    # Verify bcrypt hash matches
    _, secret = plaintext_key.split(":", 1)
    assert bcrypt.checkpw(secret.encode(), school.api_key_hash.encode())


@pytest.mark.asyncio
async def test_create_school_duplicate_code_raises(db):
    svc = SchoolService(db)
    await svc.create_school(name="A校", code="DUP01", district="X区")
    with pytest.raises(ConflictError):
        await svc.create_school(name="B校", code="DUP01", district="Y区")


@pytest.mark.asyncio
async def test_list_schools_filter_district(db):
    svc = SchoolService(db)
    await svc.create_school(name="A校", code="A01", district="海淀区")
    await svc.create_school(name="B校", code="B01", district="朝阳区")
    schools = await svc.list_schools(district="海淀区")
    assert len(schools) == 1
    assert schools[0].code == "A01"


@pytest.mark.asyncio
async def test_list_schools_filter_active(db):
    svc = SchoolService(db)
    s1, _ = await svc.create_school(name="A校", code="A01", district="X区")
    await svc.create_school(name="B校", code="B01", district="X区")
    await svc.update_school(s1.id, is_active=False)
    active = await svc.list_schools(is_active=True)
    assert all(s.is_active for s in active)


@pytest.mark.asyncio
async def test_get_school_not_found(db):
    svc = SchoolService(db)
    with pytest.raises(NotFoundError):
        await svc.get_school("nonexistent-id")


@pytest.mark.asyncio
async def test_update_school_deactivate(db):
    svc = SchoolService(db)
    school, _ = await svc.create_school(name="X校", code="X01", district="X区")
    updated = await svc.update_school(school.id, is_active=False)
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_rotate_key_invalidates_old(db):
    svc = SchoolService(db)
    school, old_key = await svc.create_school(name="R校", code="R01", district="X区")
    _, old_secret = old_key.split(":", 1)

    new_key = await svc.rotate_api_key(school.id)
    _, new_secret = new_key.split(":", 1)

    # Refresh to get updated hash
    await db.refresh(school)
    # Old key no longer works
    assert not bcrypt.checkpw(old_secret.encode(), school.api_key_hash.encode())
    # New key works
    assert bcrypt.checkpw(new_secret.encode(), school.api_key_hash.encode())
