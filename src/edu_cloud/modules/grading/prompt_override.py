"""School-level prompt overrides via school_settings table.

Allows schools to customize prompts at runtime without code deploy.
Key format: "{subject}:{prompt_type}:{level}" under category "prompt".
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school_settings import SchoolSetting
from edu_cloud.modules.grading.prompts import get_prompt

logger = logging.getLogger(__name__)

CATEGORY = "prompt"


async def get_prompt_with_override(
    db: AsyncSession,
    subject: str,
    prompt_type: str,
    level: str = "senior",
    school_id: str | None = None,
) -> str | None:
    """Get prompt with optional school-level override.

    Resolution order:
    1. School override in school_settings (if school_id provided)
    2. Code default from prompts package
    """
    if school_id:
        key = f"{subject}:{prompt_type}:{level}"
        result = await db.execute(
            select(SchoolSetting.value).where(
                SchoolSetting.school_id == school_id,
                SchoolSetting.category == CATEGORY,
                SchoolSetting.key == key,
            )
        )
        override = result.scalar_one_or_none()
        if override:
            logger.info(
                "prompt_override: using school override for %s (school=%s)",
                key, school_id,
            )
            return override

    return get_prompt(subject, prompt_type, level)


async def set_prompt_override(
    db: AsyncSession,
    school_id: str,
    subject: str,
    prompt_type: str,
    value: str,
    level: str = "senior",
) -> None:
    """Set or update a school-level prompt override."""
    key = f"{subject}:{prompt_type}:{level}"
    result = await db.execute(
        select(SchoolSetting).where(
            SchoolSetting.school_id == school_id,
            SchoolSetting.category == CATEGORY,
            SchoolSetting.key == key,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = value
    else:
        db.add(SchoolSetting(
            school_id=school_id,
            category=CATEGORY,
            key=key,
            value=value,
        ))
    await db.flush()
    logger.info("prompt_override: saved override for %s (school=%s)", key, school_id)


async def delete_prompt_override(
    db: AsyncSession,
    school_id: str,
    subject: str,
    prompt_type: str,
    level: str = "senior",
) -> bool:
    """Delete a school-level prompt override. Returns True if found and deleted."""
    key = f"{subject}:{prompt_type}:{level}"
    result = await db.execute(
        select(SchoolSetting).where(
            SchoolSetting.school_id == school_id,
            SchoolSetting.category == CATEGORY,
            SchoolSetting.key == key,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()
        logger.info("prompt_override: deleted override for %s (school=%s)", key, school_id)
        return True
    return False


async def list_prompt_overrides(
    db: AsyncSession,
    school_id: str,
) -> list[dict]:
    """List all prompt overrides for a school."""
    result = await db.execute(
        select(SchoolSetting).where(
            SchoolSetting.school_id == school_id,
            SchoolSetting.category == CATEGORY,
        )
    )
    rows = result.scalars().all()
    overrides = []
    for row in rows:
        parts = row.key.split(":")
        overrides.append({
            "subject": parts[0] if len(parts) > 0 else "",
            "prompt_type": parts[1] if len(parts) > 1 else "",
            "level": parts[2] if len(parts) > 2 else "senior",
            "value_preview": row.value[:100] + "..." if row.value and len(row.value) > 100 else row.value,
        })
    return overrides
