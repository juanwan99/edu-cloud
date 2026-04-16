import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from edu_cloud.modules.adaptive.updater import process_answer


@pytest.mark.asyncio
async def test_process_answer_creates_log_and_updates_mastery():
    """作答后应创建 answer_log 并更新 student_da_mastery"""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch("edu_cloud.modules.adaptive.updater.resolve_da_ids") as mock_resolve:
        mock_resolve.return_value = [("da:001", 1.0), ("da:002", 0.8)]

        # Mock get existing mastery (none exists)
        db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        ))

        result = await process_answer(
            db,
            student_id="s1",
            question_id="q1",
            knowledge_point_ids=["kp1"],
            correct=True,
            school_id="school1",
            exam_id="exam1",
            source_type="exam",
        )

        assert result["da_count"] == 2
        # Verify AnswerLog was created (first add call)
        assert db.add.call_count >= 1
        first_add_arg = db.add.call_args_list[0][0][0]
        from edu_cloud.modules.adaptive.models import AnswerLog
        assert isinstance(first_add_arg, AnswerLog)
        assert first_add_arg.exam_id == "exam1"
        assert first_add_arg.student_id == "s1"


@pytest.mark.asyncio
async def test_process_answer_updates_existing_mastery():
    """已有 mastery 记录时应更新而非创建"""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    with patch("edu_cloud.modules.adaptive.updater.resolve_da_ids") as mock_resolve:
        mock_resolve.return_value = [("da:001", 1.0)]

        # Mock existing mastery
        existing = MagicMock()
        existing.mastery_prob = 0.5
        existing.attempt_count = 10
        existing.correct_count = 7
        # First call: _get_or_create_mastery (returns existing)
        # Second call: _get_bkt_params (returns None → use defaults)
        db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=existing)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ])

        result = await process_answer(
            db,
            student_id="s1",
            question_id="q1",
            knowledge_point_ids=["kp1"],
            correct=True,
            school_id="school1",
        )

        assert existing.attempt_count == 11
        assert existing.correct_count == 8
        assert existing.mastery_prob != 0.5  # should be updated by BKT
