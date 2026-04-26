# P3 家校通信 — 审查交接单 Batch 1

> **时间**: 2026-03-22 19:45:00
> **Executor**: Claude Opus 4.6 (subagent-driven-development)
> **T 级别**: T3
> **Plan**: `docs/plans/2026-03-22-p3-notification-plan.md`

## Batch 范围

| Task | 描述 | Commits |
|------|------|---------|
| Task 1 | 日历+通知数据模型 + Document.assigned_to | 0b27bd8 |
| Task 2 | 日历服务 + API + 3 通知模板 + 触发规则匹配 | 23894a1 |
| Task 3 | 自动拟稿任务 + 通知分发（stub）+ arq worker | 8eaa3cf |
| Task 4 | 审批触发分发 + 权限强化 + 审批流创建 + 前端日历面板 | d92e493 |

**Commit 范围**: `0b27bd8..d92e493` (4 commits)

## 测试结果

```
251 passed, 2 warnings in 154.94s
```

**新增测试**: 13 (238 baseline → 251)

| 测试文件 | 数量 | 覆盖内容 |
|---------|------|---------|
| test_models/test_calendar.py | 5 | 模型字段存在性 + 默认值（CalendarEvent/NotificationRule/Notification） |
| test_services/test_calendar_service.py | 5 | CalendarService: 创建事件/列表/触发规则匹配/幂等防重复/软删除 |
| test_api/test_calendar_api.py | 4 | Calendar API: 创建/列表/删除/未认证拒绝 |
| test_services/test_notification.py | 2 | NotificationService: stub 分发/幂等检查 |
| test_tasks.py | 2 | auto_draft: 规则匹配创建 Document/已触发不重复 |

注：P3 无额外 studio transition 测试（F3/F4 行为由 GPT 审查覆盖）

## 新增/修改文件清单

### 新增文件 (11)
```
src/edu_cloud/models/calendar.py           # CalendarEvent + NotificationRule 模型
src/edu_cloud/models/notification.py       # Notification 模型（发送记录）
src/edu_cloud/services/calendar_service.py # 日历 CRUD + 触发规则匹配 + 防重复标记
src/edu_cloud/services/notification_service.py # 通知分发（stub 模式，幂等）
src/edu_cloud/api/calendar.py             # 日历 REST API（创建/列表/删除）
src/edu_cloud/tasks.py                    # auto_draft_notifications 定时任务
src/edu_cloud/worker.py                   # arq worker 入口（cron 22:00 UTC = 06:00 UTC+8）
frontend/src/components/calendar/CalendarPanel.vue  # 日历事件管理面板
tests/ (5 test files)
```

### 修改文件 (7)
```
src/edu_cloud/models/document.py               # +assigned_to 字段（FK → users.id, nullable）
src/edu_cloud/services/studio_service.py       # list_documents OR(created_by, assigned_to) + F4 通知审批前置检查
src/edu_cloud/api/studio.py                    # transition 权限→GENERATE_NOTIFICATION + F3 SEND_NOTIFICATION + F4 审批流 + dispatch 触发
src/edu_cloud/api/app.py                       # +calendar/notification 模型导入 + calendar_router 注册
src/edu_cloud/templates/document_templates.py  # +3 通知模板（holiday_safety/exam_reminder/meeting_invite）
frontend/src/components/context/ContextPanel.vue # +CalendarPanel 嵌入
tests/conftest.py                              # +calendar/notification 模型导入
```

## 关键设计决策

1. **企微延期（stub 模式）**: 消息发送用 stub 直接标记 sent + 日志，不调用真实 API
2. **通知幂等**: 同一 document_id 不重复发送（Notification 表查重）
3. **触发防重复**: NotificationRule.triggered 标记，已触发的规则不再匹配
4. **F1 created_by**: 自动拟稿文档的 created_by 来自事件创建者（真实 users.id FK），不用 "system"
5. **F2 assigned_to**: Document 新增 assigned_to 字段，list_documents 查 OR 条件，确保被指派教师 Studio 可见
6. **F3 权限强化**: transition 保留 GENERATE_NOTIFICATION；executed 额外检查 SEND_NOTIFICATION
7. **F4 审批流**: 通知类文档必须走审批（reviewed→executed 被阻断）；pending 时自动创建 ApprovalFlow
8. **F5 arq worker**: 导入 async_session（async_sessionmaker 实例），通过 `arq CLI` 启动
9. **F6 模板填充**: _fill_template_content 用事件上下文填充各 section，非空白占位

## 已知限制

- 审批人列表首期为空（TODO: 从组织架构自动获取）
- 前端日历无编辑/详情功能（仅创建+列表+删除）
- arq worker 未在 CI 中启动测试（需 Redis）
- 通知 transition 测试依赖 API 集成（无独立的 F3/F4 单测）
