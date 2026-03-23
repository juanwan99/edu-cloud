---
type: review-handoff
batch: 1
plan: docs/plans/2026-03-22-platform-merge-plan.md
first_commit: a958bcb
last_commit: 8471ffa
test_baseline: 267 → 271 (4 new LLMSlot tests)
---

# Batch 1 Code Review Handoff — Foundation

## Scope

5 commits implementing Batch 1 (Task 1-5) of the exam-ai → edu-cloud merge plan.

## Changes Summary

### Task 1: 模块目录结构
- 创建 `modules/` 下 15 个模块目录 + `core/models/` + `workers/` + `data/` 的 `__init__.py`

### Task 2: School 模型重命名 + FK 级联
- `RegisteredSchool` → `School`, tablename `registered_schools` → `schools`
- 删除 `last_heartbeat`, `client_version`, `exam_ai_port` 字段
- `api_key_hash` 保留为 Optional（**偏差**：计划说删除，但 sync 认证深度依赖）
- 全局 FK 替换 `registered_schools.id` → `schools.id`（8 model files）
- 全局 import 替换（services/api/tests/scripts/alembic）
- heartbeat 端点简化（不再写入已删除字段）
- schools API 响应移除已删除字段

### Task 3: PlatformUser 删除 + Auth 改造
- 删除 `models/platform_user.py`
- `auth.py` / `deps.py` 移除 PlatformUser fallback 分支
- `joint_exam.created_by` FK: `platform_users.id` → `users.id`
- `test_joint_exam_service.py` fixture 改用 User+UserRole

### Task 4: Config 合并
- 新增: `STORAGE_ROOT`, `MAX_UPLOAD_SIZE_MB`, `LLM_VISION_MODEL`
- 新增: `AI_MAX_STEPS`, `AI_SESSION_TTL`, `AI_RATE_LIMIT_*`, `AI_MAX_CALLS_PER_SESSION`
- `LLM_MAX_STEPS` 重命名为 `AI_MAX_STEPS`, agent.py 引用同步更新

### Task 5: LLMSlot 模型 + slot_selector
- `core/models/llm_slot.py`: 新模型，`school_id` FK → `schools.id`
- `modules/exam/slot_selector.py`: 三级 fallback (学校覆盖 > 平台默认 > .env)
- 4 个测试覆盖优先级链、disabled skip、env fallback

## Deviation from Plan

- **api_key_hash 保留**: 计划要求删除 api_key_hash，但 sync.py 的 API Key 认证 (`bcrypt.checkpw`) 和 ~20 个测试（含 sync_setup fixture 通过 create_school API 获取 api_key）深度依赖此字段。删除需要重写 sync 认证机制和大量测试，属于 Batch 3 的 scope。保留为 Optional[str] with default None。

## Test Evidence

```
Before: 267 passed
After:  271 passed (4 new LLMSlot tests)
```

## Files Modified (key files)

- `src/edu_cloud/models/school.py` — School rename
- `src/edu_cloud/models/joint_exam.py` — FK updates (2 FKs)
- `src/edu_cloud/models/*.py` — FK updates (student/class_group/exam/document/calendar/notification/user_role)
- `src/edu_cloud/api/auth.py` — PlatformUser fallback removed
- `src/edu_cloud/api/deps.py` — PlatformUser fallback removed
- `src/edu_cloud/api/sync.py` — School rename + heartbeat simplified
- `src/edu_cloud/api/schools.py` — removed deleted fields from response
- `src/edu_cloud/api/app.py` — PlatformUser import removed, LLMSlot added
- `src/edu_cloud/services/school_service.py` — School rename
- `src/edu_cloud/config.py` — exam-ai config merged
- `src/edu_cloud/ai/agent.py` — LLM_MAX_STEPS → AI_MAX_STEPS
- `src/edu_cloud/core/models/llm_slot.py` — NEW
- `src/edu_cloud/modules/exam/slot_selector.py` — NEW
- `tests/conftest.py` — School rename, PlatformUser removed, LLMSlot registered
- `tests/test_models/test_llm_slot.py` — NEW (4 tests)
- `tests/test_services/test_joint_exam_service.py` — User+UserRole fixture
- `tests/test_api/test_studio_api.py` — School rename
- `tests/test_api/test_workspace.py` — School rename
