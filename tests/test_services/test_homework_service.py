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


# ── Task 3: HomeworkTaskService CRUD ─────────────────────────

from edu_cloud.modules.homework.service import HomeworkTaskService
from edu_cloud.services.exceptions import NotFoundError, ValidationError


@pytest.fixture
async def hw_fixtures(db):
    """创建作业测试所需的 school + user + class + exam。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.modules.exam.models import Exam

    school = School(name="作业CRUD校", code="HWCRUD", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    teacher = User(username="hw_crud_teacher", display_name="CRUD老师")
    teacher.set_password("123456")
    db.add(teacher)
    await db.flush()

    cls = ClassGroup(name="七年级1班", grade="七年级", grade_number=7, school_id=school.id)
    db.add(cls)
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id, subject_code="SX")
    db.add(exam)
    await db.flush()

    await db.commit()
    return {
        "school_id": school.id, "teacher_id": teacher.id,
        "class_id": cls.id, "exam_id": exam.id,
    }


@pytest.mark.asyncio
async def test_create_task_regular(db, hw_fixtures):
    """创建 regular 作业，无需 exam_id。"""
    task = await HomeworkTaskService.create_task(
        db, school_id=hw_fixtures["school_id"], title="日常练习",
        task_type="regular", subject_code="SX",
        class_id=hw_fixtures["class_id"], assigned_by=hw_fixtures["teacher_id"],
    )
    assert task.status == "draft"
    assert task.task_type == "regular"
    assert task.exam_id is None


@pytest.mark.asyncio
async def test_create_task_post_exam_requires_exam_id(db, hw_fixtures):
    """post_exam 作业必须提供 exam_id。"""
    with pytest.raises(ValidationError, match="exam_id"):
        await HomeworkTaskService.create_task(
            db, school_id=hw_fixtures["school_id"], title="考后补偿",
            task_type="post_exam", subject_code="SX",
            assigned_by=hw_fixtures["teacher_id"],
        )


@pytest.mark.asyncio
async def test_create_task_post_exam_with_exam_id(db, hw_fixtures):
    """post_exam 作业提供 exam_id 可正常创建。"""
    task = await HomeworkTaskService.create_task(
        db, school_id=hw_fixtures["school_id"], title="考后补偿",
        task_type="post_exam", subject_code="SX",
        assigned_by=hw_fixtures["teacher_id"], exam_id=hw_fixtures["exam_id"],
    )
    assert task.exam_id == hw_fixtures["exam_id"]


@pytest.mark.asyncio
async def test_list_tasks_with_filters(db, hw_fixtures):
    """列表支持 status 和 task_type 过滤。"""
    for i, tt in enumerate(["regular", "regular", "pre_exam"]):
        await HomeworkTaskService.create_task(
            db, school_id=hw_fixtures["school_id"], title=f"作业{i}",
            task_type=tt, subject_code="SX", assigned_by=hw_fixtures["teacher_id"],
        )

    all_tasks = await HomeworkTaskService.list_tasks(db, school_id=hw_fixtures["school_id"])
    assert len(all_tasks) == 3

    regular_tasks = await HomeworkTaskService.list_tasks(
        db, school_id=hw_fixtures["school_id"], task_type="regular",
    )
    assert len(regular_tasks) == 2


@pytest.mark.asyncio
async def test_get_task_not_found(db, hw_fixtures):
    """获取不存在的作业抛 NotFoundError。"""
    with pytest.raises(NotFoundError):
        await HomeworkTaskService.get_task(
            db, task_id="nonexistent", school_id=hw_fixtures["school_id"],
        )


@pytest.mark.asyncio
async def test_update_task_only_draft(db, hw_fixtures):
    """只有 draft 状态可以编辑。"""
    task = await HomeworkTaskService.create_task(
        db, school_id=hw_fixtures["school_id"], title="原标题",
        task_type="regular", subject_code="SX", assigned_by=hw_fixtures["teacher_id"],
    )
    updated = await HomeworkTaskService.update_task(
        db, task_id=task.id, school_id=hw_fixtures["school_id"], title="新标题",
    )
    assert updated.title == "新标题"


@pytest.mark.asyncio
async def test_delete_task_only_draft(db, hw_fixtures):
    """只有 draft 状态可以删除。"""
    task = await HomeworkTaskService.create_task(
        db, school_id=hw_fixtures["school_id"], title="待删除",
        task_type="regular", subject_code="SX", assigned_by=hw_fixtures["teacher_id"],
    )
    await HomeworkTaskService.delete_task(db, task_id=task.id, school_id=hw_fixtures["school_id"])
    with pytest.raises(NotFoundError):
        await HomeworkTaskService.get_task(db, task_id=task.id, school_id=hw_fixtures["school_id"])
