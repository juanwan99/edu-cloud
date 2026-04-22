"""LLM Client for AI grading（从 exam-ai 迁入）。"""
import json
import logging
import httpx
from pydantic import BaseModel
from edu_cloud.modules.grading.prompts import build_grading_prompt, build_rubric_generation_prompt

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
        slot: str = "",
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.slot = slot
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
            "max_tokens": 2048,
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.slot:
            headers["X-LLM-Slot"] = self.slot

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
                    feedback=parsed.get("comment", parsed.get("feedback", "")),
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

    async def generate_rubric(
        self,
        messages: list[dict],
        images_b64: list[str] | None = None,
    ) -> list[dict]:
        """Generate a rubric (criteria list) from messages with optional images.

        Args:
            messages: [{"role": "system", ...}, {"role": "user", ...}]
            images_b64: optional list of base64-encoded image strings

        Returns:
            list of criterion dicts (blankNo, score, answer, intent, coreRequirement)
        """
        msgs = [m.copy() for m in messages]

        # Attach images to the last user message if provided
        if images_b64:
            user_msg = msgs[-1]
            text_content = user_msg.get("content", "")
            content_parts: list[dict] = [{"type": "text", "text": text_content}]
            for b64 in images_b64:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })
            user_msg["content"] = content_parts

        payload = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": 4096,
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.slot:
            headers["X-LLM-Slot"] = self.slot

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
                    logger.warning(
                        "generate_rubric attempt %d/%d failed: %s",
                        attempt + 1, self.max_retries, last_error,
                    )
                    continue

                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    last_error = "Empty choices in LLM response"
                    logger.warning(
                        "generate_rubric attempt %d/%d: %s",
                        attempt + 1, self.max_retries, last_error,
                    )
                    continue

                content = choices[0]["message"]["content"]
                text = content.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    text = text.rsplit("```", 1)[0]
                    text = text.strip()
                parsed = json.loads(text)
                if not isinstance(parsed, list):
                    raise ValueError(f"Expected JSON array, got: {type(parsed)}")
                logger.info(
                    "generate_rubric: parsed %d criteria items", len(parsed)
                )
                return parsed

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"Network error: {e}"
                logger.warning(
                    "generate_rubric attempt %d/%d: %s",
                    attempt + 1, self.max_retries, last_error,
                )
            except (json.JSONDecodeError, KeyError, TypeError, AttributeError, ValueError) as e:
                last_error = f"Parse error: {e}"
                logger.warning(
                    "generate_rubric attempt %d/%d: %s",
                    attempt + 1, self.max_retries, last_error,
                )

        raise RuntimeError(
            f"generate_rubric failed after {self.max_retries} attempts: {last_error}"
        )
