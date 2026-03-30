import re

DOMAIN_RULES: dict[str, list[str]] = {
    "exam": ["考试", "科目", "试卷", "exam", "subject", "paper"],
    "student": ["学生", "班级", "名单", "student", "class", "roster"],
    "analytics": ["成绩", "分数", "分析", "排名", "统计", "score", "rank", "stats"],
    "knowledge": ["知识点", "课标", "教材", "knowledge", "curriculum"],
    "bank": ["错题", "题库", "error book", "question bank"],
    "profile": ["画像", "趋势", "薄弱", "profile", "trend", "weakness"],
    "action": ["报告", "评语", "生成", "report", "comment", "generate"],
    "studio": ["文档", "论文", "document", "paper writing"],
    "calendar": ["日历", "校历", "通知", "calendar", "notification"],
}


class IntentResolver:
    def __init__(self, llm_client):
        self._patterns: dict[str, re.Pattern] = {}
        for domain, keywords in DOMAIN_RULES.items():
            escaped = [re.escape(k) for k in keywords]
            self._patterns[domain] = re.compile("|".join(escaped), re.IGNORECASE)
        self._llm = llm_client
        self.last_domains: list[str] = []

    def resolve_by_rules(self, message: str) -> list[str] | None:
        matched = []
        for domain, pattern in self._patterns.items():
            if pattern.search(message):
                matched.append(domain)
        return matched[:3] if matched else None

    async def resolve(self, message: str, available_tools: list) -> list:
        domains = self.resolve_by_rules(message)

        if domains is None and self._llm is not None:
            domains = await self._llm_classify(message)

        if not domains:
            self.last_domains = []
            return available_tools

        self.last_domains = domains
        selected = [t for t in available_tools if t.domain in domains]
        return selected if selected else available_tools

    async def _llm_classify(self, message: str) -> list[str]:
        from edu_cloud.ai.schemas import ChatMessage

        prompt = (
            "你是意图分类器。根据用户消息，返回 1-3 个最相关的域。"
            f"可选域：{', '.join(DOMAIN_RULES.keys())}。"
            "只返回域名，用逗号分隔，不要其他内容。"
        )
        try:
            response = await self._llm.chat(
                messages=[
                    ChatMessage(role="system", content=prompt),
                    ChatMessage(role="user", content=message),
                ],
            )
            text = response.content if hasattr(response, "content") else str(response)
            return [d.strip() for d in text.split(",") if d.strip() in DOMAIN_RULES]
        except Exception:
            return []
