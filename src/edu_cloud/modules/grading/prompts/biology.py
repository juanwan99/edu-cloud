# src/edu_cloud/modules/grading/prompts/biology.py
"""Biology (生物) subject prompts — ported from zhixue-server senior/biology.js."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, CORRECTION_PROMPT_BASE, build_rubric_generation

NAME = "生物"
LEVEL = "senior"
ROLE = "高中生物阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(
    ROLE,
    "生物注意概念层级：简称、上位词、日常说法不改变机制时可给满分或部分分；结构/物质/过程混淆不得等价"
)

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中生物阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 生物学科专用】

""" + GRADING_METHOD_BASE + """
   - 特别注意：生物学名词是否混淆不同结构、物质、过程（如"叶绿素"写成"叶绿体"）
   - 特别注意：因果关系的方向性（A导致B vs B导致A）
   - 特别注意：定量描述不能完全用定性描述替代，但可按信息量给部分分
5. **生物学科等价/近似表述**：
   - 不要求教科书原文；简称、上位词、日常说法若不改变考查机制，可给满分或部分分
   - 例："光照"可视作"光照强度"的常见简称；若题目专考变量精确名称，至少按部分分判断
   - 例："能量"相对"光能"较泛，若题目考能量来源/转化方向，可给部分分；若明确考能量类型且缺"光"，不得满分
   - 明显概念混淆（结构当物质、过程当场所、因果倒置）才判0

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
   - 生物学术语需判断是否真正混淆概念；错别字/简称不改变含义时不直接判0
   - 因果关系方向性必须正确，方向错该要点0分
   - 等价或近似表述按信息量给分：完整等值给满分，泛化但相关给部分分，概念混淆给0分

**reason示例**：
   - ✓ "'叶绿体'应为'叶绿素'，名词混淆"
   - ✓ "因果颠倒：应为A导致B，写成B导致A"
   - ✓ "与'有丝分裂'语义一致，满分"
   - ✓ "缺少'ATP'关键概念，给部分分"

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
