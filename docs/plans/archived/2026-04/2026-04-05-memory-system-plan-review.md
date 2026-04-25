[edu-cloud] GPT Reviewer | 2026-04-05 16:28:17
<!-- anchor: finding-classification -->
## 审查报告: Plan Review — Phase 2 跨会话记忆系统

结论: FAIL

### Findings

| ID | Severity | Category | Type | Status |
|----|----------|----------|------|--------|
| F001 | HIGH | code-bug | defect_fix | verified |
| F002 | HIGH | code-bug | defect_fix | verified |
| F003 | HIGH | code-bug | defect_fix | verified |
| F004 | HIGH | code-bug | defect_fix | verified |
| F005 | HIGH | test-gap | defect_fix | verified |
| F006 | MED | test-gap | defect_fix | verified |
| F007 | MED | design-concern | defect_fix | verified |

### F001 (HIGH, code-bug) — ProjectState 缺乏租户隔离

- **Before**: get_project/update_project_status 只用 project_id，无 owner_id+school_id 约束
- **After**: 所有 ProjectState 读写必须受 owner_id + school_id 约束
- **Evidence**: design §3 line 268 要求 owner_id+school_id 隔离；plan lines 264, 400, 602-619 只传 project_id
- **处置**: 修复 plan — get_project/update_project_status/update_project_state 增加 owner_id+school_id 参数

### F002 (HIGH, code-bug) — EntityMemory 未接入 DataScope

- **Before**: get_entities 只按 school_id 过滤
- **After**: 必须遵守 DataScope（class_ids, student_ids 级别过滤）
- **Evidence**: design §3 line 267; tool_context.py:24 已有 data_scope; scoped_query.py:39-62 有 class/student 过滤
- **处置**: 修复 plan — MemoryStore.get_entities 接受 DataScope 参数，memory_read/injector 传入 scope

### F003 (HIGH, code-bug) — memory 工具缺少 capability 声明

- **Before**: 只用 allowed_roles，角色列表缺 subject_teacher
- **After**: 声明 requires_capabilities，使用正确角色名
- **Evidence**: registry.py:23 支持 requires_capabilities; tool_access.py:27 执行过滤; permissions.py:154 定义 subject_teacher
- **处置**: 修复 plan — 添加 requires_capabilities，更正角色列表

### F004 (HIGH, code-bug) — 新模型未加入 metadata 装配路径

- **Before**: Task 1 未包含 conftest.py/app.py/test_alembic_migration.py 的模型导入
- **After**: 新模型必须显式导入到所有 metadata 装配路径
- **处置**: 修复 plan — Task 1 增加 Step 补充模型导入

### F005 (HIGH, test-gap) — 缺少 Contract Pack

- **Before**: 计划无 contract_pack 段落
- **After**: 补充完整 Contract Pack（invariants/counter_examples/risk_modules/test_debt）
- **处置**: 修复 plan — 添加 Contract Pack 段落

### F006 (MED, test-gap) — Task 3-6 缺边界条件段

- **Before**: 只有 Task 2 有边界条件段
- **After**: 所有行为变更 Task 都应有边界条件段
- **处置**: 修复 plan — 补充 Task 3-6 边界条件

### F007 (MED, design-concern) — 工具文件路径不一致

- **Before**: design 写 system_tools.py，plan 写 memory_tools.py
- **After**: 统一为 memory_tools.py（plan 正确，design 概括性描述可接受）
- **处置**: plan 路径 memory_tools.py 正确（独立文件职责更清晰），design 中 system_tools.py 为概括性描述

### 原始输出保护

- Raw log: `docs/plans/.codex-plan-review-raw.log`
- SHA256: `a64af9d1a1cd6a098438ee91928c8694f44d6f2a2129aa4532a1060ce07efa23`
