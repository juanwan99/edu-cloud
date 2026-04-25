---
topic: analytics-deep-T4-wrong-questions
tier: T2
handoff_type: executor
created: "2026-04-25 11:50:51"
blocked_by: [T1]
blocks: [T5, T6]
---

=== 生成块开始 ===

# T4 常错题聚合 — 执行交接卡

**目标**: 新增 `GET /analytics/exam/{id}/common-wrong-questions` 端点。

**算法**: 查班级所有学生答错的题（final_score < max_score×0.6），按题目聚合错误人数和平均得分率，按错误率降序排列。

**前置**: T1 完成（或直接查 student_answers + grading_results）

**文件**: `src/edu_cloud/modules/analytics/router.py` + `insights_service.py` 扩展
**测试**: 断言返回按 wrong_rate DESC 排序 + 每题 mean_rate ∈ [0,1]

=== 生成块结束 ===

可以复用 insights_service 的查询模式，加上班级聚合维度。
