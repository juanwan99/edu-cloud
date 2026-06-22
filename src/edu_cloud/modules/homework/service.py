"""作业模块 Service — HomeworkTaskService + HomeworkSubmissionService。"""
import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.homework.models import HomeworkTask, HomeworkSubmission
from edu_cloud.services.exceptions import NotFoundError, ValidationError, StateError
from edu_cloud.services.audit_service import audited

logger = logging.getLogger(__name__)

_TZ = timezone(timedelta(hours=8))

_VALID_TASK_TYPES = {"regular", "pre_exam", "post_exam", "remedial"}

_STATUS_TRANSITIONS = {
    "publish": {"from": frozenset({"draft"}), "to": "active"},
    "expire":  {"from": frozenset({"active"}), "to": "expired"},
    "close":   {"from": frozenset({"active", "expired", "draft"}), "to": "closed"},
}


class HomeworkTaskService:
    @staticmethod
    @audited("homework_task", action="create")
    async def create_task(
        db: AsyncSession, *, school_id: str, title: str,
        task_type: str = "regular", subject_code: str,
        class_id: str | None = None, assigned_by: str,
        exam_id: str | None = None, deadline: datetime | None = None,
        content: str | None = None,
    ) -> HomeworkTask:
        if task_type not in _VALID_TASK_TYPES:
            raise ValidationError(f"无效的作业类型: {task_type}")
        if task_type == "post_exam" and not exam_id:
            raise ValidationError("考后作业必须关联 exam_id")
        task = HomeworkTask(
            school_id=school_id, title=title, task_type=task_type,
            subject_code=subject_code, class_id=class_id,
            assigned_by=assigned_by, exam_id=exam_id,
            deadline=deadline, content=content,
        )
        db.add(task)
        await db.flush()
        logger.info("create_task: id=%s, type=%s, school=%s", task.id, task_type, school_id)
        return task

    @staticmethod
    async def list_tasks(
        db: AsyncSession, *, school_id: str,
        class_id: str | None = None, subject_code: str | None = None,
        status: str | None = None, task_type: str | None = None,
        assigned_by: str | None = None,
    ) -> list[HomeworkTask]:
        stmt = select(HomeworkTask).where(HomeworkTask.school_id == school_id)
        if class_id:
            stmt = stmt.where(HomeworkTask.class_id == class_id)
        if subject_code:
            stmt = stmt.where(HomeworkTask.subject_code == subject_code)
        if status:
            stmt = stmt.where(HomeworkTask.status == status)
        if task_type:
            stmt = stmt.where(HomeworkTask.task_type == task_type)
        if assigned_by:
            stmt = stmt.where(HomeworkTask.assigned_by == assigned_by)
        stmt = stmt.order_by(HomeworkTask.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_task(
        db: AsyncSession, *, task_id: str, school_id: str,
    ) -> HomeworkTask:
        result = await db.execute(
            select(HomeworkTask).where(
                HomeworkTask.id == task_id, HomeworkTask.school_id == school_id,
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            raise NotFoundError("作业不存在")
        return task

    @staticmethod
    async def update_task(
        db: AsyncSession, *, task_id: str, school_id: str,
        title: str | None = None, content: str | None = None,
        deadline: datetime | None = None, class_id: str | None = None,
    ) -> HomeworkTask:
        task = await HomeworkTaskService.get_task(db, task_id=task_id, school_id=school_id)
        if task.status != "draft":
            raise StateError("只有草稿状态的作业可以编辑")
        if title is not None:
            task.title = title
        if content is not None:
            task.content = content
        if deadline is not None:
            task.deadline = deadline
        if class_id is not None:
            task.class_id = class_id
        await db.flush()
        return task

    @staticmethod
    async def delete_task(
        db: AsyncSession, *, task_id: str, school_id: str,
    ) -> None:
        task = await HomeworkTaskService.get_task(db, task_id=task_id, school_id=school_id)
        if task.status != "draft":
            raise StateError("只有草稿状态的作业可以删除")
        await db.delete(task)
        await db.flush()
        logger.info("delete_task: id=%s", task_id)

    @staticmethod
    @audited("homework_task", action="update", id_param="task_id")
    async def transition_status(
        db: AsyncSession, *, task_id: str, school_id: str, action: str,
    ) -> HomeworkTask:
        task = await HomeworkTaskService.get_task(db, task_id=task_id, school_id=school_id)
        rule = _STATUS_TRANSITIONS.get(action)
        if not rule:
            raise ValidationError(f"未知的状态操作: {action}")
        if task.status not in rule["from"]:
            raise StateError(f"作业当前状态 {task.status} 不允许操作 {action}")

        if action == "publish" and not task.class_id:
            raise ValidationError("发布作业必须指定班级 (class_id)")

        task.status = rule["to"]

        if action == "publish":
            count = await HomeworkSubmissionService.create_submissions_batch(
                db, task_id=task.id, school_id=school_id, class_id=task.class_id,
            )
            logger.info("publish_task: id=%s, submissions_created=%d", task.id, count)

        await db.flush()
        return task


    # ── 考后推送 + 内容增强 (WP-C) ─────────────────────────────

    @staticmethod
    @audited("homework_task", action="create")
    async def create_remedial_task(
        db: AsyncSession, *, exam_id: str, class_id: str,
        school_id: str, created_by: str,
        error_threshold: float = 0.4,
        max_questions: int = 10,
    ) -> HomeworkTask:
        """从考试分析数据中自动创建补救作业。

        1. 读取考试的题目 + 学生作答，计算每题错误率
        2. 筛选错误率 > error_threshold 的题目
        3. 从题库中找同题型的练习题
        4. 自动构建 content JSON 并创建 HomeworkTask
        """
        from edu_cloud.services.homework_workflow import (
            BankQuestion,
            Exam,
            Question,
            StudentAnswer,
            Subject,
        )

        # 验证考试存在且属于本校
        exam_result = await db.execute(
            select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            raise NotFoundError("考试不存在")

        # 获取所有科目
        subjects_result = await db.execute(
            select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
        )
        subjects = list(subjects_result.scalars().all())
        if not subjects:
            raise NotFoundError("考试没有科目数据")

        subject_ids = [s.id for s in subjects]

        # 获取所有题目
        questions_result = await db.execute(
            select(Question).where(
                Question.subject_id.in_(subject_ids),
                Question.school_id == school_id,
                Question.max_score > 0,
            )
        )
        questions = {q.id: q for q in questions_result.scalars().all()}

        # 获取学生作答数据，按题聚合计算错误率
        answers_result = await db.execute(
            select(
                StudentAnswer.question_id,
                func.count().label("total"),
                func.avg(StudentAnswer.score).label("avg_score"),
            )
            .where(
                StudentAnswer.exam_id == exam_id,
                StudentAnswer.school_id == school_id,
                StudentAnswer.question_id.in_(list(questions.keys())),
            )
            .group_by(StudentAnswer.question_id)
        )

        # 计算错误率 = 1 - (avg_score / max_score)
        high_error_question_ids: list[str] = []
        for row in answers_result.all():
            q = questions.get(row.question_id)
            if not q or q.max_score <= 0:
                continue
            error_rate = 1.0 - (row.avg_score / q.max_score)
            if error_rate >= error_threshold:
                high_error_question_ids.append(row.question_id)

        # 从题库中找同题型的练习题
        remedial_bank_ids: list[str] = []
        if high_error_question_ids:
            # 收集高错误率题目的题型
            error_question_types = set()
            for qid in high_error_question_ids:
                q = questions.get(qid)
                if q:
                    error_question_types.add(q.question_type)

            if error_question_types:
                bank_result = await db.execute(
                    select(BankQuestion.id)
                    .where(
                        BankQuestion.school_id == school_id,
                        BankQuestion.question_type.in_(list(error_question_types)),
                    )
                    .limit(max_questions)
                )
                remedial_bank_ids = [row[0] for row in bank_result.all()]

        # 构建 content JSON
        content = json.dumps({
            "question_ids": remedial_bank_ids,
            "source_exam_id": exam_id,
            "error_threshold": error_threshold,
            "high_error_question_ids": high_error_question_ids,
        })

        # 自动生成标题
        title = f"{exam.name} 补救练习"

        task = HomeworkTask(
            school_id=school_id,
            title=title,
            task_type="remedial",
            subject_code=exam.subject_code,
            class_id=class_id,
            assigned_by=created_by,
            exam_id=exam_id,
            content=content,
        )
        db.add(task)
        await db.flush()
        logger.info(
            "create_remedial_task: id=%s, exam=%s, high_error_questions=%d, bank_questions=%d",
            task.id, exam_id, len(high_error_question_ids), len(remedial_bank_ids),
        )
        return task

    @staticmethod
    async def get_task_content_detail(
        db: AsyncSession, *, task_id: str, school_id: str,
    ) -> dict:
        """解析 task.content JSON 中的 question_ids，返回带完整题目信息的内容结构。"""
        from edu_cloud.services.homework_workflow import BankQuestion

        task = await HomeworkTaskService.get_task(db, task_id=task_id, school_id=school_id)

        if not task.content:
            return {"task_id": task_id, "questions": [], "source_exam_id": None}

        try:
            content_data = json.loads(task.content) if isinstance(task.content, str) else task.content
        except (json.JSONDecodeError, TypeError):
            return {"task_id": task_id, "questions": [], "source_exam_id": None}

        question_ids = content_data.get("question_ids", [])
        source_exam_id = content_data.get("source_exam_id")

        if not question_ids:
            return {"task_id": task_id, "questions": [], "source_exam_id": source_exam_id}

        # 从题库批量读取题目详情
        result = await db.execute(
            select(BankQuestion).where(
                BankQuestion.id.in_(question_ids),
                BankQuestion.school_id == school_id,
            )
        )
        bank_questions = {bq.id: bq for bq in result.scalars().all()}

        questions_detail = []
        for qid in question_ids:
            bq = bank_questions.get(qid)
            if bq:
                questions_detail.append({
                    "id": bq.id,
                    "content_text": bq.content_text,
                    "question_type": bq.question_type,
                    "max_score": bq.max_score,
                    "difficulty": bq.difficulty,
                    "knowledge_point_ids": bq.knowledge_point_ids,
                    "correct_answer": bq.correct_answer,
                })

        return {
            "task_id": task_id,
            "questions": questions_detail,
            "source_exam_id": source_exam_id,
        }


class HomeworkSubmissionService:
    @staticmethod
    async def create_submissions_batch(
        db: AsyncSession, *, task_id: str, school_id: str, class_id: str,
    ) -> int:
        """为班级所有学生创建 pending 提交记录（幂等）。"""
        from edu_cloud.models.student import Student
        students_result = await db.execute(
            select(Student).where(
                Student.school_id == school_id,
                Student.class_id == class_id,
            )
        )
        students = list(students_result.scalars().all())
        created = 0
        for student in students:
            existing = await db.execute(
                select(HomeworkSubmission).where(
                    HomeworkSubmission.task_id == task_id,
                    HomeworkSubmission.student_id == student.id,
                )
            )
            if existing.scalar_one_or_none() is None:
                db.add(HomeworkSubmission(task_id=task_id, student_id=student.id))
                created += 1
        await db.flush()
        return created

    @staticmethod
    async def list_submissions(
        db: AsyncSession, *, task_id: str, school_id: str,
        status: str | None = None,
    ) -> list[HomeworkSubmission]:
        stmt = (
            select(HomeworkSubmission)
            .join(HomeworkTask, HomeworkSubmission.task_id == HomeworkTask.id)
            .where(
                HomeworkSubmission.task_id == task_id,
                HomeworkTask.school_id == school_id,
            )
        )
        if status:
            stmt = stmt.where(HomeworkSubmission.status == status)
        stmt = stmt.order_by(HomeworkSubmission.student_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def submit(
        db: AsyncSession, *, task_id: str, submission_id: str,
        school_id: str, content: str | None = None,
    ) -> HomeworkSubmission:
        result = await db.execute(
            select(HomeworkSubmission)
            .join(HomeworkTask, HomeworkSubmission.task_id == HomeworkTask.id)
            .where(
                HomeworkSubmission.id == submission_id,
                HomeworkSubmission.task_id == task_id,
                HomeworkTask.school_id == school_id,
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise NotFoundError("提交记录不存在")
        if sub.status != "pending":
            raise StateError(f"当前状态 {sub.status} 不允许提交")
        # F-04: 联查 task 状态，关闭/过期的作业不接受提交
        task = await db.get(HomeworkTask, sub.task_id)
        if not task or task.status != "active":
            raise StateError("作业已关闭或未发布，不接受提交")
        sub.status = "submitted"
        sub.content = content
        sub.submit_time = datetime.now(_TZ)
        await db.flush()
        return sub

    @staticmethod
    async def grade_single(
        db: AsyncSession, *, task_id: str, submission_id: str,
        school_id: str, score: float,
        feedback: str | None = None, graded_by: str,
    ) -> HomeworkSubmission:
        result = await db.execute(
            select(HomeworkSubmission)
            .join(HomeworkTask, HomeworkSubmission.task_id == HomeworkTask.id)
            .where(
                HomeworkSubmission.id == submission_id,
                HomeworkSubmission.task_id == task_id,
                HomeworkTask.school_id == school_id,
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise NotFoundError("提交记录不存在")
        if sub.status != "submitted":
            raise StateError(f"当前状态 {sub.status} 不允许批改")
        sub.status = "graded"
        sub.score = score
        sub.feedback = feedback
        sub.graded_by = graded_by
        sub.graded_at = datetime.now(_TZ)
        await db.flush()
        return sub

    @staticmethod
    async def grade_batch(
        db: AsyncSession, *, task_id: str, school_id: str,
        grades: list[dict], graded_by: str,
    ) -> int:
        """批量批改，跳过无效 student_id。school_id 通过 JOIN 校验归属。"""
        count = 0
        for g in grades:
            result = await db.execute(
                select(HomeworkSubmission)
                .join(HomeworkTask, HomeworkSubmission.task_id == HomeworkTask.id)
                .where(
                    HomeworkSubmission.task_id == task_id,
                    HomeworkSubmission.student_id == g["student_id"],
                    HomeworkSubmission.status == "submitted",
                    HomeworkTask.school_id == school_id,
                )
            )
            sub = result.scalar_one_or_none()
            if not sub:
                continue
            sub.status = "graded"
            sub.score = g.get("score")
            sub.feedback = g.get("feedback")
            sub.graded_by = graded_by
            sub.graded_at = datetime.now(_TZ)
            count += 1
        await db.flush()
        return count

    @staticmethod
    async def get_task_stats(db: AsyncSession, *, task_id: str) -> dict:
        total_result = await db.execute(
            select(func.count()).where(HomeworkSubmission.task_id == task_id)
        )
        total = total_result.scalar() or 0

        submitted_result = await db.execute(
            select(func.count()).where(
                HomeworkSubmission.task_id == task_id,
                HomeworkSubmission.status.in_(["submitted", "graded"]),
            )
        )
        submitted = submitted_result.scalar() or 0

        graded_result = await db.execute(
            select(func.count()).where(
                HomeworkSubmission.task_id == task_id,
                HomeworkSubmission.status == "graded",
            )
        )
        graded = graded_result.scalar() or 0

        avg_result = await db.execute(
            select(func.avg(HomeworkSubmission.score)).where(
                HomeworkSubmission.task_id == task_id,
                HomeworkSubmission.score.isnot(None),
            )
        )
        avg_score = avg_result.scalar()

        return {
            "total": total,
            "pending": total - submitted,
            "submitted": submitted - graded,
            "graded": graded,
            "submission_rate": round(submitted / total * 100, 1) if total > 0 else 0.0,
            "avg_score": round(avg_score, 1) if avg_score is not None else None,
        }
