---
type: handoff
created: 2026-04-09 20:39:50
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-knowledge-graph-viz-debate.md
plan: null
---

# 知识图谱多层教学模型重设计 — 会话交接卡

## 约束与偏好

**T3 流程（Phase 1 先做设计+计划）。** 本交接卡源自 brainstorming 会话，尚未进入 writing-plans。新会话需要：先读辩论共识 → 写 Phase 1 正式设计文档 → 写计划 → Gate 1 审查。

### 当前状态

Claude×GPT 4 轮辩论 + 外部深度调研已收敛。辩论共识和路线图写入：
`C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-knowledge-graph-viz-debate.md`

核心结论：当前力导向图被用户否定。知识图谱需要从"概念+边"升级为"多层教学知识模型"（概念骨架 + 学习进阶 + 误概念 + 跨学科框架 + 证据联动）。5 阶段路线图已收敛，Phase 1 是"可信骨架"。

### 需要新会话做的事

1. 读辩论共识文档，理解全部上下文
2. 为 Phase 1（可信骨架）写正式设计文档（brainstorming skill，但辩论已完成，直接进入设计呈现）
3. Phase 1 设计通过后写实现计划（writing-plans skill）
4. Gate 1 审查（codex-review skill）

### Phase 1 交付物概要

- Graph API v2 契约（补 description/confidence/hard_in_out_count/external_hard_refs）
- 关系审查工作台 v1（按概念审核关系，支持编辑/确认/驳回）
- 质量巡检脚本（孤立点/SCC/弱连通/低置信度/跨模块硬前置）
- 发布规则 v1（默认只展示已审核内容）

### 实际数据（辩论中 GPT 查询 knowledge.db 确认）

- 108 L1 概念，分属 5 模块 10 BigConcept
- 335 条关系：147 hard + 128 soft + 31 bridge + 29 contrast
- prerequisite_hard 无环（DAG），6 个弱连通分量
- 26 条跨模块硬前置（主要 M1 → M2/M3/M4/M5）
- 所有 108 个 L1 都有 description

### 用户偏好

- 质量优先，知识图谱是最关键最核心的内容
- 知识图谱 ≠ 掌握度图谱（纯结构 vs 学情叠加，严格分层）
- 可视化服务模型，不独立追求好看
- 首要用户是教师（教研/备课/审核）

### GPT 辩论日志

辩论共识文档中已包含全部结论。GPT MCP 会话 threadId: `019d720d-544f-7752-9d55-993d7bf43381`（如需追问可继续）。

## 启动 Prompt

```
[edu-cloud] Planner | 2026-04-09 20:39:50
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-knowledge-graph-model-handoff.md。
读取辩论共识: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-knowledge-graph-viz-debate.md。

当前任务：为知识图谱多层教学模型 Phase 1（可信骨架）写正式设计文档和实现计划。

辩论已完成（4 轮 + 外部调研），共识和路线图在辩论文档中。直接进入设计呈现（brainstorming skill 的"Present design"阶段），不需要重新探索。设计通过后使用 writing-plans skill 写计划。计划 commit 后使用 codex-review skill 进行 Gate 1 审查。
```
