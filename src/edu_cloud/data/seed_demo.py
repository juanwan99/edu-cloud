"""演示数据生成 — 为 AI Agent 测试提供有意义的分析数据。

生成内容：
1. 2 次考试（期中+月考），各 3 科（语/数/英），考试 status=completed
1b. 1 次草稿考试（期末），3 科，status=draft，用于答题卡制作测试
2. 数学 10 道题 + 英语 10 道题（语文已有 22 道）
3. 160 名学生的完整答题数据（分数按正态分布 + 班级差异）
4. 知识点标注（数学题关联知识点树）
5. 运行 data_pipeline 生成题库+错题本+画像

调用方式：POST /api/pipeline/seed-demo
幂等：检查标记考试是否已存在。

Migrated from exam-ai (Task 22).
"""
import logging
import random
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Student
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.conduct.models import StudentProfile
from edu_cloud.modules.conduct.crypto import encrypt

logger = logging.getLogger(__name__)

# 数学题目定义：(题号, 题型, 满分, 正确答案(选择题), 知识点code)
MATH_QUESTIONS = [
    ("1", "choice", 5, "B", "MATH_FUNC_CONCEPT_DOMAIN"),
    ("2", "choice", 5, "A", "MATH_FUNC_CONCEPT_MONO"),
    ("3", "choice", 5, "C", "MATH_TRIG_DEF"),
    ("4", "choice", 5, "D", "MATH_SEQ_ARITH"),
    ("5", "choice", 5, "A", "MATH_GEOM_ANALYTIC_LINE"),
    ("6", "essay", 12, None, "MATH_FUNC_DERIV_APP"),
    ("7", "essay", 12, None, "MATH_TRIG_SINE_RULE"),
    ("8", "essay", 14, None, "MATH_GEOM_ANALYTIC_ELLIPSE"),
    ("9", "essay", 14, None, "MATH_PROB_DIST"),
    ("10", "essay", 18, None, "MATH_FUNC_DERIV_APP"),
]

ENGLISH_QUESTIONS = [
    ("1", "choice", 3, "B", None),
    ("2", "choice", 3, "A", None),
    ("3", "choice", 3, "C", None),
    ("4", "choice", 3, "D", None),
    ("5", "choice", 3, "B", None),
    ("6", "choice", 3, "A", None),
    ("7", "choice", 3, "C", None),
    ("8", "essay", 15, None, None),
    ("9", "essay", 20, None, None),
    ("10", "essay", 25, None, None),
]

# 班级成绩特征（均值偏移，模拟不同班级水平差异）
CLASS_PROFILES = {
    0: {"name": "高二(1)班", "mean_shift": 0.05, "desc": "优秀班"},
    1: {"name": "高二(2)班", "mean_shift": 0.0, "desc": "普通班"},
    2: {"name": "高二(3)班", "mean_shift": -0.08, "desc": "薄弱班"},
    3: {"name": "高二(4)班", "mean_shift": 0.02, "desc": "普通班"},
}


def _generate_score(max_score: float, question_type: str, base_rate: float) -> float:
    """生成一个学生某题的得分。"""
    if question_type == "choice":
        # 选择题：全对或全错
        return max_score if random.random() < base_rate else 0.0
    else:
        # 主观题：正态分布
        rate = max(0, min(1, random.gauss(base_rate, 0.2)))
        score = round(rate * max_score, 1)
        return max(0.0, min(max_score, score))


def _student_base_rate(student_idx: int, class_idx: int) -> float:
    """学生基础得分率（0-1），受班级和个体差异影响。"""
    profile = CLASS_PROFILES.get(class_idx, {"mean_shift": 0.0})
    class_shift = profile["mean_shift"]
    # 个体差异：每个学生有一个固定的能力值
    individual = random.gauss(0.65, 0.15) + class_shift
    return max(0.15, min(0.95, individual))


async def _seed_draft_exam(db: AsyncSession, school) -> bool:
    """创建一个 draft 状态考试，用于答题卡制作测试。幂等。"""
    draft_exam_name = "2026年春季期末考试"
    existing = await db.execute(
        select(Exam).where(Exam.name == draft_exam_name, Exam.school_id == school.id)
    )
    if existing.scalar_one_or_none():
        return False

    draft_exam = Exam(
        name=draft_exam_name, card_title=draft_exam_name,
        school_id=school.id, status="draft",
        exam_type="期末", semester="2025-2026-2",
        grade_scope="高二",
    )
    db.add(draft_exam)
    await db.flush()

    draft_subjects = [
        ("YW", "语文", [
            ("1", "choice", 3, "A"), ("2", "choice", 3, "B"),
            ("3", "choice", 3, "C"), ("4", "choice", 3, "D"),
            ("5", "choice", 3, "A"), ("6", "choice", 3, "B"),
            ("7", "choice", 3, "C"), ("8", "choice", 3, "D"),
            ("9", "essay", 6, None), ("10", "essay", 6, None),
            ("11", "essay", 6, None),
            ("12", "essay", 15, None), ("13", "essay", 15, None),
            ("14", "essay", 15, None),
            ("15", "essay", 10, None), ("16", "essay", 10, None),
            ("17", "essay", 10, None), ("18", "essay", 60, None),
        ]),
        ("SX", "数学", [
            ("1", "choice", 5, "B"), ("2", "choice", 5, "A"),
            ("3", "choice", 5, "C"), ("4", "choice", 5, "D"),
            ("5", "choice", 5, "A"), ("6", "choice", 5, "B"),
            ("7", "choice", 5, "C"), ("8", "choice", 5, "D"),
            ("9", "essay", 12, None), ("10", "essay", 12, None),
            ("11", "essay", 12, None), ("12", "essay", 14, None),
            ("13", "essay", 14, None), ("14", "essay", 18, None),
        ]),
        ("YY", "英语", [
            ("1", "choice", 3, "B"), ("2", "choice", 3, "A"),
            ("3", "choice", 3, "C"), ("4", "choice", 3, "D"),
            ("5", "choice", 3, "B"), ("6", "choice", 3, "A"),
            ("7", "choice", 3, "C"),
            ("8", "essay", 15, None), ("9", "essay", 20, None),
            ("10", "essay", 25, None),
        ]),
    ]

    for subj_code, subj_name, questions_def in draft_subjects:
        subj = Subject(
            exam_id=draft_exam.id, name=subj_name, code=subj_code,
            school_id=school.id,
        )
        db.add(subj)
        await db.flush()
        for qname, qtype, max_score, correct in questions_def:
            db.add(Question(
                subject_id=subj.id, school_id=school.id,
                name=qname, question_type=qtype,
                max_score=max_score, correct_answer=correct,
            ))
        await db.flush()

    await db.commit()
    logger.info("seed: draft exam '%s' created for card editor testing", draft_exam_name)
    return True


async def seed_demo_data(db: AsyncSession, school_code: str = "TEST01") -> dict:
    """生成完整演示数据。返回统计信息。"""
    # 获取学校（draft 考试和完整 seed 都需要）
    school_result = await db.execute(select(School).where(School.code == school_code))
    school = school_result.scalar_one_or_none()
    if not school:
        return {"status": "error", "message": f"学校 {school_code} 不存在"}

    # === 草稿考试（独立于完整 seed 的幂等检查）===
    await _seed_draft_exam(db, school)

    # 检查是否已有第二次考试（幂等标记）
    result = await db.execute(select(Exam).where(Exam.name == "2026年春季月考"))
    if result.scalar_one_or_none():
        return {"status": "already_seeded", "message": "演示数据已存在"}

    # 获取学生
    students_result = await db.execute(
        select(Student).where(Student.school_id == school.id).order_by(Student.student_number)
    )
    students = list(students_result.scalars().all())
    if len(students) < 40:
        return {"status": "error", "message": f"学生数量不足（{len(students)}），需至少 40 名"}

    # 按班级分组
    from collections import defaultdict
    class_students = defaultdict(list)
    class_id_to_idx = {}
    for s in students:
        if s.class_id not in class_id_to_idx:
            class_id_to_idx[s.class_id] = len(class_id_to_idx)
        class_students[s.class_id].append(s)

    # === StudentProfile seed (幂等) ===
    # 为每个学生创建 StudentProfile，设置 verify_code 为学号后 6 位（AES-256-GCM 加密）
    profile_created = 0
    existing_profile_ids = set()
    existing_profiles = await db.execute(
        select(StudentProfile.student_id).where(
            StudentProfile.student_id.in_([s.id for s in students])
        )
    )
    for row in existing_profiles.scalars().all():
        existing_profile_ids.add(row)

    for student in students:
        if student.id in existing_profile_ids:
            continue
        # verify_code = 学号后 6 位，不足 6 位则用全部学号
        raw_code = (student.student_number or "123456")[-6:]
        db.add(StudentProfile(
            student_id=student.id,
            verify_code=encrypt(raw_code),
        ))
        profile_created += 1

    if profile_created > 0:
        await db.flush()
        logger.info("seed: created %d student profiles (verify_code = last 6 of student_number)", profile_created)

    # === 知识图谱节点 code → id 映射（数学概念）===
    kp_result = await db.execute(
        select(ConceptGraphNode).where(
            ConceptGraphNode.course_code == "SW",
            ConceptGraphNode.node_type == "concept",
        )
    )
    kp_map = {kp.id: kp.id for kp in kp_result.scalars().all()}
    # Also build a map by name/code for MATH_QUESTIONS kp_code strings
    kp_by_code_result = await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.node_type == "concept")
    )
    kp_code_map = {kp.id: kp.id for kp in kp_by_code_result.scalars().all()}

    stats = {"exams": [], "total_answers": 0}

    # === 两次考试 ===
    exams_config = [
        {"name": "2026年春季期中考试", "exam_type": "期中", "semester": "2025-2026-2"},
        {"name": "2026年春季月考", "exam_type": "月考", "semester": "2025-2026-2"},
    ]

    for exam_cfg in exams_config:
        # 检查考试是否已存在
        existing_exam = await db.execute(
            select(Exam).where(Exam.name == exam_cfg["name"], Exam.school_id == school.id)
        )
        exam = existing_exam.scalar_one_or_none()
        if exam and exam.status == "completed":
            stats["exams"].append({"name": exam_cfg["name"], "status": "already_exists"})
            continue

        if not exam:
            exam = Exam(
                name=exam_cfg["name"], card_title=exam_cfg["name"],
                school_id=school.id, status="completed",
                exam_type=exam_cfg["exam_type"], semester=exam_cfg["semester"],
                grade_scope="高二",
            )
            db.add(exam)
            await db.flush()

        exam_answers = 0

        # 3 个科目
        subjects_config = [
            ("YW", "语文", None),  # 语文题目已在 app.py seed 中创建，只为期中考试创建
            ("SX", "数学", MATH_QUESTIONS),
            ("YY", "英语", ENGLISH_QUESTIONS),
        ]

        for subj_code, subj_name, questions_def in subjects_config:
            # 创建 Subject
            subj = Subject(
                exam_id=exam.id, name=subj_name, code=subj_code, school_id=school.id,
            )
            db.add(subj)
            await db.flush()

            # 创建题目（如果有定义）
            questions = []
            if questions_def:
                for qname, qtype, max_score, correct, kp_code in questions_def:
                    q = Question(
                        subject_id=subj.id, school_id=school.id,
                        name=qname, question_type=qtype,
                        max_score=max_score, correct_answer=correct,
                    )
                    db.add(q)
                    await db.flush()
                    questions.append(q)

                    # 关联知识点（concept_id = ConceptGraphNode.id 语义 string）
                    if kp_code and kp_code in kp_code_map:
                        db.add(QuestionKnowledgePoint(
                            question_id=q.id,
                            concept_id=kp_code_map[kp_code],
                            is_primary=True,
                        ))
            elif subj_code == "YW":
                # 语文：创建简化题目（不复用 app.py 的，避免跨考试 Subject）
                yw_simple = [
                    ("1", "choice", 3, "A"), ("2", "choice", 3, "B"),
                    ("3", "choice", 3, "C"), ("4", "choice", 3, "D"),
                    ("5", "choice", 3, "A"),
                    ("6", "essay", 8, None), ("7", "essay", 10, None),
                    ("8", "essay", 15, None), ("9", "essay", 20, None),
                    ("10", "essay", 60, None),
                ]
                for qname, qtype, max_score, correct in yw_simple:
                    q = Question(
                        subject_id=subj.id, school_id=school.id,
                        name=qname, question_type=qtype,
                        max_score=max_score, correct_answer=correct,
                    )
                    db.add(q)
                    questions.append(q)
                await db.flush()

            if not questions:
                continue

            # 为每个学生生成答题数据
            random.seed(42 + hash(exam_cfg["name"] + subj_code))  # 可复现
            for class_id, class_studs in class_students.items():
                class_idx = class_id_to_idx[class_id]
                for student in class_studs:
                    base_rate = _student_base_rate(
                        students.index(student), class_idx,
                    )
                    # 不同科目有不同的能力偏差
                    subject_rate = base_rate + random.gauss(0, 0.05)

                    for q in questions:
                        score = _generate_score(q.max_score, q.question_type, subject_rate)
                        detected = None
                        if q.question_type == "choice" and q.correct_answer:
                            if score > 0:
                                detected = q.correct_answer
                            else:
                                wrong_options = [x for x in "ABCD" if x != q.correct_answer]
                                detected = random.choice(wrong_options)

                        sa = StudentAnswer(
                            exam_id=exam.id, subject_id=subj.id,
                            student_id=student.id, question_id=q.id,
                            school_id=school.id, score=score,
                            detected_answer=detected,
                        )
                        db.add(sa)
                        exam_answers += 1

            await db.flush()

        await db.commit()
        stats["exams"].append({"name": exam_cfg["name"], "answers": exam_answers})
        stats["total_answers"] += exam_answers

    # === 运行 data pipeline ===
    from edu_cloud.services.post_exam_pipeline import run_post_exam_pipeline
    pipeline_results = {}
    for exam_cfg in exams_config:
        exam_result = await db.execute(
            select(Exam).where(Exam.name == exam_cfg["name"], Exam.school_id == school.id)
        )
        exam = exam_result.scalar_one_or_none()
        if exam:
            pr = await run_post_exam_pipeline(db, exam_id=exam.id, school_id=school.id)
            pipeline_results[exam_cfg["name"]] = pr

    stats["pipeline"] = pipeline_results

    # ── Academic: Semesters + Periods ──────────────────────────────
    from edu_cloud.modules.academic.models import Semester, TimePeriod
    from datetime import time as time_type

    sem1 = Semester(
        school_id=school.id, name="2025-2026学年第一学期",
        school_year="2025-2026", term=1,
        start_date=date(2025, 9, 1), end_date=date(2026, 1, 15),
        is_current=True,
    )
    sem2 = Semester(
        school_id=school.id, name="2025-2026学年第二学期",
        school_year="2025-2026", term=2,
        start_date=date(2026, 2, 17), end_date=date(2026, 7, 10),
    )
    db.add_all([sem1, sem2])
    await db.flush()

    period_defs = [
        (1, "第一节", "08:00", "08:45", "class"),
        (2, "第二节", "08:55", "09:40", "class"),
        (3, "第三节", "10:00", "10:45", "class"),
        (4, "第四节", "10:55", "11:40", "class"),
        (5, "第五节", "14:00", "14:45", "class"),
        (6, "第六节", "14:55", "15:40", "class"),
        (7, "第七节", "16:00", "16:45", "class"),
        (8, "晚自习一", "19:00", "19:45", "self_study"),
        (9, "晚自习二", "19:55", "20:40", "self_study"),
    ]
    for num, name, st, et, ptype in period_defs:
        db.add(TimePeriod(
            school_id=school.id, semester_id=sem1.id,
            period_number=num, name=name,
            start_time=time_type.fromisoformat(st),
            end_time=time_type.fromisoformat(et),
            period_type=ptype,
        ))
    await db.flush()
    logger.info("Academic seed: 2 semesters + 9 periods created")

    return stats
