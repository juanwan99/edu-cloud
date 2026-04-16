"""LLM Client for AI grading（从 exam-ai 迁入）。"""
import json
import logging
import httpx
from pydantic import BaseModel
from edu_cloud.modules.grading.prompts import build_grading_prompt

logger = logging.getLogger(__name__)


class GradeResponse(BaseModel):
    score: float
    max_score: float = 0.0
    feedback: str = ""
    confidence: float = 0.0
    raw_content: str = ""


class LLMClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self._http = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self._http.aclose()

    async def grade(
        self,
        image_b64: str,
        rubric: dict,
        question: dict,
        question_type: str | None = None,
    ) -> GradeResponse:
        messages = build_grading_prompt(rubric, question, question_type)
        max_score = question.get("max_score", 0.0)

        user_msg = messages[-1]
        user_msg["content"] = [
            {"type": "text", "text": user_msg["content"]},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._http.post(
                    f"{self.api_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}: {resp.text}"
                    logger.warning("LLM attempt %d/%d failed: %s", attempt + 1, self.max_retries, last_error)
                    continue

                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    last_error = "Empty choices in LLM response"
                    logger.warning("LLM attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)
                    continue

                content = choices[0]["message"]["content"]
                text = content.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    text = text.rsplit("```", 1)[0]
                    text = text.strip()
                parsed = json.loads(text)
                return GradeResponse(
                    score=min(max(parsed.get("score", 0), 0), max_score),
                    max_score=max_score,
                    feedback=parsed.get("feedback", ""),
                    confidence=parsed.get("confidence", 0.0),
                    raw_content=content,
                )

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"Network error: {e}"
                logger.warning("LLM attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)
            except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
                last_error = f"Parse error: {e}"
                logger.warning("LLM attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)

        raise RuntimeError(f"LLM call failed after {self.max_retries} attempts: {last_error}")
