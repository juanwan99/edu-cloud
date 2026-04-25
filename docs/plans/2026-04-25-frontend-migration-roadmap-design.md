---
baseline_command: "cd ~/projects/edu-cloud && uv run python -m pytest --collect-only -q"
baseline_verified_at: "2026-04-25 00:55"
baseline_count: 2187
---

# T3-12 前端迁移路线图 design（U-06 落地）

<!-- key-start -->
## 0. 任务卡

| 项 | 值 |
|---|---|
| Topic | frontend-migration-roadmap |
| 父任务 | edu-deep-scan §11.1 D-01 / D-11 / D-18（U-06 用户 4(a) 裁定） |
| 触发 | 用户裁定 2026-04-25 选 (a) 迁移：element-plus 替换 naive-ui，frontend 退役 |
| 范围 | edu-cloud `frontend/`（24.5k LOC）→ `frontend-nuxt/`（4.4k LOC）迁移 |
| 形态 | brainstorming 产物（design 草稿，**最大 T 级别**）；等 approve 后多个 sub-plan |
| 自治边界 | 本会话仅 design；执行将拆为 N 个 sub-plan，每 sub-plan 独立会话 |
| 前置 | 无（可平行 T3-02/T3-03 启动）|
<!-- key-end -->

### 0.1 现状证据回顾

| 维度 | frontend (Vite SPA) | frontend-nuxt (Nuxt 3) |
|---|---|---|
| UI 库 | naive-ui | element-plus |
| 路由 | vue-router 21 路由（_frozen/index.full.js） | pages/ 自动路由 46 |
| .vue / .js / .ts | 83 / 76 / 0 | 64 / 0 / 20 |
| 总 LOC | **24459** | **4444** |
| 测试文件 | 53 | 9 |
| dev 端口 | 8080 | 3100 |
| 构建产物 | dist 存在（生产 serving） | .output / dist 不存在（dev only） |
| Node engines | 无声明 | `>=22.12.0`（codex C-E 指出） |

### 0.2 关键约束

- frontend 是当前生产（https://mcu.asia 实际 serve frontend/dist）
- frontend-nuxt 未有 build/deploy pipeline
- 两版 UI 库不通用（naive-ui 组件 ≠ element-plus 组件）
- 迁移需逐页重写（不是 props rename）

---

## 1. 设计目标

**核心**：把 frontend (24.5k LOC) 全部功能迁到 frontend-nuxt，frontend 退役（删除或冷冻）。

**子目标**：
1. 建立 frontend-nuxt 的 build/deploy pipeline（解决 D-18）
2. nginx 路由分派切换（先并存灰度，后全量切换）
3. frontend-nuxt 测试覆盖补齐（解决 D-11，从 9 文件提到与 frontend 相当 53+）
4. Node 版本矩阵统一（解决 D-29）

**非目标**：
- ❌ 重新设计 UX（视觉同等）
- ❌ 改后端 API
- ❌ 引入新 framework（继续 Nuxt 3）

---

## 2. 迁移分批策略

### 2.1 当前页面分布对比

**frontend 主要页面**（21 路由 + 子页）：
- 阅卷工作台：MarkingProgressPage / GradingDispatchPage / GradingResultsPage / AiGradingPage
- 答题卡：CardEditorDevPage（开发用）
- conduct（操行）：ConductRecordPage / ConductRulesPage / ParentDetails 等
- 家长门户：ParentLogin / ParentRegister / ParentBind / ParentRankings 等
- 考试：ExamDetailPage / SchoolsPage 等
- AI：AI Agent / DocCropPanel / QuestionContentModal
- 学情：knowledge-tree 子树

**frontend-nuxt 已实现页面**（46 pages）：
- academic：course-selection / exam-schedule / score-manage / semester / timetable
- baseinfo：grades / records / schedule / selected-exam / students / teachers / vip
- exam：answercard / grading / list / quiz / statistics
- lesson：after-exam / console / resources / space
- report：config / contrast / custom / exam / level-score / students / table
- research：group-prep / knowledge / paper-builder / plan / questions / radar / school-resources
- study：class / dashboard / layer / student
- work：list / publish / scan / sync
- knowledge-tree / login / home / index

**功能重叠 / 缺口**：
- frontend-nuxt 缺：阅卷工作台（grading dispatch / results / progress） / conduct / parent portal / AI Agent
- frontend-nuxt 多：academic、baseinfo、lesson、research、study、work（haofenshu 新业务，frontend 也未实现）

**结论**：frontend-nuxt 是承接 haofenshu 新业务的新前端，frontend 是阅卷工作台的旧前端。两者实际是**业务分工**而非"双轨实现同一功能"。迁移核心是把 frontend 独有的"阅卷/conduct/家长/AI"四块迁过去。

### 2.2 迁移批次（从风险低到高）

**Batch 1：低耦合工具页**
- DocCropPanel（图像裁剪工具）
- QuestionContentModal（题目展示弹窗）
- 单页面，无路由依赖，直接重写

**Batch 2：parent portal 家长门户**
- ParentLogin / ParentRegister / ParentBind / ParentDetails / ParentRankings / ParentRules / ParentProfile / ParentOverview
- 独立 layout（ParentLayout），与 AppShell 不耦合
- 8 页 vue 重写

**Batch 3：conduct 操行管理**
- ConductRecord / ConductRules / etc
- 已有 sidebar permissions 派生（最近 7df3185）
- 与 T3-03 MANAGE_GRADING 同步（避免双重改）

**Batch 4：阅卷工作台（最复杂）**
- MarkingProgressPage / GradingDispatchPage / GradingResultsPage / AiGradingPage / MarkingAssignPage
- 涉及 5+ 页 + 大量 state（pinia store）+ 实时进度
- 需要重写 + 端到端测试

**Batch 5：AI Agent**
- AI 工作台 / 对话框
- 涉及 SSE / streaming，nuxt 3 SSR 适配需评估

**Batch 6：考试管理零散页**
- ExamDetailPage / SchoolsPage / etc
- 与最近未提交的 super-admin 任务可能冲突，**最后做**

### 2.3 build/deploy pipeline（先于 Batch 1）

**Pipeline 0**：
- frontend-nuxt `nuxt build` 产 .output/ 或 `nuxt generate` 产静态 dist
- 决策：SPA 模式（generate）vs SSR（build + node 运行时）
  - SSR 需要 node:22.12+ 运行时进程，nginx 反代
  - SPA 静态托管 nginx 简单
  - **推荐 SPA**（与现 frontend 一致，不引入新部署模式）
- 加 build script 到 edu-cloud `scripts/build_frontend_nuxt.sh`
- nginx 路由：保留 frontend/dist 在 https://mcu.asia/，frontend-nuxt 在 https://mcu.asia/v2/（或 staging）

### 2.4 nginx 灰度切换

**阶段 1**：mcu.asia/v2/ → frontend-nuxt（用户主动访问 v2 测试）
**阶段 2**：mcu.asia/v2/{已迁页面} → nuxt；其余 → frontend
**阶段 3**：所有页面迁完后，mcu.asia/ → frontend-nuxt，frontend/dist 删除

---

## 3. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 24.5k LOC 重写工作量被严重低估 | 进度延迟数月 | Batch 分批；每 Batch 独立 plan，按完成评估投入 |
| element-plus 与 naive-ui 组件 API 差异（form / table / modal） | 重写不是机械替换 | 每 Batch 起手做组件 mapping 表 |
| nuxt SSR / SPA 模式对接 SSE / WebSocket 行为差异 | AI 工作台流式响应可能不工作 | Batch 5 起手 spike SSE |
| 灰度期间用户体验断裂 | 投诉 | 在 sidebar 加"切换 v2"链接，回退顺畅 |
| 测试覆盖度（53 → 5x 起步）建立周期长 | 重写质量风险 | 每页迁移要求至少 1 个 e2e + 3 unit |

---

## 4. 实施步骤（每 Batch 一个 sub-plan）

| Batch | sub-plan 名 | 估算 |
|---|---|---|
| **B0** Pipeline | `T3-12-B0-build-deploy-pipeline-plan.md` | 3-5 天 |
| **B1** 工具页 | `T3-12-B1-tool-pages-plan.md` | 2-3 天 |
| **B2** Parent portal | `T3-12-B2-parent-portal-plan.md` | 1 周 |
| **B3** Conduct | `T3-12-B3-conduct-plan.md` | 1-2 周 |
| **B4** 阅卷工作台 | `T3-12-B4-grading-workstation-plan.md` | 3-4 周（最大）|
| **B5** AI Agent | `T3-12-B5-ai-agent-plan.md` | 1-2 周 |
| **B6** 考试零散 | `T3-12-B6-exam-misc-plan.md` | 1 周 |

**总估算**：8-12 周（视团队规模）

---

## 5. 验收标准（每 Batch 共有）

- [ ] 该 Batch 所有页 frontend-nuxt 实现 + ≥ 1 e2e + 3 unit
- [ ] 该 Batch 页 visual diff ≤ 5%（Playwright 截图对比）
- [ ] nginx 灰度切换无 5xx
- [ ] 每 Batch 完后 frontend 对应代码移到 `_frozen/`（不删，可回退）

**全 Batch 完成后**：
- [ ] frontend/ 整体移到 `_frozen/` 或 `archived-frontend/`
- [ ] mcu.asia 全量切换 frontend-nuxt
- [ ] CLAUDE.md 更新"前端单版本"声明

---

## 6. 与其他 T3 的关系

- **T3-13** answer-card-editor 合入 → 整合时其前端模块需对齐 element-plus（与本任务统一）
- **T3-03** MANAGE_GRADING → Batch 3 conduct 同时实现 sidebar 权限派生（避免冲突）
- **D-29** Node 版本矩阵 → B0 Pipeline 要把 frontend-nuxt engines `>=22.12.0` 推广到 edu-cloud 生产环境

---

**T3-12 design 草稿 v0 完 @ 2026-04-25**
**等 approve 进 6 个子 sub-plan；每 sub-plan 独立会话**
