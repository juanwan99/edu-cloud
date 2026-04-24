from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    **({} if _is_sqlite else {
        "pool_size": 20,
        "max_overflow": 40,
        "pool_timeout": 30,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }),
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI dependency: yields an async DB session."""
    async with async_session() as session:
        yield session
