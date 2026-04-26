---
topic: analytics-deep-T2-diagnosis
tier: T2
handoff_type: executor
created: "2026-04-25 11:50:51"
blocked_by: [T1]
blocks: [T5, T6]
---

=== 生成块开始 ===

# T2 三维班级诊断 — 执行交接卡

**目标**: 新增 `GET /analytics/exam/{id}/class-diagnosis` 端点，返回 3 个维度的知识点诊断。

**算法**:
- worstKnowledges: 按 ClassAnalysis.knowledge_mastery 中掌握率升序 Top5
- unmasterMaxCntKnowledges: 按 StudentKnpMastery 中 stu_rate < 0.6 的学生数降序 Top5
- maxScoreDiffKnowledges: 按 (max stu_rate - min stu_rate) 降序 Top5
- weakKnpCount: floor(总知识点数 × 0.3)

**前置**: T1 完成（需要 ClassAnalysis + StudentKnpMastery 有数据）

**文件**: `src/edu_cloud/modules/analytics/router.py` 加端点 + `ranking_service.py` 或新 `diagnosis_service.py` 加逻辑
**测试**: `tests/test_api/test_analytics_diagnosis.py` 新增

=== 生成块结束 ===

TDD: 先写测试断言 3 个列表各 ≤5 项 + weakKnpCount = floor(N*0.3)，再实现。
