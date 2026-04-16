---
type: handoff
created: 2026-03-22 08:55:15
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-super-platform-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p1-ai-brain-plan.md
---

# P1 AI 大脑 — 执行交接卡

## 约束与偏好

**T3 流程**

1. **执行方式**: Subagent-Driven Development（用户已确认）
2. **GPT 5.4 唯一 Codex 模型**: codex exec 不指定 -m（默认 gpt-5.4），禁止用 o3/gpt-4.1
3. **P0 基础**: 94 tests，User + UserRole + scope RBAC，三栏前端已就绪
4. **llm-proxy 在 port 8100**: OpenAI 兼容 API，`POST /v1/chat/completions`
5. **默认模型 claude-sonnet-4-6**: 通过 llm-proxy 调用
6. **匿名化必须集成**: agent.py 中 tool 结果匿名化后传 LLM，final answer 反匿名化后返前端
7. **L2 跨校工具延期**: 文件结构中保留 cross_school.py 占位但不实现
8. **exam-ai 参考实现**: `C:\Users\Administrator\exam-ai\src\exam_ai\agent\` 目录有 ReAct loop/tools/anonymizer 可参考

## 启动 Prompt

```
[edu-cloud] Executor | 2026-03-22
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p1-ai-brain-handoff.md，
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p1-ai-brain-plan.md Task 1-7 执行。
使用 superpowers:subagent-driven-development skill。
完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
