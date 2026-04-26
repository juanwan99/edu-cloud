[edu-cloud] Executor→Reviewer | 2026-04-17 22:40 (UTC+8)

## 审查交接单: Batch 3 Task 10-12（PowerFilter + 43 页面 stub + 端到端验证）

计划: `/home/ops/projects/edu-cloud-w3/docs/plans/2026-04-12-haofenshu-phase1-plan.md`
设计: `/home/ops/projects/edu-cloud-w3/docs/plans/2026-04-12-haofenshu-biz-replication-design.md`
前序 handoff: `/home/ops/projects/edu-cloud-w3/docs/plans/2026-04-14-haofenshu-phase1-batch3-handoff.md`
W3 窗口交接卡: `/home/ops/projects/edu-cloud-w3/docs/plans/2026-04-17-w3-haofenshu-batch3-exec-handoff.md`
Batch 2 基线: commit `6ddb19c`（R3 PASS）
Batch 3 范围: `feat/haofenshu-batch3` 分支单 commit（本交接单同 commit 内）
工作 worktree: `/home/ops/projects/edu-cloud-w3/`（W3 独立 worktree，详 §"环境差异" #1）

## 环境差异与决策清单

### #1. W3 worktree 隔离
- 起点症状: 4 并发会话（W1 card-subdir / W2 kg-batch3b / W3 haofenshu-batch3 / W4 conduct-roadmap-batch1）原共享 `/home/ops/projects/edu-cloud/` 主 worktree，staged/unstaged 改动跨分支漂移（Git index 全局共享）
- 修复命令: `git -C /home/ops/projects/edu-cloud worktree add /home/ops/projects/edu-cloud-w3 feat/haofenshu-batch3`
- 状态: `git worktree list` 现显示 3 个 worktree（主 W4 / edu-cloud-w2 W2 / edu-cloud-w3 W3），W1 未隔离

### #2. 前置-2 脚本删除（用户决策 A）
- handoff §前置-2 原要求: 写 `scripts/restart-backend-for-e2e.sh` (`pkill 9000 → serve.py → uvicorn → curl healthy`)
- ECS 环境调查发现:
  - `~/.claude/scripts/serve.py` **全盘不存在**（find / 零结果；路径沿袭自 windows CLAUDE.md）
  - `~/.claude/hooks/port_guard.py` 在 Linux 为 no-op（L215-216 `if sys.platform != 'win32': sys.exit(0)`），不是"孤儿 hook"
  - 9000 backend 由 `systemd edu-cloud.service` 管理（`systemctl list-units` 显示 `active running`），`pkill + nohup uvicorn` 与 systemd `Restart=always` 打架
  - Batch 3 本卡 §2.2 禁改后端 → 9000 systemd 实例的 29dfb8a 代码基线已含 menu API → `/api/v1/menus` 401（route 存在）证实
- 决策: 用户批准 A = 删除 `scripts/restart-backend-for-e2e.sh`（从未 commit，直接 rm）

### #3. Task 11 数字漂移（决策 1C）
- plan 头部 + handoff + design §8 宣称"45 页面"
- plan §文件结构 L145-157 + Task 11 Step 1-10 清单实际 **43 个**（exam 5 / report 6 / study 4 / work 4 / lesson 4 / research 7 / baseinfo 7 / academic 5 / knowledge-tree/index 1 = 43）
- design "45" 是 haofenshu-clone 源项目基数，与 plan 实现差 2，**未指定哪 2 页**
- 决策: 按 plan 精确 43 + 本交接单记录漂移

### #4. Task 12 Step 1+2 跳过（决策 2A）
- plan Step 1 `python -m uvicorn` 起 backend —— ECS 已有 systemd 长跑 9000 实例
- plan Step 2 `alembic upgrade head + seed_menus.py` —— 主 worktree `.venv` 已跑过（`/api/v1/menus` 401→200 with token 证实 route + seed 状态可用）
- Batch 3 零后端改动 → 无需重启/迁移

### #5. Task 12 Step 6 pytest 跳过（决策 3C）
- plan Step 6 `pytest --tb=short -q` —— W3 worktree 无 venv（`/home/ops/projects/edu-cloud-w3/.venv` 不存在）
- Batch 3 零后端改动 → pytest 不覆盖本 batch 产出
- 仅跑 frontend-nuxt vitest（29 passed）作为充分证据

## 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| 前置-1 R4 | useMenus.ts L25 startsWith 分隔符护栏 + 1 test case | useMenus.ts L25-28 改 `route.path === c.path \|\| route.path.startsWith(c.path + '/')`；useMenus.test.ts 新增 describe `activeModule 路径匹配分隔符护栏` + 1 case（`route=/examples` 不匹配 `c.path=/exam`）| ✅ | useMenus.test.ts 从 8→9 tests；Vitest 文件总 4→5（+ usePowerOptions.test.ts）|
| 前置-2 R1 | `scripts/restart-backend-for-e2e.sh` 方案 A | **删除，不实施**（用户 A） | ❌→ACCEPT | 见 §"环境差异" #2 |
| 前置-3 docs-01 | `plan.md` risk_modules 追认 2 行 | L79-80 追加 `frontend-nuxt/package.json` + `frontend-nuxt/package-lock.json` | ✅ | — |
| T10 | usePowerOptions composable + PowerFilter + cascade_reset Vitest | `composables/usePowerOptions.ts` 90 行（plan L2417-2525 抄）; `components/common/PowerFilter.vue` 58 行（plan L2530-2590 抄）; `tests/composables/usePowerOptions.test.ts` 4 case | 🔀 | 在 plan 2 骨架 case 上加：load_throw_catch（覆盖 L84-87 catch 分支）+ cascade_reset_empty_classes（plan "边界条件" L2608 明确要求，骨架未写）|
| T11 | 45 stub 页面 | **43 个**（按 plan §文件结构精确）+ bash heredoc 批量生成 + sed 修复 41 个通用 stub 措辞冗余（"Phase 2 迁移：Phase 2 填充业务逻辑" → "Phase 2 填充业务逻辑"） | 🔀 | 见 §"环境差异" #3；exam/list 和 knowledge-tree/index 保留 plan L2677/L2722 钦定文字 |
| T12 | 端到端 7 步 | Step 1-2 跳过（2A）/ Step 3 Nuxt dev 3100 2s listen / Step 4 login via proxy 拿 JWT 272 字符 / Step 5 API 层实测 / Step 5 视觉层待用户验收 / Step 6 跳过（3C）/ Step 7 本 commit | 🔀 | menu API "admin 返 2 模块"初判异常，查 seed 源码后是 platform_admin 设计（L013 自审记录在 §"根因分析"） |

状态: ✅ 一致 / ❌ 不一致 / 🔀 改进（实现优于/偏离计划，必须记录具体变更）/ ACCEPT（由用户决策接受的偏离）/ ⏸ 待用户验收 / ⏭ 按决策跳过

## 预审自检（测试契约 slice 实测）

| 测试契约 slice | 测试文件::case | 命令 | 实际输出 | 反证 |
|---------------|--------------|------|---------|------|
| 前置-1: `/examples` 不匹配 `/exam` 分隔符护栏 | `useMenus.test.ts::activeModule 路径匹配分隔符护栏` | `./node_modules/.bin/vitest run tests/composables/useMenus.test.ts` | `9 passed` / `activeModule === null` | 回退 L25-28 为 `route.path.startsWith(c.path)` → 新 case fail（`activeModule` 误等于 exam 菜单对象）|
| T10 slice 1: load() 空 tree 不崩溃 | `usePowerOptions.test.ts::load() 空数据容错::load() 空 tree 时不崩溃` | `./node_modules/.bin/vitest run tests/composables/usePowerOptions.test.ts` | `4 passed` / `tree=[]` / `selectedGrade=''` / `selectedExamIds=[]` | 删除 `tree.value = res.powerOptions \|\| []` fallback → 若 res 为 undefined 读属性 TypeError |
| T10 slice 2: cascade_reset grade→class→subject→examIds | `usePowerOptions.test.ts::级联 watch::切换 grade 时 class/subject/examIds 自动跟到第一项` | 同上 | `selectedClass=='1班'` / `selectedSubject=='语文'` / `selectedExamIds=['e1']`（3 nextTick 后）| 删除 watch(selectedGrade) → class/subject/examIds 全空，测试 fail |
| T10 slice 3: load() API 抛错 catch | `usePowerOptions.test.ts::load() 空数据容错::load() API 抛错时 tree/examInfoMap 清空` | 同上 | `await pw.load()` 不抛 + `tree=[]` + `examInfoMap={}` | 删 try/catch → rejects with network timeout |
| T10 slice 4: cascade 切换到无班级 grade | `usePowerOptions.test.ts::级联 watch::切换到无班级的 grade → selectedClass 重置为空` | 同上 | `selectedClass===''` | 改 `classOptions.value[0] \|\| ''` 为 `classOptions.value[0]` → undefined 赋值，断言 fail |
| T11: 43 stub 路径 HTTP 200 | 10 个抽样 curl /exam/list 等 | 见 §"端到端 Step 5" | 10/10 路径 200 | Nuxt SPA dev 对所有路径返 index.html+200（兜底语义），curl 200 非强证据；路由可达真证据 = `find pages/ -mindepth 2 -name "*.vue"` 清单对齐 plan §文件结构 L145-157 + Nuxt file-based routing 契约 |
| T12 Step 4 login proxy | `curl POST /api/v1/auth/login` via 3100 | 见 §"端到端 Step 4" | JWT 272 字符 | Nuxt proxy 故障 → 502 或 404 |
| T12 Step 5 menu API | `curl GET /api/v1/menus` with principal token | 见 §"端到端 Step 5" | 8 模块 42 子菜单（exam 5 + report 6 + study 4 + work 4 + lesson 4 + research 7 + baseinfo 7 + academic 5）| `admin` 登录 → 2 模块（不是 bug，是 seed_menus 对 platform_admin 只授权 baseinfo/academic 的设计；见 §"根因分析"）|

## 验证清单自检

### 前置-1 R4 审查清单
- ✅ `useMenus.ts` L25 含 `route.path === c.path || route.path.startsWith(c.path + '/')` — grep 全 frontend-nuxt 命中 1 处
- ✅ `useMenus.test.ts` 新增 describe `activeModule 路径匹配分隔符护栏` — 含 1 case
- ✅ Vitest 从 24/24 → 25/25（useMenus.test.ts 8→9 tests）（此时未含 T10 测试）

### 前置-3 docs-01 审查清单
- ✅ `plan.md` risk_modules 表 `frontend-nuxt/package.json` 行存在 — grep `frontend-nuxt/package.json | 依赖清单漂移` 命中 L79
- ✅ `plan.md` risk_modules 表 `frontend-nuxt/package-lock.json` 行存在 — 命中 L80
- ✅ 位置: 原 `modules/analytics/analysis_models.py` 行（L78）后追加，`test_debt` 段（L82+）前

### T10 审查清单（plan L2600-2610）
- ✅ 四级级联：年级→班级→学科→考试（4 watch 链）
- ✅ 上级变化时自动选中下级第一项（`classOptions.value[0] || ''` 等）
- ✅ `analysisParams` computed 自动构建请求参数
- ✅ `PowerFilter.vue` 用 `defineModel` 双向绑定（4 个 defineModel: grade/class/subject/exam）
- ✅ `load()` 容错处理（try/catch + tree=[] + examInfoMap={}）

### T11 审查清单（plan L2743-2748）
- ✅ 9 模块目录全部创建（exam/report/study/work/lesson/research/baseinfo/academic/knowledge-tree）
- 🔀 **43 页面（非宣称 45）**，与 plan Step 1-10 清单 + plan §文件结构 L145-157 完全对齐（决策 1C）
- ✅ 每个 stub 含面包屑 + 标题 + 占位段（knowledge-tree/index.vue 无面包屑按 plan L2717-2727 特殊格式）
- ✅ Nuxt 文件路由自动注册（无 router 配置改动）
- ✅ stub 零业务逻辑：`grep -rl 'useApi|useMenus|useAuthStore|usePowerOptions|$fetch' pages/` 只命中 pages/login.vue + pages/home.vue（Batch 2 Task 9 旧物，非本 Batch scope），43 个新 stub 零命中

### T12 审查清单（plan L2814-2820）
- ✅ Step 3 Nuxt dev 3100 listen（2s 起）
- ✅ Step 4 login → JWT 272 字符（via Nuxt proxy /api → :9000）
- 🔀 Step 5 API 层：admin（platform_admin）2 模块（seed 设计）/ admin_principal_1（principal）8 模块（与 plan 预期对齐）
- ⏸ Step 5 视觉层：模块卡片 + TopNav + SubNav 渲染待用户浏览器验收（autonomy-boundary 感知型任务验收权在用户）
- ⏭ Step 6 pytest：3C 跳过（Batch 3 零后端改动 + W3 无 venv）
- ✅ 不应修改 `frontend/` 目录：本 Batch 改动限于 `frontend-nuxt/ + docs/plans/ + 本 handoff`，零触 `frontend/`

## Pre-existing 继承口径

延续 Batch 2 R3 基线：`tests/test_ai/test_tool_access_fail_closed.py` 有 2 个稳定 pre-existing failures，不指向 Batch 3（零后端改动 + 跳过 pytest）。R2-F001 继承处置记录在 Batch 2 R3 PASS 报告。

## 根因分析（menu API "admin 返 2 模块"调查）

**症状**: Task 12 Step 5 初次 `curl /api/v1/menus` with admin（platform_admin）Bearer → 返 2 模块（baseinfo + academic），与 plan L2795 "顶部应显示 8 个模块导航" 预期冲突。

**根因**:
1. `scripts/seed_menus.py` L18-120 对 platform_admin **只授权 baseinfo + academic 2 个模块**（L99/L112 `roles: [..., "platform_admin"]`）；其他 6 个教师业务模块（exam/report/study/work/lesson/research）的 `roles` 列表不含 platform_admin
2. `src/edu_cloud/modules/menu/service.py::MenuService.get_menus_for_user` L48 按 `role not in (menu.roles or [])` 过滤 → 跳过 6 模块 → 返 2 模块
3. `src/edu_cloud/modules/menu/router.py` L24-26：admin 无 school_id → `enabled_modules=None` → module 过滤旁路（`MenuService` L50-52 `if menu.requires_module and enabled_modules is not None`），但 role 过滤仍生效

**证据**: `admin_principal_1 / 123456` 登录（principal 角色，school_id=31c17116...）→ menu API 返 **8 模块 42 子菜单**完整，与 plan 预期对齐。

**排除的假设**:
- DB menu_configs 残缺（排除：admin_principal_1 返 8 模块齐全）
- systemd 9000 进程陈旧（排除：health 200 + menu route 401→200 with token）
- seed_menus.py 未跑（排除：admin_principal_1 能看所有模块）

**影响面 (scope check)**:
- 同模式: 其他 `role × school_id=null` 场景（district_admin 可能，未测）
- 同边界: menu_router 决策 `school_id → enabled_modules` 链路
- 同不变量: seed_menus `roles` 列表设计

**L013 自审**: 我首次 curl 返 2 模块后用"systemd 9000 陈旧 / DB 残缺"假设为主线，忽略"admin 应看多少模块"的设计问题。按 seed 设计 platform_admin 就只看管理类菜单（baseinfo + academic），是符合业务预期的。在 curl 其他 role 之前不该定性为"异常"。本 batch 不改 seed / 不改后端（§2.2 铁律），仅记录该设计与 plan 文字"8 模块导航"的表达歧义（可能 plan 指 school 角色视角）。

## 自查四要素

**边界**:
- `pages/index.vue` / `login.vue` / `home.vue` 是 Batch 2 Task 9 旧物，本 Batch 3 不动（grep 扫 43 新 stub 零 store/API 调用；旧 2 个页面命中是 expected）
- `frontend-nuxt/` 以外: 本 Batch 改 `docs/plans/2026-04-12-haofenshu-phase1-plan.md`（前置-3 docs-01）和本交接单；均 docs-only，不触 INV-01 / INV-02（`frontend/` 零改动 + 现有后端路由不变）

**状态锁**:
- B2-F002 AuthError 链路（`useApi → useMenus → default.vue`）未回归（见下段证据）
- B2-F001 Node 基线（`package.json engines=">=22.12.0"` + `.nvmrc=22.12.0`）未动
- 45→43 数字漂移：design "45" 是源项目基数，plan 实现基数 43，两者语义不同，漂移仅文档层

**条件判断**:
- `useMenus.ts` L25-28 分隔符护栏正确（`===` 或 `startsWith(c.path + '/')` 一路放行，其他跳过）
- `usePowerOptions.ts` 级联 watch 语义：上级变 → 下级 = [0]（first）或 '' （empty）；无级联升降
- Nuxt SPA dev 对所有路径返 200（index.html 兜底）— 43 stub 可达证据锚定 = find 清单 + Nuxt file-based routing 契约，不单纯靠 curl 200

**反证已验**:
- 反证 1：useMenus 回退 startsWith（无分隔符）→ useMenus.test.ts 新 case fail（`activeModule !== null`）
- 反证 2：usePowerOptions load() 去 try/catch → load_throw_catch case rejects
- 反证 3：PowerFilter 去 defineModel → v-model 双向绑定破裂（Vue 编译报错；单测未覆盖此层，plan 已标 test_debt PowerFilter 组件测试到 Phase 2）

## B2-F002 / B2-F001 不回归证据

### B2-F002 AuthError 链路（未回归）
```
frontend-nuxt/composables/useMenus.ts:1:   import { AuthError } from '~/composables/useApi'
frontend-nuxt/composables/useMenus.ts:12:      if (err instanceof AuthError) {
frontend-nuxt/composables/useMenus.ts:13:        authStore.setMenus([])
frontend-nuxt/composables/useMenus.ts:14:        throw err
frontend-nuxt/composables/useMenus.ts:17:      authStore.setMenus([])
```
`useApi.ts` / `default.vue` / `auth.ts` 未动（git diff 零变更）。`useMenus.ts` 仅改 L25-28 activeModule 分隔符部分，loadMenus 的 AuthError try/catch 原样保留。

### B2-F001 Node 基线（未回归）
- `frontend-nuxt/package.json` engines: `"node": ">=22.12.0"`（未动）
- `frontend-nuxt/.nvmrc`: `22.12.0`（未动）
- `npm ci --ignore-scripts`: 708 packages 11s / **0 EBADENGINE 警告**（W3 worktree 独立 install，node v22.22.2）

## 改动清单

### 新建文件
- `frontend-nuxt/composables/usePowerOptions.ts`（90 行）
- `frontend-nuxt/components/common/PowerFilter.vue`（58 行）
- `frontend-nuxt/tests/composables/usePowerOptions.test.ts`（77 行，4 case）
- `frontend-nuxt/pages/{exam,report,study,work,lesson,research,baseinfo,academic,knowledge-tree}/*.vue`（43 stub）
- `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch3.md`（本文件）

### 修改文件
- `frontend-nuxt/composables/useMenus.ts`（L25-28 activeModule 分隔符护栏，+5/-1）
- `frontend-nuxt/tests/composables/useMenus.test.ts`（+23 行，+1 describe +1 case）
- `docs/plans/2026-04-12-haofenshu-phase1-plan.md`（risk_modules +2 行 L79-80）

### 未 commit 的临时文件
- `scripts/restart-backend-for-e2e.sh`（前置-2 脚本，调查后用户 A 批准删除，从未进入 git index）

## 验证结果总表

| 验证项 | 命令 | 结果 |
|-------|------|------|
| Vitest 全量 | `./node_modules/.bin/vitest run` | **29 passed / 5 files**（useApi 4 + usePowerOptions 4 + useMenus 9 + auth 8 + default.vue 4）|
| Stub 零业务逻辑 | `grep -rl 'useApi\|useMenus\|useAuthStore\|usePowerOptions\|\$fetch' pages/` | 只命中 pages/login.vue + pages/home.vue（Batch 2 旧物），43 新 stub 零命中 |
| Stub 清单对齐 plan | `find pages/ -mindepth 2 -name "*.vue"` | 43 个，与 plan §文件结构 L145-157 完全对齐 |
| Nuxt dev 启动 | `nohup npx nuxt dev --port 3100` | 2s listen（Nuxt 3.17.7 / Nitro 2.13.3 / Vite 6.4.2 / Vue 3.5.32）|
| Login proxy | `curl POST /api/v1/auth/login via 3100` | JWT 272 字符 |
| Menu API (principal) | `curl /api/v1/menus` with admin_principal_1 token | 8 模块 42 子菜单 |
| Menu API (admin) | 同上 with admin token | 2 模块（seed 对 platform_admin 设计，非 bug）|
| npm ci 依赖基线 | `npm ci --ignore-scripts` | 708 packages / 0 EBADENGINE / W3 独立 worktree |
| W3 worktree 隔离 | `git worktree list` | `/home/ops/projects/edu-cloud-w3 [feat/haofenshu-batch3]` 独立 |

## 待用户完成验收

**视觉层 Step 5**: 浏览器打开 `http://localhost:3100` → 登录 `admin_principal_1 / 123456` → 验证：
- 模块卡片（home 页，按 menu API 返回的 8 模块动态渲染）
- TopNav 8 模块顶部导航
- SubNav 蓝色二级条（切换模块时正确切换子菜单）
- 随意点击 stub 页面确认路由可达（不 404）

*autonomy-boundary 感知型任务验收权在用户，Executor 不擅自宣告 Step 5 视觉层通过。*

## 审查焦点预告（Reviewer / Planner 参考）

1. **决策接受层**: 45→43 数字漂移（1C）/ 前置-2 脚本删除（A）/ Task 12 Step 1-2 Step 6 跳过（2A + 3C）是否接受
2. **L013 自审记录**: menu API admin=2 模块的初判误判（见 §"根因分析"）
3. **W3 独立 worktree**: 执行环境隔离是否妥当（W1/W2/W4 并发中，仅 W2/W3 已 worktree 化）
4. **B2-F002 / B2-F001 不回归**: 证据段已附
5. **test_debt 延续**: PowerFilter 组件渲染级测试 deferred Phase 2（plan L86 既定）

本交接单 commit 后进入 Gate 2 Code Review Batch 3。
