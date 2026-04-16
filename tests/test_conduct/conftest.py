import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.conduct.models import ConductClassConfig
from edu_cloud.shared.auth import create_access_token


async def _make_school_class_student(db):
    """Create school -> class -> student trio for conduct tests."""
    school = School(name="测试中学", code="CTEST2026", is_active=True)
    db.add(school)
    await db.flush()
    cls = Class(name="高一(1)班", grade="高一", grade_number=1, school_id=school.id)
    db.add(cls)
    await db.flush()
    student = Student(name="张三", student_number="2026001", class_id=cls.id, school_id=school.id)
    db.add(student)
    await db.commit()
    return school, cls, student


async def _make_user(db, username, role, school_id, class_ids=None):
    user = User(username=username, display_name=username)
    user.set_password("test123")
    db.add(user)
    await db.flush()
    ur = UserRole(user_id=user.id, role=role, school_id=school_id, is_primary=True, class_ids=class_ids)
    db.add(ur)
    await db.commit()
    return user


def _auth_headers(user, role="subject_teacher"):
    token = create_access_token({"sub": user.id, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def school_class_student(db):
    return await _make_school_class_student(db)


@pytest.fixture
async def homeroom_teacher(db, school_class_student):
    school, cls, _ = school_class_student
    return await _make_user(db, "teacher_hr", "homeroom_teacher", school.id, class_ids=[cls.id])


@pytest.fixture
async def homeroom_headers(homeroom_teacher):
    return _auth_headers(homeroom_teacher, "homeroom_teacher")


@pytest.fixture
async def conduct_config(db, school_class_student):
    _, cls, _ = school_class_student
    config = ConductClassConfig(class_id=cls.id, invite_code="TEST01", verify_code_type="custom")
    db.add(config)
    await db.commit()
    return config
