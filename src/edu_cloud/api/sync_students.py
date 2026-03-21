"""学生 + 成绩同步端点（学校端 → 云端）。

学校端通过 API Key 认证，将本地学生档案和考试成绩同步到云端。
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.sync import get_school_by_api_key
from edu_cloud.models.student import Student
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.exam import Exam, ExamResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.post("/students")
async def sync_students(
    body: dict,
    school=Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """同步学生档案（upsert by student_number）。"""
    count = 0
    for s in body.get("students", []):
        class_name = s.get("class_name")
        grade = s.get("grade", "")

        # Resolve / create ClassGroup
        existing_class = None
        if class_name:
            existing_class = (await db.execute(
                select(ClassGroup).where(
                    ClassGroup.name == class_name,
                    ClassGroup.school_id == school.id,
                )
            )).scalar_one_or_none()
            if not existing_class:
                existing_class = ClassGroup(
                    name=class_name,
                    grade=grade,
                    school_id=school.id,
                )
                db.add(existing_class)
                await db.flush()

        # Upsert Student
        existing = (await db.execute(
            select(Student).where(
                Student.student_number == s["student_number"],
                Student.school_id == school.id,
            )
        )).scalar_one_or_none()

        if existing:
            existing.name = s["name"]
            existing.class_id = existing_class.id if existing_class else None
            existing.grade = grade
            existing.gender = s.get("gender")
        else:
            db.add(Student(
                name=s["name"],
                student_number=s["student_number"],
                school_id=school.id,
                class_id=existing_class.id if existing_class else None,
                grade=grade,
                gender=s.get("gender"),
            ))
        count += 1

    await db.commit()
    logger.info("sync students: school=%s, count=%d", school.code, count)
    return {"synced_count": count}


@router.post("/exam-results")
async def sync_exam_results(
    body: dict,
    school=Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """同步考试成绩（upsert by exam+student）。

    若学号在本校不存在则跳过该条目。
    """
    exam_data = body["exam"]

    # Upsert Exam
    exam = (await db.execute(
        select(Exam).where(
            Exam.name == exam_data["name"],
            Exam.subject_code == exam_data["subject_code"],
            Exam.school_id == school.id,
        )
    )).scalar_one_or_none()

    if not exam:
        exam = Exam(
            name=exam_data["name"],
            subject_code=exam_data["subject_code"],
            subject_name=exam_data.get("subject_name"),
            max_score=exam_data.get("max_score"),
            school_id=school.id,
            semester=exam_data.get("semester"),
            source="sync",
        )
        db.add(exam)
        await db.flush()

    count = 0
    for r in body.get("results", []):
        student = (await db.execute(
            select(Student).where(
                Student.student_number == r["student_number"],
                Student.school_id == school.id,
            )
        )).scalar_one_or_none()
        if not student:
            logger.debug(
                "sync exam-results: skip unknown student=%s school=%s",
                r["student_number"], school.code,
            )
            continue

        existing = (await db.execute(
            select(ExamResult).where(
                ExamResult.exam_id == exam.id,
                ExamResult.student_id == student.id,
            )
        )).scalar_one_or_none()

        if existing:
            existing.total_score = r["total_score"]
            existing.detail_scores = r.get("detail_scores")
        else:
            db.add(ExamResult(
                exam_id=exam.id,
                student_id=student.id,
                school_id=school.id,
                total_score=r["total_score"],
                detail_scores=r.get("detail_scores"),
            ))
        count += 1

    await db.commit()
    logger.info("sync exam-results: school=%s, exam=%s, count=%d", school.code, exam.name, count)
    return {"synced_count": count}
