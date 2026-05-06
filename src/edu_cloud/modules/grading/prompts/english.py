# src/edu_cloud/modules/grading/prompts/english.py
"""English (英语) subject prompts — bilingual grading with spelling & grammar checks."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, build_rubric_generation

NAME = "英语"
LEVEL = "senior"
ROLE = "高中英语阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(ROLE, "英语注意同义词、近义表达")

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中英语阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 英语学科专用】

""" + GRADING_METHOD_BASE + """
   - 特别注意：拼写必须100%正确，逐字母核对
   - 特别注意：大小写检查——句首大写、专有名词大写
   - 特别注意：语法检查——时态一致性、主谓一致
5. **英语学科特殊规则**：
   - 填空题拼写错误直接扣分，不接受近似拼写
   - 语法填空需同时满足语法和语义双重要求
   - 短文改错需标注修改位置和修改内容
   - 作文评分需关注结构完整性、语法准确性、词汇多样性
6. **作文评分维度**：
   - 内容完整性：要点是否覆盖
   - 语言准确性：语法、拼写、标点
   - 表达流畅性：句式多样、过渡自然
   - 卷面整洁度：书写清晰可辨

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中英语阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

{{charStats}}

---

【评分方法 - 英语学科专用】

""" + GRADING_METHOD_BASE + """
   - 拼写必须100%正确，逐字母核对
   - 大小写必须正确（句首、专有名词）
   - 语法必须正确（时态、主谓一致、冠词）
   - 作文按结构、语法、词汇多样性综合评分

**reason示例**：
   - ✓ "拼写错：writen应为written，双写t"
   - ✓ "时态错：应用过去式went，写成go"
   - ✓ "大小写错：句首未大写"
   - ✓ "与标准答案'achievement'一致，满分"

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
