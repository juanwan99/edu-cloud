import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Model imports — required so that Base.metadata knows about all tables.
# Every model that inherits from Base must be imported here so that
# autogenerate can discover it.  38 models across 6 source locations.
# ---------------------------------------------------------------------------
from edu_cloud.models.base import Base  # noqa: F401

# ── core models (src/edu_cloud/models/) ──────────────────────────────────
from edu_cloud.models.school import School  # noqa: F401
from edu_cloud.models.user import User  # noqa: F401
from edu_cloud.models.user_role import UserRole  # noqa: F401
from edu_cloud.models.document import Document, DocumentVersion  # noqa: F401
from edu_cloud.models.approval import ApprovalFlow, ApprovalStep  # noqa: F401
from edu_cloud.models.calendar import CalendarEvent, NotificationRule  # noqa: F401
from edu_cloud.models.notification import Notification  # noqa: F401

# ── core/models (src/edu_cloud/core/models/) ─────────────────────────────
from edu_cloud.core.models.llm_slot import LLMSlot  # noqa: F401

# ── AI models (src/edu_cloud/ai/) ────────────────────────────────────────
from edu_cloud.ai.models import AiSession, AiToolCall  # noqa: F401

# ── module models (src/edu_cloud/modules/*/models.py) ────────────────────
from edu_cloud.modules.exam.models import (  # noqa: F401
    Exam, Subject, Question, ExamResult,
    JointExam, JointExamParticipant, JointExamStudentResult,
)
from edu_cloud.modules.student.models import Class, Student  # noqa: F401
from edu_cloud.modules.card.models import Template, CardSkeleton  # noqa: F401
from edu_cloud.modules.scan.models import ScanTask, StudentAnswer  # noqa: F401
from edu_cloud.modules.grading.models import (  # noqa: F401
    Rubric, GradingTask, AIGradingResult, TeacherReview,
)
from edu_cloud.modules.marking.models import MarkingAssignment, MarkingScore  # noqa: F401
from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook  # noqa: F401
from edu_cloud.modules.profile.models import (  # noqa: F401
    StudentExamSnapshot, StudentKnowledgeMastery, StudentErrorPattern,
)
from edu_cloud.modules.knowledge.models import KnowledgePoint, QuestionKnowledgePoint  # noqa: F401
from edu_cloud.models.school_settings import SchoolSetting, SchoolModule  # noqa: F401
from edu_cloud.models.teacher_assignment import TeacherAssignment  # noqa: F401
from edu_cloud.models.subject_selection import SubjectSelection  # noqa: F401
from edu_cloud.models.capability import Capability  # noqa: F401
from edu_cloud.models.audit_log import AuditLog  # noqa: F401

# ---------------------------------------------------------------------------
# Alembic Config object, which provides access to the values within the .ini
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the application's Base.metadata for autogenerate support
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Override sqlalchemy.url from application settings when available
# ---------------------------------------------------------------------------
try:
    from edu_cloud.config import settings

    # Alembic needs a *sync* driver for offline/autogenerate.
    # Replace asyncpg with psycopg2 (or plain postgresql://) for sync usage.
    db_url = settings.DATABASE_URL
    if "asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")
    elif "aiosqlite" in db_url:
        db_url = db_url.replace("sqlite+aiosqlite", "sqlite")

    config.set_main_option("sqlalchemy.url", db_url)
except Exception:
    pass  # fall back to alembic.ini value


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though
    an Engine is acceptable here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async Engine and associate a connection with the context."""
    # For online mode, use the async driver directly
    try:
        from edu_cloud.config import settings

        async_url = settings.DATABASE_URL
        if "aiosqlite" in async_url:
            # SQLite async — swap driver for aiosqlite
            pass
        elif "postgresql" in async_url and "asyncpg" not in async_url:
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
    except Exception:
        async_url = config.get_main_option("sqlalchemy.url")
        if "postgresql://" in async_url and "asyncpg" not in async_url:
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

    from sqlalchemy.ext.asyncio import create_async_engine

    connectable = create_async_engine(async_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
