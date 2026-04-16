import pytest
from dataclasses import dataclass
from edu_cloud.ai.model_router import ModelRouter, ModelChoice


@dataclass
class MockSlot:
    slot_number: int
    api_url: str = "http://test"
    model: str = "test-model"


class TestModelRouter:
    def setup_method(self):
        self.router = ModelRouter()
        self.user_slots = [MockSlot(slot_number=1, model="deepseek-v3")]
        self.system_slots = [MockSlot(slot_number=99, model="claude-sonnet")]

    def test_enhanced_disabled_uses_user(self):
        choice = self.router.route(
            "分析成绩", self.user_slots, self.system_slots, enhanced_enabled=False
        )
        assert choice.tier == "standard"
        assert choice.slots == self.user_slots

    def test_simple_query_uses_user(self):
        choice = self.router.route(
            "张三的数学成绩是多少", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "standard"

    def test_complex_analysis_uses_system(self):
        choice = self.router.route(
            "分析全校数学成绩趋势并生成报告", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "advanced"

    def test_report_keyword_triggers_enhanced(self):
        choice = self.router.route(
            "帮我生成三年级数学诊断报告", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "advanced"

    def test_empty_system_slots_fallback(self):
        choice = self.router.route(
            "分析成绩趋势", self.user_slots, [], enhanced_enabled=True
        )
        assert choice.tier == "standard"
        assert choice.slots == self.user_slots

    def test_no_slots_raises(self):
        with pytest.raises(ValueError, match="无可用模型"):
            self.router.route("test", [], [], enhanced_enabled=False)

    def test_empty_message_uses_user(self):
        choice = self.router.route(
            "", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "standard"

    def test_multiple_keywords(self):
        choice = self.router.route(
            "对比各班成绩趋势", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "advanced"


class TestConfigurableKeywords:
    """P3-2: enhance keywords should be configurable via public route() API."""

    def test_custom_keywords_affects_route_decision(self):
        """Custom keyword should trigger 'advanced' tier via route()."""
        router = ModelRouter(enhance_keywords=["自定义词"])
        user_slots = [MockSlot(slot_number=1)]
        system_slots = [MockSlot(slot_number=99)]

        result = router.route("请自定义词处理", user_slots, system_slots, enhanced_enabled=True)
        assert result.tier == "advanced", "Custom keyword should route to advanced"

    def test_custom_keywords_non_match_stays_standard(self):
        """Non-matching message stays standard."""
        router = ModelRouter(enhance_keywords=["自定义词"])
        user_slots = [MockSlot(slot_number=1)]
        system_slots = [MockSlot(slot_number=99)]

        result = router.route("普通问题", user_slots, system_slots, enhanced_enabled=True)
        assert result.tier == "standard"

    def test_default_keywords_route_analysis(self):
        """Default keywords should route '分析' to advanced via route()."""
        router = ModelRouter()
        user_slots = [MockSlot(slot_number=1)]
        system_slots = [MockSlot(slot_number=99)]

        result = router.route("请分析数据", user_slots, system_slots, enhanced_enabled=True)
        assert result.tier == "advanced"
