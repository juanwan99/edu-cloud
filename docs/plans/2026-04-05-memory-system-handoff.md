---
type: handoff
created: 2026-04-05 16:12:17
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-evolution-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-memory-system-plan.md
---

## 约束与偏好

**T4 流程**（设计→计划→Gate 1 Plan Review→执行→Gate 2 Code Review）

- **Gate 1 待通过**: `docs/plans/2026-04-05-memory-system-gates.json` 中 plan_review 状态为 pending。执行前必须先通过 codex-review (plan) 审查。
- **Phase 1 已完成**: 多 Agent 编排引擎已交付（Supervisor + AgentTeam + 3 Teams，1327 tests）。Phase 2 在此基础上增加记忆层。
- **现有 agent_memories 表保留**: 不删除不修改，新建 entity_memory + project_state 两张独立表。session_memory.py 保持可用。
- **Tier 分级策略**: Tier 1 完整提取+注入，Tier 2 只注入不提取，Tier 3 全跳过。
- **测试需要 db_engine fixture**: MemoryStore 测试需要异步数据库会话，使用项目已有的 `conftest.py` 中 `db_engine` fixture（SQLite in-memory）。如果 fixture 名称不匹配需自行适配。
- **JSON 类型兼容**: PostgreSQL 用 JSONB，测试用 SQLite（JSON 存为 TEXT）。ORM 模型用 `JSON` 类型（SQLAlchemy 自动适配）。
- **Alembic migration**: env.py 中需新增 `from edu_cloud.models.memory import EntityMemory, ProjectState` 导入。
- **用户选择 subagent-driven-development**: 每个 Task 派发 subagent 执行。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-05 16:12:17
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-memory-system-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-memory-system-plan.md Task 1-7 执行。

执行前先运行 codex-review skill 对 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-memory-system-plan.md 进行 plan review（Gate 1）。Gate 1 通过后，使用 subagent-driven-development skill 逐 Task 执行。完成后输出审查交接单。
```
