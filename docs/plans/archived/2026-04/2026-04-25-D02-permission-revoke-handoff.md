---
topic: tech-debt-D02-permission-revoke
tier: T2
handoff_type: executor
created: "2026-04-25 10:25:37"
blocked_by: [D01-completed]
blocks: [D04]
---

=== 生成块开始 ===

# D-02 MANAGE_GRADING 权限收回 — 执行交接卡

**目标**: 从 `_TEACHER_BASE` 移除 `MANAGE_GRADING`，subject_teacher 不再有阅卷管理权。

**改动 2 处**:
1. `src/edu_cloud/core/permissions.py:88` — `_TEACHER_BASE` 集合删除 `Permission.MANAGE_GRADING`
2. `src/edu_cloud/core/permissions.py:248` — `homeroom_teacher` 显式添加 `Permission.MANAGE_GRADING`

**前端**: `frontend/src/config/permissions.js` 的 `_TEACHER_BASE` 已正确（不含 manage_grading）；检查 homeroom_teacher 是否需要显式加。

**验证命令**:
```
.venv/bin/python -m pytest tests/test_services/test_permissions_grading.py tests/test_services/test_new_permissions.py -v
```
期望: `test_subject_teacher_no_manage_grading` PASS + `test_subject_teacher_has_view_grading` PASS

**设计文档**: `docs/plans/2026-04-25-manage-grading-revoke-design.md`

**验收**: 2 个权限测试变绿 + lesson_prep_leader/homeroom_teacher 仍有 MANAGE_GRADING + 前端 vitest 全绿

=== 生成块结束 ===

D-01 已完成(2026-04-25)。当前基线: 2170 passed / 3 failed / 23 skipped。本任务修完后预期: 2 个权限测试变绿 → 剩 1 failed (alembic downgrade, 独立 debt)。改完后更新 memory `~/.claude/projects/-home-ops/memory/project_grading_permission_temp.md` 标记已收回。
