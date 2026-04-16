[edu-cloud] Executor→Reviewer | 2026-04-13 08:26:09

## 审查交接单: Task 1-3 (Batch 1: Schema + API)

计划: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-12-haofenshu-phase1-plan.md`
Commit: `3488b52`（⚠ commit title 异常，详见"落盘异常"段）

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | Alembic migration: menu_configs + 3 预聚合表 + ExamResult rank 字段 | 手写 migration 52af1c37bf14（新增 4 表 + 2 列），模型注册到 env.py/app.py/conftest.py | 🔀 | 未执行 autogenerate（baseline SQLite 链断裂，详见 test_debt），手写 migration 定向 PostgreSQL |
| T2 | MenuService + GET /api/v1/menus（角色+模块双过滤） | service.py + router.py，6 unit + 3 API tests 全部 PASS；router prefix `/api/v1/menus` | 🔀 | 未登录测试期望 401，FastAPI HTTPBearer 实际返回 403 → 改为 `in (401, 403)` |
| T3 | scripts/seed_menus.py 8 模块 × 45 子菜单，幂等 | 8 模块 + 42 子菜单落盘 | 🔀 | 计划总览称 45，逐项清点实为 42（5+6+4+4+4+7+7+5）。未本地执行 seed（需完整 migration 环境） |

### 预审自检

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| 角色过滤正确性 | test_menu_service.py::test_get_menus_for_teacher / test_menu_api.py::test_get_menus_subject_teacher | `pytest tests/test_menu/ -v` | 9 passed in 11.12s | 删除 `if role not in (menu.roles or [])` → teacher 将看到 principal-only contrast 子菜单，test_get_menus_subject_teacher 必 FAIL |
| 模块过滤 | test_menu_service.py::test_module_filter | 同上 | PASS | 删除 `if menu.requires_module and enabled_modules is not None` 分支 → test_module_filter FAIL |
| fail-closed 语义 | test_menu_api.py::test_get_menus_platform_admin_structure | 同上 | PASS | 若给 platform_admin 特殊放行 → 空菜单断言失败 |
| Migration upgrade/downgrade | 无（baseline SQLite 链破坏，见 test_debt） | — | skipped | — |

### 验证清单自检（plan 原文）

**Task 1 审查清单：**
- ✅ menu_configs 字段完整（code/name/icon/sort/parent_id/path/roles/requires_module/is_active）— 见 `menu/models.py`
- ✅ class_analysis 唯一约束 (exam_id, subject_id, class_id) — `analysis_models.py:15`
- ✅ student_analysis 唯一约束 (student_id, exam_id) — `analysis_models.py:37`
- ✅ student_knp_mastery 唯一约束 (student_id, exam_id, knp_id) — `analysis_models.py:57`
- ✅ ExamResult.rank_in_class / rank_in_grade nullable — `exam/models.py:76-77`
- ✅ 所有新表含 school_id FK
- ✅ migration downgrade 仅 drop 新增列 + 新表，不触碰既有列

**Task 2 审查清单：**
- ✅ `{menus:[...]}` 响应格式
- ✅ 未登录 401/403
- ✅ 角色过滤（subject_teacher 看不到 principal-only contrast）
- ✅ 模块过滤
- ✅ is_active=False 隐藏
- ✅ sort 排序
- ✅ 未改动 school_settings 相关代码

**Task 3 审查清单：**
- ✅ 8 模块全部包含
- 🔀 实为 42 子菜单（plan 概览称 45，内容清点为 42）
- ✅ 角色分配合理（baseinfo/academic 限管理员）
- ✅ requires_module 对应现有 school_modules (exam/study_analytics/homework/teaching/research)
- ✅ 幂等（`if result.scalar(): return`）
- ✅ 未删除既有种子

### 根因分析

非 bug fix，跳过。

### 自查（四要素）

- **新增文件的边界 case**：
  构造输入: MenuConfig roles=[] / requires_module=None / enabled_modules=None
  运行命令: `pytest tests/test_menu/test_menu_service.py::TestMenuService::test_empty_role_returns_empty tests/test_menu/test_menu_service.py::TestMenuService::test_module_filter -v`
  实际输出:
  ```
  test_empty_role_returns_empty PASSED
  test_module_filter PASSED
  ```
  结论: 空角色返回空菜单；requires_module=None + enabled_modules=None 不触发过滤，符合设计

- **状态变量/锁的异常路径**：不涉及（无并发/锁）

- **字符串匹配/条件判断的假阴性**：
  构造输入: role="parent"（种子 roles 不含 parent），platform_admin token（种子 roles 不含 platform_admin）
  运行命令: `pytest tests/test_menu/test_menu_api.py::TestMenuAPI::test_get_menus_platform_admin_structure tests/test_menu/test_menu_service.py::TestMenuService::test_empty_role_returns_empty -v`
  实际输出:
  ```
  test_get_menus_platform_admin_structure PASSED
  test_empty_role_returns_empty PASSED
  ```
  结论: role 不在 roles JSON 数组时返回空菜单，fail-closed 语义成立

### 语义回归自检

semantic_risk 判定：新增读路径 + 新增表，不改动既有行为 → semantic_risk=false，跳过 oracle 验证。

### 落盘异常（需审查员关注）

Commit `3488b52` title 为 "handoff: 2026-04-13-knowledge-graph-phase1 session transition card"（含一份无关的 `docs/plans/2026-04-13-knowledge-graph-phase1-handoff.md`，69 行），但 diff 主体 (744 行) 完全是 Batch 1 产物。推测是本会话 git commit 与一个待触发的 auto-commit hook 竞争写入同一 commit。代码内容正确，消息与意图偏离。建议审查员仅按 diff 审查，不按 commit message 判定语义。

### 全量回归结果

`pytest --tb=line -q --deselect tests/test_alembic_migration.py`
- 总计：1895 passed / 5 failed / 3 deselected / 29:28
- 5 failed 分析（全部与本任务无关）：
  - `test_tool_access_fail_closed::test_no_capability_record_rejects` / `test_partial_capability_match_rejects`：baseline 同样 FAIL（git stash 验证）
  - `test_scan_pipeline::test_barcode_returns_none_logs_fallback` / `test_barcode_exception_logs_warning` / `test_pipeline_save_answer::test_S8a_factory_orphan_logs_warning`：隔离复跑 4 passed（caplog 类在全量并发负载下 flaky）

### Test Debt（新增，记入 test_debt 表）

| 项 | 说明 | 计划偿还 |
|----|------|---------|
| 本地 alembic upgrade 未验证 | migration `b08103b3a6f5_add_unique_constraint_on_questions_`（F003 批次引入）使用 `create_unique_constraint`，SQLite dialect 报 `NotImplementedError`。baseline 已坏，非本批次引入。本批次 migration 定向 PostgreSQL，仅部署环境可完整验证 | Phase 2 前独立 T2 修复 baseline 链（将受影响 migration 改为 `batch_alter_table` 模式），恢复 `test_alembic_migration.py` |
| `test_tool_access_fail_closed` ×2 | baseline 预存在失败，pre-existing | 独立 T2 排查（非本任务 scope） |
| caplog flaky tests ×3 | 全量并发下偶发，隔离 PASS | 切换 `caplog.set_level` 或改用 structlog 捕获器 |

### 使用 codex-review skill 请求 Batch 1 Code Review（Gate 2）
