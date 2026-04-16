import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole


async def test_create_school(db):
    school = School(name="Test School", code="TS001")
    db.add(school)
    await db.commit()
    await db.refresh(school)
    assert school.id is not None
    assert school.name == "Test School"


async def test_create_user(db):
    school = School(name="Test School", code="TS002")
    db.add(school)
    await db.commit()

    user = User(username="teacher1", display_name="Zhang San")
    user.set_password("test123")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()
    await db.refresh(user)
    assert user.id is not None
    assert user.verify_password("test123")
    assert not user.verify_password("wrong")
