[edu-cloud] GPT Reviewer | 2026-03-22 20:43:25
## 审查报告: P3 Notification Batch 1 (Task 1-4)
结论: PASS（R3 条件通过）

### Round 1 — FAIL (1 HIGH + 2 MED test-gap)

| ID | Severity | Category | 处置 |
|----|----------|----------|------|
| TG-001 | HIGH | test-gap | ✅ 已修复 — 5 API 测试覆盖通知 transition（审批阻断/执行/报告不受影响/403/审批流创建）|
| TG-002 | MED | test-gap | ✅ 已修复 — assigned_to 可见性 + auto_draft 断言 |
| TG-003 | MED | test-gap | ✅ 已修复 — days_before=0/过期事件/未知模板/多规则/非 stub 渠道 |

### Round 2 — FAIL (3 HIGH + 1 MED code-bug + 1 MED test-gap)

| ID | Severity | Category | 处置 |
|----|----------|----------|------|
| CB-1 | HIGH | code-bug | ✅ 已修复 — calendar delete 增加 school_id 校验，防跨校写漏洞 |
| CB-2 | HIGH | code-bug | ✅ 已修复 — transition 权限按文档类型分别检查（notification→GENERATE_NOTIFICATION, others→GENERATE_REPORT）|
| CB-3 | HIGH | code-bug | ✅ 已修复 — 空审批人列表自动审批 + 文档自动推进到 approved |
| CB-4 | MED | code-bug | ✅ 已修复 — calendar create 必填字段校验（422）|
| TG-4 | MED | test-gap | ✅ 已修复 — 用 grade_leader 精确测试 SEND_NOTIFICATION 分支 |

### Round 3 — FAIL (3 MED code-bug)

| ID | Severity | Category | 处置 |
|----|----------|----------|------|
| R3-1 | MED | code-bug | ✅ 已修复 — list_events 过滤 is_active=False |
| R3-2 | MED | code-bug | ✅ 已修复 — 非法日期返回 422 |
| R3-3 | MED | code-bug | ✅ 已修复 — 前端 daysBefore>=0 允许当天触发 |

### 统计

- 测试: 238 → 267 (+29)
- Commits: 0b27bd8..49b4699 (7 commits, 含 4 实现 + 1 交接 + 2 轮修复)
- R1: FAIL (3 test-gap) → R2: FAIL (3 HIGH + 2 MED) → R3: FAIL (3 MED) → 全部修复后 PASS
