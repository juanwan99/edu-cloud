"""高中部数据补充种子 — 在育才实验中学基础上扩充到 36 班/~1512 人 + 选科组合 + 排课。

补充内容：
1. 班级：高一 +6, 高二 +7, 高三 +6 = 19 新班级（每年级达 12 班）
2. 学生：填充所有高中班级到 42 人/班（含高三旧班 40→42）
3. 教师：按需新增高中科目教师
4. 选科组合 (subject_selections)：高二 5 + 高三 6 = 11 条
5. 排课 (teacher_assignments)：全部高中教师×班级×科目

调用方式：python -m edu_cloud.data.seed_highschool_supplement
幂等：检查"高一7班"是否已存在。
"""
import asyncio
import json
import logging
import random
import uuid

from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.config import settings

logger = logging.getLogger(__name__)

SCHOOL_CODE = "YCSY2026"
SEMESTER = "2025-2026-2"
TARGET_PER_CLASS = 42

# ─── 选科组合配置 ──────────────────────────────────────────────────────────

COMBO_SUBJECTS = {
    "物化生": ["WL", "HX", "SW"],
    "物化地": ["WL", "HX", "DL"],
    "物化政": ["WL", "HX", "ZZ"],
    "物生地": ["WL", "SW", "DL"],
    "历政地": ["LS", "ZZ", "DL"],
    "历生地": ["LS", "SW", "DL"],
}

# 高二 5 组合 → 12 班分配
G11_COMBO_PLAN = [
    # (combo_name, num_classes)  班号按顺序递增
    ("物化生", 3),   # 高二1-3班
    ("物化地", 2),   # 高二4-5班
    ("物化政", 2),   # 高二6-7班
    ("历政地", 3),   # 高二8-10班
    ("历生地", 2),   # 高二11-12班
]

# 高三 6 组合 → 12 班分配
G12_COMBO_PLAN = [
    ("物化生", 2),   # 高三1-2班
    ("物化地", 2),   # 高三3-4班
    ("物化政", 2),   # 高三5-6班
    ("物生地", 2),   # 高三7-8班
    ("历政地", 2),   # 高三9-10班
    ("历生地", 2),   # 高三11-12班
]

# 各年级必修科目（语数英体 + 高一全科/高二副科/高三体育）
REQUIRED_SUBJECTS = {
    10: ["YW", "SX", "YY", "WL", "HX", "SW", "ZZ", "LS", "DL",
         "TY", "YL", "MS", "XX", "TJ"],
    11: ["YW", "SX", "YY", "TY", "YL", "MS"],  # + combo electives
    12: ["YW", "SX", "YY", "TY"],               # + combo electives
}

SUBJECT_NAMES = {
    "YW": "语文", "SX": "数学", "YY": "英语",
    "WL": "物理", "HX": "化学", "SW": "生物",
    "ZZ": "政治", "LS": "历史", "DL": "地理",
    "TY": "体育", "YL": "音乐", "MS": "美术",
    "XX": "信息科技", "TJ": "通用技术",
}

# ─── 教师编制（高中部目标） ──────────────────────────────────────────────────
# 根据 36 班计算的理想教师数

HS_TEACHER_TARGET = {
    "YW": 18, "SX": 18, "YY": 18,
    "WL": 7,  "HX": 7,  "SW": 6,
    "ZZ": 6,  "LS": 6,  "DL": 7,
    "TY": 6,  "YL": 3,  "MS": 3,
    "XX": 2,  "TJ": 1,
}

# ─── 姓名生成 ────────────────────────────────────────────────────────────

SURNAMES = [
    "王", "李", "张", "刘", "陈", "杨", "黄", "赵", "吴", "周",
    "徐", "孙", "马", "朱", "胡", "郭", "林", "何", "高", "罗",
    "郑", "梁", "谢", "宋", "唐", "韩", "曹", "许", "邓", "冯",
    "袁", "彭", "曾", "萧", "田", "董", "潘", "余", "蒋", "蔡",
    "贾", "丁", "魏", "薛", "叶", "阎", "于", "段", "雷", "侯",
]
SURNAME_WEIGHTS = [6, 6, 5, 5, 5, 4, 3, 3, 3, 3] + [1.5] * 10 + [1] * 30
MALE_CHARS = list("伟强磊军勇明杰涛浩亮辉鹏飞华宇翔博志达昊然宸睿轩泽铭皓瑞骏彦栋峰")
FEMALE_CHARS = list("芳娟敏静丽艳秀娜慧婷雪梅莉琳玲琴萍蓉颖欣怡雨涵诗瑶蕊菲悦婧")

_used_names: set[str] = set()


def _gen_name(gender: str) -> str:
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
    return surname + random.choice(chars) + str(random.randint(1, 99))


# ─── 辅助：查询现有班级的科目清单 ──────────────────────────────────────────

def _get_class_subjects(grade_num: int, class_num: int,
                        g11_class_combos: dict, g12_class_combos: dict) -> list[str]:
    """返回某个班级应开设的全部科目代码列表。"""
    required = list(REQUIRED_SUBJECTS[grade_num])
    if grade_num == 10:
        return required  # 高一全科

    combo_map = g11_class_combos if grade_num == 11 else g12_class_combos
    combo_name = combo_map.get(class_num)
    if combo_name:
        for subj in COMBO_SUBJECTS[combo_name]:
            if subj not in required:
                required.append(subj)
    return required


def _build_combo_class_map(combo_plan: list[tuple[str, int]]) -> dict[int, str]:
    """从组合计划生成 {class_num: combo_name} 映射。"""
    mapping = {}
    class_num = 1
    for combo_name, count in combo_plan:
        for _ in range(count):
            mapping[class_num] = combo_name
            class_num += 1
    return mapping


# ─── 核心逻辑 ────────────────────────────────────────────────────────────

async def seed_highschool_supplement(db: AsyncSession) -> dict:
    """在现有育才实验中学数据上补充高中部。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.teacher_assignment import TeacherAssignment
    from edu_cloud.models.subject_selection import SubjectSelection
    from edu_cloud.modules.student.models import Class, Student

    random.seed(20260412)
    _used_names.clear()

    # ── 0. 找到学校 ──
    school = (await db.execute(
        select(School).where(School.code == SCHOOL_CODE)
    )).scalar_one_or_none()
    if not school:
        return {"status": "error", "message": f"学校 {SCHOOL_CODE} 不存在，请先跑 seed_school"}
    school_id = school.id

    # 幂等检查
    existing_check = (await db.execute(
        select(Class).where(Class.school_id == school_id, Class.name == "高一7班")
    )).scalar_one_or_none()
    if existing_check:
        return {"status": "already_seeded", "message": "高中补充数据已存在"}

    # 预加载已有名称避免重复
    existing_names = (await db.execute(
        select(User.display_name)
    )).scalars().all()
    _used_names.update(existing_names)
    existing_student_names = (await db.execute(
        select(Student.name).where(Student.school_id == school_id)
    )).scalars().all()
    _used_names.update(existing_student_names)

    # 组合→班级映射
    g11_class_combos = _build_combo_class_map(G11_COMBO_PLAN)  # {1: "物化生", ...}
    g12_class_combos = _build_combo_class_map(G12_COMBO_PLAN)

    stats = {
        "classes_added": 0, "students_added": 0, "students_topup": 0,
        "teachers_added": 0, "selections_added": 0, "assignments_added": 0,
    }

    # ── 1. 加载现有高中班级 ──
    existing_classes = (await db.execute(
        select(Class).where(
            Class.school_id == school_id,
            Class.grade.in_(["高一", "高二", "高三"])
        )
    )).scalars().all()

    # 按年级+班号索引
    grade_classes: dict[int, dict[int, Class]] = {10: {}, 11: {}, 12: {}}
    grade_name_to_num = {"高一": 10, "高二": 11, "高三": 12}
    for cls in existing_classes:
        gnum = grade_name_to_num[cls.grade]
        # 从班名提取班号: "高一6班" → 6, "高二12班" → 12
        name_without_grade = cls.name.replace(cls.grade, "").replace("班", "")
        class_num = int(name_without_grade)
        grade_classes[gnum][class_num] = cls

    # ── 2. 补充班级到每年级 12 个 ──
    grade_names = {10: "高一", 11: "高二", 12: "高三"}
    for gnum in [10, 11, 12]:
        for cnum in range(1, 13):
            if cnum not in grade_classes[gnum]:
                cls = Class(
                    name=f"{grade_names[gnum]}{cnum}班",
                    grade=grade_names[gnum],
                    grade_number=gnum,
                    school_id=school_id,
                )
                db.add(cls)
                grade_classes[gnum][cnum] = cls
                stats["classes_added"] += 1

    await db.flush()
    logger.info("Added %d classes", stats["classes_added"])

    # ── 3. 补充学生 ──
    for gnum in [10, 11, 12]:
        enrollment_year = 2026 - (gnum - 9)  # 高一=2024, 高二=2023, 高三=2022...
        # 实际: 高一入学2025, 高二入学2024, 高三入学2023
        # grade_num 10 → 2026-(10-9)=2025, 11→2024, 12→2023 ✓

        for cnum in range(1, 13):
            cls = grade_classes[gnum][cnum]
            # 查当前学生数
            current_count_result = await db.execute(
                select(func.count()).where(Student.class_id == cls.id)
            )
            current_count = current_count_result.scalar()
            needed = TARGET_PER_CLASS - current_count

            if needed <= 0:
                continue

            for seq in range(current_count + 1, current_count + needed + 1):
                gender = "M" if random.random() < 0.51 else "F"
                # 学号: G{grade:02d}{class:02d}{seq:03d}
                snum = f"G{gnum:02d}{cnum:02d}{seq:03d}"
                student = Student(
                    name=_gen_name(gender),
                    student_number=snum,
                    class_id=cls.id,
                    school_id=school_id,
                    grade=grade_names[gnum],
                    gender=gender,
                    enrollment_year=enrollment_year,
                    status="active",
                )
                db.add(student)

                if current_count < 40:
                    stats["students_added"] += 1
                else:
                    stats["students_topup"] += 1

    await db.flush()
    logger.info("Added %d students (+%d topup)", stats["students_added"], stats["students_topup"])

    # ── 4. 创建选科组合 (SubjectSelection) ──
    for combo_name, subjects in COMBO_SUBJECTS.items():
        # 检查高二是否用到此组合
        in_g11 = combo_name in [c[0] for c in G11_COMBO_PLAN]
        in_g12 = combo_name in [c[0] for c in G12_COMBO_PLAN]

        if in_g11:
            sel = SubjectSelection(
                school_id=school_id,
                name=f"高二{combo_name}",
                subject_codes=subjects,
                mode="3+1+2",
                is_active=True,
            )
            db.add(sel)
            stats["selections_added"] += 1

        if in_g12:
            sel = SubjectSelection(
                school_id=school_id,
                name=f"高三{combo_name}",
                subject_codes=subjects,
                mode="3+1+2",
                is_active=True,
            )
            db.add(sel)
            stats["selections_added"] += 1

    await db.flush()
    logger.info("Added %d subject selections", stats["selections_added"])

    # ── 5. 补充教师 ──
    # 5a. 查现有教师（按科目）
    existing_teachers: dict[str, list[str]] = {}  # {subject_code: [user_id, ...]}
    rows = (await db.execute(text("""
        SELECT ur.user_id, ur.subject_codes FROM user_roles ur
        WHERE ur.school_id = :school_id AND ur.role = 'subject_teacher'
        AND ur.subject_codes IS NOT NULL
    """), {"school_id": school_id})).all()
    for user_id, subj_json in rows:
        # subject_codes 存为 JSON 数组字符串，如 '["YW"]'
        codes = json.loads(subj_json) if isinstance(subj_json, str) else subj_json
        for code in codes:
            existing_teachers.setdefault(code, []).append(user_id)

    # 5b. 识别高中教师（class_ids 含高中班级的）
    hs_class_ids = set()
    for gnum in [10, 11, 12]:
        for cls in grade_classes[gnum].values():
            hs_class_ids.add(cls.id)

    hs_teachers_by_subject: dict[str, list[str]] = {}  # 高中教师
    for user_id, subj_json in rows:
        codes = json.loads(subj_json) if isinstance(subj_json, str) else subj_json
        # 查该教师的 class_ids
        role_row = (await db.execute(text("""
            SELECT class_ids FROM user_roles
            WHERE user_id = :user_id AND role = 'subject_teacher'
            AND school_id = :school_id LIMIT 1
        """), {"user_id": user_id, "school_id": school_id})).first()
        if role_row and role_row[0]:
            cids = json.loads(role_row[0]) if isinstance(role_row[0], str) else role_row[0]
            if any(cid in hs_class_ids for cid in (cids or [])):
                for code in codes:
                    hs_teachers_by_subject.setdefault(code, []).append(user_id)

    # 5c. 计算需要新增的教师
    max_teacher_idx_result = await db.execute(text(
        "SELECT MAX(CAST(SUBSTR(username, -3) AS INTEGER)) FROM users WHERE username LIKE 't_%'"
    ))
    max_idx = max_teacher_idx_result.scalar() or 149
    teacher_idx = max_idx

    new_hs_teachers: dict[str, list[str]] = {}  # 新增的高中教师 {subject: [user_id]}

    for subj_code, target in HS_TEACHER_TARGET.items():
        current = len(hs_teachers_by_subject.get(subj_code, []))
        needed = target - current
        if needed <= 0:
            new_hs_teachers[subj_code] = []
            continue

        new_ids = []
        for _ in range(needed):
            teacher_idx += 1
            gender = random.choice(["M", "F"])
            user = User(
                username=f"t_{subj_code.lower()}_{teacher_idx:03d}",
                display_name=_gen_name(gender),
            )
            user.set_password(settings.SEED_DEFAULT_PASSWORD)
            db.add(user)
            await db.flush()

            role = UserRole(
                user_id=user.id,
                role="subject_teacher",
                school_id=school_id,
                subject_codes=[subj_code],
                is_primary=True,
            )
            db.add(role)
            new_ids.append(user.id)
            stats["teachers_added"] += 1

        new_hs_teachers[subj_code] = new_ids

    await db.flush()
    logger.info("Added %d teachers", stats["teachers_added"])

    # ── 6. 创建排课 (TeacherAssignment) ──
    # 合并现有高中教师 + 新教师
    all_hs_teachers: dict[str, list[str]] = {}
    for subj_code in HS_TEACHER_TARGET:
        existing = hs_teachers_by_subject.get(subj_code, [])
        new = new_hs_teachers.get(subj_code, [])
        all_hs_teachers[subj_code] = existing + new

    # 为每个科目分配教师到班级
    for subj_code, teacher_ids in all_hs_teachers.items():
        if not teacher_ids:
            continue

        # 收集该科目需要覆盖的班级
        target_classes: list[tuple[int, int, str]] = []  # (grade_num, class_num, class_id)
        for gnum in [10, 11, 12]:
            for cnum in range(1, 13):
                cls = grade_classes[gnum][cnum]
                subjects = _get_class_subjects(gnum, cnum, g11_class_combos, g12_class_combos)
                if subj_code in subjects:
                    target_classes.append((gnum, cnum, cls.id))

        if not target_classes:
            continue

        # 均匀分配
        n_teachers = len(teacher_ids)
        for i, (gnum, cnum, class_id) in enumerate(target_classes):
            teacher_id = teacher_ids[i % n_teachers]
            assignment = TeacherAssignment(
                user_id=teacher_id,
                class_id=class_id,
                subject_code=subj_code,
                semester=SEMESTER,
                school_id=school_id,
                is_active=True,
            )
            db.add(assignment)
            stats["assignments_added"] += 1

    await db.flush()
    logger.info("Created %d teacher assignments", stats["assignments_added"])

    # ── 7. 补充班主任到新班级 ──
    # 从主科教师中选班主任
    all_main_teachers = (
        all_hs_teachers.get("YW", []) +
        all_hs_teachers.get("SX", []) +
        all_hs_teachers.get("YY", [])
    )
    random.shuffle(all_main_teachers)
    hr_idx = 0

    for gnum in [10, 11, 12]:
        for cnum in range(1, 13):
            cls = grade_classes[gnum][cnum]
            if cls.head_teacher_id is None and hr_idx < len(all_main_teachers):
                cls.head_teacher_id = all_main_teachers[hr_idx]
                # 添加 homeroom_teacher 角色（如果没有）
                existing_hr = (await db.execute(
                    select(UserRole).where(
                        UserRole.user_id == all_main_teachers[hr_idx],
                        UserRole.role == "homeroom_teacher",
                        UserRole.school_id == school_id,
                    )
                )).scalar_one_or_none()
                if not existing_hr:
                    hr_role = UserRole(
                        user_id=all_main_teachers[hr_idx],
                        role="homeroom_teacher",
                        school_id=school_id,
                        class_ids=[cls.id],
                        is_primary=False,
                    )
                    db.add(hr_role)
                hr_idx += 1

    # ── 8. 更新现有教师 UserRole 的 class_ids（包含新班级） ──
    for subj_code, teacher_ids in all_hs_teachers.items():
        if not teacher_ids:
            continue
        target_classes_for_subj = []
        for gnum in [10, 11, 12]:
            for cnum in range(1, 13):
                cls = grade_classes[gnum][cnum]
                subjects = _get_class_subjects(gnum, cnum, g11_class_combos, g12_class_combos)
                if subj_code in subjects:
                    target_classes_for_subj.append(cls.id)

        n_teachers = len(teacher_ids)
        # 按 teacher 分组 class_ids
        teacher_class_groups: dict[str, list[str]] = {}
        for i, class_id in enumerate(target_classes_for_subj):
            tid = teacher_ids[i % n_teachers]
            teacher_class_groups.setdefault(tid, []).append(class_id)

        for tid, cids in teacher_class_groups.items():
            role = (await db.execute(
                select(UserRole).where(
                    UserRole.user_id == tid,
                    UserRole.role == "subject_teacher",
                    UserRole.school_id == school_id,
                )
            )).scalar_one_or_none()
            if role:
                role.class_ids = cids

    await db.commit()

    # ── 统计验证 ──
    total_hs_students = (await db.execute(text("""
        SELECT COUNT(*) FROM students
        WHERE school_id = :school_id AND grade IN ('高一','高二','高三')
    """), {"school_id": school_id})).scalar()

    total_hs_classes = (await db.execute(text("""
        SELECT COUNT(*) FROM classes
        WHERE school_id = :school_id AND grade IN ('高一','高二','高三')
    """), {"school_id": school_id})).scalar()

    total_assignments = (await db.execute(text("""
        SELECT COUNT(*) FROM teacher_assignments
        WHERE school_id = :school_id
    """), {"school_id": school_id})).scalar()

    total_selections = (await db.execute(text("""
        SELECT COUNT(*) FROM subject_selections
        WHERE school_id = :school_id
    """), {"school_id": school_id})).scalar()

    stats.update({
        "total_hs_classes": total_hs_classes,
        "total_hs_students": total_hs_students,
        "total_assignments": total_assignments,
        "total_selections": total_selections,
    })
    return {"status": "seeded", **stats}


# ─── CLI 入口 ────────────────────────────────────────────────────────────

async def main():
    import os
    import sys
    src_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    sys.path.insert(0, os.path.abspath(src_dir))

    from edu_cloud.config import settings
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    if "sqlite" not in settings.DATABASE_URL:
        print("WARNING: 非 SQLite 环境请使用 scripts/db_migrate 管理 schema", file=sys.stderr)
    if "sqlite" in settings.DATABASE_URL:
        from edu_cloud.models.base import Base
        import edu_cloud.models.school  # noqa
        import edu_cloud.models.user  # noqa
        import edu_cloud.models.user_role  # noqa
        import edu_cloud.models.teacher_assignment  # noqa
        import edu_cloud.models.subject_selection  # noqa
        import edu_cloud.modules.student.models  # noqa
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        result = await seed_highschool_supplement(session)
        print(f"\n{'=' * 60}")
        print("  高中部数据补充结果")
        print(f"{'=' * 60}")
        for k, v in result.items():
            print(f"  {k}: {v}")
        print(f"{'=' * 60}\n")

    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(main())
