---
topic: tech-debt-D04-baseline-refresh
tier: T1
handoff_type: executor
created: "2026-04-25 10:25:37"
blocked_by: [D01-completed, D02, D03-completed]
blocks: null
---

=== 生成块开始 ===

# D-04 全量测试验证 + 基线刷新 — 执行交接卡

**前置**: D-01 已完成 / D-02 待完成 / D-03 已闭环（测试自然 PASS）。

**执行**:
```bash
cd ~/projects/edu-cloud
.venv/bin/python -m pytest --tb=short -q 2>&1 | tee /tmp/pytest-full-$(date +%Y%m%d).log
cd frontend-nuxt && npx vitest run
```

**更新 CLAUDE.md**: 搜索旧基线数字替换为实测数字，日期改为 2026-04-25。

**更新 memory**:
- `project_edu_cloud_alembic_drift.md` → 标记已修复
- `project_grading_permission_temp.md` → 标记已收回

**已知 deferred**: `test_alembic_s1a_bank.py::test_upgrade_then_downgrade_is_clean` 是 S1-A downgrade 可逆性问题，不阻塞基线刷新——在 CLAUDE.md 标注为已知 debt。

**提交**: `git commit -m "chore: tech debt cleanup D-01~D-04 — alembic drift + permission revoke + test baseline refresh"`

**验收**: 1 failed (alembic downgrade deferred) / 0 error + CLAUDE.md 数字刷新 + memory 更新 + 干净 commit

=== 生成块结束 ===

收尾任务。如果全量跑出意外新失败，不在本任务修——记录并开新 issue。
