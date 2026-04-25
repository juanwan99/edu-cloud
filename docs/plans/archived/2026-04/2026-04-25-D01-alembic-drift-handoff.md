---
topic: tech-debt-D01-alembic-drift
tier: T2
handoff_type: executor
created: "2026-04-25 10:25:37"
blocked_by: null
blocks: [D02, D04]
---

=== 生成块开始 ===

# D-01 Alembic 漂移修复 — 执行交接卡

**目标**: dev DB `edu_cloud.db` 的 alembic_version 从 `e241e1568792` 升到 `f311eb126798`（HEAD），修复 6 列 schema 缺失。

**根因**: `app.py:70` create_all() 建新表但不 ALTER 已有表；2 个 migration 未跑。

**精确漂移清单**:
- `bank_questions` 缺 5 列: source / explanation / knowledge_point_ids / difficulty_level / grade_id
- `classes` 缺 1 列: grade_id
- `grades` + `teaching_plans` 表存在（create_all 建的）但 alembic 不知道 → 需先 DROP 再让 migration 重建

**执行序列**:
1. `cp edu_cloud.db edu_cloud.db.bak-pre-drift-fix-$(date +%Y%m%d)`
2. 确认 grades/teaching_plans 0 行后 DROP TABLE
3. `.venv/bin/python -m alembic upgrade head`
4. 验证: alembic current = `f311eb126798` / bank_questions 24 列 / classes 有 grade_id / grades+teaching_plans 存在
5. `.venv/bin/python -m pytest tests/test_alembic_migration.py -v` → 期望 3 绿（之前 2F+1E）

**完整步骤**: 见 `docs/plans/2026-04-25-tech-debt-cleanup-dispatch.md` §D-01

**验收**: alembic current = HEAD + 6 列补齐 + alembic 测试全绿 + 不改应用代码

**design 文档**: `docs/plans/2026-04-25-alembic-drift-spike-design.md`

=== 生成块结束 ===

SQLite batch_alter_table 如果撞 FK 问题，先 `PRAGMA foreign_keys=OFF` 再跑。subjects 表也有 4 列要验证（grade_level/semester/category/difficulty_level）。
