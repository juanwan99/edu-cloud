---
type: handoff
created: 2026-03-22 18:21:31
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-super-platform-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p3-notification-plan.md
---

# P3 家校通信 — 执行交接卡（v2，含 6 项 GPT Review Finding 修复）

## 约束与偏好

**T3 流程**

1. **执行方式**: Subagent-Driven Development
2. **P4 基础**: 233 tests，AI Agent + Studio + 知识库 + L1-L4 工具
3. **企微延期**: 消息发送用 stub 模式（标记 sent + 记录日志），不调用真实 API
4. **审批流已有**: ApprovalService + ApprovalFlow 在 P2 实现，P3 复用并接入
5. **通知幂等**: 同一 document_id 不重复发送
6. **arq worker**: 独立进程。启动方式: `arq edu_cloud.worker.WorkerSettings`（不是 `python -m`）。cron 每天 22:00 UTC (= 06:00 UTC+8)
7. **校验重点**: triggered 标记防重复、dispatch 幂等、notification→document 的 type 检查

### GPT Plan Review 修复要点（已全部写入 plan 中）

计划文件已包含 6 项 GPT Review findings 的完整修复代码，Executor 按计划执行即可：

- **F1 (HIGH code-bug)**: `created_by` 必须来自 `event.created_by`（真实 users.id），不能用 `"system"` 字符串。影响 Task 2 `get_triggered_rules` + Task 3 `auto_draft`
- **F2 (HIGH design-concern)**: Document 模型新增 `assigned_to` 字段；`list_documents` 查 `created_by OR assigned_to`。影响 Task 1 模型 + Task 3 auto_draft
- **F3 (HIGH code-bug)**: transition 端点保留 `require_permission(GENERATE_NOTIFICATION)`，executed 额外检查 `SEND_NOTIFICATION`。影响 Task 4
- **F4 (HIGH design-concern)**: 通知类文档必须走审批流（reviewed→executed 被阻断）；pending 时自动创建 ApprovalFlow。影响 Task 4
- **F5 (HIGH code-bug)**: worker.py 导入 `async_session`（不是 `async_session_factory`）；通过 `arq CLI` 启动（不是 `asyncio.run`）。影响 Task 3
- **F6 (MED design-concern)**: `_fill_template_content` 用事件上下文填充模板各 section，非空白。影响 Task 3

### database.py 关键信息

`async_session` 是 `async_sessionmaker` 实例（不是函数工厂），直接 `async with async_session() as db:` 调用。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-03-22 18:21:31
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p3-notification-handoff.md，
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p3-notification-plan.md Task 1-4 执行。
使用 executing-plans skill。
完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
