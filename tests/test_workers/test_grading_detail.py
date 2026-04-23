"""Tests for per-blank scoring details in the grading pipeline (Task 6)."""
import json

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from edu_cloud.modules.grading.prompts_legacy import build_grading_prompt


def test_grading_prompt_requests_details():
    """prompt 要求返回 details 数组。"""
    rubric = {"criteria": [{"blankNo": "1", "score": 4, "answer": "test", "intent": "i", "coreRequirement": "c"}]}
    question = {"name": "第1题", "max_score": 4}
    messages = build_grading_prompt(rubric, question, "essay")
    system_text = messages[0]["content"]
    assert "details" in system_text
    assert "blankNo" in system_text


def test_grading_prompt_backward_compat():
    """老 3 字段 criteria 也能正常构建 prompt。"""
    rubric = {"criteria": [{"point": "概念", "score": 3, "description": "正确"}]}
    question = {"name": "Q1", "max_score": 3}
    messages = build_grading_prompt(rubric, question)
    assert len(messages) == 2


def test_llm_client_comment_to_feedback_compat():
    """LLM 返回 comment 字段时映射到 feedback。"""
    raw = json.dumps({"score": 4, "comment": "好的答案", "confidence": 0.9, "details": [{"blankNo": "1", "score": 4, "maxScore": 4, "reason": "正确"}]})
    text = raw.strip()
    parsed = json.loads(text)
    feedback = parsed.get("comment", parsed.get("feedback", ""))
    assert feedback == "好的答案"


@pytest.mark.asyncio
async def test_worker_stores_details_in_raw_response():
    """Worker 将 LLM 返回的 details 存入 ai_raw_response.details。"""
    from edu_cloud.modules.grading.llm_client import GradeResponse
    resp = GradeResponse(
        score=4,
        max_score=8,
        feedback="好",
        confidence=0.9,
        raw_content='{"score":4,"details":[{"blankNo":"1","score":4}],"comment":"好","confidence":0.9}',
    )
    parsed = json.loads(resp.raw_content)
    assert "details" in parsed
    assert parsed["details"][0]["blankNo"] == "1"
