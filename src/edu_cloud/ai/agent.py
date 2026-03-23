"""ReAct Agent — 循环执行 LLM→工具→结果→LLM 直到得出最终答案。"""
import json
import logging
import time
from typing import AsyncGenerator

from edu_cloud.ai.anonymizer import Anonymizer
from edu_cloud.ai.context import AgentContext, build_system_prompt
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.schemas import AgentEvent, ChatMessage, ToolCall  # noqa: F401
from edu_cloud.config import settings

logger = logging.getLogger(__name__)

# Maps each role to the tool categories it may access.
# None means unrestricted (all categories).
ROLE_TOOL_CATEGORIES: dict[str, list[str] | None] = {
    "platform_admin": None,  # all categories
    "district_admin": ["L2_cross_school", "L3_knowledge"],
    "principal": ["L1_analytics", "L2_cross_school", "L3_knowledge", "L4_action"],
    "academic_director": ["L1_analytics", "L2_cross_school", "L3_knowledge", "L4_action"],
    "grade_leader": ["L1_analytics", "L3_knowledge", "L4_action"],
    "homeroom_teacher": ["L1_analytics", "L3_knowledge", "L4_action"],
    "subject_teacher": ["L1_analytics", "L3_knowledge", "L4_action"],
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
        self.max_steps = max_steps if max_steps is not None else settings.AI_MAX_STEPS

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
        *,
        context: AgentContext | None = None,
        anonymizer: Anonymizer | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        # ── 1. Determine tools available to this role ──────────────────────
        categories: list[str] | None = ROLE_TOOL_CATEGORIES.get(role, [])
        tool_schemas = self.registry.get_schemas(categories=categories)
        tool_names = [s["function"]["name"] for s in tool_schemas]

        # ── 2. Per-session anonymizer ──────────────────────────────────────
        anonymizer = anonymizer or Anonymizer()

        # ── 3. Context (multi-turn or single-turn) ─────────────────────────
        if context is None:
            system_content = build_system_prompt(role, display_name, scope, tool_names)
            context = AgentContext(system_content=system_content)
        context.add_user_message(user_message, session_id)

        # ── 4. ReAct loop ─────────────────────────────────────────────────
        for step in range(self.max_steps):
            messages = context.build_messages(session_id)

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
                context.add_assistant_message(content, session_id)
                yield AgentEvent(type="answer", data={"content": content})
                return

            # --- Tool calls → execute each ----------------------------------
            context.add_assistant_message(
                response.content, session_id, response.tool_calls
            )

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
                        await audit.log_tool_call(
                            session_id=session_id,
                            user_id=user_id,
                            role=role,
                            tool=tc.name,
                            arguments=json.dumps(tc.arguments, ensure_ascii=False),
                            result=json.dumps(result, ensure_ascii=False, default=str),
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
                anon_result = anonymizer.anonymize(result)
                context.add_tool_result(tc, anon_result, session_id)

        # ── Exceeded max_steps ────────────────────────────────────────────
        logger.warning(
            "Agent exceeded max_steps=%d  session=%s", self.max_steps, session_id
        )
        yield AgentEvent(
            type="answer",
            data={"content": "分析步骤过多，请尝试更具体的问题。"},
        )
