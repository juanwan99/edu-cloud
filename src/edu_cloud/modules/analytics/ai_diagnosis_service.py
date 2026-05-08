"""AI diagnosis service — build snapshot, call LLM, cache results."""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.analytics.snapshot_schema import (
    DiagnosisSnapshot, DiagnosisContext, SnapshotMeta, DataQuality,
    ScoreSummary, KnowledgePoint, StudentGroup,
    DiagnosisOutput, compute_snapshot_hash,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"
CACHE_TTL_DAYS = 7


async def build_snapshot(
    db: AsyncSession,
    *,
    exam_id: str,
    school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
    user_role: str = "academic_director",
) -> DiagnosisSnapshot:
    """Assemble a DiagnosisSnapshot from existing analytics services."""
    from edu_cloud.modules.analytics.service import exam_summary
    from edu_cloud.modules.analytics.diagnosis_service import class_diagnosis
    from edu_cloud.modules.analytics.layer_service import layer_analysis

    scope = "class" if class_id else "grade"

    summary_data = await exam_summary(db, exam_id=exam_id, school_id=school_id,
                                       visible_subject_codes=visible_subject_codes)
    exam_info = summary_data.get("exam", {})

    diag_data = await class_diagnosis(
        db, exam_id=exam_id, school_id=school_id,
        subject_id=subject_id, class_id=class_id,
        visible_class_ids=visible_class_ids,
    )

    layer_data = await layer_analysis(
        db, exam_id=exam_id, school_id=school_id,
        subject_id=subject_id, class_id=class_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=visible_class_ids,
    )

    subjects_info = summary_data.get("subjects", [])
    first_subj = subjects_info[0] if subjects_info else {}

    total_students = summary_data.get("student_count", 0)
    avg_score = summary_data.get("avg_score", 0)
    full_score = first_subj.get("full_score", 100) if subject_id and first_subj else summary_data.get("total_full_score", 100)

    score_ver = f"{exam_id}:{total_students}"
    kp_count = len(diag_data.get("worstKnowledges", []))
    knowledge_ver = f"{exam_id}:{kp_count}"

    snapshot_hash = compute_snapshot_hash(
        exam_id=exam_id, school_id=school_id, scope=scope,
        subject_id=subject_id, class_id=class_id,
        score_version=score_ver, knowledge_version=knowledge_ver,
    )

    knowledge_points = []
    for kp in diag_data.get("worstKnowledges", []):
        knowledge_points.append(KnowledgePoint(
            fact_id=f"kp:{kp['concept_id']}",
            concept_id=kp["concept_id"],
            name=kp.get("name", kp["concept_id"]),
            class_rate=kp.get("rate", 0),
        ))
    for kp in diag_data.get("unmasterMaxCntKnowledges", []):
        cid = kp["concept_id"]
        if not any(p.concept_id == cid for p in knowledge_points):
            knowledge_points.append(KnowledgePoint(
                fact_id=f"kp:{cid}",
                concept_id=cid,
                name=cid,
                class_rate=0,
                unmastered_student_count=kp.get("count", 0),
            ))

    student_groups = []
    for layer in layer_data.get("layers", []):
        student_groups.append(StudentGroup(
            fact_id=f"layer:{layer['label']}",
            label=layer["label"],
            count=layer["count"],
            avg_score_rate=layer.get("avgScoreRate"),
        ))

    context = DiagnosisContext(
        school_scope=scope,
        exam_id=exam_id,
        exam_name=exam_info.get("name", ""),
        exam_date=str(exam_info.get("exam_date", "")),
        class_id=class_id,
        subject_code=first_subj.get("code") if subject_id else None,
        user_role=user_role,
    )

    scored_count = total_students
    kp_coverage = min(len(knowledge_points) / max(kp_count, 1), 1.0) if kp_count else 0.0

    return DiagnosisSnapshot(
        context=context,
        snapshot=SnapshotMeta(
            snapshot_hash=snapshot_hash,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        data_quality=DataQuality(
            student_count=total_students,
            scored_count=scored_count,
            knowledge_mapping_coverage=round(kp_coverage, 2),
        ),
        score_summary=ScoreSummary(
            full_score=full_score,
            avg=avg_score,
            median=summary_data.get("median_score", avg_score),
            stddev=summary_data.get("stddev", 0),
            pass_rate=summary_data.get("pass_rate", 0),
            excellent_rate=summary_data.get("excellent_rate", 0),
        ),
        knowledge_points=knowledge_points,
        student_groups=student_groups,
    )


def _build_prompt(snapshot: DiagnosisSnapshot) -> str:
    """Build system + user prompt for Gemini."""
    system = (
        "你是一位资深教育数据分析师。请基于下面的考试诊断数据，生成结构化的教学诊断报告。\n"
        "要求：\n"
        "1. 每个结论都必须引用 evidence_fact_ids 中的 fact_id\n"
        "2. confidence 只能是 high/medium/low\n"
        "3. 输出严格 JSON，schema 如下：\n"
        '{"schema_version":"ai_diagnosis_output.v1","summary":{"text":"...","evidence_fact_ids":[],"confidence":"high"},'
        '"findings":[{"id":"F1","text":"...","evidence_fact_ids":[],"confidence":"high"}],'
        '"risk_alerts":[{"text":"...","evidence_fact_ids":[],"confidence":"medium"}],'
        '"teaching_actions":[{"text":"...","target":"...","priority":"high","evidence_fact_ids":[],"confidence":"medium"}],'
        '"student_followups":[{"text":"...","layer":"...","evidence_fact_ids":[],"confidence":"medium"}],'
        '"data_limits":[{"text":"...","fact_id":"quality:...","confidence":"high"}]}'
    )
    user_data = snapshot.model_dump_json(indent=2)
    return f"{system}\n\n=== 诊断数据 ===\n{user_data}"


async def generate_diagnosis(
    snapshot: DiagnosisSnapshot,
    *,
    model: str | None = None,
) -> DiagnosisOutput:
    """Call Gemini to generate a diagnosis from the snapshot."""
    from edu_cloud.config import settings
    from edu_cloud.modules.grading.gemini_client import GeminiClient
    from edu_cloud.modules.grading.json_parser import extract_json

    gemini_model = model or settings.GEMINI_MODEL
    client = GeminiClient(
        api_key=settings.GEMINI_API_KEY or None,
        model=gemini_model,
        vertex_project=settings.VERTEX_AI_PROJECT or None,
        vertex_location=settings.VERTEX_AI_LOCATION or None,
    )

    prompt = _build_prompt(snapshot)
    from google.genai import types
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]

    raw_text = await client._generate(contents, method="ai_diagnosis", max_tokens=4096)

    parsed = extract_json(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        raise RuntimeError(f"Failed to parse AI diagnosis JSON: {raw_text[:300]}")

    return DiagnosisOutput(**parsed)


async def get_or_generate(
    db: AsyncSession,
    *,
    exam_id: str,
    school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
    user_role: str = "academic_director",
    force_refresh: bool = False,
    model: str | None = None,
) -> dict:
    """Retrieve cached diagnosis or generate a new one."""
    scope = "class" if class_id else "grade"

    snapshot = await build_snapshot(
        db, exam_id=exam_id, school_id=school_id,
        subject_id=subject_id, class_id=class_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=visible_class_ids,
        user_role=user_role,
    )
    cache_key = snapshot.snapshot.snapshot_hash

    if not force_refresh:
        cached = await _get_cache(db, cache_key)
        if cached:
            return cached

    output = await generate_diagnosis(snapshot, model=model)
    result = output.model_dump()

    await _set_cache(
        db, exam_id=exam_id, school_id=school_id, cache_key=cache_key,
        scope=scope, subject_id=subject_id, class_id=class_id,
        model_version=model or "",
        result=result,
    )

    return result


async def _get_cache(db: AsyncSession, cache_key: str) -> dict | None:
    row = (await db.execute(
        text("SELECT result_json, expires_at FROM ai_diagnosis_cache WHERE cache_key = :k"),
        {"k": cache_key},
    )).first()
    if not row:
        return None
    expires = row.expires_at
    if expires:
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return None
    try:
        return json.loads(row.result_json)
    except (json.JSONDecodeError, TypeError):
        return None


async def _set_cache(
    db: AsyncSession,
    *,
    exam_id: str,
    school_id: str,
    cache_key: str,
    scope: str,
    subject_id: str | None,
    class_id: str | None,
    model_version: str,
    result: dict,
) -> None:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=CACHE_TTL_DAYS)

    await db.execute(
        text("DELETE FROM ai_diagnosis_cache WHERE cache_key = :k"),
        {"k": cache_key},
    )
    await db.execute(
        text(
            "INSERT INTO ai_diagnosis_cache "
            "(exam_id, school_id, cache_key, scope, subject_id, class_id, "
            " prompt_version, model_version, result_json, created_at, expires_at) "
            "VALUES (:exam_id, :school_id, :cache_key, :scope, :subject_id, :class_id, "
            " :prompt_version, :model_version, :result_json, :created_at, :expires_at)"
        ),
        {
            "exam_id": exam_id,
            "school_id": school_id,
            "cache_key": cache_key,
            "scope": scope,
            "subject_id": subject_id,
            "class_id": class_id,
            "prompt_version": PROMPT_VERSION,
            "model_version": model_version,
            "result_json": json.dumps(result, ensure_ascii=False),
            "created_at": now,
            "expires_at": expires,
        },
    )
    await db.commit()
