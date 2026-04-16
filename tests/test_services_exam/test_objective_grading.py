"""选择题判分共享函数测试。"""
import pytest
from edu_cloud.modules.scan.objective_grading import grade_objective_answer


class TestGradeObjectiveAnswer:
    def test_correct_single(self):
        score, is_correct = grade_objective_answer("A", "A", 3.0)
        assert is_correct is True
        assert score == 3.0

    def test_incorrect_single(self):
        score, is_correct = grade_objective_answer("B", "A", 3.0)
        assert is_correct is False
        assert score == 0.0

    def test_correct_multi_order_insensitive(self):
        score, is_correct = grade_objective_answer("CA", "AC", 5.0)
        assert is_correct is True
        assert score == 5.0

    def test_incorrect_multi(self):
        score, is_correct = grade_objective_answer("AB", "AC", 5.0)
        assert is_correct is False
        assert score == 0.0

    def test_empty_detected(self):
        score, is_correct = grade_objective_answer("", "A", 3.0)
        assert is_correct is False
        assert score == 0.0

    def test_empty_correct(self):
        score, is_correct = grade_objective_answer("A", "", 3.0)
        assert is_correct is False
        assert score == 0.0

    def test_both_empty(self):
        score, is_correct = grade_objective_answer("", "", 3.0)
        assert is_correct is True
        assert score == 3.0

    def test_case_insensitive(self):
        score, is_correct = grade_objective_answer("a", "A", 3.0)
        assert is_correct is True
        assert score == 3.0

    def test_none_detected(self):
        score, is_correct = grade_objective_answer(None, "A", 3.0)
        assert is_correct is False
        assert score == 0.0

    def test_none_correct(self):
        score, is_correct = grade_objective_answer("A", None, 3.0)
        assert is_correct is False
        assert score == 0.0
