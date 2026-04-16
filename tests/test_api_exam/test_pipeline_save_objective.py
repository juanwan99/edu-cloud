"""pipeline save_objective_fn 工厂测试。"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_session_factory():
    """构造 mock async session factory。"""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.add = MagicMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def factory():
        yield mock_session

    return factory, mock_session


class TestBuildPipelineSaveObjectiveFn:
    async def test_save_objective_single_group(self, mock_session_factory):
        """单题组：(group_id, row_index) 精确映射到 question_id。"""
        factory, mock_session = mock_session_factory
        from edu_cloud.modules.scan.pipeline_router import build_pipeline_save_objective_fn

        # choice_group regions: qg_indexno=1 表示从第 1 题开始
        regions = [
            {"id": "OBJ01", "type": "choice_group", "qg_indexno": 1, "rows": 2},
        ]
        # questions: 按 group_id + 组内序号映射
        questions_by_group = {
            "OBJ01": [
                {"id": "q-obj-1", "row_index": 1, "correct_answer": "A", "max_score": 3.0},
                {"id": "q-obj-2", "row_index": 2, "correct_answer": "C", "max_score": 3.0},
            ],
        }

        save_fn = build_pipeline_save_objective_fn(
            regions=regions,
            questions_by_group=questions_by_group,
            exam_id="e1",
            subject_id="s1",
            school_id="sc1",
            _session_factory=factory,
        )

        await save_fn(
            exam_id="e1", subject_id="s1", student_id="stu1",
            group_id="OBJ01", row_index=1,
            detected_answer="A", fill_ratios={"A": 0.8, "B": 0.05},
            anomaly=False, school_id="sc1",
        )

        assert mock_session.add.call_count == 1
        added = mock_session.add.call_args[0][0]
        assert added.question_id == "q-obj-1"
        assert added.detected_answer == "A"
        assert added.score == 3.0

    async def test_save_objective_multi_group_no_cross_contamination(self, mock_session_factory):
        """多题组：OBJ01 row 1 和 OBJ02 row 1 映射到不同 question。
        反例防护 CE-001：全局枚举会把两个 row 1 写到同一个 question。"""
        factory, mock_session = mock_session_factory
        from edu_cloud.modules.scan.pipeline_router import build_pipeline_save_objective_fn

        regions = [
            {"id": "OBJ01", "type": "choice_group", "qg_indexno": 1, "rows": 1},
            {"id": "OBJ02", "type": "choice_group", "qg_indexno": 2, "rows": 1},
        ]
        questions_by_group = {
            "OBJ01": [{"id": "q-1", "row_index": 1, "correct_answer": "A", "max_score": 3.0}],
            "OBJ02": [{"id": "q-5", "row_index": 1, "correct_answer": "B", "max_score": 5.0}],
        }

        save_fn = build_pipeline_save_objective_fn(
            regions=regions, questions_by_group=questions_by_group,
            exam_id="e1", subject_id="s1", school_id="sc1",
            _session_factory=factory,
        )

        # OBJ01 row 1
        await save_fn(exam_id="e1", subject_id="s1", student_id="stu1",
                       group_id="OBJ01", row_index=1, detected_answer="A",
                       fill_ratios={}, anomaly=False, school_id="sc1")
        # OBJ02 row 1
        await save_fn(exam_id="e1", subject_id="s1", student_id="stu1",
                       group_id="OBJ02", row_index=1, detected_answer="B",
                       fill_ratios={}, anomaly=False, school_id="sc1")

        assert mock_session.add.call_count == 2
        first = mock_session.add.call_args_list[0][0][0]
        second = mock_session.add.call_args_list[1][0][0]
        assert first.question_id == "q-1"
        assert second.question_id == "q-5"

    async def test_orphan_group_skipped(self, mock_session_factory):
        """group_id 找不到映射时 skip 不报错。"""
        factory, mock_session = mock_session_factory
        from edu_cloud.modules.scan.pipeline_router import build_pipeline_save_objective_fn

        save_fn = build_pipeline_save_objective_fn(
            regions=[], questions_by_group={},
            exam_id="e1", subject_id="s1", school_id="sc1",
            _session_factory=factory,
        )
        await save_fn(exam_id="e1", subject_id="s1", student_id="stu1",
                       group_id="UNKNOWN", row_index=1, detected_answer="A",
                       fill_ratios={}, anomaly=False, school_id="sc1")
        assert mock_session.add.call_count == 0
