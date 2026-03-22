---
type: handoff
created: 2026-03-22 11:56:32
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-super-platform-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p2-studio-plan.md
---

# P2 Studio 产出 — 执行交接卡

## 约束与偏好

**T3 流程**

1. **执行方式**: Subagent-Driven Development
2. **GPT 5.4 唯一 Codex 模型**: 禁止用其他模型
3. **P1 基础**: 138 tests，AI Agent (ReAct + 4 L1 tools + SSE)，三栏前端
4. **PDF 导出简化**: P2 用浏览器打印替代 WeasyPrint，后续补
5. **富文本简化**: P2 用 textarea 替代 Tiptap，后续补
6. **审批链固化**: 不做通用工作流引擎，3 种固定审批链
7. **L4 工具**: generate_report + generate_comment，注册到 L4_action category
8. **Alembic**: Task 1 完成后需 autogenerate migration

## 启动 Prompt

```
[edu-cloud] Executor | 2026-03-22
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p2-studio-handoff.md，
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p2-studio-plan.md Task 1-6 执行。
使用 superpowers:subagent-driven-development skill。
完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
