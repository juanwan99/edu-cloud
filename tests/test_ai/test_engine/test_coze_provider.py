from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from edu_cloud.ai.providers.base import AgentProviderContext
from edu_cloud.ai.engine.tool_wrapper import edu_tool
from edu_cloud.ai.providers.coze import (
    COZE_REQUIRED_ACTION_EVENTS,
    CozeProvider,
    CozeRun,
    PERSISTENCE_FAILURE_CODE,
    PERSISTENCE_FAILURE_MESSAGE,
)


def _run(*, required_action_submit_enabled=False):
    ctx = AgentProviderContext(
        db_sessionmaker=None,
        user_id="u1",
        school_id="s1",
        role="subject_teacher",
        data_scope=None,
        enabled_modules=frozenset({"exam"}),
        capabilities={},
        anonymizer=None,
        memory=None,
        session_id="sess1",
        system_prompt="",
        tool_meta_registry={},
        tool_functions=[],
        tool_names=["get_exam_list"],
        provider_state={},
    )
    settings = SimpleNamespace(
        AI_COZE_API_BASE="http://localhost:8888",
        AI_COZE_API_TOKEN="pat-test",
        AI_COZE_BOT_ID="bot-1",
        AI_COZE_TIMEOUT=120,
        AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED=required_action_submit_enabled,
        AI_TOOL_GATEWAY_PUBLIC_BASE="",
    )
    return CozeRun(ctx, settings)


def test_coze_delta_maps_to_answer_event():
    run = _run()
    emitted = set()
    parts = []
    events = run._map_event(
        "conversation.message.delta",
        {"id": "m1", "type": "answer", "content": "hello"},
        emitted,
        parts,
    )
    assert events[0].type == "answer"
    assert events[0].data["content"] == "hello"
    assert parts == ["hello"]
    assert "m1" in emitted


def test_coze_completed_answer_does_not_duplicate_delta():
    run = _run()
    emitted = {"m1"}
    parts = ["hello"]
    events = run._map_event(
        "conversation.message.completed",
        {"id": "m1", "type": "answer", "content": "hello"},
        emitted,
        parts,
    )
    assert events == []
    assert parts == ["hello"]


def test_coze_function_call_maps_to_tool_call():
    run = _run()
    events = run._map_event(
        "conversation.message.completed",
        {
            "id": "m2",
            "type": "function_call",
            "content": '{"name":"get_exam_list","arguments":{"status":"completed"}}',
        },
        set(),
        [],
    )
    assert events[0].type == "tool_call"
    assert events[0].data["tool"] == "get_exam_list"
    assert events[0].data["arguments"] == {"status": "completed"}


def test_coze_tool_response_confirmation_maps_to_frontend_event():
    run = _run()
    events = run._map_event(
        "conversation.message.completed",
        {
            "id": "m3",
            "type": "tool_response",
            "content": (
                '{"status":"confirmation_required","confirmation_id":"c1",'
                '"tool":"generate_comment","arguments":{"student_number":"S001"}}'
            ),
        },
        set(),
        [],
    )

    assert events[0].type == "confirmation_required"
    assert events[0].data["run_id"] == run.run_id
    assert events[0].data["tool_call_id"] == "c1"
    assert events[0].data["tool_name"] == "generate_comment"
    assert run.is_confirmation_expired("c1") is False


@pytest.mark.asyncio
async def test_coze_done_reports_persistence_failure(monkeypatch):
    run = _run()

    async def fake_stream(user_message):
        yield (
            "conversation.message.delta",
            {"id": "answer-1", "type": "answer", "content": "hello"},
        )

    async def failed_persist(*args, **kwargs):
        return {"status": "failed", "reason": "chat_history_unavailable"}

    monkeypatch.setattr(run, "_stream_coze", fake_stream)
    monkeypatch.setattr(run, "_persist_messages", failed_persist)

    events = [event async for event in run.run("hi")]

    assert [event.type for event in events] == ["thinking", "error", "done"]

    error = next(event for event in events if event.type == "error")
    assert error.data["message"] == PERSISTENCE_FAILURE_MESSAGE
    assert error.data["retryable"] is False
    assert error.data["code"] == PERSISTENCE_FAILURE_CODE
    assert error.data["reason"] == "chat_history_unavailable"
    assert error.data["blocking"] is True
    assert error.data["persistence"] == {
        "status": "failed",
        "reason": "chat_history_unavailable",
    }

    done = events[-1]
    assert done.data["persistence"] == {
        "status": "failed",
        "reason": "chat_history_unavailable",
    }
    assert done.data["status"] == "blocked"
    assert done.data["blocking_error"] == PERSISTENCE_FAILURE_CODE


@pytest.mark.asyncio
async def test_coze_resume_after_confirmation_executes_gateway_tool(monkeypatch):
    run = _run()
    run._pending_confirmations["c1"] = {
        "tool_name": "generate_comment",
        "arguments": {"student_number": "S001"},
        "requested_at": __import__("time").monotonic(),
        "timeout": 300.0,
    }
    gateway = AsyncMock(return_value={"status": "ok", "result": {"draft_id": "d1"}})
    persist_assistant = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr("edu_cloud.ai.providers.coze.execute_registered_tool", gateway)
    monkeypatch.setattr(run, "_persist_assistant_message", persist_assistant)

    events = [
        event async for event in run.resume_after_confirmation(approved_ids=["c1"])
    ]

    assert [event.type for event in events] == ["tool_call", "tool_result", "answer", "done"]
    gateway.assert_awaited_once()
    persist_assistant.assert_awaited_once()
    assert "c1" not in run._pending_confirmations


@pytest.mark.asyncio
async def test_coze_required_action_executes_gateway_and_submits_outputs(monkeypatch):
    run = _run(required_action_submit_enabled=True)
    gateway = AsyncMock(return_value={"status": "ok", "result": {"items": ["exam-1"]}})
    monkeypatch.setattr("edu_cloud.ai.providers.coze.execute_registered_tool", gateway)

    submitted = {}

    async def fake_stream_tool_outputs(*, conversation_id, chat_id, tool_outputs):
        submitted["conversation_id"] = conversation_id
        submitted["chat_id"] = chat_id
        submitted["tool_outputs"] = tool_outputs
        yield (
            "conversation.message.delta",
            {"id": "answer-1", "type": "answer", "content": "已找到考试"},
        )

    monkeypatch.setattr(run, "_stream_coze_tool_outputs", fake_stream_tool_outputs)

    events = [
        event async for event in run._handle_required_action(
            {
                "id": "chat-1",
                "conversation_id": "conv-1",
                "required_action": {
                    "submit_tool_outputs": {
                        "tool_calls": [{
                            "id": "tool-call-1",
                            "function": {
                                "name": "get_exam_list",
                                "arguments": '{"status":"completed"}',
                            },
                        }],
                    },
                },
            },
            set(),
            [],
        )
    ]

    assert [event.type for event in events] == ["tool_call", "tool_result", "answer"]
    gateway.assert_awaited_once()
    assert submitted["conversation_id"] == "conv-1"
    assert submitted["chat_id"] == "chat-1"
    assert submitted["tool_outputs"] == [
        {"tool_call_id": "tool-call-1", "output": '{"items": ["exam-1"]}'}
    ]


@pytest.mark.asyncio
async def test_coze_required_action_write_tool_waits_for_edu_confirmation(monkeypatch):
    run = _run(required_action_submit_enabled=True)
    gateway = AsyncMock(return_value={
        "status": "confirmation_required",
        "confirmation_id": "confirm-1",
        "tool": "generate_comment",
        "arguments": {"student_number": "S001"},
        "risk_level": "medium",
    })
    monkeypatch.setattr("edu_cloud.ai.providers.coze.execute_registered_tool", gateway)

    events = [
        event async for event in run._handle_required_action(
            {
                "id": "chat-1",
                "conversation_id": "conv-1",
                "required_action": {
                    "submit_tool_outputs": {
                        "tool_calls": [{
                            "id": "tool-call-1",
                            "function": {
                                "name": "generate_comment",
                                "arguments": '{"student_number":"S001"}',
                            },
                        }],
                    },
                },
            },
            set(),
            [],
        )
    ]

    assert [event.type for event in events] == ["tool_call", "confirmation_required"]
    assert run._pending_confirmations["confirm-1"]["coze_conversation_id"] == "conv-1"
    assert run._pending_confirmations["confirm-1"]["coze_chat_id"] == "chat-1"
    assert run._pending_confirmations["confirm-1"]["coze_tool_call_id"] == "tool-call-1"


@pytest.mark.asyncio
async def test_coze_confirmed_write_submits_tool_output_back_to_coze(monkeypatch):
    run = _run(required_action_submit_enabled=True)
    run._pending_confirmations["confirm-1"] = {
        "tool_name": "generate_comment",
        "arguments": {"student_number": "S001"},
        "requested_at": __import__("time").monotonic(),
        "timeout": 300.0,
        "coze_conversation_id": "conv-1",
        "coze_chat_id": "chat-1",
        "coze_tool_call_id": "tool-call-1",
        "prior_tool_outputs": [],
    }
    gateway = AsyncMock(return_value={"status": "ok", "result": {"draft_id": "d1"}})
    monkeypatch.setattr("edu_cloud.ai.providers.coze.execute_registered_tool", gateway)

    submitted = {}

    async def fake_stream_tool_outputs(*, conversation_id, chat_id, tool_outputs):
        submitted["conversation_id"] = conversation_id
        submitted["chat_id"] = chat_id
        submitted["tool_outputs"] = tool_outputs
        yield (
            "conversation.message.delta",
            {"id": "answer-1", "type": "answer", "content": "评语已生成"},
        )

    monkeypatch.setattr(run, "_stream_coze_tool_outputs", fake_stream_tool_outputs)
    persist_assistant = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr(run, "_persist_assistant_message", persist_assistant)

    events = [event async for event in run.resume_after_confirmation(approved_ids=["confirm-1"])]

    assert [event.type for event in events] == ["tool_call", "tool_result", "answer", "done"]
    assert submitted["conversation_id"] == "conv-1"
    assert submitted["chat_id"] == "chat-1"
    assert submitted["tool_outputs"] == [
        {"tool_call_id": "tool-call-1", "output": '{"draft_id": "d1"}'}
    ]
    persist_assistant.assert_awaited_once_with("评语已生成")
    assert "confirm-1" not in run._pending_confirmations


@pytest.mark.asyncio
async def test_coze_resume_after_confirmation_blocks_on_assistant_persistence_failure(monkeypatch):
    run = _run()
    run._pending_confirmations["c1"] = {
        "tool_name": "generate_comment",
        "arguments": {"student_number": "S001"},
        "requested_at": __import__("time").monotonic(),
        "timeout": 300.0,
    }
    gateway = AsyncMock(return_value={"status": "ok", "result": {"draft_id": "d1"}})
    failed_persist = AsyncMock(return_value={
        "status": "failed",
        "reason": "chat_history_unavailable",
    })
    monkeypatch.setattr("edu_cloud.ai.providers.coze.execute_registered_tool", gateway)
    monkeypatch.setattr(run, "_persist_assistant_message", failed_persist)

    events = [event async for event in run.resume_after_confirmation(approved_ids=["c1"])]

    assert [event.type for event in events] == ["tool_call", "tool_result", "error", "done"]
    error = events[-2]
    assert error.data["retryable"] is False
    assert error.data["code"] == PERSISTENCE_FAILURE_CODE
    assert error.data["blocking"] is True
    assert error.data["persistence"] == {
        "status": "failed",
        "reason": "chat_history_unavailable",
    }
    done = events[-1]
    assert done.data["status"] == "blocked"
    assert done.data["blocking_error"] == PERSISTENCE_FAILURE_CODE
    assert done.data["persistence"] == {
        "status": "failed",
        "reason": "chat_history_unavailable",
    }
    failed_persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_coze_persist_helpers_return_blocking_failure_on_db_error():
    run = _run()

    expected = {
        "status": "failed",
        "reason": "chat_history_unavailable",
        "code": PERSISTENCE_FAILURE_CODE,
        "message": PERSISTENCE_FAILURE_MESSAGE,
        "retryable": False,
        "blocking": True,
    }

    assert await run._persist_messages("hi", "hello") == expected
    assert await run._persist_assistant_message("hello") == expected


@pytest.mark.asyncio
async def test_coze_confirmed_required_action_does_not_execute_when_submit_is_disabled(monkeypatch):
    run = _run(required_action_submit_enabled=False)
    run._pending_confirmations["confirm-1"] = {
        "tool_name": "generate_comment",
        "arguments": {"student_number": "S001"},
        "requested_at": __import__("time").monotonic(),
        "timeout": 300.0,
        "coze_conversation_id": "conv-1",
        "coze_chat_id": "chat-1",
        "coze_tool_call_id": "tool-call-1",
        "prior_tool_outputs": [],
    }
    gateway = AsyncMock()
    monkeypatch.setattr("edu_cloud.ai.providers.coze.execute_registered_tool", gateway)

    events = [event async for event in run.resume_after_confirmation(approved_ids=["confirm-1"])]

    assert [event.type for event in events] == ["error", "done"]
    assert events[0].data["mode"] == "coze_required_action"
    assert events[0].data["retryable"] is False
    gateway.assert_not_awaited()
    assert "confirm-1" in run._pending_confirmations


@pytest.mark.asyncio
async def test_coze_required_action_event_is_not_executed_when_submit_is_not_ready(monkeypatch):
    run = _run(required_action_submit_enabled=False)
    gateway = AsyncMock()
    monkeypatch.setattr("edu_cloud.ai.providers.coze.execute_registered_tool", gateway)

    async def source():
        yield (
            "conversation.chat.required_action",
            {
                "id": "chat-1",
                "conversation_id": "conv-1",
                "required_action": {
                    "submit_tool_outputs": {
                        "tool_calls": [{
                            "id": "tool-call-1",
                            "function": {
                                "name": "get_exam_list",
                                "arguments": '{"status":"completed"}',
                            },
                        }],
                    },
                },
            },
        )

    events = [event async for event in run._stream_and_map(source(), set(), [])]

    assert [event.type for event in events] == ["error"]
    assert events[0].data["mode"] == "coze_required_action"
    assert events[0].data["retryable"] is False
    gateway.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("event_name", sorted(COZE_REQUIRED_ACTION_EVENTS))
async def test_coze_required_action_event_aliases_execute_only_when_submit_is_enabled(
    event_name,
    monkeypatch,
):
    run = _run(required_action_submit_enabled=True)
    gateway = AsyncMock(return_value={"status": "ok", "result": {"items": ["exam-1"]}})
    monkeypatch.setattr("edu_cloud.ai.providers.coze.execute_registered_tool", gateway)

    async def fake_stream_tool_outputs(*, conversation_id, chat_id, tool_outputs):
        yield (
            "conversation.message.delta",
            {"id": "answer-1", "type": "answer", "content": "已找到考试"},
        )

    monkeypatch.setattr(run, "_stream_coze_tool_outputs", fake_stream_tool_outputs)

    async def source():
        yield (
            event_name,
            {
                "id": "chat-1",
                "conversation_id": "conv-1",
                "required_action": {
                    "submit_tool_outputs": {
                        "tool_calls": [{
                            "id": "tool-call-1",
                            "function": {
                                "name": "get_exam_list",
                                "arguments": '{"status":"completed"}',
                            },
                        }],
                    },
                },
            },
        )

    events = [event async for event in run._stream_and_map(source(), set(), [])]

    assert [event.type for event in events] == ["tool_call", "tool_result", "answer"]
    gateway.assert_awaited_once()


def test_coze_run_remembers_conversation_id():
    run = _run()
    run._remember_conversation({"conversation_id": "conv-1"})

    assert run._context.provider_state["coze_conversation_id"] == "conv-1"


def test_coze_payload_contains_edu_tool_boundary():
    run = _run()
    payload = run._build_chat_payload("列出考试")

    assert payload["bot_id"] == "bot-1"
    content = payload["additional_messages"][0]["content"]
    assert "tool_context_token" in content
    assert "get_exam_list" in content
    assert '"tool_gateway": "/internal/ai-tools/{tool_name}"' in content
    assert '"auth_header": "X-AI-Tool-Token"' in content


def test_coze_payload_uses_public_tool_gateway_base_without_leaking_secret():
    run = _run()
    run._settings.AI_TOOL_GATEWAY_PUBLIC_BASE = "https://edu.example.com/"
    run._settings.AI_TOOL_GATEWAY_TOKEN = "secret-token"

    payload = run._build_chat_payload("列出考试")
    content = payload["additional_messages"][0]["content"]

    assert '"tool_gateway": "https://edu.example.com/internal/ai-tools/{tool_name}"' in content
    assert "https://edu.example.com/internal/ai-tools?context_token=" in content
    assert '"request_body": {"context_token":' in content
    assert "secret-token" not in content


def test_coze_payload_includes_dynamic_tool_schema():
    ctx = _run()._context
    ctx.tool_functions.append(coze_allowed_tool)
    ctx.tool_names.append("coze_allowed_tool")
    run = CozeRun(ctx, _run()._settings)

    payload = run._build_chat_payload("调用工具")
    content = payload["additional_messages"][0]["content"]

    assert '"tools": [' in content
    assert '"name": "coze_allowed_tool"' in content
    assert '"parameters":' in content


@pytest.mark.asyncio
async def test_coze_stream_accepts_quoted_done_marker(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield "event: done"
            yield 'data:"[DONE]"'

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, *args, **kwargs):
            return FakeStream()

    monkeypatch.setattr("edu_cloud.ai.providers.coze.httpx.AsyncClient", FakeClient)

    events = [item async for item in _run()._stream_coze("hello")]

    assert events == [("done", {})]


@pytest.mark.asyncio
async def test_coze_stream_ignores_empty_data_without_warning(monkeypatch, caplog):
    class FakeResponse:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield "event: message"
            yield "data:"
            yield 'data: {"content": "ok"}'

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, *args, **kwargs):
            return FakeStream()

    monkeypatch.setattr("edu_cloud.ai.providers.coze.httpx.AsyncClient", FakeClient)
    caplog.set_level("WARNING", logger="edu_cloud.ai.providers.coze")

    events = [item async for item in _run()._stream_sse("http://fake", {})]

    assert events == [("message", {"content": "ok"})]
    assert "Malformed Coze SSE data" not in caplog.text


@edu_tool(name="coze_allowed_tool", module_code="exam", domain="test")
async def coze_allowed_tool(ctx) -> str:
    return "{}"


@edu_tool(name="coze_blocked_tool", module_code="exam", domain="test")
async def coze_blocked_tool(ctx) -> str:
    return "{}"


@pytest.mark.asyncio
async def test_coze_provider_filters_tool_context_by_allowlist():
    ctx = _run()._context
    ctx.tool_functions.extend([coze_allowed_tool, coze_blocked_tool])
    ctx.tool_names.extend(["coze_allowed_tool", "coze_blocked_tool"])
    settings = SimpleNamespace(
        AI_COZE_ENABLED=True,
        AI_COZE_API_BASE="http://localhost:8888",
        AI_COZE_API_TOKEN="pat-test",
        AI_COZE_BOT_ID="bot-1",
        AI_COZE_TIMEOUT=120,
        AI_COZE_TOOL_ALLOWLIST=["coze_allowed_tool"],
    )

    run = await CozeProvider(settings).create_run(ctx)

    assert run._context.tool_names == ["coze_allowed_tool"]
