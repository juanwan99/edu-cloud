# src/edu_cloud/modules/grading/prompts/chemistry.py
"""Chemistry (化学) subject prompts — ported from zhixue-server senior/chemistry.js."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, build_rubric_generation

NAME = "化学"
LEVEL = "senior"
ROLE = "高中化学阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(ROLE, "化学注意方程式不同写法等价")

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中化学阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 化学学科专用】

""" + GRADING_METHOD_BASE + """
   - 化学方程式配平、电荷守恒
   - 化学式书写规范（下标、上标）
5. **化学学科特殊规则**：
   - 化学方程式必须检查配平
   - 离子方程式必须检查电荷守恒
   - 有机结构简式要检查碳骨架和官能团
   - 数值答案注意单位和有效数字

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中化学阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

---

【评分方法 - 化学学科专用】

""" + GRADING_METHOD_BASE + """
   - 化学方程式必须检查配平
   - 离子方程式必须检查电荷守恒
   - 有机结构简式检查碳骨架和官能团

**reason示例**：
   - ✓ "方程式未配平，H₂O系数应为2"
   - ✓ "离子方程电荷不守恒，左3+右2+"
   - ✓ "官能团-OH写成-O，结构简式错误"
   - ✓ "化学式与标准答案Na₂CO₃一致，满分"

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
