---
name: conduct
status: active
owner: backend+frontend
layer: business

owns_tables:
  - student_profiles
  - conduct_class_configs
  - conduct_rule_categories
  - conduct_rule_items
  - conduct_records
  - conduct_groups
  - conduct_group_members
  - conduct_semesters
  - conduct_notifications

owns_routes:
  - /api/v1/conduct
structure_pattern: multi-router
max_router_loc: 650
routers: [admin_router.py, parent_router.py, notification_router.py]

exposes:
  services:
    - AdminService
    - ParentService
    - RulesService
    - ExportService
    - EventService
  events: []

depends_on:
  modules:
    - student
    - school
  services:
    - ai.registry
    - ai.tool_context
    - core.permissions
    - api.deps
    - api.permissions
  ai_tools:
    - get_conduct_rankings
    - get_student_conduct_summary
    - get_conduct_records
    - add_conduct_points
    - get_conduct_rules
    - get_class_conduct_overview
    - analyze_student_behavior
    - get_class_behavior_insights
    - draft_parent_notification

created: 2026-04-12
last_reviewed: 2026-04-14
design_docs:
  - docs/plans/2026-04-12-conduct-module-design.md
  - docs/plans/2026-04-14-conduct-roadmap-design.md
---

# conduct 模块

## 职责

学生操行积分 / 德育管理 / 家长门户。覆盖班级积分记录、班规 CRUD、小组管理、学期切换、家长注册绑定查看、管理端 Excel 导出、AI Chat 9 工具。

## 边界

- **做什么**：积分 CRUD + 班规 CRUD + 排行榜 + 小组管理 + 学期管理 + 家长门户 + PII 加密 + 9 AI 工具
- **不做什么**：学生基本信息(student) / 成绩考试(exam/analytics) / 通知推送(notifications) / AI Chat 入口(ai)
