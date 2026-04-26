[edu-cloud] Executor→Reviewer | 2026-03-29 20:11:43
## 审查交接单: Task 1-7
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1a-module-management-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | SchoolSetting + SchoolModule models + conftest import | commit bbe6cc0, 两个 ORM 模型 + conftest 导入 + 3 tests | ✅ | |
| T2 | Settings + Modules service with CRUD | commit 07381b8, service 7 函数 + 6 service tests | ✅ | |
| T3 | Settings + Modules API + permission + tests | commit 6d2f22c, settings_router + MANAGE_SCHOOL_SETTINGS 权限 + 前端 permissions.js 同步 + 12 API tests | ✅ | |
| T4 | Module check middleware + tests | commit 3d582ce, ModuleCheckMiddleware + conftest monkey-patch async_session + 6 middleware tests | 🔀 | conftest 需 monkey-patch async_session 使中间件在测试中命中 test DB（计划未提及） |
| T5 | Alembic migration + env.py + test imports | commit 1943e3a, autogenerate 迁移 + env.py/test 导入 | ✅ | |
| T6 | Frontend sidebar module filtering + Vitest tests | commit 25f43da, API client + auth store (enabledModules/modulesLoaded/loadModules) + sidebar computed filter + sidebarConfig moduleCode + 3 Vitest tests | ✅ | |
| T7 | SchoolSettingsPage.vue + route | commit 0506301, 管理页面 + router 注册 | ✅ | |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） |
|---------------|------------------|---------|------------------------------|
| Model 唯一约束 | test_school_settings_service.py::test_school_module_unique_constraint | `pytest tests/test_services/test_school_settings_service.py::test_school_module_unique_constraint -v` | PASSED |
| Upsert 幂等性 | test_school_settings_service.py::test_upsert_setting_update | `pytest tests/test_services/test_school_settings_service.py::test_upsert_setting_update -v` | PASSED |
| 无效 module_code 拒绝 | test_school_settings_service.py::test_set_module_invalid_code | `pytest tests/test_services/test_school_settings_service.py::test_set_module_invalid_code -v` | PASSED |
| Multi-school isolation (API) | test_school_settings.py::test_modules_multi_school_isolation | `pytest tests/test_api/test_school_settings.py::test_modules_multi_school_isolation -v` | PASSED |
| Middleware blocks disabled | test_school_settings.py::test_middleware_blocks_disabled_module | `pytest tests/test_api/test_school_settings.py::test_middleware_blocks_disabled_module -v` | PASSED |
| Platform admin skips check | test_school_settings.py::test_middleware_no_school_id_skips_check | `pytest tests/test_api/test_school_settings.py::test_middleware_no_school_id_skips_check -v` | PASSED |
| Middleware multi-school isolation | test_school_settings.py::test_middleware_multi_school_isolation | `pytest tests/test_api/test_school_settings.py::test_middleware_multi_school_isolation -v` | PASSED |
| Sidebar module filtering (Vitest) | AppSidebar.test.js | `cd frontend && npx vitest run src/__tests__/AppSidebar.test.js` | 3 tests passed |
| Missing required field rejected | test_school_settings.py::test_upsert_setting_missing_key | `pytest tests/test_api/test_school_settings.py::test_upsert_setting_missing_key -v` | PASSED |

### 验证清单自检
- ✅ UniqueConstraint 防止同 school 同 key/module_code 重复（test_school_module_unique_constraint）
- ✅ MODULE_CODES 常量集中定义在 school_settings.py
- ✅ require_permission(Permission.MANAGE_SCHOOL_SETTINGS) 保护所有端点
- ✅ principal / academic_director 角色权限测试通过（test_principal/test_academic_director）
- ✅ Pydantic BaseModel 验证 request body（缺 key/enabled 返回 422）
- ✅ Middleware 使用 decode_token（非 decode_access_token）、async_session（非 async_session_factory）
- ✅ JWT 不含 school_id，中间件从 active_role_id→UserRole 查询 school_id
- ✅ 无 active_role_id / 无 school_id → 跳过检查（graceful degradation）
- ✅ marking 路由映射到 grading 模块
- ✅ Exempt paths 包含 /auth /health /schools /students /classes /dashboard /ai 等
- ✅ Disabled module 返回 403 + 中文消息
- ✅ Auth store 使用 setup store pattern: ref + computed + async function
- ✅ modulesLoaded 区分"未加载"和"加载但空"
- ✅ sidebar 无 moduleCode 的项始终显示
- ✅ Alembic migration smoke test 通过（upgrade/downgrade/表集合比对/单 head）
- ✅ CLAUDE.md 已同步更新（API 端点 + 数据模型 + 项目结构）

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: PATCH /modules/nonexistent enabled=true（无效 module_code）
  运行命令: `pytest tests/test_api/test_school_settings.py::test_toggle_invalid_module -v`
  实际输出:
  ```
  PASSED - assert 400 == 400
  ```
  结论: 无效 module_code 正确返回 400

- 状态变量/锁的异常路径：
  构造输入: platform_admin（无 school_id）请求 /calendar/events（模块路由）
  运行命令: `pytest tests/test_api/test_school_settings.py::test_middleware_no_school_id_skips_check -v`
  实际输出:
  ```
  PASSED - assert 200 != 403
  ```
  结论: 无 school scope 的角色正确跳过模块检查

- 字符串匹配/条件判断的假阴性：
  构造输入: School A disable calendar, School B 独立操作
  运行命令: `pytest tests/test_api/test_school_settings.py::test_middleware_multi_school_isolation -v`
  实际输出:
  ```
  PASSED - School A 403, School B != 403
  ```
  结论: 多学校隔离正确，无全局状态污染

### 全量测试
- 后端: 808 passed, 0 failed (419.31s)
- 前端: 68 passed (5.38s, 6 test files)
- Alembic migration: 3 passed (4.41s)

使用 codex-review skill 进行 GPT 代码审查。
