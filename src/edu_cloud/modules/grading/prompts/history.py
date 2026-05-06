# src/edu_cloud/modules/grading/prompts/history.py
"""History (历史) subject prompts — factual accuracy and causal reasoning emphasis."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, build_rubric_generation

NAME = "历史"
LEVEL = "senior"
ROLE = "高中历史阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(ROLE, "历史学科注意同一事件的不同表述")

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中历史阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 历史学科专用】

""" + GRADING_METHOD_BASE + """
   - 特别注意：史实准确性优先——时间、人物、事件必须准确，张冠李戴直接扣分
   - 特别注意：因果关系必须正确，不能颠倒因果
   - 特别注意：材料分析题需紧扣材料内容+时代背景
5. **历史学科特殊规则**：
   - 史实错误（时间、人物、事件搞混）→ 该要点0分
   - 因果关系颠倒 → 该要点0分
   - 材料分析题：脱离材料泛泛而谈 → 扣材料分
   - 同义表述认可：用不同措辞表达相同史实观点可给分
   - 论述题需史论结合，纯论无史或纯史无论均扣分

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中历史阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

---

【评分方法 - 历史学科专用】

""" + GRADING_METHOD_BASE + """
   - 史实必须准确（时间、人物、事件），错误直接扣分
   - 因果关系不能颠倒
   - 材料分析需紧扣材料+时代背景
   - 同义表述可给分（史实观点正确即可）
   - 论述题需史论结合

**reason示例**：
   - ✓ "时间错：鸦片战争应为1840年非1842年"
   - ✓ "因果颠倒：工业革命是原因非结果"
   - ✓ "脱离材料泛泛而谈，扣材料分"
   - ✓ "史论结合完整，观点正确，满分"

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
