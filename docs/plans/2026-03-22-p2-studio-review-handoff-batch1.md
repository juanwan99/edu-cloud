[edu-cloud] Executor→Reviewer | 2026-03-22 13:18:32
## 审查交接单: P2 Studio Task 1-6
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p2-studio-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | Document + DocumentVersion + ApprovalFlow + ApprovalStep 模型 | commit f8e712c, 4 个模型 + 5 个测试 | 🔀 | 使用 Mapped + mapped_column (SQLAlchemy 2.0 风格) 替代计划中的 Column 风格；Document 添加 __init__ 设置 Python 级默认值 |
| T2 | 模板系统 + StudioService (CRUD + 状态机 + 版本管理) | commit dee68d3, 模板 + StudioService + 7 个测试 | ✅ | |
| T3 | 审批服务 — 固化审批链 + 逐步推进 + 权限校验 | commit 46726a4, ApprovalService + 6 个测试 | 🔀 | 增加了终态检查 flow.status in ("approved", "rejected") 作为 act_on_step 前置守卫，比计划的 current_step 越界检查更严格 |
| T4 | L4 执行动作工具 — generate_report + generate_comment | commit 8b92f8f, 2 个 L4 工具 + 角色映射 + 权限 + 4 个测试 | 🔀 | 自纠 3 处：get_class_stats 需双参数；_build_section_content 字段名对齐实际 analytics 返回格式 |
| T5 | Studio REST API — 模板/文档 CRUD/状态转换/权限 | commit e887295, 6 个端点 + 7 个测试 | ✅ | |
| T6 | Studio 前端 — 模板卡片 + 文档列表 + 预览编辑 | commit c8ac864, 4 个前端文件 | ✅ | |

> 状态: ✅一致 / ❌不一致 / 🔀改进（实现优于计划）

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） |
|---------------|------------------|---------|------------------------------|
| T1 模型字段+默认值 | test_models/test_document.py::test_document_fields + test_document_status_default | `python -m pytest tests/test_models/test_document.py -v` | 5 passed |
| T2 状态机合法性 | test_services/test_studio.py::test_invalid_status_transition | `python -m pytest tests/test_services/test_studio.py -v` | 7 passed |
| T2 版本管理 | test_services/test_studio.py::test_update_document_creates_version | 同上 | version == 2 ✅ |
| T3 审批权限隔离 | test_services/test_approval.py::test_wrong_approver_denied | `python -m pytest tests/test_services/test_approval.py -v` | 6 passed |
| T3 已完成流不可操作 | test_services/test_approval.py::test_already_completed_flow_cannot_act | 同上 | StateError raised ✅ |
| T4 L4 工具创建文档 | test_ai/test_tools_actions.py::test_generate_report | `python -m pytest tests/test_ai/test_tools_actions.py -v` | 4 passed |
| T4 未知模板返回 error | test_ai/test_tools_actions.py::test_generate_report_unknown_template | 同上 | "error" in result ✅ |
| T4 缺少上下文返回 error | test_ai/test_tools_actions.py::test_generate_report_missing_context | 同上 | "缺少必需上下文" ✅ |
| T5 文档 CRUD 链路 | test_api/test_studio_api.py::test_create_and_get_document | `python -m pytest tests/test_api/test_studio_api.py -v` | 7 passed |
| T5 跨校隔离 | test_api/test_studio_api.py::test_cross_school_access_denied | 同上 | 403 ✅ |
| T5 认证检查 | test_api/test_studio_api.py::test_studio_requires_auth | 同上 | 401/403 ✅ |

### 验证清单自检
- ✅ Document 状态默认 draft, version 默认 1 (test_document_status_default)
- ✅ 4 个模板定义完整（班级报告/学科分析/学生评语/家长通知）(test_templates_have_required_keys)
- ✅ 模板按角色过滤 (test_get_templates_for_homeroom_teacher, test_get_templates_for_parent)
- ✅ 状态转换有合法性验证 (test_invalid_status_transition: draft→approved = StateError)
- ✅ 编辑时自动创建 DocumentVersion (test_update_document_creates_version)
- ✅ 3 种审批链定义 (test_approval_chains_defined)
- ✅ 非审批人被拒 (test_wrong_approver_denied: PermissionDeniedError)
- ✅ 已完成审批流不可重复操作 (test_already_completed_flow_cannot_act)
- ✅ generate_report 按模板创建 Document (test_generate_report: doc.type == "report")
- ✅ generate_comment 关联学生数据 (test_generate_comment: type == "comment")
- ✅ 未知模板返回 error (test_generate_report_unknown_template)
- ✅ ROLE_TOOL_CATEGORIES 已添加 L4_action
- ✅ subject_teacher 已添加 GENERATE_REPORT 权限
- ✅ GET /templates 按角色过滤
- ✅ POST /documents 创建文档 (201)
- ✅ PATCH /documents/{id} 编辑+版本递增
- ✅ POST /documents/{id}/transition 状态转换
- ✅ 所有端点需要认证 (test_studio_requires_auth)
- ✅ 跨 school_id 访问文档被拒 (test_cross_school_access_denied: 403)

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: draft→approved 跳转（非法状态转换）
  运行命令: `python -m pytest tests/test_services/test_studio.py::test_invalid_status_transition -v`
  实际输出:
  ```
  PASSED
  ```
  结论: StateError 正确抛出，状态机防护有效

- 状态变量/锁的异常路径：
  构造输入: 已 approved 的审批流再次 approve
  运行命令: `python -m pytest tests/test_services/test_approval.py::test_already_completed_flow_cannot_act -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 终态检查有效，flow.status in ("approved","rejected") 前置守卫阻止重复操作

- 字符串匹配/条件判断的假阴性：
  构造输入: 跨校 school_id 不匹配的文档访问
  运行命令: `python -m pytest tests/test_api/test_studio_api.py::test_cross_school_access_denied -v`
  实际输出:
  ```
  PASSED
  ```
  结论: school_id 隔离生效，PermissionDeniedError → 403

### 统计
- 测试: 138 → 167 (+29 tests)
- Commits: f8e712c..c8ac864 (6 commits)
- 新增文件: 15 个 (后端 10 + 前端 4 + templates __init__)
- 修改文件: 7 个
- 总变更: +1398 行 / -8 行

使用 codex-review skill 进行 GPT 代码审查。
