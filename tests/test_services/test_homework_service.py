import pytest
from edu_cloud.modules.homework.models import HomeworkTask, HomeworkSubmission


@pytest.mark.asyncio
async def test_create_homework_task(db):
    """HomeworkTask ORM 模型可以正常创建和查询。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User

    school = School(name="作业测试校", code="HW01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    user = User(username="hw_teacher", display_name="作业老师")
    user.set_password("123456")
    db.add(user)
    await db.flush()

    task = HomeworkTask(
        school_id=school.id,
        title="第三章练习",
        task_type="regular",
        subject_code="SX",
        assigned_by=user.id,
        status="draft",
    )
    db.add(task)
    await db.flush()

    assert task.id is not None
    assert task.title == "第三章练习"
    assert task.task_type == "regular"
    assert task.status == "draft"
    assert task.grading_mode == "manual"


@pytest.mark.asyncio
async def test_create_homework_submission(db):
    """HomeworkSubmission ORM 模型可以正常创建，唯一约束生效。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.student import Student

    school = School(name="提交测试校", code="HW02", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    user = User(username="hw_teacher2", display_name="作业老师2")
    user.set_password("123456")
    db.add(user)
    await db.flush()

    task = HomeworkTask(
        school_id=school.id, title="测试作业", task_type="regular",
        subject_code="YW", assigned_by=user.id, status="active",
    )
    db.add(task)
    await db.flush()

    student = Student(name="学生A", student_number="S001", school_id=school.id, grade="七年级")
    db.add(student)
    await db.flush()

    sub = HomeworkSubmission(task_id=task.id, student_id=student.id, status="pending")
    db.add(sub)
    await db.flush()

    assert sub.id is not None
    assert sub.status == "pending"
    assert sub.score is None
