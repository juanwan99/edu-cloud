"""Conduct 导出服务 — Excel 积分记录/排行榜"""
import io
import logging
from datetime import date

from openpyxl import Workbook
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.conduct.models import ConductRecord
from edu_cloud.services.conduct_workflow import Student
from edu_cloud.models.user import User

logger = logging.getLogger(__name__)


async def export_records_excel(db: AsyncSession, class_id: str,
                               start_date: date | None = None,
                               end_date: date | None = None) -> io.BytesIO:
    """导出积分记录 Excel"""
    stmt = (
        select(ConductRecord, Student, User)
        .join(Student, ConductRecord.student_id == Student.id)
        .join(User, ConductRecord.operator_id == User.id)
        .where(ConductRecord.class_id == class_id)
        .order_by(ConductRecord.date.desc())
    )
    if start_date:
        stmt = stmt.where(ConductRecord.date >= start_date)
    if end_date:
        stmt = stmt.where(ConductRecord.date <= end_date)

    result = await db.execute(stmt)
    rows = result.all()

    wb = Workbook()
    ws = wb.active
    ws.title = "积分记录"
    ws.append(["日期", "学生姓名", "积分", "原因", "操作人", "来源"])
    for record, student, operator in rows:
        ws.append([
            str(record.date),
            student.name,
            record.points,
            record.reason,
            operator.display_name,
            record.source,
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


async def export_rankings_excel(db: AsyncSession, class_id: str,
                                semester_id: str | None = None) -> io.BytesIO:
    """导出排行榜 Excel"""
    stmt = (
        select(Student, func.coalesce(func.sum(ConductRecord.points), 0).label("total"))
        .outerjoin(ConductRecord, ConductRecord.student_id == Student.id)
        .where(Student.class_id == class_id)
        .group_by(Student.id)
        .order_by(func.coalesce(func.sum(ConductRecord.points), 0).desc())
    )
    if semester_id:
        stmt = stmt.where(ConductRecord.semester_id == semester_id)

    result = await db.execute(stmt)
    rows = result.all()

    wb = Workbook()
    ws = wb.active
    ws.title = "积分排行"
    ws.append(["排名", "学生姓名", "学号", "总积分"])
    for i, (student, total) in enumerate(rows, 1):
        ws.append([i, student.name, student.student_number, int(total)])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
