import pytest
from sqlalchemy import inspect
from edu_cloud.modules.adaptive.models import (
    AnswerLog, StudentDaMastery, DaBktParams,
    DaKnowledgePointMap, QuestionDaOverride,
    AdaptiveCard, DaCatalogSnapshot,
)


def test_answer_log_fields():
    cols = {c.name for c in inspect(AnswerLog).columns}
    assert "student_id" in cols
    assert "da_ids" in cols
    assert "correct" in cols
    assert "source_type" in cols


def test_student_da_mastery_fields():
    cols = {c.name for c in inspect(StudentDaMastery).columns}
    assert "da_id" in cols
    assert "mastery_prob" in cols
    assert "attempt_count" in cols


def test_da_bkt_params_fields():
    cols = {c.name for c in inspect(DaBktParams).columns}
    assert "p_init" in cols
    assert "p_transit" in cols
    assert "p_guess" in cols
    assert "p_slip" in cols


def test_da_knowledge_point_map_fields():
    cols = {c.name for c in inspect(DaKnowledgePointMap).columns}
    assert "da_id" in cols
    assert "knowledge_point_id" in cols
    assert "weight" in cols
