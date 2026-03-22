"""学校端 ↔ 云端同步端点。

学校端通过 API Key 认证（非 JWT），因为学校端是系统级客户端而非人类用户。
"""

import io
import json
import logging
import os
import zipfile
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Header, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.models.school import School
from edu_cloud.models.joint_exam import JointExamParticipant, JointExam
from edu_cloud.services.joint_exam_service import JointExamService
from edu_cloud.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


async def get_school_by_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> School:
    """从 API Key 识别学校。学校端每个请求都带 X-API-Key header。"""
    # API Key 格式: {school_code}:{secret}
    if ":" not in x_api_key:
        raise HTTPException(401, "Invalid API key format")
    school_code, secret = x_api_key.split(":", 1)

    result = await db.execute(
        select(School).where(
            School.code == school_code,
            School.is_active.is_(True),
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
    client_version: str = ""
    exam_ai_port: int = 8000


@router.post("/heartbeat")
async def heartbeat(
    req: HeartbeatRequest,
    school: School = Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    # Fields removed from School model; heartbeat just confirms connectivity
    logger.debug("heartbeat: school=%s, version=%s", school.code, req.client_version)
    return {"status": "ok"}


# --- Joint Exam Pull ---

@router.get("/joint-exams")
async def pull_joint_exams(
    school: School = Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """学校端拉取分配给本校的联考列表。"""
    result = await db.execute(
        select(JointExam)
        .join(JointExamParticipant, JointExamParticipant.joint_exam_id == JointExam.id)
        .where(JointExamParticipant.school_id == school.id)
        .where(JointExam.status.in_(["distributed", "collecting"]))
    )
    exams = result.scalars().all()

    base_url = ""  # relative URL
    return {
        "joint_exams": [
            {
                "id": e.id,
                "name": e.name,
                "status": e.status,
                "subjects": [
                    {
                        **subj,
                        "template_url": f"{base_url}/api/v1/sync/templates/{e.id}/{subj['code']}",
                        "answer_detail_schema": (e.answer_detail_schema or {}).get(subj["code"], []),
                    }
                    for subj in e.subjects
                ],
            }
            for e in exams
        ]
    }


# --- Template Upload (from creator school) ---

@router.post("/templates")
async def upload_template(
    joint_exam_id: str = Form(...),
    subject_code: str = Form(...),
    answer_schema: str = Form(...),
    skeleton: UploadFile = File(...),
    pdf: UploadFile = File(...),
    school: School = Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """出题校上传试卷模板（skeleton.json + template.pdf）。"""
    # 校验：只有出题校可以上传模板
    exam = (await db.execute(
        select(JointExam).where(JointExam.id == joint_exam_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Joint exam not found")
    if exam.creator_school_id != school.id:
        raise HTTPException(403, "Only the creator school can upload templates")

    skeleton_bytes = await skeleton.read()
    pdf_bytes = await pdf.read()
    schema = json.loads(answer_schema)
    skeleton_data = json.loads(skeleton_bytes)

    svc = JointExamService(db, upload_dir=settings.UPLOAD_DIR)
    await svc.upload_template(
        exam_id=joint_exam_id,
        subject_code=subject_code,
        skeleton_data=skeleton_data,
        pdf_bytes=pdf_bytes,
        answer_schema=schema,
    )
    logger.info("template uploaded: exam=%s, subject=%s, school=%s",
                joint_exam_id, subject_code, school.code)
    return {"status": "ok"}


# --- Template Download (zip: skeleton.json + template.pdf) ---

@router.get("/templates/{exam_id}/{subject_code}")
async def download_template(
    exam_id: str,
    subject_code: str,
    school: School = Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """参与校下载试卷模板（zip 包）。"""
    # 校验：只有参与校可以下载模板
    participant = (await db.execute(
        select(JointExamParticipant).where(
            JointExamParticipant.joint_exam_id == exam_id,
            JointExamParticipant.school_id == school.id,
        )
    )).scalar_one_or_none()
    if not participant:
        raise HTTPException(403, "School not participating in this exam")

    exam_dir = os.path.join(settings.UPLOAD_DIR, exam_id, subject_code)
    skeleton_path = os.path.join(exam_dir, "skeleton.json")
    pdf_path = os.path.join(exam_dir, "template.pdf")

    if not os.path.exists(skeleton_path) or not os.path.exists(pdf_path):
        raise HTTPException(404, "Template not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(skeleton_path, "skeleton.json")
        zf.write(pdf_path, "template.pdf")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=template_{subject_code}.zip"},
    )


# --- Score Upload ---

class StudentResultItem(BaseModel):
    student_name: str
    student_number: str
    total_score: float
    detail_scores: list[dict] = []


class ScoreUploadRequest(BaseModel):
    joint_exam_id: str
    subject_code: str
    student_results: list[StudentResultItem]


@router.post("/scores")
async def upload_scores(
    req: ScoreUploadRequest,
    school: School = Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """学校端上报联考成绩（逐题明细）。"""
    svc = JointExamService(db, upload_dir=settings.UPLOAD_DIR)
    count = await svc.submit_scores(
        exam_id=req.joint_exam_id,
        school_id=school.id,
        subject_code=req.subject_code,
        student_results=[item.model_dump() for item in req.student_results],
    )
    logger.info(
        "scores uploaded: school=%s, joint_exam=%s, subject=%s, count=%d",
        school.code, req.joint_exam_id, req.subject_code, count,
    )
    return {"status": "ok", "count": count}
