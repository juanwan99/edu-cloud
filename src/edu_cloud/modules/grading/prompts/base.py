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

DRAWING_HINT = """【⚠️ 作图/画图题专用指引】

这是一道作图/画图题，学生的答案是图形而非文字。请注意：
1. **评估图形本身**：关注线条、标注、结构、位置关系，而非文字内容
2. **识别图形要素**：箭头方向、连线关系、区域标注、符号使用、比例关系
3. **允许手绘偏差**：学生手绘不可能完美，重点是概念和关系是否正确
4. **常见作图类型**：遗传图解、细胞分裂图、电路图、力学示意图、地理等高线、化学装置图等
5. **llmRecognizedText**：用文字描述你看到的图形内容（如"画了一个细胞，标注了细胞膜、细胞核"）

"""

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

CORRECTION_PROMPT_BASE = """你是OCR修正专家。对比两个OCR通道结果，输出修正后的JSON。

## Gemini OCR（主通道）
{{geminiText}}

## 百度手写OCR（辅助）
{{baiduText}}

## 参考答案（仅辅助判断OCR准确性，禁止替换为标准答案！）
{{referenceInfo}}

## 规则
1. 两通道一致→直接采用
2. 不一致→逐字符对比，识别手写形近混淆并融合修正
3. 一个通道比另一个多出内容→检查是漏识别还是多识别，倾向保留更完整的结果
4. 其中一个匹配干扰项(cf列表)→必须保留，学生真写错了
5. 百度含☰/≡/=/一等划线符号→该符号旁内容被学生划掉，从text中删除
6. 百度结果与Gemini完全无关联→百度不可信，保持Gemini结果

⚠️ 硬性约束（违反即判定失败）：
- 你是OCR纠错员，不是答题者。任务是还原学生真实笔迹，不是给出正确答案
- 输出只能来自OCR通道的原始文字（可修正形近字符），禁止出现两个通道中都没有的内容
- 参考答案(ans)仅帮你理解文字格式和判断通道可信度，禁止将答案内容复制到输出
- 自检：如果你的输出与ans完全相同，你几乎一定做错了——学生不一定写对了
- 两个通道都无法识别时，保留Gemini原始结果（含[?]、[空]等标记）

## 输出（仅JSON）
{"blanks":[{"no":"1","sub":"(1)","text":"修正后文字","c":false}]}"""
