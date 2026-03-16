import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.models.platform_user import PlatformUser
from edu_cloud.shared.auth import create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PlatformUser).where(PlatformUser.username == req.username)
    )
    user = result.scalar_one_or_none()
    if not user or not user.verify_password(req.password):
        logger.warning("login failed: username=%s", req.username)
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token({"sub": user.id, "role": user.role})
    logger.info("login ok: user=%s, role=%s", req.username, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
        },
    }
