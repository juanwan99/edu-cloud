[edu-cloud] GPT Reviewer | 2026-03-29 23:49:05
## 审查报告: Task 1-7 (Round 2)
结论: FAIL → 修复后待 Round 3 确认

Raw output hash: `006b87efe937d49d763fc6d7ed23fa99e1c0d362cb4c96bd7b7f467375eb8628`

### 第一段：测试充分性（Test Adequacy）

GPT 确认边界条件（空集合/重复/跨校）均有对应测试覆盖。发现 F02 — `subject_codes` 元素非空校验缺失，属测试+实现双缺。

### 变更理解

Phase 1b 新增 2 张表（teacher_assignments / subject_selections），各自有独立的 Service + Router + 前端管理页。Router 挂在 `/api/v1/schools/{school_id}/` 路径下，复用 Phase 1a 的 MANAGE_SCHOOL_SETTINGS 权限和 _check_school_scope 跨校防护模式。Plan Review 的 6 个 finding（P1-P6）均已在实现中修复。

### 对抗性审查

GPT 主动构造了两个对抗性验证脚本：
1. `create_assignments` 传入重复 class_ids — 验证幂等（通过，created=1）
2. `create_assignments` 传入不存在的 user_id — 发现 created=1（无 user 归属校验），但 user 是平台级实体无 school_id，此路径由 router 层权限控制，非 service 职责。

### 发现清单

| ID | Severity | Category | Status | Evidence | Impact | Suggested action |
|----|----------|----------|--------|----------|--------|-----------------|
| F01 | MED | code-bug | verified → resolved-correct | subject_selection_service.py:52 update 路径无 IntegrityError 处理 | PATCH 重名返回 500 | 预检 name conflict |
| F02 | MED | code-bug | verified → resolved-correct | subject_selection_service.py:9 不校验元素非空 | ["physics",""] 可入库 | strip + 非空校验 |

### F01 修复详情
- `update_selection()` 新增 `_check_name_conflict()` 预检（排除自身 ID）
- 补 service 测试 `test_update_selection_duplicate_name` + API 测试 `test_update_selection_duplicate_name_409`

### F02 修复详情
- `_validate_selection()` 新增 strip + 非空校验
- 补 service 测试 `test_create_selection_empty_string_subject` + API 测试 `test_create_selection_empty_string_subject_422`

### 验证
```
23 passed (subject_selection service + API tests)
```

PASS/FAIL 判定：F01 + F02 均 MED code-bug，已修复并补测试 → 待 Round 3 确认 PASS。
