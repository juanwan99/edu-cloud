[edu-cloud] GPT Reviewer | 2026-04-05 21:16:29
<!-- anchor: finding-classification -->
## 审查报告: Task 1-13
结论: FAIL

### 第一段：测试充分性（Test Adequacy）
- 后端 Service/API 测试覆盖了主要 happy path 和部分边界（空分数、零满分、角色裁剪、越权 403）
- Contract Pack invariant 1（分数段唯一性）：默认配置 upsert 有测试，但 **科目 override 的 upsert 唯一性未测试**
- Contract Pack invariant 3（趋势数据一致性）：三个趋势测试只走 fallback 路径，**snapshot 路径完全未覆盖**
- 前端测试只验证组件能挂载，删除核心逻辑后测试仍 PASS → test-gap HIGH

### 第二段：行为正确性（Behavioral Correctness）
- 变更理解：新增分数段配置 CRUD + 自定义分析构建器 + 跨考试趋势 + PDF 导出 + 3 个 AI 工具 + 前端页面
- Executor 自审抽检：test_report_query_restricted_metrics 独立验证 ✓，test_student_trend_forbidden_for_other_class 独立验证 ✓
- 对抗性审查：
  - 边界输入构造：偶数样本（4 人）下 fallback median 与 snapshot median 口径不一致 → F003
  - 异常路径追踪：删除 ClassExamReport 快照分支后 test_class_trend 仍 PASS → F002
  - 假阴性检测：同科目 override 二次 upsert 无测试覆盖 → F001；前端删除核心逻辑后测试仍 PASS → F004
- 发现 median 统计口径不一致（fallback 用 sorted[n//2]，W1 用 statistics.median）

### 第三段：未测试风险（Non-tested Risks）
- snapshot vs fallback 路径的字段语义一致性完全未测试
- 前端交互行为（查询/导出/空选择校验）未被测试覆盖

### 发现清单

**F001**
Severity: HIGH
Category: test-gap
Type: defect_fix
Before-behavior: Contract Pack invariant 1 声称"每校每科最多 1 条覆盖"，但当前测试只验证默认配置的 upsert，没有对同科目 override 二次写入的测试
After-behavior: 补充 subject_code override 的 upsert 唯一性测试
Evidence: tests/test_services_exam/test_segment_service.py:118（只有一次 math 写入）
Impact: 同校同科重复 override 的 upsert 行为可以退化为重复插入而 CI 无感知
Status: verified

**F002**
Severity: HIGH
Category: test-gap
Type: defect_fix
Before-behavior: test_class_trend 只断言 len(points)==2 且含 class_avg，没有 ClassExamReport fixture，只测 fallback 路径
After-behavior: 补充带 ClassExamReport(status="ready") 的测试，验证 snapshot 路径优先使用
Evidence: tests/test_services_exam/test_report_service.py:121-122, report_service.py:201
Impact: snapshot-first 行为可以整段失效而 CI 无感知
Status: verified

**F003**
Severity: MED
Category: code-bug
Type: defect_fix
Before-behavior: get_grade_trend fallback 路径用 sorted(values)[n//2] 计算 median，W1 快照用 statistics.median
After-behavior: 统一为 statistics.median，保证两条路径口径一致
Evidence: report_service.py:180 vs w1_post_exam.py:65
Impact: 偶数样本时 median 值会因路径不同而跳变
Status: verified

**F004**
Severity: HIGH
Category: test-gap
Type: defect_fix
Before-behavior: 前端测试只验证 wrapper.html() 为真，删除 runQuery/handleExport 等核心逻辑后仍 PASS
After-behavior: 至少覆盖 1 条成功查询路径 + 1 条空选择校验路径
Evidence: frontend/src/pages/__tests__/AnalyticsReportPage.test.js:24
Impact: 前端查询/导出行为无回归保护
Status: verified

### 三态标注汇总

| ID | Severity | Category | Type | Status | 终态 |
|----|----------|----------|------|--------|------|
| F001 | HIGH | test-gap | defect_fix | verified | — |
| F002 | HIGH | test-gap | defect_fix | verified | — |
| F003 | MED | code-bug | defect_fix | verified | — |
| F004 | HIGH | test-gap | defect_fix | verified | — |

GPT 原始输出: docs/plans/.codex-raw-code_review-20260405-211629.log
SHA256: de1527ab6780d13b591962ede0d7ccf75334016d535d47807b9ad929fdfe1a2f
