"""Artifact query tools — let the agent drill into large/PII artifact data.

When a tool result exceeds 32KB/50 rows or contains PII, ArtifactManager
replaces it with a summary + artifact_id. These tools let the agent
retrieve filtered subsets without blowing up the model context.
"""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_ALL_ROLES = frozenset({
    "platform_admin", "district_admin", "principal",
    "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher", "parent",
})


@edu_tool(
    name="query_artifact", module_code="exam", domain="system",
    allowed_roles=_ALL_ROLES, sensitivity="school",
)
async def query_artifact(
    ctx: RunContext[AgentDeps],
    artifact_id: str,
    filter_key: str | None = None,
    filter_value: str | None = None,
    sort_by: str | None = None,
    limit: int = 20,
) -> str:
    """Retrieve filtered rows from a large result artifact.

    Use this when a tool returned an artifact reference instead of inline data.
    Supports filtering by a key-value pair and sorting.
    Returns at most `limit` rows (default 20) to keep context manageable.
    """
    artifact = ctx.deps.artifacts.get_artifact(artifact_id)
    if artifact is None:
        return json.dumps({"error": f"Artifact {artifact_id} not found"})

    data = artifact.raw_data

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return json.dumps({
                "artifact_id": artifact_id,
                "type": "text",
                "content": data[:2000],
                "truncated": len(data) > 2000,
            })

    if isinstance(data, dict):
        if filter_key and filter_key in data:
            subset = data[filter_key]
            if isinstance(subset, list):
                data = subset
            else:
                return json.dumps({
                    "artifact_id": artifact_id,
                    "key": filter_key,
                    "value": subset,
                }, ensure_ascii=False, default=str)
        else:
            return json.dumps({
                "artifact_id": artifact_id,
                "keys": list(data.keys()),
                "type": "dict",
                "hint": "Use filter_key to access a specific section",
            }, ensure_ascii=False, default=str)

    if isinstance(data, list):
        rows = list(data)

        if filter_key and filter_value is not None:
            rows = [r for r in rows if isinstance(r, dict) and str(r.get(filter_key, "")) == filter_value]

        if sort_by and rows and isinstance(rows[0], dict):
            try:
                rows.sort(key=lambda r: r.get(sort_by, 0), reverse=True)
            except TypeError:
                pass

        total = len(rows)
        limit = min(limit, 50)
        rows = rows[:limit]

        if artifact.pii_level in ("student", "class"):
            from edu_cloud.ai.engine.artifact_manager import _redact_record
            rows = [_redact_record(r, ctx.deps.anonymizer) for r in rows]

        return json.dumps({
            "artifact_id": artifact_id,
            "total": total,
            "returned": len(rows),
            "rows": rows,
        }, ensure_ascii=False, default=str)

    return json.dumps({"artifact_id": artifact_id, "type": type(data).__name__, "preview": str(data)[:1000]})


@edu_tool(
    name="aggregate_artifact", module_code="exam", domain="system",
    allowed_roles=_ALL_ROLES, sensitivity="school",
)
async def aggregate_artifact(
    ctx: RunContext[AgentDeps],
    artifact_id: str,
    group_by: str,
    metric_key: str,
    operation: str = "avg",
) -> str:
    """Compute aggregates on artifact data without loading all rows into context.

    operation: avg, sum, count, min, max
    group_by: key to group rows by
    metric_key: numeric key to aggregate
    """
    artifact = ctx.deps.artifacts.get_artifact(artifact_id)
    if artifact is None:
        return json.dumps({"error": f"Artifact {artifact_id} not found"})

    data = artifact.raw_data
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"error": "Artifact data is not structured"})

    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                data = v
                break
        else:
            return json.dumps({"error": "No list data found in artifact"})

    if not isinstance(data, list):
        return json.dumps({"error": "Artifact data is not a list"})

    groups: dict[str, list[float]] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        key = str(row.get(group_by, "unknown"))
        val = row.get(metric_key)
        if val is not None:
            try:
                groups.setdefault(key, []).append(float(val))
            except (ValueError, TypeError):
                continue

    result = {}
    for key, values in groups.items():
        if operation == "avg":
            result[key] = round(sum(values) / len(values), 2) if values else 0
        elif operation == "sum":
            result[key] = round(sum(values), 2)
        elif operation == "count":
            result[key] = len(values)
        elif operation == "min":
            result[key] = min(values) if values else 0
        elif operation == "max":
            result[key] = max(values) if values else 0

    return json.dumps({
        "artifact_id": artifact_id,
        "operation": operation,
        "group_by": group_by,
        "metric_key": metric_key,
        "groups": result,
        "total_rows": len(data),
    }, ensure_ascii=False, default=str)


ALL_TOOLS = [query_artifact, aggregate_artifact]
