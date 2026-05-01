# src/edu_cloud/modules/grading/prompts/biology.py
"""Biology (生物) subject prompts — ported from zhixue-server senior/biology.js."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, CORRECTION_PROMPT_BASE, build_rubric_generation

NAME = "生物"
LEVEL = "senior"
ROLE = "高中生物阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(ROLE)

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

CORRECTION = CORRECTION_PROMPT_BASE
CORRECTION_CONFIG = {"temperature": 0, "max_tokens": 16384}
