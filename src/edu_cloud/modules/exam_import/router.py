"""Exam-import API — upload, preview, mapping, commit, status, cancel.

Five endpoints under /api/v1/exam-imports with school_id isolation.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import get_db
from edu_cloud.config import settings
from edu_cloud.core.auth import get_tenant_context, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.core.tenant import TenantContext
from edu_cloud.modules.exam_import import parser, service
from edu_cloud.modules.exam_import.models import ExamImportSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/exam-imports", tags=["exam-import"])

ALLOWED_EXTENSIONS = {".xlsx", ".zip"}


def _school_id_from(tenant: TenantContext) -> str:
    """Require a concrete school scope for exam import operations."""
    return tenant.require_school()


async def _get_session(
    db: AsyncSession,
    import_id: str,
    school_id: str,
) -> ExamImportSession:
    """Load a session with school_id isolation; raise 404 on miss."""
    stmt = select(ExamImportSession).where(
        ExamImportSession.id == import_id,
        ExamImportSession.school_id == school_id,
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "导入会话不存在")
    return session


# ── POST "" — upload + parse + preview ───────────────────────────


@router.post("", status_code=201)
async def create_import(
    file: UploadFile = File(...),
    exam_name: str = Form(...),
    exam_type: str = Form(...),
    grade_scope: str = Form(...),
    import_mode: str = Form("questions"),
    exam_date: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
    tenant: TenantContext = Depends(get_tenant_context),
):
    school_id = _school_id_from(tenant)

    # validate import_mode
    if import_mode not in ("questions", "totals"):
        raise HTTPException(400, f"不支持的导入模式: {import_mode}")

    # validate file extension
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"不支持的文件格式: {ext}（支持 .xlsx 和 .zip，不支持 .xls）",
        )

    # save uploaded file
    upload_dir = Path(settings.UPLOAD_DIR) / school_id / "exam-imports"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{ext}"
    file_path = upload_dir / safe_name

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # parse
    try:
        if ext == ".zip":
            parsed = parser.parse_zip(str(file_path))
        elif import_mode == "questions":
            parsed = parser.parse_question_scores_xlsx(str(file_path))
        else:
            parsed = parser.parse_totals_xlsx(str(file_path))
    except Exception as exc:
        logger.error("解析文件失败: %s", exc, exc_info=True)
        raise HTTPException(400, f"文件解析失败: {exc}") from exc

    # collect all students across subjects for matching
    all_students = []
    for subj in parsed.subjects:
        all_students.extend(subj.students)

    match_result = await service.match_students(db, all_students, school_id)

    # questions that may need manual confirmation
    questions_need_confirm = []
    for subj in parsed.subjects:
        for q in subj.questions:
            if q.max_score_inferred:
                questions_need_confirm.append({
                    "subject": subj.subject_name,
                    "question": q.name,
                    "inferred_max_score": q.max_score,
                })

    match_summary = {
        "matched": len(match_result.matched),
        "unmatched": len(match_result.unmatched),
        "ambiguous": len(match_result.ambiguous),
    }

    preview_data = {
        "subjects": [
            {
                "name": s.subject_name,
                "code": s.subject_code,
                "student_count": len(s.students),
                "question_count": len(s.questions),
            }
            for s in parsed.subjects
        ],
        "match_summary": match_summary,
        "questions_need_confirm": questions_need_confirm,
        "warnings": parsed.warnings,
    }

    # create session
    session = ExamImportSession(
        school_id=school_id,
        exam_name=exam_name,
        exam_type=exam_type,
        grade_scope=grade_scope,
        import_mode=import_mode,
        exam_date=exam_date or None,
        status="previewing",
        file_path=str(file_path),
        preview_data=preview_data,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "import_id": session.id,
        "status": session.status,
        "preview": preview_data,
    }


# ── PATCH "/{import_id}/mapping" — update mapping ───────────────


@router.patch("/{import_id}/mapping")
async def update_mapping(
    import_id: str,
    mapping: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
    tenant: TenantContext = Depends(get_tenant_context),
):
    school_id = _school_id_from(tenant)
    session = await _get_session(db, import_id, school_id)

    if session.status != "previewing":
        raise HTTPException(400, f"当前状态 {session.status} 不允许修改映射")

    session.mapping_data = mapping
    await db.commit()

    return {"import_id": session.id, "status": session.status, "mapping_data": mapping}


# ── POST "/{import_id}/commit" — commit import ──────────────────


@router.post("/{import_id}/commit")
async def commit_import(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
    tenant: TenantContext = Depends(get_tenant_context),
):
    school_id = _school_id_from(tenant)
    session = await _get_session(db, import_id, school_id)

    if session.status != "previewing":
        raise HTTPException(400, f"当前状态 {session.status} 不允许提交")

    try:
        # re-parse from file
        file_path = session.file_path
        ext = Path(file_path).suffix.lower()

        if ext == ".zip":
            parsed = parser.parse_zip(file_path)
        elif session.import_mode == "questions":
            parsed = parser.parse_question_scores_xlsx(file_path)
        else:
            parsed = parser.parse_totals_xlsx(file_path)

        # re-match students
        all_students = []
        for subj in parsed.subjects:
            all_students.extend(subj.students)

        match_result = await service.match_students(db, all_students, school_id)

        # build matched_students dict keyed by student_key
        matched_dict = {m.parsed.student_key: m for m in match_result.matched}

        # commit
        stats = await service.commit_import(
            db,
            parsed=parsed,
            matched_students=matched_dict,
            school_id=school_id,
            exam_name=session.exam_name,
            exam_type=session.exam_type,
            grade_scope=session.grade_scope,
            import_mode=session.import_mode,
            exam_date=session.exam_date,
        )

        # post-import pipeline
        pipeline_result = await service.run_post_import_pipeline(
            db,
            exam_id=stats["exam_id"],
            school_id=school_id,
            import_mode=session.import_mode,
            parsed=parsed,
            matched_students=matched_dict,
        )

        # update session
        session.status = "committed"
        session.exam_id = stats["exam_id"]
        session.committed_by = current["user"].id
        session.result_summary = {**stats, "pipeline": pipeline_result}
        await db.commit()

        return {
            "import_id": session.id,
            "status": session.status,
            "exam_id": session.exam_id,
            "result_summary": session.result_summary,
        }

    except Exception as exc:
        logger.error("导入提交失败: %s", exc, exc_info=True)
        session.status = "failed"
        session.result_summary = {"error": str(exc)}
        await db.commit()
        raise HTTPException(500, f"导入提交失败: {exc}") from exc


# ── GET "/{import_id}" — session status ──────────────────────────


@router.get("/{import_id}")
async def get_import_status(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
    tenant: TenantContext = Depends(get_tenant_context),
):
    school_id = _school_id_from(tenant)
    session = await _get_session(db, import_id, school_id)

    return {
        "import_id": session.id,
        "status": session.status,
        "exam_name": session.exam_name,
        "exam_type": session.exam_type,
        "grade_scope": session.grade_scope,
        "import_mode": session.import_mode,
        "exam_date": session.exam_date,
        "preview_data": session.preview_data,
        "mapping_data": session.mapping_data,
        "result_summary": session.result_summary,
        "exam_id": session.exam_id,
        "created_at": str(session.created_at) if session.created_at else None,
    }


# ── DELETE "/{import_id}" — cancel ───────────────────────────────


@router.delete("/{import_id}")
async def cancel_import(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
    tenant: TenantContext = Depends(get_tenant_context),
):
    school_id = _school_id_from(tenant)
    session = await _get_session(db, import_id, school_id)

    if session.status == "committed":
        raise HTTPException(400, "已提交的导入会话无法取消")

    session.status = "cancelled"
    await db.commit()

    return {"import_id": session.id, "status": "cancelled"}
