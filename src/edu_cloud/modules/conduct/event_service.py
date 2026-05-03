"""积分事件处理：记录积分后自动通知家长。"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.guardian import GuardianStudentLink
from edu_cloud.modules.student.models import Student
from edu_cloud.modules.conduct.models import ConductRecord, ConductNotification

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

    # 5. Create notifications
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

    await db.commit()
    logger.info(
        "notify_parents: created %d notifications for record %s",
        count, record_id,
    )
    return count
