"""Class / Student 业务逻辑（从 exam-ai 迁入）。"""
import io
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.student.models import Class, Student
from edu_cloud.models.subject_selection import SubjectSelection
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)


async def list_classes(
    db: AsyncSession,
    *,
    school_id: str,
    grade: str | None = None,
    visible_class_ids: list[str] | None = None,
) -> list[Class]:
    query = select(Class).where(Class.school_id == school_id)
    if visible_class_ids is not None:
        query = query.where(Class.id.in_(visible_class_ids))
    if grade:
        query = query.where(Class.grade == grade)
    result = await db.execute(query)
    classes = list(result.scalars().all())
    logger.debug("list_classes: school=%s, grade=%s, count=%d", school_id, grade, len(classes))
    return classes


async def list_students(
    db: AsyncSession,
    *,
    school_id: str,
    class_id: str | None = None,
    selection_id: str | None = None,
    subject_code: str | None = None,
    visible_class_ids: list[str] | None = None,
) -> list[Student]:
    query = select(Student).where(Student.school_id == school_id)
    if visible_class_ids is not None:
        if class_id and class_id not in visible_class_ids:
            return []
        query = query.where(Student.class_id.in_(visible_class_ids))
    if class_id:
        query = query.where(Student.class_id == class_id)
    if selection_id:
        query = query.where(Student.selection_id == selection_id)
    if subject_code:
        sel_result = await db.execute(
            select(SubjectSelection.id).where(SubjectSelection.school_id == school_id)
        )
        matching_ids = [
            s.id for s in sel_result.all()
        ]
        if matching_ids:
            sels = await db.execute(
                select(SubjectSelection).where(SubjectSelection.id.in_(matching_ids))
            )
            valid_ids = [s.id for s in sels.scalars().all() if subject_code in (s.subject_codes or [])]
            query = query.where(Student.selection_id.in_(valid_ids)) if valid_ids else query.where(False)
        else:
            query = query.where(False)
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


async def create_student(
    db: AsyncSession,
    *,
    school_id: str,
    name: str,
    student_number: str,
    class_id: str | None = None,
    grade: str | None = None,
    gender: str | None = None,
    id_card: str | None = None,
    selection_id: str | None = None,
) -> Student:
    existing = await db.execute(
        select(Student).where(
            Student.school_id == school_id,
            Student.student_number == student_number,
        )
    )
    if existing.scalar_one_or_none():
        raise ValidationError(f"学号 {student_number} 已存在")
    if class_id:
        cls = await db.execute(
            select(Class).where(Class.id == class_id, Class.school_id == school_id)
        )
        if not cls.scalar_one_or_none():
            raise NotFoundError("班级不存在")
    student = Student(
        name=name, student_number=student_number,
        class_id=class_id, school_id=school_id,
        grade=grade, gender=gender, id_card=id_card,
        selection_id=selection_id,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


async def update_student(
    db: AsyncSession,
    *,
    student_id: str,
    school_id: str,
    name: str | None = None,
    student_number: str | None = None,
    class_id: str | None = None,
    grade: str | None = None,
    gender: str | None = None,
    id_card: str | None = None,
    selection_id: str | None = None,
) -> Student:
    student = await get_student(db, student_id=student_id, school_id=school_id)
    if not student:
        raise NotFoundError("学生不存在")
    if student_number and student_number != student.student_number:
        dup = await db.execute(
            select(Student).where(
                Student.school_id == school_id,
                Student.student_number == student_number,
            )
        )
        if dup.scalar_one_or_none():
            raise ValidationError(f"学号 {student_number} 已存在")
        student.student_number = student_number
    if name is not None:
        student.name = name
    if class_id is not None:
        student.class_id = class_id if class_id else None
    if grade is not None:
        student.grade = grade
    if gender is not None:
        student.gender = gender
    if id_card is not None:
        student.id_card = id_card
    if selection_id is not None:
        student.selection_id = selection_id if selection_id else None
    await db.commit()
    await db.refresh(student)
    return student


async def delete_student(
    db: AsyncSession, *, student_id: str, school_id: str,
) -> bool:
    student = await get_student(db, student_id=student_id, school_id=school_id)
    if not student:
        raise NotFoundError("学生不存在")
    await db.delete(student)
    await db.commit()
    return True


_SUBJECT_ABBREV = {
    "物理": "物", "化学": "化", "生物": "生",
    "历史": "史", "政治": "政", "地理": "地",
    "语文": "语", "数学": "数", "英语": "英",
}


def _build_abbreviation(name: str) -> str:
    """'物理化学生物' → '物化生'"""
    abbrev = name
    for full, short in _SUBJECT_ABBREV.items():
        abbrev = abbrev.replace(full, short)
    return abbrev if abbrev != name else ""


async def import_students(
    db: AsyncSession,
    *,
    school_id: str,
    class_id: str = "",
    grade: str = "",
    file_content: bytes,
    filename: str,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """从 Excel 导入学生。

    class_id 为空时，Excel 必须包含「班级」列，按班级名自动匹配。
    返回 {"created": int, "skipped": int, "class_not_found": int}。
    """
    import openpyxl

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

    class_col = next((i for i, h in enumerate(header) if "班级" in h or "班" in h), None)
    gender_col = next((i for i, h in enumerate(header) if "性别" in h), None)
    id_card_col = next((i for i, h in enumerate(header) if "身份证" in h or "证件" in h), None)
    sel_col = next((i for i, h in enumerate(header) if "选课" in h or "组合" in h or "选科" in h), None)

    # class_id 和班级列都没有时，学生 class_id 为空，后续再分班

    # 固定班级模式：校验
    fixed_class_id = None
    if class_id:
        cls_result = await db.execute(
            select(Class).where(Class.id == class_id, Class.school_id == school_id)
        )
        if not cls_result.scalar_one_or_none():
            raise NotFoundError("班级不存在或无权访问")
        if visible_class_ids is not None and class_id not in visible_class_ids:
            raise PermissionDeniedError("无权向该班级导入学生")
        fixed_class_id = class_id

    # 班级名→(id, grade) 映射（按年级限定）
    class_map = {}
    class_grade_map = {}
    if class_col is not None or not fixed_class_id:
        cls_query = select(Class).where(Class.school_id == school_id)
        if grade:
            cls_query = cls_query.where(Class.grade == grade)
        cls_result = await db.execute(cls_query)
        for c in cls_result.scalars().all():
            class_map[c.name] = c.id
            class_grade_map[c.id] = c.grade
    if fixed_class_id and fixed_class_id not in class_grade_map:
        fc = await db.execute(select(Class).where(Class.id == fixed_class_id))
        fc_obj = fc.scalar_one_or_none()
        if fc_obj:
            class_grade_map[fc_obj.id] = fc_obj.grade

    # 选课组合名→id 映射（精确 + 简称模糊）
    sel_map = {}
    if sel_col is not None:
        sel_result = await db.execute(
            select(SubjectSelection).where(
                SubjectSelection.school_id == school_id, SubjectSelection.is_active.is_(True)
            )
        )
        for s in sel_result.scalars().all():
            sel_map[s.name] = s.id
            codes_str = "/".join(s.subject_codes or [])
            if codes_str:
                sel_map[codes_str] = s.id
            abbrev = _build_abbreviation(s.name)
            if abbrev:
                sel_map.setdefault(abbrev, s.id)

    created = 0
    updated = 0
    skipped = 0
    class_not_found = 0
    class_created = 0
    selection_not_found = 0
    for row in rows[1:]:
        stu_name = str(row[name_col]).strip() if row[name_col] else ""
        number = str(row[number_col]).strip() if row[number_col] else ""
        if not stu_name or not number:
            skipped += 1
            continue
        if "示例" in stu_name or "示例" in number:
            continue

        # 解析各字段
        row_class_id = fixed_class_id
        if not row_class_id and class_col is not None and row[class_col]:
            class_name = str(row[class_col]).strip()
            row_class_id = class_map.get(class_name)
            if not row_class_id and class_name:
                new_class = Class(
                    name=class_name, grade=grade or "",
                    school_id=school_id,
                )
                db.add(new_class)
                await db.flush()
                class_map[class_name] = new_class.id
                class_grade_map[new_class.id] = new_class.grade
                row_class_id = new_class.id
                class_created += 1

        gender = None
        if gender_col is not None and row[gender_col]:
            gender = str(row[gender_col]).strip()

        id_card = None
        if id_card_col is not None and row[id_card_col]:
            id_card = str(row[id_card_col]).strip()

        selection_id = None
        sel_miss = False
        if sel_col is not None and row[sel_col]:
            sel_val = str(row[sel_col]).strip()
            selection_id = sel_map.get(sel_val)
            if sel_val and not selection_id:
                sel_miss = True

        stu_grade = grade or class_grade_map.get(row_class_id, "")

        existing = await db.execute(
            select(Student).where(
                Student.school_id == school_id,
                Student.student_number == number,
            )
        )
        exist_stu = existing.scalar_one_or_none()
        if exist_stu:
            changed = False
            if row_class_id and not exist_stu.class_id:
                exist_stu.class_id = row_class_id
                changed = True
            if stu_grade and not exist_stu.grade:
                exist_stu.grade = stu_grade
                changed = True
            if gender and not exist_stu.gender:
                exist_stu.gender = gender
                changed = True
            if id_card and not exist_stu.id_card:
                exist_stu.id_card = id_card
                changed = True
            if selection_id and not exist_stu.selection_id:
                exist_stu.selection_id = selection_id
                changed = True
            if stu_name and exist_stu.name != stu_name:
                exist_stu.name = stu_name
                changed = True
            if sel_miss:
                selection_not_found += 1
            if changed:
                updated += 1
            else:
                skipped += 1
            continue

        student = Student(
            name=stu_name, student_number=number,
            class_id=row_class_id, school_id=school_id,
            grade=stu_grade or None, gender=gender,
            id_card=id_card, selection_id=selection_id,
        )
        if sel_miss:
            selection_not_found += 1
        db.add(student)
        created += 1

    await db.commit()
    logger.info("import_students: school=%s, created=%d, updated=%d, skipped=%d, class_created=%d, selection_not_found=%d",
                school_id, created, updated, skipped, class_created, selection_not_found)
    return {"created": created, "updated": updated, "skipped": skipped,
            "class_created": class_created, "selection_not_found": selection_not_found}
