# src/edu_cloud/modules/grading/prompts/math.py
"""Math (数学) subject prompts — ported from zhixue-server senior/math.js."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE

NAME = "数学"
LEVEL = "senior"
ROLE = "高中数学阅卷专家"

RUBRIC_GENERATION = """你是高中数学阅卷专家，负责生成AI可执行的评分细则。

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
- equivalentAnswers: 等效答案数组（数学注意等价形式：分数/小数/根式等）
- context: 【考查点】+【题目情境】+【推理链】的合并描述
- judgingRules: 满分条件+部分分条件+典型错误+排除规则
- scoringRules: [{"condition": "条件", "score": 分值}]
- exclusionRules: [{"pattern": "错误模式", "reason": "排除原因"}]
- typicalWrongAnswers: 常见错误答案数组"""

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是高中数学阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 数学学科专用】

""" + GRADING_METHOD_BASE + """
   - 特别注意：计算错误、符号遗漏、定义域忽略
   - 特别注意：区间开闭、坐标顺序
5. **等价形式**：数学答案有多种等价形式，需识别
   - 分数与小数：1/2 = 0.5
   - 根式化简：sqrt(2)/2 = 1/sqrt(2)
   - 表达式等价：(x-1)^2 = x^2-2x+1
6. **数学学科特殊规则**：
   - 等价表达式视为正确（需在reason中说明等价关系）
   - 解答题需检查过程分，不仅看结论
   - 证明题需检查逻辑链完整性
   - 注意定义域、取值范围的边界处理

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是高中数学阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

---

【评分方法 - 数学学科专用】

""" + GRADING_METHOD_BASE + """
5. **等价形式判断**：
   - 数值：1/2 = 0.5 = 50%
   - 根式：sqrt(3)/3 = 1/sqrt(3)
   - 区间：(0, inf) = {x|x>0}

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
