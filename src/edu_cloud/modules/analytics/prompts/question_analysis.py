"""Question-level teaching analysis prompt builder.

Chain: 错误统计 → 错误归因（结合评分细则） → 教学指导
Reference: DMIT zhixue-server buildAnalysisPrompt
"""
from __future__ import annotations

from typing import Any


def build_question_analysis_prompt(
    *,
    subject: str,
    question_no: str,
    max_score: float | int,
    reference_answer: str,
    rubric_items: list[dict[str, Any]],
    stats: dict[str, Any],
) -> str:
    rubric_text = _format_rubric(rubric_items)
    blanks_text = _format_blank_stats(stats.get("blanks") or [])
    overview_text = _format_overview(stats)

    return f"""你是一位资深的学科教研员，请根据评分细则和学生答题数据，生成面向备课组的教学诊断分析。

## 题目信息
- 学科：{subject}
- 题号：Q{question_no}
- 满分：{max_score} 分

## 参考答案
{reference_answer or '(无)'}

## 评分细则（核心信息源，错因归纳必须以此为锚）
{rubric_text}

## 整体统计
{overview_text}

## 各空答题详情
{blanks_text}

---

请严格按以下 JSON 格式返回（只返回 JSON，不要其他内容）：

{{
  "summary": "2-3 句话概述学生在本题的整体表现和核心问题",
  "blanks": [
    {{
      "blankNo": "空号如 1-1",
      "correctRate": "正确率%",
      "difficulty": "easy|medium|hard",
      "insight": "该空 1-2 句分析洞察",
      "errorTypes": [
        {{
          "type": "错误类型名称（概念混淆/知识空白/术语不精确/审题偏差/表述不完整/计算错误）",
          "description": "具体描述，引用细则中的判分规则说明为什么错",
          "affectedCount": "影响人数（从答案分布估算）",
          "topWrongAnswers": ["典型错误答案1", "典型错误答案2"]
        }}
      ]
    }}
  ],
  "correlations": [
    "跨空关联发现（如：第X空和第Y空错误高度相关，说明学生对某概念整体理解不到位）"
  ],
  "prioritizedActions": [
    {{
      "priority": 1,
      "action": "最优先的教学行动",
      "reason": "为什么这个最重要（影响人数×严重程度）",
      "targetBlanks": ["相关空号"],
      "strategy": "具体教学策略（对比教学/专题训练/错题复盘/...）"
    }}
  ],
  "knowledgeGaps": [
    "本题暴露的知识薄弱点（基于细则中的考查知识点）"
  ]
}}

重要提示：
1. errorTypes 的 type 必须是以下之一：概念混淆、知识空白、术语不精确、审题偏差、表述不完整、计算错误
2. 错因描述必须引用评分细则中的判分规则，不要自己推测
3. prioritizedActions 按影响人数×严重程度排序，最多 3 条
4. correlations 只列有证据的关联，没有就返回空数组
5. 语言简洁专业，面向教研组长"""


def build_subject_summary_prompt(
    *,
    subject: str,
    question_analyses: list[dict[str, Any]],
) -> str:
    questions_text = ""
    for qa in question_analyses:
        questions_text += f"""
### Q{qa['questionNo']}（满分 {qa['maxScore']}）
- 概述：{qa.get('summary', '-')}
- 知识薄弱点：{', '.join(qa.get('knowledgeGaps', []))}
- 最优先行动：{qa.get('prioritizedActions', [{}])[0].get('action', '-') if qa.get('prioritizedActions') else '-'}
"""

    return f"""你是教研组长，请根据下列各题分析，为 {subject} 学科生成一份备课组教学行动摘要。

## 各题分析摘要
{questions_text}

请严格按以下 JSON 格式返回（只返回 JSON）：

{{
  "subjectSummary": "2-3 句话概述本学科学生整体表现",
  "commonPatterns": [
    "跨题共性问题（如：开放题普遍不敢动笔、地理术语普遍不精确）"
  ],
  "topActions": [
    {{
      "priority": 1,
      "action": "学科级教学行动",
      "reason": "为什么优先",
      "relatedQuestions": ["Q26", "Q27"]
    }}
  ],
  "strengthAreas": ["学生掌握较好的知识点/题型"]
}}

要求：
1. topActions 最多 3 条，按优先级排序
2. commonPatterns 是跨题目的共性，不是重复单题结论
3. 语言面向备课组长，简洁可执行"""


def build_principal_summary_prompt(
    *,
    subject_summaries: list[dict[str, Any]],
    overall_stats: dict[str, Any],
) -> str:
    subjects_text = ""
    for ss in subject_summaries:
        subjects_text += f"""
### {ss['subject']}
- 概述：{ss.get('subjectSummary', '-')}
- 共性问题：{', '.join(ss.get('commonPatterns', []))}
- 最优先行动：{ss.get('topActions', [{}])[0].get('action', '-') if ss.get('topActions') else '-'}
- 优势领域：{', '.join(ss.get('strengthAreas', []))}
"""

    return f"""你是教务主任，请根据各学科分析摘要，为校长生成 5 条简洁的教学决策结论。

## 整体数据
- 考试：期中考试，3 学科 18 题
- 加权得分率：{overall_stats.get('weightedScoreRate', '-')}%
- 加权难度：{overall_stats.get('weightedDifficulty', '-')}/10

## 各学科摘要
{subjects_text}

请严格按以下 JSON 格式返回（只返回 JSON）：

{{
  "conclusions": [
    {{
      "title": "一句话结论（校长能直接引用）",
      "detail": "一句话补充说明",
      "actionOwner": "谁该行动（某学科备课组/教务处/年级组）",
      "urgency": "high|medium|low"
    }}
  ]
}}

要求：
1. 恰好 5 条，按 urgency 排序（high 在前）
2. 校长不懂教学细节，结论必须是"XX 有问题，建议 YY 做 ZZ"的形式
3. 不要提 AI 阅卷技术细节
4. 每条不超过 30 字"""


def _format_rubric(items: list[dict[str, Any]]) -> str:
    if not items:
        return "(未设置评分细则)"
    parts = []
    for item in items:
        blank_no = item.get("blankNo", "?")
        score = item.get("score", "?")
        answer = item.get("answer") or "-"
        rules = item.get("judgingRules") or "-"
        context = item.get("context") or ""
        lines = [f"【第{blank_no}空】({score}分)"]
        lines.append(f"  标准答案：{answer}")
        if context:
            lines.append(f"  考查知识点：{context}")
        lines.append(f"  判分规则：{rules}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _format_blank_stats(blanks: list[dict[str, Any]]) -> str:
    if not blanks:
        return "(无数据)"
    parts = []
    for b in blanks:
        blank_no = b.get("blankNo", "?")
        total = b.get("total", 0)
        correct_rate = b.get("correctRate", "-")
        avg_score = b.get("avgScore", "-")
        max_score = b.get("maxScore", "-")
        wrong_answers = b.get("wrongAnswers") or []

        answer_dist = "\n".join(
            f"    「{wa['answer']}」: {wa['count']}人"
            for wa in wrong_answers[:10]
        ) or "    (无高频错误)"

        parts.append(
            f"【第{blank_no}空】满分{max_score}分\n"
            f"  作答人数: {total}\n"
            f"  正确率: {correct_rate}%\n"
            f"  平均得分: {avg_score}分\n"
            f"  高频错误答案:\n{answer_dist}"
        )
    return "\n\n".join(parts)


def _format_overview(stats: dict[str, Any]) -> str:
    return (
        f"- 样本数量: {stats.get('total', '-')} 份\n"
        f"- 满分: {stats.get('maxScore', '-')} 分\n"
        f"- 平均分: {stats.get('avg', '-')} 分\n"
        f"- 得分率: {stats.get('scoreRate', '-')}%\n"
        f"- 满分人数: {stats.get('fullMark', '-')}\n"
        f"- 零分人数: {stats.get('zero', '-')}"
    )
