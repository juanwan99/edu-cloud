"""Conduct parent API routes — register, login, bind child, query children."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from edu_cloud.database import get_db
from edu_cloud.core.auth import get_current_user
from edu_cloud.core.rate_limit import limiter
from edu_cloud.modules.conduct.schemas import (
    InviteCodeInfo,
    ParentRegisterRequest,
    ParentLoginRequest,
    ParentBindRequest,
)
from edu_cloud.modules.conduct import parent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/conduct", tags=["conduct-parent"])


@router.get("/invite/{code}/info", response_model=InviteCodeInfo)
async def invite_code_info(code: str, db: AsyncSession = Depends(get_db)):
    """Public: validate invite code and return class/school info."""
    return await parent_service.get_invite_info(db, code)


@router.post("/parent/register")
async def parent_register(
    body: ParentRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public: register a parent account with invite code."""
    return await parent_service.register_parent(
        db,
        phone=body.phone,
        display_name=body.display_name,
        password=body.password,
        invite_code=body.invite_code,
        relationship=body.relationship,
    )


@router.post("/parent/login")
@limiter.limit("5/minute")
async def parent_login(
    request: Request,
    body: ParentLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public: login as parent with phone + password."""
    return await parent_service.login_parent(db, body.phone, body.password)


@router.get("/parent/me")
async def parent_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current parent info + children list."""
    user = current_user["user"]
    children = await parent_service.get_children(db, user.id)
    return {
        "user_id": user.id,
        "display_name": user.display_name,
        "phone": user.phone,
        "children": children,
    }


@router.post("/parent/bind")
async def parent_bind(
    body: ParentBindRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bind parent to a student after identity verification."""
    user = current_user["user"]
    return await parent_service.bind_child(
        db,
        user_id=user.id,
        class_id=body.class_id,
        student_name=body.student_name,
        verify_code=body.verify_code,
        relationship=body.relationship,
    )


@router.get("/parent/children")
async def parent_children(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of bound children with conduct points."""
    user = current_user["user"]
    return await parent_service.get_children(db, user.id)


@router.get("/parent/children/{student_id}/behavior-summary")
async def get_child_behavior_summary(
    student_id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get simplified behavior summary for a bound child (parent-facing)."""
    return await parent_service.get_child_behavior_summary(
        db, current_user["user"].id, student_id, days=days,
    )


@router.get("/parent/children/{student_id}/records")
async def get_child_records(
    student_id: str,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get paginated conduct records for a bound child."""
    return await parent_service.get_child_records(
        db, current_user["user"].id, student_id, page, size,
    )


@router.get("/parent/children/{student_id}/rankings")
async def get_child_rankings(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get class rankings for a bound child."""
    return await parent_service.get_child_rankings(
        db, current_user["user"].id, student_id,
    )


@router.get("/parent/classes/{class_id}/rules")
async def get_class_rules(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get class rules (categories + items)."""
    return await parent_service.get_class_rules(
        db, current_user["user"].id, class_id,
    )


@router.get("/parent/children/{student_id}/exams")
async def get_child_exams(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get list of exams the child participated in."""
    return await parent_service.get_child_exams(
        db, current_user["user"].id, student_id,
    )


@router.get("/parent/children/{student_id}/scores")
async def get_child_scores(
    student_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get child's exam score snapshots (all subjects)."""
    return await parent_service.get_child_scores(
        db, current_user["user"].id, student_id, limit=limit,
    )


@router.get("/parent/children/{student_id}/error-book")
async def get_child_error_book(
    student_id: str,
    mastery_status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get child's error book entries + stats."""
    return await parent_service.get_child_error_book(
        db, current_user["user"].id, student_id,
        mastery_status=mastery_status, limit=limit,
    )


@router.put("/parent/profile")
async def update_parent_profile(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update parent profile (display_name only)."""
    return await parent_service.update_parent_profile(
        db, current_user["user"].id, data,
    )


@router.put("/parent/password")
async def change_parent_password(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Change parent password."""
    return await parent_service.change_parent_password(
        db, current_user["user"].id, data["old_password"], data["new_password"],
    )
