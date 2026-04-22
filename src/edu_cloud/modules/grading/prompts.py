"""AI 阅卷 prompt 模板。

Phase 1-C 起按 question_type 分派：
- fill_blank: 短答评分（关键词覆盖率）
- essay:      长答评分（分步骤、论证完整性）
- 其它/未知: 通用 prompt（向后兼容）
"""
import json


_SYSTEM_PROMPT_GENERIC = """你是一位严谨的阅卷老师。根据评分细则对学生答案进行评分。

要求：
1. 仔细对照评分细则的每个得分点
2. 给出具体的评分反馈，指出得分点和失分点
3. 直接返回纯 JSON（禁止 markdown 代码块）：{"score": 总分, "details": [{"blankNo": "1", "score": 得分, "maxScore": 满分, "reason": "原因"}], "comment": "评语", "confidence": 0-1的置信度}
4. score 不能超过满分，不能为负数
5. confidence 表示你对评分的确信程度
6. comment 控制在 50 字以内"""


_SYSTEM_PROMPT_FILL_BLANK = """你是一位阅卷老师，正在批改填空题。要求精准、快速。

填空题评分原则：
1. 对照评分细则，比对学生作答与参考答案的关键词覆盖率
2. 答案核心实体/数值/术语完全正确给满分；表述等价（同义词/近义术语）给满分
3. 关键词缺失或错误按比例扣分；空白不得分
4. comment 必须简短（1-2 句话），点明对错，避免赘述
5. 直接返回纯 JSON（禁止 markdown 代码块）：{"score": 总分, "details": [{"blankNo": "1", "score": 得分, "maxScore": 满分, "reason": "原因"}], "comment": "评语", "confidence": 0-1}
6. score 不超过满分、不为负
7. comment 控制在 30 字以内"""


_SYSTEM_PROMPT_ESSAY = """你是一位严谨的阅卷老师，正在批改主观解答题（论述/作文/解答题）。

主观题评分原则：
1. 严格对照评分细则的每一个得分点逐条核对，按"采分点累加"打分
2. 关注论证完整性、步骤是否齐全、逻辑链是否自洽
3. 表达不规范但实质正确给分；缺步骤、跳步骤按对应得分点扣分
4. 字迹潦草且无法辨识可备注；不要凭主观印象扣分
5. comment 需逐条说明每个采分点的得失，便于学生复盘
6. 直接返回纯 JSON（禁止 markdown 代码块）：{"score": 总分, "details": [{"blankNo": "1", "score": 得分, "maxScore": 满分, "reason": "原因"}], "comment": "评语", "confidence": 0-1}
7. score 不超过满分、不为负
8. comment 控制在 80 字以内"""


_SYSTEM_PROMPT_BY_TYPE = {
    "fill_blank": _SYSTEM_PROMPT_FILL_BLANK,
    "essay": _SYSTEM_PROMPT_ESSAY,
}


# 向后兼容导出
SYSTEM_PROMPT = _SYSTEM_PROMPT_GENERIC


def build_rubric_generation_prompt(
    content: str,
    reference_answer: str,
    max_score: float,
    question_type: str | None = None,
) -> list[dict]:
    """构建评分细则生成 prompt。

    Args:
        content: 题目内容文字
        reference_answer: 参考答案
        max_score: 满分
        question_type: 题目类型（可选，用于角色提示）

    Returns:
        [{"role": "system", ...}, {"role": "user", ...}]
    """
    system_prompt = (
        "你是一位资深阅卷组长，具有多年命题和评分细则编制经验。"
        "请根据题目原文和参考答案，生成一份结构化的评分细则（Rubric）。\n\n"
        "要求：\n"
        "1. 按照得分点逐条拆分，每条独立计分\n"
        "2. 所有得分点的 score 之和必须等于满分\n"
        "3. answer 字段填写该得分点的标准答案或关键词\n"
        "4. intent 字段说明该得分点的考查意图\n"
        "5. coreRequirement 字段说明得分的核心要求（如\"必须包含\"、\"意思相近即可\"等）\n"
        "6. 直接返回纯 JSON 数组（禁止 markdown 代码块），格式如下：\n"
        '[{"blankNo": "1", "score": 数字, "answer": "标准答案", '
        '"intent": "考查意图", "coreRequirement": "得分要求"}, ...]'
    )

    user_content = (
        f"题目：{content}\n\n"
        f"参考答案：{reference_answer}\n\n"
        f"满分：{max_score} 分\n\n"
        "请生成评分细则 JSON 数组。"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def build_grading_prompt(
    rubric: dict,
    question: dict,
    question_type: str | None = None,
) -> list[dict]:
    """构建评分 prompt。

    Args:
        rubric: {"criteria": [...]} 评分细则
        question: {"name": str, "max_score": float}
        question_type: choice|multi_choice|fill_blank|essay（None 走通用模板）
    """
    rubric_text = json.dumps(rubric.get("criteria", []), ensure_ascii=False, indent=2)
    max_score = question.get("max_score", 0)
    question_name = question.get("name", "")

    user_content = (
        f"题目：{question_name}\n"
        f"满分：{max_score}\n\n"
        f"评分细则：\n{rubric_text}\n\n"
        "请根据图片中的学生答案和以上评分细则进行评分，返回 JSON（含 details 逐空明细）。"
    )

    system_prompt = _SYSTEM_PROMPT_BY_TYPE.get(question_type or "", _SYSTEM_PROMPT_GENERIC)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
