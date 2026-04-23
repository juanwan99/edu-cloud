import pytest
from edu_cloud.modules.grading.router import _validate_criteria


def test_valid_6_field_criteria():
    criteria = [
        {"blankNo": "1-1", "score": 5, "standardAnswer": "A", "context": "ctx", "judgingRules": "rules"},
        {"blankNo": "1-2", "score": 5, "standardAnswer": "B", "context": "ctx", "judgingRules": "rules"},
    ]
    _validate_criteria(criteria, 10.0)  # Should not raise


def test_backward_compat_answer_field():
    criteria = [{"blankNo": "1", "score": 10, "answer": "old format"}]
    _validate_criteria(criteria, 10.0)  # Should not raise (answer still accepted)


def test_missing_answer_and_standard_answer():
    criteria = [{"blankNo": "1", "score": 10}]
    with pytest.raises(Exception):
        _validate_criteria(criteria, 10.0)
