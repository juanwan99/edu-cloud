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
          "reason": "判分依据（≤20字，说明为何对/错/部分对）"
        }
      ]
    }
  ],
  "deductions": ["1-1 应填xxx"],
  "comment": "一句话总评（≤30字）"
}"""

FATAL_RULES = """【⚠️ 致命规则】

1. **禁止幻觉**：空白/未作答 → answer="（未作答）", score=0

2. **等价答案必须给满分**：学生答案匹配"等价答案"列表中任一项 → 该空满分，不得扣分
   - 【严禁】等价答案列表中有的答案，以"不完整/不规范/缺少XX"为由扣分

3. **score必须与reason一致**：
   - reason说"满足满分条件"或"命中等价答案" → score=满分
   - reason说"命中排除项/典型错误" → score=0
   - 【严禁】reason和score矛盾！

4. **分数硬性约束**：
   - blank.score ≤ blank.fullScore
   - subQuestion.score = 该小问所有blank.score之和
   - 总score = 所有subQuestion.score之和

5. **reason必须精简（≤20字）**：
   - 直接说判分依据，禁止引用规则编号或"满足/不满足判分规则"等套话
   - ✓ "③是子叶，应为④胚芽"
   - ✓ "'条件'太泛，需具体到'温度'"
   - ✓ "正确"／"命中等价答案"
   - ✗ "命中判分规则中xxx的0分条件"
   - ✗ "满足judgingRules中xxx的满分条件"

【生成顺序】先检查等价答案 → 再根据judgingRules判定 → 最后填score和精简reason！"""

GRADING_METHOD_BASE = """对每个填空：
1. **理解语境**：先看context，理解这道题的背景和答案逻辑
2. **等价答案优先**：如果学生答案匹配"等价答案（必须给满分）"中的任一项 → 直接给满分，不得以措辞/格式/完整性为由扣分
3. **语义判断**：学生答案未命中等价答案列表时，用judgingRules中的满分条件判断语义是否满足（不要求措辞一致）
4. **检查陷阱**：用"排除项"和"典型错误"排除看起来对但实际错的答案
5. **部分分判定**：满分条件不完全满足时，参考"得分梯度"给部分分（有内容但不完整 → 部分分，不是0分）
6. **互换空处理**：标注"答案可互换"的空，两空答案对调仍给满分"""

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
2. 被划掉/涂改/删除线覆盖的内容必须忽略，只识别最终有效答案（学生划掉再改，说明原内容作废）
3. 空白未作答标记为"（未作答）"
4. 无法辨识标记为"（无法辨识）"
5. 直接返回纯 JSON（禁止 markdown 代码块）

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
3. 被划掉/涂改/删除线覆盖的内容必须忽略，只识别最终有效答案（学生划掉再改，说明原内容作废）
4. 空白未作答标记为"（未作答）"
5. 无法辨识标记为"（无法辨识）"
6. 直接返回纯 JSON

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


def build_rubric_generation(role: str, equivalent_hint: str = "") -> str:
    eq_note = f"（{equivalent_hint}）" if equivalent_hint else ""
    return (
        f"你是{role}，负责生成AI可执行的评分细则。\n\n"
        "**核心原则**：评分LLM看不到原题图片，你生成的细则必须包含所有评分所需的上下文信息。\n\n"
        "{{imageDescription}}\n{{questionSection}}\n{{answerSection}}\n\n"
        "【满分】{{fullScore}}分\n\n"
        "---\n\n"
        "## ⚠️ 铁律（违反则输出无效）\n\n"
        "1. **分值必须遵守原文标注** - 原文\"每空2分\"→每空score=2\n"
        "2. **blankNo必须按顺序递增** - 格式：小问号-空号（如1-1, 1-2, 2-1）\n"
        "3. **总分验算** - 所有score之和 = {{fullScore}}分\n"
        "4. **无灰色地带** - 细则必须覆盖所有可能的学生答案类型\n"
        "5. **各空独立评分** - 每个空单独判分，禁止跨空逻辑连坐（如\"若2-1填甲则2-2应填乙→扣分\"）\n"
        "6. **equivalentAnswers 必须主动穷举** - 不能只写标准答案原文，必须列出所有可接受的变体：简写/缩写、别称/同义词、上位/下位概念、带/不带修饰词\n\n"
        "---\n\n"
        "## 输出格式\n\n"
        '请直接输出JSON对象 {"rubricItems": [...]}，不要包含markdown代码块标记。\n\n'
        "每个 rubricItem 包含：\n"
        "- subQ: 小问编号如\"(1)\"\n"
        "- blankNo: 空号如\"1-1\"\n"
        "- score: 该空分值\n"
        "- title: 简短标题\n"
        "- standardAnswer: 标准答案\n"
        f"- equivalentAnswers: 等效答案数组{eq_note}。必须穷举：简写（如\"北温带\"→[\"温\",\"北温\"]）、别称（如\"山脉\"→[\"山系\",\"山地\"]）、上下位概念（如\"孟加拉湾\"↔\"印度洋\"）\n"
        "- context: 【考查点】+【题目情境】+【推理链】的合并描述（务必详尽，评分LLM只看这个理解题目）\n"
        "- judgingRules: 满分条件+部分分条件+典型错误+排除规则+边界案例（含模糊答案如何判定，如\"学生只写简写是否给分\"）\n"
        '- scoringRules: [{"condition": "条件", "score": 分值}]\n'
        '- exclusionRules: [{"pattern": "错误模式", "reason": "排除原因"}]\n'
        "- typicalWrongAnswers: 常见错误答案数组\n"
        "- swappableWith: 可互换的blankNo（如\"1-2\"），无则填null。同一小问内多个空如果答案可交换顺序填写，必须用此字段互相标注"
    )


import re

_CN_CHAR_RE = re.compile(r'[一-鿿]')
_CN_PUNC_RE = re.compile(
    r'[，。！？、；：""''（）【】《》〈〉—…·～￥﹏'
    r',.!?;:\"\'\(\)\[\]]'
)
_EN_WORD_RE = re.compile(r'[a-zA-Z]+')
_DIGIT_RE = re.compile(r'[0-9０-９]')


_OCR_CHAR_COEFF = 1.08  # OCR 漏识别补偿：实测 OCR 字数普遍偏低 ~8%


def count_essay_chars(raw_text: str) -> tuple[int, str]:
    """统计作文字数（汉字+标点+数字），返回 (字数, charStats 提示文本)。

    中考/高考作文方格纸规则：汉字、标点、数字各占一格均计字数；
    段首空格（含全角空格）和换行不计。
    乘以 _OCR_CHAR_COEFF 补偿 OCR 漏识别。
    """
    cn_chars = len(_CN_CHAR_RE.findall(raw_text))
    cn_punc = len(_CN_PUNC_RE.findall(raw_text))
    digits = len(_DIGIT_RE.findall(raw_text))
    en_words = len(_EN_WORD_RE.findall(raw_text))

    import math
    if cn_chars >= en_words and cn_chars > 0:
        raw_total = cn_chars + cn_punc + digits
        total = math.ceil(raw_total * _OCR_CHAR_COEFF)
        return total, f"【字数统计】约{total}字（基于OCR识别，已校准；请以此数字判断是否达到字数要求，禁止自行重新估算字数）"
    elif en_words > 0:
        total = math.ceil(en_words * _OCR_CHAR_COEFF)
        return total, f"【字数统计】约{total}词（基于OCR识别，已校准；请以此数字判断是否达到词数要求，禁止自行重新估算词数）"
    else:
        total = cn_punc + digits
        return total, ""
