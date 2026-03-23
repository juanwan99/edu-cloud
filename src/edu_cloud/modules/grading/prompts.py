"""AI 阅卷 prompt 模板（从 exam-ai 迁入）。"""
import json


SYSTEM_PROMPT = """你是一位严谨的阅卷老师。根据评分细则对学生答案进行评分。

要求：
1. 仔细对照评分细则的每个得分点
2. 给出具体的评分反馈，指出得分点和失分点
3. 以 JSON 格式返回结果：{"score": 数字, "feedback": "评语", "confidence": 0-1的置信度}
4. score 不能超过满分，不能为负数
5. confidence 表示你对评分的确信程度"""


def build_grading_prompt(rubric: dict, question: dict) -> list[dict]:
    rubric_text = json.dumps(rubric.get("criteria", []), ensure_ascii=False, indent=2)
    max_score = question.get("max_score", 0)
    question_name = question.get("name", "")

    user_content = (
        f"题目：{question_name}\n"
        f"满分：{max_score}\n\n"
        f"评分细则：\n{rubric_text}\n\n"
        "请根据图片中的学生答案和以上评分细则进行评分，返回 JSON。"
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
