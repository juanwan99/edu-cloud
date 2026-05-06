# 成绩分析与 AI 阅卷报告业务管道计划

> **Status note:** This document began as a read-only plan. The user later approved execution; the implementation record is in `docs/plans/2026-05-07-analytics-ai-report-completion.md`.

**Goal:** 打通传统成绩分析报表，并新增专门的 AI 阅卷报告页面，使成绩数据从扫描/阅卷入库稳定流向统计快照、传统报表、AI 诊断报告。

**Architecture:** 先统一学生身份和有效分数口径，再生成稳定统计快照，传统报表读取成绩快照，AI 报告读取 AI 阅卷证据与诊断快照。传统报表回答“分数、排名、分布”；AI 报告回答“为什么丢分、AI 是否可靠、怎么教学补救”。

**Tech Stack:** FastAPI + SQLAlchemy async + SQLite/Postgres compatible services, Vue 3 + Naive UI + ECharts, existing `analytics`, `pipeline`, `grading`, `scan`, `profile` modules.

---

## 1. Objective Restatement

用户显式目标：

1. 传统成绩分析报表都需要有。
2. AI 驱动报表要充分发挥 AI 优势，包括大数据分析、极细粒度分析、诊断价值分析。
3. 以 Codex 为主，Claude 辅助。
4. 今晚完成成绩分析页面的业务逻辑梳理和打通。

当前约束：

- 用户已明确“先别动手”，所以本阶段只做业务逻辑梳理和打通方案，不改代码、不动数据库。
- Claude 只读辅助咨询已尝试两次，分别 300s 和 120s 超时，未返回可用结论。

## 2. Current Evidence

目标考试：

- `exam_id = 796f7c26-77d6-4606-ba42-a1c2de2aa4f7`
- 名称：`2026年上学期七年级下册语文期中考试`
- `status = draft`
- 科目数：9

只读数据库验证结果：

| 数据项 | 现状 |
|---|---|
| `student_answers` | 约 108519 行，语文/生物/地理已有分数 |
| 语文选择题 | 14751 rows / 1341 students，`student_id` 为 UUID，可 join `students.id` |
| 语文主观题 | 13410 rows / 1341 students，`student_id` 为 6 位条码，不能 join `students.id` |
| 生物选择题 | 34050 rows / 1362 students，已评分，`student_id` 为 6 位条码，不能 join `students.id` |
| 地理选择题 | 34050 rows / 1362 students，已评分，`student_id` 为 6 位条码，不能 join `students.id` |
| 生物/地理主观题 | 使用 6 位条码，不能 join `students.id` |
| 条码匹配 | 用 `25 + substr(students.student_number, -4)` 可匹配 1362/1364 个条码学生 |
| 异常条码 | `0902`, `251756` |
| `exam_results` | 1341 行，仅语文 UUID 成绩 |
| `student_exam_snapshots` | 0 |
| `exam_analysis_snapshot` | 0 |
| `class_exam_report` | 0 |
| `class_analysis` | 0 |
| `student_analysis` | 0 |
| `student_knp_mastery` | 0 |
| `question_knowledge_points` | 语文/生物/地理当前均无知识点绑定 |

从当前成绩估算看，数据本身已能形成分析：

| 口径 | 结果 |
|---|---|
| 当前原始 `student_id` 汇总 | 2704 个 student keys，三科合计均分约 101.63，明显被 UUID/条码拆成两批 |
| 通过条码归一后的 canonical 汇总 | 1364 个 student keys，三科合计均分约 201.47 |
| 语文归一前 | 2681 个 student keys，均分约 39.12 |
| 语文归一后 | 1342 个 student keys，均分约 78.16 |
| 生物 | 1362 个学生，均分约 58.68 / 100 |
| 地理 | 1362 个学生，均分约 66.07 / 100 |

结论：不是没有成绩，而是身份与快照管道未打通。

## 3. Existing Capabilities

### 3.1 Traditional Report Backend

已有后端能力：

- `/analytics/exam/{exam_id}/summary`
- `/analytics/exam/{exam_id}/distribution`
- `/analytics/subject/{subject_id}/questions`
- `/analytics/report/query`
- `/analytics/report/trend/grade`
- `/analytics/report/trend/class`
- `/analytics/report/trend/student`
- `/analytics/report/grade/{exam_id}/{subject_id}/export`
- `/analytics/report/student/{student_id}/{exam_id}/{subject_id}/export`
- `/analytics/exam/{exam_id}/student-rankings`
- `/analytics/exam/{exam_id}/critical-students`
- `/analytics/exam/{exam_id}/class-boxplot`
- `/analytics/exam/{exam_id}/common-wrong-questions`
- `/analytics/grade/{grade_id}/overview`
- `/analytics/grade/{grade_id}/trend`
- `/analytics/grade/{grade_id}/subjects`

已有统计口径：

- 有效分数：`COALESCE(grading_results.final_score, student_answers.score)`
- 选择题：主要来自 `student_answers.score`
- 主观题：主要来自 `grading_results.final_score`，缺失时 fallback 到 `student_answers.score`

### 3.2 Current Frontend Pages

已有页面：

- `frontend/src/pages/AnalyticsReportPage.vue`
  - 页面标题：分析报告
  - 可选择考试、指标、导出科目
  - 当前展示：总览、分数段、班级排名、尖子生/临界生
  - 问题：指标里有 `questions`，但页面没有渲染题目分析 tab

- `frontend/src/pages/AnalyticsPage.vue`
  - 单考试详情页，能展示考试诊断、分布、题目分析、学生排名、临界生、常错题
  - 问题：入口不够突出，且统计会被条码身份断链影响

- `frontend/src/pages/GradeAnalyticsPage.vue`
  - 年级分析页，能展示班级对比、趋势、科目雷达
  - 问题：依赖学生班级 join，条码身份未归一时会返回空或不完整

已有导航：

- 侧边栏只有一个“成绩分析”入口，指向 `/analytics/report`
- 没有单独的“AI 阅卷报告”入口

## 4. Breakpoints

### 4.1 Identity Break

现有核心统计函数按 `StudentAnswer.student_id == Student.id` join：

- `get_effective_scores(... visible_class_ids=...)`
- `get_effective_scores_batch(... visible_class_ids=...)`
- `grade_aggregates`
- `student_rankings`
- `critical_students`
- `class_boxplot`
- `class_knowledge`
- `class_error_patterns`
- `generate_exam_snapshots`
- `compute_exam_analysis`
- 年级分析服务

这导致：

- 生物/地理虽然有分，但无法进入班级、年级、排名。
- 语文选择题使用 UUID，语文主观题使用条码，同一个学生被拆成两个人。
- 三科总分会被拆成 UUID 学生和条码学生两批，导致总分、排名、分布失真。

### 4.2 Snapshot Break

目标考试所有分析快照为空：

- 没有学生考试快照。
- 没有班级报告。
- 没有年级/学科快照。
- 没有知识点掌握快照。
- 没有学生分析表。

这导致：

- 页面只能实时算。
- 趋势类页面无法稳定读取预计算数据。
- AI 工具读取快照时会返回暂无数据。

### 4.3 Page Break

`AnalyticsReportPage.vue` 的现状低于业务要求：

- 有 `questions` 指标选项，但没有对应 UI。
- 没有学生排名明细。
- 没有常错题。
- 没有班级箱线/对比。
- 没有 AI 诊断。
- 没有数据完整性/生成状态提示。

### 4.4 AI Report Break

已有 AI 数据源：

- `grading_results.ai_score`
- `grading_results.ai_confidence`
- `grading_results.ai_feedback`
- `grading_results.ai_raw_response`
- `grading_results.final_score`
- `grading_results.status`
- `grading_results.source`
- `grading_pipeline_logs.ocr_text`
- `grading_pipeline_logs.confidence`
- `grading_pipeline_logs.total_ms`
- `grading_pipeline_logs.error_type`
- `grading_pipeline_logs.is_blank`
- `grading_quality_checks`
- `student_answers.detected_answer`
- `student_answers.fill_ratios`
- `student_answers.is_anomaly`

但没有专门的 AI 阅卷报告页面，也没有稳定的 AI 报告快照。

## 5. Product Boundary

### 5.1 Traditional Score Report

回答这些问题：

- 这次考试多少人参加？
- 每科均分、最高分、最低分是多少？
- 分数段怎么分布？
- 哪些班级领先/落后？
- 哪些学生排名靠前/靠后？
- 哪些题得分率低？
- 哪些学生是临界生？
- 能否导出 PDF/Excel？

页面建议入口：

- 保留 `/analytics/report`
- 定位为“成绩分析报告”

### 5.2 AI Grading Report

回答这些问题：

- AI 阅卷覆盖了哪些题、多少份？
- AI 阅卷是否可靠？
- 哪些题低置信度多，需要人工复核？
- AI 与人工最终分差异在哪里？
- 哪些题出现系统性错因？
- 哪些班级在某类错误上集中？
- 哪些学生需要重点干预？
- 教师明天讲评应优先讲哪些题和知识点？

页面建议入口：

- 新增 `/analytics/ai-report`
- 或考试详情页内新增 `AI 阅卷报告` tab
- 侧边栏“考试阅卷”组下新增独立入口：`AI 阅卷报告`

## 6. Target Data Pipeline

### 6.1 Identity Resolver

新增统一身份解析层，供 analytics/pipeline/export 共用：

输入：

- `StudentAnswer.student_id`
- `school_id`
- `exam_id`

输出：

- `raw_student_key`
- `canonical_student_id`
- `class_id`
- `student_number`
- `match_method`
- `match_status`

匹配优先级：

1. `student_answers.student_id == students.id`
2. `student_answers.student_id == students.student_number`
3. 景炎本次条码规则：`student_answers.student_id == '25' + substr(students.student_number, -4)`
4. 人工映射表或异常清单

必须记录无法匹配条码：

- `0902`
- `251756`

### 6.2 Effective Score View

建立统一查询层，返回每个学生每题的最终有效分：

字段：

- `exam_id`
- `subject_id`
- `question_id`
- `raw_student_key`
- `canonical_student_id`
- `class_id`
- `question_type`
- `detected_answer`
- `effective_score`
- `max_score`
- `score_source`
- `ai_score`
- `ai_confidence`
- `final_score`
- `grading_status`
- `is_anomaly`

有效分数：

```text
effective_score = COALESCE(grading_results.final_score, student_answers.score)
```

分数来源：

- `objective_scan`: 选择题自动判分
- `ai_final`: AI 分数被确认
- `ai_override`: AI 分数被人工改分
- `manual`: 人工分数
- `missing`: 无有效分

### 6.3 Snapshot Generation

生成或更新：

- `student_exam_snapshots`
- `exam_analysis_snapshot`
- `class_exam_report`
- `class_analysis`
- `student_analysis`
- `student_knp_mastery`

当前目标考试知识点绑定为 0，所以第一阶段允许知识点为空，但报告必须明确提示“题目暂未绑定知识点，知识点诊断不可用”。

### 6.4 Traditional Report Read Path

传统报表优先读快照：

1. 学生/班级/年级统计：优先快照。
2. 题目分析：可读统一 effective score view 实时聚合，后续沉淀快照。
3. 快照缺失时页面显示“需生成分析快照”，不要静默展示空报告。

### 6.5 AI Report Read Path

AI 报告读取：

- `grading_results`
- `grading_pipeline_logs`
- `grading_quality_checks`
- `student_answers`
- effective score view
- 后续新增 `ai_grading_report_snapshot` 或复用 `exam_analysis_snapshot.snapshot_type = 'ai_grading_report'`

建议新增快照结构：

```json
{
  "coverage": {},
  "quality": {},
  "confidence": {},
  "ai_human_delta": {},
  "ocr": {},
  "question_diagnostics": [],
  "class_diagnostics": [],
  "student_watchlist": [],
  "teaching_actions": [],
  "data_warnings": []
}
```

## 7. Traditional Report Requirements

传统成绩分析页面必须包含：

- 考试总览：考试名、科目、参考人数、有效成绩人数、缺失人数。
- 学科概览：均分、最高分、最低分、得分率、满分、有效样本数。
- 分数段分布：总分和单科均支持。
- 班级排名：均分、最高/最低、中位数、优秀率、及格率、人数。
- 学生排名：年级排名、班级排名、总分、各科分。
- 题目分析：每题得分率、均分、满分、答题人数、错误率。
- 常错题：错误人数、错误率、班级分布。
- 临界生：差及格/优秀线、主要失分题。
- 尖子生/后进生：前 10%、后 10%，显示学生姓名和班级，不只显示 ID。
- 导出：年级报告、学科报告、学生报告。
- 数据状态：显示快照是否生成、身份匹配异常、缺失科目。

## 8. AI Report Requirements

AI 阅卷报告页面必须包含：

### 8.1 AI 阅卷总览

- AI 覆盖题数、答题份数。
- AI 已评分、待评分、待人工确认。
- 人工确认率。
- 人工改分率。
- 平均 AI 置信度。
- 低置信度数量。

数据源：

- `grading_results.status`
- `grading_results.source`
- `grading_results.ai_score`
- `grading_results.ai_confidence`
- `grading_results.final_score`

### 8.2 AI 质量审计

- AI 分数与最终分差异分布。
- 平均绝对差。
- 大偏差题目 top N。
- 人工改分最多的题。
- 质量抽检结果。

数据源：

- `grading_results.ai_score`
- `grading_results.final_score`
- `grading_quality_checks`

### 8.3 OCR 与流水线质量

- OCR 空白率。
- AI 阅卷失败率。
- 平均耗时。
- 失败类型分布。
- 低置信度 OCR/评分样本。

数据源：

- `grading_pipeline_logs.is_blank`
- `grading_pipeline_logs.error_type`
- `grading_pipeline_logs.total_ms`
- `grading_pipeline_logs.confidence`
- `grading_pipeline_logs.ocr_text`

### 8.4 题目级诊断

- 每题得分率。
- 区分度。
- AI 识别的错因分布。
- 代表性错误答案。
- 低置信度样本入口。

数据源：

- `grading_results.ai_raw_response`
- `grading_results.ai_feedback`
- `student_answers.image_path`
- `student_answers.detected_answer`

### 8.5 班级与学生诊断

- 班级薄弱题对比。
- 班级错误类型分布。
- 需要干预学生清单。
- 高风险学生：低分 + 多错因 + 低置信度 + 异常作答。

数据源：

- effective score view
- `class_analysis`
- `student_analysis`
- `student_exam_snapshots`

### 8.6 教学建议

- 优先讲评题。
- 按错误原因分组的讲评建议。
- 班级差异化教学建议。
- 个体补救建议。

第一阶段可用模板生成，后续可接 LLM 生成，但必须把数据证据结构化传入。

## 9. Implementation Plan

### Task 1: Identity Mapping Audit and Resolver

**Files:**

- Modify: `src/edu_cloud/modules/analytics/identity.py` or create a shared resolver module.
- Modify: `src/edu_cloud/modules/analytics/__init__.py`.
- Test: `tests/test_services_exam/test_analytics_identity.py`.

Steps:

- Create tests for UUID student IDs.
- Create tests for direct `student_number`.
- Create tests for Jingyan `25 + last4(student_number)` barcode rule.
- Create tests for unmatched barcode warnings.
- Implement resolver without mutating `student_answers`.
- Expose resolver to analytics and pipeline services.

Acceptance:

- For target exam, canonical match rate should be at least `1362/1364` before manual exception handling.
- Report unmatched keys `0902` and `251756`.

### Task 2: Effective Score Query Layer

**Files:**

- Modify: `src/edu_cloud/modules/analytics/__init__.py`.
- Modify: services that currently call `get_effective_scores`.
- Test: `tests/test_services_exam/test_analytics_effective_scores.py`.

Steps:

- Add canonical score rows that include `raw_student_key`, `canonical_student_id`, `class_id`, and `score_source`.
- Keep old function behavior only where backwards compatibility requires it.
- Make visible class filters use canonical class_id, not raw `StudentAnswer.student_id`.

Acceptance:

- 生物/地理 class filter returns students after identity resolution.
- 语文选择题 UUID and 主观题条码 merge to one canonical student.

### Task 3: Snapshot Pipeline Repair

**Files:**

- Modify: `src/edu_cloud/modules/pipeline/service.py`.
- Modify: `src/edu_cloud/modules/analytics/pipeline_service.py`.
- Test: `tests/test_services_exam/test_profile_pipeline.py`.

Steps:

- Use canonical effective scores in `generate_exam_snapshots`.
- Generate per-subject snapshots for YW/SW/DL.
- Generate total snapshot `_total`.
- Use canonical class_id for class ranks.
- Make pipeline idempotent.

Acceptance:

- Target exam after pipeline should have snapshots for all matched students and subjects with scores.
- `class_rank` and `class_id_at_exam` should be populated for matched students.
- `student_exam_snapshots` should no longer be 0.

### Task 4: Traditional Report Page Completion

**Files:**

- Modify: `frontend/src/pages/AnalyticsReportPage.vue`.
- Modify if needed: `frontend/src/api/analytics.js`.
- Test: `frontend/src/pages/__tests__/AnalyticsReportPage.test.js`.

Steps:

- Add data status panel.
- Render `questions` metric.
- Add student ranking section using existing endpoint.
- Add common wrong questions section.
- Add critical students section.
- Show student name/class instead of raw id where possible.
- Add empty states that distinguish “no score” from “snapshot not generated” and “identity mismatch”.

Acceptance:

- Selecting `题目分析` produces a visible tab.
- Report page shows real student/class names after canonical identity fix.

### Task 5: AI Report Backend

**Files:**

- Create/modify: `src/edu_cloud/modules/analytics/ai_report_service.py`.
- Modify: `src/edu_cloud/modules/analytics/analytics_report_router.py`.
- Test: `tests/test_services_exam/test_ai_grading_report.py`.

Endpoints:

- `GET /analytics/exam/{exam_id}/ai-grading-report`
- Optional: `POST /analytics/exam/{exam_id}/ai-grading-report/recompute`

Return sections:

- `coverage`
- `confidence`
- `quality`
- `ai_human_delta`
- `ocr_pipeline`
- `question_diagnostics`
- `class_diagnostics`
- `student_watchlist`
- `teaching_actions`
- `data_warnings`

Acceptance:

- Report works when `grading_results.ai_raw_response` exists.
- Report still returns useful quality/coverage data when knowledge points are absent.
- Low confidence, blank OCR, error logs, and AI-human delta are visible.

### Task 6: AI Report Frontend

**Files:**

- Create: `frontend/src/pages/AiGradingReportPage.vue`.
- Modify: `frontend/src/router/index.js`.
- Modify: `frontend/src/config/sidebarConfig.js`.
- Modify: `frontend/src/api/analytics.js`.
- Test: `frontend/src/pages/__tests__/AiGradingReportPage.test.js`.

Page sections:

- AI 阅卷总览
- 质量审计
- 置信度分布
- OCR/流水线质量
- 题目诊断
- 班级诊断
- 学生预警
- 教学建议

Acceptance:

- The page is reachable from sidebar.
- It does not duplicate AI grading operation page.
- It shows AI-specific value, not only score stats.

### Task 7: Verification With Jingyan Data

Commands:

- `scripts/codex-check`
- `scripts/meta-check --task "成绩分析与 AI 阅卷报告打通" --write-state`
- Focused backend tests for identity/effective score/pipeline/report.
- Focused frontend tests for traditional report and AI report page.
- Read-only SQL verification after pipeline run.

Verification targets:

- 生物/地理选择题识别准确率已达人工 99% 以上的一致性，不能因后续处理改变。
- 语文、生物、地理学生身份合并后，三科总分按 canonical student 聚合。
- 快照表不再为空。
- 班级排名不再为空。
- 题目分析显示真实题目得分率。
- AI 报告显示 AI 质量和诊断数据。

## 10. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| 条码映射规则是景炎特例 | 其他学校可能不适用 | Resolver 必须可配置，并记录 `match_method` |
| 直接改 `student_answers.student_id` 可能破坏唯一约束 | 高 | 第一阶段不改原始答案，先用 canonical resolver |
| 异常条码 `0902`, `251756` 未归属 | 少量学生统计缺失 | 报告里显示异常清单，提供人工映射入口 |
| 知识点绑定为 0 | AI 知识点诊断不可用 | 第一阶段报告显示“题目未绑定知识点”，仍提供题目/错因诊断 |
| `exam.status = draft` 不会自动触发 pipeline | 快照始终为空 | 提供管理员手动生成分析快照动作或明确状态流转 |
| `grading_results.source` 基本为 manual | AI 改分率可能失真 | 同时用 `ai_score` 与 `final_score` 差异计算 AI-human delta |
| Claude 辅助超时 | 缺少第二视角 | 记录超时，不把 Claude 作为完成依据 |

## 11. Completion Audit

| Requirement | Evidence | Status |
|---|---|---|
| 传统成绩分析报表都需要有 | 已列出传统报表所需板块和现有缺口 | Designed, not implemented |
| AI 驱动报表体现 AI 优势 | 已定义 AI 覆盖、质量、置信度、错因、教学建议等专页能力 | Designed, not implemented |
| 业务逻辑梳理 | 已梳理扫描/阅卷/身份/有效分/快照/页面/导出链路 | Complete for planning stage |
| 打通 | 识别到最关键断点：6 位条码与 `students.id` 不一致，快照为空 | Not implemented due user “先别动手” |
| Claude 辅助 | 两次只读咨询均超时，无结果 | Attempted, unavailable |
| 不动手 | 未修改业务代码，未写数据库 | Respected |

Current stage is not production-complete. It is a ready-to-execute plan awaiting approval to implement.
