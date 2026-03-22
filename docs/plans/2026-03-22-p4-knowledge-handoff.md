---
type: handoff
created: 2026-03-22 14:21:57
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-super-platform-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p4-knowledge-plan.md
---

# P4 知识深度 — 执行交接卡

## 约束与偏好

**T3 流程**

1. **执行方式**: Subagent-Driven Development
2. **GPT 5.4 唯一 Codex 模型**
3. **P2 基础**: 186 tests，AI Agent + Studio + L1/L4 工具
4. **知识库路径**: `C:\Users\Administrator\edu-knowledge-base\subjects\biology_senior\`
5. **不引入向量库**: 结构化 JSON + 内存关键词搜索（YAGNI）
6. **L3 工具无 _db 注入**: 知识库是公共数据，不需要数据库或 scope 过滤
7. **paper-skill**: 端口 9103，REST API `POST /api/paper/create`，`GET /api/paper/:id/status`
8. **知识库加载可选**: `KNOWLEDGE_ENABLED=True` 时才加载，测试时可 skip

## 启动 Prompt

```
[edu-cloud] Executor | 2026-03-22
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p4-knowledge-handoff.md，
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p4-knowledge-plan.md Task 1-4 执行。
使用 superpowers:subagent-driven-development skill。
完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
