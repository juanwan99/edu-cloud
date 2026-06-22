---
name: bank
status: active
owner: backend
layer: business

owns_tables:
  - bank_questions
  - student_error_books

owns_routes:
  - /api/v1/bank
structure_pattern: standard
max_router_loc: 200
routers: [router.py]

exposes:
  services:
    - list_bank_questions
    - get_bank_question
    - search_questions
    - get_questions_stats_overview
    - get_student_error_book
    - get_error_book_stats
    - get_error_knowledge_summary
    - get_recommended_practice
  events: []

depends_on:
  modules: []
  services:
    - bank_workflow
  ai_tools:
    - ai/tools/bank.py

created: "2026-05-05"
last_reviewed: "2026-06-22"
design_docs: []
---

# bank 模块

## 职责

学校题库管理和学生错题本。题库从考试自动入库并积累统计属性（难度/区分度/常见错误），错题本由 AI 阅卷后自动收集并跟踪掌握状态。

## 边界

- **做什么**：题库 CRUD + 多条件搜索 + 统计概览；错题本查询 + 按知识点聚合 + 基于薄弱知识点推荐练习题
- **不做什么**：题库入库写入由 `pipeline` 模块负责；题目元数据（Question 表）归 `exam` 模块

## 使用方式

```bash
GET  /api/v1/bank/questions                      # 列表（type/difficulty 过滤）
GET  /api/v1/bank/questions/search               # 多条件组合搜索（分页）
GET  /api/v1/bank/questions/stats/overview       # 统计概览
GET  /api/v1/bank/questions/{id}                 # 详情
GET  /api/v1/bank/error-book/{student_id}        # 错题本
GET  /api/v1/bank/error-book/{student_id}/stats  # 错题统计
GET  /api/v1/bank/error-book/{student_id}/knowledge-summary  # 知识点聚合
GET  /api/v1/bank/error-book/{student_id}/recommendations    # 推荐练习
```

## 数据流

```
pipeline 写入 → bank_questions（考试入库）
pipeline 写入 → student_error_books（AI 阅卷后收集）
bank service 读取 → 查询/搜索/推荐
AI tools (bank.py) → get_student_error_book / get_question_stats
```
