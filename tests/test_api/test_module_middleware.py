from edu_cloud.api.module_middleware import (
    ROUTE_MODULE_MAP,
    _longest_prefix_match,
    resolve_module_code,
)


def test_bank_api_belongs_to_research_module():
    assert ROUTE_MODULE_MAP['/api/v1/bank'] == 'research'


def test_profile_api_belongs_to_study_analytics_module():
    # R4 子任务（0.6C）：学情画像后端门控实装，收口 profile-backend-fail-open drift。
    # profile router 全端点为学情语义（trend/knowledge/error-patterns/class-weakness/ai-diagnosis），归 study_analytics。
    assert ROUTE_MODULE_MAP['/api/v1/profile'] == 'study_analytics'


# ===== Phase 0.7B item3（R5-DC2）：前缀匹配规则与守卫对齐为「最长前缀优先」=====
# 旧中间件用 dict 插入序首匹配（startswith 命中即 break），与守卫 _actual_gating 的
# sorted(route_map, key=len, reverse=True) 最长前缀不一致——重叠前缀映射到不同模块时运行时会命中错误模块
# （守卫绿但运行时漂移）。修复：抽 _longest_prefix_match + resolve_module_code，与守卫同算法。

def test_longest_prefix_match_picks_longest_overlap():
    # 重叠前缀映射到不同模块 → 必须命中最长前缀（dict 插入序首匹配会命中 /api/v1/foo='A' → 失败）
    route_map = {"/api/v1/foo": "alpha", "/api/v1/foo-bar": "beta"}
    assert _longest_prefix_match("/api/v1/foo-bar/x", route_map) == "beta"
    assert _longest_prefix_match("/api/v1/foo/x", route_map) == "alpha"


def test_longest_prefix_match_no_match_returns_none():
    assert _longest_prefix_match("/api/v1/unmapped", {"/api/v1/foo": "alpha"}) is None


def test_resolve_module_code_exempt_returns_none():
    # 豁免前缀（基础设施）→ None（不门控），exempt-first 与中间件 dispatch 一致
    assert resolve_module_code("/api/v1/health/check") is None
    assert resolve_module_code("/api/v1/auth/login") is None


def test_resolve_module_code_gated_uses_real_map():
    # 真实 map：knowledge-tree 经最长前缀命中 research（不被更短的 /api/v1/knowledge 抢匹配）
    assert resolve_module_code("/api/v1/knowledge-tree/list") == "research"
    assert resolve_module_code("/api/v1/bank/items") == "research"
    assert resolve_module_code("/api/v1/profile/trend") == "study_analytics"


def test_resolve_module_code_unmapped_returns_none():
    assert resolve_module_code("/api/v1/totally-unknown") is None
