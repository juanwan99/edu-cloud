[edu-cloud] Executor→Reviewer | 2026-04-04 21:32:00
## 审查交接单: Task 1-5 (Batch 1 基础设施)
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-04-agent-evolution-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | 8 张表 + migration | commit 1a0c1f2, 5 model files + 11 tests | ✅ | 8 张表全部创建，Alembic migration 待统一生成（plan 中 Step 13 标注但 SQLite 测试不需要） |
| T2 | DataScope frozen dataclass + DataScopeBuilder 8 角色推导 | commit ced1ed2, data_scope.py + 11 tests | ✅ | frozen=True, PERSONA_MAP 8 角色, fail-closed DataScopeBuildError |
| T3 | ScopedQuery WHERE 注入 + 参数放大拒绝 | commit 85ddbe9, scoped_query.py + 10 tests | ✅ | apply() 5 层过滤, validate_param() 放大拒绝 |
| T4a | parent 角色加 USE_AI_CHAT | commit 6827b20, permissions.py + 3 tests | ✅ | 仅加 USE_AI_CHAT，不影响其他角色 |
| T4b | ToolAccessResolver fail-open→fail-closed | commit (in T4b), tool_access.py + capability_service.py + 7 new tests + 3 existing tests updated | ✅ | 无记录=拒绝, requires_capabilities=[] 不受影响 |
| T5 | ScopeVersionChecker DB 持久化 | commit 273f634, scope_version.py + 10 tests | ✅ | get_current_version/is_valid/bump/bump_school 全实现 |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| guardian unique constraint | test_agent_models::test_guardian_link_unique_constraint | `python -m pytest tests/test_models/test_agent_models.py::test_guardian_link_unique_constraint -v` | PASSED | 不适用：新表 |
| workflow idempotency key | test_agent_models::test_workflow_idempotency_key_unique | `python -m pytest tests/test_models/test_agent_models.py::test_workflow_idempotency_key_unique -v` | PASSED | 不适用：新表 |
| DataScope frozen | test_data_scope::test_data_scope_is_frozen | `python -m pytest tests/test_ai/test_data_scope.py::test_data_scope_is_frozen -v` | PASSED | 不适用：frozen=True 是 Python 原生保证 |
| parent DataScope | test_data_scope::test_build_scope_parent | `python -m pytest tests/test_ai/test_data_scope.py::test_build_scope_parent -v` | PASSED | 不适用：新增逻辑 |
| fail-closed unknown role | test_data_scope::test_build_scope_fail_closed_missing_role | `python -m pytest tests/test_ai/test_data_scope.py::test_build_scope_fail_closed_missing_role -v` | PASSED | 不适用：新增逻辑 |
| ScopedQuery school_id | test_scoped_query::test_scoped_query_injects_school_id | `python -m pytest tests/test_ai/test_scoped_query.py::test_scoped_query_injects_school_id -v` | PASSED | 不适用：新增逻辑 |
| ScopedQuery amplification | test_scoped_query::test_scoped_query_rejects_amplification | `python -m pytest tests/test_ai/test_scoped_query.py::test_scoped_query_rejects_amplification -v` | PASSED | 不适用：新增逻辑 |
| fail-closed no record | test_tool_access_fail_closed::test_no_capability_record_rejects | `python -m pytest tests/test_ai/test_tool_access_fail_closed.py::test_no_capability_record_rejects -v` | PASSED | TDD: 修改前此测试 FAIL（fail-open），修改后 PASS |
| scope version mismatch | test_scope_version::test_version_mismatch_fails | `python -m pytest tests/test_ai/test_scope_version.py::test_version_mismatch_fails -v` | PASSED | 不适用：新增逻辑 |
| scope version persistence | test_scope_version::test_bump_persists_across_instances | `python -m pytest tests/test_ai/test_scope_version.py::test_bump_persists_across_instances -v` | PASSED | 不适用：新增逻辑 |

### 验证清单自检
- ✅ 8 张表全部继承 Base + IdMixin + TenantMixin（需要 school_id 的）+ TimestampMixin
- ✅ 所有 FK 指向正确表（users/exams/schools/agent_findings/workflow_runs）
- ✅ 幂等键字段有 UniqueConstraint + index（workflow_runs, agent_findings）
- ✅ status 字段用 String 不用 Enum
- ✅ DataScope frozen=True
- ✅ PERSONA_MAP 覆盖 8 角色
- ✅ 家长从 guardian_student_links 推导 visible_student_ids
- ✅ fail-closed: 未知角色抛 DataScopeBuildError
- ✅ ScopedQuery school_id 对非跨校角色强制注入
- ✅ validate_param 防放大
- ✅ tool_access.py 默认策略改 deny
- ✅ capability_service.py check_capability 默认改 deny
- ✅ scope_versions DB 持久化（跨进程共享）
- ✅ parent 有 USE_AI_CHAT 权限
- ✅ 52 新增测试全部 PASS
- ✅ 314 B1 相关模块测试全部 PASS

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: DataScopeBuilder.build() with nonexistent role_id
  运行命令: `python -m pytest tests/test_ai/test_data_scope.py::test_build_scope_fail_closed_missing_role -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 未知 role_id 正确抛出 DataScopeBuildError

- 字符串匹配/条件判断的假阴性：
  构造输入: ScopedQuery.validate_param("class_id", "c-forbidden") with scope visible_class_ids=["c1","c2"]
  运行命令: `python -m pytest tests/test_ai/test_scoped_query.py::test_scoped_query_rejects_amplification -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 超出 scope 的参数被正确拒绝

- 状态变量/锁的异常路径：
  构造输入: ToolAccessResolver.resolve with empty capabilities dict
  运行命令: `python -m pytest tests/test_ai/test_tool_access_fail_closed.py::test_no_capability_record_rejects -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 无 capability 记录时正确拒绝（fail-closed）

使用 codex-review skill 进行 GPT 代码审查。
