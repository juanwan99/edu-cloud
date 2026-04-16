# Code Review R2 报告 — haofenshu Phase 1 Batch 1

[edu-cloud] GPT Reviewer | 2026-04-13 19:37:35
Commit: e64957a
结论: PASS

## 第一段：测试充分性 (Test Adequacy)

独立执行 `python -m pytest tests/test_alembic_migration.py -v`，结果为 3/3 PASS；`tests/test_alembic_migration.py:46-129` 仍然覆盖了 upgrade、head 单一性、downgrade 三个 gate，因此 R1 中被跳过的 migration smoke 已被真正恢复，INV-04（Alembic 可逆）在 SQLite smoke 上重新成立。

F003 的反证也独立成立。`src/edu_cloud/modules/menu/service.py:24-38` 目前对顶级菜单和子菜单都显式 `.order_by(MenuConfig.sort)`；`tests/test_menu/test_menu_service.py:131-186` 刻意按逆序插入 `report(sort=2)` 再插 `exam(sort=1)`，并对顶级/子级都做精确序列断言。我临时删除顶级查询上的 `.order_by(MenuConfig.sort)` 后，执行 `python -m pytest tests/test_menu/test_menu_service.py::TestMenuService::test_sorted_by_sort_field -v`，测试稳定失败，报错为 `AssertionError: assert ['report', 'exam'] == ['exam', 'report']`；恢复文件后同一测试重新 PASS，说明该测试已不是 tautology。

Pre-existing failures 方面，今日独立验证的证据比交接单更窄但不指向 R2 回归。当前状态直接执行 `python -m pytest tests/test_ai/test_tool_access_fail_closed.py tests/test_services_exam/test_scan_pipeline.py::TestBarcodeFallbackObservability tests/test_api_exam/test_pipeline_save_answer.py::test_S8a_factory_orphan_logs_warning -v`，结果为 `2 failed, 9 passed`，仅稳定失败 `test_no_capability_record_rejects` 与 `test_partial_capability_match_rejects`。随后仅将 `alembic/versions` 和 `tests/test_menu/` 临时切回 `e64957a~1` 后重跑同一命令，结果仍为相同的 `2 failed, 9 passed`。这说明今日可复现的失败并非由 R2 引入；但交接单中“相同 5 个失败全部 pre-existing”的表述，今天无法按原口径完整复现。

## 第二段：行为正确性 (Behavioral Correctness)

Phase 0 Contract Pack 复核通过。`docs/plans/2026-04-12-haofenshu-phase1-plan.md:38-43` 的 INV-01/02/04/05/06 均未被 R2 破坏；其中 INV-02 的 F002 追认与 Task 2 Step 7 说明已经同步到 `docs/plans/2026-04-12-haofenshu-phase1-plan.md:39,697-702`，设计文档补充在 `docs/plans/2026-04-12-haofenshu-biz-replication-design.md:44-49`，项目总览同步在 `CLAUDE.md:680`。R1 中把 migration smoke 降格为 skipped/test_debt 的做法，在 R2 交接单里已被撤销，风险模块 `alembic/versions/` 的缓解方式重新回到“downgrade 测试 + SQLite smoke test”。

F001 修复是真修复，不是 workaround。6 个 migration 的 DDL 处理都改成了方言中立形式，而且业务语义未变：`alembic/versions/1a325e38e941_add_entity_memory_and_project_state_.py:23-37,45-62,77-84` 将两个唯一约束内嵌到 `create_table`，downgrade 直接 `drop_table`，列名/列型/约束列集合不变；`alembic/versions/b08103b3a6f5_add_unique_constraint_on_questions_.py:21-31` 用 `batch_alter_table` 包住同一唯一约束的增删；`alembic/versions/a370e2771c6d_add_knowledge_hierarchy_columns.py:25-37,53-65` 只是把原有 add/alter/drop column 操作搬进 batch mode，字段集合和 `knowledge_level` 的 4→10→4 对称性保留；`alembic/versions/2a40f59215de_add_edge_review_status.py:29-33`、`alembic/versions/52af1c37bf14_add_menu_and_analysis_tables.py:97-105`、`alembic/versions/c9587c787c6b_add_agent_profiles_and_agent_runs_.py:63-74` 也都仅把原本 SQLite 不兼容的独立 `drop_column`/`drop_index` 改为 batch 形式。`revision/down_revision` 没有改动，`tests/test_alembic_migration.py::test_migration_head_is_single` 也已 PASS，说明 revision graph 完整性未受损。

F001 的 2→6 扩面是合理且充分的。我对 `alembic/versions/` 执行 `rg -n "op\\.(create_unique_constraint|alter_column|drop_column|drop_constraint)|batch_op\\.(create_unique_constraint|alter_column|drop_column|drop_constraint)" alembic/versions`，结果只剩 6 个目标 migration 里的 `batch_op.*` 调用，没有任何残留的 standalone `op.create_unique_constraint` / `op.alter_column` / `op.drop_column` / `op.drop_constraint`；因此不存在明显 under-fix。与此同时，代码层面的改动也只限于这类同模式 DDL wrapper，没有改 revision、FK 目标、列定义或业务字段，未见 over-fix。

F002 的追认在文档间是自洽的，且没有发现新的运行时副作用。`src/edu_cloud/api/app.py:305-316` 仍然实际挂载了 `conduct_admin_router`；该 router 自身前缀是 `/api/v1/conduct`，每个端点仍带有 `require_permission(...)` 和 class/resource scope 校验，例如 `src/edu_cloud/modules/conduct/admin_router.py:30-45`。R2 对 F002 的处理是“把已批准的行为变更补记进 plan/design/CLAUDE”，而不是再引入新的 API 面变化。

F003 的测试防退化能力已建立。`tests/test_menu/test_menu_service.py:131-186` 现在明确构造逆序 fixture，并用精确列表断言顶级与子级顺序；删除实现中的排序语句会立即红测，说明该用例能真实守护 `MenuService` 的排序行为，而不是只验证“查询结果非空”或“sort 值递增”这种弱断言。

## 第三段：未测试风险 (Non-tested Risks)

R2 仍然没有做 PostgreSQL 实库 migration replay；当前对“PG 语义不变”的判断主要来自 Alembic 语义等价性和 SQLite smoke 的补强，而不是双方言实跑。这是一个剩余风险，但就本次修改面来看属于低概率残余，不构成 Gate blocker。

另一个剩余风险在于全量失败口径。今天可独立确认的 pre-existing 只有 2 个稳定失败；另外 3 个被交接单标为 flaky 的测试，在“当前状态”和“临时回退 R2 相关路径”两侧都未失败，因此我能确认的是“未见 R2 相关性”，不能确认“今天仍然精确复现相同 5 失败”。

## R1 finding 复核

| Finding | R1 | R2 终态 (Executor 声明) | GPT 复核结论 |
|---------|----|----|----|
| F001 | HIGH test-gap | resolved-correct | verified |
| F002 | MED behavior_change approved | resolved-correct (approved) | verified |
| F003 | HIGH test-gap | resolved-correct | verified |

## 新发现清单（R2 新 finding，如有）

- ID: R2-F001
- Severity: LOW
- Category: design-concern
- Type: defect_fix
- Before-behavior: R2 交接单将“5 个全量失败全部为 pre-existing”表述为已通过对照实证确认。
- After-behavior: 今日独立对照只能稳定确认 2 个 AI fail-closed 失败在 R2 前后都存在；其余 3 个 flaky 用例在两侧都 PASS，因此只能确认“未见与 R2 相关性”，不能确认“同一轮精确复现相同 5 失败”。
- Evidence: docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch1-r2.md:67-83；独立执行两轮 `python -m pytest tests/test_ai/test_tool_access_fail_closed.py tests/test_services_exam/test_scan_pipeline.py::TestBarcodeFallbackObservability tests/test_api_exam/test_pipeline_save_answer.py::test_S8a_factory_orphan_logs_warning -v`，当前态与临时切回 `e64957a~1` 相关路径后均为 `2 failed, 9 passed`。
- Impact: 不指向 R2 代码回归，也不影响本轮 Gate 结论；但交接单证据口径较 today-reproducible evidence 更强，审计可追溯性略受影响。
- Repair hypothesis: 将交接单/后续报告中的表述收窄为“2 个稳定 pre-existing 已独立确认；3 个 flaky 用例今日未复现、但两侧对照均未显示与 R2 相关”，避免继续声称“同一轮精确复现相同 5 失败”。

## 行为变更审批记录（如有 behavior_change finding）

| Finding ID | 行为变更摘要 | Before | After |
|-----------|-------------|--------|-------|
| F002 | Batch 1 追认保留 `conduct_admin_router`，纳入 28 个 `/api/v1/conduct/classes/*` 端点 | Batch 1 范围仅新增 `/api/v1/menus` | Batch 1 新增 `/api/v1/menus`，并按用户批准保留已挂载的 `conduct_admin_router` |

## PASS/FAIL 判定依据

按 `review-templates.md` 的 PASS/FAIL 规则，只有未修复的 HIGH/MED `code-bug` 或 `test-gap` 才会阻塞。本轮对 F001 和 F003 的独立复现均已验证修复成立，F002 为已批准的 behavior_change 且追认文档一致；新增的 R2-F001 仅为 LOW `design-concern`，不阻塞 Gate。因此本轮结论为 PASS。

## Inv-conflict 标注

无 direct inv-conflict。F001 重新满足 INV-04；F002 已同步更新 INV-02 的文字边界；今日对全量失败的独立复现未显示任何由 R2 新引入、且直接违反 Contract Pack 的问题。
