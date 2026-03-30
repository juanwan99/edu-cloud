[edu-cloud] Executor→Reviewer | 2026-03-30 09:17:09
## 审查交接单: Task 1-8
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-30-phase1c-permission-engine-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | Capability ORM model + tests | commit 6773fd0, 4 tests | ✅ | |
| T2 | Capability service (init/get/set/check) + tests | commit 86dae0c, 9 service tests | ✅ | |
| T3 | Capability API router + scope guard + tests | commit 23758ab, 8 API tests | ✅ | |
| T4 | ScopeFilter utility class + tests | commit f3c652a, 6 tests | ✅ | |
| T5 | ScopeFilter 集成 list_assignments + tests | commit 997f9bb, 2 tests | ✅ | |
| T6 | AuditLog model + @audited decorator + context vars | commit 559e3bd, 7 tests | 🔀 | F-02 fix: user_id 改 nullable，默认 None（非 "-"） |
| T7 | @audited 集成 settings/assignments/selections | commit 1050518, 4 integration tests | 🔀 | F-04 fix: upsert_setting 手动 write_audit_log 区分 create/update; F-05 fix: _entity_type_lookup 用 select 替代 db.get; _snapshot 增加非 ORM 对象保护 |
| T8 | AuditLog API + migration + CLAUDE.md | commit 50a3c37, 7 API tests | 🔀 | F-06 fix: 新增 test_audit_log_captures_user_and_request_id; migration 去除重复表 |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 |
|---------------|------------------|---------|----------|
| 宽松策略验证 | test_capability_service::test_check_capability_no_record_default_allow | `python -m pytest tests/test_services/test_capability_service.py::test_check_capability_no_record_default_allow -v` | PASSED |
| 初始化幂等性 | test_capability_service::test_init_school_capabilities_idempotent | `python -m pytest tests/test_services/test_capability_service.py::test_init_school_capabilities_idempotent -v` | PASSED |
| 跨校越权拦截 | test_capabilities::test_capabilities_scope_guard | `python -m pytest tests/test_api/test_capabilities.py::test_capabilities_scope_guard -v` | PASSED |
| school 隔离 | test_scope_filter::test_scope_filter_school_id | `python -m pytest tests/test_services/test_scope_filter.py::test_scope_filter_school_id -v` | PASSED |
| ScopeFilter 集成 | test_teacher_assignment_service::test_list_assignments_with_scope | `python -m pytest tests/test_services/test_teacher_assignment_service.py::test_list_assignments_with_scope -v` | PASSED |
| create 审计记录 | test_audit_service::test_audited_decorator_create | `python -m pytest tests/test_services/test_audit_service.py::test_audited_decorator_create -v` | PASSED |
| delete 审计记录 | test_audit_service::test_audited_decorator_delete | `python -m pytest tests/test_services/test_audit_service.py::test_audited_decorator_delete -v` | PASSED |
| 无 user context 安全 | test_audit_service::test_audited_decorator_no_user_context | `python -m pytest tests/test_services/test_audit_service.py::test_audited_decorator_no_user_context -v` | PASSED |
| F-04 upsert create/update 区分 | test_audit_service::test_audited_upsert_setting | `python -m pytest tests/test_services/test_audit_service.py::test_audited_upsert_setting -v` | PASSED |
| F-06 API 级 user_id/request_id | test_audit_logs::test_audit_log_captures_user_and_request_id | `python -m pytest tests/test_api/test_audit_logs.py::test_audit_log_captures_user_and_request_id -v` | PASSED |
| 审计日志联动 | test_audit_logs::test_list_audit_logs_after_setting_change | `python -m pytest tests/test_api/test_audit_logs.py::test_list_audit_logs_after_setting_change -v` | PASSED |
| 跨校审计拦截 | test_audit_logs::test_audit_logs_scope_guard | `python -m pytest tests/test_api/test_audit_logs.py::test_audit_logs_scope_guard -v` | PASSED |

### 验证清单自检
- ✅ Capability model: UniqueConstraint 防重复, ForeignKey 关联 schools, 9 域 + read/write
- ✅ Capability service: init 幂等, check 宽松策略, set 校验 domain/action
- ✅ Capability API: require_permission(MANAGE_SCHOOL_SETTINGS), _check_school_scope 跨校防护
- ✅ ScopeFilter: school_id 始终过滤, None scope 跳过, from_role(admin)=None
- ✅ ScopeFilter 集成: scope=None 向后兼容, scope 有值时过滤
- ✅ AuditLog model: user_id nullable (F-02), school_id nullable, JSON before/after
- ✅ @audited decorator: create/delete/update 三种 action, best-effort 不崩溃
- ✅ current_user_var 中间件: best-effort JWT 解析, finally 块 reset
- ✅ F-04: upsert_setting 运行时 create/update 区分 + 测试验证
- ✅ F-05: _entity_type_lookup 返回 (model_class, lookup_column), 用 select 查询
- ✅ F-06: test_audit_log_captures_user_and_request_id 断言 user_id≠None, request_id 正确
- ✅ alembic migration: 仅添加 capabilities + audit_logs 表 (去除重复 school_modules/school_settings)
- ✅ CLAUDE.md: 新增能力配置+审计日志 API 端点, 数据模型, 项目结构更新

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: 无 capability 记录时调 check_capability
  运行命令: `python -m pytest tests/test_services/test_capability_service.py::test_check_capability_no_record_default_allow -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 宽松策略正确——无记录默认允许

- 状态变量/锁的异常路径：
  构造输入: 不设置 current_user_var 调用 @audited 函数
  运行命令: `python -m pytest tests/test_services/test_audit_service.py::test_audited_decorator_no_user_context -v`
  实际输出:
  ```
  PASSED (user_id=None)
  ```
  结论: F-02 修复有效——None 不违反 FK 约束

- 字符串匹配/条件判断的假阴性：
  构造输入: upsert_setting 先 create 再 update 同 key
  运行命令: `python -m pytest tests/test_services/test_audit_service.py::test_audited_upsert_setting -v`
  实际输出:
  ```
  PASSED (create action + update action 分别记录)
  ```
  结论: F-04 修复有效——运行时正确区分 create/update

### GPT Plan Review Finding 处置摘要
| ID | Category | 处置 | 实现 |
|----|----------|------|------|
| F-01 | design-concern | accepted-risk: enforcement 在 Phase 1d | N/A |
| F-02 | code-bug | verified → fixed | user_id nullable + None 默认 |
| F-03 | design-concern | accepted-risk: best-effort 审计是明确设计 | N/A |
| F-04 | code-bug | verified → fixed | 手动 write_audit_log + 运行时判定 |
| F-05 | code-bug | verified → fixed | _entity_type_lookup + select 查询 |
| F-06 | test-gap | verified → fixed | test_audit_log_captures_user_and_request_id |
| F-07 | design-concern | verified → fixed | 统一为显式补导入 |
| F-08 | suggestion | noted | Task 2-8 已有完整测试契约 |

使用 codex-review skill 进行 GPT 代码审查。
