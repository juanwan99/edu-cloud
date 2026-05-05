---
name: studio
status: active
owner: backend
layer: business

owns_tables:
  - documents
  - document_versions
  - approval_flows
  - approval_steps

owns_routes:
  - /api/v1/studio

exposes:
  services:
    - StudioService
    - ApprovalService
    - PaperService
  events: []

depends_on:
  modules:
    - school
  services:
    - core.permissions
    - api.deps
    - services.paper_service
    - services.notification_service
    - templates.document_templates
  ai_tools: []

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs: []
---

# studio 模块

## 职责

文档工作台：角色模板、文档 CRUD（版本追踪）、状态机流转（draft→reviewed→pending→approved→executed）、审批工作流（链式多步）、论文创建（调用外部 paper-skill 服务）、通知分发触发。

## 边界

- **做什么**：文档创建/编辑/版本管理 / 状态流转（含通知文档审批强制路径）/ 审批流创建与逐步审批 / 论文任务透传到 paper-skill / 通知 executed 后触发 NotificationService.dispatch
- **不做什么**：报表数据计算(analytics) / 日历事件(calendar) / 通知路由与发送实现(notifications) / 考试管理(exam)

## 使用方式

前端 Studio 三栏组件调用。`POST /documents` 创建文档，`PATCH /documents/{id}` 编辑内容（自动保存版本），`POST /documents/{id}/transition` 推进状态。通知类文档 transition 到 pending 自动创建审批流，executed 触发分发。论文通过 `POST /paper/create` 调用 paper-skill 并关联 Studio 文档记录。

## 数据流

```
POST /api/v1/studio/documents → StudioService.create_document → documents 表(status=draft)
PATCH /api/v1/studio/documents/{id} → StudioService.update_document → document_versions 表(旧版本) + documents 表(version++)
POST /api/v1/studio/documents/{id}/transition(status=pending) → ApprovalService.create_flow → approval_flows + approval_steps
POST /api/v1/studio/documents/{id}/transition(status=executed) → NotificationService.dispatch → notifications 表
POST /api/v1/studio/paper/create → PaperService.create_paper(外部 REST) → documents 表(type=paper)
```
