[edu-cloud] GPT Reviewer | 2026-04-09 12:57:51
## 审查报告: Task 1-6
结论: PASS (Round 3)

### 变更理解

本次变更在 edu-cloud 新增 exam-ai 兼容路由层（`/api` 前缀，8 个端点），使 paper-seg 扫描客户端零代码改动即可连接 edu-cloud 完成扫描全链路。同时修复 publish 端点的 status 限制，允许 scanning 状态重新发布。

### 对抗性审查

GPT 独立审查 3 轮，逐步收紧：
- R1: 发现 upload-objective 遗漏缺考/异常字段、upload_image 缺归属校验、publish 无测试覆盖
- R2: 发现 question 归属链不完整（缺 subject_id）、测试只验响应不验 DB 持久化
- R3: 确认所有 code-bug 和 test-gap 修复到位，16 tests passed

### 发现清单

#### Round 1
| ID | Severity | Category | Type | Before-behavior | After-behavior | 状态 |
|----|----------|----------|------|-----------------|----------------|------|
| P001 | MED | design-concern | defect_fix | 计划无 Contract Pack 段 | 应补 Contract Pack | design-concern，不阻塞 |
| F001 | HIGH | code-bug | defect_fix | parse_answers 返回 skeleton/layout/has_tpl_slots | 改为只返回 v2_layout | contested → resolved-false-positive（预存工作树修改被意外提交，非本任务范围） |
| F002 | HIGH | code-bug | defect_fix | upload-objective 忽略 is_absent/anomaly/fill_ratios | 应持久化这些字段并处理缺考路径 | verified → fixed (f74ef4c) |
| F003 | MED | code-bug | defect_fix | upload_image 无 exam/subject/question 归属校验 | 应校验归属链后再存储 | verified → fixed (f74ef4c) |
| F004 | HIGH | test-gap | defect_fix | publish 端点状态放宽无测试 | 应有 grading/completed 拒绝测试 | verified → fixed (f74ef4c) |

#### Round 2
| ID | Severity | Category | Type | Before-behavior | After-behavior | 状态 |
|----|----------|----------|------|-----------------|----------------|------|
| F003-R2 | HIGH | code-bug | defect_fix | question 查询只按 id+school_id，不验 subject_id | 应加 subject_id 过滤防跨科目污染 | verified → fixed (8184e79) |
| F002-R2 | HIGH | test-gap | defect_fix | 测试只断言响应体 | 应查 DB 验证 is_absent/is_anomaly/fill_ratios 持久化 | verified → fixed (8184e79) |

#### Round 3
PASS — 无新 finding。

### 行为变更审批记录
无 behavior_change finding。
