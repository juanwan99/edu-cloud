---
type: handoff
created: 2026-04-04 15:23:23
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-04-agent-evolution-design.md
plan: (待生成，新会话用 writing-plans skill 创建)
---

## 约束与偏好

**T4 流程。** 设计已定稿（616 行，含 GPT 补充审查 27 项处置），下一步是 writing-plans 生成实施计划。

1. **设计定稿背景：** 本次设计经过 5 段讨论（DataScope/预计算表/工作流引擎/工具重组/角色人格）+ GPT 独立补充审查（10 HIGH + 7 MED 全部吸收）。用户确认了所有设计段和 GPT 修订。

2. **第一期范围明确：** W1（考后分析）+ W3（学情画像）+ W6（异常巡检）。§7 列出的扩展项（走班/家校沟通/学期报告等）第一期不做，只预留。

3. **权限是核心关切：** 用户反复强调"底层就严格规定权限"。DataScope 不是附加层而是地基——所有后续工作建立在它之上。fail-closed 是默认策略。

4. **配套设计原则：** 数据+工具+工作流必须作为一个整体设计，不能各自为政。每个工作流有自己的专用数据表和专用工具。

5. **复用现有基础设施：** pipeline 表（student_knowledge_mastery/student_error_books/student_exam_snapshots）复用不新建。AgentLoop/ToolRegistry/LLMProxyAdapter/EventBus/arq worker 全部复用。capabilities + school_settings 表复用为软规则载体。

6. **分批建议（设计 §8）：** B1 基础设施 → B2 W1 → B3 W3 → B4 W6 → B5 IntentRouter → B6 集成。B1 是地基（DataScope + ScopedQuery + 新表 + fail-closed），必须先做。

7. **端到端验证已完成：** edu-agent 内核已跑通真实 LLM 调用（Claude Sonnet 4.5 via llm-proxy），工具调用链路正常。本次修复了 3 个集成 bug（X-LLM-Slot header / ai-chat slot / tool schema 双重嵌套），这些修复已 commit 但未纳入 GPT 审查（属 T2 修复）。

8. **llm-proxy Anthropic adapter 已增强：** 本会话在 llm-proxy 项目中修复了 Anthropic adapter 的 tool_use 支持（to_provider + from_provider 双向转换），commit f653e63。这是 edu-agent 工具调用能跑通的前提。

## 启动 Prompt

```
[edu-cloud] Planner | 2026-04-04 15:23:23
项目: C:\Users\Administrator\edu-cloud  读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-04-agent-evolution-handoff.md。

角色：edu-agent 演进 T4 Planner。

任务：读取设计文档 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-04-agent-evolution-design.md，使用 writing-plans skill 生成实施计划。设计 §8 已给出分批建议（B1-B6），以此为基础细化 Task 拆分。

注意：
- 这是 T4 项目，计划完成后必须 codex-review (plan) 审查
- DataScope (B1) 是地基，所有后续批次依赖它
- 复用现有 pipeline 表，不重复建表
- 每个 Task 必须有测试契约（5 字段）和边界条件（至少 3 个）
- 完成后输出审查交接单。
```
