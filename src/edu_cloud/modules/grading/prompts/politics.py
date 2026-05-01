# src/edu_cloud/modules/grading/prompts/politics.py
"""Politics (政治) subject prompts — principle+methodology scoring with material integration."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, build_rubric_generation

NAME = "政治"
LEVEL = "senior"
ROLE = "高中政治阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(ROLE, "政治学科注意教材不同版本的表述差异")

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中政治阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 政治学科专用】

""" + GRADING_METHOD_BASE + """
   - 特别注意：原理+方法论必须配套，只答一个视为不完整
   - 特别注意：关键概念不能混淆（如唯物论与辩证法、经济基础与上层建筑）
   - 特别注意：主体不能混淆（政府/企业/个人/市场各有不同职能）
5. **政治学科要点采分规则**：
   - 原理+方法论 = 完整得分；只有原理或只有方法论 → 部分分
   - 材料结合度：纯抄原理无材料分析 → 扣材料分
   - 关键术语必须准确，概念混淆（如混淆唯物论与辩证法）→ 该要点0分
   - 主体判断：题目问政府职能却答企业行为 → 该要点0分
6. **等价表述**：意思正确且术语准确即可，不要求原文照搬

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中政治阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

---

【评分方法 - 政治学科专用】

""" + GRADING_METHOD_BASE + """
   - 原理+方法论配套才完整，只有一个给部分分
   - 纯抄原理无材料结合 → 扣材料分
   - 关键概念混淆 → 该要点0分
   - 主体混淆（政府/企业/个人） → 该要点0分
   - 等价表述可给分（术语准确即可）

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
