from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from edu_cloud.ai.engine.tools import grading_ops
from edu_cloud.modules.grading.service import GradingAssignmentService


class _DbContext:
    def __init__(self) -> None:
        self.db = object()

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        deps=SimpleNamespace(
            data_scope=SimpleNamespace(school_id="school-1"),
            get_db=_DbContext,
        )
    )


def test_assign_grading_task_calls_auto_assign_with_keyword_arguments(monkeypatch):
    asyncio.run(_assert_assign_grading_task_calls_auto_assign_with_keyword_arguments(monkeypatch))


async def _assert_assign_grading_task_calls_auto_assign_with_keyword_arguments(monkeypatch):
    captured = {}

    async def fake_auto_assign(
        db,
        *,
        exam_id: str,
        subject_id: str,
        question_ids: list[str],
        teacher_ids: list[str],
        school_id: str,
        total_count_per_question: int,
    ):
        captured.update(
            {
                "db": db,
                "exam_id": exam_id,
                "subject_id": subject_id,
                "question_ids": question_ids,
                "teacher_ids": teacher_ids,
                "school_id": school_id,
                "total_count_per_question": total_count_per_question,
            }
        )
        return [{"assignment_id": "assignment-1"}]

    monkeypatch.setattr(
        GradingAssignmentService,
        "auto_assign",
        staticmethod(fake_auto_assign),
    )

    result = await grading_ops.assign_grading_task.__wrapped__(
        _ctx(),
        "exam-1",
        "subject-1",
        ["q1", "q2"],
        ["teacher-1", "teacher-2"],
        12,
    )

    assert json.loads(result) == [{"assignment_id": "assignment-1"}]
    assert captured["db"] is not None
    assert captured["exam_id"] == "exam-1"
    assert captured["subject_id"] == "subject-1"
    assert captured["question_ids"] == ["q1", "q2"]
    assert captured["teacher_ids"] == ["teacher-1", "teacher-2"]
    assert captured["school_id"] == "school-1"
    assert captured["total_count_per_question"] == 12
