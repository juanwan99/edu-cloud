"""LLM 答案标准化：将正则粗解析结果或 PDF 图片转为结构化题目信息。"""
import base64
import json
import logging
from pathlib import Path

import httpx

from edu_cloud.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """你是一个考试答案分析助手。分析以下从答案文件提取的内容，判断每道题的类型和结构。

目标：为制作答题卡提供题目结构信息。

题型判断规则：
- 答案为单个字母(A/B/C/D)→ single_choice
- 答案为多个字母(AB/BCD/ACD等)→ multi_choice
- 答案为数值、公式、短词语（无解题过程，通常一行以内）→ fill_in_blank
- 答案有完整解题步骤、证明过程、多行文字 → short_answer
- 如果答案中有(1)(2)等标记，计算 sub_count

对每道题返回 JSON 对象：
{{
  "number": 题号(int),
  "type": "single_choice" | "multi_choice" | "fill_in_blank" | "short_answer",
  "section": "所属大题名称（如'一、选择题'），无法判断时为null",
  "answer": "标准答案文本",
  "score": "分值(int)，无法判断时为null",
  "options_count": 选项数(int, 仅选择题, 默认4),
  "sub_count": 小问数(int, 默认1)
}}

只返回 JSON 数组，不要其他文字。"""


def _get_llm_endpoint(settings, *, slot: str) -> tuple[str, dict]:
    """返回 (url, headers)。走 llm-proxy。"""
    if not settings.LLM_API_URL:
        return "", {}
    return (
        f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
        {"X-LLM-Slot": slot, "Content-Type": "application/json"},
    )


async def standardize_answers(parsed: list[dict]) -> list[dict]:
    """调 LLM 将正则粗解析结果标准化为结构化题目信息（题型识别，不含分值）。"""
    # settings already imported at module level
    url, headers = _get_llm_endpoint(settings, slot="answer-text")
    if not url:
        logger.warning("LLM not configured, using fallback heuristic")
        return _fallback_heuristic(parsed)

    system_prompt = SYSTEM_PROMPT_TEMPLATE
    user_content = json.dumps(parsed, ensure_ascii=False, indent=2)

    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"以下是从 Word 答案文件提取的内容：\n{user_content}"},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
        logger.error("LLM standardize_answers request failed: %s %s", type(e).__name__, e, exc_info=True)
        return _fallback_heuristic(parsed)

    content = data["choices"][0]["message"]["content"]
    content = _strip_markdown_fence(content)

    result = _parse_llm_json(content)
    if not result:
        logger.warning("LLM returned unparseable JSON, using fallback")
        return _fallback_heuristic(parsed)

    logger.info("standardize_answers: %d questions standardized via LLM", len(result))
    _post_process(result)
    return result


VISION_PROMPT_TEMPLATE = """你是一个考试答案分析助手。请仔细阅读图片中的考试答案，提取每道题的最终答案（不需要解题过程）。

题型判断规则：
- 答案为单个字母(A/B/C/D)→ single_choice
- 答案为多个字母(AB/BCD等)→ multi_choice
- 答案为数值、公式、短词语（无解题过程）→ fill_in_blank
- 答案有完整解题步骤、证明过程 → short_answer
- 如果答案中有(1)(2)等小问标记，计算 sub_count

重要：
- 选择题只写字母答案
- 填空题只写最终结果（公式用 LaTeX，如 \\frac{{1}}{{2}}、\\sqrt{{3}}）
- 解答题只写每小问的最终结论/结果，不写推导过程

对每道题返回 JSON 对象：
{{
  "number": 题号(int),
  "type": "single_choice" | "multi_choice" | "fill_in_blank" | "short_answer",
  "section": "所属大题名称（如'一、选择题'），无法判断时为null",
  "answer": "最终答案（公式用LaTeX）",
  "score": "分值(int)，无法判断时为null",
  "options_count": 选项数(int, 仅选择题, 默认4),
  "sub_count": 小问数(int, 默认1)
}}

只返回 JSON 数组，不要其他文字。"""


def _pdf_to_base64_images(file_path: str | Path, *, dpi: int = 200) -> list[str]:
    """将 PDF 每页渲染为 PNG 图片，返回 base64 编码列表。"""
    import fitz  # pymupdf

    doc = fitz.open(str(file_path))
    images = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        images.append(base64.b64encode(pix.tobytes("png")).decode())
    doc.close()
    logger.info("_pdf_to_base64_images: %d pages, dpi=%d", len(images), dpi)
    return images


async def standardize_from_pdf(
    file_path: str | Path,
) -> list[dict]:
    """PDF 答案文件 → 多模态 LLM（vision）→ 结构化题目 JSON。

    将 PDF 页面渲染为图片，直接发给支持 vision 的 LLM，
    保留公式、图片、特殊符号等信息。只识别题型结构，不推断分值。
    """
    # settings already imported at module level
    url, headers = _get_llm_endpoint(settings, slot="answer-vision")
    if not url:
        raise ValueError("LLM 未配置，无法解析 PDF 答案文件")

    images_b64 = _pdf_to_base64_images(file_path)
    if not images_b64:
        raise ValueError("PDF 文件无内容")

    system_prompt = VISION_PROMPT_TEMPLATE

    user_content = []
    for i, img_b64 in enumerate(images_b64):
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
        })
    user_content.append({
        "type": "text",
        "text": f"以上是考试答案文件共 {len(images_b64)} 页。请识别所有题目的题号、题型和答案，返回 JSON。",
    })

    try:
        async with httpx.AsyncClient(timeout=max(settings.LLM_TIMEOUT, 180)) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 16384,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
        logger.error("Vision LLM request failed: %s", e)
        raise ValueError(f"LLM 请求失败: {e}")

    content = data["choices"][0]["message"]["content"]
    content = _strip_markdown_fence(content)

    result = _parse_llm_json(content)
    if not result:
        raise ValueError("LLM 未返回有效题目数据")

    logger.info("standardize_from_pdf: %d questions via vision LLM", len(result))
    _post_process(result)
    return result


def _strip_markdown_fence(content: str) -> str:
    """去除 markdown 代码块包裹。"""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    return content.strip()


def _parse_llm_json(content: str) -> list[dict]:
    """解析 LLM 返回的 JSON，处理截断和格式问题。"""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试修复截断：找最后一个完整的 "}," 或 "}"，截断后补 "]"
    last_brace = content.rfind("}")
    if last_brace > 0:
        truncated = content[:last_brace + 1]
        # 去掉末尾多余的逗号
        truncated = truncated.rstrip().rstrip(",")
        # 确保以 "[" 开头
        start = truncated.find("[")
        if start >= 0:
            candidate = truncated[start:] + "]"
            try:
                result = json.loads(candidate)
                logger.warning("_parse_llm_json: repaired truncated JSON, recovered %d items", len(result))
                return result
            except json.JSONDecodeError:
                pass

    logger.error("_parse_llm_json: cannot parse, raw=%s", content[:500])
    return []


def _post_process(result: list[dict]) -> None:
    """为 LLM 返回结果补充默认字段 + 后端置信度覆盖。"""
    from edu_cloud.modules.card.parser.confidence import compute_confidence
    for q in result:
        q.setdefault("section", None)
        q.setdefault("score", None)
        q.setdefault("warnings", [])
        q["confidence"] = compute_confidence(q)


def _fallback_heuristic(parsed: list[dict]) -> list[dict]:
    """无 LLM 时的启发式推断（纯规则），只分类题型，不推断分值。"""
    classified = []
    for p in parsed:
        text = p["answer_text"].strip()
        num = p["number"]
        if len(text) <= 2 and text.isalpha() and text.isupper():
            qtype = "single_choice" if len(text) == 1 else "multi_choice"
            classified.append({"number": num, "type": qtype, "answer": text,
                               "sub_count": 1, "options_count": 4,
                               "section": None, "score": None,
                               "confidence": 0.95, "warnings": []})
        elif len(text) <= 30:
            classified.append({"number": num, "type": "fill_in_blank", "answer": text,
                               "sub_count": 1, "options_count": 0,
                               "section": None, "score": None,
                               "confidence": 0.90, "warnings": []})
        else:
            sub_count = max(1, text.count("(1)") + text.count("（1）"))
            classified.append({"number": num, "type": "short_answer", "answer": text,
                               "sub_count": sub_count, "options_count": 0,
                               "section": None, "score": None,
                               "confidence": 0.85, "warnings": []})
    return classified


def _extract_pdf_text(file_path: str | Path) -> list[str]:
    """用 pymupdf 逐页提取 PDF 文字。返回 [page_text, ...]。"""
    import fitz
    doc = fitz.open(str(file_path))
    texts = [page.get_text().strip() for page in doc]
    doc.close()
    logger.info("_extract_pdf_text: %d pages, chars=[%s]",
                len(texts), ", ".join(str(len(t)) for t in texts))
    return texts


def _has_sufficient_text(text_by_page: list[str], threshold: int = 50) -> bool:
    """判断 PDF 是否有足够且可读的文字层。

    仅检查字符数量不够——嵌入字体 PDF 提取出大量乱码字符也能过阈值。
    额外检查文字质量：CJK + 字母数字 + 常用标点 占比 >30% 才算可读。
    """
    if not text_by_page:
        return False
    avg = sum(len(t) for t in text_by_page) / len(text_by_page)
    if avg <= threshold:
        return False
    # 文字质量检测：防止嵌入字体 PDF 的乱码文字骗过字符数阈值
    # 只认 ASCII 字母数字 + CJK + 常用标点，拉丁扩展字符(Ê/É/î/š等)不算
    all_text = "".join(text_by_page)
    if not all_text:
        return False
    readable = sum(
        1 for c in all_text
        if ('a' <= c <= 'z') or ('A' <= c <= 'Z') or ('0' <= c <= '9')  # ASCII only
        or '\u4e00' <= c <= '\u9fff'           # CJK 基本区
        or '\u3400' <= c <= '\u4dbf'           # CJK 扩展A
        or c in '，。！？、；：""''（）【】·—…《》\n\r\t '  # 常用中文标点+空白
    )
    ratio = readable / len(all_text)
    if ratio < 0.5:
        logger.warning("_has_sufficient_text: 文字质量低 (readable=%.1f%%), 疑似嵌入字体乱码",
                        ratio * 100)
        return False
    return True


def _text_to_paragraphs(text_by_page: list[str]) -> list[tuple[str, int]]:
    """将按页文字转换为 word_parser._match_paragraphs 所需的 (text, image_count) 格式。"""
    paragraphs = []
    for page_text in text_by_page:
        for line in page_text.split("\n"):
            line = line.strip()
            if line:
                paragraphs.append((line, 0))
    return paragraphs


async def parse_pdf_answers(file_path: str | Path) -> tuple[list[dict], str]:
    """PDF 答案解析入口 — 自动选择文字层路径或 vision 路径。

    有文字层 → 复用 word_parser 正则分割 → 文本 LLM 标准化
    无文字层（扫描件）→ vision LLM 单次调用

    返回 (standardized, parse_method)。parse_method = 'text_llm' | 'vision_llm'。
    """
    text_by_page = _extract_pdf_text(file_path)
    if _has_sufficient_text(text_by_page):
        logger.info("parse_pdf_answers: 检测到文字层，走文本路径")
        paragraphs = _text_to_paragraphs(text_by_page)
        from edu_cloud.modules.card.parser.word_parser import _match_paragraphs
        parsed = _match_paragraphs(paragraphs)
        if not parsed:
            logger.warning("parse_pdf_answers: 文字层路径未识别到题目，降级到 vision")
            return await standardize_from_pdf(file_path), "vision_llm"
        return await standardize_answers(parsed), "text_llm"
    else:
        logger.info("parse_pdf_answers: 无文字层（扫描件），走 vision 路径")
        return await standardize_from_pdf(file_path), "vision_llm"
