---
name: portal
status: active
owner: backend
layer: cross-cutting

owns_tables: []

owns_routes:
  - /api/v1/portal
structure_pattern: standard
max_router_loc: 120
routers: [router.py]

exposes:
  services:
    - PortalAggregationService
  events: []

depends_on:
  modules: []
  services:
    - portal_workflow
    - school_settings_service
    - notifications_api
  ai_tools: []

created: 2026-06-05
last_reviewed: 2026-06-22
design_docs:
  - docs/governance/portal-aggregation-contract.md
---

# portal 模块

## 职责

门户聚合读模型底座。按当前角色、租户、模块开关和权限组合首页摘要、待办、消息、校历摘要和服务入口。

## 边界

- **做什么**：提供 `/api/v1/portal/*` 稳定 DTO；组合 source module service/API 输出；过滤学校模块开关和权限。
- **不做什么**：不拥有业务表；不变更通知、日历、审批、工作流、作业等源模块状态；不直接查询源模块表。
