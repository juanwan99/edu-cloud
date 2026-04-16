---
type: handoff
created: 2026-04-13 10:39:22
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md
review: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan-review.md
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-gates.json
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json
parent_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff.md
---

# 项目背景（简版）

- **项目**: edu-cloud（多校协同教育云平台，port 9000，FastAPI + SQLAlchemy async + Vue 3）
- **本次任务**: 知识图谱 Phase 1 优化 — 把 knowledge.db 里原本不暴露的考频/教材章节/MCU 规划权重等 7 类资产，通过 ConceptStats 投影表 + Graph API v3 合并到节点返回，前端加热力着色 + 高考真题/学习单元标签页
- **设计来源**: `2026-04-12-knowledge-graph-optimization-design.md`（4 Phase 全局规划，本次只做 Phase 1）
- **知识库路径（只读素材）**: `C:/Users/Administrator/edu-knowledge-base/knowledge.db`（34 张表）+ `C:/Users/Administrator/Archive/MCU-03/knowledge_skeleton/`（7 类规划资产）
- **Tier**: T3 流程。Gate 1 (plan_review) 已 PASS（R1-R5 FAIL → R6 PASS 10 finding resolved）。下一 Gate 为 `code_review`（每批一次）

# 已完成进度（断点）

| Task | 状态 | Commit | 产物 |
|------|------|--------|------|
| T0 环境准备与契约验证 | ✅ completed | — | 数据链路验证通过：Concept=光合作用 / DAs=4 / Items=1260；knowledge_tree 基线 124 tests pass |
| T1 ConceptStats 模型 + Alembic 迁移 | ✅ completed | `77bbd9a` | `models.py` 新增 ConceptStats（FK CASCADE）；`alembic/versions/46b200fa9704_add_concept_stats_table.py`；`tests/test_knowledge_tree/test_models_stats.py`（4 tests pass）；`CLAUDE.md` 追加 concept_stats 条目 |
| T2-T6 Batch 1 剩余 | ⏸️ pending | — | 考频计算 / 章节聚合 / MCU 导入 / importance_score / sync 集成 |
| T7-T8 Batch 2 | ⏸️ pending | — | Graph API v3 / 真题 + 统计概览 API |
| T9-T14 Batch 3 | ⏸️ pending | — | 前端热力色 / ConceptMapPanel / NodeDetailDrawer / 教材导航 / ModuleOverviewPanel / 收尾 |

state.json 中 T0/T1 已标 completed，其余 pending。

# 约束与偏好（plan/design 未记录的增量）

## 环境约束（T1 执行时发现）

- **Alembic 链已存在 SQLite 不兼容上游迁移**：`b08103b3a6f5_add_unique_constraint_on_questions_` 使用 `op.create_unique_constraint()` 非 batch 模式，在 SQLite 上 `alembic upgrade head` 会 fail with `NotImplementedError: No support for ALTER of constraints in SQLite dialect`。**不要尝试跑 `alembic upgrade head` 做测试**；写迁移对称性测试时，直接加载新迁移文件 `importlib.util` 后独立调用 `mig.upgrade()/downgrade()`（T1 test_migration_symmetric 已有参考实现）
- **conftest.py 未开启 SQLite PRAGMA foreign_keys**：如要测 FK CASCADE，测试里先 `await db.execute(sa.text("PRAGMA foreign_keys = ON"))` 再做删除（T1 test_concept_stats_cascade_on_node_delete 已有参考）
- **autogenerate 无法工作**：因上游迁移 FAIL，`alembic revision --autogenerate` 会报 Target database is not up to date。改用 `alembic revision -m "..."`（手写 upgrade/downgrade）

## 设计/实现硬约束（来自 plan Contract Pack，必读）

- **INV-002 L1-only 图谱**：`compute_exam_frequency` 等服务只返回 L1 concepts，严禁混入 L0 evidence。测试时要有反例断言"L0 id 不会出现在结果中"
- **INV-004 前端子组件契约不可改**：`TreeNavPanel.emits('select-node', node)` 传完整对象不是 id；`ModuleOverviewPanel`/`TreeNavPanel` 原有 props/emits 保持，**只能追加 optional props**（Phase 1 F002 教训）
- **NodeDetailDrawer 追加模式**：`evidence` + `questions` 原标签**不可移除**，7 tab 改造必须保留旧 tab（F007 behavior_change 规避方式）
- **CE-001/CE-002 禁止弱断言**：前端测试禁用 `wrapper.exists()` / `expect(status).to.be.oneOf([200,404])` 这类模糊断言

## 流程硬约束

- Batch 1 (T0-T6) 完成后必须走 codex-review (code) Gate 2，PASS 才能进 Batch 2。单批最多 3 轮修复
- 行为变更（未在 Contract Pack 列出的 public API 变更或 invariant 偏离）必须标 process finding，不静默引入
- 测试 fixture 用现成的 `db` / `admin_headers` / `client`（conftest.py），不要新建
- sync 入口是 `sync_knowledge_on_startup`（sync_service.py:188），不要写 `sync_knowledge_tree`
- doc_sync_guard：新增代码文件（models.py 变更、新 test 文件、新迁移、新 service）**必须**同步更新 `CLAUDE.md`（数据模型表 / API 表 / 项目结构段），否则 `git commit` 被阻断

## 工作节奏（上一会话经验）

- 单会话大概率跑不完 Batch 1（T2-T6 仍有 ~900 行 plan，含 4 个算法服务 + MCU 导入 + sync 集成）。建议每完成 2-3 个 Task 就 commit，上下文告警时及时再写 handoff
- `python -m pytest tests/test_knowledge_tree/` 全量约 150 秒，不要对每个小改动都跑全量；用 `-k` 或 file::test 定位

# 启动 Prompt（复制到新会话）

```
[edu-cloud] Executor | 2026-04-13 10:39:22
项目目录: C:\Users\Administrator\edu-cloud

读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-mid-batch1.md
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md 从 T2 继续执行。

进度：T0 + T1 已完成并 commit (77bbd9a)，state.json T0/T1=completed。
剩余 Batch 1：T2 考频计算 / T3 章节聚合 + 前置深度 / T4 MCU 导入 / T5 importance_score / T6 sync 集成。

Gate 1 已 PASS；Gate 2 (code_review) 在 Batch 1 完成后执行。使用 executing-plans skill。

关键约束（详见 handoff）:
- INV-002 L1-only：服务层只返回 L1 concepts
- INV-004 前端子组件契约：只能追加 optional props
- CE-001/CE-002：禁弱断言
- Alembic：上游 b08103b3a6f5 在 SQLite 上 fail，迁移测试要用 importlib 独立加载新迁移（T1 已有参考）
- conftest 未开 SQLite FK PRAGMA，测 CASCADE 要测试内 PRAGMA
- 新代码文件必同步 CLAUDE.md（doc_sync_guard 硬阻）

完成 Batch 1 后输出审查交接单 (路径 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch1.md)，使用 codex-review skill 进行 GPT 代码审查。
```
