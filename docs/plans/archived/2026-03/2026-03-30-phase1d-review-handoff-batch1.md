[edu-cloud] Executor→Reviewer | 2026-03-30 13:24:57
## 审查交接单: Task 1-9
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-30-phase1d-agent-instantiation-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | ToolSpec dataclass + Registry 升级 | commit 0b313e1, ToolSpec 7 字段 + register() 扩展 + get_all_specs() + 向后兼容 | ✅ | |
| T2 | AgentProfile + AgentRun 模型 | commit f6b0589, 2 个 ORM 模型 + UniqueConstraint | ✅ | |
| T3 | AgentProfileService + get_or_create | commit 73ef248, get_or_create 幂等 + record_run | ✅ | |
| T4 | ToolAccessResolver 三重过滤 | commit 148170a, RBAC→Module→Capability 三层 + 7 测试 | ✅ | |
| T5 | IntentResolver 规则+LLM | commit 49f071d, 9 domain 规则引擎 + LLM fallback + 双兜底 | ✅ | |
| T6 | ModelRouter + LLMSlot tier + LLM Factory | commit 54df272, tier 字段 + 三级 fallback + 5 规则 | ✅ | |
| T7 | Agent Pipeline 集成 | commit 4b320f2, 删除 ROLE_TOOL_CATEGORIES + Pipeline 插入 ai.py + Agent.run() tools 参数 | ✅ | |
| T8 | 31 工具元数据迁移 | commit 1226d6f, 31/31 工具有 domain + allowed_roles + parent 隔离 | ✅ | |
| T9 | Alembic + CLAUDE.md | commit 983b44d, migration 含 agent_profiles/agent_runs/llm_slots.tier | ✅ | |

### 预审自检（送审前必填，无此表不允许提交 codex-review）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） |
|---------------|------------------|---------|------------------------------|
| ToolSpec 元数据字段 | test_registry_upgrade.py::test_toolspec_has_metadata_fields | `pytest tests/test_ai/test_registry_upgrade.py -v` | pass, 5 passed in 0.35s |
| AgentProfile 唯一约束 | test_agent_profile_service.py::test_agent_profile_unique_constraint | `pytest tests/test_services/test_agent_profile_service.py -v` | pass, 7 passed in 4.68s |
| 三重过滤组合 | test_tool_access.py::test_triple_filter_combined | `pytest tests/test_ai/test_tool_access.py -v` | pass, 7 passed in 0.89s |
| Intent 规则匹配 | test_intent_resolver.py::test_rule_match_chinese_exam | `pytest tests/test_ai/test_intent_resolver.py -v` | pass, 7 passed in 0.92s |
| ModelRouter tier 选择 + LLM factory | test_model_router.py::test_high_risk_selects_advanced | `pytest tests/test_ai/test_model_router.py -v` | pass, 7 passed in 4.38s |
| Pipeline 端到端 | test_agent_pipeline.py::test_pipeline_end_to_end | `pytest tests/test_ai/test_agent_pipeline.py -v` | pass, 4 passed |
| 31 工具元数据完整 | 内联验证脚本 | `python -c "from edu_cloud.ai.tools import *; ..."` | pass, Total: 31, Missing: [], Parent leak: [] |
| tier=NULL 兼容 | test_model_router.py::test_tier_null_compat | `pytest tests/test_ai/test_model_router.py::test_tier_null_compat -v` | pass |

### 验证清单自检
- ✅ ToolSpec 包含 7 个元数据字段（module_code, domain, requires_capabilities, risk_level, allowed_roles, category, func）
- ✅ register() 新增可选参数，旧调用方式不受影响（test_register_backward_compat passed）
- ✅ get_schemas(categories=...) 向后兼容（test_get_schemas_still_works passed）
- ✅ AgentProfile 有 UniqueConstraint(owner_user_id, school_id)
- ✅ get_or_create 幂等（test_get_or_create_returns_existing passed）
- ✅ 三层过滤独立可测（7 个 test_tool_access 测试）
- ✅ 9 个 domain 关键词覆盖中英文（test_intent_resolver 7 passed）
- ✅ LLM fallback + 全工具集兜底（test_resolve_fallback_to_all passed）
- ✅ ModelRouter 规则优先级清晰（high risk > 3域 > 复杂组合 > standard）
- ✅ LLM factory 三级 fallback（学校→平台→.env）
- ✅ ROLE_TOOL_CATEGORIES 已删除（grep 确认无残留）
- ✅ Pipeline 在 Agent.run() 之前执行
- ✅ 现有 AI 测试仍通过（131 AI tests passed）
- ✅ 31 个工具全部有 domain（非 "general"）
- ✅ parent 角色看不到非 profile 域工具
- ✅ Migration 包含 agent_profiles + agent_runs + llm_slots.tier
- ✅ CLAUDE.md 同步（新模型、新组件、表计数更新）
- ✅ 308 tests passed（AI + services + alembic migration 完整覆盖）

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: ToolAccessResolver.resolve(all_specs=[], role="platform_admin", enabled_modules=set(), capabilities={})
  运行命令: `python -m pytest tests/test_ai/test_tool_access.py::test_empty_specs -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 空工具集输入正确返回空列表

- 字符串匹配/条件判断的假阴性：
  构造输入: IntentResolver.resolve_by_rules("你好，今天天气怎么样？") — 无关键词消息
  运行命令: `python -m pytest tests/test_ai/test_intent_resolver.py::test_rule_no_match -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 无匹配时正确返回 None，触发 LLM fallback 路径

- Pipeline 异常兜底：
  构造输入: IntentResolver.resolve 抛 RuntimeError
  运行命令: `python -m pytest tests/test_ai/test_agent_pipeline.py::test_pipeline_fallback_on_error -v`
  实际输出:
  ```
  PASSED
  ```
  结论: Pipeline 异常时 fallback 到全工具集 + standard 模型

使用 codex-review skill 进行 GPT 代码审查。
