import pytest
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.ai.intent_resolver import IntentResolver, DOMAIN_RULES
from edu_cloud.ai.registry import ToolSpec


def _make_spec(name, domain="general"):
    return ToolSpec(
        name=name, description=f"Tool {name}", parameters={},
        func=AsyncMock(), domain=domain,
    )


def test_rule_match_chinese_exam():
    resolver = IntentResolver(llm_client=None)
    domains = resolver.resolve_by_rules("帮我查一下这次考试的成绩")
    assert "analytics" in domains  # "成绩"


def test_rule_match_chinese_student():
    resolver = IntentResolver(llm_client=None)
    domains = resolver.resolve_by_rules("三年一班的学生名单")
    assert "student" in domains


def test_rule_match_multi_domain():
    resolver = IntentResolver(llm_client=None)
    domains = resolver.resolve_by_rules("查一下这次考试每个学生的成绩排名")
    assert "analytics" in domains or "student" in domains
    assert len(domains) <= 3


def test_rule_no_match():
    resolver = IntentResolver(llm_client=None)
    domains = resolver.resolve_by_rules("你好，今天天气怎么样？")
    assert domains is None


@pytest.mark.asyncio
async def test_resolve_with_rules():
    all_tools = [
        _make_spec("get_scores", domain="analytics"),
        _make_spec("get_students", domain="student"),
        _make_spec("get_calendar", domain="calendar"),
    ]
    resolver = IntentResolver(llm_client=None)
    result = await resolver.resolve("帮我看看成绩", all_tools)
    assert any(t.name == "get_scores" for t in result)
    assert not any(t.name == "get_calendar" for t in result)
    assert resolver.last_domains == ["analytics"]


@pytest.mark.asyncio
async def test_resolve_fallback_to_all():
    """无匹配时返回全部工具"""
    all_tools = [_make_spec("t1"), _make_spec("t2")]
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value=MagicMock(content=""))
    resolver = IntentResolver(llm_client=mock_llm)
    result = await resolver.resolve("随便聊聊", all_tools)
    assert len(result) == 2  # 全部返回


@pytest.mark.asyncio
async def test_resolve_domain_filter_empty_fallback():
    """过滤后为空时兜底返回全部"""
    all_tools = [_make_spec("only_calendar", domain="calendar")]
    resolver = IntentResolver(llm_client=None)
    # "成绩" 匹配 analytics，但工具里没有 analytics domain
    result = await resolver.resolve("成绩分析", all_tools)
    assert len(result) == 1  # 兜底
