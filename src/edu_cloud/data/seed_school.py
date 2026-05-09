"""完全中学种子数据 — 200 教师 + 1500 学生 + 36 班级 + 完整组织架构。

基于中国教育部《中小学教职工编制标准》和课程方案调研：
- 完全中学（初中+高中）6 年级 36 班
- 年级分布：七(7×42) 八(7×42) 九(5×42) 高一(6×42) 高二(5×42) 高三(6×40)
- 师生比 1:7.5（城市重点中学水平）

调用方式：python -m edu_cloud.data.seed_school
幂等：检查学校 code 是否已存在。
"""
import asyncio
import logging
import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.config import settings

logger = logging.getLogger(__name__)

# ─── 学校基础信息 ───────────────────────────────────────────────────────

SCHOOL_NAME = "育才实验中学"
SCHOOL_CODE = "YCSY2026"
SCHOOL_DISTRICT = "海淀区"

# ─── 年级和班级编排 ──────────────────────────────────────────────────────

GRADE_PLAN = [
    # (grade_name, grade_number, num_classes, students_per_class)
    ("七年级", 7, 7, 42),
    ("八年级", 8, 7, 42),
    ("九年级", 9, 5, 42),
    ("高一", 10, 6, 42),
    ("高二", 11, 5, 42),
    ("高三", 12, 6, 40),
]

# ─── 学科代码 ───────────────────────────────────────────────────────────

SUBJECT_CODES = {
    "YW": "语文", "SX": "数学", "YY": "英语",
    "WL": "物理", "HX": "化学", "SW": "生物",
    "ZZ": "政治", "LS": "历史", "DL": "地理",
    "TY": "体育", "YL": "音乐", "MS": "美术",
    "XX": "信息科技", "TJ": "通用技术",
}

# 各年级开设的科目（code 列表）
GRADE_SUBJECTS = {
    7:  ["YW", "SX", "YY", "ZZ", "LS", "DL", "SW", "TY", "YL", "MS", "XX"],
    8:  ["YW", "SX", "YY", "WL", "ZZ", "LS", "DL", "SW", "TY", "YL", "MS", "XX"],
    9:  ["YW", "SX", "YY", "WL", "HX", "ZZ", "LS", "TY", "YL", "MS"],
    10: ["YW", "SX", "YY", "WL", "HX", "SW", "ZZ", "LS", "DL", "TY", "YL", "MS", "XX", "TJ"],
    11: ["YW", "SX", "YY", "WL", "HX", "SW", "ZZ", "LS", "DL", "TY", "YL", "MS"],
    12: ["YW", "SX", "YY", "WL", "HX", "SW", "ZZ", "LS", "DL", "TY"],
}

# ─── 教师分配方案 ────────────────────────────────────────────────────────
# (subject_code, 初中人数, 高中人数)
TEACHER_PLAN = [
    ("YW", 15, 11), ("SX", 14, 11), ("YY", 14, 11),
    ("WL", 5, 7),   ("HX", 2, 6),   ("SW", 4, 4),
    ("ZZ", 5, 4),   ("LS", 4, 4),   ("DL", 3, 3),
    ("TY", 6, 6),   ("YL", 2, 1),   ("MS", 2, 1),
    ("XX", 2, 1),   ("TJ", 0, 1),
]

# ─── 行政人员 ────────────────────────────────────────────────────────────

ADMIN_STAFF = [
    # (display_name, role, 兼任学科, 兼任初/高)
    ("王建国", "principal", "YW", None),      # 校长（语文出身）
    ("李明华", "academic_director", "SX", None),  # 分管教学副校长→教务主任
    ("赵德文", "academic_director", "YY", None),  # 分管德育副校长→教务主任（另一位）
]

MIDDLE_MANAGERS = [
    # (display_name, admin_title, 兼任学科, 部门)
    ("陈志远", "教务处主任", "SX", "grade_leader"),
    ("周红梅", "教务处副主任", "YW", None),
    ("吴建平", "德育处主任", "ZZ", None),
    ("郑晓东", "德育处副主任", "TY", None),
    ("孙丽华", "总务处主任", None, None),
    ("钱伟", "教科室主任", "WL", None),
    ("何静", "办公室主任", "YY", None),
    ("冯刚", "团委书记", "LS", None),
]

# ─── 姓名生成 ────────────────────────────────────────────────────────────

SURNAMES = [
    "王", "李", "张", "刘", "陈", "杨", "黄", "赵", "吴", "周",
    "徐", "孙", "马", "朱", "胡", "郭", "林", "何", "高", "罗",
    "郑", "梁", "谢", "宋", "唐", "韩", "曹", "许", "邓", "冯",
    "袁", "彭", "曾", "萧", "田", "董", "潘", "余", "蒋", "蔡",
    "贾", "丁", "魏", "薛", "叶", "阎", "于", "段", "雷", "侯",
]
# 权重：前10大姓占45%
SURNAME_WEIGHTS = [6, 6, 5, 5, 5, 4, 3, 3, 3, 3] + [1.5] * 10 + [1] * 30

MALE_CHARS = list("伟强磊军勇明杰涛浩亮辉鹏飞华宇翔博志达昊然宸睿轩泽铭皓瑞骏彦栋峰")
FEMALE_CHARS = list("芳娟敏静丽艳秀娜慧婷雪梅莉琳玲琴萍蓉颖欣怡雨涵诗瑶蕊菲悦婧")

_used_names = set()


def _gen_name(gender: str) -> str:
    """生成不重复的中文姓名。"""
    chars = MALE_CHARS if gender == "M" else FEMALE_CHARS
    for _ in range(200):
        surname = random.choices(SURNAMES, weights=SURNAME_WEIGHTS, k=1)[0]
        if random.random() < 0.35:
            name = surname + random.choice(chars)
        else:
            name = surname + random.choice(chars) + random.choice(chars)
        if name not in _used_names:
            _used_names.add(name)
            return name
    # fallback：加数字
    return surname + random.choice(chars) + str(random.randint(1, 9))


# ─── 核心生成逻辑 ────────────────────────────────────────────────────────

async def seed_complete_school(db: AsyncSession) -> dict:
    """生成完整学校种子数据。返回统计信息。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.student.models import Class, Student

    # 幂等检查
    existing = (await db.execute(
        select(School).where(School.code == SCHOOL_CODE)
    )).scalar_one_or_none()
    if existing:
        return {"status": "already_seeded", "message": f"学校 {SCHOOL_CODE} 已存在"}

    random.seed(2026)
    _used_names.clear()

    # ── 1. 创建学校 ──
    school = School(name=SCHOOL_NAME, code=SCHOOL_CODE, district=SCHOOL_DISTRICT)
    db.add(school)
    await db.flush()
    school_id = school.id
    logger.info("Created school: %s (%s)", SCHOOL_NAME, school_id)

    # ── 2. 创建班级 ──
    classes = []  # [(class_obj, grade_name, grade_number)]
    for grade_name, grade_num, num_cls, _ in GRADE_PLAN:
        for i in range(1, num_cls + 1):
            cls = Class(
                name=f"{grade_name}{i}班",
                grade=grade_name,
                grade_number=grade_num,
                school_id=school_id,
            )
            db.add(cls)
            classes.append((cls, grade_name, grade_num))
    await db.flush()
    logger.info("Created %d classes", len(classes))

    # 按年级分组
    grade_classes = {}
    for cls, gname, gnum in classes:
        grade_classes.setdefault(gnum, []).append(cls)

    # ── 3. 创建学生 ──
    student_count = 0
    for grade_name, grade_num, num_cls, per_class in GRADE_PLAN:
        for cls in grade_classes[grade_num]:
            for j in range(per_class):
                gender = "M" if random.random() < 0.51 else "F"
                student = Student(
                    name=_gen_name(gender),
                    student_number=f"G{grade_num:02d}C{cls.name[-2]}{j + 1:03d}",
                    class_id=cls.id,
                    school_id=school_id,
                    grade=grade_name,
                    gender=gender,
                    enrollment_year=2026 - (grade_num - 6) if grade_num <= 9 else 2026 - (grade_num - 9),
                    status="active",
                )
                db.add(student)
                student_count += 1
    await db.flush()
    logger.info("Created %d students", student_count)

    # ── 4. 创建教师（科任教师） ──
    teachers = []  # [(user, subject_code, division)]  division: "初中"/"高中"

    for subj_code, ms_count, hs_count in TEACHER_PLAN:
        subj_name = SUBJECT_CODES[subj_code]
        for i in range(ms_count):
            gender = random.choice(["M", "F"])
            user = User(
                username=f"t_{subj_code.lower()}_{len(teachers) + 1:03d}",
                display_name=_gen_name(gender),
            )
            user.set_password(settings.SEED_DEFAULT_PASSWORD)
            db.add(user)
            teachers.append((user, subj_code, "初中"))

        for i in range(hs_count):
            gender = random.choice(["M", "F"])
            user = User(
                username=f"t_{subj_code.lower()}_{len(teachers) + 1:03d}",
                display_name=_gen_name(gender),
            )
            user.set_password(settings.SEED_DEFAULT_PASSWORD)
            db.add(user)
            teachers.append((user, subj_code, "高中"))

    await db.flush()
    logger.info("Created %d subject teachers", len(teachers))

    # ── 5. 创建行政人员 ──
    admin_users = []

    # 校长 + 教务主任
    for display_name, role, subj, _ in ADMIN_STAFF:
        user = User(username=f"admin_{role}_{len(admin_users) + 1}", display_name=display_name)
        user.set_password(settings.SEED_DEFAULT_PASSWORD)
        db.add(user)
        admin_users.append((user, role, subj))

    # 中层干部
    for display_name, title, subj, extra_role in MIDDLE_MANAGERS:
        user = User(username=f"mgr_{len(admin_users) + 1}", display_name=display_name)
        user.set_password(settings.SEED_DEFAULT_PASSWORD)
        db.add(user)
        admin_users.append((user, "academic_director" if "教务" in title else "homeroom_teacher", subj))

    # 补充行政辅助人员（无教学任务）
    support_titles = [
        # 专业技术（6）
        "校医", "心理教师", "实验员(物理)", "实验员(化学)", "实验员(生物)", "图书管理员",
        # 信息化（3）
        "网络管理员", "电教管理员", "档案管理员",
        # 教研组长（9，主要学科各1）
        "语文教研组长", "数学教研组长", "英语教研组长",
        "物理教研组长", "化学教研组长", "生物教研组长",
        "政治教研组长", "历史教研组长", "地理教研组长",
        # 后勤（8）
        "财务主管", "财务出纳", "采购员", "食堂管理员", "保卫科长",
        "水电维修", "校舍管理", "绿化管理",
        # 行政助理（4）
        "校办文秘", "教务干事", "德育干事", "团委干事",
        # 教辅（10）
        "教辅1", "教辅2", "教辅3", "教辅4", "教辅5",
        "教辅6", "教辅7", "教辅8", "教辅9", "教辅10",
    ]
    for title in support_titles:
        gender = random.choice(["M", "F"])
        user = User(username=f"staff_{len(admin_users) + len(teachers) + 1}", display_name=_gen_name(gender))
        user.set_password(settings.SEED_DEFAULT_PASSWORD)
        db.add(user)
        admin_users.append((user, "subject_teacher", None))  # 最低权限

    await db.flush()
    total_teachers = len(teachers) + len(admin_users)
    logger.info("Created %d admin/support staff (total personnel: %d)", len(admin_users), total_teachers)

    # ── 6. 分配教学任务（UserRole） ──

    # 6a. 科任教师分配班级
    # 主科（语数英）每人教 2 个班，副科每人教 4-5 个班
    main_subjects = {"YW", "SX", "YY"}

    for subj_code, division_teachers in _group_teachers_by_subject(teachers):
        for div_name, div_teachers in division_teachers.items():
            # 找出该学段+该科目需要覆盖的班级
            if div_name == "初中":
                target_grades = [7, 8, 9]
            else:
                target_grades = [10, 11, 12]

            target_classes = []
            for gnum in target_grades:
                if subj_code in GRADE_SUBJECTS.get(gnum, []):
                    target_classes.extend(grade_classes.get(gnum, []))

            if not target_classes or not div_teachers:
                continue

            # 均匀分配
            classes_per_teacher = max(1, len(target_classes) // len(div_teachers))
            idx = 0
            for teacher_user, _, _ in div_teachers:
                assigned = target_classes[idx:idx + classes_per_teacher]
                if not assigned:
                    assigned = [target_classes[-1]]  # 至少分一个班
                idx += classes_per_teacher

                role = UserRole(
                    user_id=teacher_user.id,
                    role="subject_teacher",
                    school_id=school_id,
                    class_ids=[c.id for c in assigned],
                    subject_codes=[subj_code],
                    is_primary=True,
                )
                db.add(role)

    # 6b. 班主任分配（从语数英教师中选）
    homeroom_candidates = [
        (u, s, d) for u, s, d in teachers
        if s in main_subjects
    ]
    random.shuffle(homeroom_candidates)
    homeroom_idx = 0

    for cls, gname, gnum in classes:
        if homeroom_idx < len(homeroom_candidates):
            teacher_user, subj, div = homeroom_candidates[homeroom_idx]
            homeroom_idx += 1

            # 添加班主任角色
            hr_role = UserRole(
                user_id=teacher_user.id,
                role="homeroom_teacher",
                school_id=school_id,
                class_ids=[cls.id],
                is_primary=False,  # 科任是 primary
            )
            db.add(hr_role)

            # 更新班级的 head_teacher_id
            cls.head_teacher_id = teacher_user.id

    # 6c. 年级组长（每年级一个，从该年级班主任中选）
    grade_leader_assigned = set()
    for cls, gname, gnum in classes:
        if gnum not in grade_leader_assigned and cls.head_teacher_id:
            gl_role = UserRole(
                user_id=cls.head_teacher_id,
                role="grade_leader",
                school_id=school_id,
                grade_ids=[str(gnum)],
                is_primary=False,
            )
            db.add(gl_role)
            grade_leader_assigned.add(gnum)

    # 6d. 行政人员角色
    for user, role, subj in admin_users:
        ur = UserRole(
            user_id=user.id,
            role=role,
            school_id=school_id,
            is_primary=True,
        )
        if subj:
            ur.subject_codes = [subj]
        db.add(ur)

    # ── 7. 平台管理员（已由 app.py lifespan 创建，这里补 principal 角色到校长） ──
    principal_user = admin_users[0][0]  # 王建国
    principal_role = UserRole(
        user_id=principal_user.id,
        role="principal",
        school_id=school_id,
        is_primary=False,  # academic_director 已设为 primary（等效，校长查看全校）
    )
    db.add(principal_role)

    await db.commit()

    return {
        "status": "seeded",
        "school": SCHOOL_NAME,
        "classes": len(classes),
        "students": student_count,
        "teachers": len(teachers),
        "admin_staff": len(admin_users),
        "total_personnel": total_teachers,
    }


def _group_teachers_by_subject(teachers):
    """按学科+学段分组教师。"""
    groups = {}
    for user, subj, div in teachers:
        groups.setdefault(subj, {}).setdefault(div, []).append((user, subj, div))

    return list(groups.items())


# ─── CLI 入口 ────────────────────────────────────────────────────────────

async def main():
    """独立运行：读取 .env 连接数据库并生成种子数据。"""
    import os
    import sys

    # 确保能 import edu_cloud
    src_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    sys.path.insert(0, os.path.abspath(src_dir))

    from edu_cloud.config import settings

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    if "sqlite" not in settings.DATABASE_URL:
        print("WARNING: 非 SQLite 环境请使用 scripts/db_migrate 管理 schema", file=sys.stderr)
    # 如果是 SQLite，需要先建表
    if "sqlite" in settings.DATABASE_URL:
        from edu_cloud.models.base import Base
        # Import all models
        import edu_cloud.models.school  # noqa
        import edu_cloud.models.user  # noqa
        import edu_cloud.models.user_role  # noqa
        import edu_cloud.models.student  # noqa
        import edu_cloud.models.class_group  # noqa
        import edu_cloud.models.exam  # noqa
        import edu_cloud.models.ai_session  # noqa
        import edu_cloud.models.document  # noqa
        import edu_cloud.models.approval  # noqa
        import edu_cloud.models.calendar  # noqa
        import edu_cloud.models.notification  # noqa
        import edu_cloud.models.llm_slot  # noqa
        import edu_cloud.modules.card.models  # noqa
        import edu_cloud.modules.scan.models  # noqa
        import edu_cloud.modules.grading.models  # noqa
        import edu_cloud.modules.marking.models  # noqa
        import edu_cloud.modules.knowledge.models  # noqa
        import edu_cloud.modules.bank.models  # noqa
        import edu_cloud.modules.profile.models  # noqa

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        result = await seed_complete_school(session)
        print(f"\n{'=' * 50}")
        for k, v in result.items():
            print(f"  {k}: {v}")
        print(f"{'=' * 50}\n")

    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(main())
