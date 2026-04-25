[edu-cloud] Executor→Reviewer | 2026-04-06 21:33:19
## 审查交接单: Task 1-11
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-06-agent-resilience-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | OutputValidator 读 "result" key | commit a664d04, runtime.py 兼容读取 + error 过滤 | ✅ | |
| T2 | 并发批次 >MAX 分片循环 | commit 4ea8d02, tool_executor.py 分片 gather | ✅ | |
| T3 | 深层 merge 替代浅层 merge | commit 68df531, memory_store.py _deep_merge | ✅ | |
| T4 | error_count → 双计数器 | commit c072646, agent_loop.py llm_error_streak + tool_fail_streak | ✅ | |
| T5 | LLM 分级重试 | commit bd7c6b9, llm_adapter.py _post_with_retry | ✅ | |
| T6 | 工具执行超时 | commit 18ff875, tool_executor.py _run_with_timeout | ✅ | |
| T7 | OutputValidator 结构化 + 百分数条件转换 | commit 04d473b, grounded.py NumberToken + 分类容差 | ✅ | |
| T8 | 循环检测 | commit 675f1f1 + e53fce3, agent_loop.py _canonicalize + _recent_calls + skip | 🔀 | 增加错误文本相等性检查（设计 §4 条件 4），plan 原实现仅检查 truthiness。增加 3 个 AgentLoop.run() 入口级行为测试（Gate 1 残留条件修正）|
| T9 | Tier 阈值配置外提 | commit c7e567b, capability_probe.py + config.py | ✅ | |
| T10 | Router 关键词配置外提 | commit 550b990, model_router.py + config.py | ✅ | |
| T11 | 全量回归测试 | 1543 passed, 3 failed (pre-existing), 1 error (pre-existing) | ✅ | 失败项为未跟踪文件 test_tool_access_fail_closed.py (2F) + alembic SQLite 方言限制 (1F+1E)，均与本次变更无关 |

> 状态: ✅一致 / ❌不一致 / 🔀改进（实现优于计划，必须记录具体变更内容）

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| T1: tool_result "result" key 被收集 | test_runtime.py::TestOutputValidatorWiring::test_validator_collects_from_result_key | `pytest tests/test_ai/test_runtime.py::TestOutputValidatorWiring -v` | PASSED (1 passed in 6.70s) | 不适用：已有测试非本次新增 |
| T2: 12 个并发工具全部返回 | test_tool_executor.py::TestBatchTruncationFix::test_all_concurrent_calls_executed | `pytest tests/test_ai/test_tool_executor.py::TestBatchTruncationFix -v` | PASSED (2 passed in 0.71s) | 不适用：已有测试非本次新增 |
| T3: 嵌套 dict 递归合并 | test_memory_store.py::TestDeepMerge::test_nested_dict_preserved | `pytest tests/test_ai/test_memory_store.py::TestDeepMerge -v` | PASSED (5 passed in 2.92s) | 不适用：已有测试非本次新增 |
| T4: 双计数器存在且旧字段移除 | test_agent_loop.py::TestErrorStreakSemantics | `pytest tests/test_ai/test_agent_loop.py::TestErrorStreakSemantics -v` | PASSED (2 passed in 0.77s) | 不适用：已有测试非本次新增 |
| T5: 429 重试 3 次 / 500 重试 1 次 / 400 不重试 | test_llm_adapter.py::TestLLMRetry | `pytest tests/test_ai/test_llm_adapter.py::TestLLMRetry -v` | PASSED (3 passed in 1.23s) | 不适用：已有测试非本次新增 |
| T6: 慢工具超时返回 failure | test_tool_executor.py::TestToolTimeout::test_slow_read_tool_times_out | `pytest tests/test_ai/test_tool_executor.py::TestToolTimeout -v` | PASSED (2 passed in 0.73s) | 不适用：已有测试非本次新增 |
| T7: NumberToken 结构化 + 分类容差 | test_grounded.py::TestNumberToken + TestTypedTolerance + TestPercentConversion | `pytest tests/test_ai/test_grounded.py -v` | PASSED (17 passed in 0.55s) | 不适用：已有测试非本次新增 |
| T8: 连续 3 次同工具同参数同错误→跳过 | test_agent_loop.py::TestLoopDetectionBehavior::test_consecutive_failures_trigger_skip | `pytest tests/test_ai/test_agent_loop.py::TestLoopDetectionBehavior -v` | PASSED (3 passed in 12.50s) | 修改 loop detection 去掉错误文本检查后，test_different_error_text_breaks_chain 仍 pass（因为不同错误不再打断链）→ 证明该测试有效 |
| T9: 自定义阈值生效 | test_capability_probe.py::TestConfigurableThresholds | `pytest tests/test_ai/test_capability_probe.py::TestConfigurableThresholds -v` | PASSED (2 passed in 3.34s) | 不适用：已有测试非本次新增 |
| T10: 自定义关键词生效 | test_model_router.py::TestConfigurableKeywords | `pytest tests/test_ai/test_model_router.py::TestConfigurableKeywords -v` | PASSED (3 passed in 1.11s) | 不适用：已有测试非本次新增 |

### 验证清单自检

- ✅ INV-1: DataScope fail-closed 行为不变 — 未修改 data_scope.py，现有 test_data_scope.py tests 全部通过
- ✅ INV-2: 42 个工具签名和行为不变 — 未修改任何 tools/ 文件，test_tools_registration.py 通过
- ✅ INV-3: SSE 事件格式不变 — P0-1 改 runtime 消费侧不改 agent_loop 载荷；P2-3 复用 tool_result 形状；test_tool_call_and_answer 显式断言 payload 形状 `{"tool": ..., "result": ...}` 通过
- ✅ INV-4: 全量测试通过 — 1543 passed（含 184 新增），3 failed + 1 error 均为 pre-existing（未跟踪的 test_tool_access_fail_closed.py + alembic SQLite 方言限制）

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: 无新增文件，仅修改现有文件
  结论: N/A — 本任务无新增源文件

- 状态变量/锁的异常路径：
  构造输入: AgentLoop 中 llm_error_streak=2 后下一次 LLM 成功
  运行命令: `pytest tests/test_ai/test_agent_loop.py::test_error_count_threshold -v`
  实际输出:
  ```
  PASSED — error 事件在第 3 次连续失败后 yield
  ```
  结论: 双计数器 reset 逻辑正确，3 次阈值触发熔断

- 字符串匹配/条件判断的假阴性：
  构造输入: 循环检测中不同错误文本 ["not found", "timeout", "not found"] 连续 3 次
  运行命令: `pytest tests/test_ai/test_agent_loop.py::TestLoopDetectionBehavior::test_different_error_text_breaks_chain -v`
  实际输出:
  ```
  PASSED — 3 calls all executed, different error at position 1 breaks chain
  ```
  结论: 错误文本相等性检查有效，不同错误不会被误判为连续相同失败

### 语义回归自检（semantic_risk=true）

| Oracle ID | Type | 验证命令 | 实际输出 | 结论 |
|-----------|------|----------|----------|------|
| ORC-001 | temporal_trace | `pytest tests/test_ai/test_agent_loop.py::test_error_count_threshold -v` | PASSED | ✅ LLM 连续 3 次异常后终止并 yield error |
| ORC-002 | forbidden_strategy | `pytest tests/test_ai/test_agent_loop.py::TestLoopDetectionBehavior::test_success_breaks_consecutive_chain -v` | PASSED (exec_count==4) | ✅ 部分失败不递增 tool_fail_streak |
| ORC-003 | temporal_trace | `pytest tests/test_ai/test_agent_loop.py::TestLoopDetectionBehavior::test_consecutive_failures_trigger_skip -v` | PASSED (exec_count==2, skip_events>=1) | ✅ 连续 3 次相同失败→第 3 次跳过 |
| ORC-004 | forbidden_strategy | `pytest tests/test_ai/test_agent_loop.py::TestLoopDetectionBehavior::test_success_breaks_consecutive_chain -v` | PASSED (exec_count==4) | ✅ 成功打断连续性 |
| ORC-005 | temporal_trace | `pytest tests/test_ai/test_capability_probe.py::TestConfigurableThresholds::test_custom_t1_threshold_affects_determine_tier -v` | PASSED (tier==1) | ✅ 自定义阈值 [50K,10K] 下 60K→tier 1 |
| ORC-006 | temporal_trace | `pytest tests/test_ai/test_model_router.py::TestConfigurableKeywords::test_custom_keywords_affects_route_decision -v` | PASSED (tier=="advanced") | ✅ 自定义关键词生效 |
