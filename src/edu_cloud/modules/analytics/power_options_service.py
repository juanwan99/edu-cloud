"""PowerOptions 级联筛选服务 — 构建 年级→班级→科目→考试 级联树。"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select, func, distinct, extract
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.services.analytics_workflow import Exam, ExamResult, Subject
from edu_cloud.services.analytics_workflow import Class, Student


async def get_power_options(
    db: AsyncSession,
    school_id: str,
    visible_class_ids: list[str] | None = None,
    visible_subject_codes: list[str] | None = None,
    exam_type: str | None = None,
    year: int | None = None,
) -> dict:
    stmt = (
        select(
            Class.grade,
            Class.id.label("class_id"),
            Class.name.label("class_name"),
            Subject.id.label("subject_id"),
            Subject.code.label("subject_code"),
            Subject.name.label("subject_name"),
            Exam.id.label("exam_id"),
            Exam.name.label("exam_name"),
            Exam.exam_date.label("exam_date"),
            func.count(distinct(ExamResult.student_id)).label("student_count"),
        )
        .select_from(Exam)
        .join(Subject, Subject.exam_id == Exam.id)
        .join(ExamResult, ExamResult.exam_id == Exam.id)
        .join(Student, Student.id == ExamResult.student_id)
        .join(Class, Class.id == Student.class_id)
        .where(Exam.school_id == school_id)
        .where(Exam.status == "completed")
        .group_by(
            Class.grade, Class.id, Class.name,
            Subject.id, Subject.code, Subject.name,
            Exam.id, Exam.name, Exam.exam_date,
        )
        .order_by(Class.grade, Class.name, Subject.name, Exam.exam_date.desc())
    )

    if visible_class_ids is not None:
        stmt = stmt.where(Class.id.in_(visible_class_ids))
    if visible_subject_codes is not None:
        stmt = stmt.where(Subject.code.in_(visible_subject_codes))
    if exam_type:
        stmt = stmt.where(Exam.exam_type == exam_type)
    if year:
        stmt = stmt.where(extract("year", Exam.exam_date) == year)

    rows = (await db.execute(stmt)).all()

    return _build_tree(rows)


def _build_tree(rows) -> dict:
    grade_map: dict[str, dict] = {}

    for row in rows:
        grade_name = row.grade
        if grade_name not in grade_map:
            grade_map[grade_name] = {}

        class_id = row.class_id
        if class_id not in grade_map[grade_name]:
            grade_map[grade_name][class_id] = {
                "id": class_id,
                "name": row.class_name,
                "subjects": {},
            }

        cls = grade_map[grade_name][class_id]
        subj_id = row.subject_id
        if subj_id not in cls["subjects"]:
            cls["subjects"][subj_id] = {
                "id": subj_id,
                "code": row.subject_code,
                "name": row.subject_name,
                "exams": [],
            }

        cls["subjects"][subj_id]["exams"].append({
            "id": row.exam_id,
            "exam_id": row.exam_id,
            "subject_id": subj_id,
            "name": row.exam_name,
            "exam_date": row.exam_date.isoformat() if row.exam_date else None,
            "student_count": row.student_count,
        })

    grades = []
    for grade_name, classes_map in grade_map.items():
        real_classes = list(classes_map.values())

        all_subjects: dict[str, dict] = {}
        for cls in real_classes:
            for subj_id, subj in cls["subjects"].items():
                if subj_id not in all_subjects:
                    all_subjects[subj_id] = {
                        "id": subj["id"],
                        "code": subj["code"],
                        "name": subj["name"],
                        "exams": defaultdict(lambda: {"student_count": 0}),
                    }
                for exam in subj["exams"]:
                    key = exam["exam_id"]
                    entry = all_subjects[subj_id]["exams"][key]
                    entry["id"] = exam["exam_id"]
                    entry["exam_id"] = exam["exam_id"]
                    entry["subject_id"] = exam["subject_id"]
                    entry["name"] = exam["name"]
                    entry["exam_date"] = exam["exam_date"]
                    entry["student_count"] += exam["student_count"]

        all_node = {
            "id": "all",
            "name": "全部班级",
            "subjects": {
                sid: {
                    "id": s["id"],
                    "code": s["code"],
                    "name": s["name"],
                    "exams": list(s["exams"].values()),
                }
                for sid, s in all_subjects.items()
            },
        }

        for cls in real_classes:
            cls["subjects"] = list(cls["subjects"].values())
        all_node["subjects"] = list(all_node["subjects"].values())

        grades.append({
            "id": grade_name,
            "name": grade_name,
            "classes": [all_node] + real_classes,
        })

    return {"grades": grades}
