"""扫描流水线 API 端点。"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Callable, Awaitable

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.config import settings
from edu_cloud.database import get_db
# R4-F001: 运行时属性查找，让 client fixture monkey-patch 生效
import edu_cloud.database as db_mod
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.exam.models import Subject, Question, QUESTION_TYPES_OBJECTIVE
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.shared.storage import get_storage, StorageService
from . import pipeline_service
from .tpl_parser import parse_tpl_file

logger = logging.getLogger(__name__)


def build_pipeline_save_answer_fn(
    regions: list[dict],
    exam_id: str,
    subject_id: str,
    school_id: str,
    _session_factory=None,
) -> Callable[..., Awaitable[None]]:
    """构造 pipeline 的 save_answer_fn 闭包——region_id → question_id 反查 + 写 StudentAnswer。"""
    session_factory = _session_factory or db_mod.async_session
    region_map: dict[str, str] = {
        r["id"]: r["question_id"]
        for r in (regions or [])
        if r.get("question_id")
    }

    async def save_answer(
        exam_id: str,
        subject_id: str,
        student_id: str,
        question_id: str,
        image_path: str,
        school_id: str,
    ) -> None:
        region_id = question_id
        real_qid = region_map.get(region_id)
        if not real_qid:
            logger.warning(
                "pipeline_orphan_crop: region_id=%s not in region_map (subject=%s, student=%s), skip",
                region_id, subject_id, student_id,
            )
            return

        async with session_factory() as db2:
            db2.add(StudentAnswer(
                exam_id=exam_id,
                subject_id=subject_id,
                student_id=student_id,
                question_id=real_qid,
                image_path=image_path,
                school_id=school_id,
            ))
            try:
                await db2.commit()
            except IntegrityError:
                await db2.rollback()
                logger.debug(
                    "pipeline_duplicate_answer: student=%s question=%s already exists, skip",
                    student_id, real_qid,
                )

    return save_answer


def build_pipeline_save_objective_fn(
    regions: list[dict],
    questions_by_group: dict[str, list[dict]],
    exam_id: str,
    subject_id: str,
    school_id: str,
    _session_factory=None,
) -> Callable[..., Awaitable[None]]:
    """构造 pipeline 的 save_objective_fn 闭包 — 选择题判分 + 写 StudentAnswer。

    INV-002: 映射 key 为 (group_id, row_index) 二元组，不依赖全局枚举。
    """
    from edu_cloud.modules.scan.objective_grading import grade_objective_answer

    session_factory = _session_factory or db_mod.async_session

    # 构建 (group_id, row_index) → question dict 的映射
    question_lookup: dict[tuple[str, int], dict] = {}
    for group_id, q_list in (questions_by_group or {}).items():
        for q in q_list:
            row_idx = q.get("row_index")
            if row_idx is not None:
                question_lookup[(group_id, row_idx)] = q

    async def save_objective(
        exam_id: str,
        subject_id: str,
        student_id: str,
        group_id: str,
        row_index: int,
        detected_answer: str,
        fill_ratios: dict,
        anomaly: bool,
        school_id: str,
    ) -> None:
        q = question_lookup.get((group_id, row_index))
        if not q:
            logger.warning(
                "pipeline_orphan_objective: group=%s, row_index=%d not in lookup, skip",
                group_id, row_index,
            )
            return

        correct_answer = q.get("correct_answer", "")
        max_score = q.get("max_score", 0.0)
        score, _ = grade_objective_answer(detected_answer, correct_answer, max_score)

        async with session_factory() as db2:
            db2.add(StudentAnswer(
                exam_id=exam_id,
                subject_id=subject_id,
                student_id=student_id,
                question_id=q["id"],
                detected_answer=detected_answer,
                score=score,
                fill_ratios=fill_ratios or None,
                is_anomaly=anomaly,
                school_id=school_id,
            ))
            try:
                await db2.commit()
            except IntegrityError:
                await db2.rollback()
                logger.debug(
                    "pipeline_duplicate_objective: student=%s question=%s already exists, skip",
                    student_id, q["id"],
                )

    return save_objective


router = APIRouter(prefix="/api/v1/scan/pipeline", tags=["scan-pipeline"])


class StartPipelineRequest(BaseModel):
    subject_id: str
    side: str = "A"
    image_dir: str
    tpl_path: str | None = None  # 可选：.tpl 文件路径（替代 Template 表）


class ImportTplRequest(BaseModel):
    tpl_path: str
    subject_id: str
    side: str = "A"


class PreviewRequest(BaseModel):
    image_path: str | None = None  # 指定图片路径
    image_dir: str | None = None   # 或指定目录（自动取第一张）
    subject_id: str
    side: str = "A"


class BrowseDirRequest(BaseModel):
    path: str = ""


@router.post("/browse-dir")
async def browse_directory(
    req: BrowseDirRequest,
    current: dict = Depends(get_current_user),
):
    """浏览服务器目录，返回子文件夹列表。"""
    d = Path(req.path) if req.path else Path(settings.UPLOAD_DIR).resolve()
    if not d.is_dir():
        raise HTTPException(400, f"目录不存在: {req.path}")

    items = []
    try:
        for entry in sorted(d.iterdir()):
            if entry.is_dir() and not entry.name.startswith('.'):
                img_count = sum(1 for f in entry.iterdir()
                                if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".bmp"))
                sub_count = sum(1 for f in entry.iterdir() if f.is_dir())
                items.append({
                    "name": entry.name,
                    "path": str(entry),
                    "has_images": img_count > 0,
                    "image_count": img_count,
                    "sub_dirs": sub_count,
                })
    except PermissionError:
        raise HTTPException(403, f"无权访问: {req.path}")

    parent = str(d.parent) if str(d) != "/" else None
    return {"current": str(d), "parent": parent, "items": items}


@router.post("/upload-folder")
async def upload_scan_folder(
    exam_id: str = Form(...),
    files: list[UploadFile] = File(...),
    current: dict = Depends(get_current_user),
):
    """接收用户上传的扫描图片，按子文件夹结构保存到服务器。"""
    school_id = current["current_role"].school_id
    base_dir = Path(settings.UPLOAD_DIR).resolve() / "scan-input" / exam_id
    base_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for f in files:
        if not f.filename:
            continue
        rel = f.filename
        parts = rel.replace("\\", "/").split("/")
        if len(parts) >= 2:
            sub_dir = parts[-2]
            fname = parts[-1]
        else:
            sub_dir = "未分类"
            fname = parts[-1]

        if not fname.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
            continue

        target_dir = base_dir / sub_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / fname
        content = await f.read()
        target.write_bytes(content)
        saved += 1

    logger.info("upload_scan_folder: exam=%s saved=%d dir=%s", exam_id, saved, base_dir)
    return {"dir_path": str(base_dir), "saved": saved}


class ScanDirRequest(BaseModel):
    dir_path: str


@router.post("/scan-dir")
async def scan_directory(
    req: ScanDirRequest,
    current: dict = Depends(get_current_user),
):
    """扫描目录结构，返回科目子文件夹和图片统计。"""
    d = Path(req.dir_path)
    if not d.is_dir():
        raise HTTPException(400, f"目录不存在: {req.dir_path}")

    subjects = []
    for sub in sorted(d.iterdir()):
        if sub.is_dir():
            imgs = [f for f in sub.iterdir() if f.suffix.lower() in (".png", ".jpg", ".bmp")]
            if imgs:
                a_count = sum(1 for f in imgs if f.stem.endswith("A"))
                b_count = sum(1 for f in imgs if f.stem.endswith("B"))
                a_imgs = sorted(f for f in imgs if f.stem.endswith("A"))
                subjects.append({
                    "name": sub.name,
                    "folder": sub.name,
                    "image_count": len(imgs),
                    "a_count": a_count,
                    "b_count": b_count,
                    "student_count": max(a_count, b_count),
                    "first_file": a_imgs[0].name if a_imgs else imgs[0].name,
                })

    # 根目录本身有图片且无科目子目录
    if not subjects:
        imgs = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".bmp")]
        if imgs:
            a_count = sum(1 for f in imgs if f.stem.endswith("A"))
            b_count = sum(1 for f in imgs if f.stem.endswith("B"))
            a_imgs = sorted(f for f in imgs if f.stem.endswith("A"))
            subjects.append({
                "name": d.name,
                "folder": ".",
                "image_count": len(imgs),
                "a_count": a_count,
                "b_count": b_count,
                "student_count": max(a_count, b_count),
                "first_file": a_imgs[0].name if a_imgs else imgs[0].name,
            })

    return {"dir_path": req.dir_path, "subjects": subjects}


@router.post("/start")
async def start_pipeline(
    req: StartPipelineRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
    storage: StorageService = Depends(get_storage),
):
    """启动扫描切割流水线。"""
    school_id = current["current_role"].school_id

    # 验证目录
    if not os.path.isdir(req.image_dir):
        raise HTTPException(400, f"目录不存在: {req.image_dir}")

    # 获取 subject（platform_admin 可跨校）
    q = select(Subject).where(Subject.id == req.subject_id)
    if school_id:
        q = q.where(Subject.school_id == school_id)
    subject = (await db.execute(q)).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")
    school_id = subject.school_id

    # 加载模板
    if req.tpl_path:
        if not os.path.isfile(req.tpl_path):
            raise HTTPException(400, f"tpl 文件不存在: {req.tpl_path}")
        template = parse_tpl_file(req.tpl_path)
    else:
        tpl = (await db.execute(
            select(Template).where(
                Template.subject_id == req.subject_id,
                Template.side == req.side,
            )
        )).scalar_one_or_none()
        if not tpl:
            raise HTTPException(404, "模板不存在，请先发布答题卡或导入 .tpl 文件")
        bc_region = None
        for r in (tpl.regions or []):
            if r.get("type") == "barcode" and r.get("rect"):
                bc_region = r["rect"]
                break
        template = {
            "image_size": {"width": tpl.image_width, "height": tpl.image_height},
            "anchors": tpl.anchors or [],
            "regions": tpl.regions or [],
            "barcode_region": bc_region,
        }

    # 列出文件
    try:
        files = pipeline_service.list_scan_images(req.image_dir, req.side)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))

    if not files:
        raise HTTPException(400, f"目录下没有 {req.side} 面的 PNG 文件")

    # 按 school/exam/subject 隔离的输出目录
    output_dir = os.path.join(storage.root, school_id, subject.exam_id, req.subject_id)

    # F003: 统一装配 save_answer_fn（两条分支都从 template["regions"] 提取）
    regions_for_factory: list[dict] = template.get("regions") or []
    save_answer_fn = build_pipeline_save_answer_fn(
        regions=regions_for_factory,
        exam_id=subject.exam_id,
        subject_id=req.subject_id,
        school_id=school_id,
    )

    if not any(r.get("question_id") for r in regions_for_factory):
        logger.warning(
            "pipeline start: empty region_map for subject=%s side=%s",
            req.subject_id, req.side,
        )

    # Gate 2 R1 F001 修复：装配 save_objective_fn
    # INV-002: 通过 region.question_ids 显式关联（Template 分支优先）
    # Gate 2 R2 F005 修复：tpl_path 分支走 fallback — 按 qg_indexno 顺序从 DB 取 objective 题目
    choice_regions = [r for r in regions_for_factory if r.get("type") == "choice_group"]
    questions_by_group: dict[str, list[dict]] = {}

    # 先尝试从 region.question_ids 构造（Template 分支）
    has_question_ids = any(cr.get("question_ids") for cr in choice_regions)

    if has_question_ids:
        for cr in choice_regions:
            gid = cr.get("id", "")
            q_ids = cr.get("question_ids", [])
            if not q_ids:
                continue
            group_questions = (await db.execute(
                select(Question).where(
                    Question.id.in_(q_ids),
                    Question.school_id == school_id,
                )
            )).scalars().all()
            q_by_id = {q.id: q for q in group_questions}
            group_qs = []
            for row_idx, qid in enumerate(q_ids, 1):
                q = q_by_id.get(qid)
                if q:
                    group_qs.append({
                        "id": q.id, "row_index": row_idx,
                        "correct_answer": q.correct_answer, "max_score": q.max_score,
                    })
            questions_by_group[gid] = group_qs
    elif choice_regions:
        # F005 fallback (R3 修复): tpl_path 分支无 question_ids 时按题号映射
        # 项目契约：Question.name 存题号字符串，export.py 按 start_no+i 生成 question_ids
        # 不能按 created_at 线性消费——必须按 Question.name 数字值查找
        objective_questions = (await db.execute(
            select(Question).where(
                Question.subject_id == req.subject_id,
                Question.school_id == school_id,
                Question.question_type.in_(QUESTION_TYPES_OBJECTIVE),
            )
        )).scalars().all()

        # 构建题号 → Question 的映射（Question.name 是题号字符串）
        def _parse_qno(name: str) -> int | None:
            try:
                return int((name or "").strip())
            except (ValueError, TypeError):
                return None

        qno_to_q = {}
        for q in objective_questions:
            qno = _parse_qno(q.name)
            if qno is not None:
                qno_to_q[qno] = q

        # 按 qg_indexno 排序 choice_regions，每组起始题号从 qg_indexno 开始（首组=1 若未指定）
        # 每组消耗 rows 个连续题号
        next_start_no = 1
        for cr in sorted(choice_regions, key=lambda r: r.get("qg_indexno", 0)):
            gid = cr.get("id", "")
            rows = cr.get("rows", 1)
            # 如果 region 显式给了 start_no 用它；否则用递增 next_start_no
            start_no = cr.get("start_no", next_start_no)
            group_qs = []
            for row_idx in range(1, rows + 1):
                qno = start_no + row_idx - 1
                q = qno_to_q.get(qno)
                if q:
                    group_qs.append({
                        "id": q.id, "row_index": row_idx,
                        "correct_answer": q.correct_answer, "max_score": q.max_score,
                    })
            if group_qs:
                questions_by_group[gid] = group_qs
            next_start_no = start_no + rows

    save_objective_fn = build_pipeline_save_objective_fn(
        regions=regions_for_factory,
        questions_by_group=questions_by_group,
        exam_id=subject.exam_id,
        subject_id=req.subject_id,
        school_id=school_id,
    ) if questions_by_group else None

    # 入队（F009 修复：每个科目携带自己的 save_fn）
    pipeline_service.enqueue_pipeline(
        save_answer_fn=save_answer_fn,
        save_objective_fn=save_objective_fn,
        image_dir=req.image_dir,
        template=template,
        output_dir=output_dir,
        exam_id=subject.exam_id,
        subject_id=req.subject_id,
        school_id=school_id,
        side=req.side,
    )

    # 如果没有正在运行的队列，启动队列处理
    if not pipeline_service.is_running():
        asyncio.create_task(pipeline_service.run_queue())

    queue_len = len(pipeline_service._queue) + (1 if pipeline_service.is_running() else 0)
    logger.info("Pipeline queued: subject=%s, dir=%s, files=%d, queue=%d",
                subject.name, req.image_dir, len(files), queue_len)
    return {"status": "queued", "total_files": len(files), "queue_length": queue_len}


@router.get("/progress")
async def get_progress(current: dict = Depends(get_current_user)):
    """获取流水线进度。"""
    return pipeline_service.get_progress()


@router.post("/stop")
async def stop_pipeline(current: dict = Depends(get_current_user)):
    """停止流水线。"""
    if not pipeline_service.is_running():
        raise HTTPException(400, "流水线未在运行")
    pipeline_service.request_stop()
    return {"status": "stopping"}


@router.post("/preview")
async def preview_scan(
    req: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """预览单张扫描图的切割区域标注。"""
    import base64
    from PIL import Image, ImageDraw
    from io import BytesIO

    school_id = current["current_role"].school_id

    # 解析图片路径：指定路径 or 从目录取第一张
    image_path = req.image_path
    if not image_path and req.image_dir:
        try:
            files = pipeline_service.list_scan_images(req.image_dir, req.side)
            if files:
                image_path = str(files[0])
        except FileNotFoundError:
            pass
    if not image_path:
        raise HTTPException(400, "请指定图片路径或扫描目录")

    if not os.path.isfile(image_path):
        raise HTTPException(400, f"文件不存在: {image_path}")

    # 加载模板
    tpl = (await db.execute(
        select(Template).where(
            Template.subject_id == req.subject_id,
            Template.side == req.side,
        )
    )).scalar_one_or_none()
    if not tpl:
        raise HTTPException(404, "模板不存在")

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    img_w, img_h = img.size
    sx = img_w / (tpl.image_width or img_w)
    sy = img_h / (tpl.image_height or img_h)

    # 标注定位点（红框）
    from .vision import detect_anchors
    import numpy as np
    gray = np.array(img.convert("L"))
    anchors = detect_anchors(gray)
    for a in anchors:
        x, y, w, h = a["x"], a["y"], a["w"], a["h"]
        draw.rectangle([x, y, x + w, y + h], outline="red", width=3)
        draw.text((x, y - 12), a["id"], fill="red")

    # 标注切割区域（蓝框）
    for r in (tpl.regions or []):
        rect = r.get("rect", {})
        x1 = int(rect.get("x1", 0) * sx)
        y1 = int(rect.get("y1", 0) * sy)
        x2 = int(rect.get("x2", 0) * sx)
        y2 = int(rect.get("y2", 0) * sy)
        color = "blue" if r.get("type") == "subjective" else "green"
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        draw.text((x1 + 2, y1 + 2), r.get("name", r.get("id", "")), fill=color)

    # 缩小图片（原图太大）
    max_w = 1200
    if img_w > max_w:
        ratio = max_w / img_w
        img = img.resize((max_w, int(img_h * ratio)))

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {"image": f"data:image/jpeg;base64,{b64}", "anchors": len(anchors)}


@router.post("/import-tpl")
async def import_tpl(
    req: ImportTplRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """导入 .tpl 文件到 Template 表。"""
    school_id = current["current_role"].school_id

    if not os.path.isfile(req.tpl_path):
        raise HTTPException(400, f"tpl 文件不存在: {req.tpl_path}")

    q = select(Subject).where(Subject.id == req.subject_id)
    if school_id:
        q = q.where(Subject.school_id == school_id)
    subject = (await db.execute(q)).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")
    school_id = subject.school_id

    tpl_data = parse_tpl_file(req.tpl_path)

    # Upsert Template
    existing = (await db.execute(
        select(Template).where(
            Template.subject_id == req.subject_id,
            Template.side == req.side,
        )
    )).scalar_one_or_none()

    values = {
        "image_width": tpl_data["image_size"]["width"],
        "image_height": tpl_data["image_size"]["height"],
        "anchors": tpl_data["anchors"],
        "regions": tpl_data["regions"],
    }

    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
    else:
        existing = Template(
            subject_id=req.subject_id, side=req.side, school_id=school_id, **values,
        )
        db.add(existing)

    await db.commit()
    await db.refresh(existing)
    logger.info("import_tpl: subject=%s, side=%s, regions=%d",
                subject.name, req.side, len(tpl_data["regions"]))
    return {"id": existing.id, "regions": len(tpl_data["regions"]), "anchors": len(tpl_data["anchors"])}


# === 扫描图片服务 ===

@router.get('/scan-image')
async def serve_scan_image(
    path: str,
    current: dict = Depends(get_current_user),
):
    """提供扫描图片的 HTTP 访问（前端模板编辑器用）。"""
    from fastapi.responses import FileResponse
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    if path.startswith("/uploads/"):
        resolved = upload_root / path.split("/uploads/", 1)[1]
    elif path.startswith("/"):
        resolved = Path(path)
    else:
        resolved = upload_root / path
    if not resolved.is_file():
        raise HTTPException(404, f"图片不存在: {path}")
    if not str(resolved.resolve()).startswith(str(upload_root.resolve())):
        raise HTTPException(403, "只能访问 uploads 目录下的图片")
    suffix = resolved.suffix.lower()
    media = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(suffix.lstrip("."), "application/octet-stream")
    return FileResponse(resolved, media_type=media)


# === OpenCV + LLM 混合检测 ===
from edu_cloud.modules.scan.auto_detect_cv import AutoDetectCVRequest, auto_detect_cv_regions

@router.post('/auto-detect-cv')
async def auto_detect_cv_api(
    req: AutoDetectCVRequest,
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    return await auto_detect_cv_regions(req)


# === 查询已有 Template ===

@router.get('/cv-template')
async def get_cv_template(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    """查询某科目已有的 CV 检测 Template（A+B 面）。"""
    rows = (await db.execute(
        select(Template).where(Template.subject_id == subject_id)
    )).scalars().all()
    if not rows:
        raise HTTPException(404, "该科目尚无模板")
    result = {}
    for t in rows:
        result[t.side] = {
            "regions": t.regions or [],
            "width": t.image_width,
            "height": t.image_height,
        }
    return result


# === 保存 CV 检测结果为 Template ===

class SaveCVTemplateRequest(BaseModel):
    subject_id: str
    side: str = "A"
    regions: list[dict]
    width: int
    height: int


@router.post('/save-cv-template')
async def save_cv_template(
    req: SaveCVTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    """将 CV 检测结果保存/更新为 Template（upsert）。"""
    school_id = current["current_role"].school_id

    q = select(Subject).where(Subject.id == req.subject_id)
    if school_id:
        q = q.where(Subject.school_id == school_id)
    subject = (await db.execute(q)).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")
    school_id = subject.school_id

    questions = (await db.execute(
        select(Question).where(Question.subject_id == req.subject_id)
    )).scalars().all()
    qno_map = {}
    for q in questions:
        try:
            qno_map[int(q.name)] = str(q.id)
        except (ValueError, TypeError):
            pass

    def _region_to_qtype(r):
        if r.get("type") == "choice_group":
            return "choice"
        return r.get("question_type", "essay")

    for r in req.regions:
        if r.get("type") == "not_a_region":
            continue
        qno = r.get("qno")
        if not qno:
            continue

        if r.get("type") == "choice_group":
            start = r.get("start_no", 1)
            rows = r.get("rows", 0)
            for n in range(start, start + rows):
                if n not in qno_map:
                    new_q = Question(
                        subject_id=req.subject_id,
                        name=str(n),
                        question_type="choice",
                        max_score=r.get("score", 0),
                        school_id=school_id,
                    )
                    db.add(new_q)
                    await db.flush()
                    qno_map[n] = str(new_q.id)
                    logger.info("auto_create_question: subject=%s qno=%d type=choice", subject.name, n)
        else:
            if qno not in qno_map:
                new_q = Question(
                    subject_id=req.subject_id,
                    name=str(qno),
                    question_type=_region_to_qtype(r),
                    max_score=r.get("score", 0),
                    school_id=school_id,
                )
                db.add(new_q)
                await db.flush()
                qno_map[qno] = str(new_q.id)
                logger.info("auto_create_question: subject=%s qno=%d type=%s", subject.name, qno, new_q.question_type)

        if qno in qno_map:
            r["question_id"] = qno_map[qno]
        qnos = r.get("qnos")
        if qnos:
            r["question_ids"] = [qno_map[n] for n in qnos if n in qno_map]

    regions = [r for r in req.regions if r.get("type") != "not_a_region"]

    existing = (await db.execute(
        select(Template).where(
            Template.subject_id == req.subject_id,
            Template.side == req.side,
        )
    )).scalar_one_or_none()

    if existing:
        existing.regions = regions
        existing.image_width = req.width
        existing.image_height = req.height
    else:
        existing = Template(
            subject_id=req.subject_id,
            side=req.side,
            regions=regions,
            image_width=req.width,
            image_height=req.height,
            school_id=school_id,
        )
        db.add(existing)

    await db.commit()
    logger.info("save_cv_template: subject=%s side=%s regions=%d",
                subject.name, req.side, len(regions))
    return {"id": str(existing.id), "regions": len(regions)}
