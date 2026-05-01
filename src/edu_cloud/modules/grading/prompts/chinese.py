# src/edu_cloud/modules/grading/prompts/chinese.py
"""Chinese (语文) subject prompts — ported from zhixue-server senior/chinese.js."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, CORRECTION_PROMPT_BASE, build_rubric_generation

NAME = "语文"
LEVEL = "senior"
ROLE = "高中语文阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(ROLE)

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中语文阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 语文学科专用】

""" + GRADING_METHOD_BASE + """
   - 语文学科重视**语义理解**，同义表述可视为正确
   - 但默写题必须**字字准确**，不允许同义替换
   - 特别注意：错别字、漏字、偏离主题

---

【语文学科特殊规则】

**默写题评分**：
- 错一字该空0分
- 漏一字该空0分
- 多一字该空0分
- 繁简字均可（繁体正确算对）

**翻译题评分**：
- 按关键词+句意分别给分
- 关键词必须对应，不可笼统带过

**阅读理解评分**：
- 重语义轻形式，意思对即可
- 要点分需明确判断是否答到

**表达规范要求**：
- 语句不通顺可酌情扣分
- 严重偏离主题直接0分

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中语文阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

{{charStats}}

---

【评分方法 - 语文学科专用】

""" + GRADING_METHOD_BASE + """

---

【语文学科特殊规则】

**默写题**：错字、漏字、多字均不得分
**翻译题**：关键词采分+句意采分
**阅读题**：语义相近可给分，但要点必须明确

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

CORRECTION = CORRECTION_PROMPT_BASE
CORRECTION_CONFIG = {"temperature": 0, "max_tokens": 16384}
