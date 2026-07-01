"""扫描流水线 API 端点。"""

import logging
import asyncio
import os
import re
from pathlib import Path
from typing import Callable, Awaitable

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.config import settings
from edu_cloud.database import get_db
# R4-F001: 运行时属性查找，让 client fixture monkey-patch 生效
import edu_cloud.database as db_mod
from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.core.tenant import get_school_id
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.services.scan_workflow import (
    Exam,
    Subject,
    Question,
    QUESTION_TYPES_OBJECTIVE,
    Template,
    Student,
)
from edu_cloud.shared.storage import get_storage, StorageService
from . import pipeline_service
from .tpl_parser import parse_tpl_file

logger = logging.getLogger(__name__)


def _validate_path_within_upload_dir(p: str | Path) -> Path:
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    candidate = Path(p)
    if not candidate.is_absolute():
        candidate = upload_root / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(upload_root):
        raise HTTPException(403, "只允许访问上传目录内的路径")
    return resolved


async def _check_scan_path_tenant(
    path: Path, school_id: str | None, db: AsyncSession,
) -> None:
    """按 exam 归属验证扫描路径的租户隔离。"""
    if not school_id:
        return
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(upload_root)
    except (OSError, ValueError):
        return
    if not rel.parts or rel.parts[0] != school_id:
        raise HTTPException(403, "只允许访问本校的上传目录")
    exam_id = _infer_exam_id_from_scan_dir(path)
    if not exam_id:
        return
    exam_school = (await db.execute(
        select(Exam.school_id).where(Exam.id == exam_id)
    )).scalar_one_or_none()
    if exam_school is None:
        return
    if exam_school != school_id:
        raise HTTPException(403, "只允许访问本校考试的扫描数据")


_JINGYAN_PAGE_NAME_RE = re.compile(
    r"^(?P<student>[^_]+)_(?P<subject>[^_]+)_(?P<page>[12])_(?P<index>[01])(?P<suffix>\.[^.]+)$",
    re.IGNORECASE,
)
_PAGE_TO_SIDE = {("1", "0"): "A", ("2", "1"): "B"}
_PIPELINE_IMAGE_SUFFIX = {".png": ".png", ".jpg": ".jpg", ".jpeg": ".jpg"}
_SUBJECT_CODE_BY_NAME = {
    "语文": "YW",
    "数学": "SX",
    "英语": "YY",
    "物理": "WL",
    "化学": "HX",
    "生物": "SW",
    "政治": "ZZ",
    "历史": "LS",
    "地理": "DL",
    "技术": "JS",
}
_AUTO_SUBJECT_SKIP_NAMES = {"", ".", "未分类"}


def normalize_uploaded_scan_filename(filename: str) -> tuple[str, bool]:
    """Normalize uploaded image names to the A/B convention used by the scanner."""
    suffix = Path(filename).suffix.lower()
    match = _JINGYAN_PAGE_NAME_RE.match(filename)
    if match and suffix in _PIPELINE_IMAGE_SUFFIX:
        side = _PAGE_TO_SIDE.get((match.group("page"), match.group("index")))
        if side:
            return f"{match.group('student')}{side}{_PIPELINE_IMAGE_SUFFIX[suffix]}", True

    normalized_suffix = _PIPELINE_IMAGE_SUFFIX.get(suffix)
    if normalized_suffix and Path(filename).suffix != normalized_suffix:
        return Path(filename).with_suffix(normalized_suffix).name, True
    return filename, False


def _infer_exam_id_from_scan_dir(path: Path) -> str | None:
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(upload_root)
    except (OSError, ValueError):
        return None
    parts = rel.parts
    if len(parts) >= 3 and parts[1] == "scan-input":
        return parts[2]
    if len(parts) >= 2 and parts[0] == "scan-input":
        return parts[1]
    return None


def _subject_code_for_scan_name(name: str, used_codes: set[str]) -> str:
    base = _SUBJECT_CODE_BY_NAME.get(name.strip())
    if not base:
        base = re.sub(r"[^A-Za-z0-9]+", "", name).upper()[:10] or f"SUB{len(used_codes) + 1}"

    code = base[:50]
    i = 2
    while code in used_codes:
        suffix = str(i)
        code = f"{base[:50 - len(suffix)]}{suffix}"
        i += 1
    used_codes.add(code)
    return code


async def _ensure_scan_subjects(
    db: AsyncSession,
    *,
    exam_id: str | None,
    school_id: str | None,
    detected_subjects: list[dict],
) -> int:
    if not exam_id or not detected_subjects:
        return 0

    q = select(Exam).where(Exam.id == exam_id)
    if school_id:
        q = q.where(Exam.school_id == school_id)
    exam = (await db.execute(q)).scalar_one_or_none()
    if not exam:
        return 0

    effective_school_id = exam.school_id
    existing = (await db.execute(
        select(Subject).where(
            Subject.exam_id == exam_id,
            Subject.school_id == effective_school_id,
        )
    )).scalars().all()
    existing_names = {s.name for s in existing}
    used_codes = {s.code for s in existing}

    created = 0
    for item in detected_subjects:
        name = str(item.get("name") or "").strip()
        folder = str(item.get("folder") or "").strip()
        if name in _AUTO_SUBJECT_SKIP_NAMES or folder == "." or name in existing_names:
            continue
        code = _subject_code_for_scan_name(name, used_codes)
        db.add(Subject(exam_id=exam_id, name=name, code=code, school_id=effective_school_id))
        existing_names.add(name)
        created += 1

    if created:
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            logger.warning("scan_directory: auto-create subjects conflicted for exam=%s", exam_id)
            return 0
        logger.info("scan_directory: auto-created %d subjects for exam=%s", created, exam_id)
    return created


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
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
    db: AsyncSession = Depends(get_db),
):
    """浏览服务器目录，返回子文件夹列表。仅限 UPLOAD_DIR 内。"""
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    school_id = get_school_id(current)

    if req.path:
        candidate = Path(req.path)
        if not candidate.is_absolute():
            candidate = upload_root / candidate
        d = candidate.resolve()
        if not d.is_relative_to(upload_root):
            raise HTTPException(403, "只允许浏览上传目录")
    elif school_id:
        d = upload_root / school_id
    else:
        d = upload_root

    await _check_scan_path_tenant(d, school_id, db)

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
                    "path": str(entry.relative_to(upload_root)),
                    "has_images": img_count > 0,
                    "image_count": img_count,
                    "sub_dirs": sub_count,
                })
    except PermissionError:
        raise HTTPException(403, f"无权访问: {req.path}")

    current_rel = "." if d == upload_root else str(d.relative_to(upload_root))
    if d == upload_root:
        parent_rel = None
    elif d.parent == upload_root:
        parent_rel = "."
    else:
        parent_rel = str(d.parent.relative_to(upload_root))
    return {"current": current_rel, "parent": parent_rel, "items": items}


@router.post("/upload-folder")
async def upload_scan_folder(
    exam_id: str = Form(...),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """接收用户上传的扫描图片，按子文件夹结构保存到服务器。"""
    school_id = get_school_id(current)
    if not school_id:
        raise HTTPException(403, "上传扫描图片需要学校上下文")
    if "/" in exam_id or "\\" in exam_id or exam_id in (".", ".."):
        raise HTTPException(400, "无效的考试 ID")
    base_dir = Path(settings.UPLOAD_DIR).resolve() / school_id / "scan-input" / exam_id
    if not base_dir.resolve().is_relative_to(
        Path(settings.UPLOAD_DIR).resolve() / school_id / "scan-input"
    ):
        raise HTTPException(403, "路径越界")
    await _check_scan_path_tenant(base_dir, school_id, db)
    base_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    normalized = 0
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

        if not fname.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".pdf")):
            continue
        if sub_dir in (".", "..", "") or "/" in sub_dir or "\\" in sub_dir:
            sub_dir = "未分类"

        fname, was_normalized = normalize_uploaded_scan_filename(fname)
        if was_normalized:
            normalized += 1

        target_dir = base_dir / sub_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / fname
        if not target.resolve().is_relative_to(base_dir):
            continue
        content = await f.read()
        target.write_bytes(content)
        saved += 1

    logger.info("upload_scan_folder: exam=%s saved=%d normalized=%d dir=%s", exam_id, saved, normalized, base_dir)
    return {"dir_path": str(base_dir), "saved": saved, "normalized": normalized}


class ScanDirRequest(BaseModel):
    dir_path: str


class PdfImportRequest(BaseModel):
    dir_path: str
    pages_per_student: int = 2
    dpi: int = 200



@router.post("/scan-dir")
async def scan_directory(
    req: ScanDirRequest,
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
    db: AsyncSession = Depends(get_db),
):
    """扫描目录结构，返回科目子文件夹和图片统计。"""
    d = _validate_path_within_upload_dir(req.dir_path)
    school_id = get_school_id(current)
    await _check_scan_path_tenant(d, school_id, db)
    if not d.is_dir():
        return {"dir_path": req.dir_path, "subjects": [], "created_subjects": 0}

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

    created_subjects = await _ensure_scan_subjects(
        db,
        exam_id=_infer_exam_id_from_scan_dir(d),
        school_id=current["current_role"].school_id,
        detected_subjects=subjects,
    )

    return {"dir_path": req.dir_path, "subjects": subjects, "created_subjects": created_subjects}


@router.post("/start")
async def start_pipeline(
    req: StartPipelineRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
    storage: StorageService = Depends(get_storage),
):
    """启动扫描切割流水线。"""
    school_id = get_school_id(current)

    # 验证目录（限制在 UPLOAD_DIR 内）
    image_dir_resolved = _validate_path_within_upload_dir(req.image_dir)
    await _check_scan_path_tenant(image_dir_resolved, school_id, db)
    if not image_dir_resolved.is_dir():
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
        tpl_resolved = _validate_path_within_upload_dir(req.tpl_path)
        await _check_scan_path_tenant(tpl_resolved, school_id, db)
        if not tpl_resolved.is_file():
            raise HTTPException(400, f"tpl 文件不存在: {req.tpl_path}")
        template = parse_tpl_file(str(tpl_resolved))
    else:
        tpl_stmt = select(Template).where(
            Template.subject_id == req.subject_id,
            Template.side == req.side,
        )
        if school_id:
            tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
        tpl = (await db.execute(tpl_stmt)).scalar_one_or_none()
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

    # 从已组装的 template dict 统一提取 barcode_region（两个分支都走这里）
    bc_region = template.get("barcode_region")
    tpl_size = template.get("image_size", {})
    tpl_width = tpl_size.get("width", 0)
    tpl_height = tpl_size.get("height", 0)

    image_dir_str = str(image_dir_resolved)
    can_use_filename_ids, filename_id_info = await asyncio.to_thread(
        pipeline_service.can_use_filename_student_ids, image_dir_str, req.side
    )
    if can_use_filename_ids:
        template["prefer_filename_student_id"] = True
        logger.info("pipeline: using filename student ids: %s", filename_id_info)

    # A/B 面以稳定文件名为准。不要在切割前按图像黑度/条码自动改名；
    # 这类启发式在作文格子上会误判，把原始上传目录里的 A/B 文件交换。

    # B 面启动时，优先用成对文件名配对；否则预建条码映射表（从 A 面文件读取条码→学号）
    if req.side == "B":
        known_numbers = set((await db.execute(
            select(Student.student_number).where(
                Student.school_id == school_id,
                Student.student_number.isnot(None),
                Student.student_number != "",
            )
        )).scalars().all())
        can_pair_by_filename, pair_info = await asyncio.to_thread(
            pipeline_service.can_use_filename_pairing_for_b_side,
            image_dir_str, known_numbers,
        )
        if can_pair_by_filename:
            pipeline_service.clear_barcode_map()
            logger.info("pipeline: B-side using filename pairing, skip barcode map: %s", pair_info)
        else:
            logger.info("pipeline: B-side barcode map required: %s", pair_info)
            a_tpl_stmt = select(Template).where(
                Template.subject_id == req.subject_id,
                Template.side == "A",
            )
            if school_id:
                a_tpl_stmt = a_tpl_stmt.where(Template.school_id == school_id)
            a_tpl = (await db.execute(a_tpl_stmt)).scalar_one_or_none()
            if a_tpl:
                a_bc = None
                for r in (a_tpl.regions or []):
                    if r.get("type") == "barcode" and r.get("rect"):
                        a_bc = r["rect"]
                        break
                if a_bc:
                    await asyncio.to_thread(
                        pipeline_service.build_barcode_map,
                        image_dir_str, a_bc, a_tpl.image_width, a_tpl.image_height,
                    )

    # 重新切割：清除该科目的旧 StudentAnswer 数据
    old_count_result = await db.execute(
        select(func.count(StudentAnswer.id)).where(
            StudentAnswer.subject_id == req.subject_id,
            StudentAnswer.school_id == school_id,
        )
    )
    old_count = old_count_result.scalar() or 0
    if old_count > 0:
        await db.execute(
            StudentAnswer.__table__.delete().where(
                StudentAnswer.subject_id == req.subject_id,
                StudentAnswer.school_id == school_id,
            )
        )
        await db.commit()
        logger.info("pipeline recut: deleted %d old answers for subject=%s",
                     old_count, req.subject_id)

    # 列出文件
    try:
        files = await asyncio.to_thread(pipeline_service.list_scan_images, image_dir_str, req.side)
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
                    Question.subject_id == req.subject_id,
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
        image_dir=image_dir_str,
        template=template,
        output_dir=output_dir,
        exam_id=subject.exam_id,
        subject_id=req.subject_id,
        school_id=school_id,
        side=req.side,
        require_known_student_for_save=True,
    )

    pipeline_service.ensure_queue_running()

    queue_len = len(pipeline_service._queue) + (1 if pipeline_service.is_running() else 0)
    logger.info("Pipeline queued: subject=%s, dir=%s, files=%d, queue=%d",
                subject.name, req.image_dir, len(files), queue_len)
    return {"status": "queued", "total_files": len(files), "queue_length": queue_len}



@router.post("/pdf-import")
async def import_pdf_to_images(
    req: PdfImportRequest,
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
    db: AsyncSession = Depends(get_db),
):
    """将目录中的 PDF 拆分为 PNG 图片，按 A/B 面命名。

    用于批量扫描件（A3 双面 PDF）的预处理。
    拆出的 PNG 可直接用于扫描流水线。
    """
    d = _validate_path_within_upload_dir(req.dir_path)
    school_id = get_school_id(current)
    await _check_scan_path_tenant(d, school_id, db)
    if not d.is_dir():
        raise HTTPException(400, f"目录不存在: {req.dir_path}")

    pdfs = list(d.rglob("*.pdf"))
    if not pdfs:
        raise HTTPException(400, f"目录下没有 PDF 文件: {req.dir_path}")

    created = pipeline_service.ensure_images_from_pdfs(
        str(d), req.pages_per_student, req.dpi,
    )
    a_count = sum(1 for f in d.iterdir() if f.name.endswith(("A.jpg", "A.png")))
    b_count = sum(1 for f in d.iterdir() if f.name.endswith(("B.jpg", "B.png")))
    return {
        "created": created,
        "total_images": a_count + b_count,
        "a_side": a_count,
        "b_side": b_count,
        "pdf_count": len(pdfs),
        "dir_path": req.dir_path,
    }


@router.get("/progress")
async def get_progress(current: dict = Depends(require_permission(Permission.MANAGE_GRADING))):
    """获取流水线进度。H4: 其他学校的流水线对本校不可见。"""
    school_id = get_school_id(current)
    return pipeline_service.get_progress_for_school(school_id)


@router.post("/stop")
async def stop_pipeline(current: dict = Depends(require_permission(Permission.MANAGE_GRADING))):
    """停止流水线。H4: 不能停止其他学校的流水线。"""
    school_id = get_school_id(current)
    if not pipeline_service.is_running():
        raise HTTPException(400, "流水线未在运行")
    owner = pipeline_service.get_pipeline_school_id()
    if school_id and owner and owner != school_id:
        raise HTTPException(403, "无权停止其他学校的流水线")
    pipeline_service.request_stop()
    return {"status": "stopping"}


@router.post("/preview")
async def preview_scan(
    req: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """预览单张扫描图的切割区域标注。"""
    import base64
    from PIL import Image, ImageDraw
    from io import BytesIO

    school_id = get_school_id(current)

    # 解析图片路径：指定路径 or 从目录取第一张
    image_path = req.image_path
    if not image_path and req.image_dir:
        scan_dir = _validate_path_within_upload_dir(req.image_dir)
        await _check_scan_path_tenant(scan_dir, school_id, db)
        try:
            files = await asyncio.to_thread(pipeline_service.list_scan_images, str(scan_dir), req.side)
            if files:
                image_path = str(files[0])
        except FileNotFoundError:
            pass
    if not image_path:
        raise HTTPException(400, "请指定图片路径或扫描目录")

    resolved_img = _validate_path_within_upload_dir(image_path)
    await _check_scan_path_tenant(resolved_img, school_id, db)
    if not resolved_img.is_file():
        raise HTTPException(400, f"文件不存在: {image_path}")

    # 加载模板
    tpl_stmt = select(Template).where(
        Template.subject_id == req.subject_id,
        Template.side == req.side,
    )
    if school_id:
        tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
    tpl = (await db.execute(tpl_stmt)).scalar_one_or_none()
    if not tpl:
        raise HTTPException(404, "模板不存在")

    img = await asyncio.to_thread(lambda: Image.open(str(resolved_img)).convert("RGB"))
    draw = ImageDraw.Draw(img)
    img_w, img_h = img.size
    sx = img_w / (tpl.image_width or img_w)
    sy = img_h / (tpl.image_height or img_h)

    # 标注定位点（红框）
    from .vision import detect_anchors
    import numpy as np
    anchors = await asyncio.to_thread(lambda: detect_anchors(np.array(img.convert("L"))))
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
    if img.mode != "RGB":
        img = img.convert("RGB")

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {"image": f"data:image/jpeg;base64,{b64}", "anchors": len(anchors)}


@router.post("/import-tpl")
async def import_tpl(
    req: ImportTplRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """导入 .tpl 文件到 Template 表。"""
    school_id = get_school_id(current)

    tpl_resolved = _validate_path_within_upload_dir(req.tpl_path)
    await _check_scan_path_tenant(tpl_resolved, school_id, db)
    if not tpl_resolved.is_file():
        raise HTTPException(400, f"tpl 文件不存在: {req.tpl_path}")

    q = select(Subject).where(Subject.id == req.subject_id)
    if school_id:
        q = q.where(Subject.school_id == school_id)
    subject = (await db.execute(q)).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")
    school_id = subject.school_id

    tpl_data = parse_tpl_file(str(tpl_resolved))

    # Upsert Template
    tpl_stmt = select(Template).where(
        Template.subject_id == req.subject_id,
        Template.side == req.side,
    )
    if school_id:
        tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
    existing = (await db.execute(tpl_stmt)).scalar_one_or_none()

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
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
    db: AsyncSession = Depends(get_db),
):
    """提供扫描图片的 HTTP 访问（前端模板编辑器用）。"""
    from fastapi.responses import FileResponse
    if path.startswith("/uploads/"):
        path = path.split("/uploads/", 1)[1]
    resolved = _validate_path_within_upload_dir(path)
    if not resolved.is_file():
        raise HTTPException(404, f"图片不存在: {path}")

    school_id = get_school_id(current)
    await _check_scan_path_tenant(resolved, school_id, db)

    suffix = resolved.suffix.lower()
    media = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(suffix.lstrip("."), "application/octet-stream")
    return FileResponse(resolved, media_type=media)


