"""积分事件处理：记录积分后自动通知家长。"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.guardian import GuardianStudentLink
from edu_cloud.modules.student.models import Student
from edu_cloud.modules.conduct.models import (
    ConductRecord, ConductNotification, ConductClassConfig,
)

logger = logging.getLogger(__name__)


async def notify_parents_on_points(db: AsyncSession, record_id: str) -> int:
    """为积分记录创建家长通知，返回创建的通知数量。"""
    # 1. Fetch the ConductRecord
    record = await db.get(ConductRecord, record_id)
    if not record:
        logger.warning("notify_parents: record %s not found", record_id)
        return 0

    # 2. Fetch the Student
    student = await db.get(Student, record.student_id)
    if not student:
        logger.warning("notify_parents: student %s not found", record.student_id)
        return 0

    # 3. Query GuardianStudentLink for this student
    links = (
        await db.execute(
            select(GuardianStudentLink).where(
                GuardianStudentLink.student_id == record.student_id,
            )
        )
    ).scalars().all()

    if not links:
        return 0

    # 4. Build title with +/- prefix
    point_str = f"+{record.points}" if record.points >= 0 else str(record.points)
    title = f"{student.name} 德育积分变动 {point_str}"
    body = f"原因：{record.reason}（{record.date}）"

    # 5. Create notifications (no commit — caller owns the transaction)
    count = 0
    for link in links:
        notification = ConductNotification(
            parent_user_id=link.guardian_user_id,
            student_id=record.student_id,
            record_id=record_id,
            title=title,
            body=body,
        )
        db.add(notification)
        count += 1

    if count:
        logger.info(
            "notify_parents: queued %d notifications for record %s",
            count, record_id,
        )
    return count


async def check_alert_threshold(db: AsyncSession, student_id: str, class_id: str) -> int:
    """Check if student's cumulative points are below the class alert threshold.

    If so, create alert notifications for bound parents.
    Returns number of notifications created (0 if no alert needed).
    """
    # 1. Fetch ConductClassConfig
    config = (
        await db.execute(
            select(ConductClassConfig).where(ConductClassConfig.class_id == class_id)
        )
    ).scalar_one_or_none()
    if config is None or config.alert_threshold is None:
        return 0

    threshold = config.alert_threshold

    # 2. Calculate cumulative points
    cumulative = (
        await db.execute(
            select(func.coalesce(func.sum(ConductRecord.points), 0)).where(
                ConductRecord.student_id == student_id,
                ConductRecord.class_id == class_id,
            )
        )
    ).scalar()

    if cumulative >= threshold:
        return 0

    # 3. Fetch student name
    student = await db.get(Student, student_id)
    if not student:
        logger.warning("check_alert_threshold: student %s not found", student_id)
        return 0

    # 4. Query parent links
    links = (
        await db.execute(
            select(GuardianStudentLink).where(
                GuardianStudentLink.student_id == student_id,
            )
        )
    ).scalars().all()

    if not links:
        return 0

    # 5. Build alert content
    title = (
        f"[预警] {student.name} 积分低于预警线"
        f"（当前 {cumulative}，预警线 {threshold}）"
    )
    body = "请关注孩子在校行为表现，积分已低于班级设定的预警线。"

    # 6. Dedup: skip if any alert exists for this student+parent within 7 days
    # F-005: Check for ANY alert (read or unread) to prevent duplicate alerts
    # when parents mark notifications as read then trigger a new points change
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    count = 0
    for link in links:
        existing = (
            await db.execute(
                select(ConductNotification.id).where(
                    and_(
                        ConductNotification.parent_user_id == link.guardian_user_id,
                        ConductNotification.student_id == student_id,
                        ConductNotification.title.like("[预警]%"),
                        ConductNotification.created_at >= seven_days_ago,
                    )
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue

        notification = ConductNotification(
            parent_user_id=link.guardian_user_id,
            student_id=student_id,
            record_id=None,
            title=title,
            body=body,
        )
        db.add(notification)
        count += 1

    if count:
        logger.info(
            "check_alert_threshold: queued %d alert notifications for student %s "
            "(cumulative=%d, threshold=%d)",
            count, student_id, cumulative, threshold,
        )
    return count
