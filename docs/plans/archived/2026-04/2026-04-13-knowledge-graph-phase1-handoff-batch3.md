---
type: handoff
created: 2026-04-13 21:05:36
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-gates.json
prev_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch2.md
review_report_batch2_r3: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-report-batch2-r3.md
---

# 约束与偏好（design.md / plan.md 未记录的增量信息）

## Tier 与流程

**T3 流程**（2 窗口）：Planner commit plan + Plan Review (Gate 1) → Executor 新会话执行 + 审查交接单 → GPT Code Review (Gate 2) per batch → 所有 Gate PASS → design.md 标记 [实现完成]。

**Batch 3 Gate 2 名称**：`code_review_batch3`（gates.json 未创建字段，GPT 审查时由 write_receipt 自动追加）。

## 已完成进度快照（2026-04-13 21:05）

| 阶段 | 状态 | 关键证据 |
|------|------|---------|
| Gate 1 Plan Review | ✅ PASS | gates.json `plan_review=pass`，subject_hash=94cb65d7... |
| Batch 1 (T1-T6) | ✅ PASS R2 | commit `1c3c1a2..bcb1971`，code_review_batch1=pass |
| Batch 2 (T7-T8) | ✅ PASS R3 | commit `ff59672..cb70873`，code_review_batch2=pass，报告路径 `review-report-batch2-r3.md` |
| Batch 3 (T9-T14) | ⏸ pending | state.json 中 T9-T14 status=pending |

**state.json 过时警告**：`updated_at=2026-04-13 19:40:18`，T7/T8 在 Batch 2 R3 PASS 后实际已 completed，但 state.json 仍显示 completed。**Batch 3 启动前 Planner 首件事：确认 state.json 已反映最新 Batch 2 完成状态**（Batch 2 R3 PASS 在 cb70873 commit 中已落 gates.json，state.json 若滞后可同步更新）。

## Batch 2 收尾留下的增量约束（Batch 3 必读）

### 前端接入契约（T9-T11 消费 T7/T8 产物）

1. **`GraphResponse.graph.nodes[].*` v3 字段**（Pydantic 类型稳定）：
   - `exam_frequency: int`（默认 0）
   - `exam_coverage: float`（默认 0.0）
   - `avg_difficulty: float | None`（**None 语义保留**，零考频概念无难度代理值——T10 着色模式若用 avg_difficulty 需处理 null 回退）
   - `importance_score: float`（默认 0.0）
   - `textbook_chapters: list`（默认 []，结构 `[{book, chapter, section, title}]`）
   - `study_unit_id: str | None`
   - `estimated_minutes: int | None`
   - `prerequisite_depth: int`（默认 0）
   - `planning_weight: dict | None`（**MCU 映射覆盖率 ~24/108**，多数概念为 None，T10 热力色 fallback 必须处理）

2. **`GET /graph/{node_id}/exam-items` 响应契约**（T11 NodeDetailDrawer 高考真题 tab 消费）：
   - `ExamItemsResponse = { total: int, items: ExamItem[], page: int, page_size: int }`
   - `ExamItem.question_number: int | None`（**注意是 int，不是 str**——assessment_items.question_number 列是 INTEGER，R2 加固时修正）
   - `ExamItem.options: str | None`（**raw JSON string**，前端需 `JSON.parse()`）
   - `ExamItem.score`（代替原 plan 中的 `difficulty` 字段——🔀 defect_fix R2 已确认，真实 schema 无 difficulty 列）
   - `ExamItem.module_tag`（额外字段，前端可用于展示所属模块）
   - **降级契约**：knowledge.db 不可达 / 概念未知 → `total=0, items=[]`，HTTP 200（非 404/500）

3. **`GET /stats/overview` 响应契约**（T13 ModuleOverviewPanel 消费）：
   - `StatsOverviewResponse = { total_concepts, total_edges, exam_freq_distribution: {high, mid, low, zero}, module_stats: {M1: ModuleStatsItem, ...} }`
   - `ModuleStatsItem = { concepts: int, edges: int, avg_freq: float, exam_coverage: float }`
   - `module` 参数：`"all"` 或 `M1/M2/M3/M4/M5`，不传默认 all

### 测试风格约束（Batch 3 前端测试必须延续）

**精确断言原则**（R1/R2/R3 审查均聚焦此）：
- **禁用弱断言**：`assert x > 0` / `assert result` / `assert status in (200, 404)` / `if photo:` / `assert total >= N`
- **必须精确**：`assert set == {id1, id2, id3}` / `assert value == 233.3` / `assert status == 200`

**反证风格**（Batch 2 R2 加固确立，Batch 3 继承）：
- 每个 Contract Pack invariant / Task 测试契约 slice 必须有"错误实现会怎样失败"的反证说明
- 用 mutant 视角问自己：如果核心逻辑被替换成占位，本测试会 fail 吗？不会 → test-gap HIGH
- 受控 fixture 优先：不要依赖真实 knowledge.db 的内容做精确断言（内容会漂移），用 controlled fixture（Vitest 前端对应用 `msw` 或内存 store 模拟）

### 前端技术栈约束

- **Vue 3.5 Composition API + Naive UI 2.44 + Vite 7**（已有）
- **AntV G6 知识图谱渲染**（KnowledgeTreePage.vue 已在用）
- **Vitest 4 + happy-dom**（已有 72 个前端 tests），T9-T11 新增组件测试走此栈
- **无新前端依赖**（plan 未授权）—— T9 热力色工具用纯 JS 实现（色阶插值），不引入 d3/chroma 等新依赖

### 已落盘但 plan 未显式声明的前端文件（Batch 3 需对齐）

- `frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue`（已存在，Phase 2）— T13 增强而非新建
- `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`（已存在，Phase 2）— T10 升级节点视觉
- `frontend/src/components/knowledge-tree/NodeDetailDrawer.vue`（已存在，Phase 2）— T11 加新 tab
- 新增建议文件：
  - `frontend/src/components/knowledge-tree/heatmapUtils.js`（T9）
  - `frontend/src/components/knowledge-tree/ColorModeToggle.vue`（T9）
  - `frontend/src/components/knowledge-tree/ChapterNavigator.vue`（T12 新导航模式）

## 遗留 Finding 待 Planner 处置

### P001（Batch 2 R1→R3 deferred）

- **范围**：plan Contract Pack 段 INV-002 / INV-004 verification 映射不准
- **状态**：R2 修了 INV-005，INV-002 (L1 集合相等) 和 INV-004 (前端组件契约) 仍 deferred
- **Planner 处置选项**：
  1. **合并进 T14 收尾**（推荐）：T14 除 design.md 标记外，补 INV-002 精确化映射（指向 `tests/test_knowledge_tree/test_sync_service.py::test_sync_only_l1` 或类似入口级验证）+ INV-004 映射指向 Batch 3 T10-T13 的前端组件测试
  2. **独立补丁 Task**：T14-bis 专门处置 Contract Pack 映射
- **不阻塞 Batch 3 启动**：GPT R3 确认实现层无回归，是文档同步问题

### R2-NEW-02（Batch 2 R2 deferred 2026-05-15）

- **范围**：governance 全仓 checkout-index 性能问题（每 commit ~2.7s）
- **状态**：与 knowledge-graph-phase1 无关，属 module-governance 项目
- **Planner 处置**：**跳过**（不属于本 topic）

## 环境/流程约束（继承自 batch2 handoff）

- **staging 污染防护**：commit 前 `git diff --cached --name-only` 确认只含本 batch 文件。其他会话并行可能污染 index（Batch 2 踩过 conduct R3 耦合坑 commit `f70af8d`，虽不影响代码但 scope 不纯）
- **doc_sync_guard 硬阻断**：T9-T12 如新建组件 / 变更 API 调用，需同步 `edu-cloud/CLAUDE.md`（前端页面/组件段 + API 端点表）
- **scope_guard 硬阻断**：commit 只能含 plan T{N}-{M} 声明的文件范围，超范围 reset 再精确 add
- **Windows git CRLF 警告**忽略，不影响 commit
- **知识库路径**：`~/edu-knowledge-base/knowledge.db` 不在 repo 内，测试应走 `skipif(not Path(KB_PATH).exists())` 或受控 fixture（见 Batch 2 `controlled_kb`）
- **前端端口**：5273（Vite dev），后端 9000（FastAPI），代理 /api → :9000，不要硬编码 localhost

## Git 操作陷阱（Batch 2 踩过的坑）

1. **linter/别会话污染 staging**：`git reset HEAD` 后仍可能有未预期的 modify 在工作区。commit 前必 `git diff --cached` 确认
2. **f70af8d 的教训**：`git add <specific_path>` 后 commit，若其他会话此前对同 repo 跑了 `git add .`，staging 可能提前含外部文件 → `git commit -m` 会全部 commit
3. **LF→CRLF 警告**：忽略，不阻断 commit
4. **分批提交**：Batch 3 至少拆成 `T9-T10 基础组件 → commit` / `T11-T12 NodeDetail+导航 → commit` / `T13-T14 集成+收尾 → commit` 三次 commit，每次独立 Gate 2 子批次 review 或合并单批次 review（由 Planner 决定）

## 审查流程约束

- **Batch 3 的 Gate 2 最多 3 轮**。前端测试加固风格延续 Batch 2 R2（精确断言 + 反证 + mutant 视角）
- **🔀 偏离强制标注**：T9-T14 若实现偏离 plan（如新增组件、字段名变更），必须在审查交接单逐 Task 自审表列 🔀 + 理由
- **behavior_change finding 单独确认**：GPT 可能将着色阈值 / 节点视觉尺寸变化识别为 behavior_change，Executor 不可自行同意
- **P001 处置纳入本批 Gate 2**：若 Planner 选择在 T14 处置 P001，Contract Pack 映射更新需在 Gate 2 R1 发送前提交 plan（否则 GPT R1 仍会报告 P001 未消除）

---

# 启动 Prompt（复制到新规划窗口）

```
[edu-cloud] Planner | 2026-04-13 21:05:36
项目目录: C:\Users\Administrator\edu-cloud
Tier: T3

读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch3.md
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md（T9-T14 段，lines 2271-3965）
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-report-batch2-r3.md（P001 deferred 终态）

进度：Batch 1 (T1-T6) + Batch 2 (T7-T8) Gate 2 全部 PASS，commit `ff59672..cb70873`，gates.json `code_review_batch1/batch2=pass`。剩余 Batch 3 (T9-T14) 前端实施 + 收尾。

Planner 启动清单（按顺序）：

1. **state.json 同步**：检查 `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json` 的 updated_at 是否反映 Batch 2 T7/T8 completed 状态（当前 2026-04-13 19:40:18 的 T7/T8 已标 completed，但 Batch 2 R3 PASS 后未再更新 timestamp）。若需刷新则 commit `state: Batch 2 R3 PASS 后同步`

2. **P001 处置决策**：
   - INV-002（L1 考频计算只涉及 L1 concepts）：重新映射到真实存在的入口级测试（建议指向 `tests/test_knowledge_tree/test_sync_service.py` 或 `test_stats_service.py` 中已有的 L1-only 断言，如无则在 T14 补一个）
   - INV-004（前端子组件契约不变）：映射到 Batch 3 即将产出的 T10-T13 组件测试
   - 两种方案：(a) 合并 T14 收尾处置（推荐）；(b) T14-bis 独立 Task
   - 在 plan Contract Pack 段追加 **Round 3 修复 (P001)** 标注（已有 R2 修复 INV-005 的格式参考 plan:3990）
   - 本步骤必须在派发 Batch 3 Executor 之前完成，否则 Gate 2 R1 会再报 P001

3. **Batch 3 拆分决策**：
   - plan T9-T14 是 6 个前端 Task，直接一批次可能 commit 范围过大
   - 建议拆分：Batch 3.a = T9-T10（热力色工具 + ConceptMapPanel 升级）/ Batch 3.b = T11-T12（NodeDetailDrawer + 教材导航）/ Batch 3.c = T13-T14（ModuleOverviewPanel 增强 + 收尾 + P001 处置）
   - 或 **单批完整**：T9-T14 一批次（更快但 Gate 2 diff 会很大，审查难度上升）
   - 决策依据：前端 diff 行数 + 测试独立性 + R1 FAIL 时的回滚成本

4. **派发 Executor**：
   - 派发前更新 state.json 中即将执行的 Task status=in_progress
   - 使用 handoff-card skill 生成 batch3.{a,b,c} 交接卡，包含：本交接卡「前端接入契约」「测试风格约束」「前端技术栈约束」「已落盘但 plan 未显式声明的前端文件」段原样继承
   - Executor 在新会话用 executing-plans skill 执行

5. **Batch 3 Gate 2 审查**：Executor 输出审查交接单后，使用 codex-review skill 进行 GPT 代码审查（Code Review 模式）。每批次最多 3 轮。

6. **Phase 1 收尾（T14 完成时）**：
   - design.md 头部追加 `> [2026-04-XX HH:MM:SS 实现完成] Commits: ff59672..<T14 final commit>`
   - 项目级 CLAUDE.md（`edu-cloud/CLAUDE.md`）「已完成设计」段追加知识图谱 Phase 1 条目
   - 全局 CLAUDE.md（`~/CLAUDE.md`）「已完成设计」段同步（按现有格式，链接到 `edu-cloud/docs/plans/...`）
   - 写 reconciliation（若 T4；本 Phase 1 是 T3 无需）

关键约束（详见 handoff-batch3）：
- 前端 v3 字段 avg_difficulty=None / planning_weight 多为 None / ExamItem.question_number=int / options=raw JSON string
- 测试精确断言风格（禁 >= N / status in (200,404) / if photo:）
- controlled fixture 优先，不依赖真实 knowledge.db
- AntV G6 + Naive UI 现有栈，不引新前端依赖
- scope_guard: commit 只含本批次文件，每次 commit 前 `git diff --cached --name-only` 确认
- doc_sync_guard: 新组件/页面同步 edu-cloud/CLAUDE.md

完成每批次后输出审查交接单（路径 `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch3{.a|.b|.c}.md`）。使用 codex-review skill 进行 GPT 代码审查。
```
