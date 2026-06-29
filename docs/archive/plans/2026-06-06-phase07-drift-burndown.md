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
   "Phase 0.7A"。证据: 定向前端 181 pass / governance 170 pass / 守卫 --check clean / meta-check green。
   **复审收口**: `codex-review range:f82df2a..HEAD` R6→R8 迭代——R6 报 RoleSwitcher 动态路由**模块**维度
   fail-open（MED，已修 `e1ff2e1`）；R7 报同根因**权限**维度 fail-open（MED，`/exams/:examId/ai-grading/
   :subjectId` 需 manage_grading 但精确表匹配不到），完整修复 `3f98a30`：抽 `canAccessMatchedRoute`
   覆盖静态精确表 ∪ 动态 `route.meta`（权限+模块两维），与 authGuard 同源；R8 **零 MED/security finding**。
   **本项（连同 R6/R7 同根因变体）已结清**。
2. **R5-DC2 (LOW, 规则漂移) — ✅ 已收口（`90c8a93`，0.7B item3）**: 守卫 `_actual_gating` 最长前缀匹配 vs 中间件
   `ROUTE_MODULE_MAP` dict-first-match。**处置**: `module_middleware.py` 抽 `resolve_module_code`/
   `_longest_prefix_match`，匹配规则由 dict-first 改最长前缀，与守卫严格同算法（exempt-first → 最长前缀）；
   守卫 `_actual_gating` 同步重排 exempt-first（exempt/gated 前缀集互斥，inert）。无行为变更（重叠前缀今同模块）。
   证据: 中间件 7 passed（含重叠前缀命中最长 RED→GREEN）+ 守卫 55 passed + --check clean。
3. **R8 LOW `defect_fix`（CRLF 尾随空白）— ✅ 已收口（`0d78f55`，0.7B item2）**: `router.test.js` +
   `auth.js` 全文件 CRLF→LF。纯行尾翻转零内容变更（`git diff --ignore-cr-at-eol --stat` 为空），转换后
   60 passed。**作用域限定**: 仅 R8 点名的 2 个活跃源文件；全仓 Windows 遗留 CRLF（~80 活跃源文件含业务 UI）
   属预存条件、不在 0.7B 范围、不碰业务 UI，留作未来独立 .gitattributes 规范化候选。
4. **后端 fail-open known_drift (security) — ✅ 部分收口（`c989e09`，0.7B item4）**:
   - **conduct / exam-imports — 已补门控**: `ROUTE_MODULE_MAP` 加 `/api/v1/conduct→conduct`、
     `/api/v1/exam-imports→exam`。前端已标 moduleCode、authGuard 0.7A 已 fail-close 导航，后端补同源门控=
     模块关即不可用（enabled 校无变化，disabled 校直达 API 403=正确收口）。证据: conduct+exam_import 153 passed。
   - **academic — 保留 known_drift（不补门控）**: 前端 `/academic/*` 仅 `permission:manage_scheduling`、无
     moduleCode（teaching-frontend-unwired）。单独后端 gating 会让有该权限但 teaching 关闭的校 403 破坏页面，
     需前端 teaching wiring 配套——超出 0.7B「不改业务 UI」范围。保留 `academic-backend-fail-open` 登记。
5. **后端 hygiene known_drift — ✅ 已收口（`c989e09`，0.7B item5）**: menus/portal/grades/teachers/client-logs
   入 `EXEMPT_PREFIXES`。本就 pass-through（不在 MAP），显式豁免行为零变更，仅令意图可见。
   守卫 stale-drift 检测强制：7 条 backend drift 已删（known_drift 11→3）。
6. **前端 known_drift — 保留（不在 0.7B 范围）**: studio-entry 缺失(ux) / teaching 未接线(semantic)。
   两者均涉及业务 UI（新增 studio 入口 / wiring /academic 到 teaching），违反「不改业务 UI」，保留为登记 drift。

## Must Preserve
0.6C 成果：router_meta 完整门控面守卫 + profile 前后端门控(`70eeac2`/`b1a6d09`/`61ed166`) +
主体 4 commit(`f51342a`/`8606ac6`/`bf421e8`/`bd8be46`) 不回退；动态 fail-closed 不削弱。

## Must Not Change
- 不回退 Phase 0.5/0.6/0.6C/0.7A 任何成果。
- **Portal homepage aggregation (Phase 1)**: 关键项 R5-DC1（MED security_design 前端 surface
  fail-open，含 R6/R7 同根因变体）已于 Phase 0.7A 处置结清、复审零 MED。剩余仅 LOW（R5-DC2 前缀漂移 +
  R8 CRLF 尾随空白）归入 0.7B。**Portal 解锁为设计者决策**——按任务契约"只剩 LOW → 规划 0.7B"，
  Portal 在设计者明确解锁前保持 BLOCKED（执行工程师不自行解锁）。
