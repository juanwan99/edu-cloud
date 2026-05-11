"""学校管理 REST 端点。"""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.services.school_service import SchoolService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/schools", tags=["schools"])


class CreateSchoolRequest(BaseModel):
    name: str
    code: str
    district: str


class UpdateSchoolRequest(BaseModel):
    name: str | None = None
    district: str | None = None
    is_active: bool | None = None


@router.post("", status_code=201)
async def create_school(
    req: CreateSchoolRequest,
    user=Depends(require_permission(Permission.MANAGE_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    school, plaintext_key = await svc.create_school(
        name=req.name, code=req.code, district=req.district,
    )
    logger.info("school created: code=%s by user=%s", req.code, user["user"].username)
    return {
        "id": school.id, "name": school.name, "code": school.code,
        "district": school.district, "is_active": school.is_active,
        "api_key": plaintext_key,
    }


@router.get("")
async def list_schools(
    district: str | None = None,
    is_active: bool | None = None,
    user=Depends(require_permission(Permission.VIEW_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    schools = await svc.list_schools(district=district, is_active=is_active)
    return [
        {"id": s.id, "name": s.name, "code": s.code, "district": s.district,
         "is_active": s.is_active}
        for s in schools
    ]


@router.get("/{school_id}")
async def get_school(
    school_id: str,
    user=Depends(require_permission(Permission.VIEW_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    s = await svc.get_school(school_id)
    return {
        "id": s.id, "name": s.name, "code": s.code, "district": s.district,
        "is_active": s.is_active,
    }


@router.patch("/{school_id}")
async def update_school(
    school_id: str,
    req: UpdateSchoolRequest,
    user=Depends(require_permission(Permission.MANAGE_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    s = await svc.update_school(school_id, **fields)
    return {
        "id": s.id, "name": s.name, "code": s.code, "district": s.district,
        "is_active": s.is_active,
    }


@router.post("/{school_id}/rotate-key")
async def rotate_key(
    school_id: str,
    user=Depends(require_permission(Permission.MANAGE_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    new_key = await svc.rotate_api_key(school_id)
    logger.info("api key rotated: school=%s by user=%s", school_id, user["user"].username)
    return {"api_key": new_key}
