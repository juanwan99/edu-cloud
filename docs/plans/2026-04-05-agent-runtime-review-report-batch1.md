[edu-cloud] GPT Reviewer | 2026-04-06 10:30:00
<!-- anchor: finding-classification -->
## 审查报告: Task 1-9 (Round 1)
结论: FAIL → Round 2 修复

### GPT Code Review R1 结论: FAIL

原始输出: `docs/plans/.codex-code-review-raw.log`
SHA256: `f9a02d115ebecdfda84f69977df0b2d707c3fb1b2a47760b16cf153593867b40`

### 第一段：测试充分性（Test Adequacy）

- plan 中声明的边界条件基本有对应测试（DataSource/OutputValidator/ModelRouter 各 8 tests）
- AgentRuntime 层测试偏弱：仅验证"有事件产出"，未验证核心编排链（validator 接入、history 回写、adapter 清理）
- Task 8 缺少入口级回归测试：SSE shape 有测试，但 history 持久化、profile recording、anonymizer 复用无专项测试
- GPT 指出删除 runtime 核心逻辑后现有测试仍可能通过 → test-gap HIGH

### 变更理解

本批次将 Agent 从 HTTP 请求附属品升级为独立运行时：
- Task 1-3: 新增 DataSource（数据溯源标签）、OutputValidator（防幻觉后置校验）、ModelRouter（双层模型路由）
- Task 4: AgentRuntime 统一调度器，封装 model routing → probe → tools → prompt → supervisor 全链路
- Task 5-7: Grounded prompt 规则 + Worker/CLI 入口
- Task 8: api/ai.py 瘦身，chat 端点从直接构造 Supervisor 改为调用 AgentRuntime.run()
- Task 9: 全量回归验证（1458 passed，3+1 pre-existing）

### 对抗性审查

GPT 独立验证了以下攻击面：
1. **OutputValidator 空转**: runtime.py 创建了 validator 但从未调用 → answer 事件中的矛盾数值直接透传
2. **多轮对话降级**: history 回写路径被注释掉 → 复用 session_id 的对话丢失上下文
3. **遥测污染**: record_run 写入静态占位值 → AgentRun 表数据全部失真
4. **资源泄漏**: adapter 无 close 路径 → httpx.AsyncClient 累积
5. **dual-model 不可达**: HTTP 入口硬编码空 slots → ModelRouter 在主入口永远返回 standard

### 发现清单

| ID | Severity | Category | Type | Before-behavior | After-behavior | Evidence | Status |
|----|----------|----------|------|-----------------|----------------|----------|--------|
| F001 | HIGH | code-bug | defect_fix | OutputValidator 已实例化但 run() 未调用 | 应在 answer 事件前校验 | runtime.py:59,157 | verified → 已修复 |
| F002 | HIGH | code-bug | defect_fix | history 回写被注释为 TODO | 应持久回写多轮历史 | ai.py:184,195 | verified → 已修复 |
| F003 | HIGH | code-bug | defect_fix | slots 硬编码空，ModelRouter 不可达 | 应传入真实 slot | ai.py:162 | accepted-risk |
| F004 | MED | code-bug | defect_fix | record_run 用静态占位值 | 应记录真实执行数据 | ai.py:199 | verified → 已修复 |
| F005 | MED | code-bug | defect_fix | adapter 无 close 路径 | 应在 finally 关闭 | runtime.py:89,157 | verified → 已修复 |
| F006 | HIGH | test-gap | defect_fix | 关键契约无入口级测试 | 应补反例驱动测试 | test_runtime.py:52 | verified → 已修复 |

### F003 Accepted Risk 理由

- **reason**: dual-model 的 DB 层（LLMSlot CRUD + school settings 开关查询）需要独立设计任务，不在 Agent Runtime 架构升级范围内。HTTP 层始终走 `ai-chat` slot（与重构前行为完全一致，不是回退）。ModelRouter 在 Worker/CLI 入口通过 AgentContext 传参可达。
- **deadline**: 下个 Phase（dual-model DB wiring）时解决

### Round 2 修复摘要

F001/F002/F004/F005 已在 commit 中修复，F006 新增 4 个测试覆盖。待 R2 重审确认。
