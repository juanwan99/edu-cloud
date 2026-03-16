"""学校端 ↔ 云端同步端点。

学校端通过 API Key 认证（非 JWT），因为学校端是系统级客户端而非人类用户。
"""

import logging
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.models.school import RegisteredSchool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


async def get_school_by_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> RegisteredSchool:
    """从 API Key 识别学校。学校端每个请求都带 X-API-Key header。"""
    # API Key 格式: {school_code}:{secret}
    if ":" not in x_api_key:
        raise HTTPException(401, "Invalid API key format")
    school_code, secret = x_api_key.split(":", 1)

    result = await db.execute(
        select(RegisteredSchool).where(
            RegisteredSchool.code == school_code,
            RegisteredSchool.is_active.is_(True),
        )
    )
    school = result.scalar_one_or_none()
    if not school:
        logger.warning("sync auth failed: school_code=%s not found or inactive", school_code)
        raise HTTPException(401, "Invalid API key")

    if not bcrypt.checkpw(secret.encode(), school.api_key_hash.encode()):
        logger.warning("sync auth failed: school_code=%s bad secret", school_code)
        raise HTTPException(401, "Invalid API key")

    return school


# --- Heartbeat ---

class HeartbeatRequest(BaseModel):
    client_version: str
    exam_ai_port: int = 8000


@router.post("/heartbeat")
async def heartbeat(
    req: HeartbeatRequest,
    school: RegisteredSchool = Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    school.last_heartbeat = datetime.now(timezone.utc)
    school.client_version = req.client_version
    school.exam_ai_port = req.exam_ai_port
    await db.commit()
    logger.debug("heartbeat: school=%s, version=%s", school.code, req.client_version)
    return {"status": "ok"}


# --- Joint Exam Pull ---

@router.get("/joint-exams")
async def pull_joint_exams(
    school: RegisteredSchool = Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """学校端拉取分配给本校的联考列表。"""
    from edu_cloud.models.joint_exam import JointExamParticipant, JointExam

    result = await db.execute(
        select(JointExam)
        .join(JointExamParticipant, JointExamParticipant.joint_exam_id == JointExam.id)
        .where(JointExamParticipant.school_id == school.id)
        .where(JointExam.status.in_(["distributed", "scanning", "grading"]))
    )
    exams = result.scalars().all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "status": e.status,
            "subjects": e.subjects,
        }
        for e in exams
    ]


# --- Score Upload ---

class ScoreItem(BaseModel):
    subject_code: str
    student_id: str
    student_name: str
    class_name: str | None = None
    score: float
    max_score: float


class ScoreUploadRequest(BaseModel):
    joint_exam_id: str
    scores: list[ScoreItem]


@router.post("/scores")
async def upload_scores(
    req: ScoreUploadRequest,
    school: RegisteredSchool = Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """学校端上报联考成绩。"""
    from edu_cloud.models.joint_exam import JointExamScore, JointExamParticipant

    # 验证该校确实参与了这个联考
    result = await db.execute(
        select(JointExamParticipant).where(
            JointExamParticipant.joint_exam_id == req.joint_exam_id,
            JointExamParticipant.school_id == school.id,
        )
    )
    participant = result.scalar_one_or_none()
    if not participant:
        raise HTTPException(403, "School not participating in this joint exam")

    # 写入成绩
    for item in req.scores:
        score = JointExamScore(
            joint_exam_id=req.joint_exam_id,
            school_id=school.id,
            subject_code=item.subject_code,
            student_id=item.student_id,
            student_name=item.student_name,
            class_name=item.class_name,
            score=item.score,
            max_score=item.max_score,
        )
        db.add(score)

    participant.status = "scores_uploaded"
    participant.score_upload_count = len(req.scores)
    await db.commit()

    logger.info(
        "scores uploaded: school=%s, joint_exam=%s, count=%d",
        school.code, req.joint_exam_id, len(req.scores),
    )
    return {"status": "ok", "count": len(req.scores)}
