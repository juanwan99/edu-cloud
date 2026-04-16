import functools
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.audit_log import AuditLog
from edu_cloud.logging_config import current_user_var, request_id_var

logger = logging.getLogger(__name__)


def _snapshot(obj) -> dict | None:
    """Extract a JSON-serializable snapshot from an ORM object."""
    if obj is None:
        return None
    if not hasattr(obj, "__table__"):
        return None  # non-ORM return (e.g. int from batch create)
    data = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name, None)
        if isinstance(val, datetime):
            val = val.isoformat()
        data[col.name] = val
    return data


async def write_audit_log(
    db: AsyncSession, *,
    school_id: str | None = None,
    user_id: str | None = None,
    entity_type: str,
    entity_id: str,
    action: str,
    before_data: dict | None = None,
    after_data: dict | None = None,
    request_id: str | None = None,
) -> AuditLog:
    log = AuditLog(
        school_id=school_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_data=before_data,
        after_data=after_data,
        request_id=request_id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_audit_logs(
    db: AsyncSession, *,
    school_id: str,
    entity_type: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.school_id == school_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if start_date:
        stmt = stmt.where(AuditLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(AuditLog.created_at <= end_date)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def audited(entity_type: str, *, action: str = "create", id_param: str = "entity_id"):
    """Service 层装饰器：自动记录 before/after 快照。

    被装饰函数需要:
    - 第一个位置参数是 db (AsyncSession)
    - keyword 参数中有 school_id
    - create: 返回 ORM 对象 → before=None, after=snapshot
    - delete: 可选 id_param kwarg → before=snapshot (先查), after=None
    - update: 可选 id_param kwarg → before=snapshot (先查), after=snapshot

    user_id 从 current_user_var ContextVar 获取 (F-02: None if not set)。
    request_id 从 request_id_var ContextVar 获取。
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            db = args[0] if args else kwargs.get("db")
            school_id = kwargs.get("school_id")
            user_id = current_user_var.get()  # F-02: None if not set
            req_id = request_id_var.get()

            before_snapshot = None
            entity_id_val = kwargs.get(id_param)

            # For update/delete: snapshot before (F-05: use select, not db.get)
            if action in ("update", "delete") and entity_id_val and db:
                model_cls, lookup_col = _entity_type_lookup(entity_type)
                if model_cls and lookup_col:
                    stmt = select(model_cls).where(
                        getattr(model_cls, lookup_col) == entity_id_val
                    )
                    if school_id and hasattr(model_cls, "school_id"):
                        stmt = stmt.where(model_cls.school_id == school_id)
                    old = (await db.execute(stmt)).scalar_one_or_none()
                    before_snapshot = _snapshot(old)

            result = await func(*args, **kwargs)

            after_snapshot = _snapshot(result) if result is not None else None

            if result is not None and hasattr(result, "id"):
                eid = result.id
            elif entity_id_val:
                eid = entity_id_val
            else:
                eid = "-"

            try:
                await write_audit_log(
                    db,
                    school_id=school_id,
                    user_id=user_id,
                    entity_type=entity_type,
                    entity_id=eid,
                    action=action,
                    before_data=before_snapshot,
                    after_data=after_snapshot,
                    request_id=req_id,
                )
            except Exception:
                logger.warning("Failed to write audit log", exc_info=True)

            return result
        return wrapper
    return decorator


def _entity_type_lookup(entity_type: str) -> tuple:
    """Map entity_type to (model_class, lookup_column).
    F-05 fix: returns the correct lookup column for each entity type,
    not assuming id_param is always the primary key."""
    mapping = {
        "school_setting": ("edu_cloud.models.school_settings:SchoolSetting", "id"),
        "school_module": ("edu_cloud.models.school_settings:SchoolModule", "module_code"),
        "teacher_assignment": ("edu_cloud.models.teacher_assignment:TeacherAssignment", "id"),
        "subject_selection": ("edu_cloud.models.subject_selection:SubjectSelection", "id"),
        "homework_task": ("edu_cloud.modules.homework.models:HomeworkTask", "id"),
        "homework_submission": ("edu_cloud.modules.homework.models:HomeworkSubmission", "id"),
    }
    entry = mapping.get(entity_type)
    if not entry:
        return None, None
    path, col = entry
    module_path, class_name = path.split(":")
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name, None), col
