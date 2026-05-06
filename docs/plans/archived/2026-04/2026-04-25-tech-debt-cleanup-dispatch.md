---
baseline_command: "cd ~/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q"
baseline_verified_at: "2026-04-24 22:55"
baseline_count: 2102
---

# 技术债清理派发手册 (2026-04-25)

> **本文档是项目管理器产出的任务派发手册。**
> 每个任务卡是一个独立的新会话执行单元。按顺序执行。

---

## 执行总览

| 任务 | 级别 | 预估 | 前置 | 状态 |
|------|------|------|------|------|
| D-01: Alembic 漂移修复 | T2 | 2-3h | 无 | 待执行 |
| D-02: MANAGE_GRADING 权限收回 | T2 | 1h | D-01 | 待执行 |
| D-03: Pipeline Worker 测试修复 | T1 | 1h | 无 | 待执行 |
| D-04: 全量测试验证 + 基线刷新 | T1 | 30min | D-01~D-03 | 待执行 |

**当前基线 (2026-04-24)**: 2102 passed / 23 skipped / 22 failed + 1 error
**目标基线**: X passed / Y skipped / 0 failed / 0 error

---

## D-01: Alembic 漂移修复 (P0, T2)

### 背景

dev DB (`edu_cloud.db`) 的 `alembic_version` 停在 `e241e1568792`，但 alembic HEAD 已推进到 `f311eb126798`（差 2 个 migration）。`app.py:70` 的 `create_all()` 在启动时从 ORM 建新表但**不 ALTER 已有表**，导致：

| 表 | 漂移类型 | 详情 |
|---|---|---|
| `bank_questions` | **缺 5 列** | source, explanation, knowledge_point_ids, difficulty_level, grade_id |
| `classes` | **缺 1 列** | grade_id (FK→grades.id) |
| `grades` | 表存在但 alembic 不知 | create_all 已建，结构正确 |
| `teaching_plans` | 表存在但 alembic 不知 | create_all 已建，结构正确 |

Migration DAG 本身健康（单头线性链），问题纯粹是"没跑 upgrade"。

### 已有设计文档

`docs/plans/2026-04-25-alembic-drift-spike-design.md` — 包含检测器架构设计��本任务取其中修复部分直接执行。

### 执行步骤

**Step 1: 备份 dev DB**
```bash
cd ~/projects/edu-cloud
Use the SQLite backup API or the project migration wrapper; do not copy active SQLite files with `cp`.
```
> 注：这是 dev DB（非活跃生产）��cp 可用。

**Step 2: 处理 create_all 已建的表**

grades 和 teaching_plans 已被 create_all 创建，直接 `alembic upgrade` 会撞 "table already exists"。需要先处理：

```bash
cd ~/projects/edu-cloud
# 确认这两个表存在但空（0 行，删除无数据损失）
.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('edu_cloud.db')
for t in ['grades', 'teaching_plans']:
    count = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t}: {count} rows')
"
# 如果都是 0 行，删除它们让 migration 重建
.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('edu_cloud.db')
c.execute('DROP TABLE IF EXISTS grades')
c.execute('DROP TABLE IF EXISTS teaching_plans')
c.commit()
print('Dropped grades + teaching_plans')
"
```

**Step 3: 运行 alembic upgrade**
```bash
cd ~/projects/edu-cloud
.venv/bin/python -m alembic upgrade head
```

期望输出：
- `a88094ee4ea6` (S1-A): ALTER bank_questions ADD 5 列
- `f311eb126798` (S1-C): CREATE grades + teaching_plans + ALTER classes ADD grade_id + ALTER subjects ADD 4 列

**Step 4: 验证修复**
```bash
cd ~/projects/edu-cloud
# 1. alembic current 应显示 f311eb126798
.venv/bin/python -m alembic current

# 2. bank_questions 应有 24 列
.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('edu_cloud.db')
cols = [r[1] for r in c.execute('PRAGMA table_info(bank_questions)').fetchall()]
print(f'bank_questions: {len(cols)} columns')
for needed in ['source','explanation','knowledge_point_ids','difficulty_level','grade_id']:
    assert needed in cols, f'MISSING: {needed}'
print('All S1-A columns present')
"

# 3. classes 应有 grade_id
.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('edu_cloud.db')
cols = [r[1] for r in c.execute('PRAGMA table_info(classes)').fetchall()]
assert 'grade_id' in cols, 'MISSING: classes.grade_id'
print('classes.grade_id present')
"

# 4. grades + teaching_plans 应存在
.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('edu_cloud.db')
tables = [r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
assert 'grades' in tables, 'MISSING: grades table'
assert 'teaching_plans' in tables, 'MISSING: teaching_plans table'
print('grades + teaching_plans exist')
"
```

**Step 5: 运行 alembic 相关测试**
```bash
cd ~/projects/edu-cloud
.venv/bin/python -m pytest tests/test_alembic_migration.py -v --tb=short
```

期望：之前 2 FAILED + 1 ERROR 的 alembic 测试变绿。

**Step 6: subjects 表 4 列验证**

S1-C migration 还给 subjects 表加了 4 列，验证：
```bash
.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('edu_cloud.db')
cols = [r[1] for r in c.execute('PRAGMA table_info(subjects)').fetchall()]
for needed in ['grade_level','semester','category','difficulty_level']:
    status = 'OK' if needed in cols else 'MISSING'
    print(f'subjects.{needed}: {status}')
"
```

### 验收标准

- [ ] `alembic current` 输出 `f311eb126798 (head)`
- [ ] `bank_questions` 有 24 列（含 5 个 S1-A 新列）
- [ ] `classes` 有 `grade_id` 列
- [ ] `grades` 和 `teaching_plans` 表存在且结构匹配 ORM
- [ ] `test_alembic_migration.py` 全绿（之前 2 FAILED + 1 ERROR）
- [ ] 不改应用代码（本任务��修 DB 状态）

### 风险

- S1-C migration 的 `batch_alter_table` 在 SQLite 上可能有 FK 限制：如果失败，检查 `PRAGMA foreign_keys` 设置
- 如果 subjects 表 ALTER 失��（SQLite 不支持某些 ALTER），migration 文件应已有 `batch_alter_table` 包装

---

## D-02: MANAGE_GRADING 权限收回 (P1, T2)

### 背景

`src/edu_cloud/core/permissions.py:88` 的 `_TEACHER_BASE` 集合临时包含 `Permission.MANAGE_GRADING`，导致 subject_teacher（科任教师）获得了阅卷管��权限。这是安全风险。

已有设计文档：`docs/plans/2026-04-25-manage-grading-revoke-design.md`

### 精确改动清单

**文件 1: `src/edu_cloud/core/permissions.py`**

1. **行 88**: 从 `_TEACHER_BASE` 集合中**删除** `Permission.MANAGE_GRADING`
2. **行 248**: `homeroom_teacher` 定义中**显式添加** `Permission.MANAGE_GRADING`
   - 当前: `homeroom_teacher = _TEACHER_BASE | {VIEW_CONDUCT, MANAGE_CONDUCT, ...}`
   - 改为: `homeroom_teacher = _TEACHER_BASE | {Permission.MANAGE_GRADING, VIEW_CONDUCT, MANAGE_CONDUCT, ...}`
3. **行 241-243**: `lesson_prep_leader` 已显式包含 `MANAGE_GRADING`，无需改动

**改后权限矩阵（MANAGE_GRADING）:**

| 角色 | 改前 | 改后 | 来源 |
|---|---|---|---|
| platform_admin | Y | Y | 全权 |
| district_admin | Y | Y | 显式 |
| principal | Y | Y | 显式 |
| academic_director | Y | Y | 显式 |
| lesson_prep_leader | Y | Y | 显式（已有） |
| homeroom_teacher | Y | Y | _TEACHER_BASE → 改为显式 |
| subject_teacher | Y | **N** | _TEACHER_BASE → 移除 |
| grade_leader | N | N | 无变化 |

**文件 2: `frontend/src/config/permissions.js`**

前端 `_TEACHER_BASE` 已经不含 `manage_grading`（设计正确）。需确认：
- `homeroom_teacher` 定义是否显式包含 `'manage_grading'` → 如果没有，需添加

**文件 3: `frontend/src/config/sidebarConfig.js`**

检查 conduct/grading 相关菜单项是否按 permission 而非 role 控制。如有 role 硬编码，改为 permission 判断。

### 执行步骤

1. **修改后端** `permissions.py`（2 处改动）
2. **检查+修改前端** `permissions.js` 和 `sidebarConfig.js`
3. **运行权限测试**：
   ```bash
   .venv/bin/python -m pytest tests/test_services/test_permissions_grading.py tests/test_services/test_new_permissions.py -v
   ```
4. **运行前端测试**：
   ```bash
   cd frontend && npx vitest run
   ```

### 验收标准

- [ ] `test_subject_teacher_no_manage_grading` PASS（之前 FAIL）
- [ ] `test_subject_teacher_has_view_grading` PASS（之前 FAIL）
- [ ] `lesson_prep_leader` 仍有 MANAGE_GRADING
- [ ] `homeroom_teacher` 仍有 MANAGE_GRADING（通过显式声明）
- [ ] 前端 vitest 全绿
- [ ] 更新 memory `project_grading_permission_temp.md` 为已完成

---

## D-03: Pipeline Worker 测试修复 (P1, T1)

### 背景

`tests/test_workers/test_grading_worker.py::test_run_post_exam_pipeline_stub` 失败，原因是 S1-A 重构后 pipeline handler 签名或 task 注册发生变化，测试 stub 未同步。

### 执行步骤

1. **定位根因**：
   ```bash
   cd ~/projects/edu-cloud
   .venv/bin/python -m pytest tests/test_workers/test_grading_worker.py::test_run_post_exam_pipeline_stub -v --tb=long
   ```
   读完整的 traceback，判断是：
   - a) Import 路径变更（同 card router 类型）
   - b) 函数签名变更（参数增减）
   - c) Mock 对象路径不匹配

2. **对比 stub vs 实际**：
   - 读测试文件中的 mock 对象路径
   - 读 `src/edu_cloud/workers/grading.py` 中 `run_post_exam_pipeline` 实际签名
   - 读 `src/edu_cloud/worker.py` 中的 task 注册

3. **修复 stub**（对齐签名/路径）

4. **验证**：
   ```bash
   .venv/bin/python -m pytest tests/test_workers/ -v --tb=short
   ```

### 验收标准

- [ ] `test_run_post_exam_pipeline_stub` PASS
- [ ] 其他 worker 测试不受影响

---

## D-04: 全量测试验证 + 基线刷新 (P1, T1)

### 前置

D-01 + D-02 + D-03 全部完成。

### 执行步骤

1. **后端全量测试**：
   ```bash
   cd ~/projects/edu-cloud
   .venv/bin/python -m pytest --tb=short -q 2>&1 | tee /tmp/pytest-full-$(date +%Y%m%d).log
   ```
   记录精确数字：`X passed / Y skipped / 0 failed`

2. **前端测试**：
   ```bash
   cd ~/projects/edu-cloud/frontend-nuxt && npx vitest run
   cd ~/projects/edu-cloud/frontend && npx vitest run 2>/dev/null || true
   ```

3. **更新 CLAUDE.md 基线**：
   - 搜索旧测试数字替换为实际数字
   - 搜索 `22 failed` 相关描述，改为 `0 failed`
   - 更新测试命令注释中的日期为 `2026-04-25`

4. **更新 memory**：
   - 更新 `project_edu_cloud_alembic_drift.md` 标记漂移已修复
   - 更新 `project_grading_permission_temp.md` 标记权限已收回

5. **提交**：
   ```bash
   git add -p  # 逐块审查
   git commit -m "chore: tech debt cleanup — alembic drift fix + permission revoke + test baseline refresh"
   ```

### 验收标准

- [ ] pytest: 0 failed, 0 error
- [ ] vitest (frontend-nuxt): 全绿
- [ ] CLAUDE.md 基线数字已刷新
- [ ] memory 文件已更新
- [ ] 一个干净的 commit
