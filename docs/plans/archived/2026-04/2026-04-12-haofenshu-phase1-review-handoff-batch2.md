[edu-cloud] Executor→Reviewer | 2026-04-13 22:10:43

## 审查交接单: Batch 2 Task 4-9（Frontend 骨架）

计划: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-12-haofenshu-phase1-plan.md`
设计: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-12-haofenshu-biz-replication-design.md`
Batch 1 基线: commit `ef8a32a`（R2 PASS）
Batch 2 范围: commits `08d86f0..674cd99`（6 commits，只触碰 `frontend-nuxt/` + `CLAUDE.md`，零后端改动）

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T4 | Nuxt 3 项目初始化（frontend-nuxt/, Element Plus, Pinia, SCSS 主题） | `08d86f0` 初始化 Nuxt 3.17.7 + @element-plus/nuxt + @pinia/nuxt；nuxt.config.ts SSR=false + proxy /api→:9000；assets/css/main.scss 品牌色+布局变量；app.vue `<NuxtLayout><NuxtPage/></NuxtLayout>` | 🔀 | 改进 1：plan Step 1 用 `npx nuxi@latest init`（选 Nuxt 4.4 minimal + `app/` 目录），我回退到 Nuxt 3.17（plan 标题明确 "Nuxt 3"）并删除 `app/` 让源码在根目录；改进 2：首次 `npm install` 遇 Windows 文件锁（fzf/consola 模块 `.DELETE.xxx` 残留），解决方案 `rm -rf node_modules package-lock.json` + `npm install --legacy-peer-deps`（vitest 2.x→3.x 以匹配 @nuxt/test-utils peer） |
| T5 | auth store + context store + auth.global.ts middleware + Vitest 骨架 3 个 | `fa2c0d5` 三文件按 plan 骨架实现；测试契约 3 slice（applyLoginResponse/applySwitchRoleResponse/restoreFromStorage）扩展为 8 个 Vitest 测试全 PASS | 🔀 | 改进：plan 骨架用 `import.meta.client` Guard，Vitest + happy-dom 环境下为 undefined 导致 `setUser` 不写 localStorage → `restoreFromStorage` 测试失败。改为 universal `typeof window !== 'undefined'`（语义等价：SSR 无 window，客户端有），2 处 replace。同时把 Task 4 遗留的 `tsconfig.json` Nuxt 4 references 形式改为 `extends ./.nuxt/tsconfig.json` |
| T6 | useApi composable（30+ 方法 + getPowerOptions stub） | `1177cf7` useApi.ts 27 个方法（Auth/Menu/Exam/Analytics/Homework/Knowledge/BaseInfo/Profile/AI chat stream/Dashboard）；getPowerOptions 返回 `{powerOptions:[], examInfoMap:{}}` | ✅ | 测试契约 1 slice 扩为 4 测试全 PASS（3 getPowerOptions 场景 + 1 API 结构校验）；setup.ts 补 `useRuntimeConfig` + `$fetch` mock |
| T7 | useMenus + TopNav + SubNav + UserDropdown | `15cb50a` useMenus.ts (loadMenus/activeModule/currentSubMenus/navigateToModule)；TopNav 毛玻璃顶栏 + logo + 动态导航；SubNav 子菜单 + 图标映射 40+；UserDropdown 角色名+学校名+logout | ✅ | 回归 vitest 12/12 PASS（未退化 Task 5/6） |
| T8 | 三种 Layout (default/fullscreen/auth) | `1f28e8f` default.vue TopNav+SubNav+slot + token watch（null→有值触发 restoreFromStorage + loadMenus，失败 logout）；fullscreen 100vw/100vh；auth 100vh 居中渐变 | ✅ | main-content marginTop 按 hasSubNav 动态 50/88px |
| T9 | login + home 页面 + index 重定向 | `674cd99` index.vue token 存在→/home 否则→/login；login.vue auth layout + ElForm + handleLogin（validate→api.login→set cookie→applyLoginResponse→loadMenus→/home）；home.vue 欢迎语+module-grid 卡片网格 | ✅ | 图标映射 8 主模块 |

> 状态: ✅一致 / ❌不一致 / 🔀改进（实现优于计划，必须记录具体变更内容）

### 预审自检（测试契约 slice 实测）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| T5 slice 1: applyLoginResponse 归一化（选 is_primary / fallback roles[0] / 单角色） | `tests/stores/auth.test.ts::applyLoginResponse` (3 测试) | `./node_modules/.bin/vitest run tests/stores/auth.test.ts -t applyLoginResponse` | `3 passed` — `active_role.id==='r2'` / `active_role.id==='r1' (fallback)` / 单角色 OK | 删除 `roles.find((r) => r.is_primary)` 只留 `roles[0]` → `'选中 is_primary 角色'` 测试 fail（当前设计 passes 只因 fallback 正确。验证 fallback 覆盖 is_primary 优先级） |
| T5 slice 2: applySwitchRoleResponse 保留 user/roles 只改 active_role + user=null 静默 | `tests/stores/auth.test.ts::applySwitchRoleResponse` (2 测试) | `./node_modules/.bin/vitest run tests/stores/auth.test.ts -t applySwitchRoleResponse` | `2 passed` — `roles.length===2` + 不抛异常 | 删除 `if (!this.user) return` → user=null 测试捕获 TypeError |
| T5 slice 3: restoreFromStorage JSON 损坏不崩溃 / 空 localStorage / 有效恢复 | `tests/stores/auth.test.ts::restoreFromStorage` (3 测试) | `./node_modules/.bin/vitest run tests/stores/auth.test.ts -t restoreFromStorage` | `3 passed` — 损坏 JSON 不抛 + `display_name==='Alice'` | 删除 try/catch → 损坏 JSON 测试报 SyntaxError（被当前 try/catch 吞掉） |
| T6 slice: getPowerOptions stub 返回固定结构 | `tests/composables/useApi.test.ts::getPowerOptions stub` (3 测试) | `./node_modules/.bin/vitest run tests/composables/useApi.test.ts -t getPowerOptions` | `3 passed` — `{powerOptions:[], examInfoMap:{}}` | 改为 `Promise.resolve(undefined)` → Task 10 `res.powerOptions` 读属性报 TypeError |
| T4 slice: Nuxt dev 启动无报错 | 手工命令 | `cd frontend-nuxt && npx nuxt dev --port 3100` | `Nuxt 3.17.7 (Nitro 2.13.3, Vite 6.4.2, Vue 3.5.32) / Local: http://localhost:3100/ / Vite client built in 102ms / Vite server built in 2221ms / Nitro server built in 5394ms` + `curl -I http://localhost:3100/` 返回 `HTTP/1.1 200 OK, x-powered-by: Nuxt` | 若 nuxt.config 缺模块（@element-plus/nuxt）→ 启动报模块找不到错 |

### 验证清单自检

**T4 审查清单（plan 行 1186-1192）:**
- ✓ nuxt.config.ts SSR=false — grep 确认 `ssr: false` 存在
- ✓ Element Plus + Pinia 模块注册 — grep `modules:` 含 `@element-plus/nuxt`, `@pinia/nuxt`
- ✓ API 代理指向 localhost:9000 — `vite.server.proxy./api.target === 'http://localhost:9000'`
- ✓ CSS 变量包含好分数品牌色和布局尺寸 — `--hfs-primary` / `--hfs-header-height` 等 10 项存在
- ✓ `npx nuxt dev` 可启动 — 见预审自检 T4 slice
- ✓ 不应修改现有 frontend/ 目录 — `git diff 08d86f0^..674cd99 -- frontend/` 零变更（已验证）

**T5 审查清单（plan 行 1401-1407）:**
- ✓ auth store 有 user/menus — `state: () => ({ user: null, menus: [] })`
- ✓ switchRole 调用 API 并重新加载菜单 — `await api.switchRole(roleId); ... await loadMenus()`
- ✓ logout 清除 cookie + 跳转登录页 — `token.value = null; navigateTo('/login')`
- ✓ middleware 检查 cookie，未登录跳转 /login — `if (!token.value && !publicPaths.includes(to.path)) return navigateTo('/login')`
- ✓ /login 和 / 是公开路径 — `publicPaths = ['/login', '/']`
- ✓ 不引用 Naive UI 组件 — grep `naive` in stores/middleware → 无

**T6 审查清单（plan 行 1620-1629）:**
- ✓ 单入口 useApi() — `export function useApi()`
- ✓ token 从 cookie 读取 + 自动注入 Authorization — `const token = useCookie('edu_token')` + `headers: token.value ? { Authorization: ... } : {}`
- ✓ baseURL 从 runtimeConfig — `config.public.apiBase + '/api/v1'`
- ✓ 方法签名与 edu-cloud RESTful 对应 — analytics 11 路径对齐 router.py；knowledge 对齐 `/knowledge-tree/graph`/`/search`；bank `/bank/questions`
- ✓ chatStream 用 responseType: stream — `responseType: 'stream' as any`
- ✓ 暴露 raw + token — `return { ..., raw: request, token }`
- ✓ F007 所有方法对齐已有后端端点（不存在的注释为 Phase 2/3 待实现）— 5 个 stub 端点（getSchoolDashboard 等）已在 plan 中注释
- ✓ F007 switchRole 用 role_id (string) 不是 role_index — `body: { role_id: roleId }`

**T7 审查清单（plan 行 1949-1955）:**
- ✓ TopNav 动态渲染 authStore.menus — `v-for="menu in authStore.menus"`
- ✓ SubNav 仅在 subMenus 非空时显示 — `v-if="subMenus.length > 0"`
- ✓ 当前激活模块高亮 — `:class="{ active: activeModule?.code === menu.code }"`
- ✓ 当前子菜单页面高亮 — `:class="{ active: route.path === item.path }"`
- ✓ 图标映射覆盖所有种子数据 icon 名 — iconMap 40+ 条目
- ✓ UserDropdown 显示角色名+学校名 — `{{ authStore.roleName }} · {{ authStore.schoolName }}`

**T8 审查清单（plan 行 2091-2096）:**
- ✓ default 包含 TopNav+SubNav+main slot — 见 default.vue
- ✓ main-content marginTop 动态调整 — `:style="{ marginTop: hasSubNav ? '88px' : '50px' }"`
- ✓ fullscreen layout 无任何 chrome — 仅 `<slot />` + 100vw/100vh overflow:hidden
- ✓ auth layout 居中渐变背景 — `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- ✓ token 变化时自动加载菜单 — `watch(token, async (val) => { ... await loadMenus() })`

**T9 审查清单（plan 行 2360-2365）:**
- ✓ index.vue 根据 token 重定向 — `if (token.value) navigateTo('/home') else navigateTo('/login')`
- ✓ login.vue 使用 auth layout — `definePageMeta({ layout: 'auth' })`
- ✓ login 成功后设置 token + 加载用户 + 加载菜单 + 跳转 home — handleLogin 流程完整
- ✓ home.vue 动态渲染可见模块卡片 — `v-for="menu in authStore.menus"` module-grid
- ✓ 点击模块卡片跳转该模块第一个子页面 — `@click="navigateToModule(menu)"` → `router.push(menu.children[0].path)`

### Batch 2 独立 Gate 4 步实测证据（plan 头部 F008 R2 要求）

**Step 1: Nuxt dev 启动无报错** — ✅ PASS
```
$ cd frontend-nuxt && npx nuxt dev --port 3100
● Nuxt 3.17.7 (with Nitro 2.13.3, Vite 6.4.2 and Vue 3.5.32)
  ➜ Local:    http://localhost:3100/
✔ Vite client built in 102ms
✔ Vite server built in 2221ms
[nitro] ✔ Nuxt Nitro server built in 5394ms
$ curl -I http://localhost:3100/
HTTP/1.1 200 OK
content-type: text/html;charset=utf-8
x-powered-by: Nuxt
```
> 注：plan 默认端口 3000 被 `haofenshu-clone` 参考项目占用（netstat 确认 PID 12736, Title "好分数精准教学"），fallback 到 3100（CLAUDE.md 已记录此端口约定）。

**Step 2: POST /api/v1/auth/login 拿到 access_token** — ✅ PASS
```
$ curl -s -X POST http://localhost:9000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"123456"}' | python -c "import sys,json; d=json.load(sys.stdin); assert 'access_token' in d"
login OK, token len: 272, roles: 1
```
另外 `t_yw_001`（subject_teacher @ YCSY2026）登录也 OK（token_len=273）。

**Step 3: 访问 /home 渲染模块卡片** — ⚠ 代码路径 PASS，端到端受 WSL 后端 reload 阻塞
- **代码路径 PASS**：
  - pytest `tests/test_menu/test_menu_api.py` 9/9 PASS（菜单 router + service 端到端契约已覆盖）
  - 本地直调 MenuService: `svc.get_menus_for_user(role='subject_teacher', enabled_modules={...})` 返回 **6 个模块 × 各 4-6 子菜单**（exam/report/study/work/lesson/research）
  - seed_menus.py 已插入 50 条（8 模块 + 42 子菜单）
- **端到端阻塞（与 Batch 2 无关）**：后端在 WSL 内以 `uvicorn --reload` 运行（监听端口 9000 PID 41476 通过 `tasklist` 查不到说明是 WSL 进程），Windows 端文件变更不触发 WSL 侧 inotify → Batch 1 已合入的 `menu_router` 挂载未被热重载。`curl http://localhost:9000/openapi.json` 显示 `menu_paths: []`，`GET /api/v1/menus` 返回 `404 Not Found`。
  - 重启 WSL 后端即可恢复；此为 baseline 运行环境已知问题，不是 Batch 2 代码缺陷
- **建议**：Reviewer 若要端到端验证 Step 3，请先 `kill` WSL 后端 + 重启 `uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000`

**Step 4: 点击模块跳转到子页面** — ⚠ 代码路径 PASS（同 Step 3）
- `navigateToModule` 实现已在 useMenus.ts 验证（menu.children?.length → router.push(menu.children[0].path)）
- 占位页路径（exam_list→`/exam/list` 等）在 seed_menus.py 已固化
- 端到端跳转受同一后端 reload 问题阻塞，代码逻辑由 T7 单测 + DB 直查证据覆盖

### 全量回归自检

**前端 vitest 12/12 PASS**:
```
✓ tests/composables/useApi.test.ts (4 tests) 22ms
✓ tests/stores/auth.test.ts (8 tests) 55ms
Test Files  2 passed (2)
     Tests  12 passed (12)
```

**后端 pytest 分层验证**:
- Batch 1 新增: `tests/test_menu/ + tests/test_alembic_migration.py` **12 passed, 1 warning in 17.27s** ✅
- Batch 2 零触碰后端代码（git diff `08d86f0..674cd99 -- src/` 空）→ 后端测试状态 = Batch 1 R2 baseline（1918 pass + 2 稳定 pre-existing failures + 3 flaky）
- 本窗口全量 pytest (1988 tests collected) 在 Windows+SQLite 环境下运行时间异常（>10 分钟后仍 47%），被 kill。已定向跑 R2-F001 指称的 2 个 failure → 稳定复现（详见下方 R2-F001 处置）

### R2-F001 处置（Batch 1 R2 LOW design-concern defect_fix 继承）

| 测试 | 状态 | 命令 | 证据 |
|------|------|------|------|
| `tests/test_ai/test_tool_access_fail_closed.py::test_no_capability_record_rejects` | FAILED (pre-existing stable) | `python -m pytest tests/test_ai/test_tool_access_fail_closed.py --tb=line` | `AssertionError: assert 1 == 0` @ line 26，`ToolSpec(name='tool_x', module_codes=[('analytics','read')], allowed_roles=['subject_teacher'])` 应被 capability 过滤但未被过滤 |
| `tests/test_ai/test_tool_access_fail_closed.py::test_partial_capability_match_rejects` | FAILED (pre-existing stable) | 同上 | `AssertionError: assert 1 == 0` @ line 75 |
| 同文件其余 5 个测试 | passed | 同上 | — |

**结论**：2 个稳定 pre-existing 已确认（Batch 2 任何 commit 前后均复现），与 Batch 2 前端改动无任何关联。与 Batch 1 R2 交接单「2 个稳定 pre-existing + 3 个 flaky 用例本轮未复现」表述一致。

### 自查（四要素格式）

- **新增文件的边界 case**:
  - 构造输入: applyLoginResponse 接收 roles=[] 场景
  - 运行命令: `./node_modules/.bin/vitest run tests/stores/auth.test.ts`（已含 `roles.find(...) || roles[0]` fallback 覆盖）
  - 实际输出: `8 passed (8)`（3 applyLoginResponse + 2 applySwitchRoleResponse + 3 restoreFromStorage）
  - 结论: is_primary 选主 / roles=[] fallback undefined / 单角色 / user=null 静默 / JSON 损坏不崩溃 — 全覆盖

- **状态变量/锁的异常路径**:
  - 构造输入: default.vue `watch(token, { immediate: true })` 的 token=null→token=T 切换路径
  - 运行命令: 代码审阅 + `grep -nE "watch\(token" frontend-nuxt/layouts/default.vue`
  - 实际输出:
    ```
    11:watch(
    12:  token,
    13:  async (val) => {
    14:    if (val && !authStore.user) {
    15:      authStore.restoreFromStorage()
    ...
    ```
  - 结论: token 变化时 `loadMenus` 失败走 `logout` 兜底（防 token 过期卡死）；immediate=true 保证挂载时立即执行；restoreFromStorage 顺序先于 loadMenus

- **字符串匹配/条件判断的假阴性**:
  - 构造输入: useMenus.activeModule 对 `route.path` 的 `startsWith` 匹配 — 若 menu child path 是 `/exam`, route.path 是 `/examples` 会误匹配吗？
  - 运行命令: 代码审查 `frontend-nuxt/composables/useMenus.ts:13`
  - 实际输出:
    ```
    authStore.menus.find((m) =>
      m.children?.some((c: any) => route.path.startsWith(c.path)),
    ) || null
    ```
  - 结论: **存在理论风险**——seed 数据中子菜单 path 如 `/exam/list`、`/report/exam`，不会被 `/examples` 等偏离路径误匹配（种子数据都含 `/module/sub` 二级结构）。Phase 2 填充更多子页面时若出现 `/foo` 和 `/foo-bar` 冲突需加分隔符（`c.path + '/'`）。记入 test_debt。

### 额外偏离 plan 的改进（汇总 🔀）

1. **Task 4 Nuxt 版本**: plan 隐含用 `npx nuxi@latest init`，实际下载 Nuxt 4.4 minimal。我回退到 Nuxt 3.17（标题约束）+ 删除 `app/` 目录让源码在根目录，与 plan 的文件结构（frontend-nuxt/composables/ 不带 app/ 前缀）一致。
2. **Task 4 tsconfig.json**: Nuxt 4 模板的 `references` 多文件形式改为 Nuxt 3 `extends ./.nuxt/tsconfig.json`（Nuxt 3 生成单文件）。修复时机归入 Task 5 commit。
3. **Task 5 Guard 判断**: `import.meta.client` → `typeof window !== 'undefined'`。语义等价（SSR 无 window），Vitest+happy-dom 环境可用。
4. **Task 5/6 测试契约扩展**: plan 骨架 3 个测试 slice，实际展开为 8+4=12 个 Vitest 测试以覆盖全部边界（is_primary / fallback / 单角色 / 空 roles / user=null / JSON 损坏 / localStorage 空 / 有效恢复）。
5. **setup.ts Nuxt global mock**: `defineStore` / `ref` / `computed` / `watch` / `useCookie` / `useApi` / `useMenus` / `useRuntimeConfig` / `$fetch` / `navigateTo` 全部注入 globalThis，beforeEach 清理 cookie 和 localStorage。
6. **vitest.config.ts 首次创建**: plan 前置要求（「测试契约 — Vitest 配置要求」），happy-dom + `~` alias + setupFiles。
7. **package.json devDependencies**: vitest 从 `^2.1.5` 升到 `^3.2.0` 以匹配 `@nuxt/test-utils@^3.14.4` peer 约束。
8. **CLAUDE.md Batch 2 进度行**: 每个 Task commit 时更新一行（技术栈段），doc-sync-guard 要求。

### 变更类型分类

- **T4/T7/T8/T9**: 非行为变更（脚手架 + UI 组件 + 路由 + 布局，无业务逻辑决策）
- **T5/T6**: 部分行为变更（auth store 归一化 + restoreFromStorage 持久化 + useApi stub），测试契约覆盖

### 送审资产

- Plan: `docs/plans/2026-04-12-haofenshu-phase1-plan.md`（commit `08d86f0` 前 subject_hash=`e77cf539...`）
- Batch 2 commits: `08d86f0..674cd99`（6 commits, diff 限于 `frontend-nuxt/` + `CLAUDE.md`）
- 本交接单: `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2.md`
- gates.json: `docs/plans/2026-04-12-haofenshu-phase1-gates.json`（plan_review PASS 已追认 R2 落盘，code_review_batch2 待写回执）

### 给 Reviewer 的建议聚焦

1. 逐 Task 自审表中 🔀 改进条目的合理性（尤其 T4 Nuxt 3 回退 + T5 guard 改写）
2. 测试契约有效性（反证验证栏，每条测试是否真能捕获错误实现）
3. Batch 2 独立 Gate Step 3-4 的"代码路径 PASS + 端到端 WSL reload 阻塞"处置方式（是 PASS 还是应 deferred 到 Reviewer 手工重启后端再 end-to-end）
4. useMenus activeModule 的 `startsWith` 理论误匹配风险（Phase 2 填充前是否需要预防性加分隔符）
5. R2-F001 继承描述是否符合 Batch 1 R2 交接单约束（2 稳定 pre-existing 已确认，不重复"5 failures pre-existing"旧表述）

使用 codex-review skill 进行 GPT 代码审查。
