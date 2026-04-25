---
type: handoff
created: 2026-04-10 19:07:22
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-plan.md
---

# 知识图谱教师工作台 Phase 2 — 会话交接卡

## 约束与偏好

**T3 流程**。Phase 2 设计 + 计划 + Gate 1 审查（3 轮 GPT 独立审查）已全部完成。本卡用于新会话按 plan 执行 Batch 1（Tasks 1-3）。

### 当前状态

- **设计基线**：`C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-design.md`（commit 8182a20）
- **实现计划**：`C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-plan.md`（commit 639e500，R1/R2 修复后最终版 2b67668）
- **Gate 1 回执**：`C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-gates.json`（plan_review: pass / gpt / R3 收敛，commit 283adb3）
- **任务状态**：`C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-state.json`（6 Tasks 全 pending）

### Phase 1 前置依赖（已全部完成，不要改动）

Phase 2 建立在 Phase 1「可信骨架」之上。Phase 1 的**以下已实现且必须保持不变**：

| 模块 | 文件 | 说明 |
|------|------|------|
| Graph API v2 响应字段 | `src/edu_cloud/modules/knowledge_tree/service.py`、`schemas.py` | `description` / `hard_in_count` / `hard_out_count` / `external_hard_refs` / edge `confidence` / edge `review_status`。Phase 2 前端直接消费这些字段，**不新增任何后端改动** |
| 审查工作台 tab 和组件 | `frontend/src/components/knowledge-tree/RelationReviewPanel.vue`（及 3 个子组件） | Phase 2 必须与之共存，tab 切换（`图谱视图` / `审查工作台`）已就位 |
| 前端 API client | `frontend/src/api/knowledgeTree.js` | `getGraph(module, includeDraft)` / `qualityCheck(module)` 均可用 |
| Composable | `frontend/src/components/knowledge-tree/useKnowledgeTree.js` | 已有 `loadQuality`。Phase 2 Task 3 会新增 `loadAllModulesQuality` 和 `modulesQuality` state |

### 关键决策（审查收敛后）

这些决策在 design.md 中都有记录，但下面列出最容易踩坑的几点，供执行者对照：

1. **模式 2 是简化版**（方案 C）：单击节点 → 底部浮动面板 + `查看详情` 按钮；**不做节点透明度淡化**（延后 Phase 2.5）；**做**画布空白 `canvas:click` 退出。这是 R1 F005 的最终处置。
2. **跨模块徽标数据源必须是 `node.external_hard_refs.out`，不是 `props.edges`**。这是 R1 F002 的最关键修复——Phase 1 后端在 module 过滤时会**过滤掉跨模块 edge**，跨模块信息只通过节点的 `external_hard_refs` 字段传递。如果扫描 `props.edges`，徽标在生产环境永远为空。
3. **showCards 分支必须保留**：教师（`canEdit=true`, 无 `studentId`）自动 `showCards=false` 进入 main-layout + ModuleOverviewPanel；家长/学生保持 `showCards=true` 看 ModuleCards 欢迎页，点击模块后进入 ConceptMapPanel。不要删除 ModuleCards import。详见 plan.md Task 6 的"入口状态机"段。
4. **单一真源**：完全删除旧 `GraphPanel.vue`（`git rm`），不保留注释或 fallback。这是 R1 F001 的硬约束。
5. **layoutEngine 是纯函数**：禁止 `Math.random` / `Date.now` / Set 迭代顺序依赖。所有排序必须按 id 字母序，以保证"同输入→同坐标"的确定性。这是 Contract Pack INV-001。

### 执行范围与边界

- **本 plan 不改动任何后端代码**。所有修改都在 `frontend/` 下。Python 后端测试只需确认无回归。
- **不引入新依赖**。复用 `@antv/g6 ^5.1.0`（只用 `layout: { type: 'preset' }`），不引 dagre/elk/d3-dag。
- **Phase 2 只覆盖 Tasks 1-6**。Contract Pack 中的 test_debt（节点淡化 / 跨模块徽标悬停展开）是 Phase 2.5 工作，不在本次执行范围。

### 用户偏好

- **质量优先**，知识图谱是最关键最核心的内容（来自 Phase 1 辩论基线）
- **可视化服务模型**，不独立追求好看；首要用户是教师（教研/备课/审核）
- **WSL 优先运行服务进程**，不用 Windows 原生（全局 feedback）
- **完成声明铁律**：本地修改必须跑项目级测试套件才能声称完成

### GPT Gate 1 审查记录

3 轮收敛的关键 Finding（供执行时对照，避免重新踩坑）：

| ID | Severity | 原因 | 最终处置 |
|----|----------|------|----------|
| F001 | HIGH code-bug | Task 6 未说明 showCards 角色分支 | Task 6 加入"入口状态机"段落，显式区分教师/家长/学生路径 |
| F002 | HIGH code-bug | crossModuleBadges 扫描 props.edges 违反 Phase 1 契约 | 改为读 `node.external_hard_refs.out` |
| F003 | MED test-gap | Task 2 缺测试契约 | 补齐 3 slice 5 字段 + 5 个单元测试 |
| F004 | MED test-gap | Task 4 无跨模块徽标测试 | 新增 slice 5 + 2 个新测试，断言 `vm.crossModuleBadges.B === {M2:2, M3:1}` |
| F005 | MED code-bug | 节点淡化口径与 design 不一致 | design.md 明确降级 Phase 2.5；plan 加 `canvas:click` 退出；Task 5 Files 说明同步更新 |

原始审查日志：`C:\Users\Administrator\edu-cloud\docs\plans\.codex-p2-plan-review-raw.log`（R1）、`.codex-p2-plan-review-r2-raw.log`（R2）、`.codex-p2-plan-review-r3-raw.log`（R3）。

### Batch 结构

| Batch | Tasks | 文件数 | 关键产出 |
|-------|-------|--------|---------|
| 1 | T1 / T2 / T3 | 3 源 + 3 测试 + 1 修改 composable | `layoutEngine.js`（纯函数算法）+ `ModuleStatCard.vue` + `ModuleOverviewPanel.vue` + `loadAllModulesQuality()` |
| 2 | T4 / T5 / T6 | 2 源 + 2 测试 + 1 修改 page + 1 删除 | `ConceptMapPanel.vue` + `ConceptFocusOverlay.vue` + `KnowledgeTreePage.vue` 集成 + `git rm GraphPanel.vue` |

**批次边界**：Batch 1 完成后先送 GPT 代码审查，PASS 再继续 Batch 2。中间绝对不跨批次执行。

### 测试命令速查

```bash
# 前端单测（Vitest）
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run

# 指定文件
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js

# 后端回归（确认无 Python 端破坏）
cd /c/Users/Administrator/edu-cloud && python -m pytest --tb=short -q

# 前端启动（Git Bash，port_guard 必须走 serve.py）
cd /c/Users/Administrator/edu-cloud/frontend && python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev
# → http://localhost:5273
```

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-10 19:07:22
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-plan.md 的 Task 1-3 执行（Batch 1：layoutEngine + ModuleStatCard + ModuleOverviewPanel）。使用 executing-plans skill。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
