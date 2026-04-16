---
type: handoff
created: 2026-04-14 09:30:30
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md
---

## 任务背景（新窗口零上下文假设）

### 这是什么
`edu-cloud` 好分数业务复刻 Phase 1 最后一批 — **Batch 3 (Task 10-12: PowerFilter + 45 页面 stub + 端到端验证)**，完成后 Phase 1 架构基座闭环。

### 当前阶段
**Phase 1 / Batch 3 / 待执行 — Batch 1 & 2 Gate 2 已 PASS**

| 批次 | 范围 | 状态 | Commits / 关键产物 |
|------|------|------|-------------------|
| Batch 1 | Schema + Menu API (Task 1-3) | ✅ Gate 2 R2 PASS | `e64957a → ef8a32a` |
| Batch 2 | Frontend 骨架 (Task 4-9, Nuxt 3 + Element Plus + AuthError 链) | ✅ **Gate 2 R3 PASS** (2026-04-14 09:25) | `08d86f0..6ddb19c`（R1 FAIL → R2 FAIL → R3 PASS）|
| **Batch 3** | **PowerFilter + 45 页面 stub + 端到端** | 🟡 **本批次** | — |

### Batch 3 Task 清单（plan §Task 10-12）

- **Task 10**: `usePowerOptions` composable + `PowerFilter` 组件（级联筛选：年级→班级→学科→考试）
  - 入口：`frontend-nuxt/composables/usePowerOptions.ts` + `frontend-nuxt/components/PowerFilter.vue`
  - Phase 1 本地 stub 返回 `{powerOptions:[], examInfoMap:{}}`，Phase 2 才真正接入后端
  - Vitest 骨架已在 plan 给出（级联 reset 场景）
- **Task 11**: 45 个页面 stub（Nuxt 文件路由）
  - 8 模块 × 45 页面：`pages/exam/*`、`pages/analytics/*`、`pages/homework/*`、`pages/teach/*`、`pages/research/*`、`pages/admin/*`、`pages/profile/*`、`pages/knowledge-tree/*`
  - 每个 stub 仅含占位内容（h1 标题 + 模块描述），**禁止**业务逻辑/API 调用
  - Nuxt 文件路由自动注册，无需 router 配置
- **Task 12**: 端到端全链路验证
  - plan 头部「Batch 2 独立验证命令」扩展为 Batch 3 完整验证：所有 45 路由 curl 200 + 登录 + 模块卡片 + 子页面跳转
  - 全量 pytest + vitest 回归

### 完成后达到的状态（Phase 1 闭环）

- 前端 Nuxt 3 骨架 + 45 页面可达（stub 级）
- 后端动态菜单 + 预聚合 schema + ExamResult rank 字段
- Phase 2 填充真实业务功能的基座已就绪

## Batch 2 R3 PASS 关键数据（Batch 3 必读）

| 维度 | 结果 |
|------|------|
| R3 结论 | **PASS**（commit 6ddb19c, `code_review_batch2.status=pass`）|
| Node 基线 | **≥22.12.0**（engines + frontend-nuxt/.nvmrc 锁定）|
| Vitest 基线 | 24/24 PASS（useApi 4 + auth 8 + useMenus 8 + default 4）|
| AuthError 链 | useApi → useMenus → default.vue 三层传递已 verified，**Batch 3 不得回归** |
| npm 依赖基线 | `npm ci --ignore-scripts` 零 EBADENGINE + `npm ls` 零 invalid |
| pre-existing | `tests/test_ai/test_tool_access_fail_closed.py` 2 failed 稳定（延续 R2-F001 口径）|

## 约束与偏好（design / plan 未记录的增量，Batch 3 强制）

- **任务级别**: T4（Phase 1 最终批次，同 T4 轨道）
- **角色**: Executor（执行 Task 10-12），不是 Planner、不是 Reviewer
- **流程**: T4 流程（Batch 3 完成 → 审查交接单 → Planner 调度 codex-review R1）
- **新窗口声明**: `[T4] haofenshu Phase 1 Batch 3 — PowerFilter + 45 页面 stub + 端到端验证`

### 前置修复（Batch 3 Task 10 前处置 — Planner 追加）

这 3 项是 R1/R2/R3 审查中识别但延期到 Batch 3 的 debt，**必须在 Task 10 Step 1 前完成**：

#### 前置-1: R4 useMenus startsWith 分隔符修复

- 文件：`frontend-nuxt/composables/useMenus.ts` (L13)
- 当前：`route.path.startsWith(c.path)` — 理论风险 `/exam/list` vs `/examples` 冲突
- 修改：`route.path === c.path || route.path.startsWith(c.path + '/')` （等值匹配 + 分隔符保护）
- 测试补丁：`tests/composables/useMenus.test.ts` 加 1 个 case（`/exam` 不误匹配 `/examples`）
- 理由：Batch 3 新增 45 页面 stub 路径，种子 scope 扩大，startsWith 误匹配风险从理论变为实际

#### 前置-2: R1 WSL 后端 hot-reload baseline 修复

- 问题：9000 常驻 uvicorn 进程陈旧不重启 → 端到端 Step ③④ 无法验证 `/api/v1/menus`
- 处置方案（Executor 选一）：
  - **A (推荐)**: Task 12 端到端前脚本化：先 `pkill -f "port 9000"` → 重启 `python ~/.claude/scripts/serve.py python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000` → 等 healthy → 跑 E2E
  - **B**: 启 fresh 9001 对照实例做 E2E（已在 R2/R3 验证可行）
- Task 12 文档必须记录 "采用方案 A/B + 启动脚本代码"

#### 前置-3: T2-docs-01 plan risk_modules 追认（R1/R2/R3 均提出）

- 文件：`docs/plans/2026-04-12-haofenshu-phase1-plan.md` 的 Contract Pack §risk_modules 段
- 追加 2 项：
  ```
  | frontend-nuxt/package.json | 依赖清单漂移 + Node floor 契约 | engines ≥22.12.0 + .nvmrc + npm ci 零 EBADENGINE gate |
  | frontend-nuxt/package-lock.json | 锁文件与 package.json 一致性 | 禁止 --legacy-peer-deps / 禁止手工改 lockfile |
  ```

### Task 10-12 执行铁律

- **禁止回归 B2-F002**: AuthError 链路 (useApi / useMenus / default.vue) 在 Batch 3 任何改动都必须保留 R3 PASS 的代码面
- **禁止降级 node 基线**: `frontend-nuxt/.nvmrc` / `package.json` engines 字段不得修改（除非 Phase 2 独立 design 批准）
- **禁止手工改 package-lock.json**: 新增 dep 用 `npm install <pkg>` 自动更新 lockfile，禁止手编辑
- **Task 10 PowerFilter 保留 stub 特性**: Phase 1 返回 `{powerOptions:[], examInfoMap:{}}` 固定 shape，Phase 2 才接后端（plan F007 已锁定）
- **Task 11 45 页面 stub 零业务逻辑**: 每个 .vue 只写 `<h1>` + 描述，**禁止** `useApi` 调用 / 状态管理 / 动态数据
- **Task 12 端到端必须独立启动后端**: 不依赖"已在跑"的 9000 进程（baseline 不可靠，见前置-2）

### Windows 环境铁律

- Node 版本必须 ≥22.12.0（R3 已锁，`frontend-nuxt/.nvmrc` 已写 `22.12.0`）
- 用 `python` 不用 `python3`
- `cd` 用 Bash 工具
- 服务启动通过 `~/.claude/scripts/serve.py`（port_guard.py 硬拦截直接 uvicorn）
- Windows+SQLite 全量 pytest >10 min 超时 → 用分层跑：`pytest tests/test_menu/ tests/test_alembic_migration.py -q` + `pytest tests/test_api/ -q` 等按需分批

### 审查范围预告（Batch 3 完成后 Planner 调度）

- Gate 2 code_review_batch3 是 Phase 1 最后一个 Gate
- 审查焦点预告：
  - 45 页面 stub 的文件路径与 plan 清单逐一对齐
  - PowerFilter 级联 reset 的反证验证（stub shape 在 Phase 2 切换时不破坏契约）
  - 端到端 4 步 Gate 真正跑通（Nuxt dev + login + home + 模块跳转）
  - 前置-1/2/3 debt 处置到位
  - B2-F002 AuthError 链 + B2-F001 Node 基线不回归

## 启动 Prompt（复制到新窗口）

```
[edu-cloud] Executor (Phase 1 Batch 3 — PowerFilter + 45 页面 stub + 端到端) | 2026-04-14 09:30:30
项目: C:\Users\Administrator\edu-cloud

声明：[T4] haofenshu Phase 1 Batch 3 — PowerFilter + 45 页面 stub + 端到端验证（Phase 1 最终批次）

读取交接卡（本窗口入口）: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-haofenshu-phase1-batch3-handoff.md
读取 Plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md（重点 Task 10-12 + 头部 Batch 2/3 独立验证命令段）
读取 Design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md
读取 Batch 2 R3 PASS 报告: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-report-batch2-r3.md
读取 gates.json: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-gates.json

角色: Executor（不是 Planner、不是 Reviewer）。使用 executing-plans skill。

## Step 0: 前置修复（Task 10 前必做，Planner 追加）

0.1 前置-1 useMenus startsWith 分隔符:
    - 编辑 frontend-nuxt/composables/useMenus.ts L13
    - 原: route.path.startsWith(c.path)
    - 改: route.path === c.path || route.path.startsWith(c.path + '/')
    - 补测试: tests/composables/useMenus.test.ts 加 1 case
      (fixture: c.path='/exam', route.path='/examples' → activeModule != that menu)
    - 验证: ./node_modules/.bin/vitest run → 25/25 PASS（原 24 + 新 1）

0.2 前置-2 端到端 baseline 修复方案选型:
    - 推荐方案 A: 写 scripts/restart-backend-for-e2e.sh（或 .ps1/.py）
      pkill -f "port 9000" || true
      python ~/.claude/scripts/serve.py python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 &
      curl -f http://localhost:9000/api/v1/health（轮询直到 healthy，最多 30s）
    - 方案 B 备选: fresh 9001 对照实例
    - Task 12 端到端必须用此脚本启动，不依赖已在跑的 9000

0.3 前置-3 plan.md risk_modules 追认:
    - 编辑 docs/plans/2026-04-12-haofenshu-phase1-plan.md Contract Pack § risk_modules 段
    - 追加 2 行（见交接卡「前置-3」段）

## Step 1-3: Task 10 usePowerOptions + PowerFilter

1.1 创建 frontend-nuxt/composables/usePowerOptions.ts（plan Task 10 规格）
    - Phase 1 stub: 返回 {powerOptions:[], examInfoMap:{}}
    - 级联 reset: watch selectedGrade → selectedClass 重置, etc.
1.2 创建 frontend-nuxt/components/PowerFilter.vue（级联 ElCascader 或级联 Select）
1.3 新建 tests/composables/usePowerOptions.test.ts 覆盖 cascade_reset 契约（plan 已给骨架）
1.4 ./node_modules/.bin/vitest run → 应 26+/26+ PASS（原 24 + 前置-1 +1 + Task 10 测试 +2~3）

## Step 4-5: Task 11 45 页面 stub

4.1 按 plan Task 11 清单创建 45 个 .vue 文件（文件路由自动注册）
    - 每个仅含 <template><h1>{模块名}</h1><p>Phase 1 stub - Phase 2 填充业务逻辑</p></template>
    - 禁止任何 useApi/useMenus/useAuth/Pinia store 调用
4.2 清单 grep 验证: find frontend-nuxt/pages -name "*.vue" | wc -l → 应 ≥45

## Step 6-8: Task 12 端到端验证

6.1 启动后端（前置-2 脚本方案 A）
6.2 启动 Nuxt dev: cd frontend-nuxt && npm run dev --port 3100
6.3 全量回归:
    - ./node_modules/.bin/vitest run → PASS 全绿
    - 45 路由 curl 检查: for p in $(grep -r '"path"' pages/ | extract); do curl -s -o /dev/null -w "$p %{http_code}\n" http://localhost:3100$p; done → 全 200
    - login → /home 模块卡片 → 点击跳转到 stub 页面（手工或 Playwright）
    - 后端分层 pytest: pytest tests/test_menu/ tests/test_alembic_migration.py -q + pytest tests/test_ai/ -q（含继承的 2 pre-existing）

## Step 9: R1 审查交接单

9.1 写审查交接单到 docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch3.md
    按 ~/.claude/rules-t3/review-templates.md「审查交接单」格式
    必填段落:
    - 逐 Task 自审表（Task 10-12 + 前置-1/2/3）
    - 预审自检（各 slice 实测 + 反证栏）
    - 验证清单自检（Step 0-8 每步证据）
    - Pre-existing 继承口径（test_tool_access_fail_closed 2 failed 稳定）
    - 根因分析（bug fix 段，若 Task 12 发现后端 hot-reload 根因）
    - 自查四要素（边界/状态锁/条件判断）
    - B2-F002 不回归证据（grep useApi.ts + useMenus.ts + default.vue 关键守卫仍在）
    - B2-F001 Node 基线不回归证据（.nvmrc 内容 + engines 字段）

9.2 commit:
    - 一次 commit 合并前置-1/2/3 + Task 10-12 + 交接单
    - commit message: feat(frontend): haofenshu phase1 batch3 — Task 10-12 + 前置修复 R1/R4/docs-01

完成后输出审查交接单。

---

Windows 环境铁律: 用 `python` 不用 `python3`；Node 必须 ≥22.12.0；服务启动通过 `~/.claude/scripts/serve.py`。
禁止回归铁律: B2-F002 AuthError 链路 + B2-F001 Node 基线不得破坏。
PASS 报告锚定: Gate 2 Batch 3 若多轮，gates.json report_path 必须指向最新 PASS 报告。
```

## 验证清单（本交接卡自检）

- ✅ plan 文件绝对路径存在
- ✅ design 文件绝对路径存在
- ✅ Batch 2 R3 PASS 报告绝对路径存在
- ✅ gates.json 绝对路径存在
- ✅ 启动 Prompt 无 `<...>` 占位符
- ✅ 启动 Prompt 末尾含 `完成后输出审查交接单。`（T4 格式）
- ✅ 任务级别 T4 已声明
- ✅ 3 项前置修复指令完整（R1/R4/docs-01）
- ✅ Batch 2 不回归铁律明确（AuthError + Node 基线）
- ✅ 45 页面 stub 零业务逻辑铁律明确
- ✅ 端到端 baseline 修复选型给出（方案 A 推荐）
- ✅ Windows 环境 + 分层跑 pytest 指引完整
