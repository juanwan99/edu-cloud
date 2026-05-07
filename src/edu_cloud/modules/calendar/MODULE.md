---
name: calendar
status: active
owner: backend
layer: business

owns_tables:
  - calendar_events
  - notification_rules
  - notifications
  - teaching_plans

owns_routes:
  - /api/v1/calendar
structure_pattern: standard
max_router_loc: 100
routers: [router.py]

exposes:
  services:
    - CalendarService
    - NotificationService
    - teaching_plan_service
  events: []

depends_on:
  modules:
    - school
  services:
    - school_settings_service
  ai_tools: []

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs: []
---

# calendar 模块

## 职责

校历事件管理、通知规则触发、通知分发（stub 模式）、教学计划 CRUD。事件可配置 N 天前自动触发通知规则，规则到期后由 worker 定时任务检查并生成通知草稿。

## 边界

- **做什么**：校历事件 CRUD + 通知规则配置 + 按日期查询触发规则 + 通知分发（首期 stub）+ 教学计划（按学校+科目+年级+学期唯一约束）
- **不做什么**：通知文档内容生成由 `studio` 模块负责；实际推送渠道（企业微信）未接入

## 使用方式

```bash
POST /api/v1/calendar/events          # 创建事件（含通知规则）
GET  /api/v1/calendar/events          # 列表（start/end 日期过滤）
DELETE /api/v1/calendar/events/{id}   # 软删除
```

TeachingPlan 目前由 Studio 文档流程间接调用，无独立 API 路由。

## 数据流

```
用户创建事件 → calendar_events + notification_rules
Worker W3 定时检查 → get_triggered_rules(today) → mark_rule_triggered
Studio 文档 executed → NotificationService.dispatch → notifications 表
教学计划 CRUD → teaching_plans 表（school+subject+grade+semester 唯一）
```
