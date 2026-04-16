from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.agent_profile import AgentProfile, AgentRun


class AgentProfileService:
    @staticmethod
    async def get_or_create(
        db: AsyncSession, *, user_id: str, school_id: str, display_name: str
    ) -> AgentProfile:
        stmt = select(AgentProfile).where(
            AgentProfile.owner_user_id == user_id,
            AgentProfile.school_id == school_id,
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile:
            return profile
        profile = AgentProfile(
            owner_user_id=user_id,
            school_id=school_id,
            profile_type="employee",
            display_name=display_name,
        )
        db.add(profile)
        await db.flush()
        return profile

    @staticmethod
    async def record_run(
        db: AsyncSession,
        *,
        profile_id: str,
        session_id: str,
        tools_resolved: list[str],
        tools_selected: list[str],
        model_used: str,
        model_tier: str,
        intent_domains: list[str],
        token_input: int = 0,
        token_output: int = 0,
    ) -> AgentRun:
        run = AgentRun(
            profile_id=profile_id,
            session_id=session_id,
            tools_resolved=tools_resolved,
            tools_selected=tools_selected,
            model_used=model_used,
            model_tier=model_tier,
            intent_domains=intent_domains,
            token_input=token_input,
            token_output=token_output,
        )
        db.add(run)
        await db.flush()
        return run
