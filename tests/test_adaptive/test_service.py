import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from edu_cloud.modules.adaptive.service import diagnose_and_recommend


@pytest.mark.asyncio
async def test_diagnose_returns_da_states_and_path():
    """诊断应返回 DA 状态列表和学习路径"""
    db = AsyncMock()

    mastery1 = MagicMock(da_id="da:001", mastery_prob=0.3, attempt_count=5)
    mastery2 = MagicMock(da_id="da:002", mastery_prob=0.8, attempt_count=10)
    db.execute = AsyncMock(return_value=MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mastery1, mastery2])))
    ))

    with patch("edu_cloud.modules.adaptive.service.get_da_study_unit_map") as mock_su_map, \
         patch("edu_cloud.modules.adaptive.service.get_su_prerequisites") as mock_prereqs, \
         patch("edu_cloud.modules.adaptive.service.get_candidate_questions") as mock_questions:

        mock_su_map.return_value = {"da:001": "su1", "da:002": "su2"}
        mock_prereqs.return_value = {}
        mock_questions.return_value = [
            {"id": "q1", "transfer_band": "near", "da_id": "da:001"},
        ]

        result = await diagnose_and_recommend(
            db, student_id="s1", school_id="school1",
        )

        assert "da_states" in result
        assert "learning_path" in result
        assert "recommended_questions" in result
        # Verify da_states has actual content from mastery rows
        assert len(result["da_states"]) == 2
        da_ids_in_result = {d["da_id"] for d in result["da_states"]}
        assert "da:001" in da_ids_in_result
        assert "da:002" in da_ids_in_result
        # Verify mastery values propagated
        weak_da = next(d for d in result["da_states"] if d["da_id"] == "da:001")
        assert weak_da["state"] == "weak"
        assert weak_da["mastery"] == 0.3


def test_tool_registered():
    """F001: 验证工具在新引擎注册"""
    from edu_cloud.ai.engine.tools import collect_all_tools
    all_tools = collect_all_tools()
    names = {getattr(fn, "_edu_meta").name for fn in all_tools if getattr(fn, "_edu_meta", None)}
    assert "diagnose_and_recommend" in names
