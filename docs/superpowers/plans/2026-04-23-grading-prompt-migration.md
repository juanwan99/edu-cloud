# AI Grading Prompt System Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate zhixue-server's proven AI grading prompt system (subject-specific prompts, 6-field rubric structure, two-step OCR+grading pipeline) into edu-cloud, replacing the current 3 generic prompts with a production-quality grading engine.

**Architecture:** Three-layer design: (1) Subject-specific prompt templates in `prompts/` package with Mustache-style `{{variable}}` rendering, (2) Rubric formatter converting structured criteria into grading text, (3) Two-step worker pipeline (OCR extract → text-based grading) replacing current single-step image grading. The existing GradingTask/GradingResult models and arq worker infrastructure remain unchanged.

**Tech Stack:** Python 3.11, FastAPI, asyncio.Semaphore, httpx (async), existing llm-proxy at localhost:8100

**Source reference:** zhixue-server code at `~/projects/zhixue-server-git/src/`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/edu_cloud/modules/grading/prompts/__init__.py` | Create | Prompt dispatcher: get_prompt(subject, type, level) + render_prompt() |
| `src/edu_cloud/modules/grading/prompts/rubric_template.py` | Create | RUBRIC_GENERATION master template (from zhixue rubric-template.js) |
| `src/edu_cloud/modules/grading/prompts/biology.py` | Create | Biology: 4 prompt types (RUBRIC_GEN/GRADING/GRADING_TEXT/OCR) |
| `src/edu_cloud/modules/grading/prompts/math.py` | Create | Math: 4 prompt types |
| `src/edu_cloud/modules/grading/prompts/chinese.py` | Create | Chinese: 4 prompt types |
| `src/edu_cloud/modules/grading/prompts/base.py` | Create | Shared constants: JSON output schema, fatal rules, grading method template |
| `src/edu_cloud/modules/grading/rubric_formatter.py` | Create | format_rubric_for_grading(items) — criteria list → text for LLM |
| `src/edu_cloud/modules/grading/json_parser.py` | Create | extract_json(text) — 4-level fallback JSON extraction |
| `src/edu_cloud/modules/grading/prompts.py` | Modify | Keep backward-compat exports, delegate to prompts/ package |
| `src/edu_cloud/modules/grading/llm_client.py` | Modify | Add extract_text(), grade_text(), multi-image grade(); use json_parser |
| `src/edu_cloud/modules/grading/router.py` | Modify | Update _validate_criteria for 6-field schema; update generate endpoint |
| `src/edu_cloud/workers/grading.py` | Modify | Two-step pipeline + Semaphore + blank detection |
| `tests/test_services_exam/test_grading_prompts.py` | Modify | Test new prompt dispatch |
| `tests/test_services_exam/test_json_parser.py` | Create | Test JSON extraction |
| `tests/test_services_exam/test_rubric_formatter.py` | Create | Test rubric formatting |
| `tests/test_workers/test_grading_worker.py` | Modify | Test two-step pipeline |

---

## Phase 1: Core Pipeline (8 Tasks)

### Task 1: JSON Parser — Robust LLM Output Extraction

**Files:**
- Create: `src/edu_cloud/modules/grading/json_parser.py`
- Create: `tests/test_services_exam/test_json_parser.py`

- [ ] **Step 1: Write failing tests for JSON extraction**

```python
# tests/test_services_exam/test_json_parser.py
import pytest
from edu_cloud.modules.grading.json_parser import extract_json


def test_clean_json():
    assert extract_json('{"score": 5}') == {"score": 5}


def test_markdown_code_block():
    text = '```json\n{"score": 5}\n```'
    assert extract_json(text) == {"score": 5}


def test_markdown_no_lang():
    text = '```\n{"score": 5}\n```'
    assert extract_json(text) == {"score": 5}


def test_text_before_json():
    text = 'Here is my analysis:\n{"score": 5, "comment": "good"}'
    assert extract_json(text) == {"score": 5, "comment": "good"}


def test_json_array():
    text = '[{"blankNo": "1", "score": 3}]'
    result = extract_json(text)
    assert isinstance(result, list)
    assert result[0]["blankNo"] == "1"


def test_nested_braces():
    text = '{"score": 5, "details": [{"sub": {"a": 1}}]}'
    assert extract_json(text)["details"][0]["sub"]["a"] == 1


def test_garbage_returns_none():
    assert extract_json("I cannot grade this image") is None


def test_truncated_json():
    text = '{"score": 5, "details": [{"blank": "1"'
    result = extract_json(text)
    assert result is not None
    assert result["score"] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_json_parser.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement json_parser.py**

```python
# src/edu_cloud/modules/grading/json_parser.py
"""Robust JSON extraction from LLM responses.

4-level fallback: clean parse → code block strip → bracket balance → greedy search.
Ported from zhixue-server llmService.extractJsonFromText.
"""
import json
import re


def extract_json(text: str) -> dict | list | None:
    if not text or not text.strip():
        return None
    text = text.strip()

    # Level 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Level 2: strip markdown code block
    stripped = _strip_code_block(text)
    if stripped != text:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Level 3: find balanced brackets
    result = _find_balanced(stripped or text)
    if result is not None:
        return result

    # Level 4: greedy — find first { or [ and try to parse
    result = _greedy_parse(text)
    if result is not None:
        return result

    return None


def _strip_code_block(text: str) -> str:
    m = re.match(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


def _find_balanced(text: str) -> dict | list | None:
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def _greedy_parse(text: str) -> dict | list | None:
    for opener in ["{", "["]:
        start = text.find(opener)
        if start == -1:
            continue
        candidate = text[start:]
        # Try progressively shorter substrings
        for end in range(len(candidate), 0, -1):
            try:
                return json.loads(candidate[:end])
            except json.JSONDecodeError:
                continue
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_json_parser.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/grading/json_parser.py tests/test_services_exam/test_json_parser.py
git commit -m "feat(grading): add robust JSON parser with 4-level fallback extraction"
```

---

### Task 2: Prompt Dispatcher & Template Rendering

**Files:**
- Create: `src/edu_cloud/modules/grading/prompts/__init__.py`
- Create: `src/edu_cloud/modules/grading/prompts/base.py`
- Modify: `src/edu_cloud/modules/grading/prompts.py` (keep backward compat)

- [ ] **Step 1: Write failing test for prompt dispatch**

```python
# tests/test_services_exam/test_prompt_dispatch.py
import pytest
from edu_cloud.modules.grading.prompts import get_prompt, render_prompt, get_prompt_config


def test_render_prompt_replaces_variables():
    template = "满分{{fullScore}}分\n细则：{{rubric}}"
    result = render_prompt(template, {"fullScore": "12", "rubric": "test"})
    assert result == "满分12分\n细则：test"


def test_render_prompt_preserves_unknown():
    result = render_prompt("{{known}} and {{unknown}}", {"known": "yes"})
    assert result == "yes and {{unknown}}"


def test_get_prompt_biology_grading():
    prompt = get_prompt("biology", "GRADING", "senior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt
    assert "{{rubric}}" in prompt


def test_get_prompt_biology_rubric_generation():
    prompt = get_prompt("biology", "RUBRIC_GENERATION", "senior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt


def test_get_prompt_unknown_subject():
    prompt = get_prompt("underwater_basket_weaving", "GRADING", "senior")
    assert prompt is None


def test_get_prompt_config():
    config = get_prompt_config("biology", "GRADING", "senior")
    assert config is not None
    assert "temperature" in config
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_prompt_dispatch.py -v`

- [ ] **Step 3: Create prompts/base.py with shared constants**

```python
# src/edu_cloud/modules/grading/prompts/base.py
"""Shared prompt constants and output schemas."""

GRADING_JSON_SCHEMA = """{
  "score": 总分,
  "llmRecognizedText": "识别的学生答案原文",
  "details": [
    {
      "subQuestion": "(1)",
      "score": 小问得分,
      "fullScore": 小问满分,
      "blanks": [
        {
          "index": 1,
          "answer": "学生答案",
          "score": 得分,
          "fullScore": 满分,
          "correct": true/false,
          "reason": "说明满足/不满足judgingRules中的哪些条件"
        }
      ]
    }
  ],
  "deductions": ["扣分点"],
  "comment": "总评"
}"""

FATAL_RULES = """【⚠️ 致命规则】

1. **禁止幻觉**：空白/未作答 → answer="（未作答）", score=0

2. **score必须与reason一致**：
   - reason说"满足满分条件" → score=满分
   - reason说"命中典型错误" → score=0
   - 【严禁】reason和score矛盾！

3. **分数硬性约束**：
   - blank.score ≤ blank.fullScore
   - subQuestion.score = 该小问所有blank.score之和
   - 总score = 所有subQuestion.score之和

4. **reason必须具体**：
   - ✓ "满足judgingRules中'xxx'的满分条件"
   - ✗ "答案正确"

【生成顺序】先根据judgingRules写reason，再填score！"""

GRADING_METHOD_BASE = """对每个填空：
1. **理解语境**：先看context，理解这道题的背景和答案逻辑
2. **语义判断**：用judgingRules中的满分条件判断学生答案是否满足语义要求（不要求措辞一致）
3. **检查陷阱**：用judgingRules中的典型错误/排除规则排除看起来对但实际错的答案
4. **部分分判定**：满分条件不完全满足时，参考judgingRules中的部分分条件"""

OCR_PROMPT_BASE = """请准确识别图片中学生的手写答案。

要求：
1. 逐空识别，保持原文（包括错字、符号）
2. 空白未作答标记为"（未作答）"
3. 无法辨识标记为"（无法辨识）"
4. 直接返回纯 JSON（禁止 markdown 代码块）

【输出格式】
{
  "blanks": [
    {"blankNo": "1-1", "subQ": "(1)", "text": "识别的答案文字"}
  ]
}"""

OCR_STRUCTURED_PROMPT_BASE = """请准确识别图片中学生的手写答案，并按评分细则中的空号顺序输出。

【评分细则结构】
{{rubricStructure}}

要求：
1. 按 blankNo 顺序逐空识别
2. 保持原文（包括错字、符号）
3. 空白未作答标记为"（未作答）"
4. 无法辨识标记为"（无法辨识）"
5. 直接返回纯 JSON

【输出格式】
{
  "blanks": [
    {"blankNo": "1-1", "subQ": "(1)", "text": "识别的答案文字"}
  ]
}"""
```

- [ ] **Step 4: Create prompts/__init__.py with dispatcher**

```python
# src/edu_cloud/modules/grading/prompts/__init__.py
"""Subject-specific prompt dispatch system.

Usage:
    from edu_cloud.modules.grading.prompts import get_prompt, render_prompt
    template = get_prompt("biology", "GRADING", "senior")
    prompt = render_prompt(template, {"fullScore": "12", "rubric": rubric_text})
"""
import re
import importlib
import logging

logger = logging.getLogger(__name__)

_SUBJECTS = {
    "biology", "math", "chinese", "physics", "chemistry",
    "english", "politics", "history", "geography",
}

_cache: dict[str, dict] = {}


def _load_subject(subject: str, level: str = "senior") -> dict | None:
    key = f"{level}/{subject}"
    if key in _cache:
        return _cache[key]

    try:
        mod = importlib.import_module(f".{subject}", package=__name__)
    except ModuleNotFoundError:
        logger.warning("prompt module not found: %s", key)
        _cache[key] = None
        return None

    data = {
        "name": getattr(mod, "NAME", subject),
        "level": getattr(mod, "LEVEL", level),
        "role": getattr(mod, "ROLE", f"{subject}阅卷专家"),
    }
    for attr in dir(mod):
        if attr.isupper() and not attr.startswith("_"):
            data[attr] = getattr(mod, attr)

    _cache[key] = data
    return data


def get_prompt(subject: str, prompt_type: str, level: str = "senior") -> str | None:
    mod = _load_subject(subject, level)
    if mod is None:
        return None
    return mod.get(prompt_type)


def get_prompt_config(subject: str, prompt_type: str, level: str = "senior") -> dict | None:
    mod = _load_subject(subject, level)
    if mod is None:
        return None
    return mod.get(f"{prompt_type}_CONFIG")


def render_prompt(template: str, variables: dict) -> str:
    if not template:
        return ""
    return re.sub(
        r"\{\{(\w+)\}\}",
        lambda m: str(variables.get(m.group(1), m.group(0))),
        template,
    )
```

- [ ] **Step 5: Update old prompts.py to re-export from package**

Add at the top of `src/edu_cloud/modules/grading/prompts.py`:

```python
# Re-export new dispatch API for gradual migration
from edu_cloud.modules.grading.prompts import get_prompt, render_prompt, get_prompt_config  # noqa: F401
```

Note: The old `build_rubric_generation_prompt` and `build_grading_prompt` stay for backward compat until Task 6 replaces them.

**Problem:** `prompts.py` and `prompts/` package conflict (a file and directory can't share the same name in Python). Rename the old file first:

```bash
cd ~/projects/edu-cloud/src/edu_cloud/modules/grading
mv prompts.py prompts_legacy.py
```

Then update all imports of the old module:
- `llm_client.py`: `from edu_cloud.modules.grading.prompts_legacy import build_grading_prompt, build_rubric_generation_prompt`
- `router.py:94`: `from edu_cloud.modules.grading.prompts_legacy import build_rubric_generation_prompt`

- [ ] **Step 6: Run tests**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_prompt_dispatch.py -v`
Expected: 6 PASS (will fail until Task 3 creates biology.py)

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/grading/prompts/ src/edu_cloud/modules/grading/prompts_legacy.py
git commit -m "feat(grading): add prompt dispatcher with subject-specific template rendering"
```

---

### Task 3: Biology Subject Prompts (First Subject)

**Files:**
- Create: `src/edu_cloud/modules/grading/prompts/biology.py`

- [ ] **Step 1: Write biology.py with all 4 prompt types**

Port from `~/projects/zhixue-server-git/src/config/prompts/senior/biology.js`. The file contains: NAME, LEVEL, ROLE, RUBRIC_GENERATION, RUBRIC_GENERATION_CONFIG, GRADING, GRADING_CONFIG, GRADING_TEXT, GRADING_TEXT_CONFIG, OCR, OCR_CONFIG, OCR_STRUCTURED, OCR_STRUCTURED_CONFIG.

```python
# src/edu_cloud/modules/grading/prompts/biology.py
"""Biology (生物) subject prompts — ported from zhixue-server senior/biology.js."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE

NAME = "生物"
LEVEL = "senior"
ROLE = "高中生物阅卷专家"

RUBRIC_GENERATION = """你是高中生物阅卷专家，负责生成AI可执行的评分细则。

**核心原则**：评分LLM看不到原题图片，你生成的细则必须包含所有评分所需的上下文信息。

{{imageDescription}}
{{questionSection}}
{{answerSection}}

【满分】{{fullScore}}分

---

## ⚠️ 铁律（违反则输出无效）

1. **分值必须遵守原文标注** - 原文"每空2分"→每空score=2
2. **blankNo必须按顺序递增** - 格式：小问号-空号（如1-1, 1-2, 2-1）
3. **总分验算** - 所有score之和 = {{fullScore}}分
4. **无灰色地带** - 细则必须覆盖所有可能的学生答案类型

---

## 输出格式

请直接输出JSON对象 {"rubricItems": [...]}，不要包含markdown代码块标记。

每个 rubricItem 包含：
- subQ: 小问编号如"(1)"
- blankNo: 空号如"1-1"
- score: 该空分值
- title: 简短标题
- standardAnswer: 标准答案
- equivalentAnswers: 等效答案数组
- context: 【考查点】+【题目情境】+【推理链】的合并描述（务必详尽，评分LLM只看这个理解题目）
- judgingRules: 满分条件+部分分条件+典型错误+排除规则的合并描述
- scoringRules: [{"condition": "条件", "score": 分值}]
- exclusionRules: [{"pattern": "错误模式", "reason": "排除原因"}]
- typicalWrongAnswers: 常见错误答案数组"""

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中生物阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 生物学科专用】

""" + GRADING_METHOD_BASE + """
   - 特别注意：生物学名词的书写错误（如"叶绿素"写成"叶绿体"）
   - 特别注意：因果关系的方向性（A导致B vs B导致A）
   - 特别注意：定量描述不能用定性描述替代
5. **生物学科等价表述**：意思正确即可，不要求教科书原文

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中生物阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

---

【评分方法 - 生物学科专用】

""" + GRADING_METHOD_BASE + """
   - 生物学名词拼写错误直接扣分
   - 因果关系方向性必须正确
   - 等价表述可给分（意思对即可）

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_TEXT_CONFIG = {"temperature": 0, "max_tokens": 32768}

OCR = OCR_PROMPT_BASE
OCR_CONFIG = {"temperature": 0, "max_tokens": 16384}

OCR_STRUCTURED = OCR_STRUCTURED_PROMPT_BASE
OCR_STRUCTURED_CONFIG = {"temperature": 0, "max_tokens": 16384}

- [ ] **Step 2: Re-run dispatch tests**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_prompt_dispatch.py -v`
Expected: 6 PASS

- [ ] **Step 3: Commit**

```bash
git add src/edu_cloud/modules/grading/prompts/biology.py src/edu_cloud/modules/grading/prompts/base.py
git commit -m "feat(grading): add biology subject prompts (rubric/grading/ocr)"
```

---

### Task 4: Rubric Formatter

**Files:**
- Create: `src/edu_cloud/modules/grading/rubric_formatter.py`
- Create: `tests/test_services_exam/test_rubric_formatter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services_exam/test_rubric_formatter.py
from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading


def test_basic_format():
    items = [
        {"blankNo": "1-1", "score": 2, "standardAnswer": "动物细胞",
         "context": "图中有中心体无细胞壁", "judgingRules": "满分：答出动物细胞"},
    ]
    result = format_rubric_for_grading(items)
    assert "【第1-1空】（2分）" in result
    assert "标准答案：动物细胞" in result
    assert "背景与逻辑：图中有中心体无细胞壁" in result
    assert "判分规则：满分：答出动物细胞" in result


def test_fallback_answer_field():
    items = [{"blankNo": "1", "score": 3, "answer": "fallback answer"}]
    result = format_rubric_for_grading(items)
    assert "标准答案：fallback answer" in result


def test_multiple_items_separated():
    items = [
        {"blankNo": "1-1", "score": 2, "standardAnswer": "A"},
        {"blankNo": "1-2", "score": 3, "standardAnswer": "B"},
    ]
    result = format_rubric_for_grading(items)
    assert "---" in result
    assert "【第1-1空】" in result
    assert "【第1-2空】" in result


def test_empty_list():
    assert format_rubric_for_grading([]) == ""
    assert format_rubric_for_grading(None) == ""
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement rubric_formatter.py**

```python
# src/edu_cloud/modules/grading/rubric_formatter.py
"""Format rubric criteria items into text for LLM grading prompts.

Ported from zhixue-server rubricFormatter.js.
"""


def format_rubric_for_grading(items: list[dict] | None) -> str:
    if not items:
        return ""

    parts = []
    for item in items:
        blank_no = item.get("blankNo", "?")
        score = item.get("score", 0)
        answer = item.get("standardAnswer") or item.get("answer", "")

        text = f"【第{blank_no}空】（{score}分）\n"
        text += f"标准答案：{answer}\n"

        context = item.get("context", "")
        if context:
            text += f"背景与逻辑：{context}\n"

        rules = item.get("judgingRules", "")
        if rules:
            text += f"判分规则：{rules}\n"

        parts.append(text)

    return "\n---\n".join(parts)
```

- [ ] **Step 4: Run tests**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_rubric_formatter.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/grading/rubric_formatter.py tests/test_services_exam/test_rubric_formatter.py
git commit -m "feat(grading): add rubric formatter for LLM grading text"
```

---

### Task 5: LLM Client — Add extract_text() and grade_text()

**Files:**
- Modify: `src/edu_cloud/modules/grading/llm_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services_exam/test_llm_client_new.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from edu_cloud.modules.grading.llm_client import LLMClient


@pytest.fixture
def client():
    return LLMClient(
        api_url="http://fake:8100",
        api_key="test-key",
        model="test-model",
        timeout=10,
        max_retries=1,
    )


@pytest.mark.asyncio
async def test_grade_accepts_multiple_images(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"score": 5, "comment": "ok", "confidence": 0.9}'}}]
    }
    client._http.post = AsyncMock(return_value=mock_resp)

    result = await client.grade(
        images_b64=["base64img1", "base64img2"],
        rubric={"criteria": []},
        question={"name": "1", "max_score": 10},
    )
    assert result.score == 5
    payload = client._http.post.call_args[1]["json"]
    user_content = payload["messages"][-1]["content"]
    image_parts = [p for p in user_content if p.get("type") == "image_url"]
    assert len(image_parts) == 2


@pytest.mark.asyncio
async def test_extract_text(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"blanks": [{"blankNo": "1-1", "subQ": "(1)", "text": "hello"}]}'}}]
    }
    client._http.post = AsyncMock(return_value=mock_resp)

    result = await client.extract_text(
        images_b64=["base64img"],
        prompt="OCR prompt here",
    )
    assert len(result) == 1
    assert result[0]["text"] == "hello"


@pytest.mark.asyncio
async def test_grade_text(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"score": 8, "comment": "good", "confidence": 0.95}'}}]
    }
    client._http.post = AsyncMock(return_value=mock_resp)

    result = await client.grade_text(
        prompt="Grade this text",
        max_score=10,
    )
    assert result.score == 8
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Modify llm_client.py**

Add to LLMClient class (after existing `grade` method):

1. Change `grade()` signature: `image_b64: str` → `images_b64: str | list[str]` (multi-image support)
2. Add `extract_text()` method
3. Add `grade_text()` method
4. Use `json_parser.extract_json()` instead of manual JSON parsing in all methods

Key changes to `grade()`:
```python
async def grade(
    self,
    images_b64: str | list[str],  # Changed: accept single or list
    rubric: dict,
    question: dict,
    question_type: str | None = None,
) -> GradeResponse:
    from edu_cloud.modules.grading.prompts_legacy import build_grading_prompt
    from edu_cloud.modules.grading.json_parser import extract_json

    messages = build_grading_prompt(rubric, question, question_type)

    # Build multimodal content with multiple images
    if isinstance(images_b64, str):
        images_b64 = [images_b64]

    user_msg = messages[-1]
    content_parts = [{"type": "text", "text": user_msg["content"]}]
    for img in images_b64:
        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
    user_msg["content"] = content_parts
    # ... rest of method uses extract_json() instead of manual parsing
```

New methods:
```python
async def extract_text(
    self,
    images_b64: list[str],
    prompt: str,
) -> list[dict]:
    """OCR: extract text from answer images. Returns list of blanks."""
    from edu_cloud.modules.grading.json_parser import extract_json

    content_parts = []
    for img in images_b64:
        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
    content_parts.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content_parts}]
    payload = {"model": self.model, "messages": messages, "max_tokens": 16384, "temperature": 0}
    # ... retry loop similar to grade(), parse blanks from response
    # Returns: [{"blankNo": "1-1", "subQ": "(1)", "text": "..."}]

async def grade_text(
    self,
    prompt: str,
    max_score: float,
) -> GradeResponse:
    """Text-based grading (after OCR). No images, pure text prompt."""
    from edu_cloud.modules.grading.json_parser import extract_json

    messages = [{"role": "user", "content": prompt}]
    payload = {"model": self.model, "messages": messages, "max_tokens": 32768, "temperature": 0}
    # ... retry loop, parse score/feedback/confidence from response
```

- [ ] **Step 4: Run tests**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_llm_client_new.py -v`
Expected: 3 PASS

- [ ] **Step 5: Run existing tests to verify backward compat**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/ -k grading -v`
Expected: All existing grading tests still PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/grading/llm_client.py tests/test_services_exam/test_llm_client_new.py
git commit -m "feat(grading): add extract_text, grade_text, multi-image to LLM client"
```

---

### Task 6: Update Rubric Validation for 6-Field Schema

**Files:**
- Modify: `src/edu_cloud/modules/grading/router.py:45-81` (_validate_criteria)

- [ ] **Step 1: Write test for new schema**

```python
# tests/test_services_exam/test_rubric_validation.py
import pytest
from edu_cloud.modules.grading.router import _validate_criteria


def test_valid_6_field_criteria():
    criteria = [
        {"blankNo": "1-1", "score": 5, "standardAnswer": "A", "context": "ctx", "judgingRules": "rules"},
        {"blankNo": "1-2", "score": 5, "standardAnswer": "B", "context": "ctx", "judgingRules": "rules"},
    ]
    _validate_criteria(criteria, 10.0)  # Should not raise


def test_backward_compat_answer_field():
    criteria = [{"blankNo": "1", "score": 10, "answer": "old format"}]
    _validate_criteria(criteria, 10.0)  # Should not raise (answer still accepted)


def test_missing_answer_and_standard_answer():
    criteria = [{"blankNo": "1", "score": 10}]
    with pytest.raises(Exception):
        _validate_criteria(criteria, 10.0)
```

- [ ] **Step 2: Update _validate_criteria**

Change line 69-71: accept either `answer` or `standardAnswer`:
```python
answer = c.get("standardAnswer") or c.get("answer")
if not answer or not isinstance(answer, str) or not answer.strip():
    raise HTTPException(422, f"criteria[{i}] missing standardAnswer or answer")
```

- [ ] **Step 3: Run tests**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_rubric_validation.py tests/test_api_exam/test_grading_rubric.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/modules/grading/router.py tests/test_services_exam/test_rubric_validation.py
git commit -m "feat(grading): accept 6-field rubric schema (standardAnswer+context+judgingRules)"
```

---

### Task 7: Two-Step Worker Pipeline (OCR → Grade Text)

**Files:**
- Modify: `src/edu_cloud/workers/grading.py`

- [ ] **Step 1: Write test for two-step flow**

```python
# tests/test_workers/test_two_step_grading.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from edu_cloud.modules.grading.llm_client import GradeResponse


@pytest.mark.asyncio
async def test_grade_single_two_step():
    from edu_cloud.workers.grading import _grade_single

    mock_llm = MagicMock()
    # Step 1: OCR returns blanks
    mock_llm.extract_text = AsyncMock(return_value=[
        {"blankNo": "1-1", "subQ": "(1)", "text": "动物细胞"},
    ])
    # Step 2: gradeText returns score
    mock_llm.grade_text = AsyncMock(return_value=GradeResponse(
        score=2, max_score=2, feedback="correct", confidence=0.95, raw_content='{"score":2}'
    ))

    ad = {
        "answer_id": "a1", "question_id": "q1",
        "question_name": "6", "question_max_score": 2,
        "image_path": "/tmp/fake.png", "question_type": "essay",
        "subject_code": "biology",
    }
    rubrics = {"q1": [{"blankNo": "1-1", "score": 2, "standardAnswer": "动物细胞", "context": "ctx", "judgingRules": "rules"}]}

    with patch("edu_cloud.workers.grading._read_image_b64", return_value="fakebase64"):
        result, error = await _grade_single(mock_llm, ad, rubrics)

    assert error is None
    assert result["score"] == 2
    mock_llm.extract_text.assert_called_once()
    mock_llm.grade_text.assert_called_once()
```

- [ ] **Step 2: Modify _grade_single for two-step**

```python
async def _grade_single(
    llm,
    ad: dict,
    rubrics_by_question: dict,
) -> tuple[dict | None, dict | None]:
    answer_id = ad["answer_id"]
    question_id = ad["question_id"]

    rubric_criteria = rubrics_by_question.get(question_id)
    if rubric_criteria is None:
        return None, {"answer_id": answer_id, "error": f"No rubric for question {question_id}"}

    try:
        image_b64 = await _read_image_b64(ad["image_path"])

        # Blank detection: skip LLM for empty images (< 5KB likely blank)
        if len(image_b64) < 6800:  # ~5KB base64
            return {
                "answer_id": answer_id, "question_id": question_id,
                "score": 0, "max_score": ad["question_max_score"],
                "feedback": "空白卷", "confidence": 1.0, "raw_content": "",
            }, None

        subject = ad.get("subject_code", "")
        from edu_cloud.modules.grading.prompts import get_prompt, render_prompt
        from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading

        rubric_text = format_rubric_for_grading(rubric_criteria)
        full_score = str(ad["question_max_score"])

        # Step 1: OCR
        ocr_prompt = get_prompt(subject, "OCR_STRUCTURED", "senior") or get_prompt(subject, "OCR", "senior")
        if ocr_prompt:
            structure = "\n".join(f"- {c.get('blankNo', '?')}: {c.get('subQ', '')}" for c in rubric_criteria)
            ocr_prompt = render_prompt(ocr_prompt, {"rubricStructure": structure})
        else:
            from edu_cloud.modules.grading.prompts.base import OCR_PROMPT_BASE
            ocr_prompt = OCR_PROMPT_BASE

        blanks = await llm.extract_text(images_b64=[image_b64], prompt=ocr_prompt)
        extracted_text = "\n".join(f"{b.get('blankNo', '?')}: {b.get('text', '')}" for b in blanks)

        # Step 2: Grade text
        grading_prompt_tpl = get_prompt(subject, "GRADING_TEXT", "senior")
        if grading_prompt_tpl:
            grading_prompt = render_prompt(grading_prompt_tpl, {
                "fullScore": full_score,
                "rubric": rubric_text,
                "extractedText": extracted_text,
            })
        else:
            # Fallback to legacy single-step
            grade_result = await llm.grade(
                images_b64=image_b64,
                rubric={"criteria": rubric_criteria},
                question={"name": ad["question_name"], "max_score": ad["question_max_score"]},
                question_type=ad.get("question_type"),
            )
            return {
                "answer_id": answer_id, "question_id": question_id,
                "score": grade_result.score, "max_score": grade_result.max_score,
                "feedback": grade_result.feedback, "confidence": grade_result.confidence,
                "raw_content": grade_result.raw_content,
            }, None

        grade_result = await llm.grade_text(prompt=grading_prompt, max_score=ad["question_max_score"])

        return {
            "answer_id": answer_id, "question_id": question_id,
            "score": grade_result.score, "max_score": grade_result.max_score,
            "feedback": grade_result.feedback, "confidence": grade_result.confidence,
            "raw_content": grade_result.raw_content,
        }, None

    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        logger.warning("grading_task: answer=%s FAILED: %s", answer_id, e)
        return None, {"answer_id": answer_id, "error": str(e)}
```

- [ ] **Step 3: Add Semaphore to process_grading_task**

In `process_grading_task`, wrap the batch gather with a semaphore:

```python
# At module level
import asyncio
_grading_semaphore = asyncio.Semaphore(20)

async def _grade_with_semaphore(llm, ad, rubrics):
    async with _grading_semaphore:
        return await _grade_single(llm, ad, rubrics)
```

Replace `coros = [_grade_single(llm, ad, rubrics_by_question) for ad in batch]` with:
```python
coros = [_grade_with_semaphore(llm, ad, rubrics_by_question) for ad in batch]
```

- [ ] **Step 4: Add subject_code to answer_data**

In `process_grading_task`, where `answer_data` is built (around line 153), add:
```python
# Need subject code for prompt dispatch
subject_result = await db.execute(select(Subject).where(Subject.id == task.subject_id))
subject_row = subject_result.scalar_one()
subject_code = subject_row.code if hasattr(subject_row, 'code') else subject_row.name
```

Then in the answer_data loop:
```python
answer_data.append({
    ...existing fields...,
    "subject_code": subject_code,
})
```

- [ ] **Step 5: Run tests**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_workers/test_two_step_grading.py tests/test_workers/test_grading_worker.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/workers/grading.py tests/test_workers/test_two_step_grading.py
git commit -m "feat(grading): two-step OCR→gradeText pipeline + semaphore + blank detection"
```

---

### Task 8: Math & Chinese Subject Prompts

**Files:**
- Create: `src/edu_cloud/modules/grading/prompts/math.py`
- Create: `src/edu_cloud/modules/grading/prompts/chinese.py`

- [ ] **Step 1: Create math.py**

Port from `~/projects/zhixue-server-git/src/config/prompts/senior/math.js`. Key differences from biology:
- Math equivalence rules (分数/小数/根式)
- 区间开闭、坐标顺序
- 解答题过程分

```python
# src/edu_cloud/modules/grading/prompts/math.py
"""Math (数学) subject prompts."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE

NAME = "数学"
LEVEL = "senior"
ROLE = "高中数学阅卷专家"

# [Port RUBRIC_GENERATION, GRADING, GRADING_TEXT from math.js]
# Include math-specific rules: equivalence (1/2=0.5), interval notation, process marks
```

- [ ] **Step 2: Create chinese.py**

Port from `~/projects/zhixue-server-git/src/config/prompts/senior/chinese.js`. Key differences:
- 默写题零容忍（错字漏字0分）
- 翻译题关键词+句意
- 阅读理解重语义轻形式

- [ ] **Step 3: Test all 3 subjects load**

```python
# Add to test_prompt_dispatch.py
def test_get_prompt_math_grading():
    prompt = get_prompt("math", "GRADING", "senior")
    assert prompt is not None
    assert "等价" in prompt or "equivalen" in prompt.lower()

def test_get_prompt_chinese_grading():
    prompt = get_prompt("chinese", "GRADING", "senior")
    assert prompt is not None
    assert "默写" in prompt
```

- [ ] **Step 4: Run all prompt tests**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_prompt_dispatch.py -v`
Expected: 8+ PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/grading/prompts/math.py src/edu_cloud/modules/grading/prompts/chinese.py
git commit -m "feat(grading): add math and chinese subject prompts"
```

---

## Phase 2: Quality & Coverage (4 Tasks)

### Task 9: Remaining Science Subjects (Physics, Chemistry)

Create `physics.py` and `chemistry.py` following biology.py pattern, with subject-specific rules (物理单位/公式, 化学方程式配平/化学式书写).

### Task 10: Remaining Humanities Subjects (English, Politics, History, Geography)

Create 4 subject files. English has unique bilingual grading rules. Humanities share "要点采分" pattern.

### Task 11: Multi-LLM Provider Support

Extend `LLMClient` to support provider fallback chains using edu-cloud's existing `llm_slots` table.

### Task 12: OCR Validation & Garbage Detection

Create `ocr_validator.py` with blank detection, English commentary filtering, and truncation recovery.

---

## Phase 3: Advanced (3 Tasks)

### Task 13: Junior Level Prompt Inheritance

Create `junior/` variants that inherit from senior and override NAME/LEVEL/ROLE.

### Task 14: Visual Confusion Correction (CORRECTION prompt)

Add CORRECTION prompt type for OCR error recovery (e.g., "叶" vs "十").

### Task 15: Prompt Hot-Update via DB

Allow schools to customize prompts via `school_settings` table (runtime override without code deploy).

---

## semantic_regression

Invariants that must not be violated during migration:

- `ORC-001`: Confirmed GradingResults must never be re-graded by worker
- `ORC-002`: Subject-level tasks must include ALL subjective questions
- `AGP-001`: Question-level tasks must validate question belongs to subject AND is subjective
- `F007`: GradingTask must be cleaned up if Redis enqueue fails
- `SUM-CHECK`: Criteria scores sum must equal question max_score (1e-6 tolerance)
