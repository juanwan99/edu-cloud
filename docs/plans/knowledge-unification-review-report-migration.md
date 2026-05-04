[edu-cloud] GPT Reviewer | 2026-05-04 07:16:19

## 审查报告: knowledge-unification migration (Task 2)

结论: **PASS**

| 字段 | 值 |
|------|-----|
| Subject | `alembic/versions/51c91f4d98e8_add_edge_evidence_and_node_course_code.py` |
| Reviewer | GPT-5.4 via MCP Codex (thread 019df01d-f14b-7960-a403-18e73d026777) |
| Round | R1 |

### 第一段：测试充分性（Test Adequacy）

本次变更为纯 schema 追加（3 个 nullable 列 + 1 个索引），无业务逻辑变更。
项目已有 `tests/test_alembic_migration.py` smoke test 覆盖 upgrade/downgrade 往返，GPT 验证 `pytest -q tests/test_alembic_migration.py` 通过 3 passed。
对纯 DDL 追加迁移，smoke test 是充分的测试覆盖。

## 变更理解

本次迁移将 Task 1（commit 2cb0435）已合并的 3 个 ORM 新列同步到数据库 schema：

1. `concept_graph_edges.evidence`（Text, nullable）— 存储边的证据来源文本
2. `concept_graph_edges.pedagogical_use`（String(30), nullable）— 边的教学用途标注
3. `concept_graph_nodes.course_code`（String(10), nullable, indexed）— 节点关联的课程代码

upgrade 按 edges→nodes 顺序添加列，downgrade 对称地先删索引再删列。down_revision 锚定到 `d8e2f4a1b3c5`（conduct_notifications），经 `alembic heads` 验证为迁移前的唯一 head。

## 对抗性审查

**PostgreSQL DDL 兼容性**：GPT 对 migration 做 offline DDL 渲染，生成 PG SQL 为：
- `ALTER TABLE concept_graph_edges ADD COLUMN evidence TEXT;`
- `ALTER TABLE concept_graph_edges ADD COLUMN pedagogical_use VARCHAR(30);`
- `ALTER TABLE concept_graph_nodes ADD COLUMN course_code VARCHAR(10);`
- `CREATE INDEX ix_concept_graph_nodes_course_code ON concept_graph_nodes (course_code);`

`op.f()` 命名函数在 PG 上正确展开为 `ix_concept_graph_nodes_course_code`，与 ORM 的 `index=True` 自动命名一致。

**downgrade 顺序**：PG 上删除被索引列时会自动级联删除索引，但显式先 `DROP INDEX` 再 `DROP COLUMN` 是安全且清晰的实践，无问题。

**SQLite batch_alter_table**：SQLite 对 `ADD COLUMN nullable` 直接支持，不需要 `batch_alter_table` 包装。现有 smoke test 在 SQLite 上已验证通过。

**down_revision 链路**：`alembic history` 确认 `51c91f4d98e8` 的 parent 为 `d8e2f4a1b3c5`（conduct_notifications），DAG 无分叉，链路正确。

## 发现清单

| ID | Severity | Category | Type | 问题 | 状态 |
|----|----------|----------|------|------|------|
| — | — | — | — | 无 finding | — |

PASS/FAIL 判定：无 HIGH/MED code-bug 或 test-gap → **PASS**
