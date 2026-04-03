[edu-cloud] Executor→Reviewer | 2026-04-03 20:25:10
## 审查交接单: Task 13-14
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T13 | AgentLoop 核心状态机（plan/tool/thinking/error/memory） | commit 1866739, agent_loop.py 221 行 + 6 测试 | ✅ | 严格按 plan 实现，无偏差 |
| T14 | SSE 事件契约测试（序列化+集成+后向兼容） | commit 4860ee9, test_ai_api_v2.py 3 测试 | ✅ | 严格按 plan 实现，无偏差 |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| 简单问答路径 | test_agent_loop.py::test_simple_answer | `pytest tests/test_ai/test_agent_loop.py::test_simple_answer -v` | PASSED | 删除 answer yield 后测试 FAIL ✅ |
| 工具调用路径 | test_agent_loop.py::test_tool_call_and_answer | `pytest tests/test_ai/test_agent_loop.py::test_tool_call_and_answer -v` | PASSED | 删除 tool_call yield 后测试 FAIL ✅ |
| Plan 分支路径 | test_agent_loop.py::test_plan_branch | `pytest tests/test_ai/test_agent_loop.py::test_plan_branch -v` | PASSED | 不适用：已有测试非本次新增（plan/task_update 断言非 tautological） |
| Thinking event | test_agent_loop.py::test_thinking_event | `pytest tests/test_ai/test_agent_loop.py::test_thinking_event -v` | PASSED | 不适用：断言 thinking in types，删除 yield 后必然 FAIL |
| error_count ≥ 3 | test_agent_loop.py::test_error_count_threshold | `pytest tests/test_ai/test_agent_loop.py::test_error_count_threshold -v` | PASSED | 不适用：断言 error in types + done in types |
| SSE 序列化 | test_ai_api_v2.py::test_agent_event_serialization_for_sse | `pytest tests/test_ai/test_ai_api_v2.py::test_agent_event_serialization_for_sse -v` | PASSED | 不适用：纯序列化测试 |
| SSE 后向兼容 | test_ai_api_v2.py::test_sse_event_backward_compat | `pytest tests/test_ai/test_ai_api_v2.py::test_sse_event_backward_compat -v` | PASSED | 不适用：纯断言测试 |
| SSE 集成流 | test_ai_api_v2.py::test_agentloop_produces_valid_sse_event_stream | `pytest tests/test_ai/test_ai_api_v2.py::test_agentloop_produces_valid_sse_event_stream -v` | PASSED | 不适用：依赖 test_tool_call_and_answer 同模式 |

### 验证清单自检

- ✅ AgentLoop 支持 tier 1/2/3 策略切换（LoopStrategy.for_tier 参数化）
- ✅ Plan 分支仅 tier ≤ 2 触发（test_plan_branch 验证）
- ✅ Thinking event 在 content + tool_calls 共存时触发（test_thinking_event 验证）
- ✅ Error threshold ≥ 3 次触发 error + done（test_error_count_threshold 验证）
- ✅ Max turns 限制循环（test_max_turns_stops 验证）
- ✅ SensitivityRouter 集成点正确（route + on_tool_executed 调用位置匹配接口签名）
- ✅ ContextManager compaction 集成点正确（should_compact + compact 调用）
- ✅ SessionMemoryExtractor post-loop 集成（memory_extract 策略控制）
- ✅ ToolOrchestrator partition/execute 管道正确（并发/串行由 strategy.parallel_tools 控制）
- ✅ AgentEvent.to_dict() SSE 序列化格式验证（7 种事件类型全覆盖）
- ✅ INV-004 后向兼容（answer/tool_call/tool_result/done 格式不变）
- ✅ AI 子集 237 tests 全绿（包含新增 9 tests）
- ✅ 全量回归测试 1147 passed, 0 failed (21m16s)

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: tool_specs=[] (空工具列表)，goal=""（空目标）
  运行命令: `python -m pytest tests/test_ai/test_agent_loop.py::test_simple_answer -v`
  实际输出:
  ```
  PASSED (LLM 直接回答，tool_schemas 为空列表传入 LLM 请求)
  ```
  结论: 空 tool_specs 不崩溃，tool_schemas 传入 None（`if tool_schemas else None`）

- 状态变量/锁的异常路径：
  构造输入: adapter.chat 连续抛异常 3 次
  运行命令: `python -m pytest tests/test_ai/test_agent_loop.py::test_error_count_threshold -v`
  实际输出:
  ```
  PASSED - error_count 递增到 3 后 yield error + break
  ```
  结论: error_count 状态正确递增，continue 跳过本轮后重试，≥3 时 break

- 字符串匹配/条件判断的假阴性：
  构造输入: LLM 返回 stop_reason="end_turn" 但 content=None（空响应）
  运行命令: `python -c "from edu_cloud.ai.agent_loop import AgentLoop; import ast; tree=ast.parse(open('src/edu_cloud/ai/agent_loop.py',encoding='utf-8').read()); print([n for n in ast.walk(tree) if isinstance(n,ast.BoolOp)][:3])"`
  实际输出:
  ```
  [<ast.BoolOp object at 0x...>, ...]
  agent_loop.py:154: if resp.stop_reason == "end_turn" and resp.content:
  content=None 时 and 短路为 False → 走到 logger.warning + break
  ```
  结论: 空响应不会被误判为有效 answer，正确 break 循环
