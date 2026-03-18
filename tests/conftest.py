import pytest
import bcrypt
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.models.base import Base
from edu_cloud.models.platform_user import PlatformUser
from edu_cloud.models.school import RegisteredSchool
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
    """Seed a platform_admin user and return it."""
    user = PlatformUser(
        username="admin_test",
        display_name="Test Admin",
        role="platform_admin",
    )
    user.set_password("test123")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def admin_headers(admin_user):
    """JWT Authorization headers for platform_admin."""
    token = create_access_token({"sub": admin_user.id, "role": admin_user.role})
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
