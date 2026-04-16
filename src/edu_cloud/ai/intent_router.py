"""Keyword-based intent classification for user messages."""
from __future__ import annotations

from dataclasses import dataclass, field

from edu_cloud.ai.entity_extractor import EntityExtractor

WORKFLOW_KEYWORDS: dict[str, list[str]] = {
    "post_exam_analysis": [
        "考试分析", "成绩分析", "考后", "这次考试", "期中", "期末", "月考", "分析报告",
    ],
    "student_profile": [
        "学情", "画像", "学习情况", "进步", "退步", "掌握", "薄弱",
    ],
    "patrol": [
        "异常", "告警", "巡检", "超时", "未完成", "提交率",
    ],
}

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "exam_query": ["考试", "科目", "试卷", "题目"],
    "score_analysis": ["成绩", "分数", "排名", "均分", "对比"],
    "student_profile": ["画像", "掌握度", "错题", "趋势"],
    "homework": ["作业", "提交", "批改"],
    "knowledge": ["知识点", "课标", "教材", "概念"],
    "report": ["报告", "评语", "总结"],
    "findings": ["异常", "告警", "待办"],
}


@dataclass
class IntentResult:
    workflow: str | None
    mode: str  # "workflow" | "free"
    domains: list[str] = field(default_factory=list)
    confidence: float = 0.0
    needs_clarification: bool = False
    entities: dict | None = None


class IntentRouter:
    def classify(
        self,
        message: str,
        available_workflows: list[str] | None = None,
    ) -> IntentResult:
        entities = EntityExtractor.extract(message)

        # 1. Try workflow match (count keyword hits)
        best_wf: str | None = None
        best_score = 0
        for wf_name, keywords in WORKFLOW_KEYWORDS.items():
            if available_workflows is not None and wf_name not in available_workflows:
                continue
            score = sum(1 for kw in keywords if kw in message)
            if score > best_score:
                best_score = score
                best_wf = wf_name

        if best_score >= 2:
            return IntentResult(
                workflow=best_wf,
                mode="workflow",
                domains=[],
                confidence=min(best_score / 3, 1.0),
                entities=entities,
            )

        # 2. Domain classification
        domains = [
            d for d, kws in DOMAIN_KEYWORDS.items() if any(kw in message for kw in kws)
        ]

        if best_score == 1:
            return IntentResult(
                workflow=best_wf,
                mode="workflow",
                domains=domains,
                confidence=0.4,
                needs_clarification=True,
                entities=entities,
            )

        return IntentResult(
            workflow=None,
            mode="free",
            domains=domains[:2],
            confidence=0.8 if domains else 0.3,
            entities=entities,
        )
