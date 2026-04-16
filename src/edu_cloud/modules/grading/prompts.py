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
3. 以 JSON 格式返回结果：{"score": 数字, "feedback": "评语", "confidence": 0-1的置信度}
4. score 不能超过满分，不能为负数
5. confidence 表示你对评分的确信程度"""


_SYSTEM_PROMPT_FILL_BLANK = """你是一位阅卷老师，正在批改填空题。要求精准、快速。

填空题评分原则：
1. 对照评分细则，比对学生作答与参考答案的关键词覆盖率
2. 答案核心实体/数值/术语完全正确给满分；表述等价（同义词/近义术语）给满分
3. 关键词缺失或错误按比例扣分；空白不得分
4. feedback 必须简短（1-2 句话），点明对错，避免赘述
5. 以 JSON 返回：{"score": 数字, "feedback": "评语", "confidence": 0-1}
6. score 不超过满分、不为负"""


_SYSTEM_PROMPT_ESSAY = """你是一位严谨的阅卷老师，正在批改主观解答题（论述/作文/解答题）。

主观题评分原则：
1. 严格对照评分细则的每一个得分点逐条核对，按"采分点累加"打分
2. 关注论证完整性、步骤是否齐全、逻辑链是否自洽
3. 表达不规范但实质正确给分；缺步骤、跳步骤按对应得分点扣分
4. 字迹潦草且无法辨识可备注；不要凭主观印象扣分
5. feedback 需逐条说明每个采分点的得失，便于学生复盘
6. 以 JSON 返回：{"score": 数字, "feedback": "评语", "confidence": 0-1}
7. score 不超过满分、不为负"""


_SYSTEM_PROMPT_BY_TYPE = {
    "fill_blank": _SYSTEM_PROMPT_FILL_BLANK,
    "essay": _SYSTEM_PROMPT_ESSAY,
}


# 向后兼容导出
SYSTEM_PROMPT = _SYSTEM_PROMPT_GENERIC


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
        "请根据图片中的学生答案和以上评分细则进行评分，返回 JSON。"
    )

    system_prompt = _SYSTEM_PROMPT_BY_TYPE.get(question_type or "", _SYSTEM_PROMPT_GENERIC)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
