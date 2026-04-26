[edu-cloud] Executor→Reviewer | 2026-04-05 10:51:19

## 审查交接单: Task 1-9

计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-orchestration-plan.md

### 逐 Task 自审

- T1: AgentSpec dataclass + select_slot → commit bf4c545, 12 tests ✅
- T2: SharedState 容器 → commit 0d189ae, 7 tests ✅
- T3: ToolRegistry.filter_by_names() → commit 5133dee, 6 tests + 31 regression ✅
- T4: AgentTeam + TeamRegistry + TeamExecutor → commit 2c9782a, 12 tests ✅
- T5: AgentLoop.run_as_sub_agent() → commit 0b48cdb, 4 tests + 381 AI regression ✅
- T6: Supervisor 核心 → commit 4c73a84, 6 tests ✅
- T7: 预设 Team (edu_data/knowledge/homework) → commit 0451c5d, 5 tests (30 tools verified) ✅
- T8: API 集成 Supervisor → commit abccc79, 4 backward compat tests + 1324 全量 ✅
- T9: 全量回归验证 → 396 AI tests + 1324 全量 PASS ✅

### 预审自检

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| AgentSpec 创建 | test_agent_spec.py::test_create_basic | `pytest tests/test_ai/test_agent_spec.py -v` | 12 passed | 不适用：新增模块 |
| SharedState 读写 | test_shared_state.py::test_set_and_get | `pytest tests/test_ai/test_shared_state.py -v` | 7 passed | 不适用：新增模块 |
| filter_by_names | test_registry_filter.py::test_filter_subset | `pytest tests/test_ai/test_registry_filter.py -v` | 6 passed | 不适用：新增方法 |
| TeamExecutor 顺序 | test_agent_team.py::test_sequential_execution | `pytest tests/test_ai/test_agent_team.py -v` | 12 passed | 不适用：新增模块 |
| 工具过滤 | test_agent_loop_subagent.py::test_run_as_sub_agent_filters_tools | `pytest tests/test_ai/test_agent_loop_subagent.py -v` | 4 passed | 不适用：新增方法 |
| 简单请求单循环 | test_backward_compat.py::test_simple_message_returns_answer_event | `pytest tests/test_ai/test_backward_compat.py -v` | 4 passed | 不适用：新增测试 |
| Team 工具验证 | test_teams.py::test_tools_exist | `pytest tests/test_ai/test_teams.py -v` | 5 passed | 不适用：新增模块 |

### 验证清单自检

- ✅ 向后兼容：简单请求仍走单 AgentLoop，零破坏性
- ✅ SSE 事件格式不变：AgentEvent.to_dict() 输出与前端兼容
- ✅ 权限模型不变：ToolAccessResolver 在 Supervisor 之前执行
- ✅ 敏感度路由不变：SensitivityRouter 传入 Supervisor
- ✅ 会话管理不变：session_id + history + TTL 机制保持
- ✅ 审计不变：AuditLogger 在 api/ai.py 层面记录
- ✅ model_tier 为 str（supervisor.model_tier property）
- ✅ get_history() 替代 _last_loop（稳定公共 API）
- ✅ Team 工具名全部匹配 ToolRegistry（30 tools verified）
- ✅ 全量测试 1324 passed, 0 failed

### 自查

- 新增文件的边界 case：
  构造输入: AgentSpec(tools=[]) + SharedState 空 get + TeamExecutor 空 agents
  运行命令: `python -m pytest tests/test_ai/test_agent_spec.py tests/test_ai/test_shared_state.py tests/test_ai/test_agent_team.py -v -k "empty or missing"`
  实际输出:
  ```
  test_create_empty_tools PASSED
  test_get_missing_key_returns_default PASSED
  test_empty_agents PASSED
  test_list_teams_empty PASSED
  ```
  结论: 空值/缺失场景全部覆盖

- 字符串匹配/条件判断的假阴性：
  构造输入: select_slot 未知 complexity 类型
  运行命令: `python -m pytest tests/test_ai/test_agent_spec.py::TestSelectSlot::test_unknown_complexity_fallback -v`
  实际输出: PASSED (fallback to "primary")
  结论: 未知输入安全回退

### 语义回归自检（semantic_risk=true）

| Oracle ID | Type | 验证命令 | 实际输出 | 结论 |
|-----------|------|----------|----------|------|
| ORC-001 | temporal_trace | `python -m pytest tests/test_ai/test_backward_compat.py::TestBackwardCompat::test_simple_message_returns_answer_event -v` | PASSED — 简单请求产出 answer/done 事件，不经过 TeamExecutor | ✅ |
| ORC-002 | forbidden_strategy | `python -m pytest tests/test_ai/test_backward_compat.py::TestBackwardCompat::test_tier3_never_uses_team -v` | PASSED — tier3 未调用 _classify，mock_classify.assert_not_called() 通过 | ✅ |
| ORC-003 | temporal_trace | `python -m pytest tests/test_ai/test_supervisor.py::TestSupervisorDispatch::test_unknown_team_fallback -v` | PASSED — 不存在的 team fallback 到单循环，产出事件 | ✅ |
| ORC-004 | forbidden_strategy | 代码审查：Supervisor.handle() 中 team dispatch 路径只调用一次 _run_team，无链式 fallback 到其他 team | supervisor.py:107-115 仅匹配单个 team 或 fallback 到 _run_single，无循环/链式逻辑 | ✅ |

### 新增测试统计

| 文件 | 测试数 |
|------|--------|
| test_agent_spec.py | 12 |
| test_shared_state.py | 7 |
| test_registry_filter.py | 6 |
| test_agent_team.py | 12 |
| test_agent_loop_subagent.py | 4 |
| test_supervisor.py | 6 |
| test_teams.py | 5 |
| test_backward_compat.py | 4 |
| **合计** | **56** |
