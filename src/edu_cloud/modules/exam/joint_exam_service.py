"""联考生命周期服务。"""
import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import (
    JointExam, JointExamParticipant, JointExamStudentResult,
)
from edu_cloud.services.exceptions import (
    NotFoundError, StateError, ConflictError, ValidationError, PermissionDeniedError,
)

logger = logging.getLogger(__name__)


class JointExamService:
    def __init__(self, db: AsyncSession, upload_dir: str = "./uploads"):
        self.db = db
        self.upload_dir = upload_dir

    # --- Queries ---

    async def _get_exam(self, exam_id: str) -> JointExam:
        result = await self.db.execute(
            select(JointExam).where(JointExam.id == exam_id)
        )
        exam = result.scalar_one_or_none()
        if not exam:
            raise NotFoundError(f"Joint exam '{exam_id}' not found")
        return exam

    async def get_exam_detail(self, exam_id: str) -> dict:
        exam = await self._get_exam(exam_id)
        participants = (await self.db.execute(
            select(JointExamParticipant)
            .where(JointExamParticipant.joint_exam_id == exam_id)
        )).scalars().all()

        return {
            "id": exam.id,
            "name": exam.name,
            "status": exam.status,
            "subjects": exam.subjects,
            "creator_school_id": exam.creator_school_id,
            "answer_detail_schema": exam.answer_detail_schema,
            "created_at": str(exam.created_at),
            "participants": [
                {
                    "school_id": p.school_id,
                    "status": p.status,
                    "is_creator": p.is_creator,
                    "student_count": p.student_count,
                    "score_upload_count": p.score_upload_count,
                }
                for p in participants
            ],
        }

    async def list_exams(self, status: str | None = None, school_id: str | None = None) -> list[JointExam]:
        q = select(JointExam)
        if status:
            q = q.where(JointExam.status == status)
        if school_id:
            q = q.where(
                JointExam.id.in_(
                    select(JointExamParticipant.joint_exam_id)
                    .where(JointExamParticipant.school_id == school_id)
                )
            )
        q = q.order_by(JointExam.created_at.desc())
        return list((await self.db.execute(q)).scalars().all())

    # --- Mutations ---

    async def create_exam(
        self, name: str, subjects: list, creator_school_id: str, created_by: str,
        description: str | None = None,
    ) -> JointExam:
        exam = JointExam(
            name=name,
            description=description,
            subjects=subjects,
            creator_school_id=creator_school_id,
            created_by=created_by,
            status="draft",
        )
        self.db.add(exam)
        await self.db.flush()

        participant = JointExamParticipant(
            joint_exam_id=exam.id,
            school_id=creator_school_id,
            is_creator=True,
        )
        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(exam)
        logger.info("joint exam created: id=%s, name=%s", exam.id, name)
        return exam

    async def add_participant(self, exam_id: str, school_id: str) -> JointExamParticipant:
        await self._get_exam(exam_id)

        existing = (await self.db.execute(
            select(JointExamParticipant).where(
                JointExamParticipant.joint_exam_id == exam_id,
                JointExamParticipant.school_id == school_id,
            )
        )).scalar_one_or_none()
        if existing:
            raise ConflictError(f"School '{school_id}' already participates in this exam")

        p = JointExamParticipant(
            joint_exam_id=exam_id, school_id=school_id, is_creator=False,
        )
        self.db.add(p)
        await self.db.commit()
        await self.db.refresh(p)
        return p

    async def remove_participant(self, exam_id: str, school_id: str) -> None:
        p = (await self.db.execute(
            select(JointExamParticipant).where(
                JointExamParticipant.joint_exam_id == exam_id,
                JointExamParticipant.school_id == school_id,
            )
        )).scalar_one_or_none()
        if not p:
            raise NotFoundError(f"Participant not found")
        if p.is_creator:
            raise ValidationError("Cannot remove the creator school")
        await self.db.delete(p)
        await self.db.commit()

    async def distribute(self, exam_id: str) -> JointExam:
        exam = await self._get_exam(exam_id)
        if exam.status != "templates_ready":
            raise StateError(
                f"Cannot distribute: status must be 'templates_ready', got '{exam.status}'"
            )
        exam.status = "distributed"
        await self.db.commit()
        await self.db.refresh(exam)
        logger.info("joint exam distributed: id=%s", exam_id)
        return exam

    # --- Template Upload ---

    async def upload_template(
        self, exam_id: str, subject_code: str,
        skeleton_data: dict, pdf_bytes: bytes,
        answer_schema: list,
    ) -> None:
        exam = await self._get_exam(exam_id)
        if exam.status not in ("draft", "templates_ready"):
            raise StateError(f"Cannot upload template: status is '{exam.status}'")

        subject_codes = [s["code"] for s in exam.subjects]
        if subject_code not in subject_codes:
            raise ValidationError(f"Subject '{subject_code}' not in exam subjects: {subject_codes}")

        exam_dir = os.path.join(self.upload_dir, exam_id, subject_code)
        os.makedirs(exam_dir, exist_ok=True)
        with open(os.path.join(exam_dir, "skeleton.json"), "w", encoding="utf-8") as f:
            json.dump(skeleton_data, f, ensure_ascii=False)
        with open(os.path.join(exam_dir, "template.pdf"), "wb") as f:
            f.write(pdf_bytes)

        schema = exam.answer_detail_schema or {}
        schema[subject_code] = answer_schema
        exam.answer_detail_schema = schema
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(exam, "answer_detail_schema")

        all_done = all(sc in schema for sc in subject_codes)
        if all_done:
            exam.status = "templates_ready"

        await self.db.commit()
        await self.db.refresh(exam)

    # --- Score Submission ---

    async def submit_scores(
        self, exam_id: str, school_id: str, subject_code: str,
        student_results: list[dict],
    ) -> int:
        exam = await self._get_exam(exam_id)
        if exam.status not in ("distributed", "collecting"):
            raise StateError(f"Cannot submit scores: status is '{exam.status}'")

        participant = (await self.db.execute(
            select(JointExamParticipant).where(
                JointExamParticipant.joint_exam_id == exam_id,
                JointExamParticipant.school_id == school_id,
            )
        )).scalar_one_or_none()
        if not participant:
            raise PermissionDeniedError("School not participating in this exam")

        if not student_results:
            raise ValidationError("student_results cannot be empty")

        count = 0
        for item in student_results:
            existing = (await self.db.execute(
                select(JointExamStudentResult).where(
                    JointExamStudentResult.joint_exam_id == exam_id,
                    JointExamStudentResult.school_id == school_id,
                    JointExamStudentResult.subject_code == subject_code,
                    JointExamStudentResult.student_number == item["student_number"],
                )
            )).scalar_one_or_none()
            if existing:
                existing.total_score = item["total_score"]
                existing.detail_scores = item["detail_scores"]
                existing.student_name = item["student_name"]
                existing.uploaded_at = datetime.now(timezone.utc)
            else:
                self.db.add(JointExamStudentResult(
                    joint_exam_id=exam_id,
                    school_id=school_id,
                    subject_code=subject_code,
                    student_name=item["student_name"],
                    student_number=item["student_number"],
                    total_score=item["total_score"],
                    detail_scores=item.get("detail_scores", []),
                ))
            count += 1

        participant.status = "scores_uploaded"
        participant.score_upload_count = (participant.score_upload_count or 0) + count

        if exam.status == "distributed":
            exam.status = "collecting"

        await self._check_auto_complete(exam)

        await self.db.commit()
        return count

    async def _check_auto_complete(self, exam: JointExam) -> None:
        participants = (await self.db.execute(
            select(JointExamParticipant)
            .where(JointExamParticipant.joint_exam_id == exam.id)
        )).scalars().all()

        subject_codes = [s["code"] for s in exam.subjects]
        all_done = True
        for p in participants:
            for sc in subject_codes:
                result_count = (await self.db.execute(
                    select(func.count())
                    .select_from(JointExamStudentResult)
                    .where(
                        JointExamStudentResult.joint_exam_id == exam.id,
                        JointExamStudentResult.school_id == p.school_id,
                        JointExamStudentResult.subject_code == sc,
                    )
                )).scalar()
                if not result_count:
                    all_done = False
                    break
            if not all_done:
                break

        if all_done:
            exam.status = "completed"

    async def force_complete(self, exam_id: str) -> JointExam:
        exam = await self._get_exam(exam_id)
        if exam.status not in ("distributed", "collecting"):
            raise StateError(f"Cannot force complete: status is '{exam.status}'")
        exam.status = "completed"
        await self.db.commit()
        await self.db.refresh(exam)
        return exam
