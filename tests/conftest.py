import pytest
import bcrypt
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.models.base import Base
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import RegisteredSchool
import edu_cloud.models.platform_user  # noqa: F401 — ensures platform_users table is in metadata
import edu_cloud.models.joint_exam  # noqa: F401 — ensures joint_exam tables are in metadata
import edu_cloud.models.student  # noqa: F401
import edu_cloud.models.class_group  # noqa: F401
import edu_cloud.models.exam  # noqa: F401
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def db():
    """In-memory SQLite session for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db):
    """Test client with DB dependency override."""
    from edu_cloud.api.app import create_app
    from edu_cloud.database import get_db

    app = create_app()

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


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
    school = RegisteredSchool(
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
async def seed_teacher(db):
    """Seed a homeroom_teacher user with school scope."""
    user = User(
        username="teacher1",
        display_name="张老师",
    )
    user.set_password("123456")
    db.add(user)
    await db.flush()
    school = RegisteredSchool(
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
