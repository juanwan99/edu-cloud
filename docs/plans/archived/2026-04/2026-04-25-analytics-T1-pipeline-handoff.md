---
topic: analytics-deep-T1-pipeline
tier: T3
handoff_type: executor
created: "2026-04-25 11:50:51"
blocked_by: null
blocks: [T2, T3, T4, T5, T6]
---

=== 生成块开始 ===

# T1 预计算管线实现 — 执行交接卡

**目标**: 实现 W1 post-exam pipeline，考试发布后自动填充 ClassAnalysis / StudentAnalysis / StudentKnpMastery 三张表。

**核心事实**:
- 三张表已有 ORM 定义（`src/edu_cloud/modules/analytics/models.py`），DB 中存在但 0 行
- W1 pipeline 入口在 `src/edu_cloud/worker.py` (run_post_exam_pipeline) 已注册但未实现填充逻辑
- 数据源: student_answers (142K) + grading_results (48) 通过 `get_effective_scores()` 获取
- 及格线 60% / 优秀线 85%；排名同分同名次跳号；掌握率 = 学生KP题得分 / KP题满分

**改动范围**: `src/edu_cloud/modules/analytics/` 内新增 pipeline_service.py（或扩展 service.py）
**不动**: 现有 26 个端点签名、router.py、前端代码

**验证**:
1. 手动触发: `.venv/bin/python -c "from edu_cloud.modules.analytics.pipeline_service import compute_exam_analysis; import asyncio; asyncio.run(compute_exam_analysis(exam_id))"`
2. 确认 3 张表有数据
3. 确认 trend 端点命中快照而非实时计算
4. `pytest tests/test_api/test_analytics* -v` 全绿 + 新增 pipeline 测试

**设计文档**: `docs/plans/2026-04-25-analytics-deep-through-design.md` §T1

=== 生成块结束 ===

这是最关键的任务——没有预计算数据，后续 T2-T6 都无法验证。先 TDD：写一个测试验证 compute 后 ClassAnalysis 表有正确数据，再实现。
