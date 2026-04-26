---
type: handoff
created: 2026-04-13 19:14:24
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md
review_report_batch1: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-report-batch1.md
review_handoff_batch1: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch1.md
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-gates.json
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json
parent_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff.md
mid_batch1_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-mid-batch1.md
---

# 项目背景（简版）

- **项目**: edu-cloud（多校协同教育云平台，FastAPI + SQLAlchemy async + Vue 3，后端 port 9000）
- **本次任务**: 知识图谱 Phase 1 优化 Batch 2 — 把 Batch 1 投影到 PG 的 concept_stats 通过 Graph API v3 暴露给前端，并补 `/graph/{id}/exam-items` 和 `/stats/overview` 两个新端点
- **Tier: T3 流程**（2 窗口模式：Planner commit plan → GPT Plan Review → Executor 执行 → GPT Code Review per batch）
- **Gate 1 plan_review** 已 PASS（R6，11/11 finding resolved，上上会话）
- **Gate 2 code_review_batch1** 已 PASS（R1 FAIL → R2 PASS，本轮上一会话）。Batch 2 完成后再走一次 Gate 2 (code_review_batch2)

# 已完成进度（断点）

| Task | 状态 | Commit | 产物 |
|------|------|--------|------|
| T0 环境准备 | ✅ | — | 基线 124 tests + state sidecar（上上会话） |
| T1 ConceptStats 模型 + 迁移 | ✅ | `77bbd9a` | models.py + Alembic `46b200fa9704` + 4 tests |
| T2 考频/难度/覆盖率 | ✅ | `1c3c1a2` | stats_service.py + 4 tests（🔀 avg_difficulty 源） |
| T3 章节聚合+前置深度 | ✅ | `1bdad6b` | textbook_chapters + Kahn 拓扑 + 3 tests |
| T4 MCU 权重导入 | ✅ | `e534dfa` | scripts/import_mcu_planning_weights.py + 3 tests |
| T5 importance+compute_all | ✅ | `fe9faf2` | importance 公式 + UPSERT + 2 tests |
| T6 sync 集成 | ✅ | `d0ed76e` | sync 末尾触发 stats + 2 tests |
| **Batch 1 Gate 2 R2 修复** | ✅ | `bcb1971` | _ensure_concept_stats + 4 pairwise monotonic + F003 重写 |
| **Gate 2 PASS** | ✅ | `093e255` | gates.json code_review_batch1=pass |
| T7 Graph API v3 | ⏸️ pending | — | 合并 stats 到 /graph 节点返回，保留 v2 字段 |
| T8 真题+统计概览 API | ⏸️ pending | — | 新 /graph/{id}/exam-items + /stats/overview |
| T9-T14 Batch 3 | ⏸️ pending | — | 前端热力色/ConceptMapPanel/NodeDetailDrawer/教材导航/收尾 |

state.json 中 T0-T6 已标 completed，T7 起 pending。

# Batch 1 收尾留下的增量约束（design/plan 未写，必读）

## 代码层约束（Batch 2 实现时触发）

1. **`_ensure_concept_stats(db, kb_path)` 契约（F001 Round 2 落地）**：
   - 位置: `src/edu_cloud/modules/knowledge_tree/sync_service.py` 末尾 + 模块私有
   - 语义: `ConceptStats` 表为空 → 调用 `compute_all_stats` 补算；非空 → 直接 return
   - **不自愈"非空但不完整"状态**（GPT R2 审查明确承认低风险）。Batch 2 若加字段或改写入语义，需考虑 startup 时是否应强制重算
   - skipped 和 synced 两条分支都会调用，不要在 T7/T8 里改回"只在 synced 触发"

2. **avg_difficulty 语义（T2 🔀 已接受）**：
   - `stats_service.compute_avg_difficulty` 用 `q_matrix.transfer_band`（near=2.0 / mid=3.0 / far=4.0）聚合，不是"题目实际难度"
   - T7 Graph API v3 返回此字段时**不要改字段名**，但 schema `Field.description` 或 docstring 可补一句"基于 transfer_band 的认知难度代理"防止下游误解
   - 零考频概念返回 `None`，前端需对应处理 null（Batch 3 T10 再处理）

3. **MCU 映射覆盖率 24/218（TD-002 已覆盖）**：
   - T8 真题查询走 `q_matrix.attribute_id → linked_concept_ids`，与 MCU 权重无关，不受影响
   - 但 T7 Graph API v3 返回 `planning_weight` 字段时，~84/108 concept 的值会是 NULL。Schema 必须声明 `Optional[dict]`，前端默认值走 fallback（Batch 3 T10 的着色模式处理）

4. **精确断言风格（F003 Round 2 落地）**：
   - T7 test_graph_v3.py 必须用 `stats_count == expected_count` 或 `.scalar_one()` 硬断言
   - 禁止 `total >= N` / `if photo:` / `assert result`（弱断言），见 `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch1.md` §F003
   - API 测试禁止 `assert status in (200, 404)`（CE-002，plan Contract Pack）

5. **单调性测试风格（F002 Round 2 落地）**：
   - T7/T8 若新增任何"聚合/加权/排序"逻辑，测试必须独立锁定每个输入维度的单调/非单调性。参考 `tests/test_knowledge_tree/test_stats_service.py::test_importance_score_monotonic_in_*`

## 环境/流程约束（继承自上个会话 handoff）

- **Alembic 上游链 SQLite 不兼容**：`b08103b3a6f5_add_unique_constraint_on_questions_` 非 batch 模式 `create_unique_constraint`，`alembic upgrade head` 在 SQLite fail。Batch 2 T7/T8 若需新迁移，用 `alembic revision -m "..."` 手写 upgrade/downgrade，测试用 importlib 独立加载（T1 有参考）
- **conftest.py SQLite FK PRAGMA 未开**：FK CASCADE 测试要测内 `PRAGMA foreign_keys=ON`
- **scripts/ 已是 package**（Batch 1 T4 落地了 `__init__.py`）：测试 import `from scripts.xxx import ...` 已可工作
- **seeded_concepts fixture**（T5 Batch 1 落地）：在 `tests/test_knowledge_tree/conftest.py`，调用 `sync_knowledge_on_startup` 同步真实 knowledge.db 到测试 DB；skipif KB_PATH 不存在
- **knowledge_tree 全量测试约 50s**，不要对每个小改动都跑全量，用 `-k` 或 file::test 定位
- **doc_sync_guard**（commit 硬阻）：T7 新 service 文件（如 `exam_items_service.py`）、T8 新路由端点要同步更新 `edu-cloud/CLAUDE.md`（项目结构段 + API 端点表）。否则 commit 被阻断
- **scope_guard**（commit 硬阻）：本 batch commit 只能含 plan T7/T8 声明的文件。T14 收尾 design.md 标记另算

## Git 操作陷阱（Batch 1 踩过的坑）

- **非本任务文件遗留在 staging 区**：会话开始时 `git status` 显示一堆其他会话的 M/A 文件已 staged。`git commit <path> -m ...` 仍会 include 这些 staged 文件（实测 commit 变成 12 文件）。**解决方案**：commit 前先 `git diff --cached --name-only` 确认；污染则 `git reset --mixed HEAD~1` 撤销后重新 add 指定文件
- **Windows git LF→CRLF 警告**忽略即可，不影响 commit

## 审查流程约束

- **🔀 偏离强制标注**：T7/T8 若发现 plan 里的 API shape 与 concept_stats 实际字段不符（例如 plan 要求返回 `difficulty` 但我们存的是 `avg_difficulty`），必须在审查交接单列 🔀 + 理由。禁止默认批量批准
- **behavior_change finding 单独确认**：GPT 可能将 API 路径/字段/响应码的任何偏离识别为 behavior_change，Executor 不可自行同意，必须让 Planner 或用户批准
- **Batch 2 的 Gate 2 最多 3 轮**。Round 1-2 Executor 修复；2 轮仍 FAIL → Planner 介入分类 code-bug / design-concern

# 启动 Prompt（复制到新会话）

```
[edu-cloud] Executor | 2026-04-13 19:14:24
项目目录: C:\Users\Administrator\edu-cloud

读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch2.md
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md 从 T7 继续执行。

进度：T0-T6 已完成并 Gate 2 PASS（R1 FAIL → R2 PASS）。最新 commit 093e255（R2 PASS 报告 + gates.json 回执）。state.json T0-T6=completed。

剩余 Batch 2（T7-T8）：
- T7 Graph API v3：合并 stats 到 /graph 节点返回，保留全部 v2 字段；新增 test_graph_v3.py
- T8 新端点：GET /api/v1/knowledge-tree/graph/{id}/exam-items（概念→高考真题查询）+ GET /api/v1/knowledge-tree/stats/overview（模块级覆盖率统计）

Gate 2 (code_review_batch2) 在 Batch 2 完成后执行。使用 executing-plans skill。

关键约束（详见 handoff-batch2）:
- `_ensure_concept_stats` 契约：空表才自愈，Batch 2 不要改回"只在 synced 触发"
- avg_difficulty 是 transfer_band 代理（2/3/4），Schema 字段名不变，docstring 补语义
- MCU 映射 ~84/108 为 NULL，planning_weight 字段声明 Optional[dict]
- 精确断言：stats_count == count，禁 `total >= N` / `if photo:` / `assert status in (200,404)`
- 单调性测试：任何新聚合/加权逻辑都要独立锁定每个输入维度
- Alembic 上游 SQLite fail，新迁移手写 + importlib 独立加载测试（T1 参考）
- Batch 2 新代码文件（service/router 端点）必同步 edu-cloud/CLAUDE.md（doc_sync_guard 硬阻）
- commit 前 `git diff --cached --name-only` 确认 staging 只含本 batch 文件（Batch 1 踩过 12 文件污染坑）

完成 Batch 2 后输出审查交接单（路径 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch2.md）。使用 codex-review skill 进行 GPT 代码审查。
```
