"""学校管理服务。"""
import secrets
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import RegisteredSchool
from edu_cloud.services.exceptions import NotFoundError, ConflictError


class SchoolService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_school(
        self, name: str, code: str, district: str
    ) -> tuple[RegisteredSchool, str]:
        # Check uniqueness
        existing = (
            await self.db.execute(
                select(RegisteredSchool).where(RegisteredSchool.code == code)
            )
        ).scalar_one_or_none()
        if existing:
            raise ConflictError(f"School code '{code}' already exists")

        secret = secrets.token_urlsafe(32)
        api_key_hash = bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()
        plaintext_key = f"{code}:{secret}"

        school = RegisteredSchool(
            name=name, code=code, district=district, api_key_hash=api_key_hash,
        )
        self.db.add(school)
        await self.db.commit()
        await self.db.refresh(school)
        return school, plaintext_key

    async def list_schools(
        self, district: str | None = None, is_active: bool | None = None,
    ) -> list[RegisteredSchool]:
        q = select(RegisteredSchool)
        if district is not None:
            q = q.where(RegisteredSchool.district == district)
        if is_active is not None:
            q = q.where(RegisteredSchool.is_active == is_active)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_school(self, school_id: str) -> RegisteredSchool:
        result = await self.db.execute(
            select(RegisteredSchool).where(RegisteredSchool.id == school_id)
        )
        school = result.scalar_one_or_none()
        if not school:
            raise NotFoundError(f"School '{school_id}' not found")
        return school

    async def update_school(self, school_id: str, **fields) -> RegisteredSchool:
        school = await self.get_school(school_id)
        for key, value in fields.items():
            if hasattr(school, key):
                setattr(school, key, value)
        await self.db.commit()
        await self.db.refresh(school)
        return school

    async def rotate_api_key(self, school_id: str) -> str:
        school = await self.get_school(school_id)
        secret = secrets.token_urlsafe(32)
        school.api_key_hash = bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()
        await self.db.commit()
        return f"{school.code}:{secret}"
