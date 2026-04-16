"""Class / Student 路由 — 从 exam-ai 迁入。"""
import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.api.permissions import get_visible_class_ids
from edu_cloud.modules.student import service as student_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["students"])


def _class_response(c) -> dict:
    return {"id": c.id, "name": c.name, "grade": c.grade,
            "head_teacher_id": c.head_teacher_id, "school_id": c.school_id}


def _student_response(s) -> dict:
    return {"id": s.id, "name": s.name, "student_number": s.student_number,
            "class_id": s.class_id, "school_id": s.school_id}


@router.get("/classes")
async def list_classes(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    classes = await student_service.list_classes(
        db, school_id=role.school_id,
        visible_class_ids=get_visible_class_ids(role),
    )
    return [_class_response(c) for c in classes]


@router.get("/students")
async def list_students(
    class_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    students = await student_service.list_students(
        db, school_id=role.school_id, class_id=class_id,
        visible_class_ids=get_visible_class_ids(role),
    )
    return [_student_response(s) for s in students]


@router.post("/students/import", status_code=201)
async def import_students(
    file: UploadFile = File(...),
    class_id: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    content = await file.read()
    return await student_service.import_students(
        db, school_id=role.school_id, class_id=class_id,
        file_content=content, filename=file.filename or "",
        visible_class_ids=get_visible_class_ids(role),
    )
