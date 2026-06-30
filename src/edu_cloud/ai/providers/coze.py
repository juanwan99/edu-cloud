"""Coze Studio provider for the edu-cloud chat SSE contract."""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from edu_cloud.ai.providers.base import AgentProviderContext
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.tool_gateway import describe_context_tools, execute_registered_tool, register_tool_context

logger = logging.getLogger(__name__)

DEFAULT_COZE_TOOL_ALLOWLIST = frozenset({
    "get_exam_list",
    "get_exam_summary",
    "get_class_report",
    "get_class_list",
    "get_knowledge_tree",
    "list_homework_tasks",
    "get_homework_stats",
    "generate_comment",
})

CONFIRMATION_TIMEOUT_SECONDS = 300.0
COZE_REQUIRED_ACTION_EVENTS = frozenset({
    "conversation.chat.requires_action",
    "conversation.chat.required_action",
})
COZE_REQUIRED_ACTION_UNSUPPORTED_MESSAGE = (
    "当前 Coze CE 运行态未验证可用的 OpenAPI 工具结果回传接口；"
    "请先使用 Coze HTTP 插件回调到 edu Tool Gateway。"
)


class CozeRun:
    provider_name = "coze"

    def __init__(self, context: AgentProviderContext, settings: Any) -> None:
        self._context = context
        self._settings = settings
        self._provider_state = context.provider_state
        self._run_id = uuid.uuid4().hex[:16]
        self._last_messages: list[Any] = []
        self._tool_context_token = register_tool_context(context)
        self._pending_confirmations: dict[str, dict[str, Any]] = {}

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def last_messages(self) -> list[Any]:
        return self._last_messages

    def is_confirmation_expired(self, confirmation_id: str) -> bool:
        pending = self._pending_confirmations.get(confirmation_id)
        if not pending:
            return True
        return (time.monotonic() - pending["requested_at"]) > pending["timeout"]

    async def resume_after_confirmation(
        self,
        *,
        approved_ids: list[str],
        denied_ids: list[str] | None = None,
        message_history: list[Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        persistence = {"status": "ok"}
        for confirmation_id in denied_ids or []:
            pending = self._pending_confirmations.pop(confirmation_id, None)
            if pending:
                yield AgentEvent(type="answer", data={"content": f"已拒绝执行 {pending['tool_name']}。"})

        for confirmation_id in approved_ids:
            pending = self._pending_confirmations.get(confirmation_id)
            if not pending:
                yield AgentEvent(type="error", data={"message": "No pending confirmation"})
                continue
            if self.is_confirmation_expired(confirmation_id):
                self._pending_confirmations.pop(confirmation_id, None)
                yield AgentEvent(type="error", data={"message": "确认已超时（5 分钟），操作未执行"})
                continue

            tool_name = pending["tool_name"]
            arguments = pending["arguments"]
            assistant_parts: list[str] = []
            emitted_delta_ids: set[str] = set()
            is_coze_required_action_confirmation = bool(
                pending.get("coze_conversation_id")
                and pending.get("coze_chat_id")
                and pending.get("coze_tool_call_id")
            )
            if is_coze_required_action_confirmation and not self._required_action_submit_ready():
                yield self._required_action_unavailable_event()
                continue

            yield AgentEvent(type="tool_call", data={"tool": tool_name, "arguments": arguments})
            try:
                result = await execute_registered_tool(
                    context_token=self._tool_context_token,
                    tool_name=tool_name,
                    arguments=arguments,
                    allow_write=True,
                )
                self._pending_confirmations.pop(confirmation_id, None)
                yield AgentEvent(type="tool_result", data={"tool": tool_name, "result": result.get("result")})
                if is_coze_required_action_confirmation:
                    tool_outputs = list(pending.get("prior_tool_outputs") or [])
                    tool_outputs.append({
                        "tool_call_id": pending["coze_tool_call_id"],
                        "output": json.dumps(result.get("result"), ensure_ascii=False),
                    })
                    async for event in self._stream_and_map(
                        self._stream_coze_tool_outputs(
                            conversation_id=pending["coze_conversation_id"],
                            chat_id=pending["coze_chat_id"],
                            tool_outputs=tool_outputs,
                        ),
                        emitted_delta_ids,
                        assistant_parts,
                    ):
                        yield event
                    if assistant_parts:
                        assistant_text = "".join(assistant_parts).strip()
                        self._last_messages = [
                            {"role": "assistant", "content": assistant_text},
                        ]
                        persistence = await self._persist_assistant_message(assistant_text)
                else:
                    assistant_text = f"已执行 {tool_name}。"
                    persistence = await self._persist_assistant_message(assistant_text)
                    yield AgentEvent(type="answer", data={"content": assistant_text})
            except Exception as exc:
                logger.exception("Confirmed Coze tool execution failed: %s", exc)
                yield AgentEvent(type="error", data={"message": str(exc)})

        yield AgentEvent(type="done", data={
            "run_id": self._run_id,
            "session_id": self._context.session_id,
            "provider": self.provider_name,
            "persistence": persistence,
        })

    async def run(
        self,
        user_message: str,
        *,
        message_history: list[Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        assistant_parts: list[str] = []
        emitted_delta_ids: set[str] = set()
        yield AgentEvent(type="thinking", data={"content": ""})

        try:
            async for item in self._stream_and_map(
                self._stream_coze(user_message),
                emitted_delta_ids,
                assistant_parts,
            ):
                yield item
        except Exception as exc:
            logger.exception("Coze chat failed: %s", exc)
            yield AgentEvent(
                type="error",
                data={"message": "Coze AI 服务暂时不可用，已保留回退入口", "retryable": True},
            )

        assistant_text = "".join(assistant_parts).strip() or None
        persistence = await self._persist_messages(user_message, assistant_text)
        self._last_messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_text or ""},
        ]
        yield AgentEvent(type="done", data={
            "run_id": self._run_id,
            "session_id": self._context.session_id,
            "provider": self.provider_name,
            "persistence": persistence,
        })

    async def _stream_coze(self, user_message: str) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        url = self._settings.AI_COZE_API_BASE.rstrip("/") + "/v3/chat"
        conversation_id = self._provider_state.get("coze_conversation_id")
        if conversation_id:
            url += "?" + urlencode({"conversation_id": conversation_id})
        async for item in self._stream_sse(url, self._build_chat_payload(user_message)):
            yield item

    async def _stream_coze_tool_outputs(
        self,
        *,
        conversation_id: str,
        chat_id: str,
        tool_outputs: list[dict[str, str]],
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        query = urlencode({"conversation_id": conversation_id, "chat_id": chat_id})
        url = self._settings.AI_COZE_API_BASE.rstrip("/") + f"/v3/chat/submit_tool_outputs?{query}"
        payload = {
            "tool_outputs": tool_outputs,
            "stream": True,
            "auto_save_history": True,
        }
        async for item in self._stream_sse(url, payload):
            yield item

    async def _stream_sse(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        event_name = ""
        timeout = httpx.Timeout(float(self._settings.AI_COZE_TIMEOUT), connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=self._headers(), json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        event_name = line.split(":", 1)[1].strip()
                        continue
                    if not line.startswith("data:"):
                        continue
                    raw = line.split(":", 1)[1].strip()
                    if not raw:
                        continue
                    if raw.strip('"') == "[DONE]":
                        yield "done", {}
                        continue
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("Malformed Coze SSE data: %s", raw[:200])
                        continue
                    if data == "[DONE]":
                        yield "done", {}
                        continue
                    if not isinstance(data, dict):
                        logger.warning("Unexpected Coze SSE data type: %s", type(data).__name__)
                        continue
                    self._remember_conversation(data)
                    yield event_name, data

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.AI_COZE_API_TOKEN}",
            "Content-Type": "application/json",
        }

    def _build_chat_payload(self, user_message: str) -> dict[str, Any]:
        return {
            "bot_id": self._settings.AI_COZE_BOT_ID,
            "user_id": self._context.user_id,
            "stream": True,
            "auto_save_history": True,
            "additional_messages": [{
                "role": "user",
                "content": self._build_user_content(user_message),
                "content_type": "text",
            }],
        }

    def _remember_conversation(self, payload: dict[str, Any]) -> None:
        conversation_id = payload.get("conversation_id")
        if conversation_id:
            self._provider_state["coze_conversation_id"] = conversation_id

    def _build_user_content(self, user_message: str) -> str:
        tool_context = {
            "tool_context_token": self._tool_context_token,
            "allowed_tools": self._context.tool_names,
            "tool_gateway": self._tool_gateway_url(),
            "tool_list": self._tool_list_url(),
            "auth_header": "X-AI-Tool-Token",
            "request_body": {
                "context_token": self._tool_context_token,
                "arguments": {},
            },
            "tools": describe_context_tools(self._context)["tools"],
        }
        return (
            "[edu-cloud tool boundary]\n"
            + json.dumps(tool_context, ensure_ascii=False)
            + "\n\n"
            + user_message
        )

    def _tool_gateway_url(self) -> str:
        return self._tool_gateway_base() + "/internal/ai-tools/{tool_name}"

    def _tool_list_url(self) -> str:
        return self._tool_gateway_base() + f"/internal/ai-tools?context_token={self._tool_context_token}"

    def _tool_gateway_base(self) -> str:
        base = str(getattr(self._settings, "AI_TOOL_GATEWAY_PUBLIC_BASE", "") or "").strip().rstrip("/")
        return base

    def _map_event(
        self,
        event: str,
        payload: dict[str, Any],
        emitted_delta_ids: set[str],
        assistant_parts: list[str],
    ) -> list[AgentEvent]:
        if event == "conversation.message.delta" and payload.get("type") == "answer":
            content = payload.get("content") or ""
            if content:
                emitted_delta_ids.add(str(payload.get("id", "")))
                assistant_parts.append(content)
                return [AgentEvent(type="answer", data={"content": content})]
            return []

        if event == "conversation.message.completed":
            msg_type = payload.get("type")
            content = payload.get("content") or ""
            if msg_type == "answer" and str(payload.get("id", "")) not in emitted_delta_ids and content:
                assistant_parts.append(content)
                return [AgentEvent(type="answer", data={"content": content})]
            if msg_type == "function_call":
                tool_name, arguments = _parse_function_call(content)
                return [AgentEvent(type="tool_call", data={"tool": tool_name, "arguments": arguments})]
            if msg_type in {"tool_response", "tool_output"}:
                return self._map_tool_response(content)
            if msg_type in {"knowledge", "verbose"}:
                return [AgentEvent(type="thinking", data={"content": ""})]

        if event == "conversation.chat.failed" or event == "error":
            msg = payload.get("msg") or payload.get("message") or "Coze chat failed"
            return [AgentEvent(type="error", data={"message": msg, "retryable": True})]

        if event in COZE_REQUIRED_ACTION_EVENTS:
            return [self._required_action_unavailable_event()]

        return []

    async def _stream_and_map(
        self,
        source: AsyncIterator[tuple[str, dict[str, Any]]],
        emitted_delta_ids: set[str],
        assistant_parts: list[str],
        *,
        depth: int = 0,
    ) -> AsyncIterator[AgentEvent]:
        async for event, payload in source:
            if event in COZE_REQUIRED_ACTION_EVENTS:
                if not self._required_action_submit_ready():
                    yield self._required_action_unavailable_event()
                    continue
                async for item in self._handle_required_action(
                    payload,
                    emitted_delta_ids,
                    assistant_parts,
                    depth=depth,
                ):
                    yield item
                continue
            mapped = self._map_event(event, payload, emitted_delta_ids, assistant_parts)
            for item in mapped:
                yield item

    def _required_action_submit_ready(self) -> bool:
        return bool(getattr(self._settings, "AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED", False))

    def _required_action_unavailable_event(self) -> AgentEvent:
        return AgentEvent(
            type="error",
            data={
                "message": COZE_REQUIRED_ACTION_UNSUPPORTED_MESSAGE,
                "retryable": False,
                "mode": "coze_required_action",
            },
        )

    async def _handle_required_action(
        self,
        payload: dict[str, Any],
        emitted_delta_ids: set[str],
        assistant_parts: list[str],
        *,
        depth: int = 0,
    ) -> AsyncIterator[AgentEvent]:
        if depth >= 3:
            yield AgentEvent(type="error", data={"message": "Coze tool recursion limit reached", "retryable": False})
            return

        conversation_id = str(payload.get("conversation_id") or "")
        chat_id = str(payload.get("id") or payload.get("chat_id") or "")
        tool_calls = (
            payload.get("required_action", {})
            .get("submit_tool_outputs", {})
            .get("tool_calls", [])
        )
        if not conversation_id or not chat_id or not isinstance(tool_calls, list):
            yield AgentEvent(type="error", data={"message": "Malformed Coze required_action payload", "retryable": False})
            return

        tool_outputs: list[dict[str, str]] = []
        for tool_call in tool_calls:
            tool_call_id, tool_name, arguments = _parse_required_tool_call(tool_call)
            if not tool_call_id or not tool_name:
                yield AgentEvent(type="error", data={"message": "Malformed Coze tool call", "retryable": False})
                return

            yield AgentEvent(type="tool_call", data={"tool": tool_name, "arguments": arguments})
            try:
                result = await execute_registered_tool(
                    context_token=self._tool_context_token,
                    tool_name=tool_name,
                    arguments=arguments,
                )
            except Exception as exc:
                logger.exception("Coze required_action tool failed: %s", exc)
                yield AgentEvent(type="error", data={"message": str(exc), "retryable": False})
                return

            if result.get("status") == "confirmation_required":
                confirmation_id = str(result.get("confirmation_id") or uuid.uuid4().hex)
                self._pending_confirmations[confirmation_id] = {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "requested_at": time.monotonic(),
                    "timeout": CONFIRMATION_TIMEOUT_SECONDS,
                    "coze_conversation_id": conversation_id,
                    "coze_chat_id": chat_id,
                    "coze_tool_call_id": tool_call_id,
                    "prior_tool_outputs": tool_outputs.copy(),
                }
                expires_at = (
                    datetime.now(timezone.utc) + timedelta(seconds=CONFIRMATION_TIMEOUT_SECONDS)
                ).isoformat()
                yield AgentEvent(
                    type="confirmation_required",
                    data={
                        "run_id": self._run_id,
                        "tool_call_id": confirmation_id,
                        "tool_name": tool_name,
                        "args": arguments,
                        "expires_at": expires_at,
                    },
                )
                return

            yield AgentEvent(type="tool_result", data={"tool": tool_name, "result": result.get("result")})
            tool_outputs.append({
                "tool_call_id": tool_call_id,
                "output": json.dumps(result.get("result"), ensure_ascii=False),
            })

        async for item in self._stream_and_map(
            self._stream_coze_tool_outputs(
                conversation_id=conversation_id,
                chat_id=chat_id,
                tool_outputs=tool_outputs,
            ),
            emitted_delta_ids,
            assistant_parts,
            depth=depth + 1,
        ):
            yield item

    def _map_tool_response(self, content: str) -> list[AgentEvent]:
        data = _parse_json_object(content)
        if data.get("status") == "confirmation_required":
            confirmation_id = str(data.get("confirmation_id") or uuid.uuid4().hex)
            tool_name = str(data.get("tool") or data.get("tool_name") or "unknown")
            arguments = data.get("arguments") if isinstance(data.get("arguments"), dict) else {}
            timeout = CONFIRMATION_TIMEOUT_SECONDS
            self._pending_confirmations[confirmation_id] = {
                "tool_name": tool_name,
                "arguments": arguments,
                "requested_at": time.monotonic(),
                "timeout": timeout,
            }
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=timeout)).isoformat()
            return [AgentEvent(
                type="confirmation_required",
                data={
                    "run_id": self._run_id,
                    "tool_call_id": confirmation_id,
                    "tool_name": tool_name,
                    "args": arguments,
                    "expires_at": expires_at,
                },
            )]
        return [AgentEvent(type="tool_result", data={"tool": _tool_name_from_output(content)})]

    async def _persist_messages(self, user_message: str, assistant_output: str | None) -> dict[str, str]:
        try:
            from edu_cloud.ai.models import AiChatMessage
            async with self._context.db_sessionmaker() as db:
                db.add(AiChatMessage(session_id=self._context.session_id, role_in_chat="user", content=user_message))
                if assistant_output:
                    db.add(AiChatMessage(
                        session_id=self._context.session_id,
                        role_in_chat="assistant",
                        content=assistant_output,
                        metadata_json=json.dumps({"provider": self.provider_name}, ensure_ascii=False),
                    ))
                await db.commit()
            return {"status": "ok"}
        except Exception as exc:
            logger.warning("Failed to persist Coze chat messages: %s", exc)
            return {"status": "failed", "reason": "chat_history_unavailable"}

    async def _persist_assistant_message(self, assistant_output: str | None) -> dict[str, str]:
        if not assistant_output:
            return {"status": "ok"}
        try:
            from edu_cloud.ai.models import AiChatMessage
            async with self._context.db_sessionmaker() as db:
                db.add(AiChatMessage(
                    session_id=self._context.session_id,
                    role_in_chat="assistant",
                    content=assistant_output,
                    metadata_json=json.dumps({"provider": self.provider_name}, ensure_ascii=False),
                ))
                await db.commit()
            return {"status": "ok"}
        except Exception as exc:
            logger.warning("Failed to persist Coze assistant message: %s", exc)
            return {"status": "failed", "reason": "chat_history_unavailable"}


class CozeProvider:
    name = "coze"

    def __init__(self, settings: Any) -> None:
        self._settings = settings

    def is_available(self) -> bool:
        return bool(
            self._settings.AI_COZE_ENABLED
            and self._settings.AI_COZE_API_BASE
            and self._settings.AI_COZE_BOT_ID
            and self._settings.AI_COZE_API_TOKEN
        )

    async def create_run(self, context: AgentProviderContext) -> CozeRun:
        return CozeRun(_filter_context_tools(context, self._settings), self._settings)


def _parse_function_call(content: str) -> tuple[str, dict[str, Any]]:
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return "unknown", {"raw": content}
    return str(data.get("name") or data.get("tool_name") or "unknown"), data.get("arguments") or {}


def _parse_required_tool_call(tool_call: Any) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(tool_call, dict):
        return "", "", {}
    function = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
    arguments = function.get("arguments") or {}
    if isinstance(arguments, str):
        arguments = _parse_json_object(arguments)
    if not isinstance(arguments, dict):
        arguments = {}
    return (
        str(tool_call.get("id") or ""),
        str(function.get("name") or ""),
        arguments,
    )


def _tool_name_from_output(content: str) -> str:
    data = _parse_json_object(content)
    return str(data.get("name") or data.get("tool_name") or data.get("tool") or "unknown")


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _filter_context_tools(context: AgentProviderContext, settings: Any) -> AgentProviderContext:
    allowlist = set(getattr(settings, "AI_COZE_TOOL_ALLOWLIST", None) or DEFAULT_COZE_TOOL_ALLOWLIST)
    allowed_functions = []
    for fn in context.tool_functions:
        meta = getattr(fn, "_edu_meta", None)
        if meta and meta.name in allowlist:
            allowed_functions.append(fn)
    allowed_names = [
        getattr(fn, "_edu_meta").name
        for fn in allowed_functions
        if getattr(fn, "_edu_meta", None)
    ]
    return replace(context, tool_functions=allowed_functions, tool_names=allowed_names)
