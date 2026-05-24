# Agent Phase 2 Plan — R2 修正附录

> GPT R2 审查 7 findings，全部确认。此附录修正计划中的代码事实偏差。
> 计划主文件不再编辑（L019 打地鼠防护）。

## R2-F-001: WorkflowContext 桥接方式修正

**计划原文**: 手建 WorkflowContext（传 db_sessionmaker 等）
**事实**: WorkflowExecutor.execute() 自己创建 context（engine.py:106）
**修正**: S4-T2 工具直接调用 `executor.execute(W1_POST_EXAM, school_id=deps.school_id, trigger_type="agent", trigger_ref=exam_id)`，不需要 _agent_to_workflow_ctx adapter。删除 adapter 设计段。

## R2-F-002: 消息历史存储格式修正

**计划原文**: 存 role_in_chat + content + metadata_json
**事实**: Pydantic AI 的 message_history 是内部格式（ModelRequest/ModelResponse 对象），`result.all_messages()` 返回的是序列化可反序列化的结构
**修正**（R3-F-001 再修正）: 使用 Pydantic AI 官方序列化 API:
- 存储: `result.all_messages_json().decode()` → AiChatMessage.content (Text)
- 恢复: `from pydantic_ai.messages import ModelMessagesTypeAdapter` → `ModelMessagesTypeAdapter.validate_json(saved)` → 传入 `message_history`
- 单独存 user/assistant 纯文本供 UI 展示（metadata_json 中）
- 不用 `json.dumps(result.all_messages())`（ModelMessage 不可直接 JSON 序列化）

## R2-F-003: Prompt 中工具名修正

**计划原文**: prompt 引导调用 `get_recent_findings`
**修正**: 改为 `get_findings`（misc.py 实际工具名）

## R2-F-004: 幂等键说明修正

**计划原文**: `idempotency_key = w1_post_exam_{exam_id}`
**事实**: WorkflowExecutor 内部生成 `{school_id}:{workflow.name}:{trigger_ref}:{date.today()}`
**修正**: 计划描述改为"executor 内置按 school+workflow+ref+date 去重，同日同考试不重复执行"

## R2-F-005: FK cascade 策略补充

**修正**: AiChatMessage 的 session_id FK 加 `ondelete="CASCADE"`。AiToolCall 如果有 session_id FK 也加 CASCADE。DELETE session 端点改为先删 DB 记录（CASCADE 自动清理子表），再删内存。

## R2-F-006: 验证标准补充

**修正**: 所有涉及前端的 Sprint（S2/S5）验证标准统一为：
1. `npx vitest run`（单测通过）
2. `npx vite build`（构建成功）
3. `https://mcu.asia` 手动验证（交付证据）

## R2-F-007: 文件路径修正

**修正**: AiSession 真实 ORM 定义在 `src/edu_cloud/ai/models.py:5`，`src/edu_cloud/models/ai_session.py` 是 re-export stub。实施时修改 `ai/models.py`。
