# 成绩分析与 AI 阅卷报告打通记录

## 范围

- 传统「分析报告」页补齐题目分析、学生排名、常错题、临界生、前后 10% 展示。
- 新增独立「AI 阅卷报告」页，呈现 AI 覆盖率、置信度、人工改分差异、OCR/流水线质量、题目诊断、学生预警和教学建议。
- 打通条码型 `student_answers.student_id` 与学生 roster 的 canonical 身份解析，解决生物/地理选择题按 6 位条码入库后成绩分析查不到学生的问题。

## 关键修复

- `analytics.identity.resolve_student_identities()` 支持 UUID、学籍号、景炎 `25 + student_number[-4:]` 条码映射。
- `get_effective_scores()` / `get_effective_scores_batch()` 统一返回 canonical student id，并在已有 roster 匹配时把未匹配条码排除在正式成绩统计之外。
- `pipeline.service`、`analytics.pipeline_service`、`insights_service`、`ranking_service` 改为使用 canonical effective score。
- `ai_report_service` 对大规模 answer_id 查询分批，避免 SQLite `too many SQL variables`。

## 景炎实盘只读验证

考试：`796f7c26-77d6-4606-ba42-a1c2de2aa4f7`

| 科目 | 选择题答案 | 选择题学生 | 有效成绩学生 | 题目分析行 | 未匹配条码 |
| --- | ---: | ---: | ---: | ---: | --- |
| 语文 | 14740 effective / 14751 raw | 1340 | 1340 | 21 | `0902`, `251756` |
| 生物 | 34025 effective / 34050 raw | 1361 | 1361 | 31 | `251756` |
| 地理 | 34025 effective / 34050 raw | 1361 | 1361 | 28 | `251756` |

三科汇总：`summary_total_students=1362`，班级排名 26 个班，前后 10% 样本 1362。

选择题内部判分一致性：

- 生物：34050 / 34050 分数与标准答案一致。
- 地理：34050 / 34050 分数与标准答案一致。
- 语文：14740 / 14751 effective 分数可进入分析；raw 中 11 条选择题分数为空。

说明：这里验证的是扫描结果、标准答案和入库分数的内部一致性；若要证明「与人工选择题录入 99%+ 一致」，仍需要独立人工选择题明细作为对照源。

## Evidence / 验证证据

- `.venv/bin/python -m pytest tests/test_services_exam/test_analytics_identity.py tests/test_services_exam/test_ai_grading_report.py tests/test_services_exam/test_report_service.py tests/test_services_exam/test_profile_pipeline.py tests/test_services_exam/test_analytics.py tests/test_services_exam/test_analytics_pipeline.py -q`
- `.venv/bin/python -m ruff check src/edu_cloud/modules/analytics/__init__.py src/edu_cloud/modules/analytics/identity.py src/edu_cloud/modules/analytics/ai_report_service.py src/edu_cloud/modules/analytics/analytics_report_router.py src/edu_cloud/modules/analytics/insights_service.py src/edu_cloud/modules/analytics/ranking_service.py src/edu_cloud/modules/analytics/report_service.py src/edu_cloud/modules/analytics/pipeline_service.py src/edu_cloud/modules/pipeline/service.py tests/test_services_exam/test_analytics_identity.py tests/test_services_exam/test_ai_grading_report.py tests/test_services_exam/test_report_service.py`
- `cd frontend && npm test -- src/pages/__tests__/AiGradingReportPage.test.js src/pages/__tests__/AnalyticsReportPage.test.js`
- `cd frontend && npm run build`
- `scripts/meta-check --task "成绩分析与 AI 阅卷报告打通" --write-state`

本地调试服务：后端 `http://localhost:9001`，前端 `http://localhost:8081/`。
