"""答题卡模板/骨架管理子路由。"""
from __future__ import annotations
import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.modules.card.models import CardSkeleton

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Word 答案模板 API ---

@router.get("/template/download")
async def download_answer_template(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """根据科目题目列表生成 Word 答案模板骨架，教师下载后填答案。"""
    from edu_cloud.modules.exam.models import Question, Subject
    from edu_cloud.modules.card.parser.word_parser import generate_word_template
    from fastapi.responses import Response
    import urllib.parse

    subj_row = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == current["current_role"].school_id)
    )
    subject = subj_row.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")

    result = await db.execute(
        select(Question).where(
            Question.subject_id == subject_id,
            Question.school_id == current["current_role"].school_id,
        )
    )
    questions = result.scalars().all()
    if not questions:
        raise HTTPException(400, "该科目还没有创建题目")

    q_list = [{"number": i + 1, "question_type": q.question_type} for i, q in enumerate(
        sorted(questions, key=lambda q: q.name)
    )]

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        generate_word_template(q_list, tmp_path)
        docx_bytes = Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename*=UTF-8\'\'{urllib.parse.quote(f"答案模板_{subject.name}.docx")}',
        },
    )


# --- 内置模板 API ---

@router.get("/templates/builtin")
async def list_builtin_templates(
    current: dict = Depends(get_current_user),
):
    """列出所有内置模板科目。"""
    from edu_cloud.modules.card.template.template_library import list_builtin_subjects
    return {"subjects": list_builtin_subjects()}


@router.get("/templates/builtin/{subject}")
async def get_builtin_template_detail(
    subject: str,
    current: dict = Depends(get_current_user),
):
    """获取内置模板详情。"""
    from edu_cloud.modules.card.template.template_library import get_builtin_template
    tpl = get_builtin_template(subject)
    if not tpl:
        raise HTTPException(404, f"科目 {subject} 无内置模板")
    return tpl


# --- 骨架管理 API ---

@router.post("/skeleton/import")
async def import_skeleton(
    file: UploadFile = File(...),
    subject_code: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """上传 .tpl 文件，解析为 CardSkeleton 并存入数据库。"""
    if not file.filename or not file.filename.endswith(".tpl"):
        raise HTTPException(400, "请上传 .tpl 文件")

    with tempfile.NamedTemporaryFile(suffix=".tpl", delete=False, mode="wb") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        from edu_cloud.modules.card.rendering.tpl_parser import parse_tpl_file
        skeleton_data = parse_tpl_file(tmp_path)
        # 不存储大尺寸背景图到数据库
        skeleton_data.pop("tpl_images", None)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("import_skeleton: parse failed, file=%s, subject=%s, error=%s", file.filename, subject_code, e)
        raise HTTPException(400, f"解析 .tpl 文件失败: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    # upsert
    result = await db.execute(
        select(CardSkeleton).where(
            CardSkeleton.school_id == current["current_role"].school_id,
            CardSkeleton.subject_code == subject_code,
        )
    )
    existing = result.scalar_one_or_none()
    is_update = existing is not None
    if existing:
        existing.skeleton_data = skeleton_data
        existing.paper_size = skeleton_data.get("paper_size", "A3")
    else:
        existing = CardSkeleton(
            school_id=current["current_role"].school_id,
            subject_code=subject_code,
            paper_size=skeleton_data.get("paper_size", "A3"),
            skeleton_data=skeleton_data,
        )
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    logger.info("import_skeleton: subject=%s, paper=%s, action=%s, slots=%d",
                subject_code, existing.paper_size,
                "update" if is_update else "create",
                len(skeleton_data.get("subjective_slots", [])))

    return {
        "id": existing.id,
        "subject_code": existing.subject_code,
        "paper_size": existing.paper_size,
        "skeleton_data": existing.skeleton_data,
    }


@router.get("/skeleton/list")
async def list_skeletons(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """列出当前学校所有已导入骨架。"""
    result = await db.execute(
        select(CardSkeleton).where(
            CardSkeleton.school_id == current["current_role"].school_id,
        )
    )
    skeletons = result.scalars().all()
    return [
        {
            "id": s.id,
            "subject_code": s.subject_code,
            "paper_size": s.paper_size,
            "slots_count": len(s.skeleton_data.get("subjective_slots", [])),
            "obj_groups_count": len(s.skeleton_data.get("objective_groups", [])),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in skeletons
    ]


@router.get("/skeleton/{subject_code}")
async def get_skeleton(
    subject_code: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """获取骨架详情。"""
    result = await db.execute(
        select(CardSkeleton).where(
            CardSkeleton.school_id == current["current_role"].school_id,
            CardSkeleton.subject_code == subject_code,
        )
    )
    skeleton = result.scalar_one_or_none()
    if not skeleton:
        raise HTTPException(404, "骨架不存在")
    return {
        "id": skeleton.id,
        "subject_code": skeleton.subject_code,
        "paper_size": skeleton.paper_size,
        "skeleton_data": skeleton.skeleton_data,
    }


@router.delete("/skeleton/{subject_code}")
async def delete_skeleton(
    subject_code: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """删除骨架。"""
    result = await db.execute(
        select(CardSkeleton).where(
            CardSkeleton.school_id == current["current_role"].school_id,
            CardSkeleton.subject_code == subject_code,
        )
    )
    skeleton = result.scalar_one_or_none()
    if not skeleton:
        raise HTTPException(404, "骨架不存在")
    logger.info("delete_skeleton: subject=%s", subject_code)
    await db.delete(skeleton)
    await db.commit()
    return {"ok": True}
