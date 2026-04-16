"""作业模块 Service — HomeworkTaskService + HomeworkSubmissionService。"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.homework.models import HomeworkTask, HomeworkSubmission
from edu_cloud.services.exceptions import NotFoundError, ValidationError, StateError
from edu_cloud.services.audit_service import audited

logger = logging.getLogger(__name__)

_TZ = timezone(timedelta(hours=8))

_VALID_TASK_TYPES = {"regular", "pre_exam", "post_exam"}

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
        db: AsyncSession, *, task_id: str, status: str | None = None,
    ) -> list[HomeworkSubmission]:
        stmt = select(HomeworkSubmission).where(HomeworkSubmission.task_id == task_id)
        if status:
            stmt = stmt.where(HomeworkSubmission.status == status)
        stmt = stmt.order_by(HomeworkSubmission.student_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def submit(
        db: AsyncSession, *, task_id: str, submission_id: str, content: str | None = None,
    ) -> HomeworkSubmission:
        sub = await db.get(HomeworkSubmission, submission_id)
        if not sub:
            raise NotFoundError("提交记录不存在")
        if sub.task_id != task_id:
            raise ValidationError("提交记录不属于该作业")
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
        db: AsyncSession, *, task_id: str, submission_id: str, score: float,
        feedback: str | None = None, graded_by: str,
    ) -> HomeworkSubmission:
        sub = await db.get(HomeworkSubmission, submission_id)
        if not sub:
            raise NotFoundError("提交记录不存在")
        if sub.task_id != task_id:
            raise ValidationError("提交记录不属于该作业")
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
        db: AsyncSession, *, task_id: str,
        grades: list[dict], graded_by: str,
    ) -> int:
        """批量批改，跳过无效 student_id。"""
        count = 0
        for g in grades:
            result = await db.execute(
                select(HomeworkSubmission).where(
                    HomeworkSubmission.task_id == task_id,
                    HomeworkSubmission.student_id == g["student_id"],
                    HomeworkSubmission.status == "submitted",
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
