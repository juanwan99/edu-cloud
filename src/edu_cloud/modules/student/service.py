"""Class / Student 业务逻辑（从 exam-ai 迁入）。"""
import io
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.student.models import Class, Student
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)


async def list_classes(
    db: AsyncSession,
    *,
    school_id: str,
    visible_class_ids: list[str] | None = None,
) -> list[Class]:
    query = select(Class).where(Class.school_id == school_id)
    if visible_class_ids is not None:
        query = query.where(Class.id.in_(visible_class_ids))
    result = await db.execute(query)
    classes = list(result.scalars().all())
    logger.debug("list_classes: school=%s, count=%d", school_id, len(classes))
    return classes


async def list_students(
    db: AsyncSession,
    *,
    school_id: str,
    class_id: str | None = None,
    visible_class_ids: list[str] | None = None,
) -> list[Student]:
    query = select(Student).where(Student.school_id == school_id)
    if visible_class_ids is not None:
        if class_id and class_id not in visible_class_ids:
            return []
        query = query.where(Student.class_id.in_(visible_class_ids))
    if class_id:
        query = query.where(Student.class_id == class_id)
    result = await db.execute(query)
    students = list(result.scalars().all())
    logger.debug("list_students: school=%s, class_id=%s, count=%d", school_id, class_id, len(students))
    return students


async def search_students(
    db: AsyncSession, *, school_id: str, query: str, visible_class_ids: list[str] | None = None,
) -> list[Student]:
    stmt = select(Student).where(Student.school_id == school_id, Student.name.contains(query))
    if visible_class_ids is not None:
        stmt = stmt.where(Student.class_id.in_(visible_class_ids))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_student(
    db: AsyncSession, *, student_id: str, school_id: str,
) -> Student | None:
    result = await db.execute(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )
    return result.scalar_one_or_none()


async def import_students(
    db: AsyncSession,
    *,
    school_id: str,
    class_id: str,
    file_content: bytes,
    filename: str,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """从 Excel 导入学生。返回 {"created": int, "skipped": int}。"""
    import openpyxl  # lazy import — openpyxl 可能未安装

    if not class_id:
        raise ValidationError("class_id 为必填参数")

    cls_result = await db.execute(
        select(Class).where(Class.id == class_id, Class.school_id == school_id)
    )
    if not cls_result.scalar_one_or_none():
        raise NotFoundError("班级不存在或无权访问")

    if visible_class_ids is not None and class_id not in visible_class_ids:
        raise PermissionDeniedError("无权向该班级导入学生")

    if not filename or not filename.endswith((".xlsx", ".xls")):
        raise ValidationError("仅支持 .xlsx/.xls 文件")

    wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise ValidationError("Excel 为空或仅含表头")

    header = [str(h).strip() if h else "" for h in rows[0]]
    name_col = next((i for i, h in enumerate(header) if "姓名" in h), None)
    number_col = next((i for i, h in enumerate(header) if "准考证" in h or "学号" in h), None)

    if name_col is None or number_col is None:
        raise ValidationError("Excel 需包含「姓名」和「准考证号/学号」列")

    created = 0
    skipped = 0
    for row in rows[1:]:
        name = str(row[name_col]).strip() if row[name_col] else ""
        number = str(row[number_col]).strip() if row[number_col] else ""
        if not name or not number:
            skipped += 1
            continue

        existing = await db.execute(
            select(Student).where(
                Student.school_id == school_id,
                Student.student_number == number,
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        student = Student(
            name=name, student_number=number,
            class_id=class_id, school_id=school_id,
        )
        db.add(student)
        created += 1

    await db.commit()
    logger.info("import_students: school=%s, created=%d, skipped=%d", school_id, created, skipped)
    return {"created": created, "skipped": skipped}
