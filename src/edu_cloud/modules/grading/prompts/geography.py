# src/edu_cloud/modules/grading/prompts/geography.py
"""Geography (地理) subject prompts — directional accuracy and causal completeness."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, build_rubric_generation

NAME = "地理"
LEVEL = "senior"
ROLE = "高中地理阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(
    ROLE,
    "地理注意空间范围等值的地名别称和同义表述；上位区域/泛化因子只能作为部分分规则，不得放入满分等价答案。审题关键：若填空题干有后缀（如___洋、___带），学生只需填缺失部分，应将省略后缀的答案列入 equivalentAnswers"
)

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中地理阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 地理学科专用】

""" + GRADING_METHOD_BASE + """
   - 特别注意：方位表述必须准确，东西南北不能颠倒
   - 特别注意：地名、区域、尺度是否准确；空间范围等值的简称/别称可给分
   - 特别注意：因果分析按机制完整度给分，答到因素但缺机制不得直接0分
5. **地理学科特殊规则**：
   - 方位错误（东西南北颠倒）→ 该要点0分
   - 地名完全错误或空间范围不一致 → 该要点0分；同一地点别称/简称/行政区规范简称可给分
   - **题干补足**：若 rubric context 声明题干有后缀（如"___洋"），学生只填核心词即视为完整答案
   - 因果分析不完整（只有结果无原因，或只有原因无结果）→ 部分分
   - 只答"气候/地形/交通/市场"等因素词但未展开机制 → 给因素部分分，不得满分
   - 自然地理重原理推导：气候、地形、水文等需说明成因机制
   - 人文地理重要点覆盖：区位因素需逐条列举
   - 等价表述认可：同一地理现象的不同准确描述方式可给分

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
   - 因果分析按"因素+机制+结果"完整度给分，缺机制给部分分
   - 地名需空间范围准确；规范简称/别称可给分，范围错才判0
   - **题干补足判分**：若 rubric 的 context 或 judgingRules 说明题干有后缀（如"___洋"），学生只填核心词（如"印度"）即视为完整答案，以 rubric 声明为准
   - 简称处理：rubric 的 equivalentAnswers 中列出的简称可给满分；未列出的简称按 scoringRules 或语境判断
   - 自然地理重原理，人文地理重要点覆盖
   - 等价表述可给分，但泛化因素词不得直接满分

**reason示例**：
   - ✓ "方位写反，应为'西北'写成'东北'"
   - ✓ "只答结果未分析原因，给部分分"
   - ✓ "地名错：'孟加拉湾'写成'阿拉伯海'"
   - ✓ "与'热带季风气候'一致，满分"

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
