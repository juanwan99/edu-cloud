import pytest
from edu_cloud.ai.agent_spec import AgentSpec, select_slot


class TestAgentSpec:
    def test_create_basic(self):
        spec = AgentSpec(
            name="research",
            description="Research agent for literature search",
            tools=["search_literature", "knowledge_base_query"],
        )
        assert spec.name == "research"
        assert spec.tools == ["search_literature", "knowledge_base_query"]
        assert spec.model_tier is None
        assert spec.max_turns == 15
        assert spec.task_complexity == "retrieval"

    def test_create_with_forced_tier(self):
        spec = AgentSpec(
            name="writer",
            description="Writing agent",
            tools=["format_citation"],
            model_tier=1,
            task_complexity="generation",
        )
        assert spec.model_tier == 1

    def test_create_empty_tools(self):
        spec = AgentSpec(name="empty", description="No tools", tools=[])
        assert spec.tools == []


class TestSelectSlot:
    def test_forced_tier_1(self):
        spec = AgentSpec(name="x", description="x", tools=[], model_tier=1)
        assert select_slot(spec) == "enhanced"

    def test_forced_tier_2(self):
        spec = AgentSpec(name="x", description="x", tools=[], model_tier=2)
        assert select_slot(spec) == "primary"

    def test_forced_tier_3(self):
        spec = AgentSpec(name="x", description="x", tools=[], model_tier=3)
        assert select_slot(spec) == "basic"

    def test_auto_reasoning(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="reasoning")
        assert select_slot(spec) == "enhanced"

    def test_auto_generation(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="generation")
        assert select_slot(spec) == "enhanced"

    def test_auto_retrieval(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="retrieval")
        assert select_slot(spec) == "primary"

    def test_auto_data_query(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="data_query")
        assert select_slot(spec) == "primary"

    def test_auto_formatting(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="formatting")
        assert select_slot(spec) == "basic"

    def test_unknown_complexity_fallback(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="unknown_type")
        assert select_slot(spec) == "primary"
