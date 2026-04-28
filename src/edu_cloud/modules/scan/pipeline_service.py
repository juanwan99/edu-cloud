"""扫描流水线服务 — 批量切割扫描图并存入 StudentAnswer。"""
import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image
import numpy as np

from .vision import detect_anchors, crop_region, read_barcode, recognize_choice_group
from edu_cloud import database as db_mod

logger = logging.getLogger(__name__)


@dataclass
class PipelineProgress:
    total: int = 0
    processed: int = 0
    failed: int = 0
    current_file: str = ""
    warnings: list = field(default_factory=list)
    status: str = "idle"  # idle, running, completed, stopped, failed
    barcode_failed: int = 0  # F004: 条码识别失败且走 fallback 的图片数
    barcode_failed_files: list = field(default_factory=list)
    current_subject_id: str = ""


# 全局进度和锁
_progress: dict[str, PipelineProgress] = {}
_lock = asyncio.Lock()
_running = False

# 多科目队列（F009 修复：每个队列项携带自己的 save_fn）
_queue: list[dict] = []
_queue_stopped: bool = False  # F013: 独立 stop 标志，不复用 _running


def get_progress(pipeline_id: str = "default") -> dict:
    p = _progress.get(pipeline_id, PipelineProgress())
    return {
        "status": p.status,
        "total": p.total,
        "processed": p.processed,
        "failed": p.failed,
        "current_file": p.current_file,
        "warnings": p.warnings[-50:],  # 最近 50 条
        "barcode_failed": p.barcode_failed,
        "barcode_failed_files": p.barcode_failed_files[-50:],
        "queue_remaining": len(_queue),
        "current_subject_id": p.current_subject_id,
    }


def is_running() -> bool:
    return _running


def request_stop():
    global _running, _queue_stopped
    _running = False
    _queue_stopped = True


def list_scan_images(image_dir: str, side: str = "A") -> list[Path]:
    """列出扫描目录下指定面的图片文件（兼容 JPEG 和 PNG）。"""
    d = Path(image_dir)
    if not d.exists():
        raise FileNotFoundError(f"目录不存在: {image_dir}")
    by_stem: dict[str, Path] = {}
    for f in [*d.glob(f"*{side}.jpg"), *d.glob(f"*{side}.png")]:
        if f.stem not in by_stem:
            by_stem[f.stem] = f
    return sorted(by_stem.values())


def auto_fix_ab_sides(image_dir: str, barcode_rect: dict, tpl_w: int, tpl_h: int) -> int:
    """检测并修复 A/B 面文件名标反的情况。

    通过条码区域暗像素比例判断真实 A/B 面：有条码 = A 面。
    标反的文件对会被重命名交换。

    Returns: 交换的文件对数量。
    """
    d = Path(image_dir)
    a_files = sorted([
        f for f in d.iterdir()
        if f.suffix.lower() in ('.jpg', '.png') and f.stem.endswith('A')
    ])
    if not a_files:
        return 0

    swapped = 0
    for a_file in a_files:
        stu_num = a_file.stem[:-1]
        b_file = None
        for ext in ('.jpg', '.jpeg', '.png'):
            candidate = d / f"{stu_num}B{ext}"
            if candidate.exists():
                b_file = candidate
                break
        if not b_file:
            continue

        a_has = _has_barcode(a_file, barcode_rect, tpl_w, tpl_h)
        if a_has:
            continue

        b_has = _has_barcode(b_file, barcode_rect, tpl_w, tpl_h)
        if not b_has:
            continue

        tmp = d / f"{stu_num}_swap_tmp{a_file.suffix}"
        a_file.rename(tmp)
        b_new_name = d / f"{stu_num}A{b_file.suffix}"
        b_file.rename(b_new_name)
        a_new_name = d / f"{stu_num}B{a_file.suffix}"
        tmp.rename(a_new_name)
        swapped += 1

    if swapped:
        logger.info("auto_fix_ab: swapped %d/%d pairs in %s", swapped, len(a_files), image_dir)
    return swapped


def _has_barcode(image_path: Path, barcode_rect: dict, tpl_w: int, tpl_h: int) -> bool:
    """裁剪条码区域后用 pyzbar 解码，fallback 到暗像素比例 > 0.20。"""
    from pyzbar.pyzbar import decode

    img = Image.open(image_path)
    img_w, img_h = img.size
    sx = img_w / tpl_w if tpl_w > 0 else 1.0
    sy = img_h / tpl_h if tpl_h > 0 else 1.0

    pad = 80
    x1 = max(0, int(barcode_rect["x1"] * sx) - pad)
    y1 = max(0, int(barcode_rect["y1"] * sy) - pad)
    x2 = min(img_w, int(barcode_rect["x2"] * sx) + pad)
    y2 = min(img_h, int(barcode_rect["y2"] * sy) + pad)

    crop = img.crop((x1, y1, x2, y2))
    barcodes = decode(crop)
    if barcodes:
        return True

    gray = np.array(crop.convert("L"))
    if gray.size == 0:
        return False
    dark_ratio = np.mean(gray < 128)
    return dark_ratio > 0.20


def _render_page(args):
    """Worker: render one PDF page to JPEG."""
    pdf_path_str, page_num, out_path_str, dpi = args
    import fitz
    from PIL import Image as _PILImage
    doc = fitz.open(pdf_path_str)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=dpi)
    img = _PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img.save(out_path_str, format="JPEG", quality=85)
    doc.close()
    return out_path_str


def ensure_images_from_pdfs(image_dir: str, pages_per_student: int = 2, dpi: int = 150) -> int:
    """检查目录中是否有 PDF，并行拆分为 PNG 图片（幂等）。

    跨 PDF 全局递增编号，输出 0001A.png / 0001B.png，
    直接适配原有 pipeline 命名逻辑。

    Returns: 新生成的 PNG 数量
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed

    d = Path(image_dir)
    pdfs = sorted(d.rglob("*.pdf"), key=lambda p: p.stem)
    if not pdfs:
        return 0

    sides = "AB"
    tasks = []
    global_stu = 0

    for pdf_path in pdfs:
        import fitz
        doc = fitz.open(str(pdf_path))
        n_pages = len(doc)
        n_students = n_pages // pages_per_student
        pdf_tasks = 0

        for stu_idx in range(n_students):
            global_stu += 1
            for offset in range(pages_per_student):
                page_num = stu_idx * pages_per_student + offset
                side = sides[offset % len(sides)]
                out_name = f"{global_stu:04d}{side}.jpg"
                out_path = pdf_path.parent / out_name
                png_compat = pdf_path.parent / f"{global_stu:04d}{side}.png"

                if not out_path.exists() and not png_compat.exists():
                    tasks.append((str(pdf_path), page_num, str(out_path), dpi))
                    pdf_tasks += 1

        remainder = n_pages % pages_per_student
        if remainder:
            global_stu += 1
            for offset in range(remainder):
                page_num = n_students * pages_per_student + offset
                side = sides[offset % len(sides)]
                out_name = f"{global_stu:04d}{side}.jpg"
                out_path = pdf_path.parent / out_name
                png_compat = pdf_path.parent / f"{global_stu:04d}{side}.png"
                if not out_path.exists() and not png_compat.exists():
                    tasks.append((str(pdf_path), page_num, str(out_path), dpi))
                    pdf_tasks += 1

        doc.close()
        logger.info("pdf_import: %s -> %d pages, %d students, %d to render",
                     pdf_path.name, n_pages, n_students, pdf_tasks)

    if not tasks:
        logger.info("pdf_import: all %d students already converted, skip", global_stu)
        return 0

    logger.info("pdf_import: %d total students, %d pages to render across %d workers",
                global_stu, len(tasks), min(6, len(tasks)))
    created = 0
    with ProcessPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_render_page, t): t for t in tasks}
        for fut in as_completed(futures):
            try:
                fut.result()
                created += 1
            except Exception as e:
                t = futures[fut]
                logger.error("pdf_import: failed to render page %d of %s: %s", t[1], t[0], e)

    logger.info("pdf_import: done, %d images created", created)
    return created



def _extract_student_id(filename: str) -> str:
    """从文件名提取学生 ID。去掉面标识(A/B)和扩展名。"""
    name = Path(filename).stem
    if name and name[-1] in ("A", "B"):
        return name[:-1]
    return name


def process_one_image(
    image_path: Path,
    template: dict,
    output_dir: str,
    barcode_region: dict | None = None,
) -> dict:
    """处理单张扫描图：检测定位点 → 缩放裁切 → 保存切图。

    Returns:
        {student_id, crops: [{region_id, name, path, size}], errors: [str]}
    """
    img = Image.open(str(image_path)).convert("RGB")
    img_w, img_h = img.size

    # 条码识别（F004：失败必须记录，禁止静默）
    student_id = None
    barcode_status = "ok"  # ok / fallback_exception / fallback_none / skipped
    if barcode_region:
        try:
            student_id = read_barcode(image_path, barcode_region)
            if not student_id:
                barcode_status = "fallback_none"
                logger.warning(
                    "barcode_fallback_none: file=%s, read_barcode returned None, using filename stem",
                    image_path.name,
                )
        except Exception as e:
            barcode_status = "fallback_exception"
            logger.warning(
                "barcode_read_failed: file=%s, error=%s, using filename stem",
                image_path.name, e, exc_info=True,
            )
    else:
        barcode_status = "skipped"  # 模板无 barcode_region，走文件名提取不算 fallback

    if not student_id:
        student_id = _extract_student_id(image_path.name)

    # 模板尺寸 → 缩放比
    tpl_size = template.get("image_size", {})
    tpl_w = tpl_size.get("width", img_w)
    tpl_h = tpl_size.get("height", img_h)
    sx = img_w / tpl_w if tpl_w > 0 else 1.0
    sy = img_h / tpl_h if tpl_h > 0 else 1.0

    # 裁切每个主观题区域
    crops = []
    errors = []
    subjective = [r for r in template.get("regions", []) if r.get("type") == "subjective"]
    stu_dir = os.path.join(output_dir, student_id)
    os.makedirs(stu_dir, exist_ok=True)

    for region in subjective:
        try:
            rect = region["rect"]
            scaled_rect = {
                "x1": int(rect["x1"] * sx),
                "y1": int(rect["y1"] * sy),
                "x2": int(rect["x2"] * sx),
                "y2": int(rect["y2"] * sy),
            }
            cropped = crop_region(img, scaled_rect)
            out_path = os.path.join(stu_dir, f"{region['id']}.jpg")
            cropped.save(out_path, format="JPEG", quality=85)
            crops.append({
                "region_id": region["id"],
                "name": region.get("name", region["id"]),
                "path": out_path,
                "size": cropped.size,
            })
        except Exception as e:
            errors.append(f"Region {region['id']}: {e}")

    # 选择题识别
    objective_results = []
    choice_groups = [r for r in template.get("regions", []) if r.get("type") == "choice_group"]
    if choice_groups:
        gray = np.array(img.convert("L"))
        for group in choice_groups:
            try:
                rect = group["rect"]
                scaled_rect = {
                    "x1": int(rect["x1"] * sx),
                    "y1": int(rect["y1"] * sy),
                    "x2": int(rect["x2"] * sx),
                    "y2": int(rect["y2"] * sy),
                }
                gr = recognize_choice_group(
                    gray,
                    region=scaled_rect,
                    rows=group.get("rows", 1),
                    cols=group.get("cols", 4),
                    labels=group.get("labels", ["A", "B", "C", "D"]),
                    multi_select=group.get("multi_select", False),
                    group_id=group.get("id", ""),
                )
                answers = []
                for qr in gr.question_results:
                    selected = qr["selected"]
                    detected = "".join(selected) if selected else ""
                    answers.append({
                        "question": qr["question"],
                        "detected_answer": detected,
                        "fill_ratios": qr["all_ratios"],
                        "anomaly": qr["anomaly"],
                    })
                objective_results.append({
                    "group_id": group.get("id", ""),
                    "answers": answers,
                })
            except Exception as e:
                errors.append(f"ChoiceGroup {group.get('id', '?')}: {e}")

    return {
        "student_id": student_id,
        "crops": crops,
        "errors": errors,
        "barcode_status": barcode_status,
        "objective_results": objective_results,
    }


async def run_pipeline(
    image_dir: str,
    template: dict,
    output_dir: str,
    exam_id: str,
    subject_id: str,
    school_id: str,
    side: str = "A",
    pipeline_id: str = "default",
    save_answer_fn=None,
    save_objective_fn=None,
) -> dict:
    """异步运行批量切割流水线。

    Args:
        save_answer_fn: async fn(exam_id, subject_id, student_id, question_id, image_path, school_id)
            用于将切图保存到 StudentAnswer 表。None 时只切不存。
        save_objective_fn: async fn(exam_id, subject_id, student_id, group_id, row_index, ...)
            用于将选择题结果保存到 StudentAnswer 表。None 时只识别不存。
    """
    global _running

    async with _lock:
        if _running:
            raise RuntimeError("流水线正在运行")
        _running = True

    pdf_created = ensure_images_from_pdfs(image_dir)
    if pdf_created:
        logger.info("pipeline: auto-converted PDFs -> %d PNG images in %s", pdf_created, image_dir)

    files = list_scan_images(image_dir, side)
    progress = PipelineProgress(total=len(files), status="running", current_subject_id=subject_id)
    _progress[pipeline_id] = progress

    barcode_region = template.get("barcode_region")

    # 预加载 student_number → student.id 映射
    student_number_map = {}
    try:
        from sqlalchemy import select, text
        async with db_mod.async_session() as db:
            rows = (await db.execute(text(
                "SELECT id, student_number FROM students WHERE school_id = :sid"
            ), {"sid": school_id})).all()
            student_number_map = {r[1]: r[0] for r in rows if r[1]}
        logger.info("pipeline: loaded %d student_number mappings for school %s", len(student_number_map), school_id[:8])
    except Exception as e:
        logger.warning("pipeline: failed to load student mappings: %s", e)

    results = {
        "total": len(files),
        "processed": 0,
        "failed": 0,
        "students": [],
        "barcode_failed": 0,
        "barcode_failed_files": [],
    }

    try:
        for f in files:
            if not _running:
                progress.status = "stopped"
                break

            progress.current_file = f.name
            try:
                result = process_one_image(f, template, output_dir, barcode_region)

                # 条码/文件名 → 查学生表拿真实 UUID
                raw_sid = result["student_id"]
                if raw_sid in student_number_map:
                    result["student_id"] = student_number_map[raw_sid]
                elif student_number_map:
                    result["is_anomaly"] = True
                    logger.warning("pipeline: student_number %s not found in students table, file=%s", raw_sid, f.name)

                progress.processed += 1
                results["processed"] += 1
                results["students"].append(result["student_id"])

                # F004: 聚合 barcode fallback 计数（fallback_exception / fallback_none）
                bc_status = result.get("barcode_status", "ok")
                if bc_status in ("fallback_exception", "fallback_none"):
                    progress.barcode_failed += 1
                    results["barcode_failed"] += 1
                    entry = {
                        "file": f.name,
                        "fallback_student_id": result["student_id"],
                        "status": bc_status,
                    }
                    progress.barcode_failed_files.append(entry)
                    results["barcode_failed_files"].append(entry)

                if result["errors"]:
                    for e in result["errors"]:
                        progress.warnings.append({"file": f.name, "message": e})

                # 保存到数据库
                if save_answer_fn:
                    for crop in result["crops"]:
                        await save_answer_fn(
                            exam_id=exam_id,
                            subject_id=subject_id,
                            student_id=result["student_id"],
                            question_id=crop["region_id"],
                            image_path=crop["path"],
                            school_id=school_id,
                        )

                # 保存选择题结果到数据库
                if save_objective_fn and result.get("objective_results"):
                    for group in result["objective_results"]:
                        for ans in group["answers"]:
                            await save_objective_fn(
                                exam_id=exam_id,
                                subject_id=subject_id,
                                student_id=result["student_id"],
                                group_id=group["group_id"],
                                row_index=ans["question"],
                                detected_answer=ans["detected_answer"],
                                fill_ratios=ans["fill_ratios"],
                                anomaly=ans["anomaly"],
                                school_id=school_id,
                            )
            except Exception as e:
                progress.failed += 1
                results["failed"] += 1
                progress.warnings.append({"file": f.name, "message": str(e)})
                logger.error("Pipeline error for %s: %s", f.name, e)

            # 让出事件循环
            await asyncio.sleep(0)

        if _running:
            progress.status = "completed"
    finally:
        _running = False

    logger.info("Pipeline finished: %d/%d processed, %d failed",
                results["processed"], results["total"], results["failed"])
    return results


def enqueue_pipeline(
    save_answer_fn=None,
    save_objective_fn=None,
    **pipeline_kwargs,
) -> int:
    """将一个科目加入切割队列，返回队列长度。
    每个科目携带自己的 save_fn，不与其他科目共享（F009）。"""
    _queue.append({
        "pipeline_kwargs": pipeline_kwargs,
        "save_answer_fn": save_answer_fn,
        "save_objective_fn": save_objective_fn,
    })
    return len(_queue)


async def run_queue() -> list[dict]:
    """依次执行队列中所有科目的切割。INV-004: stop 传播到整个队列。

    F013 修复：不能用 `not _running` 判断 stop，因为 run_pipeline 正常结束
    也会在 finally 中复位 _running=False。改用独立的 _queue_stopped 标志，
    由 request_stop 同时设置。
    """
    global _queue_stopped
    _queue_stopped = False
    results = []
    while _queue:
        if _queue_stopped:
            _queue.clear()
            break
        item = _queue.pop(0)
        result = await run_pipeline(
            save_answer_fn=item["save_answer_fn"],
            save_objective_fn=item["save_objective_fn"],
            **item["pipeline_kwargs"],
        )
        results.append(result)
    return results
