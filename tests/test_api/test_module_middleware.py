from edu_cloud.api.module_middleware import (
    ROUTE_MODULE_MAP,
    _longest_prefix_match,
    _prefix_matches,
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


# ===== Phase 0.7B item4（后端 fail-open drift）：conduct / exam-imports 补门控 =====
# 参照 0.6C profile 处置：前端 /conduct、/exam-import 已标 moduleCode（authGuard 已 fail-close 导航），
# 后端补门控为同源 defense-in-depth——模块关闭=功能不可用（与 exam/grading/profile 一致），enabled 校无变化。
# academic 不在此列：前端 /academic/* 仅 permission 无 moduleCode（未门控），后端单独 gating 会让有
# manage_scheduling 但 teaching 关闭的校 403 破坏页面（teaching-frontend-unwired drift），保留为 known_drift。

def test_conduct_api_gated_to_conduct_module():
    assert ROUTE_MODULE_MAP['/api/v1/conduct'] == 'conduct'
    assert resolve_module_code('/api/v1/conduct/records') == 'conduct'


def test_exam_imports_api_gated_to_exam_module():
    assert ROUTE_MODULE_MAP['/api/v1/exam-imports'] == 'exam'
    assert resolve_module_code('/api/v1/exam-imports/preview') == 'exam'


def test_exam_imports_does_not_shadow_exams_prefix():
    # /api/v1/exams 与 /api/v1/exam-imports 前缀不重叠（最长前缀下各自归 exam，互不影响）
    assert resolve_module_code('/api/v1/exams/123') == 'exam'
    assert resolve_module_code('/api/v1/exam-imports/123') == 'exam'


# ===== Phase 0.7B item5（hygiene drift）：menus/portal/grades/teachers/client-logs 显式入 exempt =====
# 这些入口当前未在 MAP 也未在 EXEMPT → resolve 返回 None（pass-through）。加入 EXEMPT 后仍 None（exempt），
# 行为零变更，仅令豁免意图显式（守卫据此从 pass-through 收口为 exempt，删 hygiene drift）。

def test_hygiene_routes_pass_through_unchanged():
    for path in ('/api/v1/menus', '/api/v1/portal/home', '/api/v1/grades',
                 '/api/v1/teachers', '/api/v1/client-logs'):
        assert resolve_module_code(path) is None, path


# ===== Phase 0.7B item3 加固（codex-review R2 F-001 LOW design_concern）：段边界安全匹配 =====
# 裸 startswith 是字符前缀而非路径段边界：/api/v1/conductors 会被 /api/v1/conduct 误命中 → conduct。
# 最长前缀只解决「先匹配谁」，未解决「邻接同段名误命中」。修复：前缀须在段边界（== 或 prefix+'/'）匹配。

def test_prefix_matches_segment_boundary():
    assert _prefix_matches('/api/v1/conduct', '/api/v1/conduct') is True       # 精确
    assert _prefix_matches('/api/v1/conduct/records', '/api/v1/conduct') is True  # 子路径
    assert _prefix_matches('/api/v1/conductors', '/api/v1/conduct') is False   # 邻接同段名不命中
    assert _prefix_matches('/docsify', '/docs') is False                       # 豁免前缀同理


def test_resolve_module_code_no_adjacent_name_false_gating():
    # 邻接路由名不应被错误门控（裸 startswith 会误命中，段边界修复后返回 None）
    assert resolve_module_code('/api/v1/conductors') is None
    assert resolve_module_code('/api/v1/exam-imports-v2') is None
    # 合法路由与子路径仍正常门控
    assert resolve_module_code('/api/v1/conduct') == 'conduct'
    assert resolve_module_code('/api/v1/conduct/records') == 'conduct'
    assert resolve_module_code('/api/v1/exam-imports/preview') == 'exam'
