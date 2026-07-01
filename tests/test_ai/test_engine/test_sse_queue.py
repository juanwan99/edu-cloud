"""Integration tests for SSE asyncio.Queue event streaming in EduAgentRuntime."""
from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from edu_cloud.ai.data_scope import DataScope
from edu_cloud.ai.engine.edu_runtime import (
    EduAgentRuntime,
    PERSISTENCE_FAILURE_CODE,
    PERSISTENCE_FAILURE_MESSAGE,
)
from edu_cloud.ai.schemas import AgentEvent


def _scope() -> DataScope:
    return DataScope(
        user_id="u1", school_id="s1", role="subject_teacher",
        visible_class_ids=["c1"], visible_subject_codes=["math"],
        visible_grade_ids=None, visible_student_ids=None, district_ids=None,
        can_write=True, can_see_rankings=True, can_cross_school=False,
        persona="teacher_assistant", version=1, computed_at=datetime.now(),
    )


def _mock_sessionmaker():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    maker = MagicMock(return_value=session)
    return maker


def _runtime(**kwargs) -> EduAgentRuntime:
    defaults = dict(
        db_sessionmaker=_mock_sessionmaker(),
        user_id="u1",
        school_id="s1",
        role="subject_teacher",
        data_scope=_scope(),
        enabled_modules=frozenset({"exam"}),
        capabilities={},
        anonymizer=MagicMock(anonymize_text=MagicMock(side_effect=lambda x: x)),
        memory=MagicMock(get_entity_memory=AsyncMock(return_value=None)),
        system_prompt="Test prompt",
    )
    defaults.update(kwargs)
    return EduAgentRuntime(**defaults)


@pytest.mark.asyncio
async def test_queue_drain_receives_all_events():
    """Tool events pushed to queue during agent.run() are yielded by run()."""
    rt = _runtime()
    rt.build_agent()

    tool_events = [
        AgentEvent(type="tool_call", data={"tool": "get_scores", "args": {}}),
        AgentEvent(type="tool_result", data={"tool": "get_scores", "result": "ok"}),
    ]

    async def fake_agent_run(user_message, **kwargs):
        deps = kwargs["deps"]
        for ev in tool_events:
            await deps.event_queue.put(ev)
        result = MagicMock()
        result.output = "Test answer"
        result.usage = MagicMock(total_tokens=100)
        result.all_messages = MagicMock(return_value=[])
        return result

    with patch.object(rt._agent, "run", side_effect=fake_agent_run):
        collected = []
        async for ev in rt.run("hello"):
            collected.append(ev)

    types = [e.type for e in collected]
    assert "thinking" in types
    assert "tool_call" in types
    assert "tool_result" in types
    assert "answer" in types
    assert "done" in types
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_queue_drain_handles_agent_error():
    """When agent.run() raises, an error event is yielded instead of answer."""
    rt = _runtime()
    rt.build_agent()

    async def failing_run(user_message, **kwargs):
        raise RuntimeError("LLM connection failed")

    with patch.object(rt._agent, "run", side_effect=failing_run):
        collected = []
        async for ev in rt.run("hello"):
            collected.append(ev)

    types = [e.type for e in collected]
    assert "error" in types
    assert "done" in types
    error_ev = next(e for e in collected if e.type == "error")
    assert "LLM connection failed" in error_ev.data["message"]


@pytest.mark.asyncio
async def test_done_event_reports_persistence_failure():
    """A generated answer must surface chat persistence failure before done."""
    rt = _runtime()
    rt.build_agent()

    async def fake_agent_run(user_message, **kwargs):
        result = MagicMock()
        result.output = "Test answer"
        result.usage = MagicMock(total_tokens=1)
        result.all_messages = MagicMock(return_value=[])
        return result

    async def failed_persist(*args, **kwargs):
        return {"status": "failed", "reason": "chat_history_unavailable"}

    with patch.object(rt._agent, "run", side_effect=fake_agent_run), \
         patch.object(rt, "_persist_messages", side_effect=failed_persist):
        collected = []
        async for ev in rt.run("hello"):
            collected.append(ev)

    types = [e.type for e in collected]
    assert types[-2:] == ["error", "done"]
    assert "answer" not in types

    error_ev = next(e for e in collected if e.type == "error")
    assert error_ev.data["message"] == PERSISTENCE_FAILURE_MESSAGE
    assert error_ev.data["retryable"] is False
    assert error_ev.data["code"] == PERSISTENCE_FAILURE_CODE
    assert error_ev.data["reason"] == "chat_history_unavailable"
    assert error_ev.data["blocking"] is True
    assert error_ev.data["persistence"] == {
        "status": "failed",
        "reason": "chat_history_unavailable",
    }

    done_ev = collected[-1]
    assert done_ev.data["persistence"] == {
        "status": "failed",
        "reason": "chat_history_unavailable",
    }
    assert done_ev.data["status"] == "blocked"
    assert done_ev.data["blocking_error"] == PERSISTENCE_FAILURE_CODE


@pytest.mark.asyncio
async def test_persist_messages_returns_failed_status_on_db_error():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.add = MagicMock()
    session.commit = AsyncMock(side_effect=RuntimeError("db down"))
    maker = MagicMock(return_value=session)
    rt = _runtime(db_sessionmaker=maker)

    status = await rt._persist_messages("hello", "answer")

    assert status == {
        "status": "failed",
        "reason": "chat_history_unavailable",
        "code": PERSISTENCE_FAILURE_CODE,
        "message": PERSISTENCE_FAILURE_MESSAGE,
        "retryable": False,
        "blocking": True,
    }


@pytest.mark.asyncio
async def test_resume_after_confirmation_blocks_answer_on_persistence_failure():
    rt = _runtime()
    rt.build_agent()
    rt._last_messages = ["pending-history"]

    async def fake_resume_run(**kwargs):
        result = MagicMock()
        result.output = "Resumed answer"
        result.all_messages = MagicMock(return_value=["resumed-history"])
        return result

    persist = AsyncMock(return_value={
        "status": "failed",
        "reason": "chat_history_unavailable",
    })

    with patch.object(rt._agent, "run", side_effect=fake_resume_run), \
         patch.object(rt, "_persist_messages", persist):
        collected = [
            ev async for ev in rt.resume_after_confirmation(approved_ids=["confirm-1"])
        ]

    types = [event.type for event in collected]
    assert types == ["error", "done"]
    assert "answer" not in types
    persist.assert_awaited_once_with(None, "Resumed answer")

    error_ev = collected[0]
    assert error_ev.data["message"] == PERSISTENCE_FAILURE_MESSAGE
    assert error_ev.data["retryable"] is False
    assert error_ev.data["code"] == PERSISTENCE_FAILURE_CODE
    assert error_ev.data["blocking"] is True
    assert error_ev.data["persistence"] == {
        "status": "failed",
        "reason": "chat_history_unavailable",
    }

    done_ev = collected[-1]
    assert done_ev.data["persistence"] == {
        "status": "failed",
        "reason": "chat_history_unavailable",
    }
    assert done_ev.data["status"] == "blocked"
    assert done_ev.data["blocking_error"] == PERSISTENCE_FAILURE_CODE
    assert rt.last_messages == ["pending-history"]


@pytest.mark.asyncio
async def test_resume_after_confirmation_emits_answer_after_persistence_success():
    rt = _runtime()
    rt.build_agent()
    rt._last_messages = ["pending-history"]

    async def fake_resume_run(**kwargs):
        result = MagicMock()
        result.output = "Resumed answer"
        result.all_messages = MagicMock(return_value=["resumed-history"])
        return result

    persist = AsyncMock(return_value={"status": "ok"})

    with patch.object(rt._agent, "run", side_effect=fake_resume_run), \
         patch.object(rt, "_persist_messages", persist):
        collected = [
            ev async for ev in rt.resume_after_confirmation(approved_ids=["confirm-1"])
        ]

    assert [event.type for event in collected] == ["answer", "done"]
    persist.assert_awaited_once_with(None, "Resumed answer")
    assert collected[0].data["content"] == "Resumed answer"
    assert collected[-1].data["persistence"] == {"status": "ok"}
    assert "status" not in collected[-1].data
    assert rt.last_messages == ["resumed-history"]


@pytest.mark.asyncio
async def test_task_cancel_on_generator_close():
    """Explicit aclose() triggers cancel path and cleans up event_queue."""
    rt = _runtime()
    rt.build_agent()

    async def slow_run(user_message, **kwargs):
        deps = kwargs["deps"]
        await deps.event_queue.put(AgentEvent(type="tool_call", data={"tool": "test"}))
        await asyncio.sleep(10)

    with patch.object(rt._agent, "run", side_effect=slow_run):
        gen = rt.run("hello")
        ev1 = await gen.__anext__()
        assert ev1.type == "thinking"
        ev2 = await gen.__anext__()
        assert ev2.type == "tool_call"
        await gen.aclose()

    assert rt._deps.event_queue is None, "event_queue should be cleaned up after aclose"
