# src/edu_cloud/modules/grading/prompts/english.py
"""English (英语) subject prompts — bilingual grading with spelling & grammar checks."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE

NAME = "英语"
LEVEL = "senior"
ROLE = "高中英语阅卷专家"

RUBRIC_GENERATION = """你是高中英语阅卷专家，负责生成AI可执行的评分细则。

**核心原则**：评分LLM看不到原题图片，你生成的细则必须包含所有评分所需的上下文信息。

{{imageDescription}}
{{questionSection}}
{{answerSection}}

【满分】{{fullScore}}分

---

## ⚠️ 铁律（违反则输出无效）

1. **分值必须遵守原文标注** - 原文"每空2分"→每空score=2
2. **blankNo必须按顺序递增** - 格式：小问号-空号（如1-1, 1-2, 2-1）
3. **总分验算** - 所有score之和 = {{fullScore}}分
4. **无灰色地带** - 细则必须覆盖所有可能的学生答案类型

---

## 输出格式

请直接输出JSON对象 {"rubricItems": [...]}，不要包含markdown代码块标记。

每个 rubricItem 包含：
- subQ: 小问编号如"(1)"
- blankNo: 空号如"1-1"
- score: 该空分值
- title: 简短标题
- standardAnswer: 标准答案
- equivalentAnswers: 等效答案数组（英语注意同义词、近义表达）
- context: 【考查点】+【题目情境】+【推理链】的合并描述（务必详尽，评分LLM只看这个理解题目）
- judgingRules: 满分条件+部分分条件+典型错误+排除规则
- scoringRules: [{"condition": "条件", "score": 分值}]
- exclusionRules: [{"pattern": "错误模式", "reason": "排除原因"}]
- typicalWrongAnswers: 常见错误答案数组"""

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

---

【评分方法 - 英语学科专用】

""" + GRADING_METHOD_BASE + """
   - 拼写必须100%正确，逐字母核对
   - 大小写必须正确（句首、专有名词）
   - 语法必须正确（时态、主谓一致、冠词）
   - 作文按结构、语法、词汇多样性综合评分

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
