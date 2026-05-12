"""TraceRecorder — structured decision event logging (JSONL, no PII)."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from edu_cloud.ai.engine.policy_guardrail import ToolCallRecord

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TraceEvent:
    seq: int
    event_type: str
    tool_name: str | None
    args_ref: str | None
    result_ref: str | None
    duration_ms: int | None
    denied: bool
    ts: float


class TraceRecorder:
    """Append-only event log for a single agent run.

    Writes JSONL to logs/ai-trace/. No student names or raw scores —
    only fingerprints and percentile bands.
    """

    def __init__(
        self,
        run_id: str,
        session_id: str,
        school_id: str,
        user_id: str,
        role: str,
        log_dir: Path | None = None,
    ):
        self.run_id = run_id
        self.session_id = session_id
        self.school_id = school_id
        self._user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:12]
        self._role = role
        self._events: list[TraceEvent] = []
        self._seq = 0
        self._log_dir = log_dir or Path("logs/ai-trace")

    def record_tool_call(self, record: ToolCallRecord, result: Any) -> None:
        self._seq += 1
        duration_ms = None
        if record.ended_at is not None:
            duration_ms = int((record.ended_at - record.started_at) * 1000)

        event = TraceEvent(
            seq=self._seq,
            event_type="tool_call",
            tool_name=record.tool_name,
            args_ref=record.args_fingerprint,
            result_ref=_result_fingerprint(result),
            duration_ms=duration_ms,
            denied=record.denied,
            ts=time.time(),
        )
        self._events.append(event)

    def record_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        self._seq += 1
        event = TraceEvent(
            seq=self._seq,
            event_type=event_type,
            tool_name=None,
            args_ref=_result_fingerprint(data) if data else None,
            result_ref=None,
            duration_ms=None,
            denied=False,
            ts=time.time(),
        )
        self._events.append(event)

    def flush(self) -> None:
        """Write accumulated events to JSONL file."""
        if not self._events:
            return
        self._log_dir.mkdir(parents=True, exist_ok=True)
        path = self._log_dir / f"trace-{self.run_id}.jsonl"
        with open(path, "a") as f:
            for ev in self._events:
                line = {
                    "run_id": self.run_id,
                    "session_id": self.session_id,
                    "school_id": self.school_id,
                    "user_hash": self._user_hash,
                    "role": self._role,
                    "seq": ev.seq,
                    "event_type": ev.event_type,
                    "tool_name": ev.tool_name,
                    "args_ref": ev.args_ref,
                    "result_ref": ev.result_ref,
                    "duration_ms": ev.duration_ms,
                    "denied": ev.denied,
                    "ts": ev.ts,
                }
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

    async def flush_to_db(self, db_sessionmaker: Any) -> None:
        """Persist trace header + events to ai_agent_trace / ai_agent_trace_event tables."""
        if not self._events:
            return
        try:
            from edu_cloud.models.ai_engine import AiAgentTrace, AiAgentTraceEvent

            async with db_sessionmaker() as db:
                trace = AiAgentTrace(
                    run_id=self.run_id,
                    session_id=self.session_id,
                    school_id=self.school_id,
                    user_id=self._user_hash,
                    role=self._role,
                    status="completed",
                    event_count=len(self._events),
                )
                db.add(trace)
                await db.flush()

                for ev in self._events:
                    db.add(AiAgentTraceEvent(
                        trace_id=trace.id,
                        seq=ev.seq,
                        event_type=ev.event_type,
                        tool_name=ev.tool_name,
                        args_ref=ev.args_ref,
                        result_ref=ev.result_ref,
                        duration_ms=ev.duration_ms,
                        pii_level="none",
                    ))
                await db.commit()
        except Exception as exc:
            logger.warning("Failed to persist trace to DB: %s", exc)
        finally:
            self._events.clear()

    @property
    def events(self) -> list[TraceEvent]:
        return list(self._events)


def _result_fingerprint(result: Any) -> str:
    raw = json.dumps(result, sort_keys=True, default=str)[:4096]
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
