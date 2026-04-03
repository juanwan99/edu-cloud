[edu-cloud] Executor→Reviewer | 2026-04-03 19:45:28
## 审查交接单: Task 9-12 (Batch 4: Intelligence Layer + Prompts)
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T9 | 创建 ContextManager + TokenCounter | commit 64b7c92, 新建 context_manager.py + 7 tests | ✅ | — |
| T10 | 创建 AgentMemory ORM + SessionMemoryExtractor + Alembic migration | commit 589f80d, 新建 agent_memory.py + session_memory.py + migration + 4 tests | 🔀 | Alembic autogenerate 产生了错误的 homework 表删除，已手工清理只保留 agent_memories 创建 |
| T11 | 创建 TaskPlanner (LLM 驱动分解 + 拓扑调度) | commit d949f28, 新建 task_planner.py + 5 tests | ✅ | — |
| T12 | 创建 prompts.py (tier-aware system prompt) | commit c63f6bc, 新建 prompts.py + 4 tests | 🔀 | plan 中的中文嵌套引号导致 SyntaxError，改用单引号字符串 |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| TokenCounter 中文估算 | test_context_manager.py::test_token_counter_chinese | `pytest tests/test_ai/test_context_manager.py::test_token_counter_chinese -v` | PASSED | 不适用：新增测试 |
| compact 保留 system+recent | test_context_manager.py::test_compact_preserves_system_and_recent | `pytest tests/test_ai/test_context_manager.py::test_compact_preserves_system_and_recent -v` | PASSED | 不适用：新增测试 |
| AgentMemory ORM 列完整 | test_session_memory.py::test_agent_memory_model_has_fields | `pytest tests/test_ai/test_session_memory.py::test_agent_memory_model_has_fields -v` | PASSED | 不适用：新增测试 |
| SessionMemoryExtractor 解析 JSON | test_session_memory.py::test_extract_returns_memories | `pytest tests/test_ai/test_session_memory.py::test_extract_returns_memories -v` | PASSED | 不适用：新增测试 |
| Bad JSON 不崩溃 | test_session_memory.py::test_extract_handles_bad_json | `pytest tests/test_ai/test_session_memory.py::test_extract_handles_bad_json -v` | PASSED | 不适用：新增测试 |
| maybe_plan null → None | test_task_planner.py::test_maybe_plan_returns_none_for_simple | `pytest tests/test_ai/test_task_planner.py::test_maybe_plan_returns_none_for_simple -v` | PASSED | 不适用：新增测试 |
| schedule 拓扑序 | test_task_planner.py::test_schedule_topological_order | `pytest tests/test_ai/test_task_planner.py::test_schedule_topological_order -v` | PASSED | 不适用：新增测试 |
| Tier 1/2 有计划指令 | test_prompts.py::test_teacher_prompt_tier1_has_plan_instruction | `pytest tests/test_ai/test_prompts.py::test_teacher_prompt_tier1_has_plan_instruction -v` | PASSED | 不适用：新增测试 |
| Tier 3 无计划指令 | test_prompts.py::test_teacher_prompt_tier3_no_plan_instruction | `pytest tests/test_ai/test_prompts.py::test_teacher_prompt_tier3_no_plan_instruction -v` | PASSED | 不适用：新增测试 |

### 验证清单自检

- ✅ TokenCounter: 中文 1.5 token/字, 英文 0.4 token/字
- ✅ should_compact: threshold = context_window - 13K buffer - 20K summary
- ✅ compact: 保留 system + summary + 最近 4 轮(8条消息)
- ✅ compact: LLM 失败时 fallback 到简略摘要
- ✅ AgentMemory: 8 列 + id + timestamps
- ✅ SessionMemoryExtractor: 解析 JSON/markdown 包裹 JSON/非 JSON
- ✅ TaskPlanner: tier=3 跳过规划，不调 LLM
- ✅ TaskPlanner: maybe_plan 解析 {"plan": null} → None
- ✅ TaskPlanner: schedule 拓扑排序 + 死锁检测
- ✅ Prompts: tier<=2 有计划指令，tier==1 有自省指令
- ✅ Prompts: ROLE_CN 映射 8 个角色
- ✅ Alembic migration: upgrade/downgrade 通过
- ✅ 全量 test_ai/ 222 tests PASSED

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: messages 只有 2 条（system + user）
  运行命令: `python -c "import asyncio; from edu_cloud.ai.context_manager import ContextManager; from edu_cloud.ai.schemas import Message; cm = ContextManager(); r = asyncio.run(cm.compact([Message(role='system', content='hi'), Message(role='user', content='test')], None)); print(len(r))"`
  实际输出:
  ```
  2
  ```
  结论: 少于 3 条消息时原样返回，不 compact

- 字符串匹配/条件判断的假阴性：
  构造输入: LLM 返回 markdown 包裹的 JSON（```json\n[...]\n```）
  运行命令: `python -c "from edu_cloud.ai.session_memory import SessionMemoryExtractor; e = SessionMemoryExtractor._parse('\`\`\`json\n[{\"type\":\"finding\",\"content\":\"test\"}]\n\`\`\`'); print(len(e), e[0].memory_type)"`
  实际输出:
  ```
  1 finding
  ```
  结论: markdown 代码块包裹被正确剥离

- 状态变量/锁的异常路径：
  构造输入: 循环依赖 A→B→A
  运行命令: `python -c "from edu_cloud.ai.task_planner import TaskPlanner, Plan, Task; p = TaskPlanner(); plan = Plan(goal='test', tasks=[Task(id='0', description='a', depends_on=['1']), Task(id='1', description='b', depends_on=['0'])]); print([t.id for t in p.schedule(plan)])"`
  实际输出:
  ```
  ['0', '1']
  ```
  结论: 死锁检测触发，yield 所有 remaining tasks（不无限循环）
