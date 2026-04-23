"""Tests for two-step grading pipeline: OCR -> grade text."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from edu_cloud.modules.grading.llm_client import GradeResponse


@pytest.mark.asyncio
async def test_grade_single_two_step():
    from edu_cloud.workers.grading import _grade_single

    mock_llm = MagicMock()
    mock_llm.extract_text = AsyncMock(return_value=[
        {"blankNo": "1-1", "subQ": "(1)", "text": "动物细胞"},
    ])
    mock_llm.grade_text = AsyncMock(return_value=GradeResponse(
        score=2, max_score=2, feedback="correct", confidence=0.95, raw_content='{"score":2}'
    ))

    ad = {
        "answer_id": "a1", "question_id": "q1",
        "question_name": "6", "question_max_score": 2,
        "image_path": "/tmp/fake.png", "question_type": "essay",
        "subject_code": "biology",
    }
    rubrics = {"q1": [{"blankNo": "1-1", "score": 2, "standardAnswer": "动物细胞", "context": "ctx", "judgingRules": "rules"}]}

    with patch("edu_cloud.workers.grading._read_image_b64", return_value="A" * 10000):
        result, error = await _grade_single(mock_llm, ad, rubrics)

    assert error is None
    assert result["score"] == 2
    mock_llm.extract_text.assert_called_once()
    mock_llm.grade_text.assert_called_once()


@pytest.mark.asyncio
async def test_grade_single_blank_detection():
    """Small images (< 5KB base64 ~ 6800 chars) are treated as blank."""
    from edu_cloud.workers.grading import _grade_single

    mock_llm = MagicMock()
    ad = {
        "answer_id": "a2", "question_id": "q1",
        "question_name": "6", "question_max_score": 5,
        "image_path": "/tmp/blank.png", "question_type": "essay",
        "subject_code": "biology",
    }
    rubrics = {"q1": [{"blankNo": "1-1", "score": 5, "standardAnswer": "X"}]}

    # Return a tiny base64 string (< 6800 chars = ~5KB)
    with patch("edu_cloud.workers.grading._read_image_b64", return_value="x" * 100):
        result, error = await _grade_single(mock_llm, ad, rubrics)

    assert error is None
    assert result["score"] == 0
    assert result["feedback"] == "空白卷"
    mock_llm.extract_text.assert_not_called()
    mock_llm.grade_text.assert_not_called()


@pytest.mark.asyncio
async def test_grade_single_fallback_no_subject_prompt():
    """When subject prompt not found, falls back to legacy single-step grading."""
    from edu_cloud.workers.grading import _grade_single

    mock_llm = MagicMock()
    mock_llm.grade = AsyncMock(return_value=GradeResponse(
        score=3, max_score=5, feedback="partial", confidence=0.7, raw_content='{"score":3}'
    ))

    ad = {
        "answer_id": "a3", "question_id": "q1",
        "question_name": "6", "question_max_score": 5,
        "image_path": "/tmp/fake.png", "question_type": "essay",
        "subject_code": "unknown_subject",  # no prompt module for this
    }
    rubrics = {"q1": [{"blankNo": "1-1", "score": 5, "answer": "X"}]}

    with patch("edu_cloud.workers.grading._read_image_b64", return_value="A" * 10000):
        result, error = await _grade_single(mock_llm, ad, rubrics)

    assert error is None
    assert result["score"] == 3
    mock_llm.grade.assert_called_once()
