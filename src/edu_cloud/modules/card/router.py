"""答题卡生成 + 条码贴纸 + 骨架管理 API。

编辑器 CRUD + 答案解析 + 条码 + 权重预览 + 模板导出 保留在此文件。
模板/骨架管理 → card_template_router.py
导出/渲染/发布 → card_export_router.py
"""
from __future__ import annotations
import copy
import json
import logging
import re
import tempfile
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)


def _q_sort_key(q):
    """统一排序 key：提取题目名中的数字部分，非数字排最后。"""
    m = re.match(r'(\d+)', q.name)
    return (0, int(m.group(1))) if m else (1, q.name)
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.core.tenant import get_school_id
from edu_cloud.config import settings
from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.modules.card.models import Template, CardSkeleton
from edu_cloud.modules.card.export.barcode_gen import parse_student_excel, render_barcode_pdf
from edu_cloud.modules.card.layout_helpers import is_biology_generic_pollution, strip_runtime_render_fields
from edu_cloud.modules.card.rendering.renderer import render_card_v2
from edu_cloud.modules.card.rendering.subject_defaults import (
    CanonicalLayoutError,
    final_canonical_layout_drift_reason,
    get_default_layout,
)

router = APIRouter(prefix="/api/v1/card", tags=["card"])

# --- 子路由注册 ---
from edu_cloud.modules.card.card_template_router import router as template_sub_router
from edu_cloud.modules.card.card_export_router import router as export_sub_router
router.include_router(template_sub_router)
router.include_router(export_sub_router)

class EditorLayoutBody(BaseModel):
    layout: dict
    config: dict = {}
    choices: list = []


# Editor layout 按 subject_id 文件隔离，避免同校不同考试相同科目代码互相覆盖
_EDITOR_LAYOUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "editor_layouts"
_EDITOR_LAYOUT_DIR.mkdir(exist_ok=True)


def _editor_layout_path(school_id: str, subject_id: str) -> Path:
    return _EDITOR_LAYOUT_DIR / f"{school_id}_{subject_id}.json"


def _default_layout_response(subject_name: str) -> dict:
    """学科默认布局响应（deepcopy 隔离 subject_defaults 模块级缓存，防污染）。

    canonical 资产不可用时 fail-closed 抛 500，不得退回泛化模板（pack3）。
    """
    try:
        layout = copy.deepcopy(get_default_layout(subject_name))
    except CanonicalLayoutError as e:
        raise HTTPException(500, f"学科 canonical 模板资产不可用，已 fail-closed：{e}") from e
    return {
        "found": True,
        "source": "default",
        "layout": layout,
        "config": layout.get("config", {}),
        "choices": [],
    }


@router.get("/editor-layout/{subject_id}")
async def get_editor_layout(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_EXAMS)),
):
    """获取科目的可视化编辑器布局：优先 editor_layouts/ 已保存文件，无保存时返回学科默认布局。"""
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == current["current_role"].school_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")

    path = _editor_layout_path(current["current_role"].school_id, subject_id)
    if not path.exists():
        return _default_layout_response(subject.name)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("get_editor_layout: unreadable layout file %s, falling back to subject default", path.name)
        return _default_layout_response(subject.name)

    if not isinstance(data, dict):
        logger.warning("get_editor_layout: non-dict layout data in %s, falling back to subject default", path.name)
        return _default_layout_response(subject.name)

    layout = data.get("layout") or {}
    if not isinstance(layout, dict):
        logger.warning("get_editor_layout: non-dict layout in %s, falling back to subject default", path.name)
        return _default_layout_response(subject.name)

    layout_config = layout.get("config", {})
    saved_config = data.get("config", {}) or {}
    merged_config = {**layout_config, **saved_config}
    layout["config"] = {**layout.get("config", {}), **merged_config}

    if is_biology_generic_pollution(layout, merged_config, subject.name):
        logger.warning(
            "get_editor_layout: saved layout %s matches biology generic pollution "
            "fingerprint (A4 [1,1] choice=11 fill=3), falling back to subject default",
            path.name,
        )
        return _default_layout_response(subject.name)

    drift_reason = final_canonical_layout_drift_reason(layout, merged_config, subject.name)
    if drift_reason:
        logger.warning(
            "get_editor_layout: saved layout %s rejected by final canonical guard: %s",
            path.name, drift_reason,
        )
        return _default_layout_response(subject.name)

    return {"found": True, "layout": layout, "source": "saved", "config": merged_config, "choices": data.get("choices", [])}




@router.put("/editor-layout/{subject_id}")
async def save_editor_layout(
    subject_id: str,
    body: EditorLayoutBody,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """保存科目的可视化编辑器布局（按 subject_id 文件隔离）。

    命中生物 generic 污染指纹的布局拒绝写入（422）——这是 2026-06 模板
    劣化事故的写入侧防线，与 GET/_load_layout 的读取侧回退同源。
    """
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == current["current_role"].school_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")

    layout_config = body.layout.get("config") if isinstance(body.layout.get("config"), dict) else {}
    merged_config = {**(layout_config or {}), **(body.config or {})}
    if is_biology_generic_pollution(body.layout, merged_config, subject.name):
        logger.warning(
            "save_editor_layout: rejected layout matching biology generic pollution "
            "fingerprint (A4 [1,1] choice=11 fill=3), subject=%s", subject_id,
        )
        raise HTTPException(
            422,
            "拒绝保存：布局命中生物 generic 污染指纹（A4 单栏 11选择/3填空 兜底布局），"
            "请刷新编辑器重新加载学科模板后再保存",
        )

    # 剥离前端渲染注入的 _side/_col/_sideIdx 等运行时字段，不得持久化（pack3）
    drift_reason = final_canonical_layout_drift_reason(body.layout, merged_config, subject.name)
    if drift_reason:
        logger.warning(
            "save_editor_layout: rejected final canonical drift, subject=%s, reason=%s",
            subject_id, drift_reason,
        )
        raise HTTPException(
            422,
            f"refuse save: layout structure drift from final canonical ({drift_reason})",
        )

    editor_data = strip_runtime_render_fields(
        {"layout": body.layout, "config": body.config, "choices": body.choices}
    )
    path = _editor_layout_path(current["current_role"].school_id, subject_id)
    path.write_text(json.dumps(editor_data, ensure_ascii=False), encoding="utf-8")
    logger.info("save_editor_layout: subject=%s, path=%s", subject_id, path.name)
    return {"ok": True}


@router.delete("/editor-layout/{subject_id}")
async def reset_editor_layout(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """删除保存的编辑器布局，恢复为系统默认模板。"""
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == current["current_role"].school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Subject not found")

    path = _editor_layout_path(current["current_role"].school_id, subject_id)
    if path.exists():
        path.unlink()
        logger.info("reset_editor_layout: deleted %s", path.name)
    return {"ok": True}


@router.post("/upload-answer")
async def upload_answer_file(
    file: UploadFile = File(...),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """上传答案文件（.docx）到临时目录，返回文件路径供 auto-layout 使用。"""
    import tempfile
    if not file.filename.endswith(".docx"):
        raise HTTPException(400, "仅支持 .docx 格式")
    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False, dir=tempfile.gettempdir())
    content = await file.read()
    tmp.write(content)
    tmp.close()
    logger.info("upload_answer: %s → %s", file.filename, tmp.name)
    return {"file_path": tmp.name}


class AutoLayoutRequest(BaseModel):
    answer_file: str | None = None  # 答案文件路径（.docx）
    parsed_questions: list | None = None  # 或直接传解析后的数据


@router.post("/auto-layout/{subject_id}")
async def auto_layout_card(
    subject_id: str,
    body: AutoLayoutRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """小微智能排版：解析答案文件 → 计算空间分配 → 保存到编辑器布局。"""
    from edu_cloud.modules.card.layout_helpers import calculate_layout, _load_layout, _apply_to_regions, _save_layout

    school_id = current["current_role"].school_id
    subject = (await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")

    # 获取解析后的题目数据
    if body.parsed_questions:
        parsed = body.parsed_questions
    elif body.answer_file:
        from pathlib import Path
        import tempfile as _tempfile
        answer_path = Path(body.answer_file).resolve()
        allowed_dirs = [Path(_tempfile.gettempdir()).resolve(), Path(settings.UPLOAD_DIR).resolve()]
        if not any(answer_path.is_relative_to(d) for d in allowed_dirs):
            raise HTTPException(400, "文件路径不在允许范围内")
        if answer_path.suffix.lower() != ".docx":
            raise HTTPException(400, "仅支持 .docx 文件")
        if not answer_path.exists():
            raise HTTPException(400, f"文件不存在: {body.answer_file}")
        from edu_cloud.modules.card.parser.answer_parser import parse_answer_docx
        parsed = parse_answer_docx(body.answer_file)
        if not parsed:
            raise HTTPException(400, "未解析到主观题")
    else:
        raise HTTPException(400, "需要 answer_file 或 parsed_questions")

    try:
        layout = _load_layout(school_id, subject_id, subject.name)
    except CanonicalLayoutError as e:
        raise HTTPException(500, f"学科 canonical 模板资产不可用，已 fail-closed：{e}") from e
    result = calculate_layout(parsed, layout.get("config"), existing_layout=layout)
    layout = _apply_to_regions(layout, result)
    _save_layout(school_id, subject_id, layout)

    logger.info("auto_layout: subject=%s, questions=%d", subject.name, len(parsed))
    return {"subject": subject.name, "applied": True, **result}


@router.post("/barcode")
async def generate_barcode(
    file: UploadFile = File(...),
    barcode_column: str = Form("准考证号"),
    name_column: str = Form("姓名"),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """上传学生 Excel，生成条码贴纸 PDF。"""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "请上传 .xlsx 文件")

    # 保存临时文件
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        students = parse_student_excel(tmp_path, barcode_column, name_column)
        logger.info("barcode: file=%s, students=%d, barcode_col=%s, name_col=%s",
                     file.filename, len(students), barcode_column, name_column)
        pdf_bytes = render_barcode_pdf(students)
    except ValueError as e:
        logger.warning("barcode failed: file=%s, error=%s", file.filename, e)
        raise HTTPException(400, str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename*=UTF-8\'\'{urllib.parse.quote("条码贴纸.pdf")}',
        },
    )


async def _auto_create_questions(
    standardized: list[dict],
    subject_id: str,
    school_id: str,
    db: AsyncSession,
) -> list:
    """从 LLM 标准化结果自动创建 Question 记录（先删旧的）。"""
    from edu_cloud.modules.exam.models import Question

    await db.execute(
        delete(Question).where(
            Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )
    await db.flush()

    questions = []
    for item in standardized:
        q_type = _map_standardized_type(item["type"])
        q = Question(
            subject_id=subject_id,
            school_id=school_id,
            name=str(item["number"]),
            question_type=q_type,
            max_score=item.get("score") or 1,
            correct_answer=item.get("answer") if q_type in ("choice", "multi_choice") else None,
        )
        db.add(q)
        questions.append(q)
    await db.flush()
    return questions


def _map_standardized_type(stype: str) -> str:
    """answer_standardizer 输出的题型 → Question.question_type 统一枚举。"""
    return {
        "single_choice": "choice",
        "multi_choice": "multi_choice",
        "fill_in_blank": "fill_blank",
        "short_answer": "essay",
    }.get(stype, "essay")


@router.post("/parse-answers")
async def parse_answers(
    file: UploadFile = File(...),
    subject_id: str = Form(...),
    exam_id: str = Form(...),
    total_score: int = Form(100),
    paper_size: str = Form("A3"),
    sides: str = Form("duplex"),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """解析答案文件（Word/PDF）→ LLM 标准化 → 自动创建题目 → 返回权重 + 骨架 + 布局。

    Word: 正则提取文本 → LLM 标准化
    PDF:  渲染为图片 → 多模态 LLM（vision）直接输出结构化 JSON
    """
    import time
    from edu_cloud.modules.exam.models import Question
    from edu_cloud.modules.card.parser.word_parser import parse_word_answers, compute_weights_from_text
    from edu_cloud.modules.card.parser.answer_standardizer import standardize_answers, parse_pdf_answers

    filename = (file.filename or "").lower()
    if not filename.endswith((".docx", ".pdf")):
        raise HTTPException(400, "仅支持 .docx 或 .pdf 格式")
    is_pdf = filename.endswith(".pdf")

    subj_result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.school_id == current["current_role"].school_id,
        )
    )
    subject = subj_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")

    exam_result = await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == current["current_role"].school_id)
    )
    exam = exam_result.scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "考试不存在")
    if subject.exam_id != exam.id:
        raise HTTPException(400, "该科目不属于此考试")

    t_start = time.time()
    parse_method = "text_llm"
    _v2_structured = []  # v2 排版引擎用的结构化数据，Word 路径在文件删除前填充

    # 1. 保存上传文件
    suffix = ".pdf" if is_pdf else ".docx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if is_pdf:
            try:
                standardized, parse_method = await parse_pdf_answers(tmp_path)
            except ValueError as e:
                raise HTTPException(400, str(e))
            if not standardized:
                raise HTTPException(400, "未识别到任何题目答案")
            parsed = [
                {"number": item["number"], "answer_text": item.get("answer", ""), "image_count": 0}
                for item in standardized
            ]
        else:
            # Word 路径：正则提取文本 → LLM 标准化
            parsed = parse_word_answers(tmp_path)
            if not parsed:
                logger.warning("parse_answers: no questions found, file=%s, subject=%s", file.filename, subject.name)
                raise HTTPException(400, "未识别到任何题目答案")
            standardized = await standardize_answers(parsed)
            # v2 排版引擎需要结构化解析（sub 级别答案），趁文件还在先解析
            try:
                from edu_cloud.modules.card.parser.answer_parser import parse_answer_docx
                _v2_structured = parse_answer_docx(tmp_path)
            except Exception as e:
                logger.debug("v2 answer parsing skipped: %s", e)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # 2. 自动创建 Question（先删旧的）
    db_questions = await _auto_create_questions(
        standardized, subject_id, current["current_role"].school_id, db,
    )
    await db.commit()

    logger.info("parse_answers: file=%s, subject=%s, source=%s, standardized=%d, created=%d questions",
                file.filename, subject.name, "vision" if is_pdf else "text", len(standardized), len(db_questions))

    # 3. 识别主观题（从 standardized 结果得到类型）
    type_map = {}  # number -> question_type (choice/multi_choice/fill_blank/essay)
    score_map = {}  # number -> max_score
    for item in standardized:
        num = item["number"]
        q_type = _map_standardized_type(item["type"])
        type_map[num] = q_type
        score_map[num] = item.get("score", 1)

    subjective_numbers = {num for num, t in type_map.items() if t in ("fill_blank", "essay")}
    subjective_parsed = [p for p in parsed if p["number"] in subjective_numbers]
    weights = compute_weights_from_text(subjective_parsed) if subjective_parsed else []

    for w in weights:
        actual_score = score_map.get(w["number"], 1)
        sub_count = next((item.get("sub_count", 1) for item in standardized if item["number"] == w["number"]), 1)
        w["parsed_structure"] = [{"sub": 1, "score": actual_score or 1, "space_type": "essay"}] * sub_count

    total_text_length = sum(len(p["answer_text"]) for p in parsed)
    subjective_count = len(subjective_numbers)

    # 4. 纸张选择：优先用前端指定，未指定时自动推断
    if not paper_size or paper_size not in ("A3", "A4"):
        from edu_cloud.modules.card.template.template_library import A4_TEXT_THRESHOLD
        if total_text_length > A4_TEXT_THRESHOLD or subjective_count > 8:
            paper_size = "A3"
        else:
            paper_size = "A4"
    logger.info("parse_answers: paper=%s, text_len=%d, subjective=%d, weights=%d",
                paper_size, total_text_length, subjective_count, len(weights))

    # 5. v2 排版引擎：结构化数据 → 空间分配 → 写入编辑器布局
    v2_layout_result = {}
    try:
        from edu_cloud.modules.card.layout_helpers import calculate_layout, _load_layout, _apply_to_regions, _save_layout

        if not is_pdf:
            structured = _v2_structured  # Word: 已在文件删除前解析好
        else:
            # PDF: 从 standardized 构建 v2 格式
            structured = []
            for item in standardized:
                if item["type"] in ("single_choice", "multi_choice"):
                    continue
                structured.append({
                    "qno": item["number"],
                    "total_score": item.get("score") or 1,
                    "default_score_per_blank": 2,
                    "subs": [{"sub": i + 1, "answers": [item.get("answer", "")]}
                             for i in range(item.get("sub_count", 1))],
                })

        if structured:
            school_id = current["current_role"].school_id
            layout_data = _load_layout(school_id, subject_id, subject.name)
            v2_layout_result = calculate_layout(structured, layout_data.get("config"), existing_layout=layout_data)
            layout_data = _apply_to_regions(layout_data, v2_layout_result)
            _save_layout(school_id, subject_id, layout_data)
            logger.info("parse_answers: v2 layout applied, subject=%s, questions=%d",
                        subject.name, len(structured))
    except Exception as e:
        logger.warning("parse_answers: v2 layout failed (non-fatal): %s", e)

    # 6. 构建前端显示数据
    weight_map = {w["number"]: w["weight"] for w in weights}

    question_info = []
    for item in standardized:
        num = item["number"]
        question_info.append({
            "number": num,
            "answer_text": item.get("answer", ""),
            "image_count": 0,
            "question_type": type_map.get(num, "subjective"),
            "weight": round(weight_map.get(num, 0), 4),
        })

    return {
        "questions": question_info,
        "standardized": standardized,
        "weights": weights,
        "v2_layout": v2_layout_result,
        "subject_code": subject.code,
        "subject_name": subject.name,
        "exam_name": exam.card_title,
        "total_questions": len(db_questions),
        "parse_method": parse_method,
        "parse_time_ms": int((time.time() - t_start) * 1000),
    }


class WeightsPreviewRequest(BaseModel):
    subject_code: str
    exam_id: str
    subject_id: str
    weights: list[dict]
    skeleton: dict | None = None


@router.post("/preview-by-weights")
async def preview_by_weights(
    body: WeightsPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    """根据调整后权重重算布局并渲染预览 PDF。"""
    skeleton = body.skeleton
    if not skeleton:
        from edu_cloud.modules.card.card_utils import get_skeleton_data
        skeleton = await get_skeleton_data(body.subject_code, current["current_role"].school_id, db)

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

    # 加 parsed_structure
    for w in body.weights:
        if "parsed_structure" not in w:
            w["parsed_structure"] = [{"sub": 1, "score": 1, "space_type": "essay"}]

    layout = _compute_layout(skeleton, body.weights)

    pdf_bytes = render_card_v2(
        skeleton=skeleton,
        layout=layout,
        exam_name=exam.card_title if exam else "",
        subject_name=subject.name,
    )

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/template-json")
async def export_template_json(
    exam_id: str,
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_EXAMS)),
):
    """导出 paper-seg 兼容的切割模板 JSON。"""
    # D2: conditional filter — admin (school_id=None) sees all schools
    school_id = get_school_id(current)

    subj_stmt = select(Subject).where(Subject.id == subject_id)
    if school_id:
        subj_stmt = subj_stmt.where(Subject.school_id == school_id)
    subj_result = await db.execute(subj_stmt)
    subject = subj_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")

    exam_stmt = select(Exam).where(Exam.id == subject.exam_id)
    if school_id:
        exam_stmt = exam_stmt.where(Exam.school_id == school_id)
    exam_result = await db.execute(exam_stmt)
    exam = exam_result.scalar_one_or_none()
    if not exam:
        raise HTTPException(403, "无权访问该科目模板")

    tpl_stmt = select(Template).where(
        Template.subject_id == subject_id,
        Template.side == "A",
    )
    if school_id:
        tpl_stmt = tpl_stmt.where(Template.school_id == school_id)
    tpl_result = await db.execute(tpl_stmt)
    tpl = tpl_result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(404, "该科目还没有生成答题卡模板")

    return {
        "version": "1.0",
        "exam_id": exam_id,
        "subject_id": subject_id,
        "side": "A",
        "image_size": {"width": tpl.image_width, "height": tpl.image_height},
        "anchors": tpl.anchors,
        "regions": tpl.regions,
    }




async def _match_skeleton(
    db: AsyncSession, school_id: str, subject, paper_size: str, num_subjective: int,
    db_questions=None,
) -> dict:
    """模板匹配：DB 骨架 → .tpl → build_skeleton_from_spec fallback。"""
    from edu_cloud.modules.card.template.template_library import match_template

    skeleton = None
    source = "generated"

    db_skel = await db.execute(
        select(CardSkeleton).where(
            CardSkeleton.school_id == school_id,
            CardSkeleton.subject_code == subject.code,
        )
    )
    skel_row = db_skel.scalar_one_or_none()
    if (skel_row
            and skel_row.skeleton_data.get("columns")
            and all("y2" in c for c in skel_row.skeleton_data["columns"])):
        skeleton = skel_row.skeleton_data
        source = "db"

    if not skeleton:
        matched = match_template(
            subject=subject.name,
            num_subjective=num_subjective,
            paper_size=paper_size,
        )
        if matched and matched.get("columns") and all("y2" in c for c in matched["columns"]):
            skeleton = matched
            source = "tpl"

    if not skeleton:
        from edu_cloud.modules.card.rendering.layout import build_skeleton_from_spec
        q_list = []
        if db_questions:
            for i, q in enumerate(sorted(db_questions, key=_q_sort_key)):
                q_list.append({
                    "number": i + 1,
                    "question_type": q.question_type,
                    "options_count": 4,
                })
        skeleton = build_skeleton_from_spec(
            q_list, paper_size=paper_size, columns=3,
            exam_number_digits=8,
        )

    logger.info("_match_skeleton: source=%s, subject=%s, paper=%s, columns=%d",
                source, subject.code, paper_size, len(skeleton.get("columns", [])))
    return skeleton


def _compute_layout(skeleton: dict, weights: list[dict]) -> dict:
    """根据骨架和权重计算布局（统一走权重分配，不再短路到 tpl 固定坐标）。"""
    from edu_cloud.modules.card.rendering.layout import allocate_by_weights
    from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
    finalize_skeleton(skeleton)  # 确保 columns[0].y1 精确
    columns = skeleton.get("columns", [])
    if weights and columns:
        return allocate_by_weights(weights, columns)
    return {"slots": []}




def _tpl_slots_to_layout(tpl_slots: list[dict]) -> dict:
    """将 .tpl 解析的 subjective_slots 转为 renderer 期望的 layout 格式。

    .tpl 坐标是扫描裁切区域（有重叠），需要去重叠后用作印刷边框。
    算法：同栏内按 y1 排序，相邻区域 y 重叠时取中点作为边界。
    """
    import re

    # 按 inpage 分组，每组内按栏（x 聚类）再按 y1 排序去重叠
    adjusted = _deoverlap_slots(tpl_slots)

    slots = []
    for s in adjusted:
        rect = s["rect"]
        score = s.get("score", 0)
        label = s.get("label", s.get("slot_id", ""))
        slot_id = s.get("slot_id", "")
        num_match = re.search(r"\d+", slot_id)
        name = num_match.group() if num_match else label

        sr = {
            "id": slot_id,
            "name": name,
            "score": score,
            "rect": dict(rect),
            "type": "essay",
        }
        slots.append({
            "slot_id": slot_id,
            "final_rect": dict(rect),
            "sub_regions": [sr],
            "inpage": s.get("inpage", 0),
        })
    return {"slots": slots}


def _deoverlap_slots(tpl_slots: list[dict]) -> list[dict]:
    """去除同栏相邻区域的 y 方向重叠。

    算法：按 x 中心聚类分栏 → 栏内按 y1 排序 → 相邻重叠取中点。
    """
    import copy
    result = []

    for inpage in (0, 1):
        page_slots = [s for s in tpl_slots if s.get("inpage", 0) == inpage]
        if not page_slots:
            continue

        # 按 x 中心聚类分栏
        columns = _cluster_by_x(page_slots)

        for col_slots in columns:
            # 栏内按 y1 排序
            col_slots.sort(key=lambda s: s["rect"]["y1"])
            adjusted = [copy.deepcopy(s) for s in col_slots]

            # 相邻去重叠
            for i in range(len(adjusted) - 1):
                cur = adjusted[i]["rect"]
                nxt = adjusted[i + 1]["rect"]
                if cur["y2"] > nxt["y1"]:
                    mid = (cur["y2"] + nxt["y1"]) // 2
                    cur["y2"] = mid
                    nxt["y1"] = mid

            result.extend(adjusted)

    return result


def _cluster_by_x(slots: list[dict], threshold_ratio: float = 0.15) -> list[list[dict]]:
    """按 x 中心坐标聚类。"""
    if not slots:
        return []

    # 计算 x 中心
    def x_center(s):
        return (s["rect"]["x1"] + s["rect"]["x2"]) / 2

    sorted_slots = sorted(slots, key=x_center)
    max_x = max(s["rect"]["x2"] for s in slots)
    threshold = max_x * threshold_ratio

    clusters: list[list[dict]] = [[sorted_slots[0]]]
    for s in sorted_slots[1:]:
        if x_center(s) - x_center(clusters[-1][-1]) > threshold:
            clusters.append([s])
        else:
            clusters[-1].append(s)

    return clusters


