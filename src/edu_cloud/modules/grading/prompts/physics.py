# src/edu_cloud/modules/grading/prompts/physics.py
"""Physics (物理) subject prompts — ported from zhixue-server senior/physics.js."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, build_rubric_generation

NAME = "物理"
LEVEL = "senior"
ROLE = "高中物理阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(ROLE, "物理注意单位换算等价：km/h与m/s等")

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中物理阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 物理学科专用】

""" + GRADING_METHOD_BASE + """
   - 单位是否正确、是否漏写单位
   - 矢量是否标明方向（正负号或文字说明）
   - 有效数字是否符合要求
5. **物理学科特殊规则**：
   - 物理量必须带单位（除无量纲量或比值）
   - 矢量必须标明方向
   - 有效数字必须符合题目要求
   - 实验读数必须估读到最小分度的下一位
   - 作图题检查坐标轴标注、数据点、拟合线

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中物理阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

---

【评分方法 - 物理学科专用】

""" + GRADING_METHOD_BASE + """
   - 单位是否正确、是否漏写单位
   - 矢量是否标明方向
   - 有效数字是否符合题目要求

**reason示例**：
   - ✓ "漏写单位m/s，扣1分"
   - ✓ "方向未标明正负，应注明向右为正"
   - ✓ "有效数字应保留3位，多保留了1位"
   - ✓ "数值与标准答案9.8一致，满分"

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
