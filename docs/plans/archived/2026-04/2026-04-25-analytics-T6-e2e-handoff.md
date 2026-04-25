---
topic: analytics-deep-T6-e2e
tier: T1
handoff_type: executor
created: "2026-04-25 11:50:51"
blocked_by: [T5]
blocks: null
---

=== 生成块开始 ===

# T6 端到端验证 — 执行交接卡

**目标**: 模拟完整业务流程：考试发布 → 预计算 → 分析页面可看。

**流程**:
1. 用 seed 数据的考试 → 触发 W1 pipeline → 检查 3 张预计算表
2. 访问 report/ 每个页面确认数据展示
3. 权限验证: subject_teacher 看不到排名
4. 级联筛选: 年级→班级→科目→考试 全链路
5. 全量 pytest 确认 >= 2172 passed

**验收**: "考试发布→分析报告可看"闭环跑通 + 测试基线不降

=== 生成块结束 ===

收尾任务。跑通后更新 CLAUDE.md analytics 相关描述和测试基线。
