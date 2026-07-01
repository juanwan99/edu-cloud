import base64
from unittest.mock import AsyncMock, patch

import pytest
from google.genai import types

from edu_cloud.modules.grading.gemini_client import GeminiClient


@pytest.mark.asyncio
async def test_gemini_grade_vision_rejects_short_details_with_expected_count():
    client = GeminiClient.__new__(GeminiClient)
    client.model = "gemini-test"
    client._generate = AsyncMock(return_value=(
        '{"score": 3, "comment": "short", '
        '"details": [{"blankNo": "1", "score": 1}]}'
    ))

    image_b64 = base64.b64encode(b"image-bytes").decode()

    with patch(
        "edu_cloud.modules.grading.gemini_client._make_image_part",
        return_value=types.Part.from_text(text="image"),
    ):
        with pytest.raises(RuntimeError, match="Failed to parse vision grading JSON"):
            await client.grade_vision(
                images_b64=image_b64,
                prompt="Grade this image",
                max_score=4,
                expected_details_count=2,
            )

    client._generate.assert_awaited_once()
