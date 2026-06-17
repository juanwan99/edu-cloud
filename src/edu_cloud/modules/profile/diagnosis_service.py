"""学生个体 AI 诊断（profile 模块自有，模板拼接 ORC-007，不调 LLM）。

D-03A：所有权从 analytics.insights_service 迁回 profile，消除 profile -> analytics 依赖边。
诊断仅消费 profile 自有三表（student_knowledge_mastery / student_error_patterns），
不依赖 analytics 内部聚合，迁移后无新增跨模块边。
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.profile.models import StudentKnowledgeMastery, StudentErrorPattern

logger = logging.getLogger(__name__)


async def student_ai_diagnosis(
    db: AsyncSession, *, student_id: str, school_id: str,
    exam_id: str | None = None,
    subject_code: str | None = None,
) -> dict:
    """学生个体 AI 诊断文本（模板拼接）。ORC-007。

    F004 修复：
    1. exam_id 用于过滤 last_exam_id，subject_code 过滤知识点关联科目
    2. 接入 StudentErrorPattern 维度
    """
    # 查询知识点掌握度
    stmt = select(StudentKnowledgeMastery).where(
        StudentKnowledgeMastery.student_id == student_id,
        StudentKnowledgeMastery.school_id == school_id,
    )
    if exam_id:
        stmt = stmt.where(StudentKnowledgeMastery.last_exam_id == exam_id)
    rows = list((await db.execute(stmt)).scalars().all())

    # 查询错误模式
    ep_stmt = select(StudentErrorPattern).where(
        StudentErrorPattern.student_id == student_id,
        StudentErrorPattern.school_id == school_id,
    )
    if subject_code:
        ep_stmt = ep_stmt.where(StudentErrorPattern.subject_code == subject_code)
    error_patterns = list((await db.execute(ep_stmt)).scalars().all())

    improving = []
    declining = []
    weak_points = []

    for m in rows:
        item = {
            "kp_name": m.concept_id,
            "mastery_level": round(m.mastery_level, 4) if m.mastery_level else 0,
            "trend": m.trend or "stable",
            "recent_scores": m.recent_scores or [],
        }
        if m.trend == "improving":
            improving.append(item)
        elif m.trend == "declining":
            declining.append(item)
        if m.mastery_level is not None and m.mastery_level < 0.6:
            weak_points.append(item)

    # 构建诊断文本
    parts = []
    if declining:
        d = declining[0]
        parts.append(f"知识点'{d['kp_name']}'掌握率持续下降（当前 {d['mastery_level']:.0%}），建议重点关注。")
    if improving:
        imp = improving[0]
        parts.append(f"知识点'{imp['kp_name']}'掌握率在上升（当前 {imp['mastery_level']:.0%}），继续保持。")
    if weak_points and not declining:
        w = weak_points[0]
        parts.append(f"知识点'{w['kp_name']}'掌握率较低（{w['mastery_level']:.0%}），建议加强练习。")

    # F004: 融入错误模式
    if error_patterns:
        ep = error_patterns[0]
        dist = ep.error_distribution or {}
        if dist:
            top_error = max(dist, key=dist.get)
            parts.append(f"主要错误类型为{top_error}（占比 {dist[top_error]:.0%}）。")

    if not parts:
        parts.append("暂无足够数据生成诊断。")

    return {
        "summary": "".join(parts),
        "improving": improving[:5],
        "declining": declining[:5],
        "weak_points": weak_points[:5],
        "error_patterns": [{"subject_code": ep.subject_code, "distribution": ep.error_distribution} for ep in error_patterns[:3]],
    }
