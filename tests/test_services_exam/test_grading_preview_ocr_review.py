import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from edu_cloud.modules.grading.llm_client import GradeResponse
from edu_cloud.modules.grading.ocr_validator import OCR_REVIEW_TEXT


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    def __init__(self, values):
        self._values = list(values)
        self.add = MagicMock()

    async def execute(self, _stmt):
        return _FakeResult(self._values.pop(0))


@pytest.mark.asyncio
async def test_grade_single_preview_llm_config_lookup_failure_fails_closed(tmp_path, monkeypatch):
    fake_pyzbar = ModuleType("pyzbar.pyzbar")
    fake_pyzbar.decode = lambda *_args, **_kwargs: []
    monkeypatch.setitem(sys.modules, "pyzbar", ModuleType("pyzbar"))
    monkeypatch.setitem(sys.modules, "pyzbar.pyzbar", fake_pyzbar)

    from edu_cloud.modules.grading.router import GradeSingleRequest, grade_single_answer

    image_path = tmp_path / "answer.bin"
    image_path.write_bytes(b"x" * 6000)

    school_id = "school-1"
    answer = SimpleNamespace(
        id="answer-1",
        question_id="question-1",
        school_id=school_id,
        image_path=str(image_path),
        question_type="fill_blank",
    )
    question = SimpleNamespace(
        id="question-1",
        subject_id="subject-1",
        school_id=school_id,
        question_type="fill_blank",
        max_score=2,
    )
    rubric = SimpleNamespace(criteria=[{"blankNo": "1-1", "subQ": "(1)", "score": 2}])
    subject = SimpleNamespace(code="biology")
    db = _FakeDB([answer, question, rubric, subject])

    role = SimpleNamespace(
        school_id=school_id,
        role="school_admin",
        subject_codes=None,
        class_ids=None,
        grade_ids=None,
    )
    current = {"current_role": role}

    with patch("edu_cloud.modules.grading.router.resolve_stored_file_path", return_value=image_path), \
         patch("edu_cloud.modules.grading.router.settings") as mock_settings, \
         patch(
             "edu_cloud.services.grading_workflow.get_llm_config",
             new_callable=AsyncMock,
             side_effect=RuntimeError("slot db unavailable"),
         ), \
         patch("edu_cloud.workers.grading._create_llm_client") as mock_create_llm:
        mock_settings.GEMINI_API_KEY = None
        mock_settings.VERTEX_AI_PROJECT = None

        with pytest.raises(HTTPException) as exc_info:
            await grade_single_answer(GradeSingleRequest(answer_id="answer-1"), db=db, current=current)

    assert exc_info.value.status_code == 503
    assert "LLM 配置读取失败" in str(exc_info.value.detail)
    mock_create_llm.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_grade_single_preview_ocr_review_needed_returns_422(tmp_path, monkeypatch):
    fake_pyzbar = ModuleType("pyzbar.pyzbar")
    fake_pyzbar.decode = lambda *_args, **_kwargs: []
    monkeypatch.setitem(sys.modules, "pyzbar", ModuleType("pyzbar"))
    monkeypatch.setitem(sys.modules, "pyzbar.pyzbar", fake_pyzbar)

    from edu_cloud.modules.grading.router import GradeSingleRequest, grade_single_answer

    image_path = tmp_path / "answer.bin"
    image_path.write_bytes(b"x" * 6000)

    school_id = "school-1"
    answer = SimpleNamespace(
        id="answer-1",
        question_id="question-1",
        school_id=school_id,
        image_path=str(image_path),
        question_type="fill_blank",
    )
    question = SimpleNamespace(
        id="question-1",
        subject_id="subject-1",
        school_id=school_id,
        question_type="fill_blank",
        max_score=2,
    )
    rubric = SimpleNamespace(
        criteria=[{"blankNo": "1-1", "subQ": "(1)", "score": 2, "standardAnswer": "动物细胞"}],
    )
    subject = SimpleNamespace(code="biology")
    db = _FakeDB([answer, question, rubric, subject])

    role = SimpleNamespace(
        school_id=school_id,
        role="school_admin",
        subject_codes=None,
        class_ids=None,
        grade_ids=None,
    )
    current = {"current_role": role}

    mock_llm = MagicMock()
    mock_llm.model = "test-model"
    mock_llm.extract_text = AsyncMock(return_value=[
        {"blankNo": "1-1", "subQ": "(1)", "text": OCR_REVIEW_TEXT},
    ])
    mock_llm.grade_text = AsyncMock()
    mock_llm.close = AsyncMock()

    with patch("edu_cloud.modules.grading.router.resolve_stored_file_path", return_value=image_path), \
         patch("edu_cloud.modules.grading.router.settings") as mock_settings, \
         patch("edu_cloud.services.grading_workflow.get_llm_config", new_callable=AsyncMock, return_value=("http://llm", "key", "model")), \
         patch("edu_cloud.workers.grading._create_llm_client", return_value=mock_llm):
        mock_settings.GEMINI_API_KEY = None
        mock_settings.VERTEX_AI_PROJECT = None

        with pytest.raises(HTTPException) as exc_info:
            await grade_single_answer(GradeSingleRequest(answer_id="answer-1"), db=db, current=current)

    assert exc_info.value.status_code == 422
    assert "OCR" in str(exc_info.value.detail)
    mock_llm.extract_text.assert_awaited_once()
    mock_llm.grade_text.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_grade_single_preview_passes_expected_details_count(tmp_path, monkeypatch):
    fake_pyzbar = ModuleType("pyzbar.pyzbar")
    fake_pyzbar.decode = lambda *_args, **_kwargs: []
    monkeypatch.setitem(sys.modules, "pyzbar", ModuleType("pyzbar"))
    monkeypatch.setitem(sys.modules, "pyzbar.pyzbar", fake_pyzbar)

    from edu_cloud.modules.grading.router import GradeSingleRequest, grade_single_answer

    image_path = tmp_path / "answer.bin"
    image_path.write_bytes(b"x" * 6000)

    school_id = "school-1"
    answer = SimpleNamespace(
        id="answer-1",
        question_id="question-1",
        school_id=school_id,
        image_path=str(image_path),
        question_type="fill_blank",
    )
    question = SimpleNamespace(
        id="question-1",
        subject_id="subject-1",
        school_id=school_id,
        question_type="fill_blank",
        max_score=2,
    )
    rubric = SimpleNamespace(
        criteria=[{"blankNo": "1-1", "subQ": "(1)", "score": 2, "standardAnswer": "cell"}],
    )
    subject = SimpleNamespace(code="biology")
    db = _FakeDB([answer, question, rubric, subject])

    role = SimpleNamespace(
        school_id=school_id,
        role="school_admin",
        subject_codes=None,
        class_ids=None,
        grade_ids=None,
    )
    current = {"current_role": role}

    mock_llm = MagicMock()
    mock_llm.model = "test-model"
    mock_llm.extract_text = AsyncMock(return_value=[
        {"blankNo": "1-1", "subQ": "(1)", "text": "cell"},
    ])
    mock_llm.grade_text = AsyncMock(return_value=GradeResponse(
        score=2,
        max_score=2,
        feedback="correct",
        confidence=0.95,
        raw_content='{"score": 2}',
        details=[{"blankNo": "1-1", "score": 2}],
    ))
    mock_llm.close = AsyncMock()

    with patch("edu_cloud.modules.grading.router.resolve_stored_file_path", return_value=image_path), \
         patch("edu_cloud.modules.grading.router.settings") as mock_settings, \
         patch("edu_cloud.services.grading_workflow.get_llm_config", new_callable=AsyncMock, return_value=("http://llm", "key", "model")), \
         patch("edu_cloud.workers.grading._create_llm_client", return_value=mock_llm):
        mock_settings.GEMINI_API_KEY = None
        mock_settings.VERTEX_AI_PROJECT = None

        result = await grade_single_answer(GradeSingleRequest(answer_id="answer-1"), db=db, current=current)

    assert result["score"] == 2
    assert mock_llm.grade_text.call_args.kwargs["expected_details_count"] == 1
