"""答题卡导出/渲染/发布子路由。"""
from __future__ import annotations
import logging
import tempfile
import urllib.parse
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.config import settings
from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.card.rendering.renderer import render_card_v2

logger = logging.getLogger(__name__)

router = APIRouter()


# --- v2 生成/预览 API ---


class CardGenerateV2Request(BaseModel):
    subject_code: str
    exam_id: str
    subject_id: str
    layout: dict


@router.post("/generate/v2")
async def generate_card_v2(
    body: CardGenerateV2Request,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """v2 答题卡生成：接收布局 JSON → 渲染 PDF + 写入 Template。"""
    from edu_cloud.modules.card.router import _get_skeleton_data

    skeleton = await _get_skeleton_data(body.subject_code, current["current_role"].school_id, db)

    # 获取科目（验证权限）
    subj_result = await db.execute(
        select(Subject).where(
            Subject.id == body.subject_id,
            Subject.school_id == current["current_role"].school_id,
        )
    )
    subject = subj_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")

    exam_result = await db.execute(
        select(Exam).where(Exam.id == body.exam_id, Exam.school_id == current["current_role"].school_id)
    )
    exam = exam_result.scalar_one_or_none()

    # 渲染 PDF
    pdf_bytes = render_card_v2(
        skeleton=skeleton,
        layout=body.layout,
        exam_name=exam.card_title if exam else "",
        subject_name=subject.name,
    )

    # 导出 paper-seg 兼容格式，写入 Template
    from edu_cloud.modules.card.export.export import skeleton_to_paperseg_json
    tpl_data = skeleton_to_paperseg_json(
        skeleton, body.layout,
        exam_id=str(body.exam_id),
        subject=subject.name if subject else "",
    )

    school_id = current["current_role"].school_id
    tpl_stmt = select(Template).where(Template.subject_id == body.subject_id, Template.side == "A")
    if school_id:
        tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
    tpl_result = await db.execute(tpl_stmt)
    tpl = tpl_result.scalar_one_or_none()

    template_values = {
        "image_width": tpl_data["image_size"]["width"],
        "image_height": tpl_data["image_size"]["height"],
        "anchors": tpl_data["anchors"],
        "regions": tpl_data["regions"],
        "school_id": current["current_role"].school_id,
    }

    if tpl:
        for k, v in template_values.items():
            setattr(tpl, k, v)
    else:
        tpl = Template(subject_id=body.subject_id, side="A", **template_values)
        db.add(tpl)

    await db.commit()
    logger.info("generate_card_v2: subject=%s, exam=%s, pdf=%d bytes, template=%s",
                body.subject_code, body.exam_id, len(pdf_bytes), "updated" if tpl else "created")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename*=UTF-8\'\'{urllib.parse.quote(f"答题卡_{subject.name}.pdf")}',
            "X-Template-Saved": "true",
        },
    )


@router.post("/preview/v2")
async def preview_card_v2(
    body: CardGenerateV2Request,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_EXAMS)),
):
    """v2 预览：渲染 PDF 但不写入 Template。"""
    from edu_cloud.modules.card.router import _get_skeleton_data

    skeleton = await _get_skeleton_data(body.subject_code, current["current_role"].school_id, db)

    subj_result = await db.execute(
        select(Subject).where(
            Subject.id == body.subject_id,
            Subject.school_id == current["current_role"].school_id,
        )
    )
    subject = subj_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")

    exam_result = await db.execute(
        select(Exam).where(Exam.id == body.exam_id, Exam.school_id == current["current_role"].school_id)
    )
    exam = exam_result.scalar_one_or_none()

    pdf_bytes = render_card_v2(
        skeleton=skeleton,
        layout=body.layout,
        exam_name=exam.card_title if exam else "",
        subject_name=subject.name,
    )

    return Response(content=pdf_bytes, media_type="application/pdf")


# --- HTML→PDF 导出 API ---


class HtmlExportRequest(BaseModel):
    html: str
    paper_size: str = "A3"


@router.post("/export/pdf")
async def export_card_pdf(
    body: HtmlExportRequest,
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """接收完整 HTML，用 playwright 转 PDF 返回。"""
    from edu_cloud.modules.card.export.html_export import html_to_pdf

    pdf_bytes = await html_to_pdf(body.html, body.paper_size)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.post("/export/skeleton")
async def export_card_skeleton(
    body: HtmlExportRequest,
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """接收完整 HTML，提取 skeleton JSON 返回。"""
    from edu_cloud.modules.card.export.html_export import extract_skeleton

    return await extract_skeleton(body.html)


class PublishCardRequest(BaseModel):
    html: str
    subject_id: str
    exam_id: str
    paper_size: str = "A3"


@router.post("/publish")
async def publish_card(
    body: PublishCardRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """原子发布答题卡：HTML→PDF + upsert Question + 双面 Template + status→scanning。

    F003 新实现：业务逻辑在 publish_service.publish_card_atomic。
    """
    from edu_cloud.modules.card.publish_service import publish_card_atomic

    pdf_bytes = await publish_card_atomic(
        db,
        html=body.html,
        subject_id=body.subject_id,
        exam_id=body.exam_id,
        school_id=current["current_role"].school_id,
        paper_size=body.paper_size,
    )
    return Response(content=pdf_bytes, media_type="application/pdf")


# ---------------------------------------------------------------------------
# Document → page images (render-doc-pages)
# ---------------------------------------------------------------------------

@router.post("/render-doc-pages")
async def render_doc_pages(
    file: UploadFile = File(...),
    subject_id: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """将上传的 Word/PDF 文档渲染为页面图片，返回每页 URL 和尺寸。"""
    # Validate subject belongs to the caller's school
    if subject_id:
        subj_result = await db.execute(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.school_id == current["current_role"].school_id,
            )
        )
        if not subj_result.scalar_one_or_none():
            raise HTTPException(403, "无权访问该科目")

    import fitz  # pymupdf

    filename = (file.filename or "").lower()
    if not filename.endswith((".docx", ".pdf")):
        raise HTTPException(400, "仅支持 .docx 或 .pdf 格式")

    suffix = ".pdf" if filename.endswith(".pdf") else ".docx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        try:
            doc = fitz.open(tmp_path)
        except Exception as exc:
            if suffix == ".docx":
                raise HTTPException(
                    400,
                    "无法打开 Word 文件，请先将其转换为 PDF 后重新上传",
                ) from exc
            raise HTTPException(400, f"无法打开 PDF 文件: {exc}") from exc

        if doc.page_count == 0:
            doc.close()
            raise HTTPException(400, "文档无内容（0 页）")

        batch_id = subject_id or uuid4().hex
        upload_root = Path(settings.UPLOAD_DIR).resolve()
        out_dir = upload_root / "doc-pages" / batch_id
        if out_dir.exists():
            import shutil
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        dpi = 200
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        pages = []
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix)
            img_name = f"page_{i}.png"
            img_path = out_dir / img_name
            pix.save(str(img_path))
            pages.append({
                "page_num": i,
                "image_url": f"/uploads/doc-pages/{batch_id}/{img_name}",
                "width": pix.width,
                "height": pix.height,
            })
        doc.close()
        logger.info(
            "render_doc_pages: %d pages rendered, batch=%s, dpi=%d",
            len(pages), batch_id, dpi,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"pages": pages}


@router.get("/doc-pages")
async def get_doc_pages(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_EXAMS)),
):
    """查询科目已有的文档页面图片。"""
    # Validate subject belongs to the caller's school
    subj_result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.school_id == current["current_role"].school_id,
        )
    )
    if not subj_result.scalar_one_or_none():
        raise HTTPException(403, "无权访问该科目")

    upload_root = Path(settings.UPLOAD_DIR).resolve()
    out_dir = upload_root / "doc-pages" / subject_id
    if not out_dir.is_dir():
        return {"pages": []}
    from PIL import Image as PILImage
    pages = []
    for img_path in sorted(out_dir.glob("page_*.png")):
        try:
            with PILImage.open(img_path) as im:
                w, h = im.size
        except Exception:
            continue
        i = int(img_path.stem.split("_")[1])
        pages.append({
            "page_num": i,
            "image_url": f"/uploads/doc-pages/{subject_id}/{img_path.name}",
            "width": w,
            "height": h,
        })
    return {"pages": pages}


@router.get("/doc-page-image")
async def get_doc_page_image(
    path: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_EXAMS)),
):
    """通过 API 路径代理 doc-pages 图片，避免 nginx 不代理 /uploads 的问题。"""
    from starlette.responses import FileResponse
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    # path 形如 /uploads/doc-pages/{batch}/{file}
    rel = path.lstrip("/")
    if rel.startswith("uploads/"):
        rel = rel[len("uploads/"):]
    full = (upload_root / rel).resolve()
    # Use is_relative_to for safe prefix check (prevents directory name prefix collisions)
    if not full.is_relative_to(upload_root) or not full.is_file():
        raise HTTPException(404, "Image not found")

    # If path is under doc-pages/{subject_id}/..., validate subject ownership
    import re
    m = re.match(r"doc-pages/([^/]+)/", rel)
    if m:
        subject_id = m.group(1)
        subj_result = await db.execute(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.school_id == current["current_role"].school_id,
            )
        )
        if not subj_result.scalar_one_or_none():
            raise HTTPException(403, "无权访问该科目图片")

    return FileResponse(str(full), media_type="image/png")
