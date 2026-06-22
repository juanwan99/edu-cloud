---
name: homework
status: active
owner: backend
layer: business

owns_tables:
  - homework_tasks
  - homework_submissions

owns_routes:
  - /api/v1/homework
structure_pattern: standard
max_router_loc: 300
routers: [router.py]

exposes:
  services:
    - HomeworkTaskService
    - HomeworkSubmissionService
  events: []

depends_on:
  modules: []
  services:
    - homework_workflow
  ai_tools:
    - ai/tools/homework.py

created: "2026-05-05"
last_reviewed: "2026-06-22"
design_docs: []
---

# homework 模块

## 职责

作业全生命周期管理：创建→发布→提交→批改→关闭。支持考后补救作业自动生成（基于考试分析数据 + 题库关联），角色 scope 过滤（subject_teacher 只看自己布置的，homeroom_teacher 限本班）。

## 边界

- **做什么**：作业 CRUD + 状态流转（draft→active→expired→closed）+ 学生提交 + 单个/批量批改 + 考后补救作业生成 + 作业内容详情解析
- **不做什么**：题库查询由 `bank` 模块提供；考试原始数据由 `exam`/`scan` 模块提供

## 使用方式

```bash
POST /api/v1/homework/tasks                          # 创建
GET  /api/v1/homework/tasks                          # 列表（class/subject/status/type 过滤）
GET  /api/v1/homework/tasks/{id}                     # 详情（含 stats）
PATCH /api/v1/homework/tasks/{id}                    # 更新（仅 draft）
POST /api/v1/homework/tasks/{id}/publish             # 发布
POST /api/v1/homework/tasks/{id}/close               # 关闭
DELETE /api/v1/homework/tasks/{id}                   # 删除（仅 draft）
POST /api/v1/homework/tasks/from-exam                # 考后补救自动生成
GET  /api/v1/homework/tasks/{id}/submissions         # 提交列表
POST /api/v1/homework/tasks/{id}/submissions/{sub_id}/submit  # 学生提交
POST /api/v1/homework/tasks/{id}/submissions/{sub_id}/grade   # 单个批改
POST /api/v1/homework/tasks/{id}/grade-batch         # 批量批改
GET  /api/v1/homework/tasks/{id}/stats               # 提交/批改统计
```

## 数据流

```
教师创建作业 → homework_tasks
发布时自动创建 → homework_submissions（per student）
学生提交 → submission.status=submitted
教师批改 → submission.score + feedback
考后补救 → 读 exam/scan/bank 数据 → 自动生成 remedial 类型作业
AI tools (homework.py) → list/stats/submit/assign/recommend_remedial
```
