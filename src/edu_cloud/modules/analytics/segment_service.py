"""分数段配置 CRUD + 分段计算。"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.score_segment import ScoreSegmentConfig
from edu_cloud.services.exceptions import ValidationError

logger = logging.getLogger(__name__)

DEFAULT_BOUNDARIES = [85, 70, 60]
DEFAULT_LABELS = ["优秀", "良好", "及格", "不及格"]


def compute_segments(
    scores: list[float],
    max_score: float,
    boundaries: list[int],
    labels: list[str],
) -> list[dict]:
    """将原始分按百分比阈值分段。

    boundaries 降序，如 [85, 70, 60]。labels 比 boundaries 多一个。
    返回 [{label, count, percentage, boundary_min, boundary_max}]。
    """
    n = len(scores)
    segments = []
    sorted_boundaries = sorted(boundaries, reverse=True)

    if not sorted_boundaries:
        # 无阈值：所有人归入单一段
        return [{
            "label": labels[0] if labels else "全部",
            "count": n,
            "percentage": 1.0 if n > 0 else 0,
            "boundary_min": 0,
            "boundary_max": 101,
        }]

    for i, label in enumerate(labels):
        if i == 0:
            b_min = sorted_boundaries[0]
            b_max = 101  # inclusive upper
        elif i < len(sorted_boundaries):
            b_min = sorted_boundaries[i]
            b_max = sorted_boundaries[i - 1]
        else:
            b_min = 0
            b_max = sorted_boundaries[-1] if sorted_boundaries else 101

        count = 0
        for score in scores:
            pct = (score / max_score * 100) if max_score > 0 else 0
            if b_min <= pct < b_max:
                count += 1
            elif i == 0 and pct >= b_min:
                # 最高段: >= boundary
                count += 1

        segments.append({
            "label": label,
            "count": count,
            "percentage": round(count / n, 4) if n > 0 else 0,
            "boundary_min": b_min,
            "boundary_max": b_max,
        })

    return segments


async def get_segment_config(
    db: AsyncSession, school_id: str, subject_code: str | None = None,
) -> tuple[list[int], list[str]]:
    """获取分数段配置。优先科目覆盖，fallback 学校默认，最终 fallback 硬编码默认。"""
    if subject_code:
        result = await db.execute(
            select(ScoreSegmentConfig).where(
                ScoreSegmentConfig.school_id == school_id,
                ScoreSegmentConfig.subject_code == subject_code,
            )
        )
        cfg = result.scalar_one_or_none()
        if cfg:
            return cfg.boundaries, cfg.labels

    # fallback: 学校默认
    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school_id,
            ScoreSegmentConfig.subject_code.is_(None),
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        return cfg.boundaries, cfg.labels

    return DEFAULT_BOUNDARIES, DEFAULT_LABELS


async def upsert_segment_config(
    db: AsyncSession,
    school_id: str,
    boundaries: list[int],
    labels: list[str],
    created_by: str | None = None,
    subject_code: str | None = None,
) -> ScoreSegmentConfig:
    """创建或更新分数段配置（upsert 语义）。"""
    if len(labels) != len(boundaries) + 1:
        raise ValidationError(f"labels 数量({len(labels)})必须比 boundaries({len(boundaries)})多 1")
    if boundaries != sorted(boundaries, reverse=True):
        raise ValidationError("boundaries 必须降序排列")
    if any(b < 0 or b > 100 for b in boundaries):
        raise ValidationError("boundaries 值必须在 0-100 之间")

    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school_id,
            ScoreSegmentConfig.subject_code == subject_code
            if subject_code
            else ScoreSegmentConfig.subject_code.is_(None),
        )
    )
    cfg = result.scalar_one_or_none()

    if cfg:
        cfg.boundaries = boundaries
        cfg.labels = labels
    else:
        cfg = ScoreSegmentConfig(
            school_id=school_id,
            subject_code=subject_code,
            boundaries=boundaries,
            labels=labels,
            created_by=created_by,
        )
        db.add(cfg)

    await db.flush()
    return cfg


async def list_segment_configs(
    db: AsyncSession, school_id: str,
) -> list[ScoreSegmentConfig]:
    """列出学校所有分数段配置（默认 + 科目覆盖）。"""
    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school_id,
        )
    )
    return list(result.scalars().all())
