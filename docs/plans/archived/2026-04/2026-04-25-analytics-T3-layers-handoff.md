---
topic: analytics-deep-T3-layers
tier: T2
handoff_type: executor
created: "2026-04-25 11:50:51"
blocked_by: [T1]
blocks: [T5, T6]
---

=== 生成块开始 ===

# T3 分层学情分析 — 执行交接卡

**目标**: 新增 `GET /analytics/exam/{id}/layer-analysis` 端点。

**算法**: 按分数段分 3 层（>=85% 优秀 / 60-84% 良好 / <60% 待提升），每层统计人数+平均得分率+各 KP 掌握率。附 maxDiffKnowledges: 层间差异最大的知识点。

**前置**: T1 完成（需要 StudentAnalysis + StudentKnpMastery 有数据）

**文件**: `src/edu_cloud/modules/analytics/router.py` + 新 `layer_service.py`
**测试**: 断言 3 层人数之和 = 总人数；每层 avgScoreRate 在合理范围

=== 生成块结束 ===

分层阈值用 score_segment_config，如果没配置走默认 [85,70,60]。
