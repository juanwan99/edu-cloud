"""Gemini 官方 API 客户端 — 支持实时和 Batch 两种模式。

实时模式：直接调用 generate_content，秒级返回
Batch 模式：提交批量请求，异步处理，半价计费
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel

from edu_cloud.modules.grading.json_parser import extract_json
from edu_cloud.modules.grading.image_utils import resize_image_for_llm

logger = logging.getLogger(__name__)

GradingMode = Literal["realtime", "batch"]


class GeminiGradeResponse(BaseModel):
    score: float
    max_score: float = 0.0
    feedback: str = ""
    confidence: float | None = None
    raw_content: str = ""
    details: list | None = None
    deductions: list | None = None
    comment: str = ""
    recognized_text: str = ""


def _log_usage(method: str, model: str, usage, finish_reason=None) -> None:
    if not usage:
        return
    thoughts = getattr(usage, "thoughts_token_count", 0) or 0
    candidates = getattr(usage, "candidates_token_count", 0) or 0
    total = getattr(usage, "total_token_count", 0) or 0
    if thoughts > 0:
        logger.warning(
            "gemini-usage method=%s model=%s in=%s out=%s thoughts=%s total=%s cached=%s finish=%s — THINKING DETECTED",
            method, model,
            getattr(usage, "prompt_token_count", 0),
            candidates, thoughts, total,
            getattr(usage, "cached_content_token_count", 0),
            finish_reason,
        )
    else:
        logger.info(
            "gemini-usage method=%s model=%s in=%s out=%s thoughts=%s total=%s cached=%s finish=%s",
            method, model,
            getattr(usage, "prompt_token_count", 0),
            candidates, thoughts, total,
            getattr(usage, "cached_content_token_count", 0),
            finish_reason,
        )


def _make_image_part(image_bytes: bytes) -> types.Part:
    resized = resize_image_for_llm(image_bytes)
    mime = "image/png" if resized[:4] == b"\x89PNG" else "image/jpeg"
    return types.Part.from_bytes(data=resized, mime_type=mime)


class GeminiClient:
    """Gemini 官方 API 客户端，支持实时和 Batch 双模式。

    支持两种连接方式：
    - API Key 模式（AI Studio）：传入 api_key
    - Vertex AI 模式（Cloud 赠金）：传入 vertex_project + vertex_location
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        max_retries: int = 3,
        *,
        vertex_project: str | None = None,
        vertex_location: str | None = None,
    ):
        self.model = model
        self.max_retries = max_retries
        self._cache_map: dict[str, str] = {}

        if vertex_project:
            self._client = genai.Client(
                vertexai=True,
                project=vertex_project,
                location=vertex_location or "global",
            )
            self._mode = "vertex"
        else:
            self._client = genai.Client(api_key=api_key)
            self._mode = "api_key"

    async def close(self):
        pass

    def _get_config(self, max_tokens: int = 2048) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

    async def _generate(
        self,
        contents: list,
        *,
        method: str,
        max_tokens: int = 2048,
        cached_content: str | None = None,
    ) -> str:
        config = self._get_config(max_tokens)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                kwargs = {
                    "model": self.model,
                    "contents": contents,
                    "config": config,
                }
                if cached_content:
                    kwargs["cached_content"] = cached_content

                response = await asyncio.to_thread(
                    self._client.models.generate_content, **kwargs
                )

                finish = None
                if response.candidates:
                    finish = getattr(response.candidates[0], "finish_reason", None)
                _log_usage(method, self.model, response.usage_metadata, finish)

                if not response.text:
                    last_error = "Empty response from Gemini"
                    logger.warning(
                        "gemini %s attempt %d/%d: %s",
                        method, attempt + 1, self.max_retries, last_error,
                    )
                    continue

                return response.text

            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(
                    "gemini %s attempt %d/%d: %s",
                    method, attempt + 1, self.max_retries, last_error,
                )

        raise RuntimeError(
            f"gemini {method} failed after {self.max_retries} attempts: {last_error}"
        )

    async def extract_text(
        self,
        image_bytes: bytes,
        prompt: str,
    ) -> list[dict]:
        image_part = _make_image_part(image_bytes)
        contents = [
            types.Content(
                role="user",
                parts=[image_part, types.Part.from_text(text=prompt)],
            ),
        ]

        last_text = ""
        for attempt in range(self.max_retries):
            text = await self._generate(contents, method="extract_text")
            parsed = extract_json(text)
            if parsed is not None:
                if isinstance(parsed, dict):
                    return parsed.get("blanks", [])
                return parsed
            last_text = text
            logger.warning("extract_text: JSON parse failed attempt %d/%d, text[:200]=%s",
                           attempt + 1, self.max_retries, text[:200])
        raise RuntimeError(f"Failed to parse OCR JSON after {self.max_retries} attempts: {last_text[:200]}")

    async def grade_text(
        self,
        prompt: str,
        max_score: float,
        *,
        cache_key: str | None = None,
        cache_prompt_prefix: str | None = None,
    ) -> GeminiGradeResponse:
        cached_content_name = None
        if cache_key and cache_prompt_prefix:
            cached_content_name = await self._get_or_create_cache(
                cache_key, cache_prompt_prefix,
            )

        if cached_content_name:
            contents = [types.UserContent(parts=[types.Part.from_text(text=prompt)])]
        else:
            contents = [types.UserContent(parts=[types.Part.from_text(text=prompt)])]

        text = await self._generate(
            contents,
            method="grade_text",
            max_tokens=2048,
            cached_content=cached_content_name,
        )

        parsed = extract_json(text)
        if parsed is None or not isinstance(parsed, dict):
            raise RuntimeError(f"Failed to parse grading JSON: {text[:200]}")

        from edu_cloud.modules.grading.detail_flatten import flatten_llm_details
        return GeminiGradeResponse(
            score=min(max(parsed.get("score", 0), 0), max_score),
            max_score=max_score,
            feedback=parsed.get("comment", parsed.get("feedback", "")),
            confidence=parsed.get("confidence"),
            raw_content=text,
            details=flatten_llm_details(parsed.get("details")),
            deductions=parsed.get("deductions") or [],
            comment=parsed.get("comment", ""),
            recognized_text=parsed.get("llmRecognizedText", ""),
        )

    async def grade_vision(
        self,
        images_b64: str | list[str],
        prompt: str,
        max_score: float,
    ) -> GeminiGradeResponse:
        if isinstance(images_b64, str):
            images_b64 = [images_b64]

        import base64
        parts = []
        for img_b64 in images_b64:
            img_bytes = base64.b64decode(img_b64)
            parts.append(_make_image_part(img_bytes))
        parts.append(types.Part.from_text(text=prompt))

        contents = [types.Content(role="user", parts=parts)]
        text = await self._generate(contents, method="grade_vision", max_tokens=4096)

        parsed = extract_json(text)
        if parsed is None or not isinstance(parsed, dict):
            raise RuntimeError(f"Failed to parse vision grading JSON: {text[:200]}")

        from edu_cloud.modules.grading.detail_flatten import flatten_llm_details
        return GeminiGradeResponse(
            score=min(max(parsed.get("score", 0), 0), max_score),
            max_score=max_score,
            feedback=parsed.get("comment", parsed.get("feedback", "")),
            confidence=parsed.get("confidence"),
            raw_content=text,
            details=flatten_llm_details(parsed.get("details")),
            deductions=parsed.get("deductions") or [],
            comment=parsed.get("comment", ""),
            recognized_text=parsed.get("llmRecognizedText", ""),
        )

    async def _get_or_create_cache(
        self, cache_key: str, prompt_prefix: str,
    ) -> str | None:
        if cache_key in self._cache_map:
            return self._cache_map[cache_key]

        try:
            cached = await asyncio.to_thread(
                self._client.caches.create,
                model=self.model,
                config=types.CreateCachedContentConfig(
                    display_name=f"grading-{cache_key[:32]}",
                    contents=[
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=prompt_prefix)],
                        ),
                    ],
                    ttl="3600s",
                ),
            )
            name = cached.name
            logger.info(
                "gemini cache created: key=%s, name=%s, tokens=%s",
                cache_key[:32], name,
                getattr(cached.usage_metadata, "total_token_count", "?"),
            )
            self._cache_map[cache_key] = name
            return name
        except Exception as e:
            logger.warning("gemini cache creation failed: %s, proceeding without cache", e)
            return None

    # ── Batch API ──

    async def create_batch_job(
        self,
        requests: list[dict],
    ) -> str:
        """创建 Batch 任务。

        requests: [{"custom_id": "xxx", "contents": [...], "config": {...}}]
        返回 batch job name。
        """
        inline_requests = []
        for req in requests:
            inline_req = types.InlinedRequest(
                model=self.model,
                contents=req["contents"],
                config=self._get_config(req.get("max_tokens", 2048)),
            )
            inline_requests.append(inline_req)

        job = await asyncio.to_thread(
            self._client.batches.create,
            model=self.model,
            src=inline_requests,
            config=types.CreateBatchJobConfig(
                display_name=f"grading-batch-{int(time.time())}",
            ),
        )
        logger.info("gemini batch job created: name=%s, state=%s", job.name, job.state)
        return job.name

    async def poll_batch_job(self, job_name: str, poll_interval: int = 10, timeout: int = 3600) -> list[dict]:
        """轮询 Batch 任务直到完成，返回结果列表。"""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            job = await asyncio.to_thread(
                self._client.batches.get, name=job_name,
            )
            state = str(job.state)
            logger.debug("gemini batch poll: name=%s, state=%s", job_name, state)

            if "SUCCEEDED" in state or "JOB_STATE_SUCCEEDED" in state:
                return self._parse_batch_results(job)
            if "FAILED" in state or "CANCELLED" in state:
                raise RuntimeError(f"Batch job {job_name} failed: {state}")

            await asyncio.sleep(poll_interval)

        raise RuntimeError(f"Batch job {job_name} timed out after {timeout}s")

    def _parse_batch_results(self, job) -> list[dict]:
        results = []
        if hasattr(job, "dest") and job.dest:
            dest = job.dest
            if hasattr(dest, "inlined_responses") and dest.inlined_responses:
                for i, resp in enumerate(dest.inlined_responses):
                    response = getattr(resp, "response", None)
                    if response and hasattr(response, "text"):
                        finish = None
                        if response.candidates:
                            finish = getattr(response.candidates[0], "finish_reason", None)
                        _log_usage(f"batch[{i}]", self.model, response.usage_metadata, finish)
                        results.append({"text": response.text, "usage": response.usage_metadata})
                    else:
                        results.append({"text": None, "error": str(resp)})
        return results
