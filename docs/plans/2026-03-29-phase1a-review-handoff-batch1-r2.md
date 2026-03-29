[edu-cloud] Executor→Reviewer | 2026-03-29 20:48:28
## 审查交接单 R2: F-01~F-05 修复
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1a-module-management-plan.md
R1 报告: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1a-review-report-batch1.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| F-01 | scope guard: school-scoped 角色强制校验 school_id | `_check_school_scope()` 在 5 个端点调用，platform_admin/district_admin 放行 | ✅ | |
| F-02 | 修复路由映射 `/api/v1/cards` → `/api/v1/card` | module_middleware.py ROUTE_MODULE_MAP 单行修改 | ✅ | |
| F-03 | 页面刷新时恢复 enabledModules | AppShell.vue onMounted 检测 token+school_id+!modulesLoaded → loadModules() | ✅ | |
| F-04 | 弱断言 `!= 403` → 具体状态码 | 3 处改为 `== 200` | ✅ | |
| F-05 | 补 SchoolSetting 唯一约束测试 | test_school_setting_unique_constraint PASSED | ✅ | |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 |
|---------------|------------------|---------|---------|
| 跨校越权阻塞 | test_school_settings.py::test_principal_cannot_access_other_school_settings | `pytest tests/test_api/test_school_settings.py::test_principal_cannot_access_other_school_settings -v` | PASSED |
| 中间件放行断言 | test_school_settings.py::test_middleware_allows_enabled_module | `pytest tests/test_api/test_school_settings.py::test_middleware_allows_enabled_module -v` | PASSED (assert == 200) |
| Platform admin 跳过检查 | test_school_settings.py::test_middleware_no_school_id_skips_check | `pytest tests/test_api/test_school_settings.py::test_middleware_no_school_id_skips_check -v` | PASSED (assert == 200) |
| 多校隔离中间件 | test_school_settings.py::test_middleware_multi_school_isolation | `pytest tests/test_api/test_school_settings.py::test_middleware_multi_school_isolation -v` | PASSED (assert == 200) |
| SchoolSetting 唯一约束 | test_school_settings_service.py::test_school_setting_unique_constraint | `pytest tests/test_services/test_school_settings_service.py::test_school_setting_unique_constraint -v` | PASSED |

### 验证清单自检
- ✅ F-01: `_check_school_scope` 在全部 5 个端点（list_settings/update_setting/list_modules/list_enabled_modules/toggle_module）调用
- ✅ F-01: platform_admin 和 district_admin 在 `_CROSS_SCHOOL_ROLES` 中，跳过 scope 检查
- ✅ F-01: PermissionDeniedError 经 app.py exception_handler 返回 403
- ✅ F-01: 负向测试覆盖 GET settings + PATCH settings + GET modules（跨校均 403）
- ✅ F-02: `"/api/v1/card": "exam"` 与 `card/router.py` prefix `/api/v1/card` 一致
- ✅ F-03: AppShell onMounted 条件：token 存在 + currentRole.school_id 存在 + modulesLoaded 为 false
- ✅ F-04: 3 处断言从 `!= 403` 改为 `== 200`（lines 255, 292, 353）
- ✅ F-05: SchoolSetting duplicate key → IntegrityError 测试 PASSED
- ✅ 路由计数测试从 14 → 15（school-settings 路由）
- ✅ 全量后端 810 passed / 前端 68 passed，0 regression

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: principal 用户访问其他学校的 settings/modules/toggle 端点
  运行命令: `pytest tests/test_api/test_school_settings.py::test_principal_cannot_access_other_school_settings -v`
  实际输出:
  ```
  PASSED - resp_own 200, resp_other 403, resp_write 403, resp_modules 403
  ```
  结论: scope guard 正确拦截跨校访问，本校访问正常

- 状态变量/锁的异常路径：
  构造输入: platform_admin（无 school_id）访问任意学校的 settings
  运行命令: `pytest tests/test_api/test_school_settings.py::test_get_settings -v`
  实际输出:
  ```
  PASSED - admin_headers 使用 platform_admin，_CROSS_SCHOOL_ROLES 放行
  ```
  结论: 跨校角色正确绕过 scope guard

- 字符串匹配/条件判断的假阴性：
  构造输入: 禁用 exam 模块后请求 /api/v1/calendar/events（不同模块，不应被拦截）
  运行命令: `pytest tests/test_api/test_school_settings.py::test_middleware_allows_enabled_module -v`
  实际输出:
  ```
  PASSED - assert 200 == 200
  ```
  结论: 启用模块路由正确放行，返回明确 200

### 全量测试
- 后端: 810 passed, 0 failed (378.56s)
- 前端: 68 passed (4.97s, 6 test files)

使用 codex-review skill 进行 GPT 代码审查 R2。
