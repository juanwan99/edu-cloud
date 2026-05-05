# src/edu_cloud/modules/grading/prompts/chinese.py
"""Chinese (语文) subject prompts — ported from zhixue-server senior/chinese.js."""
from .base import GRADING_JSON_SCHEMA, FATAL_RULES, GRADING_METHOD_BASE, OCR_PROMPT_BASE, OCR_STRUCTURED_PROMPT_BASE, CORRECTION_PROMPT_BASE, build_rubric_generation

NAME = "语文"
LEVEL = "senior"
ROLE = "高中语文阅卷专家"

RUBRIC_GENERATION = build_rubric_generation(
    ROLE,
    "语文阅读/表达题只把完整语义等值答案放入 equivalentAnswers；采分关键词、主题词、泛化概括放 scoringRules，不得当作整空满分等价"
)

RUBRIC_GENERATION_CONFIG = {"temperature": 0.7, "max_tokens": 32768}

GRADING = """你是初中语文阅卷专家，请识别图片中学生的手写答案并评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

---

【评分方法 - 语文学科专用】

""" + GRADING_METHOD_BASE + """
   - 阅读理解重视语义，但必须按"要点完整度"给分：对象、原因/作用、情感/态度、限定条件缺一项则不得满分
   - 同义表述可给分，但只写关键词、主题词、套话或泛化概括，只能按 scoringRules 给部分分或0分
   - 默写题必须**字字准确**，不允许同义替换
   - 特别注意：错别字、漏字、偏离主题、答非所问

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
- 语义相近可给分，但必须明确答到题目要求的核心要点
- 只出现采分关键词，不等于整句要点完整；缺对象、缺原因、缺作用、缺情感指向时给部分分
- 排除项只否定核心错误方向；答案同时包含有效要点时，不得因出现排除词整空0分

**作文评分专用规则（满分≥40时生效）**：

⚠️ 作文必须使用「整体印象定档法」，严格按以下两步执行：

**第一步：整体印象定档（只看三个维度，忽略一切细节瑕疵）**
  A. 扣题度：文章主题是否与题目要求相关？
  B. 叙事完整度：是否有完整的事件经过？
  C. 情感真诚度：能否感受到作者的真实经历和感受？
定档：ABC全满足→二类(40+)；AB满足C弱→三类(35+)；仅A→四类(30+)；A不满足→五类

**第二步：档内微调**
  - 细节生动、语言流畅 → 档内偏上（可升档）
  - 错别字每2个扣1分，最多扣3分
  - 错别字、语病、字数略有不足 → 只影响档内微调，不影响定档

---

【输出JSON格式】
""" + GRADING_JSON_SCHEMA + """

---

""" + FATAL_RULES

GRADING_CONFIG = {"temperature": 0, "max_tokens": 32768}

GRADING_TEXT = """你是初中语文阅卷专家，请根据学生答案和评分细则进行精准评分。

【满分】{{fullScore}}分

【评分细则】
{{rubric}}

【学生答案】
{{extractedText}}

{{charStats}}

---

【评分方法 - 语文学科专用】

""" + GRADING_METHOD_BASE + """

---

【语文学科特殊规则】

**默写题**：错字、漏字、多字均不得分
**翻译题**：关键词采分+句意采分
**阅读题**：语义相近可给分，但要点必须明确、完整；只答关键词/泛化词不得满分
**排除项处理**：只有核心意思落入排除项且无有效要点时才0分；若有有效要点，按要点给部分分

**reason示例**：
   - ✓ "'辩'应为'辨'，错字不得分"
   - ✓ "漏写'也'字，默写不完整"
   - ✓ "关键词'以'译为'用来'，正确"
   - ✓ "答出核心要点'思乡之情'，满分"
   - ✓ "只答表层含义，缺深层理解，给1分"

**作文评分专用规则（满分≥40时生效）**：

⚠️ 作文必须使用「整体印象定档法」，严格按以下两步执行：

**第一步：整体印象定档**
通读全文，仅根据以下三个维度判断档次，此阶段完全忽略错别字、语病、字数：
  A. 扣题度：文章主题是否与题目要求相关？（标题格式不完美但内容沾边也算扣题）
  B. 叙事完整度：是否有完整的事件经过？（有起因、经过、结尾即可）
  C. 情感真诚度：能否感受到作者的真实经历和感受？

定档规则：
  - ABC 三项全部满足 → 二类文起评（40分）
  - AB 满足但 C 较弱 → 三类文起评（35分）
  - A 满足但 B 不足 → 四类文起评（30分）
  - A 不满足 → 五类文（0-29分）

**第二步：档内微调**
在已定档次的分数区间内加减：
  - 细节描写生动、语言流畅 → 档内加分，优秀者可升入上一档
  - 错别字每2个扣1分，最多扣3分
  - 字数判断必须使用【字数统计】提供的数字，禁止自行估算
  - 字数降档硬线：只有字数不足500字才可因字数降到四类文。500-600字属于"未完全达标"，只在档内扣1-2分，不降档

⚠️ 铁律：第二步的微调绝不能推翻第一步的定档结论。如果第一步定为二类文，那么即使错别字多、有语病，最终分数也必须在40分以上（扣完错别字3分后最低37分，仍在三类上限，不会跌到四类）。

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
