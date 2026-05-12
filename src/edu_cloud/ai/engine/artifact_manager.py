"""ArtifactManager — large result deidentification + storage.

Results exceeding size thresholds are stored as artifacts with
redacted previews. The model and SSE stream never see raw student data.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from edu_cloud.ai.anonymizer import Anonymizer

logger = logging.getLogger(__name__)

INLINE_MAX_BYTES = 32_768  # 32KB
INLINE_MAX_ROWS = 50


@dataclass(slots=True)
class Artifact:
    artifact_id: str
    run_id: str
    school_id: str
    source_tool: str
    kind: str
    pii_level: str
    summary: dict[str, Any]
    preview: dict[str, Any]
    raw_data: Any


class ArtifactManager:
    """Manages large tool results: store raw, return redacted preview.

    Step 2 version stores artifacts in memory. Production will use
    the ai_artifacts DB table + optional object storage.
    """

    def __init__(
        self,
        run_id: str,
        school_id: str,
        anonymizer: Anonymizer | None = None,
    ):
        self._run_id = run_id
        self._school_id = school_id
        self._anonymizer = anonymizer
        self._artifacts: dict[str, Artifact] = {}

    def should_artifact(self, result: Any, sensitivity: str) -> bool:
        """Determine if a result should be stored as an artifact."""
        if sensitivity == "pii":
            return True

        raw = json.dumps(result, default=str, ensure_ascii=False)
        if len(raw.encode()) > INLINE_MAX_BYTES:
            return True

        if isinstance(result, list) and len(result) > INLINE_MAX_ROWS:
            return True

        return False

    def create_artifact(
        self,
        source_tool: str,
        result: Any,
        sensitivity: str,
    ) -> Artifact:
        """Store result as artifact, return object with redacted preview."""
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"

        pii_level = "none"
        if sensitivity in ("student", "pii"):
            pii_level = "student"
        elif sensitivity == "class":
            pii_level = "class"
        elif sensitivity == "school":
            pii_level = "school"

        summary = self._build_summary(result, source_tool)
        preview = self._build_preview(result, pii_level)

        artifact = Artifact(
            artifact_id=artifact_id,
            run_id=self._run_id,
            school_id=self._school_id,
            source_tool=source_tool,
            kind=_infer_kind(result),
            pii_level=pii_level,
            summary=summary,
            preview=preview,
            raw_data=result,
        )
        self._artifacts[artifact_id] = artifact
        return artifact

    def process_result(
        self,
        source_tool: str,
        result: Any,
        sensitivity: str,
    ) -> Any:
        """If result is large/sensitive, replace with artifact reference."""
        if not self.should_artifact(result, sensitivity):
            return result

        artifact = self.create_artifact(source_tool, result, sensitivity)
        return {
            "_artifact": True,
            "artifact_id": artifact.artifact_id,
            "summary": artifact.summary,
            "preview": artifact.preview,
        }

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    @property
    def artifacts(self) -> dict[str, Artifact]:
        return dict(self._artifacts)

    async def flush_to_db(self, db_sessionmaker: Any) -> None:
        if not self._artifacts:
            return
        try:
            from edu_cloud.models.ai_engine import AiArtifact
            async with db_sessionmaker() as db:
                for art in self._artifacts.values():
                    db.add(AiArtifact(
                        artifact_id=art.artifact_id,
                        run_id=art.run_id,
                        school_id=art.school_id,
                        source_tool=art.source_tool,
                        kind=art.kind,
                        pii_level=art.pii_level,
                        summary_json=json.dumps(art.summary, default=str),
                        preview_json=json.dumps(art.preview, default=str),
                    ))
                await db.commit()
        except Exception as exc:
            logger.warning("ArtifactManager flush_to_db failed: %s", exc)

    def _build_summary(self, result: Any, source_tool: str) -> dict[str, Any]:
        if isinstance(result, list):
            return {"tool": source_tool, "row_count": len(result), "type": "list"}
        if isinstance(result, dict):
            return {"tool": source_tool, "keys": list(result.keys())[:10], "type": "dict"}
        raw = str(result)
        return {"tool": source_tool, "length": len(raw), "type": type(result).__name__}

    def _build_preview(self, result: Any, pii_level: str) -> dict[str, Any]:
        if isinstance(result, list):
            sample = result[:5]
            if pii_level in ("student", "class"):
                sample = [_redact_record(r, self._anonymizer) for r in sample]
            return {"sample": sample, "truncated": len(result) > 5}
        if isinstance(result, dict):
            preview = {k: v for k, v in list(result.items())[:5]}
            if pii_level in ("student", "class"):
                preview = _redact_record(preview, self._anonymizer)
            return {"sample": preview, "truncated": len(result) > 5}
        return {"sample": str(result)[:500], "truncated": len(str(result)) > 500}


def _redact_record(record: Any, anonymizer: Any | None) -> Any:
    if not isinstance(record, dict):
        return record
    redacted = {}
    sensitive_keys = {"student_name", "name", "display_name", "student_number", "id_card", "phone"}
    for k, v in record.items():
        if k in sensitive_keys:
            if anonymizer and k in ("student_name", "name", "display_name"):
                redacted[k] = anonymizer.anonymize_text(str(v)) if hasattr(anonymizer, "anonymize_text") else "***"
            else:
                redacted[k] = "***"
        else:
            redacted[k] = v
    return redacted


def _infer_kind(result: Any) -> str:
    if isinstance(result, list):
        return "table"
    if isinstance(result, dict):
        return "record"
    return "text"
