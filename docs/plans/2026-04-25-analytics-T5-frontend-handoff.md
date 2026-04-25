---
topic: analytics-deep-T5-frontend
tier: T2
handoff_type: executor
created: "2026-04-25 11:50:51"
blocked_by: [T1, T2, T3, T4]
blocks: [T6]
---

=== 生成块开始 ===

# T5 前端 report/ 页面填充 — 执行交接卡

**目标**: frontend-nuxt/pages/report/ 7 个页面接入真实后端数据，在浏览器中可视化验证。

**按页面**:
1. exam.vue — 基础 Tab: StatCard + 分布直方图 + ClassRankTable + 题目表; 进阶 Tab: AiDiagnosis + ErrorCause
2. contrast.vue — 班级对比: boxplot + knowledge heatmap + error patterns + class-diagnosis(T2)
3. students.vue — 学生追踪: StudentRankTable + TrendLine
4. level-score.vue — 已有，验证交互
5. config.vue — 已有，验证
6. custom.vue — 多指标选择器 → report/query
7. table.vue — 导出功能验证

**前置**: T1-T4 后端数据就绪
**启动后端**: `.venv/bin/python -m uvicorn edu_cloud.api.app:create_app --factory --port 9000`
**启动前端**: `cd frontend-nuxt && npm run dev`

**验收**: 浏览器访问每个 report/ 页面，能看到基于 142K 答题数据的图表

=== 生成块结束 ===

视觉验证需要用户确认，不能自审"已完成"。每个页面截图或描述差异后等用户确认。
