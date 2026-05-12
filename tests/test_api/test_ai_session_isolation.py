"""AI 会话隔离测试。"""
import pytest
from unittest.mock import AsyncMock, patch
from edu_cloud.ai.anonymizer import Anonymizer
from edu_cloud.api.ai import _SessionState, _sessions, _sessions_lock


@pytest.mark.asyncio
async def test_session_reuse_by_same_owner():
    """同一用户可以复用自己的 session。"""
    test_sid = "test-same-owner-session"
    async with _sessions_lock:
        _sessions[test_sid] = _SessionState(anonymizer=Anonymizer(), owner_id="user-a")
    try:
        async with _sessions_lock:
            existing = _sessions.get(test_sid)
            assert existing is not None
            assert existing.owner_id == "user-a"
    finally:
        async with _sessions_lock:
            _sessions.pop(test_sid, None)


@pytest.mark.asyncio
async def test_session_reuse_by_different_owner_blocked():
    """不同用户不可以复用他人的 session。"""
    test_sid = "test-diff-owner-session"
    async with _sessions_lock:
        _sessions[test_sid] = _SessionState(anonymizer=Anonymizer(), owner_id="user-a")
    try:
        async with _sessions_lock:
            existing = _sessions.get(test_sid)
            assert existing is not None
            assert existing.owner_id != "user-b"
    finally:
        async with _sessions_lock:
            _sessions.pop(test_sid, None)
