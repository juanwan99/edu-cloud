"""LLM Client for AI grading（从 exam-ai 迁入）。"""
from __future__ import annotations

import logging
import httpx
from pydantic import BaseModel
from edu_cloud.modules.grading.json_parser import extract_json
from edu_cloud.modules.grading.prompts_legacy import build_grading_prompt, build_rubric_generation_prompt

logger = logging.getLogger(__name__)


def _img_data_url(b64: str) -> str:
    mime = "image/png" if b64.startswith("iVBOR") else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _log_llm_usage(method: str, data: dict, model: str) -> None:
    u = data.get("usage") or {}
    ch = (data.get("choices") or [{}])[0]
    logger.info(
        "llm-usage method=%s model=%s in=%s out=%s finish=%s",
        method,
        model,
        u.get("prompt_tokens", u.get("input_tokens", 0)),
        u.get("completion_tokens", u.get("output_tokens", 0)),
        ch.get("finish_reason"),
    )



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
        images_b64: str | list[str],
        rubric: dict,
        question: dict,
        question_type: str | None = None,
    ) -> GradeResponse:
        messages = build_grading_prompt(rubric, question, question_type)
        max_score = question.get("max_score", 0.0)

        if isinstance(images_b64, str):
            images_b64 = [images_b64]

        user_msg = messages[-1]
        content_parts: list[dict] = [{"type": "text", "text": user_msg["content"]}]
        for img in images_b64:
            content_parts.append({"type": "image_url", "image_url": {"url": _img_data_url(img)}})
        user_msg["content"] = content_parts

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 16384,
            "temperature": 0,
            "thinking_mode": "nothinking",
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
                _log_llm_usage("grade", data, self.model)
                choices = data.get("choices") or []
                if not choices:
                    last_error = "Empty choices in LLM response"
                    logger.warning("LLM attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)
                    continue

                content = choices[0]["message"]["content"]
                parsed = extract_json(content)
                if parsed is None or not isinstance(parsed, dict):
                    last_error = "Failed to parse JSON from LLM response"
                    logger.warning("LLM attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)
                    continue
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
                    "image_url": {"url": _img_data_url(b64)},
                })
            user_msg["content"] = content_parts

        payload = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": 16384,
            "temperature": 0,
            "thinking_mode": "nothinking",
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
                _log_llm_usage("rubric", data, self.model)
                choices = data.get("choices") or []
                if not choices:
                    last_error = "Empty choices in LLM response"
                    logger.warning(
                        "generate_rubric attempt %d/%d: %s",
                        attempt + 1, self.max_retries, last_error,
                    )
                    continue

                content = choices[0]["message"]["content"]
                parsed = extract_json(content)
                if parsed is None or not isinstance(parsed, list):
                    last_error = "Failed to parse JSON array from rubric response"
                    logger.warning(
                        "generate_rubric attempt %d/%d: %s",
                        attempt + 1, self.max_retries, last_error,
                    )
                    continue
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

        raise RuntimeError(
            f"generate_rubric failed after {self.max_retries} attempts: {last_error}"
        )

    async def extract_text(
        self,
        images_b64: list[str],
        prompt: str,
    ) -> list[dict]:
        """OCR: extract text from answer images. Returns list of blanks."""
        content_parts: list[dict] = []
        for img in images_b64:
            content_parts.append({"type": "image_url", "image_url": {"url": _img_data_url(img)}})
        content_parts.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content_parts}]
        payload = {"model": self.model, "messages": messages, "max_tokens": 16384, "temperature": 0, "thinking_mode": "nothinking"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.slot:
            headers["X-LLM-Slot"] = self.slot

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._http.post(f"{self.api_url}/chat/completions", json=payload, headers=headers)
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}: {resp.text}"
                    logger.warning("extract_text attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)
                    continue
                data = resp.json()
                _log_llm_usage("extract_text", data, self.model)
                choices = data.get("choices") or []
                if not choices:
                    last_error = "Empty choices"
                    continue
                content = choices[0]["message"]["content"]
                parsed = extract_json(content)
                if parsed is None:
                    last_error = "Failed to parse JSON from OCR response"
                    continue
                if isinstance(parsed, dict):
                    return parsed.get("blanks", [])
                return parsed
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"Network error: {e}"
                logger.warning("extract_text attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)

        raise RuntimeError(f"extract_text failed after {self.max_retries} attempts: {last_error}")

    async def grade_text(
        self,
        prompt: str,
        max_score: float,
    ) -> GradeResponse:
        """Text-based grading (after OCR). No images, pure text prompt."""
        messages = [{"role": "user", "content": prompt}]
        payload = {"model": self.model, "messages": messages, "max_tokens": 32768, "temperature": 0, "thinking_mode": "nothinking"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.slot:
            headers["X-LLM-Slot"] = self.slot

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._http.post(f"{self.api_url}/chat/completions", json=payload, headers=headers)
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}: {resp.text}"
                    logger.warning("grade_text attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)
                    continue
                data = resp.json()
                _log_llm_usage("grade_text", data, self.model)
                choices = data.get("choices") or []
                if not choices:
                    last_error = "Empty choices"
                    continue
                content = choices[0]["message"]["content"]
                parsed = extract_json(content)
                if parsed is None or not isinstance(parsed, dict):
                    last_error = "Failed to parse JSON from grading response"
                    continue
                return GradeResponse(
                    score=min(max(parsed.get("score", 0), 0), max_score),
                    max_score=max_score,
                    feedback=parsed.get("comment", parsed.get("feedback", "")),
                    confidence=parsed.get("confidence", 0.0),
                    raw_content=content,
                )
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"Network error: {e}"
                logger.warning("grade_text attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)

        raise RuntimeError(f"grade_text failed after {self.max_retries} attempts: {last_error}")
