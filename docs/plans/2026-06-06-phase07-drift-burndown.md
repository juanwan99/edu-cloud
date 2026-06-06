<!-- no-projectctl -->
# Phase 0.7 — 模块门控 drift burn-down

**来源**: Phase 0.6C R5 复审（`codex-review f82df2a..HEAD` = FINDINGS，reviewed_sha
`7f4c296`，log `docs/plans/.codex-review-2026-06-06_182801.log`）报出 2 个 scope 外、
预先存在的 design_concern；外加现存 known_drift 清单。0.6C 本体（R4 三 finding）已收口达标。

## Goal
逐项 burn down 模块门控「只登记不修复」的 known_drift 与跨层 fail 策略不一致，使前端各
surface 与后端中间件门控 fail 策略统一、守卫匹配规则与运行时中间件一致。

## Burn-down 清单（按优先级）
1. **R5-DC1 / codex F-001 (MED `security_design`) — ✅ 已处置于 Phase 0.7A（2026-06-06）**:
   **订正定性**——codex 引擎实测分类为 `security_design`（非可延期 `design_concern`）：菜单可见性
   层 `moduleMatches`(`routeAccess.js:46` 空列表=允许) + `AppHeader.moduleFallbacks` 与 authGuard
   (有校 fail-closed，`router.test.js:415` 实测) 策略不一致 → loadModules 失败/未加载/无模块时菜单/
   入口**视觉 fail-open**（authGuard 兜底实际访问，但 surface 自身是 fail-open 安全面缺陷）。
   **处置**: `routeAccess.js` 引入显式门控上下文 `{exempt,modulesLoaded,enabledModules}`
   (`createModuleGate`/`moduleGateFromAuth`)，4 个 surface（`AppSidebar`/`AppHeader`/`RoleSwitcher`/
   `DashboardPage`）统一经 `moduleGateFromAuth(auth)` 取门控、与 authGuard 数学等价 fail-closed；
   删 `AppHeader.moduleFallbacks` + `DashboardPage` 死代码 fallback；authGuard 不动。详见 NOW.md
   "Phase 0.7A"。证据: 定向前端 176 pass / governance 170 pass / 守卫 --check clean / meta-check green。
   R6 `codex-review` PASS 后本项结清。
2. **R5-DC2 (LOW, 规则漂移)**: 守卫 `_actual_gating` 最长前缀匹配 vs 中间件
   `ROUTE_MODULE_MAP` dict-first-match。当前 knowledge/knowledge-tree 同属 research 无影响；
   统一匹配规则以防未来重叠前缀误判（守卫绿但运行时命中另一模块）。
3. **后端 fail-open known_drift (security)**: academic / conduct / exam-imports
   (ROUTE_MODULE_MAP 缺 → pass-through)。参照 profile(0.6C 已修)逐个评估低风险后加门控。
4. **后端 hygiene known_drift**: menus/portal/grades/teachers/client-logs 未在 exempt list。
5. **前端 known_drift**: studio-entry 缺失(ux) / teaching 未接线(semantic)。

## Must Preserve
0.6C 成果：router_meta 完整门控面守卫 + profile 前后端门控(`70eeac2`/`b1a6d09`/`61ed166`) +
主体 4 commit(`f51342a`/`8606ac6`/`bf421e8`/`bd8be46`) 不回退；动态 fail-closed 不削弱。

## Must Not Change
- 不回退 Phase 0.5/0.6/0.6C 任何成果。
- **Portal homepage aggregation (Phase 1) 在本 burn-down 关键项（至少 R5-DC1）处置或设计者
  明确解锁前，保持 BLOCKED。**
