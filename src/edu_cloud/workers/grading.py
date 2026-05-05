"""AI 阅卷 Worker — 后台处理主观题评分任务。

通过 arq 调度，从 Redis 接收 task_id，微批次并发调用 LLM 评分。
"""
import asyncio
import base64
import json
import logging
import time
import aiofiles

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.config import settings
from edu_cloud.modules.exam.models import Question, Subject, QUESTION_TYPES_SUBJECTIVE
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import Rubric, GradingTask, GradingResult
from edu_cloud.modules.grading.equivalence_guard import apply_equivalence_guard
import edu_cloud.models.user  # noqa: F401 — FK resolution for grading_tasks.created_by
import edu_cloud.models.school  # noqa: F401 — FK resolution for *.school_id

logger = logging.getLogger(__name__)


def _create_llm_client(
    api_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    *,
    use_gemini_official: bool = False,
) -> "LLMClient | GeminiClient":
    """Create LLM client for grading.

    use_gemini_official=True → 使用 Gemini 官方 SDK（实时+Batch 双模式）
    use_gemini_official=False → 使用 httpx 代理客户端（兼容旧路径）
    """
    if use_gemini_official:
        from edu_cloud.modules.grading.gemini_client import GeminiClient
        if settings.VERTEX_AI_PROJECT:
            return GeminiClient(
                vertex_project=settings.VERTEX_AI_PROJECT,
                vertex_location=settings.VERTEX_AI_LOCATION,
                model=model or settings.GEMINI_MODEL,
                max_retries=settings.LLM_MAX_RETRIES,
            )
        return GeminiClient(
            api_key=api_key or settings.GEMINI_API_KEY,
            model=model or settings.GEMINI_MODEL,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    from edu_cloud.modules.grading.llm_client import LLMClient
    return LLMClient(
        api_url=api_url or settings.LLM_API_URL,
        api_key=api_key or settings.LLM_API_KEY,
        model=model or settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
        slot=settings.LLM_SLOT,
    )


async def _read_image_b64(path: str) -> str:
    async with aiofiles.open(path, "rb") as f:
        data = await f.read()
    return base64.b64encode(data).decode()


_grading_semaphore = asyncio.Semaphore(20)

_ESSAY_CHAR_CAPS = [(20, 0), (150, 8), (200, 8), (350, 22), (450, 28), (500, 34)]


def _apply_essay_score_cap(score: float, char_count: int | None, question_type: str, max_score: float) -> float:
    """作文字数硬规则：残篇/严重不足时限制最高分。仅对作文题（max_score>=40）生效。"""
    if question_type != "essay" or max_score < 40 or char_count is None:
        return score
    for threshold, cap in _ESSAY_CHAR_CAPS:
        if char_count < threshold:
            return min(score, cap)
    return score


import math


_SENTENCE_END = set("。！？…）》"''"）")


def _detect_unfinished(char_count: int | None, ocr_tail: str) -> bool:
    """代码层硬判定未完成：字数<500 且结尾无句末标点。"""
    if char_count is None or char_count >= 500:
        return False
    tail = ocr_tail.rstrip()
    if not tail:
        return True
    return tail[-1] not in _SENTENCE_END


def _apply_boundary_guard(
    score: float,
    char_count: int | None,
    c1_parsed: dict,
    ocr_tail: str = "",
) -> float:
    """三层边界守卫：无效封顶 + 字数扣分/未完成封顶 + 议论式保底。"""
    validity = c1_parsed.get("validity", "normal")
    completion = c1_parsed.get("completion", "complete")
    style = c1_parsed.get("style", "event")

    # 代码层硬检测：模型可能误判 complete，用字数+尾部标点覆盖
    if completion != "unfinished" and _detect_unfinished(char_count, ocr_tail):
        completion = "unfinished"

    caps: list[float] = [42.0]

    # P1: 无效作文硬封顶
    if validity == "invalid":
        caps.append(15.0)

    # P2: 字数不足扣分 + 未完成封顶
    if char_count is not None and char_count < 600:
        shortage_penalty = math.ceil((600 - char_count) / 50)
        score -= shortage_penalty

    if completion == "unfinished":
        if char_count is not None and char_count < 500:
            caps.append(28.0)
        elif char_count is not None and char_count < 600:
            caps.append(30.0)
        else:
            caps.append(32.0)
    elif completion == "rushed":
        if char_count is not None and char_count < 600:
            caps.append(34.0)
        else:
            caps.append(36.0)

    effective_cap = min(caps)
    score = min(score, effective_cap)

    # P3: 议论式记叙文保底（仅当未触发无效/未完成封顶时）
    if (
        effective_cap >= 37
        and validity == "normal"
        and completion == "complete"
        and style == "reflective"
        and char_count is not None
        and char_count >= 550
    ):
        score = max(score, 37.0)
        caps.append(40.0)
        score = min(score, min(caps))

    return max(0.0, min(42.0, round(score)))


def _synthesize_essay_score(s1: float, s2: float | None) -> float:
    """合成作文最终分数：s1（3锚主评）+ s2（5锚confirm）。

    s2 作为确认信号，不与 s1 平均。39 分边界保守处理。
    """
    if s1 < 39:
        return s1
    if s1 == 39:
        return 39
    if s2 is None or s2 < 40:
        return 39
    if s1 == 40:
        if s2 <= 43:
            return 40
        if s2 <= 45:
            return 41
        return 42
    if s2 <= 45:
        return min(s1, 42)
    return min(s1 + 1, 42)


async def _grade_single(
    llm,
    ad: dict,
    rubrics_by_question: dict,
    *,
    use_gemini_official: bool = False,
) -> tuple[dict | None, dict | None, dict]:
    """Grade a single answer using two-step pipeline: OCR -> text-based grading.

    Falls back to legacy single-step if subject prompts not available.
    Returns (result_dict, error_dict, pipeline_log_dict).
    """
    answer_id = ad["answer_id"]
    question_id = ad["question_id"]
    t_start = time.perf_counter()

    plog = {
        "answer_id": answer_id,
        "question_id": question_id,
        "subject_code": ad.get("subject_code", ""),
        "question_type": ad.get("question_type", ""),
        "pipeline_type": "unknown",
        "is_blank": False,
        "image_size_bytes": None,
        "ocr_model": None, "ocr_prompt_type": None, "ocr_ms": None,
        "ocr_text": None, "ocr_blanks_count": None, "char_count": None,
        "grading_model": None, "grading_prompt_type": None, "grading_ms": None,
        "total_ms": None, "score": None, "confidence": None,
        "error_type": None, "error_message": None,
    }

    rubric_criteria = rubrics_by_question.get(question_id)
    if rubric_criteria is None:
        logger.warning("grading_task: no rubric for question=%s", question_id)
        plog["pipeline_type"] = "error"
        plog["error_type"] = "no_rubric"
        plog["error_message"] = f"No rubric for question {question_id}"
        plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
        return None, {"answer_id": answer_id, "error": plog["error_message"]}, plog

    try:
        image_b64 = await _read_image_b64(ad["image_path"])
        plog["image_size_bytes"] = len(image_b64) * 3 // 4

        # Blank detection: size check + CV ink ratio
        image_bytes_raw = base64.b64decode(image_b64)
        _is_blank = len(image_b64) < 6800
        if not _is_blank:
            from edu_cloud.modules.grading.image_utils import is_blank_image_cv
            _is_blank = is_blank_image_cv(image_bytes_raw)
        if _is_blank:
            plog["pipeline_type"] = "blank"
            plog["is_blank"] = True
            plog["score"] = 0
            plog["confidence"] = 1.0
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            return {
                "answer_id": answer_id, "question_id": question_id,
                "score": 0, "max_score": ad["question_max_score"],
                "feedback": "空白卷", "confidence": 1.0, "raw_content": "",
            }, None, plog

        subject = ad.get("subject_code", "")
        from edu_cloud.modules.grading.prompts import get_prompt, render_prompt

        grading_prompt_tpl = get_prompt(subject, "GRADING_TEXT", "senior")
        vision_prompt_tpl = get_prompt(subject, "GRADING_VISION", "senior") or get_prompt(subject, "GRADING", "senior")

        _is_drawing = ad.get("question_type") == "drawing"
        _is_essay = ad.get("question_type") == "essay" and ad["question_max_score"] >= 40
        _essay_anchors_early = rubric_criteria[0].get("essayAnchors") if _is_essay and rubric_criteria else None
        _use_vision = (_is_drawing or ad.get("use_vision", False)) and vision_prompt_tpl and not _essay_anchors_early

        if _use_vision:
            # Vision-direct: image + rubric → score (no OCR)
            plog["pipeline_type"] = "vision_direct"
            plog["grading_model"] = llm.model
            from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading as _fmt_rubric
            _rubric_text = _fmt_rubric(rubric_criteria)
            _full_score = str(ad["question_max_score"])
            _vision_prompt = render_prompt(vision_prompt_tpl, {
                "fullScore": _full_score,
                "rubric": _rubric_text,
            })
            if ad.get("question_type") == "drawing":
                from edu_cloud.modules.grading.prompts.base import DRAWING_HINT
                _vision_prompt = DRAWING_HINT + _vision_prompt
                plog["pipeline_type"] = "vision_direct_drawing"

            # Load reference answer images (standard answer) for visual comparison
            all_images_b64 = [image_b64]
            ref_paths = ad.get("reference_answer_images", [])
            has_ref = False
            for ref_path in ref_paths:
                try:
                    resolved = ref_path.lstrip("/")
                    ref_b64 = await _read_image_b64(resolved)
                    all_images_b64.append(ref_b64)
                    has_ref = True
                except Exception:
                    logger.warning("vision: failed to read reference image: %s", ref_path)
            if has_ref:
                _vision_prompt = "【第1张图片】学生作答\n【第2张图片】标准答案（请对比评分）\n\n" + _vision_prompt

            plog["grading_prompt_type"] = "GRADING_VISION"
            t_grade = time.perf_counter()
            grade_result = await llm.grade_vision(
                images_b64=all_images_b64,
                prompt=_vision_prompt,
                max_score=ad["question_max_score"],
            )
            plog["grading_ms"] = int((time.perf_counter() - t_grade) * 1000)
            plog["score"] = grade_result.score
            plog["confidence"] = grade_result.confidence
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)

            _details = None
            try:
                import json as _json
                _raw = _json.loads(grade_result.raw_content)
                _details = _raw.get("details")
            except Exception:
                pass

            return {
                "answer_id": answer_id, "question_id": question_id,
                "score": grade_result.score, "max_score": grade_result.max_score,
                "feedback": grade_result.feedback, "confidence": grade_result.confidence,
                "raw_content": grade_result.raw_content,
                "details": _details,
            }, None, plog

        elif grading_prompt_tpl is None:
            plog["pipeline_type"] = "error"
            plog["error_type"] = "no_prompt"
            plog["error_message"] = f"No grading prompt for subject '{subject}'"
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            logger.error("grading_task: no prompt for subject=%s, answer=%s", subject, answer_id)
            return None, {"answer_id": answer_id, "error": plog["error_message"]}, plog

        # Two-step path: OCR → text grading
        plog["pipeline_type"] = "two_step"
        plog["ocr_model"] = llm.model
        plog["grading_model"] = llm.model
        from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading

        rubric_text = format_rubric_for_grading(rubric_criteria)
        full_score = str(ad["question_max_score"])

        # Detect essay with anchor-based scoring
        _is_essay = ad.get("question_type") == "essay" and ad["question_max_score"] >= 40
        _essay_anchors = rubric_criteria[0].get("essayAnchors") if _is_essay and rubric_criteria else None

        # Step 1: OCR (essay uses dedicated plain-text OCR + CV cross-check)
        if _essay_anchors and use_gemini_official:
            from edu_cloud.modules.grading.prompts.base import ESSAY_OCR_PROMPT, clean_essay_ocr
            from edu_cloud.modules.grading.image_utils import estimate_char_count_cv
            plog["ocr_prompt_type"] = "ESSAY_OCR"
            plog["pipeline_type"] = "essay_anchor"
            t_ocr = time.perf_counter()
            image_bytes = base64.b64decode(image_b64)
            cv_estimate = estimate_char_count_cv(image_bytes)
            plog["cv_char_estimate"] = cv_estimate
            ocr_text = await llm.extract_essay_text(image_bytes=image_bytes, prompt=ESSAY_OCR_PROMPT)
            ocr_text = ocr_text or ""
            ocr_len = len(ocr_text)
            if cv_estimate > 0 and ocr_len < cv_estimate * 0.5:
                plog["ocr_retry"] = True
                plog["ocr_first_len"] = ocr_len
                ocr_text = await llm.extract_essay_text(image_bytes=image_bytes, prompt=ESSAY_OCR_PROMPT)
                ocr_text = ocr_text or ""
            ocr_text = clean_essay_ocr(ocr_text)
            plog["ocr_ms"] = int((time.perf_counter() - t_ocr) * 1000)
            blanks = [{"blankNo": "1", "text": ocr_text}]
            extracted_text = ocr_text
            plog["ocr_text"] = ocr_text[:500]
            plog["ocr_blanks_count"] = 1
        else:
            ocr_prompt = get_prompt(subject, "OCR_STRUCTURED", "senior") or get_prompt(subject, "OCR", "senior")
            plog["ocr_prompt_type"] = "OCR_STRUCTURED" if get_prompt(subject, "OCR_STRUCTURED", "senior") else "OCR"
            if ocr_prompt:
                structure = "\n".join(f"- {c.get('blankNo', '?')}: {c.get('subQ', '')}" for c in rubric_criteria)
                ocr_prompt = render_prompt(ocr_prompt, {"rubricStructure": structure})
            else:
                from edu_cloud.modules.grading.prompts.base import OCR_PROMPT_BASE
                ocr_prompt = OCR_PROMPT_BASE
                plog["ocr_prompt_type"] = "OCR_BASE"

            t_ocr = time.perf_counter()
            if use_gemini_official:
                image_bytes = base64.b64decode(image_b64)
                blanks = await llm.extract_text(image_bytes=image_bytes, prompt=ocr_prompt)
            else:
                blanks = await llm.extract_text(images_b64=[image_b64], prompt=ocr_prompt)
            plog["ocr_ms"] = int((time.perf_counter() - t_ocr) * 1000)

            from edu_cloud.modules.grading.ocr_validator import validate_ocr_blanks, recover_truncated_blanks
            blanks = validate_ocr_blanks(blanks)
            blanks = recover_truncated_blanks(blanks, len(rubric_criteria))

            extracted_text = "\n".join(f"{b.get('blankNo', '?')}: {b.get('text', '')}" for b in blanks)
            plog["ocr_text"] = extracted_text
            plog["ocr_blanks_count"] = len(blanks)

        # OCR-based blank detection: check each blank individually
        non_empty_blanks = [b for b in blanks if b.get("text", "").strip()]
        if len(non_empty_blanks) == 0:
            plog["pipeline_type"] = "blank"
            plog["is_blank"] = True
            plog["score"] = 0
            plog["confidence"] = 1.0
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            logger.info("grading_task: OCR blank detection — all %d blanks empty, answer=%s", len(blanks), answer_id)
            return {
                "answer_id": answer_id, "question_id": question_id,
                "score": 0, "max_score": ad["question_max_score"],
                "feedback": "空白卷（所有填空均未检测到作答内容）", "confidence": 1.0, "raw_content": "",
                "details": [{"blankNo": b.get("blankNo", str(i+1)), "score": 0, "maxScore": 0, "reason": "未作答"} for i, b in enumerate(blanks)],
            }, None, plog

        # Character count for essay questions
        char_stats = ""
        if ad.get("question_type") == "essay":
            from edu_cloud.modules.grading.prompts.base import count_essay_chars
            raw_text = "".join(b.get("text", "") for b in blanks)
            char_count, char_stats = count_essay_chars(raw_text)
            plog["char_count"] = char_count

        # Step 2: Grade — essay anchor path vs standard text grading
        if _essay_anchors:
            from edu_cloud.modules.grading.rubric_formatter import split_essay_anchors, build_essay_anchor_prompt
            from edu_cloud.modules.grading.json_parser import extract_json
            anchors_3, anchors_5 = split_essay_anchors(_essay_anchors)
            if len(anchors_3) >= 3:
                plog["grading_prompt_type"] = "ESSAY_ANCHOR_3+5"

                ds_key = settings.DEEPSEEK_API_KEY
                if not ds_key:
                    raise RuntimeError("DEEPSEEK_API_KEY not configured for essay anchor scoring")
                from edu_cloud.modules.grading.llm_client import LLMClient
                ds_llm = LLMClient(
                    api_url="https://api.deepseek.com/v1",
                    api_key=ds_key,
                    model="deepseek-v4-flash",
                    timeout=180,
                    max_retries=3,
                )
                plog["essay_scoring_model"] = "deepseek-v4-flash"

                # Call 1: 3-anchor score (0-42) via DeepSeek
                prompt_c1 = build_essay_anchor_prompt(extracted_text, char_stats, anchors_3, mode="score")
                t_grade = time.perf_counter()
                resp_c1 = await ds_llm.grade_text(prompt=prompt_c1, max_score=42)
                c1_ms = int((time.perf_counter() - t_grade) * 1000)
                c1_data = extract_json(resp_c1.raw_content)
                c1_parsed = c1_data if isinstance(c1_data, dict) else {}
                s1 = min(max(c1_parsed.get("score", 0), 0), 42)
                above_boundary = c1_parsed.get("above_boundary", False)

                # Call 2a: 5-anchor high-score confirm (s1 >= 39) via DeepSeek
                s2 = None
                c2_ms = 0
                if s1 >= 39 and len(anchors_5) >= 5:
                    prompt_c2 = build_essay_anchor_prompt(extracted_text, char_stats, anchors_5, mode="confirm")
                    t_c2 = time.perf_counter()
                    resp_c2 = await ds_llm.grade_text(prompt=prompt_c2, max_score=50)
                    c2_ms = int((time.perf_counter() - t_c2) * 1000)
                    c2_data = extract_json(resp_c2.raw_content)
                    c2_parsed = c2_data if isinstance(c2_data, dict) else {}
                    s2 = c2_parsed.get("score")
                    if s2 is not None:
                        s2 = float(s2)

                # Call 2b: low-score review (s1 < 32) via DeepSeek
                low_review = None
                c3_ms = 0
                if s1 < 32:
                    prompt_c3 = build_essay_anchor_prompt(extracted_text, char_stats, [], mode="low_review")
                    t_c3 = time.perf_counter()
                    resp_c3 = await ds_llm.grade_text(prompt=prompt_c3, max_score=42)
                    c3_ms = int((time.perf_counter() - t_c3) * 1000)
                    c3_data = extract_json(resp_c3.raw_content)
                    low_review = c3_data if isinstance(c3_data, dict) else {}
                    plog["low_review"] = low_review

                await ds_llm.close()

                # Boundary guard: apply validity/completion/style rules
                s1_guarded = _apply_boundary_guard(
                    float(s1), plog.get("char_count"), c1_parsed,
                    ocr_tail=extracted_text[-50:] if extracted_text else "",
                )
                plog["s1_raw"] = s1
                plog["s1_guarded"] = s1_guarded
                s1 = s1_guarded

                # Synthesize with tiered logic
                if s1 < 32 and low_review:
                    if low_review.get("confirmed_low"):
                        raw_final = float(min(max(low_review.get("score", s1), 0), 42))
                    else:
                        raw_final = max(float(s1), 34.0)
                else:
                    raw_final = _synthesize_essay_score(float(s1), s2)

                final_score = _apply_essay_score_cap(
                    raw_final, plog.get("char_count"), "essay", ad["question_max_score"],
                )
                plog["grading_ms"] = c1_ms + c2_ms + c3_ms
                plog["score"] = final_score
                plog["confidence"] = None
                plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)

                reason_c1 = c1_parsed.get("reason", "")
                raw_content = json.dumps({
                    "s1_raw": plog.get("s1_raw"), "s1": s1, "s2": s2,
                    "above_boundary": above_boundary,
                    "validity": c1_parsed.get("validity"),
                    "completion": c1_parsed.get("completion"),
                    "style": c1_parsed.get("style"),
                    "low_review": low_review,
                    "synthesized": raw_final, "final": final_score,
                    "reason_c1": reason_c1,
                }, ensure_ascii=False)

                logger.info(
                    "grading_task: essay_anchor answer=%s s1=%.0f s2=%s low=%s synth=%.0f final=%.0f char=%s",
                    answer_id, s1, s2, low_review, raw_final, final_score, plog.get("char_count"),
                )

                feedback = reason_c1
                if s1 < 32:
                    feedback = f"⚠️低分预警，建议重点复核。{feedback}"
                    plog["low_score_warning"] = True

                return {
                    "answer_id": answer_id, "question_id": question_id,
                    "score": final_score, "max_score": ad["question_max_score"],
                    "feedback": feedback, "confidence": None,
                    "raw_content": raw_content,
                    "details": [{"blankNo": "1", "score": final_score, "maxScore": ad["question_max_score"],
                                 "reason": f"s1={s1} s2={s2} → {final_score}"}],
                    "recognizedText": extracted_text,
                    "ocr_blanks": blanks,
                }, None, plog

        # Standard text grading (non-essay or no anchors)
        plog["grading_prompt_type"] = "GRADING_TEXT"
        grading_prompt = render_prompt(grading_prompt_tpl, {
            "fullScore": full_score,
            "rubric": rubric_text,
            "extractedText": extracted_text,
            "charStats": char_stats,
        })

        t_grade = time.perf_counter()
        grade_result = await llm.grade_text(prompt=grading_prompt, max_score=ad["question_max_score"])
        plog["grading_ms"] = int((time.perf_counter() - t_grade) * 1000)

        if grade_result.details and rubric_criteria:
            guarded = apply_equivalence_guard(
                {"score": grade_result.score, "details": grade_result.details},
                rubric_criteria,
            )
            grade_result.score = guarded["score"]
            grade_result.details = guarded["details"]

        plog["score"] = grade_result.score
        plog["confidence"] = grade_result.confidence
        plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)

        final_score = _apply_essay_score_cap(
            grade_result.score, plog.get("char_count"),
            ad.get("question_type", ""), ad["question_max_score"],
        )
        plog["score"] = final_score

        return {
            "answer_id": answer_id, "question_id": question_id,
            "score": final_score, "max_score": grade_result.max_score,
            "feedback": grade_result.feedback, "confidence": grade_result.confidence,
            "raw_content": grade_result.raw_content,
            "details": grade_result.details,
            "deductions": grade_result.deductions,
            "comment": grade_result.comment,
            "recognizedText": extracted_text,
            "ocr_blanks": blanks,
        }, None, plog

    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        logger.warning("grading_task: answer=%s FAILED: %s", answer_id, e)
        plog["pipeline_type"] = plog["pipeline_type"] if plog["pipeline_type"] != "unknown" else "error"
        plog["error_type"] = type(e).__name__
        plog["error_message"] = str(e)
        plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
        return None, {"answer_id": answer_id, "error": str(e)}, plog


async def _process_gemini_batch(llm, answer_data, rubrics_by_question, subject_code, use_gemini_official):
    """Gemini Batch API: 两阶段全 batch — OCR batch → 评分 batch。Cost = 50% of realtime."""
    from edu_cloud.modules.grading.prompts import get_prompt, render_prompt
    from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading
    from edu_cloud.modules.grading.json_parser import extract_json
    from edu_cloud.modules.grading.detail_flatten import flatten_llm_details
    from edu_cloud.modules.grading.ocr_validator import validate_ocr_blanks, recover_truncated_blanks
    from google.genai import types

    results = []  # [(result_dict|None, error_dict|None, plog)]
    # Phase 1 准备：分流 vision 直评 vs two-step OCR
    vision_pending = []   # [(idx, ad, plog, contents, t_start)]
    ocr_pending = []      # [(idx, ad, plog, ocr_contents, rubric_criteria, t_start)]

    for ad in answer_data:
        answer_id = ad["answer_id"]
        question_id = ad["question_id"]
        plog = {
            "answer_id": answer_id, "question_id": question_id,
            "subject_code": subject_code, "question_type": ad.get("question_type", ""),
            "pipeline_type": "unknown", "is_blank": False, "image_size_bytes": None,
            "ocr_model": None, "ocr_prompt_type": None, "ocr_ms": None,
            "ocr_text": None, "ocr_blanks_count": None, "char_count": None,
            "grading_model": None, "grading_prompt_type": None, "grading_ms": None,
            "total_ms": None, "score": None, "confidence": None,
            "error_type": None, "error_message": None,
        }
        t_start = time.perf_counter()
        rubric_criteria = rubrics_by_question.get(question_id)
        if not rubric_criteria:
            plog["pipeline_type"] = "error"
            plog["error_type"] = "no_rubric"
            plog["error_message"] = f"No rubric for question {question_id}"
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            results.append((None, {"answer_id": answer_id, "error": plog["error_message"]}, plog))
            continue

        try:
            image_b64 = await _read_image_b64(ad["image_path"])
            plog["image_size_bytes"] = len(image_b64) * 3 // 4

            if len(image_b64) < 6800:
                plog.update(pipeline_type="blank", is_blank=True, score=0, confidence=1.0,
                            total_ms=int((time.perf_counter() - t_start) * 1000))
                results.append(({
                    "answer_id": answer_id, "question_id": question_id,
                    "score": 0, "max_score": ad["question_max_score"],
                    "feedback": "空白卷", "confidence": 1.0, "raw_content": "",
                }, None, plog))
                continue

            rubric_text = format_rubric_for_grading(rubric_criteria)
            full_score = str(ad["question_max_score"])
            grading_prompt_tpl = get_prompt(subject_code, "GRADING_TEXT", "senior")
            vision_prompt_tpl = get_prompt(subject_code, "GRADING_VISION", "senior") or get_prompt(subject_code, "GRADING", "senior")
            _is_drawing = ad.get("question_type") == "drawing"
            _use_vision = (_is_drawing or ad.get("use_vision", False)) and vision_prompt_tpl

            if _use_vision:
                plog["pipeline_type"] = "vision_direct_drawing" if _is_drawing else "vision_direct"
                plog["grading_prompt_type"] = "GRADING_VISION"
                prompt = render_prompt(vision_prompt_tpl, {"fullScore": full_score, "rubric": rubric_text})
                if _is_drawing:
                    from edu_cloud.modules.grading.prompts.base import DRAWING_HINT
                    prompt = DRAWING_HINT + prompt
                image_bytes = base64.b64decode(image_b64)
                from edu_cloud.modules.grading.image_utils import resize_image_for_llm
                parts = []
                resized = resize_image_for_llm(image_bytes)
                mime = "image/png" if resized[:4] == b"\x89PNG" else "image/jpeg"
                parts.append(types.Part.from_bytes(data=resized, mime_type=mime))
                has_ref = False
                for ref_path in ad.get("reference_answer_images", []):
                    try:
                        ref_b64 = await _read_image_b64(ref_path.lstrip("/"))
                        ref_bytes = base64.b64decode(ref_b64)
                        ref_resized = resize_image_for_llm(ref_bytes)
                        ref_mime = "image/png" if ref_resized[:4] == b"\x89PNG" else "image/jpeg"
                        parts.append(types.Part.from_bytes(data=ref_resized, mime_type=ref_mime))
                        has_ref = True
                    except Exception:
                        pass
                if has_ref:
                    prompt = "【第1张图片】学生作答\n【第2张图片】标准答案（请对比评分）\n\n" + prompt
                parts.append(types.Part.from_text(text=prompt))
                contents = [types.Content(role="user", parts=parts)]
                plog["grading_model"] = llm.model
                idx = len(results)
                results.append(None)
                vision_pending.append((idx, ad, plog, contents, t_start))
            elif grading_prompt_tpl is None:
                plog["pipeline_type"] = "error"
                plog["error_type"] = "no_prompt"
                plog["error_message"] = f"No grading prompt for subject '{subject_code}'"
                plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
                results.append((None, {"answer_id": answer_id, "error": plog["error_message"]}, plog))
                continue
            else:
                plog["pipeline_type"] = "two_step"
                plog["grading_prompt_type"] = "GRADING_TEXT"
                ocr_prompt = get_prompt(subject_code, "OCR_STRUCTURED", "senior") or get_prompt(subject_code, "OCR", "senior")
                plog["ocr_prompt_type"] = "OCR_STRUCTURED" if get_prompt(subject_code, "OCR_STRUCTURED", "senior") else "OCR"
                if ocr_prompt:
                    structure = "\n".join(f"- {c.get('blankNo', '?')}: {c.get('subQ', '')}" for c in rubric_criteria)
                    ocr_prompt = render_prompt(ocr_prompt, {"rubricStructure": structure})
                else:
                    from edu_cloud.modules.grading.prompts.base import OCR_PROMPT_BASE
                    ocr_prompt = OCR_PROMPT_BASE
                    plog["ocr_prompt_type"] = "OCR_BASE"
                image_bytes = base64.b64decode(image_b64)
                from edu_cloud.modules.grading.image_utils import resize_image_for_llm
                resized = resize_image_for_llm(image_bytes)
                mime = "image/png" if resized[:4] == b"\x89PNG" else "image/jpeg"
                ocr_contents = [types.Content(role="user", parts=[
                    types.Part.from_bytes(data=resized, mime_type=mime),
                    types.Part.from_text(text=ocr_prompt),
                ])]
                plog["ocr_model"] = llm.model
                plog["grading_model"] = llm.model
                idx = len(results)
                results.append(None)
                ocr_pending.append((idx, ad, plog, ocr_contents, rubric_criteria, t_start))

        except Exception as e:
            plog["pipeline_type"] = plog["pipeline_type"] if plog["pipeline_type"] != "unknown" else "error"
            plog["error_type"] = type(e).__name__
            plog["error_message"] = str(e)
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            results.append((None, {"answer_id": answer_id, "error": str(e)}, plog))

    # ── Phase 1: OCR batch ──
    grade_pending = list(vision_pending)  # vision 直接进评分 batch

    if ocr_pending:
        logger.info("gemini_batch: phase1 OCR submitting %d requests", len(ocr_pending))
        ocr_reqs = [{"contents": c} for _, _, _, c, _, _ in ocr_pending]
        t_ocr_batch = time.perf_counter()
        try:
            ocr_job = await llm.create_batch_job(ocr_reqs)
            ocr_results = await llm.poll_batch_job(ocr_job, poll_interval=5, timeout=1200)
        except Exception as e:
            logger.error("gemini_batch: OCR batch failed: %s", e)
            for idx, ad, plog, _, _, t_start in ocr_pending:
                plog["error_type"] = "ocr_batch_failed"
                plog["error_message"] = str(e)
                plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
                results[idx] = (None, {"answer_id": ad["answer_id"], "error": str(e)}, plog)
            ocr_pending = []  # B002: 跳过解析循环
            ocr_results = []

        ocr_batch_ms = int((time.perf_counter() - t_ocr_batch) * 1000) if ocr_pending else 0
        if ocr_pending:
            logger.info("gemini_batch: phase1 OCR completed in %dms, got %d results", ocr_batch_ms, len(ocr_results))

        for i, (idx, ad, plog, _, rubric_criteria, t_start) in enumerate(ocr_pending):
            plog["ocr_ms"] = ocr_batch_ms // max(len(ocr_pending), 1)
            if i >= len(ocr_results) or not ocr_results[i].get("text"):
                plog["error_type"] = "ocr_batch_no_result"
                plog["error_message"] = "No OCR result from batch"
                plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
                results[idx] = (None, {"answer_id": ad["answer_id"], "error": plog["error_message"]}, plog)
                continue

            ocr_text = ocr_results[i]["text"]
            ocr_parsed = extract_json(ocr_text)
            if ocr_parsed is None:
                plog["error_type"] = "ocr_parse_error"
                plog["error_message"] = f"OCR JSON parse failed: {ocr_text[:100]}"
                plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
                results[idx] = (None, {"answer_id": ad["answer_id"], "error": plog["error_message"]}, plog)
                continue

            if isinstance(ocr_parsed, dict):
                blanks = ocr_parsed.get("blanks", [])
            else:
                blanks = ocr_parsed
            blanks = validate_ocr_blanks(blanks)
            blanks = recover_truncated_blanks(blanks, len(rubric_criteria))
            extracted_text = "\n".join(f"{b.get('blankNo', '?')}: {b.get('text', '')}" for b in blanks)
            plog["ocr_text"] = extracted_text
            plog["ocr_blanks_count"] = len(blanks)

            non_empty = [b for b in blanks if b.get("text", "").strip()]
            if not non_empty:
                plog.update(pipeline_type="blank", is_blank=True, score=0, confidence=1.0,
                            total_ms=int((time.perf_counter() - t_start) * 1000))
                results[idx] = ({
                    "answer_id": ad["answer_id"], "question_id": ad["question_id"],
                    "score": 0, "max_score": ad["question_max_score"],
                    "feedback": "空白卷（所有填空均未检测到作答内容）", "confidence": 1.0, "raw_content": "",
                    "details": [{"blankNo": b.get("blankNo", str(j+1)), "score": 0, "maxScore": 0, "reason": "未作答"} for j, b in enumerate(blanks)],
                }, None, plog)
                continue

            rubric_text = format_rubric_for_grading(rubric_criteria)
            full_score = str(ad["question_max_score"])

            char_stats = ""
            if ad.get("question_type") == "essay":
                from edu_cloud.modules.grading.prompts.base import count_essay_chars
                raw_text = "".join(b.get("text", "") for b in blanks)
                char_count, char_stats = count_essay_chars(raw_text)
                plog["char_count"] = char_count

            grading_prompt_tpl = get_prompt(subject_code, "GRADING_TEXT", "senior")
            grading_prompt = render_prompt(grading_prompt_tpl, {
                "fullScore": full_score, "rubric": rubric_text,
                "extractedText": extracted_text, "charStats": char_stats,
            })
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=grading_prompt)])]
            grade_pending.append((idx, ad, plog, contents, t_start))

    # ── Phase 2: 评分 batch（vision + text 一起提交）──
    if not grade_pending:
        return [r for r in results if r is not None]

    logger.info("gemini_batch: phase2 grading submitting %d requests", len(grade_pending))
    batch_reqs = [{"contents": contents} for _, _, _, contents, _ in grade_pending]
    t_batch = time.perf_counter()
    try:
        job_name = await llm.create_batch_job(batch_reqs)
        api_results = await llm.poll_batch_job(job_name, poll_interval=5, timeout=1200)
    except Exception as e:
        logger.error("gemini_batch: grading batch failed: %s", e)
        for idx, ad, plog, _, t_start in grade_pending:
            plog["error_type"] = "batch_failed"
            plog["error_message"] = str(e)
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            results[idx] = (None, {"answer_id": ad["answer_id"], "error": str(e)}, plog)
        return [r for r in results if r is not None]

    batch_ms = int((time.perf_counter() - t_batch) * 1000)
    logger.info("gemini_batch: phase2 grading completed in %dms, got %d results", batch_ms, len(api_results))

    # Parse batch results
    for i, (idx, ad, plog, _, t_start) in enumerate(grade_pending):
        if i >= len(api_results) or not api_results[i].get("text"):
            plog["error_type"] = "batch_no_result"
            plog["error_message"] = "No result from batch API"
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            results[idx] = (None, {"answer_id": ad["answer_id"], "error": "batch_no_result"}, plog)
            continue

        text = api_results[i]["text"]
        plog["grading_ms"] = batch_ms // len(grade_pending)
        plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)

        parsed = extract_json(text)
        if not parsed or not isinstance(parsed, dict):
            plog["error_type"] = "parse_error"
            plog["error_message"] = f"Failed to parse: {text[:100]}"
            results[idx] = (None, {"answer_id": ad["answer_id"], "error": plog["error_message"]}, plog)
            continue

        max_score = ad["question_max_score"]
        score = min(max(parsed.get("score", 0), 0), max_score)
        score = _apply_essay_score_cap(
            score, plog.get("char_count"),
            ad.get("question_type", ""), max_score,
        )
        plog["score"] = score
        plog["confidence"] = parsed.get("confidence")

        results[idx] = ({
            "answer_id": ad["answer_id"], "question_id": ad["question_id"],
            "score": score, "max_score": max_score,
            "feedback": parsed.get("comment", parsed.get("feedback", "")),
            "confidence": parsed.get("confidence"),
            "raw_content": text,
            "details": flatten_llm_details(parsed.get("details")),
            "deductions": parsed.get("deductions") or [],
            "comment": parsed.get("comment", ""),
            "recognizedText": parsed.get("llmRecognizedText", ""),
        }, None, plog)

    return [r for r in results if r is not None]


async def _grade_with_semaphore(llm, ad, rubrics, *, use_gemini_official=False):
    async with _grading_semaphore:
        return await _grade_single(llm, ad, rubrics, use_gemini_official=use_gemini_official)


async def process_grading_task(ctx: dict, task_id: str) -> None:
    """Process a single grading task: load answers, call LLM in micro-batches, save results."""
    task_start = time.perf_counter()
    logger.info("grading_task START: task=%s", task_id)

    session_factory = ctx.get("db_session_factory")

    local_engine = None
    if session_factory is None or not isinstance(session_factory, async_sessionmaker):
        local_engine = create_async_engine(settings.DATABASE_URL)
        session_factory = async_sessionmaker(local_engine, class_=AsyncSession, expire_on_commit=False)

    batch_size = settings.GRADING_BATCH_SIZE
    llm = None
    try:
        async with session_factory() as db:
            # Load task
            result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
            task = result.scalar_one()
            task.status = "processing"
            await db.commit()
            logger.info("grading_task: task=%s, subject=%s, status→processing", task_id, task.subject_id)

            # Resolve LLM config: school override → platform default → .env fallback
            from edu_cloud.modules.exam.slot_selector import get_llm_config, SLOT_AI_GRADING
            try:
                llm_url, llm_key, llm_model = await get_llm_config(
                    db, slot=SLOT_AI_GRADING, school_id=task.school_id,
                )
                logger.info("grading_task: task=%s, llm_config resolved from DB (model=%s)", task_id, llm_model)
            except Exception:
                llm_url, llm_key, llm_model = None, None, None
                logger.warning("grading_task: task=%s, llm_config DB lookup failed, fallback to .env", task_id, exc_info=True)

            use_gemini = bool(settings.GEMINI_API_KEY or settings.VERTEX_AI_PROJECT)
            if use_gemini:
                llm_key = settings.GEMINI_API_KEY
                llm_model = settings.GEMINI_MODEL
                logger.info("grading_task: task=%s, using Gemini official API (mode=%s, model=%s)", task_id, task.grading_mode, llm_model)
            llm = _create_llm_client(
                api_url=llm_url, api_key=llm_key, model=llm_model,
                use_gemini_official=bool(use_gemini),
            )

            # Find subjective questions
            if task.question_ids:
                # Multi-question batch: load specified questions
                q_result = await db.execute(
                    select(Question).where(
                        Question.id.in_(task.question_ids),
                        Question.subject_id == task.subject_id,
                        Question.school_id == task.school_id,
                        Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
                    )
                )
            elif task.question_id:
                # Question-level: only load specified question
                q_result = await db.execute(
                    select(Question).where(
                        Question.id == task.question_id,
                        Question.subject_id == task.subject_id,
                        Question.school_id == task.school_id,
                        Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
                    )
                )
            else:
                # Subject-level: load all subjective questions (ORC-002: unchanged)
                q_result = await db.execute(
                    select(Question).where(
                        Question.subject_id == task.subject_id,
                        Question.school_id == task.school_id,
                        Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
                    )
                )
            questions = {q.id: q for q in q_result.scalars().all()}
            logger.info("grading_task: task=%s, question_id=%s, subjective_questions=%d",
                        task_id, task.question_id, len(questions))

            # Get subject code for prompt dispatch
            subject_result = await db.execute(select(Subject).where(Subject.id == task.subject_id))
            subject_row = subject_result.scalar_one_or_none()
            subject_code = subject_row.code if subject_row else ""

            if not questions:
                task.status = "completed"
                await db.commit()
                logger.info("grading_task DONE: task=%s, no subjective questions", task_id)
                return

            # Find answers — same order as manual grading (student_id ASC)
            answer_filter = [
                StudentAnswer.subject_id == task.subject_id,
                StudentAnswer.school_id == task.school_id,
                StudentAnswer.question_id.in_(list(questions.keys())),
            ]
            if task.question_id:
                answer_filter.append(StudentAnswer.question_id == task.question_id)
            a_result = await db.execute(
                select(StudentAnswer)
                .where(*answer_filter)
                .order_by(StudentAnswer.student_id)
            )
            answers_raw = a_result.scalars().all()

            # Exclude answers that already have grading results (confirmed or ai_done)
            all_answer_ids = [a.id for a in answers_raw]
            graded_rows = set()
            if all_answer_ids:
                graded_rows = set((await db.execute(
                    select(GradingResult.answer_id).where(
                        GradingResult.answer_id.in_(all_answer_ids),
                        GradingResult.status.in_(["confirmed", "ai_done"]),
                    )
                )).scalars().all())

            answer_data = []
            for a in answers_raw:
                if a.id in graded_rows:
                    continue
                q = questions[a.question_id]
                ans_qtype = a.question_type or q.question_type
                answer_data.append({
                    "answer_id": a.id,
                    "question_id": q.id,
                    "question_name": q.name,
                    "question_max_score": q.max_score,
                    "image_path": a.image_path,
                    "question_type": ans_qtype,
                    "subject_code": subject_code,
                    "use_vision": getattr(task, "use_vision", False),
                    "reference_answer_images": q.reference_answer_images or [],
                })
            if len(graded_rows) > 0:
                logger.info("grading_task: excluded %d already graded answers", len(graded_rows))

            # Load rubrics
            rubric_result = await db.execute(
                select(Rubric).where(Rubric.question_id.in_(list(questions.keys())))
            )
            rubrics_by_question = {r.question_id: r.criteria for r in rubric_result.scalars().all()}

            if task.grading_limit and task.grading_limit > 0 and len(answer_data) > task.grading_limit:
                logger.info("grading_task: applying limit %d (total available %d)", task.grading_limit, len(answer_data))
                answer_data = answer_data[:task.grading_limit]

            task.total = len(answer_data)
            await db.commit()
            logger.info("grading_task: task=%s, answers=%d, rubrics=%d, batch_size=%d",
                        task_id, len(answer_data), len(rubrics_by_question), batch_size)

            # Batch API mode: collect requests → submit → poll → parse
            if task.grading_mode == "batch" and use_gemini:
                batch_results = await _process_gemini_batch(
                    llm, answer_data, rubrics_by_question, subject_code, use_gemini,
                )
                logger.info("grading_task: task=%s, batch API returned %d results", task_id, len(batch_results))

            # Realtime mode (or non-Gemini fallback): micro-batch concurrent calls with per-batch commit
            else:
                from edu_cloud.modules.grading.models import GradingPipelineLog
                errors = []
                processed = 0
                for batch_start in range(0, len(answer_data), batch_size):
                    batch = answer_data[batch_start:batch_start + batch_size]
                    batch_num = batch_start // batch_size + 1
                    logger.info("grading_task: task=%s, micro-batch %d, size=%d", task_id, batch_num, len(batch))
                    coros = [_grade_with_semaphore(llm, ad, rubrics_by_question, use_gemini_official=use_gemini) for ad in batch]
                    mb_results = await asyncio.gather(*coros)
                    batch_completed = 0
                    batch_failed = 0
                    for result_dict, error_dict, plog in mb_results:
                        db.add(GradingPipelineLog(
                            answer_id=plog["answer_id"], question_id=plog["question_id"],
                            task_id=task.id, school_id=task.school_id,
                            subject_code=plog.get("subject_code"), question_type=plog.get("question_type"),
                            pipeline_type=plog["pipeline_type"], image_size_bytes=plog.get("image_size_bytes"),
                            is_blank=plog.get("is_blank", False),
                            ocr_model=plog.get("ocr_model"), ocr_prompt_type=plog.get("ocr_prompt_type"),
                            ocr_ms=plog.get("ocr_ms"), ocr_text=plog.get("ocr_text"),
                            ocr_blanks_count=plog.get("ocr_blanks_count"), char_count=plog.get("char_count"),
                            grading_model=plog.get("grading_model"), grading_prompt_type=plog.get("grading_prompt_type"),
                            grading_ms=plog.get("grading_ms"), total_ms=plog.get("total_ms"),
                            score=plog.get("score"), confidence=plog.get("confidence"),
                            error_type=plog.get("error_type"), error_message=plog.get("error_message"),
                        ))
                        if error_dict is not None:
                            errors.append(error_dict)
                            batch_failed += 1
                        else:
                            details = result_dict.get("details") or []
                            db.add(GradingResult(
                                ai_task_id=task.id, answer_id=result_dict["answer_id"],
                                question_id=result_dict["question_id"], school_id=task.school_id,
                                ai_score=result_dict["score"], ai_confidence=result_dict["confidence"],
                                ai_feedback=result_dict.get("comment") or result_dict.get("feedback", ""),
                                ai_raw_response={
                                    "raw_content": result_dict.get("raw_content", ""),
                                    "details": details,
                                    "deductions": result_dict.get("deductions") or [],
                                    "comment": result_dict.get("comment", ""),
                                    "recognizedText": result_dict.get("recognizedText"),
                                },
                                final_score=result_dict["score"], max_score=result_dict["max_score"],
                                status="ai_done",
                            ))
                            sa = await db.get(StudentAnswer, result_dict["answer_id"])
                            if sa:
                                sa.score = result_dict["score"]
                            batch_completed += 1
                    processed += len(batch)
                    result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
                    task = result.scalar_one()
                    task.completed += batch_completed
                    task.failed += batch_failed
                    await db.commit()
                    logger.info("grading_task: task=%s, batch %d done, +%d/+%d, progress=%d/%d",
                                task_id, batch_num, batch_completed, batch_failed, processed, len(answer_data))

            # Batch API mode: write all results at once
            if task.grading_mode == "batch" and use_gemini and batch_results:
                from edu_cloud.modules.grading.models import GradingPipelineLog
                errors = []
                total_completed = 0
                total_failed = 0
                for result_dict, error_dict, plog in batch_results:
                    db.add(GradingPipelineLog(
                        answer_id=plog["answer_id"], question_id=plog["question_id"],
                        task_id=task.id, school_id=task.school_id,
                        subject_code=plog.get("subject_code"), question_type=plog.get("question_type"),
                        pipeline_type=plog["pipeline_type"], image_size_bytes=plog.get("image_size_bytes"),
                        is_blank=plog.get("is_blank", False),
                        ocr_model=plog.get("ocr_model"), ocr_prompt_type=plog.get("ocr_prompt_type"),
                        ocr_ms=plog.get("ocr_ms"), ocr_text=plog.get("ocr_text"),
                        ocr_blanks_count=plog.get("ocr_blanks_count"), char_count=plog.get("char_count"),
                        grading_model=plog.get("grading_model"), grading_prompt_type=plog.get("grading_prompt_type"),
                        grading_ms=plog.get("grading_ms"), total_ms=plog.get("total_ms"),
                        score=plog.get("score"), confidence=plog.get("confidence"),
                        error_type=plog.get("error_type"), error_message=plog.get("error_message"),
                    ))
                    if error_dict is not None:
                        errors.append(error_dict)
                        total_failed += 1
                    else:
                        details = result_dict.get("details") or []
                        db.add(GradingResult(
                            ai_task_id=task.id, answer_id=result_dict["answer_id"],
                            question_id=result_dict["question_id"], school_id=task.school_id,
                            ai_score=result_dict["score"], ai_confidence=result_dict["confidence"],
                            ai_feedback=result_dict.get("comment") or result_dict.get("feedback", ""),
                            ai_raw_response={
                                "raw_content": result_dict.get("raw_content", ""),
                                "details": details,
                                "deductions": result_dict.get("deductions") or [],
                                "comment": result_dict.get("comment", ""),
                                "recognizedText": result_dict.get("recognizedText"),
                            },
                            final_score=result_dict["score"], max_score=result_dict["max_score"],
                            status="ai_done",
                        ))
                        sa = await db.get(StudentAnswer, result_dict["answer_id"])
                        if sa:
                            sa.score = result_dict["score"]
                        total_completed += 1
                result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
                task = result.scalar_one()
                task.completed = total_completed
                task.failed = total_failed
                await db.commit()

            # Final status
            result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
            task = result.scalar_one()
            task.status = "failed" if errors else "completed"
            task.error_log = errors if errors else None
            await db.commit()

            elapsed = time.perf_counter() - task_start
            logger.info("grading_task DONE: task=%s, status=%s, completed=%d, failed=%d, elapsed=%.1fs",
                        task_id, task.status, task.completed, task.failed, elapsed)
    finally:
        if llm is not None:
            await llm.close()
        if local_engine is not None:
            await local_engine.dispose()


async def run_post_exam_pipeline(ctx: dict, exam_id: str, school_id: str) -> None:
    """考后流水线 arq 任务 — 调用 pipeline 全流程。"""
    logger.info("post_exam_pipeline START: exam=%s, school=%s", exam_id, school_id)
    from edu_cloud.database import async_session
    from edu_cloud.modules.pipeline.service import run_full_pipeline
    async with async_session() as db:
        results = await run_full_pipeline(db, exam_id=exam_id, school_id=school_id)
        await db.commit()
    logger.info("post_exam_pipeline DONE: exam=%s, results=%s", exam_id, results)
