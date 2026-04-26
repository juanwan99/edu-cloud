[edu-cloud] GPT Reviewer | 2026-04-05 08:29:52

## 审查报告: Plan Review (Gate 1)
结论: FAIL

原始输出 SHA256: `5640528f9b34e2a2871a1dc4c7aa481a233e60cc43b3fa80535a3c04390fb079`

---

### 第一段：测试充分性（Test Adequacy）

- Task 1-4 的测试契约完整（5 字段），且反例说明具体
- Task 5 的 `test_run_as_sub_agent_filters_tools` 断言过弱：条件守卫 `if call_args:` 和 `if request.tools:` 使得空 tools 场景可无声通过（F004）
- Task 6-8 缺少入口级（`/api/v1/ai/chat`）的 team dispatch 验证（F005）
- 整个计划缺少 Contract Pack（invariants/counter_examples/risk_modules/test_debt）（F003）

### 第二段：行为正确性（Behavioral Correctness）

- F001: Task 7 的预设 Team 工具名与代码库不匹配（21 个别名错误），test_tools_exist 必定 FAIL
- F002: Task 8 的 API 集成依赖 Task 6 未定义的 `_last_loop` 属性，且 `model_tier` int/str 类型不一致

### 第三段：未测试风险（Non-tested Risks）

- Team 执行模式下的多轮历史持久化（F002）
- Team fallback 后的 SSE 事件格式兼容性

### 发现清单

**F001** — verified
ID: F001
Severity: HIGH
Category: code-bug
Type: defect_fix
Before-behavior: 预设 Team 应使用 ToolRegistry 中实际注册的工具名
After-behavior: 21 个工具名使用了不存在的别名（exam_list→get_exam_list 等）
Evidence: plan:1622, plan:1650, exams.py:7, students.py:7, knowledge.py:34, homework.py:8
Impact: Task 7 test_tools_exist 不可达，Supervisor 路由后子 Agent 拿不到工具
Status: verified（已独立 grep 确认全部 39 个工具名与 plan 中 21 个不匹配）

**F002** — verified
ID: F002
Severity: HIGH
Category: code-bug
Type: defect_fix
Before-behavior: api/ai.py 当前使用 `loop.get_history()` 和 `model_tier: str` 记录 AgentRun
After-behavior: Task 8 依赖 `supervisor._last_loop`（不存在）、传 `strategy.tier`（int）给 `model_tier: str`
Evidence: plan:1920-1935, agent_profile_service.py:39, api/ai.py:229-268
Impact: history 持久化断裂，AgentRun 记录 model_tier 类型错误
Status: verified（已确认 record_run 签名为 model_tier: str，Supervisor 无 _last_loop 属性）

**F003** — verified
ID: F003
Severity: HIGH
Category: test-gap
Type: defect_fix
Before-behavior: 涉及路由策略/fallback/模型选择的高风险变更须附 Contract Pack
After-behavior: 计划缺少 contract_pack 全部段落
Evidence: plan 全文无 contract_pack/invariants/counter_examples/risk_modules/test_debt
Impact: 核心不变量（简单请求不误分派、team fallback 不破坏单循环、SSE 兼容）无可执行护栏
Status: verified

**F004** — verified
ID: F004
Severity: HIGH
Category: test-gap
Type: defect_fix
Before-behavior: 工具过滤测试应在隔离失效时稳定 FAIL
After-behavior: 条件守卫 `if call_args:` + `if request.tools:` 使空/无 tools 可无声通过
Evidence: plan:899-926
Impact: 权限过滤和工具隔离退化时测试不报错
Status: verified

**F005** — verified
ID: F005
Severity: MED
Category: test-gap
Type: defect_fix
Before-behavior: 核心行为变更应有入口级验证
After-behavior: Task 8 只测 team_registry=None 或 tier3，不覆盖 team dispatch SSE/history/fallback
Evidence: plan:1750-1874
Impact: 真实入口上的 team 路由行为无测试覆盖
Status: verified

**F006** — design-concern（不阻塞 PASS/FAIL）
ID: F006
Severity: MED
Category: design-concern
Type: behavior_change
Before-behavior: 设计文档要求 AgentTeam 带 state_class（ExamAnalysisState 等 typed state）
After-behavior: 计划降为通用 SharedState + 无类型 dict key
Evidence: design:71, design:121, plan:647
Impact: 接口隔离削弱，Phase 2/3 typed state 扩展失去落点
Status: verified

### Round 2 结果（2026-04-05 08:45）

- F001: ✅ 通过（工具名已全部对齐）
- F002: ✅ 通过（Supervisor 暴露 get_history/model_tier/dispatched_team）
- F003: ❌ Contract Pack 字段名不符 schema → R3 修复
- F004: ✅ 通过（强断言，去掉条件守卫）
- F005: ❌ 测试仍调 supervisor.handle() 非真实 API → R3 修复

### Round 3 结果（2026-04-05 09:01）

- F003: ✅ 通过（schema 完全对齐，semantic_regression 已补）
- F005: contested → **resolved-false-positive**
  GPT 检查了 ai.py 当前代码发现"仍创建 AgentLoop"和"test 文件不存在"。
  但这是 Plan Review 而非 Code Review——计划中 Task 8 Step 1b 包含完整的
  test_api_supervisor_integration.py 内容（POST /api/v1/ai/chat 真实端点），
  Step 3 描述了 AgentLoop→Supervisor 的替换。执行后才会落地到代码。

### 最终结论：PASS（F001-F004 verified-fixed, F005 contested→false-positive, F006 approved）

### 行为变更审批记录

| Finding ID | 行为变更摘要 | 用户决定 | 理由 |
|-----------|-------------|---------|------|
| F006 | 将设计文档的 typed state 降为通用 SharedState | approved | Phase 1 用通用 SharedState，Phase 2 再加类型化 |
