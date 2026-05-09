import pytest
import json
import httpx
from unittest.mock import AsyncMock, patch
from edu_cloud.modules.grading.llm_client import LLMClient, GradeResponse
from edu_cloud.modules.grading.prompts_legacy import build_grading_prompt


def test_build_grading_prompt():
    rubric = {"criteria": [{"blankNo": "1", "standardAnswer": "概念", "score": 3.0}]}
    question = {"name": "填空题1", "max_score": 10.0}
    messages = build_grading_prompt(rubric, question)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "评分" in messages[0]["content"]
    # user message references rubric and question
    user_text = json.dumps(messages[1]["content"]) if isinstance(messages[1]["content"], list) else messages[1]["content"]
    assert "概念" in user_text
    assert "10" in user_text


def test_grade_response_model():
    r = GradeResponse(score=8.0, max_score=10.0, feedback="不错", confidence=0.85)
    assert r.score == 8.0
    assert r.confidence == 0.85


@pytest.mark.asyncio
async def test_llm_client_grade_success():
    mock_response = httpx.Response(
        200,
        json={
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "score": 8.0, "feedback": "回答正确", "confidence": 0.9
                    })
                }
            }]
        },
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )

    client = LLMClient(
        api_url="https://api.example.com/v1",
        api_key="test-key",
        model="test-model",
        timeout=30,
        max_retries=1,
    )

    rubric = {"criteria": [{"point": "概念", "score": 10.0, "description": "正确"}]}
    question = {"name": "Q1", "max_score": 10.0}
    messages = build_grading_prompt(rubric, question)
    prompt_text = messages[-1]["content"]

    with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.grade_vision(
            images_b64="base64data",
            prompt=prompt_text,
            max_score=question["max_score"],
        )
    assert result.score == 8.0
    assert result.feedback == "回答正确"
    assert result.confidence == 0.9
    assert result.raw_content != ""


@pytest.mark.asyncio
async def test_llm_client_grade_retry_on_error():
    error_response = httpx.Response(
        500,
        json={"error": "server error"},
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )
    success_response = httpx.Response(
        200,
        json={
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "score": 5.0, "feedback": "部分正确", "confidence": 0.7
                    })
                }
            }]
        },
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )

    client = LLMClient(
        api_url="https://api.example.com/v1",
        api_key="test-key",
        model="test-model",
        timeout=30,
        max_retries=3,
    )

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return error_response
        return success_response

    rubric = {"criteria": []}
    question = {"name": "Q1", "max_score": 10.0}
    messages = build_grading_prompt(rubric, question)
    prompt_text = messages[-1]["content"]

    with patch.object(client._http, "post", side_effect=mock_post):
        result = await client.grade_vision(
            images_b64="base64data",
            prompt=prompt_text,
            max_score=question["max_score"],
        )
    assert result.score == 5.0
    assert call_count == 2


@pytest.mark.asyncio
async def test_llm_client_retry_on_non_json_response():
    """LLM returns 200 but non-JSON text — should retry."""
    non_json_response = httpx.Response(
        200,
        json={
            "choices": [{
                "message": {"content": "I cannot evaluate this image."}
            }]
        },
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )
    success_response = httpx.Response(
        200,
        json={
            "choices": [{
                "message": {
                    "content": json.dumps({"score": 6.0, "feedback": "ok", "confidence": 0.8})
                }
            }]
        },
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )

    client = LLMClient(api_url="https://api.example.com/v1", api_key="k", model="m", max_retries=3)
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return non_json_response
        return success_response

    rubric = {"criteria": []}
    question = {"name": "Q", "max_score": 10.0}
    messages = build_grading_prompt(rubric, question)
    prompt_text = messages[-1]["content"]

    with patch.object(client._http, "post", side_effect=mock_post):
        result = await client.grade_vision(images_b64="x", prompt=prompt_text, max_score=question["max_score"])
    assert result.score == 6.0
    assert call_count == 2


@pytest.mark.asyncio
async def test_llm_client_retry_on_empty_choices():
    """LLM returns 200 with empty choices — should retry."""
    empty_response = httpx.Response(
        200,
        json={"choices": []},
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )
    success_response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps({"score": 9.0, "feedback": "great", "confidence": 0.95})}}]},
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )

    client = LLMClient(api_url="https://api.example.com/v1", api_key="k", model="m", max_retries=2)
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return empty_response
        return success_response

    rubric = {"criteria": []}
    question = {"name": "Q", "max_score": 10.0}
    messages = build_grading_prompt(rubric, question)
    prompt_text = messages[-1]["content"]

    with patch.object(client._http, "post", side_effect=mock_post):
        result = await client.grade_vision(images_b64="x", prompt=prompt_text, max_score=question["max_score"])
    assert result.score == 9.0
    assert call_count == 2


@pytest.mark.asyncio
async def test_llm_client_retry_on_timeout():
    """Network timeout — should retry."""
    success_response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps({"score": 4.0, "feedback": "partial", "confidence": 0.6})}}]},
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )

    client = LLMClient(api_url="https://api.example.com/v1", api_key="k", model="m", max_retries=3)
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ReadTimeout("Connection timed out")
        return success_response

    rubric = {"criteria": []}
    question = {"name": "Q", "max_score": 10.0}
    messages = build_grading_prompt(rubric, question)
    prompt_text = messages[-1]["content"]

    with patch.object(client._http, "post", side_effect=mock_post):
        result = await client.grade_vision(images_b64="x", prompt=prompt_text, max_score=question["max_score"])
    assert result.score == 4.0
    assert call_count == 2


@pytest.mark.asyncio
async def test_llm_client_retry_on_non_dict_json():
    """LLM returns valid JSON but not a dict (e.g. list) — should retry."""
    bad_response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": "[1, 2, 3]"}}]},
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )
    success_response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps({"score": 7.0, "feedback": "ok", "confidence": 0.8})}}]},
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )

    client = LLMClient(api_url="https://api.example.com/v1", api_key="k", model="m", max_retries=3)
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return bad_response
        return success_response

    rubric = {"criteria": []}
    question = {"name": "Q", "max_score": 10.0}
    messages = build_grading_prompt(rubric, question)
    prompt_text = messages[-1]["content"]

    with patch.object(client._http, "post", side_effect=mock_post):
        result = await client.grade_vision(images_b64="x", prompt=prompt_text, max_score=question["max_score"])
    assert result.score == 7.0
    assert call_count == 2


@pytest.mark.asyncio
async def test_llm_client_exhausted_retries():
    """All retries fail — should raise RuntimeError."""
    client = LLMClient(api_url="https://api.example.com/v1", api_key="k", model="m", max_retries=2)

    async def mock_post(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    rubric = {"criteria": []}
    question = {"name": "Q", "max_score": 10.0}
    messages = build_grading_prompt(rubric, question)
    prompt_text = messages[-1]["content"]

    with patch.object(client._http, "post", side_effect=mock_post):
        with pytest.raises(RuntimeError, match="grade_vision failed after 2 attempts"):
            await client.grade_vision(images_b64="x", prompt=prompt_text, max_score=question["max_score"])
