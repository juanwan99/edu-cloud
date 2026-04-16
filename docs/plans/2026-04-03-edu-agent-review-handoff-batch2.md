[edu-cloud] Executor→Reviewer | 2026-04-03 18:46:16
## 审查交接单: Task 5-7 (Batch 2: LLM Adapter Layer)
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T5 | 创建 LLMProxyAdapter + LLMRequest/Response/Chunk + LLMAdapter Protocol | commit 09f171b, 新建 llm_adapter.py (164行) + 6 tests | 🔀 | 测试中 httpx.Response 需要 request 参数才能 raise_for_status()，增加了 _mock_response 辅助函数 |
| T6 | 创建 CapabilityProbe + LoopStrategy | commit 5d55713, 新建 capability_probe.py + 8 tests | ✅ | — |
| T7 | 创建 SensitivityRouter（双通道路由 + student 锁定） | commit ba80e27, 新建 sensitivity_router.py + 5 tests | ✅ | — |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| chat() 解析 OpenAI 响应 | test_llm_adapter.py::test_proxy_adapter_chat_basic | `pytest tests/test_ai/test_llm_adapter.py::test_proxy_adapter_chat_basic -v` | PASSED | 不适用：新增测试 |
| chat() 提取 tool_calls | test_llm_adapter.py::test_proxy_adapter_chat_with_tool_calls | `pytest tests/test_ai/test_llm_adapter.py::test_proxy_adapter_chat_with_tool_calls -v` | PASSED | 不适用：新增测试 |
| Tier 自动检测 | test_capability_probe.py::test_probe_tier1 | `pytest tests/test_ai/test_capability_probe.py::test_probe_tier1 -v` | PASSED | 不适用：新增测试 |
| Tier 3 降级（异常） | test_capability_probe.py::test_probe_tier3_on_error | `pytest tests/test_ai/test_capability_probe.py::test_probe_tier3_on_error -v` | PASSED | 不适用：新增测试 |
| Student 工具锁定通道 (INV-005) | test_sensitivity_router.py::test_student_tool_locks_channel | `pytest tests/test_ai/test_sensitivity_router.py::test_student_tool_locks_channel -v` | PASSED | 不适用：新增测试 |
| 全 public 工具路由到 enhanced | test_sensitivity_router.py::test_public_tools_use_enhanced | `pytest tests/test_ai/test_sensitivity_router.py::test_public_tools_use_enhanced -v` | PASSED | 不适用：新增测试 |

### 验证清单自检

- ✅ LLMProxyAdapter 通过 X-Slot header 路由到 llm-proxy slot
- ✅ _parse_response 正确映射 finish_reason: "tool_calls"→"tool_use", "stop"→"end_turn"
- ✅ ToolCall.from_openai 解析 arguments JSON 字符串
- ✅ TokenUsage.total 正确计算 input + output
- ✅ CapabilityProbe: tool_use=True + context>=100K → Tier 1
- ✅ CapabilityProbe: tool_use=True + context>=30K → Tier 2
- ✅ CapabilityProbe: adapter 异常 → Tier 3（不抛异常）
- ✅ CapabilityProbe: manual override 优先于自动检测
- ✅ SensitivityRouter: enhanced=None → 始终 primary
- ✅ SensitivityRouter: 全 public → enhanced
- ✅ SensitivityRouter: school/student → primary
- ✅ SensitivityRouter: student 执行后锁定 primary_locked (INV-005)
- ✅ SensitivityRouter: 锁定后即使全 public 也返回 primary
- ✅ 全量 test_ai/ 182 tests PASSED

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: adapter.chat 抛 ConnectionError
  运行命令: `pytest tests/test_ai/test_capability_probe.py::test_probe_tier3_on_error -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 异常被 _test_tool_use 捕获，返回 has_tool_use=False，tier 降级到 3

- 状态变量/锁的异常路径：
  构造输入: state.channel="primary_locked" 后再调用 route([public_specs])
  运行命令: `pytest tests/test_ai/test_sensitivity_router.py::test_student_tool_locks_channel -v`
  实际输出:
  ```
  PASSED
  ```
  结论: primary_locked 状态正确阻止路由到 enhanced，即使工具全部是 public

- 字符串匹配/条件判断的假阴性：
  构造输入: finish_reason="function_call"（旧 OpenAI 格式）
  运行命令: `python -c "from edu_cloud.ai.llm_adapter import LLMProxyAdapter; r = LLMProxyAdapter._parse_response({'choices': [{'message': {'role': 'assistant', 'content': 'hi'}, 'finish_reason': 'function_call'}], 'usage': {}}); print(r.stop_reason)"`
  实际输出:
  ```
  tool_use
  ```
  结论: function_call 正确映射为 tool_use
