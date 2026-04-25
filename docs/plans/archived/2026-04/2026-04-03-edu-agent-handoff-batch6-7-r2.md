---
type: handoff
created: 2026-04-04 08:08:46
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md
---

## 约束与偏好

**T4 流程 — Round 2 修复。** GPT R1 FAIL，5 个 HIGH finding 需修复。

### 必须修复的 Findings

**F001 (HIGH code-bug)：fallback 死路径**
- 位置：`src/edu_cloud/api/ai.py` L105-L159
- 问题：`enabled_modules` 在 try 块内赋值，如果 `get_enabled_modules()` 之前的步骤失败（如 `AgentProfileService.get_or_create()`），fallback 分支构造 ToolContext 时引用未定义变量 → UnboundLocalError
- 修复方向：fallback 所需的局部变量（enabled_modules、capabilities、tool_specs）在 try 块前初始化默认值

**F002 (HIGH code-bug, behavior_change, 用户拒绝)：多轮会话语义丢失**
- 位置：`src/edu_cloud/api/ai.py` L35 `_sessions` dict + `src/edu_cloud/ai/agent_loop.py` L65
- 问题：旧 Agent 通过 `_sessions[session_id].context` 保存 AgentContext（含历史消息），同 session_id 的后续请求继承历史。新 AgentLoop.run() 每次从空消息列表开始。
- 修复方向：`_sessions` 保存 AgentLoop 运行后的消息历史，下次同 session_id 请求时注入。AgentLoop.run() 增加 `history_messages` 参数。

**F003 (HIGH code-bug)：Anonymizer 链路断裂**
- 位置：`src/edu_cloud/ai/agent_loop.py` L168-L191
- 问题：`ctx.anonymizer` 被设置但从未被消费。工具结果原样写入 messages，LLM 直接接触学生实名。最终回答也不做 deanonymize。
- 修复方向：工具结果写入 messages 前经过 `anonymizer.anonymize()`，最终 answer 经过 `anonymizer.deanonymize()`

**F004 (HIGH test-gap)：无 HTTP 入口级 SSE 合同测试**
- 位置：`tests/test_ai/test_ai_api.py`
- 问题：SSE 测试只在 AgentLoop 层面，未经过 FastAPI HTTP 入口
- 修复方向：用 TestClient 对 `POST /api/v1/ai/chat` 发请求，mock LLM 返回，验证 SSE 事件流格式

**F005 (HIGH test-gap)：17 个迁移工具无执行级测试**
- 位置：analytics_score.py, analytics_compare.py, grading_ops.py, bank.py, profile.py 对应的 test 文件
- 问题：这些工具只有注册元数据测试，无 `(input, ctx) → ToolResult` 执行级覆盖
- 修复方向：每个文件补至少 1 个执行级测试（空输入 + 正常输入 + 异常包装）

**P001 (MED design-concern)：** diff 范围混入非 AI 改动 — 记入 design.md 待处置，不阻塞本轮修复。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-04 08:08:46
项目: C:\Users\Administrator\edu-cloud  读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-handoff-batch6-7-r2.md，修复 F001-F005（GPT R1 FAIL findings）。使用 executing-plans skill。完成后输出审查交接单。
```
