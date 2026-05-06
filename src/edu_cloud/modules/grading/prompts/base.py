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
          "reason": "判分要点（≤40字，写清差异点和给分依据）"
        }
      ]
    }
  ],
  "deductions": ["1-1 应填xxx"],
  "comment": "一句话总评（≤30字）"
}"""

FATAL_RULES = """【⚠️ 致命规则】

1. **禁止幻觉**：空白/未作答/无法辨识 → answer="（未作答）"或"（无法辨识）", score=0

2. **等价答案不是关键词池**：
   - equivalentAnswers 只表示与标准答案在本题语境下完全等值、可独立拿满分的答案
   - 命中 equivalentAnswers 时，仍需确认没有命中排除项/典型错误，且没有缺少题目要求的对象、限定、因果或形式要求
   - 若只是采分关键词、上位/下位概念、泛化说法、半句要点，必须按 judgingRules/scoringRules 给分，不得直接满分

3. **排除项不是整空一票否决**：
   - 只有学生答案核心意思确实落入排除项，且无可采有效要点时，才给0
   - 同一答案中既有错误表述又有有效要点时，按有效要点给部分分，并在reason说明错误限制

4. **scoringRules 是给分依据，不是参考建议**：
   - scoringRules 定义了明确的分数梯度，你必须严格按 condition 描述匹配给分
   - 学生答案符合中间档 condition（如"方向正确但模糊"）时，必须给该档分数，禁止自行降到0
   - 给0分前必须确认：学生答案不符合 scoringRules 中任何一档的 condition
   - 【严禁】用自创的更高标准（如"不够具体"、"缺可操作性"）覆盖 scoringRules 已定义的给分条件

5. **score必须与reason一致**：
   - reason说完整满足满分条件 → score=满分
   - reason说只答到部分要点/表达泛化/限定不足 → score必须是部分分
   - reason说核心命中排除项且无有效要点 → score=0
   - 【严禁】reason和score矛盾！

6. **分数硬性约束**：
   - blank.score ≤ blank.fullScore
   - subQuestion.score = 该小问所有blank.score之和
   - 总score = 所有subQuestion.score之和

7. **reason是教师复核用判分要点（≤40字）**：
   - 写清差异点和给分依据，让老师一眼看懂为什么给这个分
   - 满分时说清匹配了什么：✓ "与标准答案'北温带'一致" ✓ "1/2与0.5等价形式"
   - 扣分时说清错在哪里：✓ "③是子叶，应为④胚芽" ✓ "'条件'太泛，需具体到'温度'"
   - 部分分说清缺什么：✓ "答出原因缺结果，给部分分" ✓ "只答原理缺方法论"
   - ✗ 禁止输出"正确"/"命中等价答案"/"满足评分标准"等无信息套话
   - ✗ 禁止引用规则编号或judgingRules等内部术语

【生成顺序】先判断空白/OCR不可辨 → 再检查排除项是否核心命中 → 再判断等价答案是否完整等值 → 最后按judgingRules/scoringRules给分并写清reason。"""

GRADING_METHOD_BASE = """对每个填空：
1. **理解语境**：先看context，理解题目背景、考查点和答案逻辑
2. **先判空白/OCR不可辨**：空白、未作答、无法辨识不得猜测，给0并如实标注
3. **检查陷阱**：先看"排除项"和"典型错误"，判断学生答案核心意思是否落入错误方向
4. **等价答案校验**：学生答案命中 equivalentAnswers 时，只有在本题语境下完整等值、未缺限定、未命中排除项时才给满分
5. **语义判断**：未命中等价答案时，用judgingRules中的满分条件判断语义是否完整满足
6. **scoringRules 强制逐条匹配（不可跳过）**：
   - 未达满分时，必须将学生答案与 scoringRules 中的每一条 condition 逐条比对
   - 学生答案符合哪一档的 condition 描述，就必须给该档分数，不得自行加码降档
   - 特别注意：scoringRules 中"方向正确但模糊"、"做法合理但关联弱"等中间档是专门为不完美但有价值的答案设计的，不得跳过直接给0
   - 只有学生答案不符合 scoringRules 任何一档的 condition 时，才可给0分
7. **部分分判定**：有有效内容但不完整时，参考"得分梯度"给部分分；不得因一个瑕疵抹掉已答对要点
8. **互换空处理**：标注"答案可互换"的空，两空答案对调仍给满分
9. **reason写判分要点**：reason必须说清这个分数怎么来的，禁止输出"正确"/"命中等价答案"等套话
   - 满分：说清匹配了什么（如"与'光合作用'一致"）
   - 扣分：说清错在哪（如"应为'胚芽'，写成'子叶'"）
   - 部分分：说清有什么缺什么（如"有原因缺结果，给1分"）
10. **宽容度校准（对齐人工阅卷）**：
   - 短答题学生简称、漏后缀、轻微错别字，只要在本题语境下无歧义且不改变核心概念，不因表达不完整直接判0
   - 但上位词、泛化词、相邻概念、缺限定的答案不得直接判满分，应按 scoringRules 给部分分
   - 当 rubric 的 judgingRules 已显式说明宽松/严格条件时，以 rubric 为准"""

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
3. 只有该空确实没有任何学生书写痕迹时，才标记为"（未作答）"
4. 有书写痕迹但内容看不清，标记为"（无法辨识）"，不要标成未作答
5. 答案可能错误也必须照实识别，禁止按标准答案推断或替换
6. 直接返回纯 JSON（禁止 markdown 代码块）

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
1a. 若学生在同一行用①②、(1)(2)、1. 2. 写出多个答案，必须按评分细则空号拆分到多个 blanks
2. 保持原文（包括错字、符号）
3. 被划掉/涂改/删除线覆盖的内容必须忽略，只识别最终有效答案（学生划掉再改，说明原内容作废）
4. 只有该空确实没有任何学生书写痕迹时，才标记为"（未作答）"
5. 有书写痕迹但内容看不清，标记为"（无法辨识）"，不要标成未作答
6. 答案可能错误也必须照实识别，禁止按标准答案推断或替换
7. 直接返回纯 JSON

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
        "6. **equivalentAnswers 只放满分等价答案** - 只能列与标准答案在本题语境下完整等值、可独立拿满分的变体；采分关键词、上位/下位概念、泛化表达、半句要点必须放入 scoringRules 或 judgingRules，不得放入 equivalentAnswers\n\n"
        "---\n\n"
        "## 审题清单（生成每空前必须逐项检查）\n\n"
        "1. **题干上下文补足**：仔细审读题目原文，识别填空位置前后的文字。\n"
        "   - 若题干已有后缀/前缀（如\"___洋\"、\"___带\"、\"___区\"），学生只需填缺失部分即可满分，应将省略后缀的答案列入 equivalentAnswers\n"
        "   - 若题干要求从选项/图中选填（如\"甲/乙/丙\"），equivalentAnswers 应同时包含选项代号和对应地理实体名称\n"
        "   - 将题干上下文写入 context 字段，让评分 LLM 理解学生只需填什么\n\n"
        "2. **维度策略声明**：参考答案含多个维度（如\"高温多雨\"含热量+降水）时，必须在 judgingRules 中显式声明：\n"
        "   - 满分需要 all（全部维度）/ any（任一维度）/ k-of-n（N选K）\n"
        "   - 此判断依据是题干要求和官方评分标准，不得机械地将并列短语全部设为必要条件\n"
        "   - 仅当题干、官方评分标准或显式策略支持时才标注 any；默认按参考答案的维度数量要求\n\n"
        "3. **简称/省略审计**：\n"
        "   - 只有题干上下文或学科惯例能补足缺失信息且无歧义时，简称才可进 equivalentAnswers\n"
        "   - 可能有歧义的简称（如\"印度\"在非地理水域语境下指国家）只能进 scoringRules 作为条件给分\n\n"
        "4. **错别字/OCR 处理**：\n"
        "   - 不改变学科概念的常见错别字、形近字、OCR 重复字（如\"受精精\"→\"受精\"）应在 judgingRules 中注明\"不扣分\"\n"
        "   - 改变学科概念的错字（如\"蒸发\"vs\"蒸腾\"是不同生物学概念）不得放入 equivalentAnswers，应在 scoringRules 中按语境给部分分或在 exclusionRules 中排除\n\n"
        "5. **上下位概念边界**：\n"
        "   - 完整等值答案（同义词、规范简称）→ equivalentAnswers\n"
        "   - 上位概念/泛化表达（信息量减少但方向正确）→ scoringRules 部分分\n"
        "   - 下位例子（过于具体但方向正确）→ scoringRules 部分分\n"
        "   - 相邻概念/混淆概念 → exclusionRules\n\n"
        "---\n\n"
        "## 输出格式\n\n"
        '请直接输出JSON对象 {"rubricItems": [...]}，不要包含markdown代码块标记。\n\n'
        "每个 rubricItem 包含：\n"
        "- subQ: 小问编号如\"(1)\"\n"
        "- blankNo: 空号如\"1-1\"\n"
        "- score: 该空分值\n"
        "- title: 简短标题\n"
        "- standardAnswer: 标准答案\n"
        f"- equivalentAnswers: 满分等价答案数组{eq_note}。只列完整等值变体：规范简称、无歧义别称、题干明确认可的同义表述；禁止把采分关键词、上位/下位概念、泛化词、缺少限定的短语放入此数组\n"
        "- context: 【考查点】+【题目情境】+【推理链】的合并描述（务必详尽，评分LLM只看这个理解题目）\n"
        "- judgingRules: 满分条件+部分分条件+典型错误+排除规则+边界案例（含模糊答案如何判定，如\"学生只写简写是否给分\"）\n"
        '- scoringRules: [{"condition": "条件", "score": 分值}]\n'
        '- exclusionRules: [{"pattern": "错误模式", "reason": "排除原因"}]\n'
        "- typicalWrongAnswers: 常见错误答案数组\n"
        "- swappableWith: 可互换的blankNo（如\"1-2\"），无则填null。同一小问内多个空如果答案可交换顺序填写，必须用此字段互相标注"
    )


ESSAY_OCR_PROMPT = """请识别图片中的手写中文作文内容，完整逐字逐段输出原文文字。
图片包含左右两页内容，请务必从左页第一行开始，逐行识别全部页面的文字。
只输出作文正文，不要添加任何说明、标题标注或格式标记。
保持原文（包括错字），被划掉的内容忽略。"""


import re

_SENTENCE_END_RE = re.compile(r"[。！？…）》”’']$")


def clean_essay_ocr(text: str) -> str:
    """去除 OCR 产生的假换行，保留段落分隔和首行标题。"""
    if not text:
        return text
    lines = text.split('\n')
    parts = []
    for i, line in enumerate(lines):
        s = line.rstrip()
        if not s:
            parts.append('\n')
            continue
        parts.append(s)
        if i < len(lines) - 1:
            nxt = lines[i + 1].strip()
            if not nxt or _SENTENCE_END_RE.search(s) or i == 0:
                parts.append('\n')
        else:
            parts.append('\n')
    return ''.join(parts).strip()


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
