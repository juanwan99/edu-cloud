---
type: review-handoff
batch: 3
plan: docs/plans/2026-03-22-platform-merge-plan.md
first_commit: 723505c
last_commit: 723505c
test_baseline: 300
---

# Batch 3 审查交接单 — API Routes & App Factory

## 变更范围

### Task 12: 迁入 exam-ai 路由 — Exam/Student/Card/Scan
- `modules/exam/router.py` — exam.py + question.py 合并，11 端点 (185 LOC)
- `modules/student/router.py` — student.py 迁入，3 端点 (70 LOC)
- `modules/card/router.py` — cards.py 迁入，19 端点 (~1140 LOC, bash copy + sed 修复)
- `modules/card/template_router.py` — template.py 迁入，3 端点 (110 LOC)
- `modules/scan/router.py` — scan.py 迁入，6 端点 (~422 LOC, bash copy + sed 修复)
- `api/permissions.py` — 数据权限过滤 (get_visible_class_ids/get_visible_subject_codes)

### Task 13: 迁入 exam-ai 路由 — Grading/Marking/Analytics/Knowledge/Pipeline/LLMConfig
- `modules/grading/router.py` — grading.py 迁入，9 端点 (~344 LOC, bash copy + sed)
- `modules/marking/router.py` — marking.py 迁入，11 端点 (~368 LOC, bash copy + sed)
- `modules/analytics/router.py` — analytics.py 迁入，4 端点 (80 LOC)
- `modules/knowledge/router.py` — knowledge.py 迁入，6 端点 (95 LOC)
- `modules/pipeline/router.py` — pipeline.py 迁入，1 端点 (30 LOC, seed-demo/import-excel 不迁)
- `modules/exam/llm_config_router.py` — llm_config.py 迁入，3 端点 (130 LOC)

### Task 14: 重组已有路由到模块 + 删除 sync
- 移动到 modules/: joint_exams.py→joint_exam_router.py, results.py→results_router.py, schools.py→router.py, studio.py→router.py, calendar.py→router.py, workspace.py→workspace_router.py
- 旧位置 api/*.py 改为 re-export stub
- 删除 `api/sync.py` + `tests/test_api/test_sync_v2.py`
- 修复 sync 依赖测试：joint_exams/results 改用直接 DB 插入

### Task 15: App factory 改造
- app.py lifespan 清理：module models 为 canonical, legacy stubs 仅保留 document/approval/calendar/notification
- 统一路由挂载：auth + ai 留在 api/, 其余 18 路由从 modules/ 导入
- 118 路由注册

## Auth 适配模式

exam-ai: `current_user: User = Depends(get_current_user)` → `current_user.school_id`
edu-cloud: `current: dict = Depends(get_current_user)` → `current["current_role"].school_id`

大文件 (card/scan/grading/marking) 用 bash copy + sed 批量替换，小文件手写。
`api/permissions.py` 中 visibility helpers 适配 UserRole 多角色模型。

## 测试状态

- **总量**: 300 tests, all PASS
- **新增**: 6 API tests (`tests/test_modules/test_exam/test_api.py`)
  - 成功路径 (create/list/get)
  - 跨 school 隔离 (teacher vs admin 不同 school_id)
  - 401 无认证
  - 题目 CRUD 完整流程
- **删除**: 8 sync tests (sync 端点已废弃)
- **修复**: 4 tests (joint_exams distribute + results + paper mock target)

## 风险点

1. **大文件 sed 替换**: card/scan/grading/marking 路由是 bash copy + sed 批量替换 import，可能遗漏边界情况
2. **pipeline 路由精简**: exam-ai 有 3 端点 (run/seed-demo/import-excel)，edu-cloud 只迁入 run (seed-demo 和 import-excel 是 exam-ai 本地数据工具)
3. **knowledge service 无 school_id**: edu-cloud 的 knowledge_service 不接受 school_id 参数（知识点是全局的，school_id 默认 "__GLOBAL__"），路由中去掉了 school_id 传参
