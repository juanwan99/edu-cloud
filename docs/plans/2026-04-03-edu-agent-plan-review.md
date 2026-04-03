[edu-cloud] GPT Reviewer | 2026-04-03 16:20:02

## 审查报告: edu-agent Plan Review (Gate 1)
结论: FAIL

GPT 原始输出: `docs/plans/.codex-raw-plan_review-20260403-161956.log`
SHA256: `85c1e425247726890adb1273ee2d06687ff9d4abb2a2c3da476478d8f97a6a23`

---

### Finding 清单与三态标注

#### F001 — Registry 接口切换导致主干持续失绿
- **Severity:** HIGH
- **Category:** code-bug
- **Type:** defect_fix
- **Before-behavior:** 当前 AI 主链建立在 `registry.execute(..., **injected)` 旧契约上，现有 API、Agent 和测试都依赖该签名
- **After-behavior:** Task 2 明确接受 ToolRegistry 新签名落地后现有测试先失败，直到 Batch 6 再统一修复
- **Evidence:** plan L343-346 明确写出"旧 test_registry.py FAIL 也接受"；现有调用链 agent.py:114 用 `**injected`
- **Impact:** Batch 1-5 处于"计划允许主干失绿"状态，违背"each batch testable, committable"承诺

**Claude 三态: verified** ✅
GPT 判断正确。现有 `registry.execute()` 签名是 `(name, args, **kwargs)` (agent.py:114)，新签名改为 `(name, args, ctx: ToolContext)`。plan 明确说"旧测试 FAIL 也接受"，这确实违背了 bottom-up 原则。

**处置方案:** 保持 `registry.execute()` 同时支持新旧签名（adapter pattern），旧签名走 `**kwargs` 注入，新签名走 `ToolContext`。Batch 6 统一迁移后删除旧路径。每批结束全绿。

---

#### F002 — AgentLoop 实现与设计状态机脱节
- **Severity:** HIGH
- **Category:** code-bug
- **Type:** defect_fix
- **Before-behavior:** 设计要求 AgentLoop 含 CapabilityProbe → SensitivityRouter → plan 分支 → errors>3 降级 → memory extract → thinking/plan/task_update 事件
- **After-behavior:** Task 13 实现仅覆盖 answer/tool_calls/tool_result/done 基本循环
- **Evidence:** 设计 §3 L109-125 定义完整状态机；plan L2491-2587 的 AgentLoop 只有基本 while 循环，TaskPlanner 虽然实例化但未使用

**Claude 三态: verified** ✅
GPT 判断正确。Task 13 的 `AgentLoop.__init__` 虽然接收了 `ToolOrchestrator`/`ContextManager`/`TaskPlanner`，但 `run()` 方法没有调用 `_planner.maybe_plan()`，没有 SensitivityRouter 注入，没有 thinking/plan/task_update 事件发射。与设计文档描述的完整状态机有本质差距。

**处置方案:** Task 13 必须实现设计中定义的完整状态机：① plan 分支（tier≤2 时 maybe_plan）② SensitivityRouter 作为构造参数传入 ③ 发射 thinking/plan/task_update 事件 ④ error_count ≥ 3 时 tier 降级。

---

#### F003 — API SSE 测试是逻辑镜像，无入口级验证
- **Severity:** HIGH
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** `/api/v1/ai/chat` 行为变更应有 SSE 入口级契约验证
- **After-behavior:** Task 14 只测 `AgentEvent.to_dict()` 序列化，真正 API 迁移延后到 Batch 7
- **Evidence:** plan L2630-2648 测试只是 JSON 拼接循环；plan L2657 明确说 API 迁移 deferred

**Claude 三态: verified** ✅
GPT 判断正确。Task 14 的测试确实是逻辑镜像——即使 `/api/v1/ai/chat` 完全不发新事件类型，这些测试仍然通过。

**处置方案:** Task 14 重定义为"SSE 契约集成测试"——通过 AsyncClient 发请求到 `/api/v1/ai/chat`，验证 SSE 流中出现 thinking/plan/answer 等事件类型。需要 Batch 7 的 API wiring 提前到 Batch 5。

---

#### F004 — 全部 Task 缺少测试契约和边界条件段
- **Severity:** HIGH
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** 每个行为变更 Task 应有 `**测试契约:**`（5 字段）和 `**边界条件:**`（≥3 个）
- **After-behavior:** 整份 plan 没有这些结构化段落
- **Evidence:** grep `**测试契约:**` 和 `**边界条件:**` 在 plan 中均为空

**Claude 三态: verified** ✅
确认 plan 确实没有这些段落。plan 每个 Task 有内联测试代码，但没有按 review-templates.md 要求的 5 字段格式（入口/反例/边界/回归/命令）。

**处置方案:** 为每个行为变更 Task（T1-T14）补充 `**测试契约:**` 和 `**边界条件:**` 段。Batch 6 的机械迁移 Task 可共用一个测试契约模板。

---

#### F005 — 缺少 Contract Pack
- **Severity:** HIGH
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** plan 应包含结构化 `contract_pack:` YAML（invariants/counter_examples/risk_modules/test_debt）
- **After-behavior:** 当前 plan 完全没有 Contract Pack
- **Evidence:** grep `contract_pack:` / `invariants:` / `counter_examples:` 在 plan 中均为空

**Claude 三态: verified** ✅
确认缺失。

**处置方案:** 补充 Contract Pack，至少包含：
- invariants: ① 旧工具签名在迁移完成前持续可用 ② capability 缺省语义="无记录默认允许" ③ 39 tools 全部注册且通过 RBAC+Module+Capability 三重过滤 ④ SSE 事件流向前兼容
- counter_examples: ① 旧 `**kwargs` 签名被破坏但测试仍 pass（因为新测试覆盖了新签名）② capability 默认拒绝但无种子数据
- risk_modules: registry.py, tool_access.py, agent_loop.py, api/ai.py
- test_debt: 无

---

#### F006 — Capability 默认语义从"允许"变为"拒绝"（behavior_change）
- **Severity:** HIGH
- **Category:** code-bug
- **Type:** behavior_change（GPT 标注正确）
- **Before-behavior:** 当前 `_check_capabilities` 语义是"无记录默认允许"（`if key in caps and not caps[key]: return False` → 不在 caps 中 = 允许）
- **After-behavior:** Task 3 改为 `all(caps.get(req, False) ...)` → 不在 caps 中 = **拒绝**
- **Evidence:** 现有代码 tool_access.py:33-36 明确"无记录默认允许"；test_tool_access.py:65-73 测试 `test_capability_default_allow` 验证此语义；capability_service.py:124 注释"无记录 = 默认允许"

**Claude 三态: verified** ✅
这是 **behavior_change**，且命中红旗模式"改选择策略"。GPT 分类正确。

**处置方案:** Task 3 的 `_check_capabilities` 必须保持现有默认允许语义。修复代码：
```python
@staticmethod
def _check_capabilities(required, caps):
    for req in required:
        if req in caps and not caps[req]:
            return False
    return True
```
这与现有 tool_access.py 的逻辑一致。

---

#### F007 — AgentMemory 模型与 Alembic 迁移拆到不同批次
- **Severity:** MED
- **Category:** code-bug
- **Type:** defect_fix
- **Before-behavior:** 新增 ORM 表应同批接入 Alembic 模型发现链和迁移 smoke test
- **After-behavior:** Task 10 创建模型，Task 29 (Batch 7) 才做 migration
- **Evidence:** alembic/env.py:29 的固定导入列表不含 AgentMemory；test_alembic_migration.py:76 同理

**Claude 三态: verified** ✅
GPT 判断正确。如果 env.py 不 import AgentMemory，autogenerate 不会发现这张表。

**处置方案:** Task 10 增加步骤：① 在 alembic/env.py 添加 `from edu_cloud.models.agent_memory import AgentMemory` ② 更新 test_alembic_migration.py 的导入列表 ③ 生成 migration 文件。Task 29 删除。

---

#### F008 — Batch 7 破坏性操作无回滚路径
- **Severity:** MED
- **Category:** design-concern
- **Type:** defect_fix
- **Before-behavior:** 破坏性操作应有回滚路径
- **After-behavior:** Task 28 删除旧文件、Task 29 upgrade head，无 backout 说明
- **Evidence:** plan L2790 删除 6 个旧文件；plan L2826 upgrade head

**Claude 三态: verified** ✅
GPT 判断正确。虽然开发阶段无线上用户，但计划应说明回退策略。

**处置方案:** Task 28 前增加"回退检查点"步骤：① git tag 标记 pre-cutover ② 运行全量测试确认新旧共存正常 ③ 删除旧文件 ④ 再次全量测试。失败时 `git revert` 到 tag。Task 29 的 migration 需要验证 downgrade 路径。

---

### 行为变更审批记录

| Finding ID | 行为变更摘要 | 用户决定 | 理由 |
|-----------|-------------|---------|------|
| F006 | capability 默认语义从"无记录允许"变为"无记录拒绝" | **待确认** | 需用户单独审批 |

---

### 处置总结

| Finding | 状态 | 处置 |
|---------|------|------|
| F001 | verified | 修复：registry.execute() 支持新旧双签名 |
| F002 | verified | 修复：Task 13 实现完整状态机 |
| F003 | verified | 修复：Task 14 改为 SSE 入口级集成测试 |
| F004 | verified | 修复：补充测试契约+边界条件段 |
| F005 | verified | 修复：补充 Contract Pack |
| F006 | verified (behavior_change) | 修复：保持默认允许语义 |
| F007 | verified | 修复：migration 合入 Task 10 |
| F008 | verified | 修复：增加回退检查点 |

**下一步:** 修复全部 8 个 finding 后更新 plan，重新提交 Gate 1 审查（Round 2）。
