import pytest
from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.modules.adaptive.da_mapper import resolve_da_ids

DaRow = namedtuple("DaRow", ["da_id", "weight"])


@pytest.mark.asyncio
async def test_override_takes_priority():
    """question_da_override 优先于知识点映射"""
    db = AsyncMock()
    override_row = MagicMock()
    override_row.da_ids = ["da:bio_sr:001", "da:bio_sr:002"]
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=override_row))

    result = await resolve_da_ids(db, question_id="q1", knowledge_point_ids=["kp1"])
    assert result == [("da:bio_sr:001", 1.0), ("da:bio_sr:002", 1.0)]


@pytest.mark.asyncio
async def test_fallback_to_kp_mapping():
    """无 override 时走知识点→DA 映射"""
    db = AsyncMock()

    row1 = DaRow(da_id="da:bio_sr:003", weight=0.8)
    row2 = DaRow(da_id="da:bio_sr:004", weight=0.5)
    map_result = MagicMock()
    map_result.all.return_value = [row1, row2]

    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        map_result,
    ])

    result = await resolve_da_ids(db, question_id="q1", knowledge_point_ids=["kp1", "kp2"])
    assert ("da:bio_sr:003", 0.8) in result
    assert ("da:bio_sr:004", 0.5) in result


@pytest.mark.asyncio
async def test_empty_kp_returns_empty():
    """无知识点时返回空"""
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    result = await resolve_da_ids(db, question_id="q1", knowledge_point_ids=[])
    assert result == []
