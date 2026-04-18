<!-- pre-takeover: archived for history, not active spec -->
[edu-cloud] GPT Reviewer (Integration) | 2026-04-04 10:28:01
## 集成审查报告: edu-agent T4 (7 Batches, 30 Tasks)

结论: PASS (GPT FAIL → 修复 3 finding → 全量 1124 tests 通过)

### 变更理解

edu-agent 替换 edu-cloud 旧 ReAct Agent，基于 Claude Code 架构裁剪。7 个 batch 实现：
- B1: ToolContext/ToolResult/ToolRegistry/ToolSpec 基础数据结构
- B2: LLMProxyAdapter + CapabilityProbe + SensitivityRouter
- B3: ToolExecutor/ToolOrchestrator（并行/串行执行引擎）
- B4: ToolAccessResolver（RBAC ∩ Module ∩ Capability 三层过滤）
- B5: AgentLoop（plan→tool exec→answer 状态机）+ Anonymizer + SessionMemory
- B6: 39 个工具从旧签名迁移到 (input, ctx) → ToolResult
- B7: api/ai.py pipeline 替换 + 旧模块删除

### 对抗性审查

GPT 独立验证了 5 个跨批次接口 + 4 个不变量 + 全量测试 + 删除代码残留检查。
发现 3 个 code-bug，全部 verified 并修复。

### 发现清单

| ID | Severity | Category | Type | 问题 | 修复 commit | 状态 |
|----|----------|----------|------|------|------------|------|
| F001 | HIGH | code-bug | defect_fix | LLM URL 双重拼接：config 含 /v1/chat/completions + adapter 再追加 | cb2c800 | resolved-correct |
| F002 | HIGH | code-bug | defect_fix | Session 隔离缺失：_sessions 无 owner，任意用户可列举/删除他人会话 | cb2c800 | resolved-correct |
| F003 | MED | code-bug | defect_fix | Session TTL 未生效：AI_SESSION_TTL 定义但无清理逻辑 | cb2c800 | resolved-correct |

### 跨批次接口一致性核验（GPT 独立确认）

| 接口 | 涉及 Batch | 结果 |
|------|-----------|------|
| ToolContext ↔ all tools ↔ ToolExecutor | B1/B3/B6 | ✅ 一致 |
| ToolRegistry/ToolSpec ↔ ToolAccessResolver ↔ AgentLoop | B1/B4/B5 | ✅ 一致 |
| LLMAdapter ↔ AgentLoop (LLMRequest/LLMResponse) | B2/B5 | ✅ 一致（F001 URL 已修） |
| CapabilityProbe ↔ AgentLoop (LoopStrategy) | B2/B5 | ✅ 一致 |
| SensitivityRouter ↔ AgentLoop (channel selection) | B2/B5 | ✅ 一致 |
| Anonymizer ↔ AgentLoop ↔ api/ai.py | B5/B7 | ✅ 一致 |
| AgentLoop ↔ api/ai.py (SSE + sessions) | B5/B7 | ✅ 一致（F002/F003 已修） |

### 不变量保持

| INV | 描述 | 状态 |
|-----|------|------|
| INV-001 | registry.py 双签名兼容 | ✅ GPT 确认 |
| INV-002 | tool_access.py 三层过滤 | ✅ GPT 确认 |
| INV-003 | sensitivity_router.py 双通道 (student locked) | ✅ GPT 确认 |
| INV-004 | SSE 事件格式向后兼容 | ✅ GPT 确认 |

### 删除代码核查

GPT 执行 `grep -r "from edu_cloud.ai.agent import|from edu_cloud.ai.intent_resolver import|from edu_cloud.ai.model_router import" src/` → NO_MATCH。无残留 import。

### 测试统计

- 全量: 1124 passed
- AI 子集: 214 passed
- 工具注册: 39 tools 确认
