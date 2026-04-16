[edu-cloud] GPT+Claude Reviewer | 2026-04-04 09:12:56
## 审查报告: Task 15-30 (Batch 6-7) — Migration+Integration

结论: PASS (R1 FAIL → R2 FAIL → R3 FAIL → Planner 补充修复 → 全部关闭)

---

### 审查轨迹

| Round | 结论 | Findings | 处置 |
|-------|------|----------|------|
| R1 | FAIL | F001 code-bug, F002 behavior_change, F003 code-bug, F004 test-gap, F005 test-gap (5 HIGH) + P001 design-concern | R2 修复 |
| R2 | FAIL | F005 still-open (2/17 工具缺测试), NEW-F006 test-gap (anonymizer 假绿) | R3 修复 |
| R3 | FAIL | F005 still-open (get_class_scores 缺成功路径测试), NEW-F006 关闭 | Planner 补充修复 |
| R3+ | PASS | Planner 补 get_class_scores success+empty 测试, 反证验证通过 | 全部关闭 |

---

### 变更理解

Batch 6 将 39 个工具从旧 `**kwargs` 签名迁移到 `(input: dict, ctx: ToolContext) -> ToolResult`，Batch 7 将 `api/ai.py` 的旧 Agent pipeline（IntentResolver → ModelRouter → Agent.run）替换为新 AgentLoop pipeline（CapabilityProbe → ToolAccessResolver → SensitivityRouter → AgentLoop.run），并删除 6 个旧模块文件。

### 对抗性审查

GPT R1 构造了三个对抗场景均确认缺陷存在：
1. `enabled_modules` 未赋值场景（F001）— fallback 路径 UnboundLocalError
2. 同 session_id 连续请求场景（F002）— 多轮会话丢失
3. 含学生姓名的工具返回场景（F003）— anonymizer 链路断裂

R3+ Planner 补充反证：删除 `get_class_scores` 核心聚合逻辑 → `test_get_class_scores_success` FAILED (`assert 0 == 2`)。

### 发现清单

### R1 原始发现（GPT 独立审查）

| ID | Severity | Category | Type | Before-behavior | After-behavior |
|----|----------|----------|------|----------------|----------------|
| F001 | HIGH | code-bug | defect_fix | pipeline 初始化失败时进入 fallback 降级 | enabled_modules 未赋值导致 fallback 触发 UnboundLocalError |
| F002 | HIGH | code-bug | behavior_change | 同 session_id 多轮请求继承历史消息 | AgentLoop 每次从空消息开始，多轮语义丢失 |
| F003 | HIGH | code-bug | defect_fix | 工具结果脱敏后进 LLM，回答反脱敏后给用户 | ctx.anonymizer 未被消费，学生实名直接进 LLM |
| F004 | HIGH | test-gap | defect_fix | 应有 HTTP 入口级 SSE 合同测试 | SSE 测试停留在 AgentLoop 层 |
| F005 | HIGH | test-gap | defect_fix | 迁移工具应有执行级测试 | 17 个工具无执行级覆盖 |
| P001 | MED | design-concern | defect_fix | diff 范围应只含 edu-agent 改动 | 混入 card-editor 等非 AI 改动 |

### 行为变更审批记录

| Finding ID | 行为变更摘要 | 用户决定 | 理由 |
|-----------|-------------|---------|------|
| F002 | 多轮会话退化为单轮 | rejected（必须修复） | 多轮会话是核心功能 |

---

### Finding 处置总表

| ID | 修复 commit | 状态 | 关闭轮次 |
|----|------------|------|---------|
| F001 | R2 — api/ai.py fallback 死路径修复 | resolved-correct | R2 |
| F002 | R2 — agent_loop.py history 参数 + API _sessions | resolved-correct | R2 |
| F003 | R2 — agent_loop.py anonymize/deanonymize 接线 | resolved-correct | R2 |
| F004 | R2 — test_ai_api_v2.py SSE contract test | resolved-correct | R2 |
| F005 (15/17) | b264459 — 15 工具执行级测试 | resolved-correct | R2 |
| F005 (student_scores) | f340227 — success+not_found 测试 | resolved-correct | R3 |
| NEW-F006 | ec38aa4 — anonymizer 消息内容断言 | resolved-correct (GPT 反证确认) | R3 |
| F005 (class_scores) | 467eed9 — success+empty 测试 | resolved-correct (Planner 自审反证) | R3+ |
| P001 | 记入 design.md §待处置 | deferred (不阻塞) | R1 |

### 反证验证记录

| 测试 | 反证方法 | 结果 |
|------|---------|------|
| test_get_class_scores_success | 删除 student_totals 聚合+排序+结果组装 | FAILED: `assert 0 == 2` |
| test_agentloop_anonymizer_integration | 删除 anonymize() 调用 | FAILED: `S001 not found, got 张三` |
| test_get_student_scores_success | 删除核心取数/汇总逻辑 | FAILED: 无返回数据 |

### 测试统计

- AI 测试: 213 passed (R3+ 后)
- 全量: 待 Integration Review 确认
