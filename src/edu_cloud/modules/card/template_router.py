"""Template 路由 — 从 exam-ai 迁入。"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import get_current_user
from edu_cloud.core.tenant import get_school_id
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.exam.models import Subject

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


class TemplateBody(BaseModel):
    image_width: int
    image_height: int
    anchors: list[dict]
    regions: list[dict]
    sample_image: str | None = None


def _template_response(t: Template) -> dict:
    return {
        "id": t.id, "subject_id": t.subject_id, "side": t.side,
        "image_width": t.image_width, "image_height": t.image_height,
        "anchors": t.anchors, "regions": t.regions, "sample_image": t.sample_image,
    }


@router.put("/{subject_id}/{side}")
async def upsert_template(
    subject_id: str,
    side: Literal["A", "B"],
    body: TemplateBody,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    school_id = get_school_id(current)

    # D2: conditional Subject filter — admin (school_id=None) sees all schools
    subj_stmt = select(Subject).where(Subject.id == subject_id)
    if school_id:
        subj_stmt = subj_stmt.where(Subject.school_id == school_id)
    result = await db.execute(subj_stmt)
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")
    # Use subject's actual school_id for Template ownership
    effective_school_id = subject.school_id

    tpl_stmt = select(Template).where(
        Template.subject_id == subject_id, Template.side == side,
        Template.school_id == effective_school_id,
    )
    result = await db.execute(tpl_stmt)
    template = result.scalar_one_or_none()
    is_update = template is not None
    if template:
        template.image_width = body.image_width
        template.image_height = body.image_height
        template.anchors = body.anchors
        template.regions = body.regions
        template.sample_image = body.sample_image
    else:
        template = Template(
            subject_id=subject_id, side=side,
            image_width=body.image_width, image_height=body.image_height,
            anchors=body.anchors, regions=body.regions,
            sample_image=body.sample_image, school_id=effective_school_id,
        )
        db.add(template)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Template already exists, retry")
    await db.refresh(template)
    logger.info("upsert_template: id=%s, subject=%s, side=%s, action=%s",
                template.id, subject_id, side, "update" if is_update else "create")
    return _template_response(template)


@router.get("/{subject_id}/{side}")
async def get_template(
    subject_id: str,
    side: Literal["A", "B"],
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    # D2: conditional Template filter — admin (school_id=None) sees all schools
    school_id = get_school_id(current)
    tpl_stmt = select(Template).where(
        Template.subject_id == subject_id, Template.side == side,
    )
    if school_id:
        tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
    result = await db.execute(tpl_stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "Template not found")
    return _template_response(template)


@router.get("/{subject_id}")
async def list_templates(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    # D2: conditional Template filter — admin (school_id=None) sees all schools
    school_id = get_school_id(current)
    tpl_stmt = select(Template).where(Template.subject_id == subject_id)
    if school_id:
        tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
    result = await db.execute(tpl_stmt)
    return [_template_response(t) for t in result.scalars()]
