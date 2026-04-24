"""Admin business logic for conduct config management."""
import logging
from datetime import date as date_type

from sqlalchemy import select, delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.user import User
from edu_cloud.models.guardian import GuardianStudentLink
from edu_cloud.modules.student.models import Student, Class
from edu_cloud.modules.conduct.models import (
    ConductClassConfig, StudentProfile, ConductRecord,
    ConductRuleItem, ConductGroup, ConductGroupMember, ConductSemester,
)
from edu_cloud.modules.conduct.crypto import encrypt
from edu_cloud.modules.conduct.parent_service import generate_invite_code
from edu_cloud.services.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


async def get_config(db: AsyncSession, class_id: str) -> dict:
    """Get ConductClassConfig by class_id."""
    config = (
        await db.execute(
            select(ConductClassConfig).where(ConductClassConfig.class_id == class_id)
        )
    ).scalar_one_or_none()
    if not config:
        raise NotFoundError("班级操行配置不存在")
    return {
        "id": config.id,
        "class_id": config.class_id,
        "invite_code": config.invite_code,
        "verify_code_type": config.verify_code_type,
        "required_parent_fields": config.required_parent_fields,
        "is_active": config.is_active,
    }


async def update_config(db: AsyncSession, class_id: str, data: dict) -> dict:
    """Update (or create) ConductClassConfig for a class."""
    config = (
        await db.execute(
            select(ConductClassConfig).where(ConductClassConfig.class_id == class_id)
        )
    ).scalar_one_or_none()

    if not config:
        # Create with defaults
        code = await _unique_invite_code(db)
        config = ConductClassConfig(
            class_id=class_id,
            invite_code=code,
        )
        db.add(config)
        await db.flush()

    if "verify_code_type" in data and data["verify_code_type"] is not None:
        config.verify_code_type = data["verify_code_type"]
    if "required_parent_fields" in data and data["required_parent_fields"] is not None:
        config.required_parent_fields = data["required_parent_fields"]
    if "is_active" in data and data["is_active"] is not None:
        config.is_active = data["is_active"]

    await db.commit()
    await db.refresh(config)

    return {
        "id": config.id,
        "class_id": config.class_id,
        "invite_code": config.invite_code,
        "verify_code_type": config.verify_code_type,
        "required_parent_fields": config.required_parent_fields,
        "is_active": config.is_active,
    }


async def regenerate_invite_code(db: AsyncSession, class_id: str) -> dict:
    """Generate a new unique invite code for the class."""
    config = (
        await db.execute(
            select(ConductClassConfig).where(ConductClassConfig.class_id == class_id)
        )
    ).scalar_one_or_none()

    if not config:
        # Create config with defaults if first time
        code = await _unique_invite_code(db)
        config = ConductClassConfig(
            class_id=class_id,
            invite_code=code,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return {"invite_code": config.invite_code}

    new_code = await _unique_invite_code(db)
    config.invite_code = new_code
    await db.commit()
    await db.refresh(config)
    return {"invite_code": config.invite_code}


async def _unique_invite_code(db: AsyncSession, max_retries: int = 10) -> str:
    """Generate a unique invite code, retry on collision."""
    for _ in range(max_retries):
        code = generate_invite_code()
        existing = (
            await db.execute(
                select(ConductClassConfig).where(ConductClassConfig.invite_code == code)
            )
        ).scalar_one_or_none()
        if not existing:
            return code
    # Fallback: extremely unlikely
    raise RuntimeError("Failed to generate unique invite code after retries")


async def setup_student_verify_code(
    db: AsyncSession, student_id: str, verify_code: str,
) -> dict:
    """Set or update the verify_code for a student profile."""
    profile = (
        await db.execute(
            select(StudentProfile).where(StudentProfile.student_id == student_id)
        )
    ).scalar_one_or_none()

    encrypted = encrypt(verify_code)

    if not profile:
        profile = StudentProfile(student_id=student_id, verify_code=encrypted)
        db.add(profile)
    else:
        profile.verify_code = encrypted

    await db.commit()
    return {"student_id": student_id, "status": "ok"}


async def list_parents(db: AsyncSession, class_id: str) -> list[dict]:
    """List all parents linked to students in a class."""
    # Find students in the class
    students = (
        await db.execute(
            select(Student).where(Student.class_id == class_id)
        )
    ).scalars().all()

    if not students:
        return []

    student_map = {s.id: s for s in students}
    student_ids = list(student_map.keys())

    # Find all GuardianStudentLinks for those students
    links = (
        await db.execute(
            select(GuardianStudentLink).where(
                GuardianStudentLink.student_id.in_(student_ids)
            )
        )
    ).scalars().all()

    if not links:
        return []

    # Group by parent user_id
    parent_links: dict[str, list[GuardianStudentLink]] = {}
    for link in links:
        parent_links.setdefault(link.guardian_user_id, []).append(link)

    # Fetch parent User info
    parent_ids = list(parent_links.keys())
    parents = (
        await db.execute(
            select(User).where(User.id.in_(parent_ids))
        )
    ).scalars().all()
    parent_map = {p.id: p for p in parents}

    result = []
    for user_id, user_links in parent_links.items():
        parent = parent_map.get(user_id)
        if not parent:
            continue
        students_info = []
        for link in user_links:
            student = student_map.get(link.student_id)
            if student:
                students_info.append({
                    "student_id": student.id,
                    "student_name": student.name,
                    "relationship": link.relationship,
                })
        result.append({
            "user_id": parent.id,
            "display_name": parent.display_name,
            "phone": parent.phone,
            "students": students_info,
        })

    return result


async def remove_parent(db: AsyncSession, class_id: str, user_id: str) -> dict:
    """Remove a parent's links to students in a specific class."""
    # Find students in the class
    students = (
        await db.execute(
            select(Student).where(Student.class_id == class_id)
        )
    ).scalars().all()

    if not students:
        raise NotFoundError("班级不存在或没有学生")

    student_ids = [s.id for s in students]

    # Delete GuardianStudentLink records for this parent in this class
    result = await db.execute(
        delete(GuardianStudentLink).where(
            GuardianStudentLink.guardian_user_id == user_id,
            GuardianStudentLink.student_id.in_(student_ids),
        )
    )
    await db.commit()

    deleted = result.rowcount
    if deleted == 0:
        raise NotFoundError("未找到该家长在此班级的绑定关系")

    logger.info(
        "admin removed parent: user_id=%s, class_id=%s, deleted=%d links",
        user_id, class_id, deleted,
    )
    return {"deleted": deleted}


# ═══════════════════════════════════════════════════
# Task 10: 积分 CRUD
# ═══════════════════════════════════════════════════

async def add_points(
    db: AsyncSession,
    class_id: str,
    operator_id: str,
    student_ids: list[str],
    points: int,
    reason: str,
    rule_item_id: str | None = None,
    record_date: date_type | None = None,
) -> list[str]:
    """Create ConductRecord per student. Returns list of created record IDs."""
    # Validate students belong to this class
    students = (
        await db.execute(
            select(Student).where(
                Student.id.in_(student_ids),
                Student.class_id == class_id,
            )
        )
    ).scalars().all()
    found_ids = {s.id for s in students}
    missing = set(student_ids) - found_ids
    if missing:
        raise ValidationError(f"以下学生不在此班级: {missing}")

    use_date = record_date or date_type.today()
    created_ids = []
    for sid in student_ids:
        record = ConductRecord(
            student_id=sid,
            class_id=class_id,
            points=points,
            reason=reason,
            date=use_date,
            operator_id=operator_id,
            source="manual",
            rule_item_id=rule_item_id,
        )
        db.add(record)
        await db.flush()
        created_ids.append(record.id)

    await db.commit()
    return created_ids


async def get_records(
    db: AsyncSession,
    class_id: str,
    page: int = 1,
    size: int = 20,
    student_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Query ConductRecord with optional filters, paginated."""
    base = (
        select(
            ConductRecord,
            User.display_name.label("operator_name"),
            Student.name.label("student_name"),
            ConductRuleItem.name.label("rule_item_name"),
        )
        .join(User, ConductRecord.operator_id == User.id)
        .join(Student, ConductRecord.student_id == Student.id)
        .outerjoin(ConductRuleItem, ConductRecord.rule_item_id == ConductRuleItem.id)
        .where(ConductRecord.class_id == class_id)
    )

    count_base = (
        select(func.count(ConductRecord.id))
        .where(ConductRecord.class_id == class_id)
    )

    if student_id:
        base = base.where(ConductRecord.student_id == student_id)
        count_base = count_base.where(ConductRecord.student_id == student_id)
    if start_date:
        base = base.where(ConductRecord.date >= start_date)
        count_base = count_base.where(ConductRecord.date >= start_date)
    if end_date:
        base = base.where(ConductRecord.date <= end_date)
        count_base = count_base.where(ConductRecord.date <= end_date)

    total = (await db.execute(count_base)).scalar() or 0

    rows = (
        await db.execute(
            base
            .order_by(ConductRecord.date.desc(), ConductRecord.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()

    items = []
    for row in rows:
        record = row[0]
        items.append({
            "id": record.id,
            "student_id": record.student_id,
            "student_name": row.student_name,
            "points": record.points,
            "reason": record.reason,
            "date": str(record.date),
            "operator_name": row.operator_name,
            "source": record.source,
            "rule_item_name": row.rule_item_name,
            "created_at": str(record.created_at),
        })

    return {"items": items, "total": total, "page": page, "size": size}


async def delete_record(db: AsyncSession, class_id: str, record_id: str) -> dict:
    """Delete a conduct record, verify class_id matches."""
    record = await db.get(ConductRecord, record_id)
    if not record or record.class_id != class_id:
        raise NotFoundError("操行记录不存在")
    await db.delete(record)
    await db.commit()
    return {"deleted": True}


async def get_student_rankings(
    db: AsyncSession, class_id: str, semester_id: str | None = None,
) -> list[dict]:
    """Rank students by total points in a class."""
    # Get all students in the class
    students = (
        await db.execute(
            select(Student).where(Student.class_id == class_id)
        )
    ).scalars().all()
    student_map = {s.id: s.name for s in students}

    # SUM points per student
    q = (
        select(
            ConductRecord.student_id,
            func.sum(ConductRecord.points).label("total"),
        )
        .where(ConductRecord.class_id == class_id)
    )
    if semester_id:
        q = q.where(ConductRecord.semester_id == semester_id)
    q = q.group_by(ConductRecord.student_id)

    rows = (await db.execute(q)).all()
    score_map = {row.student_id: row.total or 0 for row in rows}

    # Build result for ALL students (including those with 0 points)
    result = []
    for sid, sname in student_map.items():
        result.append({
            "student_id": sid,
            "student_name": sname,
            "total_points": score_map.get(sid, 0),
        })

    # Sort by total descending
    result.sort(key=lambda x: x["total_points"], reverse=True)

    # Assign rank
    for i, item in enumerate(result):
        item["rank"] = i + 1

    return result


async def get_group_rankings(
    db: AsyncSession, class_id: str, semester_id: str | None = None,
) -> list[dict]:
    """Rank groups by sum of member points."""
    groups = (
        await db.execute(
            select(ConductGroup).where(ConductGroup.class_id == class_id)
        )
    ).scalars().all()

    if not groups:
        return []

    result = []
    for group in groups:
        # Get group member student_ids
        members = (
            await db.execute(
                select(ConductGroupMember.student_id)
                .where(ConductGroupMember.group_id == group.id)
            )
        ).scalars().all()

        total = 0
        if members:
            q = (
                select(func.sum(ConductRecord.points))
                .where(
                    ConductRecord.class_id == class_id,
                    ConductRecord.student_id.in_(members),
                )
            )
            if semester_id:
                q = q.where(ConductRecord.semester_id == semester_id)
            total = (await db.execute(q)).scalar() or 0

        result.append({
            "group_id": group.id,
            "group_name": group.name,
            "avatar": group.avatar,
            "member_count": len(members),
            "total_points": total,
        })

    result.sort(key=lambda x: x["total_points"], reverse=True)
    for i, item in enumerate(result):
        item["rank"] = i + 1

    return result


# ═══════════════════════════════════════════════════
# Task 12: 小组管理
# ═══════════════════════════════════════════════════

async def get_groups(db: AsyncSession, class_id: str) -> list[dict]:
    """List groups with members for a class."""
    groups = (
        await db.execute(
            select(ConductGroup).where(ConductGroup.class_id == class_id)
        )
    ).scalars().all()

    result = []
    for group in groups:
        members_rows = (
            await db.execute(
                select(ConductGroupMember, Student.name.label("student_name"))
                .join(Student, ConductGroupMember.student_id == Student.id)
                .where(ConductGroupMember.group_id == group.id)
            )
        ).all()
        members = [
            {
                "student_id": row[0].student_id,
                "student_name": row.student_name,
            }
            for row in members_rows
        ]
        result.append({
            "id": group.id,
            "name": group.name,
            "avatar": group.avatar,
            "members": members,
        })

    return result


async def create_group(
    db: AsyncSession, class_id: str, name: str, avatar: str | None = None,
) -> dict:
    """Create a conduct group for a class."""
    group = ConductGroup(class_id=class_id, name=name, avatar=avatar)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return {"id": group.id, "name": group.name, "avatar": group.avatar}


async def delete_group(db: AsyncSession, group_id: str) -> dict:
    """Delete a group and its members."""
    group = await db.get(ConductGroup, group_id)
    if not group:
        raise NotFoundError("小组不存在")
    await db.execute(
        delete(ConductGroupMember).where(ConductGroupMember.group_id == group_id)
    )
    await db.delete(group)
    await db.commit()
    return {"deleted": True}


async def add_group_members(
    db: AsyncSession, group_id: str, student_ids: list[str],
) -> dict:
    """Bulk add students to a group."""
    group = await db.get(ConductGroup, group_id)
    if not group:
        raise NotFoundError("小组不存在")

    added = 0
    for sid in student_ids:
        # Check if already a member
        existing = (
            await db.execute(
                select(ConductGroupMember).where(
                    ConductGroupMember.group_id == group_id,
                    ConductGroupMember.student_id == sid,
                )
            )
        ).scalar_one_or_none()
        if not existing:
            db.add(ConductGroupMember(group_id=group_id, student_id=sid))
            added += 1

    await db.commit()
    return {"added": added}


async def remove_group_member(
    db: AsyncSession, group_id: str, student_id: str,
) -> dict:
    """Remove a single member from a group."""
    result = await db.execute(
        delete(ConductGroupMember).where(
            ConductGroupMember.group_id == group_id,
            ConductGroupMember.student_id == student_id,
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise NotFoundError("该学生不在此小组中")
    return {"removed": True}


# ═══════════════════════════════════════════════════
# Task 12: 学期管理
# ═══════════════════════════════════════════════════

async def get_semesters(db: AsyncSession, class_id: str) -> list[dict]:
    """List semesters — read from platform Semester table, filtered by school_id."""
    from edu_cloud.modules.academic.models import Semester
    cls = await db.get(Class, class_id)
    if not cls:
        raise NotFoundError("班级不存在")

    semesters = (
        await db.execute(
            select(Semester)
            .where(Semester.school_id == cls.school_id)
            .order_by(Semester.start_date.desc())
        )
    ).scalars().all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "start_date": str(s.start_date),
            "end_date": str(s.end_date),
            "is_current": s.is_current,
        }
        for s in semesters
    ]


async def create_semester(
    db: AsyncSession,
    class_id: str,
    name: str,
    start_date: date_type,
    end_date: date_type,
) -> dict:
    """Create semester — dual-write to both platform Semester and ConductSemester."""
    from edu_cloud.modules.academic.models import Semester

    cls = await db.get(Class, class_id)
    school_id = cls.school_id if cls else None

    # Write to platform Semester (school-level, term=1 as default)
    platform_sem = Semester(
        school_id=school_id, name=name,
        school_year=name[:9] if len(name) >= 9 else name,
        term=1, start_date=start_date, end_date=end_date,
    )
    db.add(platform_sem)

    # Write to ConductSemester (backward compat)
    conduct_sem = ConductSemester(
        class_id=class_id, school_id=school_id,
        name=name, start_date=start_date, end_date=end_date,
        is_current=False,
    )
    db.add(conduct_sem)

    await db.commit()
    await db.refresh(platform_sem)
    return {
        "id": platform_sem.id,
        "name": platform_sem.name,
        "start_date": str(platform_sem.start_date),
        "end_date": str(platform_sem.end_date),
        "is_current": platform_sem.is_current,
    }


async def activate_semester(db: AsyncSession, semester_id: str) -> dict:
    """Activate — sync both platform Semester and ConductSemester."""
    from edu_cloud.modules.academic.models import Semester

    # Try platform Semester first
    semester = await db.get(Semester, semester_id)
    if not semester:
        # Fallback: might be a ConductSemester id (legacy)
        conduct_sem = await db.get(ConductSemester, semester_id)
        if not conduct_sem:
            raise NotFoundError("学期不存在")
        await db.execute(
            update(ConductSemester)
            .where(ConductSemester.class_id == conduct_sem.class_id)
            .values(is_current=False)
        )
        conduct_sem.is_current = True
        await db.commit()
        await db.refresh(conduct_sem)
        return {
            "id": conduct_sem.id, "name": conduct_sem.name,
            "start_date": str(conduct_sem.start_date),
            "end_date": str(conduct_sem.end_date),
            "is_current": conduct_sem.is_current,
        }

    # Platform path: deactivate all in school, activate target
    await db.execute(
        update(Semester)
        .where(Semester.school_id == semester.school_id)
        .values(is_current=False)
    )
    semester.is_current = True

    # Sync ConductSemester (best-effort)
    await db.execute(
        update(ConductSemester)
        .where(ConductSemester.school_id == semester.school_id)
        .values(is_current=False)
    )

    await db.commit()
    await db.refresh(semester)
    return {
        "id": semester.id, "name": semester.name,
        "start_date": str(semester.start_date),
        "end_date": str(semester.end_date),
        "is_current": semester.is_current,
    }
