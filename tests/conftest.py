import pytest
import bcrypt
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.models.base import Base
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
import edu_cloud.models.joint_exam  # noqa: F401 — ensures joint_exam tables are in metadata
import edu_cloud.models.student  # noqa: F401
import edu_cloud.models.class_group  # noqa: F401
import edu_cloud.models.exam  # noqa: F401
import edu_cloud.models.ai_session  # noqa: F401
import edu_cloud.models.document  # noqa: F401
import edu_cloud.models.approval  # noqa: F401
import edu_cloud.models.calendar  # noqa: F401
import edu_cloud.models.notification  # noqa: F401
import edu_cloud.core.models.llm_slot  # noqa: F401
import edu_cloud.modules.card.models  # noqa: F401
import edu_cloud.modules.scan.models  # noqa: F401
import edu_cloud.modules.grading.models  # noqa: F401
import edu_cloud.modules.marking.models  # noqa: F401
import edu_cloud.modules.knowledge.models  # noqa: F401
import edu_cloud.modules.bank.models  # noqa: F401
import edu_cloud.modules.profile.models  # noqa: F401
import edu_cloud.models.school_settings  # noqa: F401
import edu_cloud.models.teacher_assignment  # noqa: F401
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def db_engine():
    """In-memory SQLite engine (shared with db fixture)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db(db_engine):
    """In-memory SQLite session for tests."""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db, db_engine, tmp_path):
    """Test client with DB + Storage dependency overrides."""
    import tempfile
    import shutil
    from edu_cloud.api.app import create_app
    from edu_cloud.database import get_db
    from edu_cloud.shared.storage import get_storage, StorageService
    from edu_cloud.modules.scan.service import get_storage as get_scan_storage

    app = create_app()
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    storage_dir = tempfile.mkdtemp(prefix="edu_")

    def _override_storage():
        return StorageService(root=storage_dir)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = _override_storage
    app.dependency_overrides[get_scan_storage] = _override_storage

    # Monkey-patch async_session so middleware (which bypasses DI) uses test DB
    import edu_cloud.database as _db_mod
    _orig_session = _db_mod.async_session
    _db_mod.async_session = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    _db_mod.async_session = _orig_session
    shutil.rmtree(storage_dir, ignore_errors=True)


@pytest.fixture
async def admin_user(db):
    """Seed a platform_admin user (new User+UserRole model) and return it."""
    user = User(
        username="admin_test",
        display_name="Test Admin",
    )
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="platform_admin", is_primary=True))
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def admin_headers(admin_user):
    """JWT Authorization headers for platform_admin."""
    token = create_access_token({"sub": admin_user.id, "role": "platform_admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def observer_user(db):
    """Seed an observer user (new User+UserRole model) and return it."""
    user = User(
        username="observer_test",
        display_name="Test Observer",
    )
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="observer", is_primary=True))
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def observer_headers(observer_user):
    """JWT Authorization headers for observer."""
    token = create_access_token({"sub": observer_user.id, "role": "observer"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_school(db):
    """Seed a test school with known API key."""
    secret = "test_secret_123"
    hashed = bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()
    school = School(
        name="测试一校",
        code="SCHOOL01",
        api_key_hash=hashed,
        district="测试区",
    )
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school, secret


@pytest.fixture
def school_api_headers(seed_school):
    """X-API-Key headers for sync endpoints."""
    school, secret = seed_school
    return {"X-API-Key": f"{school.code}:{secret}"}


@pytest.fixture
async def seed_exam_with_results(db):
    """Create school+class+students+exam+results for AI tool tests"""
    from edu_cloud.models.school import School
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.models.student import Student
    from edu_cloud.models.exam import Exam, ExamResult
    import random

    school = School(name="AI测试校", code="AITEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls = ClassGroup(name="七年级2班", grade="七年级", grade_number=7, school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i in range(10):
        s = Student(name=f"学生{i}", student_number=f"T{i:03d}", school_id=school.id,
                    class_id=cls.id, grade="七年级")
        db.add(s)
        students.append(s)
    await db.flush()

    exam = Exam(name="期中数学", subject_code="SX", subject_name="数学",
                max_score=150, school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()

    random.seed(42)
    for s in students:
        score = round(random.gauss(105, 20), 1)
        score = max(0, min(150, score))
        db.add(ExamResult(exam_id=exam.id, student_id=s.id, school_id=school.id, total_score=score))
    await db.commit()

    return {"school_id": school.id, "class_id": cls.id, "exam_id": exam.id, "student_ids": [s.id for s in students]}


@pytest.fixture
async def seed_teacher(db):
    """Seed a homeroom_teacher user with school scope."""
    user = User(
        username="teacher1",
        display_name="张老师",
    )
    user.set_password("123456")
    db.add(user)
    await db.flush()
    school = School(
        name="测试校",
        code="TEST01",
        district="测试区",
        api_key_hash="placeholder",
    )
    db.add(school)
    await db.flush()
    role = UserRole(
        user_id=user.id,
        role="homeroom_teacher",
        school_id=school.id,
        class_ids=["class-7-2"],
        is_primary=True,
    )
    db.add(role)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def teacher_headers(client, seed_teacher):
    """JWT headers for teacher (via login endpoint)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "teacher1", "password": "123456"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_approver(db):
    """创建一个教务主任（审批人）"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    user = User(username="director1", display_name="王主任")
    user.set_password("123456")
    db.add(user)
    await db.flush()

    from edu_cloud.models.school import School
    from sqlalchemy import select

    school = (await db.execute(select(School))).scalars().first()
    if not school:
        school = School(
            name="审批测试校", code="APTEST", district="测试区", api_key_hash="x"
        )
        db.add(school)
        await db.flush()
    db.add(
        UserRole(
            user_id=user.id,
            role="academic_director",
            school_id=school.id,
            is_primary=True,
        )
    )
    await db.commit()
    return {"user_id": user.id, "school_id": school.id}


@pytest.fixture
async def seed_subject_teacher(db):
    """Seed a subject_teacher user with school scope."""
    user = User(
        username="subject_teacher1",
        display_name="李老师",
    )
    user.set_password("123456")
    db.add(user)
    await db.flush()

    from sqlalchemy import select
    school = (await db.execute(select(School))).scalars().first()
    if not school:
        school = School(
            name="论文测试校", code="PAPER01", district="测试区", api_key_hash="x"
        )
        db.add(school)
        await db.flush()

    db.add(UserRole(
        user_id=user.id,
        role="subject_teacher",
        school_id=school.id,
        is_primary=True,
    ))
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def subject_teacher_headers(client, seed_subject_teacher):
    """JWT headers for subject_teacher (via login endpoint)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "subject_teacher1", "password": "123456"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_grade_leader(db):
    """Seed a grade_leader user with school scope."""
    user = User(
        username="grade_leader1",
        display_name="赵组长",
    )
    user.set_password("123456")
    db.add(user)
    await db.flush()

    from sqlalchemy import select
    school = (await db.execute(select(School))).scalars().first()
    if not school:
        school = School(
            name="组长测试校", code="GRADE01", district="测试区", api_key_hash="x"
        )
        db.add(school)
        await db.flush()

    db.add(UserRole(
        user_id=user.id,
        role="grade_leader",
        school_id=school.id,
        is_primary=True,
    ))
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def grade_leader_headers(client, seed_grade_leader):
    """JWT headers for grade_leader (via login endpoint)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "grade_leader1", "password": "123456"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
