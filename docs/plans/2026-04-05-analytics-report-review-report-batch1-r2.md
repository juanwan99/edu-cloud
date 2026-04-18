<!-- pre-takeover: archived for history, not active spec -->
[edu-cloud] GPT Reviewer | 2026-04-05 22:25:33
<!-- anchor: finding-classification -->
## 审查报告 Round 2: Task 1-13
结论: PASS

### Round 1 Finding 处置

| ID | R1 Severity | R1 Category | 修复 commit | R2 状态 | 证据 |
|----|-------------|-------------|------------|---------|------|
| F001 | HIGH | test-gap | 4af2c34 | resolved-correct | test_upsert_subject_override_is_update_not_duplicate: 同校同科二次 upsert 断言 len==1 且值已更新 |
| F002 | HIGH | test-gap | 4af2c34 | resolved-correct | test_class_trend_snapshot_path: ClassExamReport(class_avg=99.99) 区分快照/fallback |
| F003 | MED | code-bug | 4af2c34 | resolved-correct | report_service.py:181 改用 statistics.median，与 W1 口径一致 |
| F004 | HIGH | test-gap | 4af2c34 | resolved-correct | 前端新增 3 交互测试: 空选择 warning / queryReport 参数+回填 / exportReport 调用 |

### 第一段：测试充分性（Test Adequacy）
- F001 新增测试有效：删除 upsert 逻辑（改为纯 insert）后测试会 fail（assert len==1 失败）
- F002 新增测试有效：删除 snapshot 分支后测试会 fail（class_avg ≠ 99.99）
- F003 代码修复已落地，新增 median 一致性测试覆盖奇数样本
- F004 前端测试从 1 个挂载测试扩展到 4 个（挂载+空选择+查询+导出）

### 第二段：行为正确性（Behavioral Correctness）
- 变更理解：Round 2 修复包含 1 处运行时代码变更（median 口径统一）+ 3 处测试补充（segment upsert / snapshot 路径 / 前端交互）
- 运行时代码变更仅 1 处：sorted[n//2] → statistics.median
- 其余均为测试补充，未改变业务行为
- 对抗性审查：GPT 独立运行 22 backend + 4 frontend tests 全绿

### 第三段：未测试风险（Non-tested Risks）
- 偶数样本 median 的 statistics.median 行为（返回两个中位数的平均值）与 W1 一致
- 无新增未测试风险

### 发现清单

Round 2 无新增 Finding。Round 1 的 F001-F004 全部 resolved-correct（见上方处置表）。

### 回归检查
- 后端 1422 passed / 3 failed（预存：tool_access_fail_closed ×2 + alembic_migration ×1，非本次引入）
- 前端 76 passed（+3 new）
- git diff --stat：4 files changed, 147 insertions, 21 deletions

GPT 原始输出: docs/plans/.codex-raw-code_review_r2-20260405-222533.log
SHA256: 9ee5b17b3a83074ca3fa758887c9e6e2edd88415f5e32cb0302ef49251a50138
