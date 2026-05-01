# src/edu_cloud/modules/grading/prompts/geography.py
"""Geography (地理) subject prompts — directional accuracy and causal completeness."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, build_rubric_generation

NAME = "地理"
LEVEL = "senior"
ROLE = "高中地理阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(ROLE, "地理注意地名别称和同义表述")

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中地理阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 地理学科专用】

""" + GRADING_METHOD_BASE + """
   - 特别注意：方位表述必须准确，东西南北不能颠倒
   - 特别注意：因果分析必须完整，不能只说结果不说原因
   - 特别注意：地名必须正确，错误地名直接扣分
5. **地理学科特殊规则**：
   - 方位错误（东西南北颠倒）→ 该要点0分
   - 地名错误 → 该要点0分
   - 因果分析不完整（只有结果无原因，或只有原因无结果）→ 部分分
   - 自然地理重原理推导：气候、地形、水文等需说明成因机制
   - 人文地理重要点覆盖：区位因素需逐条列举
   - 等价表述认可：同一地理现象的不同描述方式可给分

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中地理阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

---

【评分方法 - 地理学科专用】

""" + GRADING_METHOD_BASE + """
   - 方位表述必须准确（东西南北不能颠倒）
   - 因果分析必须完整（原因+结果）
   - 地名必须正确
   - 自然地理重原理，人文地理重要点
   - 等价表述可给分

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
