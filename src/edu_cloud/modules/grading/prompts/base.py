"""Shared prompt constants and output schemas."""

GRADING_JSON_SCHEMA = """{
  "score": 总分,
  "llmRecognizedText": "识别的学生答案原文",
  "details": [
    {
      "subQuestion": "(1)",
      "score": 小问得分,
      "fullScore": 小问满分,
      "blanks": [
        {
          "index": 1,
          "answer": "学生答案",
          "score": 得分,
          "fullScore": 满分,
          "correct": true/false,
          "reason": "说明满足/不满足judgingRules中的哪些条件"
        }
      ]
    }
  ],
  "deductions": ["扣分点"],
  "comment": "总评"
}"""

FATAL_RULES = """【⚠️ 致命规则】

1. **禁止幻觉**：空白/未作答 → answer="（未作答）", score=0

2. **score必须与reason一致**：
   - reason说"满足满分条件" → score=满分
   - reason说"命中典型错误" → score=0
   - 【严禁】reason和score矛盾！

3. **分数硬性约束**：
   - blank.score ≤ blank.fullScore
   - subQuestion.score = 该小问所有blank.score之和
   - 总score = 所有subQuestion.score之和

4. **reason必须具体**：
   - ✓ "满足judgingRules中'xxx'的满分条件"
   - ✗ "答案正确"

【生成顺序】先根据judgingRules写reason，再填score！"""

GRADING_METHOD_BASE = """对每个填空：
1. **理解语境**：先看context，理解这道题的背景和答案逻辑
2. **语义判断**：用judgingRules中的满分条件判断学生答案是否满足语义要求（不要求措辞一致）
3. **检查陷阱**：用judgingRules中的典型错误/排除规则排除看起来对但实际错的答案
4. **部分分判定**：满分条件不完全满足时，参考judgingRules中的部分分条件"""

OCR_PROMPT_BASE = """请准确识别图片中学生的手写答案。

要求：
1. 逐空识别，保持原文（包括错字、符号）
2. 空白未作答标记为"（未作答）"
3. 无法辨识标记为"（无法辨识）"
4. 直接返回纯 JSON（禁止 markdown 代码块）

【输出格式】
{
  "blanks": [
    {"blankNo": "1-1", "subQ": "(1)", "text": "识别的答案文字"}
  ]
}"""

OCR_STRUCTURED_PROMPT_BASE = """请准确识别图片中学生的手写答案，并按评分细则中的空号顺序输出。

【评分细则结构】
{{rubricStructure}}

要求：
1. 按 blankNo 顺序逐空识别
2. 保持原文（包括错字、符号）
3. 空白未作答标记为"（未作答）"
4. 无法辨识标记为"（无法辨识）"
5. 直接返回纯 JSON

【输出格式】
{
  "blanks": [
    {"blankNo": "1-1", "subQ": "(1)", "text": "识别的答案文字"}
  ]
}"""
