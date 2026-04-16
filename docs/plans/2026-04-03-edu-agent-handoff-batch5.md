---
type: handoff
created: 2026-04-03 20:11:04
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md
---

## 约束与偏好

**T4 流程。** Batch 5 是核心集成批次——AgentLoop 把前 4 批所有模块串起来。

### Batch 1-4 已落地的关键实现细节（plan 中没有，执行中产生的）

1. **registry.py 双签名兼容**：`_is_new_style()` 启发式检测工具签名，旧 `**kwargs` 工具和新 `(input, ctx)` 工具共存。AgentLoop 中调用 `registry.execute(name, args, ctx)` 即可，内部自动路由。
2. **tool_executor.py 并发安全降级**：`ctx.db is not None` 时自动串行化（AsyncSession 不支持并发），`ctx.db is None` 时才并发执行。AgentLoop 传入真实 db session 时所有工具串行，这是正确行为。
3. **capability_probe.py 缓存**：首次 `determine_tier()` 后结果缓存在 `_cached_tier`，后续直接用 `get_tier()`。AgentLoop 初始化时调一次即可。
4. **context_manager.py 基于 turn 的压缩**：`should_compact()` 接受 `turn_count` 参数，不仅看 token 也看轮次（>12 轮触发）。
5. **task_planner.py plan 解析容错**：LLM 返回非 JSON 或非 dict 的 plan 字段时返回 None（不崩溃），AgentLoop 应当 fallback 到直接 ReAct。
6. **schemas.py ChatMessage 别名**：`ChatMessage = Message`，旧代码引用 `ChatMessage` 仍然可用，AgentLoop 内部统一用 `Message`。
7. **GPT 审查共发现 6 code-bug + 9 test-gap，全部已修复**。228 tests 全绿。

### Batch 5 特别注意

- Task 13（AgentLoop）是整个项目最复杂的单个 Task，预估 ~300 行。它需要导入并协调：llm_adapter、capability_probe、sensitivity_router、tool_executor、context_manager、task_planner、prompts、schemas 全部模块。
- Task 14（SSE Contract Tests）验证 AgentEvent 序列化格式与前端 `stores/aiChat.js` 的 SSEProcessor 兼容。
- prompts.py（Task 12）已在 Batch 4 完成，AgentLoop 可直接 `from edu_cloud.ai.prompts import build_teacher_prompt` 调用。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-03 20:11:04
项目: C:\Users\Administrator\edu-cloud  读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-handoff-batch5.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md Task 13-14 执行。使用 executing-plans skill。完成后输出审查交接单。
```
