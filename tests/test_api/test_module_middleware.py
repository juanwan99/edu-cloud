from edu_cloud.api.module_middleware import (
    ROUTE_MODULE_MAP,
    _longest_prefix_match,
    _prefix_matches,
    module_enabled_default,
    resolve_module_code,
)
from edu_cloud.models.school_settings import DEFAULT_ENABLED, MODULE_CODES


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
# academic 在 0.7B 当时不补门控（前端 /academic/* 仅 permission 无 moduleCode），已由 0.7D 收口：
# 前端三 surface 接 teaching + 后端补门控，academic-backend-fail-open 与 teaching-frontend-unwired drift 均删除
# （见下方 Phase 0.7D 段与 test_academic_api_gated_to_teaching_module）。

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


# ===== Phase 0.7D（academic 双面 fail-open 收口）：academic 后端补 teaching 门控 =====
# 前端 /academic/* 已接 teaching 门控（routeAccess/router-meta/sidebar，authGuard 已 fail-close 导航），
# 后端 /api/v1/academic 补同源门控——模块关闭即功能不可用，闭合最后一处双面 fail-open。
# teaching 默认未开启（不在 DEFAULT_ENABLED）。0.7D 当时缺 SchoolModule(teaching) 行 → pass-through
# （仅依赖正常建校 init_school_modules 已建 enabled=False 行才 403），codex-review F-001 标记此缺行 fail-open；
# 0.7E 已收口：缺行按 module_enabled_default 镜像前端默认 → 非默认模块缺行 fail-closed 403（见文件末尾
# Phase 0.7E 段），与前端入口隐藏双面对齐（参照 0.6C profile / 0.7B conduct）。

def test_academic_api_gated_to_teaching_module():
    assert ROUTE_MODULE_MAP['/api/v1/academic'] == 'teaching'
    assert resolve_module_code('/api/v1/academic/semesters') == 'teaching'
    assert resolve_module_code('/api/v1/academic/timetable') == 'teaching'
    assert resolve_module_code('/api/v1/academic/teaching-plans') == 'teaching'


def test_academic_segment_boundary_no_false_gating():
    # 段边界安全：邻接同名前缀不应误命中 academic（裸 startswith 会让 /api/v1/academics 误命中）
    assert resolve_module_code('/api/v1/academics') is None
    # 精确与子路径正常门控
    assert resolve_module_code('/api/v1/academic') == 'teaching'


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


# ===== Phase 0.7E（F-001 absent-row fail-open 收口）：缺行默认语义对齐前端 =====
# 0.7D 遗留 F-001：中间件在缺 SchoolModule 行时 pass-through（fail-open），与前端 get_all_modules
# （school_settings_service.py:109 `existing[code].enabled if code in existing else (code in
# DEFAULT_ENABLED)`）不一致——非默认模块（teaching/research/study_analytics）缺行时前端隐藏入口、
# 后端却放行，形成 API fail-open。0.7E 修复：dispatch 抽 module_enabled_default(code,row)，缺行
# 镜像前端默认（在 DEFAULT_ENABLED 才启用）→ 非默认模块缺行 fail-closed 403；DEFAULT_ENABLED 模块
# 缺行仍 pass-through（行为不变）；显式 SchoolModule 行的 enabled 值始终优先。下列单测脱离
# DB/JWT/session 直测该纯函数语义（dispatch 第 208 行调用同一函数 → 单测即门控行为）。

def test_absent_row_non_default_modules_fail_closed():
    # 缺行（row=None）的非默认模块 → disabled → 中间件 403。F-001 核心收口。
    # academic 路由 → teaching；bank/knowledge → research；analytics/profile → study_analytics。
    for code in ('teaching', 'research', 'study_analytics'):
        assert module_enabled_default(code, None) is False, code


def test_absent_row_default_modules_pass_through_unchanged():
    # 缺行的 DEFAULT_ENABLED 模块 → enabled（pass-through，未引入回归，行为与 0.7E 前一致）。
    for code in DEFAULT_ENABLED:
        assert module_enabled_default(code, None) is True, code


def test_present_row_disabled_blocks_any_module():
    # 显式行 enabled=False → disabled（显式值优先于 DEFAULT_ENABLED 默认，含默认模块也能被关）。
    assert module_enabled_default('research', (False,)) is False     # 非默认显式关
    assert module_enabled_default('exam', (False,)) is False         # 默认模块显式关 → 403


def test_present_row_enabled_allows_any_module():
    # 显式行 enabled=True → enabled（显式值优先，含非默认模块开启后放行）。
    assert module_enabled_default('research', (True,)) is True       # 非默认显式开
    assert module_enabled_default('teaching', (True,)) is True       # 非默认显式开 → 允许


def test_academic_route_absent_teaching_row_fails_closed():
    # 端到端语义：/api/v1/academic 经 resolve 命中 teaching（非默认），缺 teaching 行 → fail-closed。
    # 串联路由解析（resolve_module_code）与缺行默认（module_enabled_default），表达 goal
    # 「academic 缺行 → 403」的完整链路。
    module_code = resolve_module_code('/api/v1/academic/semesters')
    assert module_code == 'teaching'
    assert module_enabled_default(module_code, None) is False


def test_absent_row_default_mirrors_frontend_source_of_truth():
    # 同源契约：中间件缺行默认逐模块镜像前端 get_all_modules 的 `else (code in DEFAULT_ENABLED)`，
    # 两端共用 models 真源 DEFAULT_ENABLED，防止默认集漂移造成前后端可见性/门控不一致。
    for code in MODULE_CODES:
        assert module_enabled_default(code, None) is (code in DEFAULT_ENABLED), code
