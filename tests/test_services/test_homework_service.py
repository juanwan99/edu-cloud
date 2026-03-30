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


@pytest.mark.asyncio
async def test_submission_unique_constraint(db):
    """CR-4: 同一 task_id + student_id 重复插入抛 IntegrityError。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.student import Student
    from sqlalchemy.exc import IntegrityError

    school = School(name="唯一约束校", code="HW03", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    user = User(username="hw_teacher3", display_name="老师3")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    task = HomeworkTask(
        school_id=school.id, title="唯一测试", task_type="regular",
        subject_code="SX", assigned_by=user.id, status="active",
    )
    db.add(task)
    await db.flush()
    student = Student(name="学生B", student_number="S002", school_id=school.id, grade="七年级")
    db.add(student)
    await db.flush()

    db.add(HomeworkSubmission(task_id=task.id, student_id=student.id))
    await db.flush()
    db.add(HomeworkSubmission(task_id=task.id, student_id=student.id))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


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


# ── Task 4: 状态机 + HomeworkSubmissionService ───────────────

from edu_cloud.modules.homework.service import HomeworkSubmissionService
from edu_cloud.services.exceptions import StateError


@pytest.fixture
async def hw_with_students(db, hw_fixtures):
    """在 hw_fixtures 基础上创建 3 个学生。"""
    from edu_cloud.models.student import Student

    students = []
    for i in range(3):
        s = Student(
            name=f"学生{i}", student_number=f"HW{i:03d}",
            school_id=hw_fixtures["school_id"], grade="七年级",
            class_id=hw_fixtures["class_id"],
        )
        db.add(s)
        students.append(s)
    await db.flush()
    hw_fixtures["student_ids"] = [s.id for s in students]
    return hw_fixtures


@pytest.mark.asyncio
async def test_publish_creates_submissions(db, hw_with_students):
    """发布作业时自动为班级学生创建 pending 提交记录。"""
    f = hw_with_students
    task = await HomeworkTaskService.create_task(
        db, school_id=f["school_id"], title="发布测试",
        task_type="regular", subject_code="SX",
        class_id=f["class_id"], assigned_by=f["teacher_id"],
    )
    result = await HomeworkTaskService.transition_status(
        db, task_id=task.id, school_id=f["school_id"], action="publish",
    )
    assert result.status == "active"

    subs = await HomeworkSubmissionService.list_submissions(db, task_id=task.id)
    assert len(subs) == 3
    assert all(s.status == "pending" for s in subs)


@pytest.mark.asyncio
async def test_publish_requires_class_id(db, hw_fixtures):
    """发布时 class_id 为空抛 ValidationError。"""
    task = await HomeworkTaskService.create_task(
        db, school_id=hw_fixtures["school_id"], title="无班级",
        task_type="regular", subject_code="SX",
        assigned_by=hw_fixtures["teacher_id"],
    )
    with pytest.raises(ValidationError, match="class_id"):
        await HomeworkTaskService.transition_status(
            db, task_id=task.id, school_id=hw_fixtures["school_id"], action="publish",
        )


@pytest.mark.asyncio
async def test_invalid_transition(db, hw_fixtures):
    """active 状态不能再 publish。"""
    task = await HomeworkTaskService.create_task(
        db, school_id=hw_fixtures["school_id"], title="状态测试",
        task_type="regular", subject_code="SX",
        class_id=hw_fixtures["class_id"], assigned_by=hw_fixtures["teacher_id"],
    )
    await HomeworkTaskService.transition_status(
        db, task_id=task.id, school_id=hw_fixtures["school_id"], action="publish",
    )
    with pytest.raises(StateError):
        await HomeworkTaskService.transition_status(
            db, task_id=task.id, school_id=hw_fixtures["school_id"], action="publish",
        )


@pytest.mark.asyncio
async def test_submit_homework(db, hw_with_students):
    """学生提交作业：pending → submitted。"""
    f = hw_with_students
    task = await HomeworkTaskService.create_task(
        db, school_id=f["school_id"], title="提交测试",
        task_type="regular", subject_code="SX",
        class_id=f["class_id"], assigned_by=f["teacher_id"],
    )
    await HomeworkTaskService.transition_status(
        db, task_id=task.id, school_id=f["school_id"], action="publish",
    )
    subs = await HomeworkSubmissionService.list_submissions(db, task_id=task.id)
    updated = await HomeworkSubmissionService.submit(
        db, task_id=task.id, submission_id=subs[0].id, content='{"answer": "A"}',
    )
    assert updated.status == "submitted"
    assert updated.submit_time is not None


@pytest.mark.asyncio
async def test_grade_single(db, hw_with_students):
    """教师批改单个提交：submitted → graded。"""
    f = hw_with_students
    task = await HomeworkTaskService.create_task(
        db, school_id=f["school_id"], title="批改测试",
        task_type="regular", subject_code="SX",
        class_id=f["class_id"], assigned_by=f["teacher_id"],
    )
    await HomeworkTaskService.transition_status(
        db, task_id=task.id, school_id=f["school_id"], action="publish",
    )
    subs = await HomeworkSubmissionService.list_submissions(db, task_id=task.id)
    await HomeworkSubmissionService.submit(db, task_id=task.id, submission_id=subs[0].id, content='{}')
    graded = await HomeworkSubmissionService.grade_single(
        db, task_id=task.id, submission_id=subs[0].id, score=85.0,
        feedback="不错", graded_by=f["teacher_id"],
    )
    assert graded.status == "graded"
    assert graded.score == 85.0
    assert graded.graded_by == f["teacher_id"]


@pytest.mark.asyncio
async def test_grade_batch(db, hw_with_students):
    """批量批改。"""
    f = hw_with_students
    task = await HomeworkTaskService.create_task(
        db, school_id=f["school_id"], title="批量批改",
        task_type="regular", subject_code="SX",
        class_id=f["class_id"], assigned_by=f["teacher_id"],
    )
    await HomeworkTaskService.transition_status(
        db, task_id=task.id, school_id=f["school_id"], action="publish",
    )
    subs = await HomeworkSubmissionService.list_submissions(db, task_id=task.id)
    for s in subs:
        await HomeworkSubmissionService.submit(db, task_id=task.id, submission_id=s.id, content='{}')

    grades = [
        {"student_id": f["student_ids"][0], "score": 90, "feedback": "优秀"},
        {"student_id": f["student_ids"][1], "score": 75, "feedback": "良好"},
        {"student_id": "nonexistent_id", "score": 60, "feedback": "无效"},
    ]
    count = await HomeworkSubmissionService.grade_batch(
        db, task_id=task.id, grades=grades, graded_by=f["teacher_id"],
    )
    assert count == 2  # 跳过 nonexistent


@pytest.mark.asyncio
async def test_submit_after_close_rejected(db, hw_with_students):
    """关闭作业后不接受新提交。"""
    f = hw_with_students
    task = await HomeworkTaskService.create_task(
        db, school_id=f["school_id"], title="关闭测试",
        task_type="regular", subject_code="SX",
        class_id=f["class_id"], assigned_by=f["teacher_id"],
    )
    await HomeworkTaskService.transition_status(
        db, task_id=task.id, school_id=f["school_id"], action="publish",
    )
    await HomeworkTaskService.transition_status(
        db, task_id=task.id, school_id=f["school_id"], action="close",
    )
    subs = await HomeworkSubmissionService.list_submissions(db, task_id=task.id)
    with pytest.raises(StateError, match="已关闭"):
        await HomeworkSubmissionService.submit(db, task_id=task.id, submission_id=subs[0].id, content='{}')


@pytest.mark.asyncio
async def test_get_task_stats(db, hw_with_students):
    """统计提交/批改/平均分。"""
    f = hw_with_students
    task = await HomeworkTaskService.create_task(
        db, school_id=f["school_id"], title="统计测试",
        task_type="regular", subject_code="SX",
        class_id=f["class_id"], assigned_by=f["teacher_id"],
    )
    await HomeworkTaskService.transition_status(
        db, task_id=task.id, school_id=f["school_id"], action="publish",
    )
    stats = await HomeworkSubmissionService.get_task_stats(db, task_id=task.id)
    assert stats["total"] == 3
    assert stats["pending"] == 3
    assert stats["submitted"] == 0
    assert stats["graded"] == 0
    assert stats["submission_rate"] == 0.0
