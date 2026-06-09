"""Fallback provider backed by the existing EduAgentRuntime."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from edu_cloud.ai.engine.edu_runtime import EduAgentRuntime
from edu_cloud.ai.providers.base import AgentProviderContext
from edu_cloud.ai.schemas import AgentEvent


class CurrentPydanticRun:
    provider_name = "current_pydantic"

    def __init__(self, runtime: EduAgentRuntime) -> None:
        self._runtime = runtime

    @property
    def run_id(self) -> str:
        return self._runtime.run_id

    @property
    def last_messages(self) -> list[Any]:
        return self._runtime.last_messages

    def is_confirmation_expired(self, confirmation_id: str) -> bool:
        return self._runtime.deps.confirmations.is_expired(confirmation_id)

    async def run(
        self,
        user_message: str,
        *,
        message_history: list[Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        async for event in self._runtime.run(user_message, message_history=message_history):
            yield event

    async def resume_after_confirmation(
        self,
        *,
        approved_ids: list[str],
        denied_ids: list[str] | None = None,
        message_history: list[Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        async for event in self._runtime.resume_after_confirmation(
            approved_ids=approved_ids,
            denied_ids=denied_ids,
            message_history=message_history,
        ):
            yield event


class CurrentPydanticProvider:
    name = "current_pydantic"

    def is_available(self) -> bool:
        return True

    async def create_run(self, context: AgentProviderContext) -> CurrentPydanticRun:
        runtime = EduAgentRuntime(
            db_sessionmaker=context.db_sessionmaker,
            user_id=context.user_id,
            school_id=context.school_id,
            role=context.role,
            data_scope=context.data_scope,
            enabled_modules=context.enabled_modules,
            capabilities=context.capabilities,
            anonymizer=context.anonymizer,
            memory=context.memory,
            session_id=context.session_id,
            system_prompt=context.system_prompt,
            tool_meta_registry=context.tool_meta_registry,
            tool_functions=context.tool_functions,
        )
        runtime.build_agent()
        return CurrentPydanticRun(runtime)
