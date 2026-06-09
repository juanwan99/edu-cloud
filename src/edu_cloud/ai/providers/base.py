"""Provider contracts for edu-cloud AI chat.

The provider layer keeps the public /api/v1/ai/chat SSE contract stable while
allowing the reasoning engine to change underneath it.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from edu_cloud.ai.schemas import AgentEvent


@dataclass(slots=True)
class AgentProviderContext:
    """Immutable request context shared by provider implementations."""

    db_sessionmaker: Any
    user_id: str
    school_id: str
    role: str
    data_scope: Any
    enabled_modules: frozenset[str]
    capabilities: dict[tuple[str, str], bool]
    anonymizer: Any
    memory: Any
    session_id: str
    system_prompt: str
    tool_meta_registry: dict[str, Any]
    tool_functions: list[Any]
    tool_names: list[str]
    provider_state: dict[str, Any]


class AgentRunHandle(Protocol):
    """A single provider-backed chat run stored in the hot session cache."""

    provider_name: str

    @property
    def run_id(self) -> str:
        ...

    @property
    def last_messages(self) -> list[Any]:
        ...

    def is_confirmation_expired(self, confirmation_id: str) -> bool:
        ...

    async def run(
        self,
        user_message: str,
        *,
        message_history: list[Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        ...

    async def resume_after_confirmation(
        self,
        *,
        approved_ids: list[str],
        denied_ids: list[str] | None = None,
        message_history: list[Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        ...


class AgentProvider(Protocol):
    """Factory for provider-backed runs."""

    name: str

    def is_available(self) -> bool:
        ...

    async def create_run(self, context: AgentProviderContext) -> AgentRunHandle:
        ...


class AgentProviderUnavailable(RuntimeError):
    """Raised when no configured provider can serve a chat request."""
