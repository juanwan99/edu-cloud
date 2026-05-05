---
name: analytics
status: active
owner: backend
layer: business

owns_tables:
  - class_analysis
  - student_analysis
  - student_knp_mastery

owns_routes:
  - /api/v1/analytics

exposes:
  services:
    - get_effective_scores
    - get_effective_scores_batch
    - compute_exam_analysis
    - build_report
    - get_grade_trend
    - get_class_trend
    - get_student_trend
    - student_rankings
    - critical_students
    - class_diagnosis
  events: []

depends_on:
  modules:
    - exam
    - scan
    - grading
    - student
    - knowledge
    - knowledge_tree
    - profile
    - studio
  services: []
  ai_tools:
    - get_exam_scores (analytics.py)
    - get_class_stats (analytics.py)
    - get_exam_summary (analytics_score.py)
    - get_score_distribution (analytics_score.py)
    - get_question_analysis (analytics_score.py)
    - get_student_scores (analytics_score.py)
    - get_class_scores (analytics_score.py)
    - compare_classes (analytics_compare.py)
    - rank_students (analytics_compare.py)
    - get_grade_aggregates (analytics_compare.py)
    - get_score_segments (analytics_report.py)
    - compare_exams (analytics_report.py)
    - generate_analysis_report (analytics_report.py)
    - get_class_report (class_report_tool.py)

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs:
  - docs/plans/2026-04-05-analytics-report-design.md
---

# analytics 模块

## 职责

考后成绩统计分析全链路：预计算管线（ClassAnalysis/StudentAnalysis/StudentKnpMastery 填充）、实时查询（摘要/分布/排名/趋势/诊断/错因/临界生/箱线图/热力图）、分数段配置、等级赋分转换、级联筛选树、报告导出（PDF/XLSX）。

## 边界

- **做什么**：考后预聚合计算、实时统计查询、排名/趋势/对比、分数段管理、知识掌握度热力图、报告导出
- **不做什么**：原始评分写入（grading）、学生作答数据采集（scan）、学生个体画像长期追踪（profile）

## 使用方式

pipeline 触发 `compute_exam_analysis` 填充三张预计算表；前端通过 `/api/v1/analytics/*` 系列端点查询；AI Agent 通过 14 个工具函数提供自然语言分析能力。`get_effective_scores` 是有效分计算的公共入口（COALESCE GradingResult.final_score 和 StudentAnswer.score）。

## 数据流

```
exam.published 事件 → pipeline.run_full_pipeline
    → analytics.compute_exam_analysis
        → 读 StudentAnswer + GradingResult + Question + Student
        → 写 ClassAnalysis / StudentAnalysis / StudentKnpMastery
前端/Agent 查询 → router → service → 读预计算表 或 实时聚合
```
