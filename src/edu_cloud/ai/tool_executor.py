"""Tool execution pipeline with concurrent batching (Design §4)."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import ToolCall
from edu_cloud.ai.tool_context import ToolContext, ToolResult

logger = logging.getLogger(__name__)

MAX_TOOL_CONCURRENCY = 10


@dataclass
class ToolBatch:
    calls: list[ToolCall]
    concurrent: bool


class ToolExecutor:
    """Executes a single tool call with error handling and timing."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def run_one(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        spec = self._registry.get(call.name)
        if spec is None:
            return ToolResult(success=False, error=f"Unknown tool: {call.name}")

        start = time.monotonic()
        try:
            result = await spec.func(call.arguments, ctx)
            duration_ms = (time.monotonic() - start) * 1000
            if result.metadata is None:
                result.metadata = {}
            result.metadata["duration_ms"] = round(duration_ms, 1)
            return result
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception("Tool %s failed after %.1fms", call.name, duration_ms)
            return ToolResult(
                success=False,
                error=str(exc),
                metadata={"duration_ms": round(duration_ms, 1)},
            )


class ToolOrchestrator:
    """Partitions tool calls into concurrent/serial batches and executes them.

    Read-only tools run concurrently (up to MAX_TOOL_CONCURRENCY).
    Write tools run serially, one at a time.
    """

    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self._executor = ToolExecutor(registry)

    def partition(self, calls: list[ToolCall]) -> list[ToolBatch]:
        batches: list[ToolBatch] = []
        current_reads: list[ToolCall] = []

        for call in calls:
            spec = self._registry.get(call.name)
            is_read_only = spec.is_read_only if spec else True

            if is_read_only:
                current_reads.append(call)
            else:
                if current_reads:
                    batches.append(ToolBatch(calls=current_reads, concurrent=True))
                    current_reads = []
                batches.append(ToolBatch(calls=[call], concurrent=False))

        if current_reads:
            batches.append(ToolBatch(calls=current_reads, concurrent=True))

        return batches

    async def execute(self, batches: list[ToolBatch], ctx: ToolContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        for batch in batches:
            if batch.concurrent and len(batch.calls) > 1:
                batch_results = await asyncio.gather(
                    *[self._executor.run_one(call, ctx) for call in batch.calls[:MAX_TOOL_CONCURRENCY]]
                )
                results.extend(batch_results)
            else:
                for call in batch.calls:
                    results.append(await self._executor.run_one(call, ctx))
        return results
