---
type: handoff
created: 2026-03-22 18:06:31
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-super-platform-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p3-notification-plan.md
---

# P3 家校通信 — 执行交接卡

## 约束与偏好

**T3 流程**

1. **执行方式**: Subagent-Driven Development
2. **GPT 5.4 唯一 Codex 模型**
3. **P4 基础**: 233 tests，AI Agent + Studio + 知识库 + L1-L4 工具
4. **企微延期**: 消息发送用 stub 模式（标记 sent + 记录日志），不调用真实 API
5. **审批流已有**: ApprovalService + ApprovalFlow 在 P2 实现，P3 复用
6. **通知幂等**: 同一 document_id 不重复发送
7. **arq worker**: 独立进程，PM2 管理。cron 每天 22:00 UTC (= 06:00 UTC+8)
8. **校验重点**: triggered 标记防重复、dispatch 幂等、notification→document 的 type 检查

## 启动 Prompt

```
[edu-cloud] Executor | 2026-03-22
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p3-notification-handoff.md，
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p3-notification-plan.md Task 1-4 执行。
使用 superpowers:subagent-driven-development skill。
完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
