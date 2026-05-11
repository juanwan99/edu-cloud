import logging

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import Session as SyncSession

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

_tenant_logger = logging.getLogger("edu_cloud.tenant")


# ── Tenant audit listener ────────────────────────────────────────────────
# Attached to the *sync* Session class because AsyncSession proxies events
# through its internal sync session.  do_orm_execute fires for every ORM
# query execution, giving us a single interception point.

@event.listens_for(SyncSession, "do_orm_execute")
def _tenant_audit_listener(execute_state):
    """Audit-mode tenant filter: log queries on tenant-scoped tables that
    lack an explicit school_id predicate.

    This listener is intentionally lightweight:
      - skips non-SELECT statements
      - skips requests that opt-out via ``tenant_bypass`` execution option
      - skips when no tenant context is set (platform_admin / system jobs)
      - only does a string-contains check on the compiled SQL (no AST walk)
    """
    # Opt-out escape hatch
    if execute_state.execution_options.get("tenant_bypass"):
        return

    # Only audit SELECT queries
    if not execute_state.is_select:
        return

    from edu_cloud.core.tenant_registry import get_tenant, get_tenant_scoped_models, TENANT_MODE

    if TENANT_MODE != "audit":
        return  # future: enforce mode will inject WHERE here

    tenant_id = get_tenant()
    if tenant_id is None:
        return  # no tenant context (platform_admin, system job, unauthenticated)

    scoped_tables = get_tenant_scoped_models()
    if not scoped_tables:
        return

    # Compile the statement to SQL text for a cheap string check.
    # We use the dialect from the bind so the SQL is representative.
    try:
        statement = execute_state.statement
        compiled = statement.compile(
            dialect=execute_state.bind.dialect,
            compile_kwargs={"literal_binds": False},
        )
        sql_text = str(compiled)
    except Exception:
        # If compilation fails for any reason, skip auditing this query.
        return

    for table in scoped_tables:
        if table in sql_text and "school_id" not in sql_text:
            _tenant_logger.warning(
                "TENANT_AUDIT: query on tenant-scoped table '%s' "
                "without school_id filter | tenant=%s | sql=%.300s",
                table,
                tenant_id,
                sql_text,
            )
            # Only report the first offending table per query
            break


async def get_db():
    """FastAPI dependency: yields an async DB session."""
    async with async_session() as session:
        yield session
