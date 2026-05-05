---
name: school
status: active
owner: backend
layer: infrastructure

owns_tables:
  - schools
  - school_settings
  - school_modules
  - teacher_assignments
  - subject_selections
  - capabilities
  - audit_logs

owns_routes:
  - /api/v1/schools

exposes:
  services:
    - SchoolService
    - SchoolSettingsService
    - TeacherAssignmentService
    - SubjectSelectionService
    - CapabilityService
    - AuditService
  events: []

depends_on:
  modules: []
  services:
    - core.permissions
    - api.deps
  ai_tools: []

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs: []
---

# school 模块

## 职责

学校注册与全生命周期管理：学校档案 CRUD + API Key 轮换、KV 配置项、模块开关（9 codes）、教师排课（幂等批量创建）、选考组合（3+1+2/3+3/custom）、角色能力矩阵、实体变更审计日志。

## 边界

- **做什么**：学校 CRUD + API Key 管理 / 学校配置（KV + 模块开关）/ 排课管理 / 选考组合管理 / 能力矩阵初始化与修改 / 审计日志查询
- **不做什么**：用户管理(platform_user) / 联考(joint_exam) / 考试(exam) / 通知(notifications) / AI Agent

## 使用方式

前端 `SchoolsPage.vue` / `SchoolSettingsPage.vue` / `TeacherAssignmentsPage.vue` / `SubjectSelectionsPage.vue` 调用。所有子路由挂在 `/api/v1/schools/{id}/` 下，跨校角色（platform_admin/district_admin）可访问任意学校，校内角色强制 school scope 隔离。

## 数据流

```
POST /api/v1/schools → SchoolService.create_school → schools 表 + API Key hash
PATCH /api/v1/schools/{id}/settings → upsert_setting → school_settings 表
PATCH /api/v1/schools/{id}/modules/{code} → set_module_enabled → school_modules 表
POST /api/v1/schools/{id}/assignments → create_assignments → teacher_assignments 表（幂等）
POST /api/v1/schools/{id}/selections → create_selection → subject_selections 表
PATCH /api/v1/schools/{id}/capabilities → set_capability → capabilities 表
GET /api/v1/schools/{id}/audit-logs → list_audit_logs → audit_logs 表
```
