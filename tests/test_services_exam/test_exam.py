import pytest
from edu_cloud.models.school import School
from edu_cloud.models.exam import Exam, Subject


async def test_create_exam_with_subjects(db):
    school = School(name="S1", code="S1")
    db.add(school)
    await db.commit()

    exam = Exam(school_id=school.id, name="2026 Spring Midterm", status="draft")
    db.add(exam)
    await db.commit()

    subj = Subject(
        school_id=school.id,
        exam_id=exam.id,
        name="Math",
        code="math",
    )
    db.add(subj)
    await db.commit()
    await db.refresh(subj)
    assert subj.exam_id == exam.id
