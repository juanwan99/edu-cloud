"""教学数据模型单测 — TDD Red phase."""
from edu_cloud.models.student import Student
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.exam import Exam, ExamResult


def test_student_fields():
    cols = {c.name for c in Student.__table__.columns}
    assert "name" in cols
    assert "student_number" in cols
    assert "school_id" in cols
    assert "class_id" in cols


def test_class_group_fields():
    cols = {c.name for c in ClassGroup.__table__.columns}
    assert "name" in cols
    assert "grade" in cols
    assert "school_id" in cols


def test_exam_fields():
    cols = {c.name for c in Exam.__table__.columns}
    assert "name" in cols
    assert "school_id" in cols
    assert "subject_code" in cols


def test_exam_result_fields():
    cols = {c.name for c in ExamResult.__table__.columns}
    assert "exam_id" in cols
    assert "student_id" in cols
    assert "total_score" in cols
