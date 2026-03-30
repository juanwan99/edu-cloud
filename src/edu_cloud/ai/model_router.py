from edu_cloud.ai.registry import ToolSpec

_COMPLEX_COMBOS = [
    {"analytics", "profile"},
    {"analytics", "knowledge"},
]


class ModelRouter:
    def select(self, intent_domains: list[str], tools: list[ToolSpec]) -> str:
        """返回 LLMSlot tier: "mini" | "standard" | "advanced" """
        if any(t.risk_level == "high" for t in tools):
            return "advanced"
        if len(intent_domains) >= 3:
            return "advanced"
        domain_set = set(intent_domains)
        if any(combo.issubset(domain_set) for combo in _COMPLEX_COMBOS):
            return "advanced"
        return "standard"
