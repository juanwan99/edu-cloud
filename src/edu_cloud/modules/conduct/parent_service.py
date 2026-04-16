"""Parent authentication service — register, login, bind child, query children."""
import logging
import random
import string

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.conduct.models import (
    ConductClassConfig, ConductRecord, ConductRuleCategory, ConductRuleItem, StudentProfile,
)
from edu_cloud.modules.conduct.crypto import decrypt
from edu_cloud.shared.auth import create_access_token
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from edu_cloud.models.guardian import GuardianStudentLink

logger = logging.getLogger(__name__)


def generate_invite_code(length: int = 6) -> str:
    """Generate a random uppercase + digits invite code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


async def get_invite_info(db: AsyncSession, code: str) -> dict:
    """Validate invite code and return class/school info."""
    row = (
        await db.execute(
            select(ConductClassConfig, Class, School)
            .join(Class, ConductClassConfig.class_id == Class.id)
            .join(School, Class.school_id == School.id)
            .where(
                ConductClassConfig.invite_code == code,
                ConductClassConfig.is_active.is_(True),
            )
        )
    ).first()
    if not row:
        raise NotFoundError("邀请码无效或已失效")
    config, cls, school = row
    return {
        "class_name": cls.name,
        "school_name": school.name,
        "verify_code_type": config.verify_code_type,
    }


async def register_parent(
    db: AsyncSession,
    phone: str,
    display_name: str,
    password: str,
    invite_code: str,
    relationship: str = "other",
) -> dict:
    """Register a parent account and return JWT token."""
    # Check phone uniqueness
    existing = (
        await db.execute(
            select(User).where(
                or_(User.username == phone, User.phone == phone)
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ValidationError("该手机号已注册")

    # Validate invite code — get class/school info
    row = (
        await db.execute(
            select(ConductClassConfig, Class)
            .join(Class, ConductClassConfig.class_id == Class.id)
            .where(
                ConductClassConfig.invite_code == invite_code,
                ConductClassConfig.is_active.is_(True),
            )
        )
    ).first()
    if not row:
        raise NotFoundError("邀请码无效或已失效")
    config, cls = row

    # Create User
    user = User(username=phone, phone=phone, display_name=display_name)
    user.set_password(password)
    db.add(user)
    await db.flush()

    # Create UserRole (parent)
    role = UserRole(
        user_id=user.id,
        role="parent",
        school_id=cls.school_id,
        is_primary=True,
    )
    db.add(role)
    await db.commit()
    await db.refresh(user)
    await db.refresh(role)

    token = create_access_token({
        "sub": user.id,
        "role": "parent",
        "active_role_id": role.id,
    })
    logger.info("parent registered: user_id=%s, phone=%s", user.id, phone)
    return {"access_token": token, "token_type": "bearer"}


async def login_parent(db: AsyncSession, phone: str, password: str) -> dict:
    """Login a parent by phone and return JWT token."""
    user = (
        await db.execute(
            select(User).where(User.username == phone)
        )
    ).scalar_one_or_none()
    if not user or not user.verify_password(password):
        raise ValidationError("手机号或密码错误")

    # Find parent role
    role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role == "parent",
            )
        )
    ).scalar_one_or_none()
    if not role:
        raise ValidationError("该账号不是家长账号")

    token = create_access_token({
        "sub": user.id,
        "role": "parent",
        "active_role_id": role.id,
    })
    logger.info("parent login: user_id=%s", user.id)
    return {"access_token": token, "token_type": "bearer"}


async def bind_child(
    db: AsyncSession,
    user_id: str,
    class_id: str,
    student_name: str,
    verify_code: str,
    relationship: str = "other",
) -> dict:
    """Bind a parent to a student after identity verification."""
    # Get class config
    config = (
        await db.execute(
            select(ConductClassConfig).where(
                ConductClassConfig.class_id == class_id,
                ConductClassConfig.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not config:
        raise NotFoundError("班级未开通操行管理")

    # Find student
    student = (
        await db.execute(
            select(Student).where(
                Student.class_id == class_id,
                Student.name == student_name,
            )
        )
    ).scalar_one_or_none()
    if not student:
        raise NotFoundError("未找到该学生")

    # Verify identity based on config type
    verify_type = config.verify_code_type
    profile = (
        await db.execute(
            select(StudentProfile).where(StudentProfile.student_id == student.id)
        )
    ).scalar_one_or_none()

    if verify_type == "id_card":
        # N001/F005 Option A（Round 1 用户决策，锁定契约）：
        # 比对身份证号后 6 位。严禁退化为整串相等——整串相等让完整身份证号
        # 在输入流量中以明文出现，违反 Option A 授权边界。
        stored = decrypt(profile.id_card_number) if profile else None
        if not stored or stored[-6:] != verify_code:
            raise ValidationError("身份证号验证失败")
    elif verify_type in ("phone", "custom"):
        # F005 Option A: phone 与 custom 共享 verify_code 字段
        # verify_code_type 仅决定输入 UX 提示类型（手机号 vs 自定义文本）
        stored = decrypt(profile.verify_code) if profile else None
        if not stored or stored != verify_code:
            msg = "手机号验证失败" if verify_type == "phone" else "验证码错误"
            raise ValidationError(msg)
    else:
        raise ValidationError(f"未知的验证类型: {verify_type}")

    # Check not already bound
    existing_link = (
        await db.execute(
            select(GuardianStudentLink).where(
                GuardianStudentLink.guardian_user_id == user_id,
                GuardianStudentLink.student_id == student.id,
            )
        )
    ).scalar_one_or_none()
    if existing_link:
        raise ValidationError("已绑定该学生")

    # Get parent role for school_id
    role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role == "parent",
            )
        )
    ).scalar_one_or_none()
    school_id = role.school_id if role else ""

    link = GuardianStudentLink(
        guardian_user_id=user_id,
        student_id=student.id,
        relationship=relationship,
        is_primary=False,
        school_id=school_id,
    )
    db.add(link)
    await db.commit()
    logger.info("parent bind: user_id=%s, student_id=%s", user_id, student.id)
    return {"student_id": student.id, "student_name": student.name}


async def get_children(db: AsyncSession, user_id: str) -> list[dict]:
    """Query all bound children with their conduct points summary."""
    links = (
        await db.execute(
            select(GuardianStudentLink, Student, Class)
            .join(Student, GuardianStudentLink.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .where(GuardianStudentLink.guardian_user_id == user_id)
        )
    ).all()

    result = []
    for link, student, cls in links:
        # Sum conduct points for this student
        total_points = (
            await db.execute(
                select(func.coalesce(func.sum(ConductRecord.points), 0)).where(
                    ConductRecord.student_id == student.id,
                )
            )
        ).scalar()
        result.append({
            "student_id": student.id,
            "student_name": student.name,
            "class_id": cls.id,
            "class_name": cls.name,
            "relationship": link.relationship,
            "total_points": total_points or 0,
        })
    return result


# ── Parent query endpoints (Task 5) ──


async def _verify_guardian_link(db: AsyncSession, user_id: str, student_id: str) -> GuardianStudentLink:
    """Verify the user has a GuardianStudentLink to the given student."""
    link = (
        await db.execute(
            select(GuardianStudentLink).where(
                GuardianStudentLink.guardian_user_id == user_id,
                GuardianStudentLink.student_id == student_id,
            )
        )
    ).scalar_one_or_none()
    if not link:
        raise PermissionDeniedError("您没有查看该学生信息的权限")
    return link


async def _verify_guardian_class(db: AsyncSession, user_id: str, class_id: str) -> None:
    """Verify the user has at least one bound student in the given class."""
    exists = (
        await db.execute(
            select(GuardianStudentLink.id)
            .join(Student, GuardianStudentLink.student_id == Student.id)
            .where(
                GuardianStudentLink.guardian_user_id == user_id,
                Student.class_id == class_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if not exists:
        raise PermissionDeniedError("您没有查看该班级信息的权限")


async def get_child_records(
    db: AsyncSession, user_id: str, student_id: str, page: int = 1, size: int = 20,
) -> dict:
    """Get paginated conduct records for a bound child."""
    await _verify_guardian_link(db, user_id, student_id)

    Operator = aliased(User)

    # Total count
    total = (
        await db.execute(
            select(func.count()).select_from(ConductRecord).where(
                ConductRecord.student_id == student_id,
            )
        )
    ).scalar() or 0

    # Paginated query with operator name and rule_item name
    offset = (page - 1) * size
    rows = (
        await db.execute(
            select(ConductRecord, Operator.display_name, ConductRuleItem.name)
            .join(Operator, ConductRecord.operator_id == Operator.id)
            .outerjoin(ConductRuleItem, ConductRecord.rule_item_id == ConductRuleItem.id)
            .where(ConductRecord.student_id == student_id)
            .order_by(ConductRecord.date.desc(), ConductRecord.created_at.desc())
            .offset(offset)
            .limit(size)
        )
    ).all()

    items = []
    for record, operator_name, rule_item_name in rows:
        items.append({
            "id": record.id,
            "points": record.points,
            "reason": record.reason,
            "date": str(record.date),
            "operator_name": operator_name,
            "source": record.source,
            "rule_item_name": rule_item_name,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        })

    return {"items": items, "total": total, "page": page, "size": size}


async def get_child_rankings(db: AsyncSession, user_id: str, student_id: str) -> list[dict]:
    """Get class rankings by total conduct points, highlighting the requested student."""
    await _verify_guardian_link(db, user_id, student_id)

    # Get student's class_id
    student = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalar_one_or_none()
    if not student or not student.class_id:
        raise NotFoundError("未找到学生或班级信息")

    class_id = student.class_id

    # Query all students in that class with their total points
    rows = (
        await db.execute(
            select(
                Student.id,
                Student.name,
                func.coalesce(func.sum(ConductRecord.points), 0).label("total_points"),
            )
            .outerjoin(ConductRecord, ConductRecord.student_id == Student.id)
            .where(Student.class_id == class_id)
            .group_by(Student.id, Student.name)
            .order_by(func.coalesce(func.sum(ConductRecord.points), 0).desc())
        )
    ).all()

    result = []
    for rank, (sid, sname, total) in enumerate(rows, start=1):
        result.append({
            "rank": rank,
            "student_id": sid,
            "student_name": sname,
            "total_points": total,
            "is_self": sid == student_id,
        })
    return result


async def get_class_rules(db: AsyncSession, user_id: str, class_id: str) -> list[dict]:
    """Get class rules (categories + items) for a given class.

    Requires the guardian to have at least one bound student in this class.
    """
    await _verify_guardian_class(db, user_id, class_id)
    # Get the class to find school_id
    cls = (
        await db.execute(select(Class).where(Class.id == class_id))
    ).scalar_one_or_none()
    if not cls:
        raise NotFoundError("班级不存在")

    # Query categories: class-level OR school-level
    categories = (
        await db.execute(
            select(ConductRuleCategory)
            .where(
                or_(
                    ConductRuleCategory.class_id == class_id,
                    ConductRuleCategory.school_id == cls.school_id,
                )
            )
            .order_by(ConductRuleCategory.sort_order)
        )
    ).scalars().all()

    result = []
    for cat in categories:
        # Query items for this category
        items = (
            await db.execute(
                select(ConductRuleItem)
                .where(ConductRuleItem.category_id == cat.id)
                .order_by(ConductRuleItem.sort_order)
            )
        ).scalars().all()
        result.append({
            "id": cat.id,
            "name": cat.name,
            "sort_order": cat.sort_order,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "points": item.points,
                    "sort_order": item.sort_order,
                }
                for item in items
            ],
        })
    return result


async def update_parent_profile(db: AsyncSession, user_id: str, data: dict) -> dict:
    """Update parent profile (only display_name allowed)."""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise NotFoundError("用户不存在")

    if "display_name" in data and data["display_name"]:
        user.display_name = data["display_name"]
        await db.commit()
        await db.refresh(user)

    return {
        "user_id": user.id,
        "display_name": user.display_name,
        "phone": user.phone,
    }


async def change_parent_password(
    db: AsyncSession, user_id: str, old_password: str, new_password: str,
) -> dict:
    """Change parent password after verifying old password."""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise NotFoundError("用户不存在")

    if not user.verify_password(old_password):
        raise ValidationError("旧密码错误")

    if len(new_password) < 6:
        raise ValidationError("新密码长度不能少于6位")

    user.set_password(new_password)
    await db.commit()
    logger.info("parent password changed: user_id=%s", user_id)
    return {"message": "密码修改成功"}
