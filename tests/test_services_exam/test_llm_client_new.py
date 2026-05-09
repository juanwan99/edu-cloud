import pytest
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.modules.grading.llm_client import LLMClient
from edu_cloud.modules.grading.prompts_legacy import build_grading_prompt


@pytest.fixture
def client():
    return LLMClient(
        api_url="http://fake:8100",
        api_key="test-key",
        model="test-model",
        timeout=10,
        max_retries=1,
    )


@pytest.mark.asyncio
async def test_grade_accepts_multiple_images(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"score": 5, "comment": "ok", "confidence": 0.9}'}}]
    }
    client._http.post = AsyncMock(return_value=mock_resp)

    rubric = {"criteria": []}
    question = {"name": "1", "max_score": 10}
    messages = build_grading_prompt(rubric, question)
    prompt_text = messages[-1]["content"]

    result = await client.grade_vision(
        images_b64=["base64img1", "base64img2"],
        prompt=prompt_text,
        max_score=question["max_score"],
    )
    assert result.score == 5
    payload = client._http.post.call_args[1]["json"]
    user_content = payload["messages"][-1]["content"]
    image_parts = [p for p in user_content if p.get("type") == "image_url"]
    assert len(image_parts) == 2


@pytest.mark.asyncio
async def test_extract_text(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"blanks": [{"blankNo": "1-1", "subQ": "(1)", "text": "hello"}]}'}}]
    }
    client._http.post = AsyncMock(return_value=mock_resp)

    result = await client.extract_text(
        images_b64=["base64img"],
        prompt="OCR prompt here",
    )
    assert len(result) == 1
    assert result[0]["text"] == "hello"


@pytest.mark.asyncio
async def test_grade_text(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"score": 8, "comment": "good", "confidence": 0.95}'}}]
    }
    client._http.post = AsyncMock(return_value=mock_resp)

    result = await client.grade_text(
        prompt="Grade this text",
        max_score=10,
    )
    assert result.score == 8
