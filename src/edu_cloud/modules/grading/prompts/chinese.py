# src/edu_cloud/modules/grading/prompts/chinese.py
"""Chinese (语文) subject prompts — ported from zhixue-server senior/chinese.js."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE

NAME = "语文"
LEVEL = "senior"
ROLE = "高中语文阅卷专家"

RUBRIC_GENERATION = """你是高中语文阅卷专家，负责生成AI可执行的评分细则。

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
- equivalentAnswers: 等效答案数组
- context: 【考查点】+【题目情境】+【推理链】的合并描述
- judgingRules: 满分条件+部分分条件+典型错误+排除规则
- scoringRules: [{"condition": "条件", "score": 分值}]
- exclusionRules: [{"pattern": "错误模式", "reason": "排除原因"}]
- typicalWrongAnswers: 常见错误答案数组"""

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中语文阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 语文学科专用】

""" + GRADING_METHOD_BASE + """
   - 语文学科重视**语义理解**，同义表述可视为正确
   - 但默写题必须**字字准确**，不允许同义替换
   - 特别注意：错别字、漏字、偏离主题

---

【语文学科特殊规则】

**默写题评分**：
- 错一字该空0分
- 漏一字该空0分
- 多一字该空0分
- 繁简字均可（繁体正确算对）

**翻译题评分**：
- 按关键词+句意分别给分
- 关键词必须对应，不可笼统带过

**阅读理解评分**：
- 重语义轻形式，意思对即可
- 要点分需明确判断是否答到

**表达规范要求**：
- 语句不通顺可酌情扣分
- 严重偏离主题直接0分

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中语文阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

---

【评分方法 - 语文学科专用】

""" + GRADING_METHOD_BASE + """

---

【语文学科特殊规则】

**默写题**：错字、漏字、多字均不得分
**翻译题**：关键词采分+句意采分
**阅读题**：语义相近可给分，但要点必须明确

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
