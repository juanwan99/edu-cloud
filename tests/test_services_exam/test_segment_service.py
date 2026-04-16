import pytest
from edu_cloud.models.school import School
from edu_cloud.models.score_segment import ScoreSegmentConfig
from sqlalchemy import select


@pytest.fixture
async def school(db):
    s = School(name="SegTest", code="SEG01")
    db.add(s)
    await db.commit()
    return s


async def test_create_default_segment(db, school):
    cfg = ScoreSegmentConfig(school_id=school.id)
    db.add(cfg)
    await db.commit()

    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school.id,
            ScoreSegmentConfig.subject_code.is_(None),
        )
    )
    row = result.scalar_one()
    assert row.boundaries == [85, 70, 60]
    assert row.labels == ["优秀", "良好", "及格", "不及格"]


async def test_upsert_prevents_duplicate_default(db, school):
    """Service 层 upsert 阻止同校重复默认配置。"""
    from edu_cloud.modules.analytics.segment_service import upsert_segment_config
    await upsert_segment_config(db, school.id, [85, 70, 60], ["优", "良", "及", "不"])
    await db.commit()
    await upsert_segment_config(db, school.id, [90, 75, 60], ["A", "B", "C", "D"])
    await db.commit()
    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school.id,
            ScoreSegmentConfig.subject_code.is_(None),
        )
    )
    configs = list(result.scalars().all())
    assert len(configs) == 1
    assert configs[0].boundaries == [90, 75, 60]


from edu_cloud.modules.analytics.segment_service import (
    compute_segments, get_segment_config, upsert_segment_config,
    list_segment_configs,
)


def test_compute_segments_default():
    scores = [95, 82, 73, 65, 50, 88, 40]
    result = compute_segments(
        scores=scores, max_score=100.0,
        boundaries=[85, 70, 60], labels=["优秀", "良好", "及格", "不及格"],
    )
    assert len(result) == 4
    excellent = next(s for s in result if s["label"] == "优秀")
    assert excellent["count"] == 2  # 95, 88
    poor = next(s for s in result if s["label"] == "不及格")
    assert poor["count"] == 2  # 50, 40


def test_compute_segments_empty():
    result = compute_segments(scores=[], max_score=100.0, boundaries=[85, 70, 60], labels=["优秀", "良好", "及格", "不及格"])
    assert all(s["count"] == 0 for s in result)


def test_compute_segments_empty_boundaries():
    """boundaries=[] 应退化为单段。"""
    result = compute_segments(scores=[80, 90], max_score=100.0, boundaries=[], labels=["全部"])
    assert len(result) == 1
    assert result[0]["count"] == 2
    assert result[0]["label"] == "全部"


def test_compute_segments_max_score_zero():
    result = compute_segments(scores=[0, 0], max_score=0.0, boundaries=[85, 70, 60], labels=["优秀", "良好", "及格", "不及格"])
    assert result[-1]["count"] == 2


async def test_upsert_create_default(db, school):
    cfg = await upsert_segment_config(
        db, school_id=school.id,
        boundaries=[90, 75, 60],
        labels=["A", "B", "C", "D"],
    )
    await db.commit()
    assert cfg.subject_code is None
    assert cfg.boundaries == [90, 75, 60]


async def test_upsert_update_existing(db, school):
    await upsert_segment_config(db, school.id, [85, 70, 60], ["优", "良", "及", "不"])
    await db.commit()
    await upsert_segment_config(db, school.id, [90, 75, 60], ["A", "B", "C", "D"])
    await db.commit()
    configs = await list_segment_configs(db, school.id)
    defaults = [c for c in configs if c.subject_code is None]
    assert len(defaults) == 1
    assert defaults[0].boundaries == [90, 75, 60]


async def test_upsert_validation_labels_count(db, school):
    with pytest.raises(Exception, match="labels 数量"):
        await upsert_segment_config(db, school.id, [85, 70, 60], ["A", "B"])


async def test_upsert_validation_order(db, school):
    with pytest.raises(Exception, match="降序"):
        await upsert_segment_config(db, school.id, [60, 70, 85], ["A", "B", "C", "D"])


async def test_get_config_subject_override(db, school):
    await upsert_segment_config(db, school.id, [85, 70, 60], ["优", "良", "及", "不"])
    await db.commit()
    await upsert_segment_config(db, school.id, [90, 80, 60], ["A", "B", "C", "D"], subject_code="math")
    await db.commit()

    b, l = await get_segment_config(db, school.id, subject_code="math")
    assert b == [90, 80, 60]

    b2, l2 = await get_segment_config(db, school.id, subject_code="chinese")
    assert b2 == [85, 70, 60]  # fallback to school default


async def test_upsert_subject_override_is_update_not_duplicate(db, school):
    """F001: 同校同科目 override 二次 upsert 应更新而非重复创建。"""
    await upsert_segment_config(
        db, school.id, [90, 80, 60], ["A", "B", "C", "D"], subject_code="math",
    )
    await db.commit()
    # 第二次 upsert 同科目
    await upsert_segment_config(
        db, school.id, [95, 85, 70], ["S", "A", "B", "C"], subject_code="math",
    )
    await db.commit()
    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school.id,
            ScoreSegmentConfig.subject_code == "math",
        )
    )
    configs = list(result.scalars().all())
    assert len(configs) == 1, f"Expected 1 math config, got {len(configs)}"
    assert configs[0].boundaries == [95, 85, 70]
    assert configs[0].labels == ["S", "A", "B", "C"]


async def test_get_config_hardcoded_fallback(db, school):
    b, l = await get_segment_config(db, school.id)
    assert b == [85, 70, 60]
    assert l == ["优秀", "良好", "及格", "不及格"]
