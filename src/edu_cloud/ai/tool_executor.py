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
    """Executes a single tool call with error handling and timing.

    Delegates to ToolRegistry.execute() to preserve dual-signature
    compatibility (INV-001: legacy **kwargs + new ToolContext).
    """

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def run_one(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        start = time.monotonic()
        # Delegate to registry.execute() which handles both new (input, ctx)
        # and legacy (**kwargs) tool signatures (F002 / INV-001).
        result = await self._registry.execute(call.name, call.arguments, ctx)
        duration_ms = (time.monotonic() - start) * 1000

        if isinstance(result, ToolResult):
            if result.metadata is None:
                result.metadata = {}
            result.metadata["duration_ms"] = round(duration_ms, 1)
            return result

        # Legacy tool returned dict — wrap into ToolResult
        is_error = isinstance(result, dict) and "error" in result
        return ToolResult(
            success=not is_error,
            data=result if not is_error else None,
            error=result.get("error") if is_error else None,
            metadata={"duration_ms": round(duration_ms, 1)},
        )


class ToolOrchestrator:
    """Partitions tool calls into concurrent/serial batches and executes them.

    Read-only tools run concurrently (up to MAX_TOOL_CONCURRENCY).
    Write tools run serially, one at a time.

    F001 safety: When ctx.db is not None (real database session), concurrent
    batches fall back to serial execution because AsyncSession is not safe
    for concurrent use across tasks.
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

    async def execute(
        self,
        batches: list[ToolBatch],
        ctx: ToolContext,
        *,
        default_read_timeout: float = 30.0,
        default_write_timeout: float = 60.0,
    ) -> list[ToolResult]:
        # F001: AsyncSession is not concurrent-safe. When a real db session
        # exists, fall back to serial even for concurrent batches.
        can_concurrent = ctx.db is None
        results: list[ToolResult] = []
        for batch in batches:
            if batch.concurrent and can_concurrent and len(batch.calls) > 1:
                # P0-2: chunk to avoid dropping calls beyond MAX_TOOL_CONCURRENCY
                for i in range(0, len(batch.calls), MAX_TOOL_CONCURRENCY):
                    chunk = batch.calls[i:i + MAX_TOOL_CONCURRENCY]
                    chunk_results = await asyncio.gather(
                        *[self._run_with_timeout(call, ctx, default_read_timeout, default_write_timeout)
                          for call in chunk]
                    )
                    results.extend(chunk_results)
            else:
                for call in batch.calls:
                    results.append(
                        await self._run_with_timeout(call, ctx, default_read_timeout, default_write_timeout)
                    )
        return results

    async def _run_with_timeout(
        self,
        call: ToolCall,
        ctx: ToolContext,
        read_timeout: float,
        write_timeout: float,
    ) -> ToolResult:
        spec = self._registry.get(call.name)
        timeout = read_timeout if (spec and spec.is_read_only) else write_timeout
        try:
            return await asyncio.wait_for(self._executor.run_one(call, ctx), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Tool %s timed out after %.0fs", call.name, timeout)
            return ToolResult(success=False, error=f"工具执行超时({timeout:.0f}s)")
        except asyncio.CancelledError:
            return ToolResult(success=False, error="工具执行被取消")
