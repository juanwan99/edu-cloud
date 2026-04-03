import json
import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.task_planner import TaskPlanner, Plan, Task
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolSpec
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def _make_specs():
    async def _noop(i, c): return ToolResult(success=True, data=None)
    return [
        ToolSpec(name="get_exam_summary", description="Get exam summary", parameters={}, func=_noop,
                 is_read_only=True, sensitivity="school"),
        ToolSpec(name="get_class_stats", description="Get class stats", parameters={}, func=_noop,
                 is_read_only=True, sensitivity="school"),
        ToolSpec(name="generate_report", description="Generate report", parameters={}, func=_noop,
                 is_read_only=False, sensitivity="school", risk_level="medium"),
    ]


@pytest.mark.asyncio
async def test_maybe_plan_returns_none_for_simple():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content='{"plan": null}',
        usage=TokenUsage(10, 5),
    ))
    planner = TaskPlanner()
    plan = await planner.maybe_plan("数学平均分多少", tier=2, adapter=adapter, available_tools=_make_specs())
    assert plan is None


@pytest.mark.asyncio
async def test_maybe_plan_returns_plan_for_complex():
    plan_json = json.dumps({"plan": [
        {"description": "收集成绩数据", "tools_hint": ["get_exam_summary", "get_class_stats"], "depends_on": []},
        {"description": "生成报告", "tools_hint": ["generate_report"], "depends_on": ["0"]},
    ]})
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content=plan_json,
        usage=TokenUsage(50, 30),
    ))
    planner = TaskPlanner()
    plan = await planner.maybe_plan("全面分析三年级", tier=2, adapter=adapter, available_tools=_make_specs())
    assert plan is not None
    assert len(plan.tasks) == 2
    assert plan.tasks[0].description == "收集成绩数据"
    assert plan.tasks[1].depends_on == ["0"]


@pytest.mark.asyncio
async def test_maybe_plan_skipped_for_tier3():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    planner = TaskPlanner()
    plan = await planner.maybe_plan("全面分析", tier=3, adapter=adapter, available_tools=_make_specs())
    assert plan is None


def test_schedule_topological_order():
    planner = TaskPlanner()
    plan = Plan(goal="test", tasks=[
        Task(id="0", description="first"),
        Task(id="1", description="second", depends_on=["0"]),
        Task(id="2", description="third", depends_on=["1"]),
    ])
    order = list(planner.schedule(plan))
    assert [t.id for t in order] == ["0", "1", "2"]


def test_schedule_parallel_independent():
    planner = TaskPlanner()
    plan = Plan(goal="test", tasks=[
        Task(id="0", description="a"),
        Task(id="1", description="b"),
        Task(id="2", description="c", depends_on=["0", "1"]),
    ])
    order = list(planner.schedule(plan))
    ids = [t.id for t in order]
    assert ids[-1] == "2"
    assert set(ids[:2]) == {"0", "1"}
