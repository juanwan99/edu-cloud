"""L1 校本分析工具 — 4 个核心工具，注册到全局 registry。"""
import statistics
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.registry import tools
from edu_cloud.models.exam import Exam, ExamResult
from edu_cloud.models.student import Student
from edu_cloud.models.class_group import ClassGroup

logger = logging.getLogger(__name__)


def _compute_stats(scores: list[float]) -> dict:
    """计算 count/avg/max/min/median 统计。"""
    if not scores:
        return {"count": 0, "avg": None, "max": None, "min": None, "median": None}
    return {
        "count": len(scores),
        "avg": round(sum(scores) / len(scores), 2),
        "max": round(max(scores), 2),
        "min": round(min(scores), 2),
        "median": round(statistics.median(scores), 2),
    }


@tools.register(
    name="get_exam_scores",
    description="获取指定考试的学生成绩列表（含班级信息），按总分降序排列，附整体统计数据。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
    },
    category="L1_analytics",
)
async def get_exam_scores(
    exam_id: str,
    _db: AsyncSession = None,
    _school_id: str = None,
    _class_ids: list[str] | None = None,
) -> dict[str, Any]:
    """返回考试的逐学生成绩列表 + 整体统计。支持按班级过滤（_class_ids）。"""
    if _db is None:
        return {"error": "no database session"}

    # 构建查询：ExamResult join Student
    stmt = (
        select(ExamResult, Student)
        .join(Student, ExamResult.student_id == Student.id)
        .where(ExamResult.exam_id == exam_id)
    )
    if _school_id:
        stmt = stmt.where(ExamResult.school_id == _school_id)
    if _class_ids:
        stmt = stmt.where(Student.class_id.in_(_class_ids))

    rows = (await _db.execute(stmt)).all()

    students_data = []
    scores = []
    for result, student in rows:
        students_data.append({
            "student_id": student.id,
            "name": student.name,
            "student_number": student.student_number,
            "class_id": student.class_id,
            "grade": student.grade,
            "total_score": result.total_score,
        })
        scores.append(result.total_score)

    # 按总分降序排列，并附加名次
    students_data.sort(key=lambda x: x["total_score"], reverse=True)
    for rank, s in enumerate(students_data, start=1):
        s["rank"] = rank

    return {
        "exam_id": exam_id,
        "students": students_data,
        "stats": _compute_stats(scores),
    }


@tools.register(
    name="get_class_stats",
    description="获取指定班级在某场考试中的成绩统计（均值/最高/最低/中位数/人数）。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "class_id": {"type": "string", "description": "班级 ID"},
        },
        "required": ["exam_id", "class_id"],
    },
    category="L1_analytics",
)
async def get_class_stats(
    exam_id: str,
    class_id: str,
    _db: AsyncSession = None,
    _school_id: str = None,
    _class_ids: list[str] | None = None,
) -> dict[str, Any]:
    """返回指定班级的成绩聚合统计。"""
    if _db is None:
        return {"error": "no database session"}

    # Scope enforcement: restrict to caller's classes
    if _class_ids is not None and class_id not in _class_ids:
        return {"error": "无权访问此班级数据"}

    stmt = (
        select(ExamResult.total_score)
        .join(Student, ExamResult.student_id == Student.id)
        .where(ExamResult.exam_id == exam_id)
        .where(Student.class_id == class_id)
    )
    if _school_id:
        stmt = stmt.where(ExamResult.school_id == _school_id)

    rows = (await _db.execute(stmt)).scalars().all()
    scores = list(rows)

    # 查询班级名称
    class_name = None
    cls_row = (await _db.execute(select(ClassGroup).where(ClassGroup.id == class_id))).scalar_one_or_none()
    if cls_row:
        class_name = cls_row.name

    stats = _compute_stats(scores)
    return {
        "exam_id": exam_id,
        "class_id": class_id,
        "class_name": class_name,
        **stats,
    }


@tools.register(
    name="compare_classes",
    description="对比多个班级在同一场考试中的成绩（均值/最高/最低/人数），用于横向比较。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
    },
    category="L1_analytics",
)
async def compare_classes(
    exam_id: str,
    _db: AsyncSession = None,
    _school_id: str = None,
    _class_ids: list[str] | None = None,
) -> dict[str, Any]:
    """返回各班级的成绩对比（按均值降序）。"""
    if _db is None:
        return {"error": "no database session"}

    # 获取所有参与该考试的学生成绩 + 班级信息
    stmt = (
        select(ExamResult.total_score, Student.class_id)
        .join(Student, ExamResult.student_id == Student.id)
        .where(ExamResult.exam_id == exam_id)
    )
    if _school_id:
        stmt = stmt.where(ExamResult.school_id == _school_id)
    if _class_ids:
        stmt = stmt.where(Student.class_id.in_(_class_ids))

    rows = (await _db.execute(stmt)).all()

    # 按班级分组
    class_scores: dict[str, list[float]] = {}
    for total_score, class_id in rows:
        if class_id not in class_scores:
            class_scores[class_id] = []
        class_scores[class_id].append(total_score)

    # 查询班级名称
    class_names: dict[str, str] = {}
    if class_scores:
        cls_rows = (await _db.execute(
            select(ClassGroup).where(ClassGroup.id.in_(list(class_scores.keys())))
        )).scalars().all()
        for cls in cls_rows:
            class_names[cls.id] = cls.name

    # 构建结果
    classes_data = []
    for class_id, scores in class_scores.items():
        stats = _compute_stats(scores)
        classes_data.append({
            "class_id": class_id,
            "class_name": class_names.get(class_id),
            **stats,
        })

    # 按均值降序
    classes_data.sort(key=lambda x: (x["avg"] or 0), reverse=True)
    for rank, c in enumerate(classes_data, start=1):
        c["rank"] = rank

    return {
        "exam_id": exam_id,
        "classes": classes_data,
    }


@tools.register(
    name="get_student_profile",
    description="查询学生的基本信息及历次考试成绩记录（按时间排序）。",
    parameters={
        "type": "object",
        "properties": {
            "student_number": {"type": "string", "description": "学生学号"},
        },
        "required": ["student_number"],
    },
    category="L1_analytics",
)
async def get_student_profile(
    student_number: str,
    _db: AsyncSession = None,
    _school_id: str = None,
    _class_ids: list[str] | None = None,
) -> dict[str, Any]:
    """返回学生基本信息及历次考试成绩。"""
    if _db is None:
        return {"error": "no database session"}

    # 查找学生
    stmt = select(Student).where(Student.student_number == student_number)
    if _school_id:
        stmt = stmt.where(Student.school_id == _school_id)

    student = (await _db.execute(stmt)).scalar_one_or_none()
    if student is None:
        return {"error": f"学生 {student_number!r} 不存在"}

    # Scope enforcement: restrict to caller's classes
    if _class_ids is not None and student.class_id not in _class_ids:
        return {"error": "无权访问此学生数据"}

    # 查询该学生的所有考试成绩（join Exam 取考试名称）
    results_stmt = (
        select(ExamResult, Exam)
        .join(Exam, ExamResult.exam_id == Exam.id)
        .where(ExamResult.student_id == student.id)
        .order_by(Exam.created_at)
    )
    rows = (await _db.execute(results_stmt)).all()

    exams = []
    for result, exam in rows:
        exams.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "subject_code": exam.subject_code,
            "subject_name": exam.subject_name,
            "total_score": result.total_score,
            "max_score": exam.max_score,
            "semester": exam.semester,
        })

    # 查询班级名称
    class_name = None
    if student.class_id:
        cls = (await _db.execute(
            select(ClassGroup).where(ClassGroup.id == student.class_id)
        )).scalar_one_or_none()
        if cls:
            class_name = cls.name

    return {
        "student_id": student.id,
        "name": student.name,
        "student_number": student.student_number,
        "grade": student.grade,
        "class_id": student.class_id,
        "class_name": class_name,
        "gender": student.gender,
        "exams": exams,
    }
