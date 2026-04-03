[edu-cloud] Executor→Reviewer | 2026-04-03 18:19:05
## 审查交接单: Task 1-4 (Batch 1: Foundation Layer)
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | 创建 ToolContext + ToolResult dataclass | commit ae568cb, 新建 tool_context.py + 5 tests | ✅ | — |
| T2 | ToolSpec 新增 is_read_only/sensitivity，ToolRegistry 双签名 execute + get() | commit a73bcf8, 重写 registry.py + 6 new tests + 9 old tests pass | 🔀 | get_schemas 增加了自动检测 legacy 全 JSON Schema vs 新 properties-only 格式，防止双层包装 |
| T3 | ToolAccessResolver async→sync | commit 68207a2 + 982c288, 改 tool_access.py + 修 ai.py 调用方 + 更新 3 个测试文件 | 🔀 | plan 只列了 tool_access.py 和 test_tool_access_v2.py，实际还需修 ai.py:119、test_agent_pipeline.py(4处)、test_tools_registration.py(2处) 的 await 调用 |
| T4 | schemas 新增 Message 别名 + Transition 枚举 | commit 320ce82, 重写 schemas.py + 5 new tests + 7 old tests pass | ✅ | — |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| ToolResult 序列化 | test_tool_context.py::test_tool_result_to_dict | `pytest tests/test_ai/test_tool_context.py::test_tool_result_to_dict -v` | PASSED | 不适用：新增测试 |
| ToolContext 字段完整性 | test_tool_context.py::test_tool_context_fields | `pytest tests/test_ai/test_tool_context.py::test_tool_context_fields -v` | PASSED | 不适用：新增测试 |
| 新签名 execute | test_registry_v2.py::test_registry_execute_new_style | `pytest tests/test_ai/test_registry_v2.py::test_registry_execute_new_style -v` | PASSED | 不适用：新增测试 |
| 旧签名兼容 (INV-001) | test_registry.py::test_execute_tool | `pytest tests/test_ai/test_registry.py::test_execute_tool -v` | PASSED | 不适用：已有测试非本次新增 |
| RBAC 过滤 | test_tool_access_v2.py::test_rbac_filter | `pytest tests/test_ai/test_tool_access_v2.py::test_rbac_filter -v` | PASSED | 不适用：新增测试 |
| Capability 默认允许 (INV-002) | test_tool_access_v2.py::test_capability_default_allow | `pytest tests/test_ai/test_tool_access_v2.py::test_capability_default_allow -v` | PASSED | 不适用：已有测试非本次新增 |
| AgentEvent 8 类型 | test_schemas_v2.py::test_agent_event_new_types | `pytest tests/test_ai/test_schemas_v2.py::test_agent_event_new_types -v` | PASSED | 不适用：新增测试 |
| Transition 枚举 | test_schemas_v2.py::test_transition_enum | `pytest tests/test_ai/test_schemas_v2.py::test_transition_enum -v` | PASSED | 不适用：新增测试 |

### 验证清单自检

- ✅ ToolResult.to_dict() 省略 None 的 error/metadata key
- ✅ ToolContext 全部可选字段有默认值
- ✅ ToolSpec.is_read_only 默认 True, sensitivity 默认 "school"
- ✅ ToolRegistry.execute() 双签名：ToolContext → new path, **kwargs → legacy path
- ✅ ToolRegistry.get() 返回 ToolSpec 或 None
- ✅ ToolAccessResolver.resolve() 改为 sync，三层过滤逻辑不变
- ✅ INV-001: 旧 test_registry.py 9 tests 全绿（双签名兼容）
- ✅ INV-002: 空 capabilities 默认允许（test_capability_default_allow）
- ✅ Message = ChatMessage 别名，旧 test_schemas.py 7 tests 全绿
- ✅ Transition 枚举 7 个成员齐全
- ✅ 全量 test_ai/ 160 tests PASSED

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: ToolResult(success=True, data=None) — data 为 None 的成功结果
  运行命令: `pytest tests/test_ai/test_tool_context.py::test_tool_result_to_dict_omits_none -v`
  实际输出:
  ```
  PASSED
  ```
  结论: to_dict 正确省略 None 的 error 和 metadata key

- 新增文件的边界 case：
  构造输入: registry.execute("nonexistent", {}, ctx) — 未注册工具名 + 新签名
  运行命令: `pytest tests/test_ai/test_registry_v2.py::test_registry_execute_unknown_tool_new_style -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 新签名路径返回 ToolResult(success=False, error="Unknown tool: nonexistent")

- 字符串匹配/条件判断的假阴性：
  构造输入: resolver.resolve(specs, role="admin", enabled_modules=None, capabilities={}) — enabled_modules=None 跳过模块过滤
  运行命令: `pytest tests/test_ai/test_tool_access.py::test_enabled_modules_none_skips_module_filter -v`
  实际输出:
  ```
  PASSED
  ```
  结论: enabled_modules=None 正确跳过 Layer 2 过滤，所有工具可见
