import json
import logging
import time
from typing import AsyncGenerator

from edu_cloud.ai.anonymizer import Anonymizer
from edu_cloud.ai.context import build_system_prompt
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.schemas import AgentEvent, ChatMessage, ToolCall  # noqa: F401
from edu_cloud.config import settings

logger = logging.getLogger(__name__)

# Maps each role to the tool categories it may access.
# None means unrestricted (all categories).
ROLE_TOOL_CATEGORIES: dict[str, list[str] | None] = {
    "platform_admin": None,  # all categories
    "district_admin": ["L2_cross_school"],
    "principal": ["L1_analytics", "L2_cross_school", "L4_action"],
    "academic_director": ["L1_analytics", "L2_cross_school", "L4_action"],
    "grade_leader": ["L1_analytics", "L4_action"],
    "homeroom_teacher": ["L1_analytics", "L4_action"],
    "subject_teacher": ["L1_analytics", "L4_action"],
}


class Agent:
    """ReAct loop engine.

    Yields :class:`AgentEvent` objects as the conversation progresses:
    - ``tool_call``  — LLM decided to invoke a tool
    - ``tool_result`` — tool execution completed (real names retained for UI)
    - ``answer``     — final answer to the user (student names de-anonymized)
    - ``error``      — unrecoverable error (LLM failure)
    """

    def __init__(
        self,
        llm,
        registry: ToolRegistry,
        max_steps: int | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.max_steps = max_steps if max_steps is not None else settings.LLM_MAX_STEPS

    async def run(
        self,
        user_message: str,
        session_id: str,
        db,
        school_id,
        class_ids,
        role: str,
        display_name: str,
        scope: dict,
        audit=None,
        user_id: str = "",
    ) -> AsyncGenerator[AgentEvent, None]:
        # ── 1. Determine tools available to this role ──────────────────────
        # Roles not in the mapping get an empty list (no tool access).
        categories: list[str] | None = ROLE_TOOL_CATEGORIES.get(role, [])
        tool_schemas = self.registry.get_schemas(categories=categories)
        tool_names = [s["function"]["name"] for s in tool_schemas]

        # ── 2. System prompt ────────────────────────────────────────────────
        system_prompt = build_system_prompt(role, display_name, scope, tool_names)

        # ── 3. Initial message list ─────────────────────────────────────────
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]

        # ── 4. Per-session anonymizer ───────────────────────────────────────
        anonymizer = Anonymizer()

        # ── 5. ReAct loop ───────────────────────────────────────────────────
        for step in range(self.max_steps):
            logger.debug(
                "Agent step %d/%d  session=%s role=%s",
                step + 1,
                self.max_steps,
                session_id,
                role,
            )

            # --- Call LLM ---------------------------------------------------
            try:
                response: ChatMessage = await self.llm.chat(
                    messages,
                    tools=tool_schemas if tool_schemas else None,
                )
            except Exception as exc:  # pragma: no cover — tested via mock
                logger.error("LLM call failed at step %d: %s", step + 1, exc)
                yield AgentEvent(
                    type="error",
                    data={"message": f"AI 服务暂时不可用: {exc}"},
                )
                return

            # --- No tool calls → final answer --------------------------------
            if not response.tool_calls:
                content: str = response.content or "抱歉，我无法回答这个问题。"
                content = anonymizer.deanonymize(content)
                yield AgentEvent(type="answer", data={"content": content})
                return

            # --- Tool calls → execute each ----------------------------------
            messages.append(response)

            for tc in response.tool_calls:
                yield AgentEvent(
                    type="tool_call",
                    data={"tool": tc.name, "arguments": tc.arguments},
                )

                # Execute tool
                t0 = time.monotonic()
                try:
                    result = await self.registry.execute(
                        tc.name,
                        tc.arguments,
                        _db=db,
                        _school_id=school_id,
                        _class_ids=class_ids,
                        _user_id=user_id,
                    )
                except Exception as exc:
                    logger.error("Tool %s failed: %s", tc.name, exc)
                    result = {"error": str(exc)}
                duration_ms = int((time.monotonic() - t0) * 1000)

                # Persist audit record
                if audit is not None:
                    try:
                        result_str_for_audit = json.dumps(result, ensure_ascii=False, default=str)
                        await audit.log_tool_call(
                            session_id=session_id,
                            user_id=user_id,
                            role=role,
                            tool=tc.name,
                            arguments=json.dumps(tc.arguments, ensure_ascii=False),
                            result=result_str_for_audit,
                            duration_ms=duration_ms,
                        )
                    except Exception as audit_exc:
                        logger.warning("Audit log_tool_call failed: %s", audit_exc)

                # Yield raw result to frontend (real names intact for display)
                yield AgentEvent(
                    type="tool_result",
                    data={"tool": tc.name, "result": result},
                )

                # Anonymize student names before feeding back to LLM
                student_names = self._extract_names(result)
                anon_result = anonymizer.anonymize_data(result, student_names)
                result_str = json.dumps(anon_result, ensure_ascii=False, default=str)

                messages.append(
                    ChatMessage(
                        role="tool",
                        content=result_str,
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

        # ── Exceeded max_steps ──────────────────────────────────────────────
        logger.warning(
            "Agent exceeded max_steps=%d  session=%s", self.max_steps, session_id
        )
        yield AgentEvent(
            type="answer",
            data={"content": "分析步骤过多，请尝试更具体的问题。"},
        )

    @staticmethod
    def _extract_names(data) -> list[str]:
        """Recursively extract student name values from tool result data."""
        names: list[str] = []
        if isinstance(data, dict):
            for key in ("name", "student_name"):
                if key in data and isinstance(data[key], str):
                    names.append(data[key])
            for v in data.values():
                names.extend(Agent._extract_names(v))
        elif isinstance(data, list):
            for item in data:
                names.extend(Agent._extract_names(item))
        return list(set(names))
