---
baseline_command: "cd ~/projects/edu-cloud && .venv/bin/python -m pytest --tb=no -q"
baseline_verified_at: "2026-04-26T22:38:00+08:00"
baseline_count: "2199 passed / 23 skipped / 21 failed (既有债)"
---

# Sprint 1 修正版：基线加固 + Dashboard 实现 + Sprint 2 调研

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 Alembic 多 head 基线隐患 + 实现 Dashboard 3 个 null 字段 + 补前端测试 + 提前完成 Sprint 2 调研

**Architecture:** 增量修改。Alembic migration 链修复 + dashboard.py 3 个查询 + vitest 补全。

**Tech Stack:** FastAPI / SQLAlchemy / Alembic / Vue 3 / Vitest / ECharts

**Design:** `docs/plans/2026-04-26-systematic-dev-plan-design.md`

**调研依据：** Sprint 1 调研发现 ErrorBookPage(316行)/QuestionBankPage(345行)/DashboardPage(596行) 三页面已存在，原 25h "新建页面"计划缩减为 8h "加固+增强"。

---

## 调研发现摘要（Sprint 1 调研阶段产出）

### 资产盘点

| 模块 | 后端 | 前端页面 | API client | 路由 | 测试 |
|------|------|---------|-----------|------|------|
| bank/error-book | 8 端点 (router.py 187行) | ErrorBookPage 316行 | bank.js 26行/8方法 | /error-book 已注册 | 40 passed / 6 failed (migration) |
| bank/questions | 同上 | QuestionBankPage 345行 | 同上 | /question-bank 已注册 | 同上 |
| dashboard | 1 端点 (dashboard.py 56行) | DashboardPage 596行 | 内联 client.get | / (默认页) | 4 pytest + 19 vitest |

### 待解决问题

1. Alembic 多 head：6 个 migration 测试失败，阻塞后续 S1-B/C/D migration
2. Dashboard 3 个 null/硬编码字段：total_staff / pending_subjects / pending_grading
3. Dashboard 前端测试空缺：fetchCharts / fetchActivity 无单测

---

## Task 1: 修复 Alembic 多 head

**Files:**
- Modify: `alembic/versions/` 中冲突的 migration 文件（调研确定具体文件）

- [ ] **Step 1: 诊断多 head 根因**

```bash
cd ~/projects/edu-cloud
.venv/bin/python -m alembic heads
```

记录所有 head revision ID。

- [ ] **Step 2: 查看 migration 历史**

```bash
.venv/bin/python -m alembic history --verbose | head -40
```

找出分叉点（哪个 revision 有两个子 revision）。

- [ ] **Step 3: 合并 head**

如果是两个独立分支，用 `alembic merge` 创建合并 revision：

```bash
.venv/bin/python -m alembic merge heads -m "merge: unify migration heads after branch merge"
```

- [ ] **Step 4: 验证单一 head**

```bash
.venv/bin/python -m alembic heads
# Expected: 1 个 head
```

- [ ] **Step 5: 跑 migration 测试**

```bash
.venv/bin/python -m pytest tests/test_alembic_s1a_bank.py tests/test_alembic_s1c_admin.py -v
```

Expected: 之前 6 个 FAILED 恢复为 PASSED（或减少）

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/
git commit -m "fix: merge alembic heads to single linear chain"
```

---

## Task 2: Dashboard 后端 3 字段实现

**Files:**
- Modify: `src/edu_cloud/api/dashboard.py`
- Modify: `tests/test_api/test_dashboard.py`

- [ ] **Step 1: 写失败测试（total_staff）**

在 test_dashboard.py 中添加：验证 principal 角色返回的 total_staff 不为 null。

- [ ] **Step 2: 实现 total_staff 查询**

在 dashboard.py 中，将 `"total_staff": None` 替换为对 PlatformUser 表的 COUNT 查询（按 school_id + 非 parent 角色过滤）。

- [ ] **Step 3: 写失败测试（pending_grading）**

验证存在 pending 状态 grading task 时，pending_grading > 0。

- [ ] **Step 4: 实现 pending_grading 查询**

将 `"pending_grading": 0` 替换为对 GradingTask 表的 COUNT 查询（status='pending', school_id 过滤）。

- [ ] **Step 5: 写失败测试（pending_subjects）**

验证存在 stage != 'done' 的科目时，pending_subjects > 0。

- [ ] **Step 6: 实现 pending_subjects 查询**

查询 grading dispatch 中 stage 不为 'done' 的科目数。

- [ ] **Step 7: 全量 dashboard 测试**

```bash
.venv/bin/python -m pytest tests/test_api/test_dashboard.py -v
```

Expected: 原 4 + 新增 3 = 7 PASSED

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/api/dashboard.py tests/test_api/test_dashboard.py
git commit -m "feat: implement dashboard summary total_staff/pending_grading/pending_subjects"
```

---

## Task 3: 前端 Dashboard 测试补全

**Files:**
- Modify: `frontend/src/pages/__tests__/DashboardPage.test.js`

- [ ] **Step 1: 补 fetchCharts mock 测试**

测试 fetchCharts 调用 analytics API 并填充图表数据。

- [ ] **Step 2: 补 fetchActivity mock 测试**

测试 fetchActivity 调用 exams + notifications API 并渲染 activity feed。

- [ ] **Step 3: 补网络错误处理测试**

测试 API 返回 500 时页面不崩溃，显示降级 UI。

- [ ] **Step 4: 跑全量 vitest**

```bash
cd frontend && npx vitest run
```

Expected: 373+ passed / 0 failed

- [ ] **Step 5: vite build**

```bash
npx vite build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/__tests__/DashboardPage.test.js
git commit -m "test: add dashboard fetchCharts/fetchActivity/error-handling tests"
```

---

## Task 4: Sprint 2 提前调研

**Files:**
- 无代码变更，纯调研输出

- [ ] **Step 1: homework 模块调研**

读 modules/homework/router.py + service.py + models.py，确认端点签名。
检查前端是否已有 HomeworkPage.vue（可能和 bank 一样已存在）。

- [ ] **Step 2: academic 模块调研**

读 modules/academic/router.py，确认 semester/timetable/period 端点。
检查前端是否已有 SemesterPage/TimetablePage。

- [ ] **Step 3: calendar 模块调研**

读 modules/calendar/router.py + CalendarPanel.vue 现状。

- [ ] **Step 4: 输出调研文档**

按纪律 1 格式输出：资产盘点 + 端点签名 + [M]/[N] 清单。
保存到 docs/plans/2026-04-26-sprint2-investigation.md。

---

## 出口标准

- [ ] Alembic head 单一，migration 测试恢复
- [ ] Dashboard 3 字段返回真实数据（非 null/0）
- [ ] vitest 无新增 fail + vite build 成功
- [ ] pytest 无新增 fail
- [ ] Sprint 2 调研文档产出
