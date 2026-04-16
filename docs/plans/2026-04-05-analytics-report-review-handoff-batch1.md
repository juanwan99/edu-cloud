[edu-cloud] Executor→Reviewer | 2026-04-05 20:33:41
## 审查交接单: Task 1-13
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-analytics-report-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | ScoreSegmentConfig 数据模型 + Migration | commit 2404555（含模型+migration） | ✅ | |
| T2 | segment_service CRUD + compute_segments | commit 2404555（含 service+11 tests） | ✅ | |
| T3 | 修改 exam_distribution 支持动态分数段 | commit bdad685 | ✅ | |
| T4 | 分数段 API 路由 GET/PUT/DELETE | commit 5f10e8e | ✅ | |
| T5 | report_service build_report | commit 7daf28a | ✅ | |
| T6 | report_service 趋势函数 | commit 7daf28a | ✅ | |
| T7 | 报告 API 路由 query/trend/export + 权限 | commit 6833d76 | ✅ | |
| T8 | 3 个 AI Agent 工具 | commit 950cac6 | ✅ | |
| T9 | 前端 API/路由/侧栏 | commit 139166c | ✅ | |
| T10 | AnalyticsReportPage.vue + test | commit 139166c | ✅ | |
| T11 | AnalyticsTrendPage.vue | commit 139166c | ✅ | |
| T12 | ScoreSegmentSettings + 嵌入 SchoolSettings | commit 139166c | ✅ | |
| T13 | 全量测试 + 收尾 | commit a5f2866 + 2404555 | ✅ | |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| 分数段唯一性（upsert） | test_segment_service::test_upsert_prevents_duplicate_default | `pytest tests/test_services_exam/test_segment_service.py::test_upsert_prevents_duplicate_default -v` | PASSED | 不适用：已有测试非本次新增设计，upsert 逻辑验证已覆盖 |
| compute_segments 正确分段 | test_segment_service::test_compute_segments_default | `pytest tests/test_services_exam/test_segment_service.py::test_compute_segments_default -v` | PASSED — excellent["count"]==2, poor["count"]==2 | 不适用 |
| exam_distribution 动态配置 | test_analytics::test_exam_distribution_uses_school_config | `pytest tests/test_services_exam/test_analytics.py::test_exam_distribution_uses_school_config -v` | PASSED — labels 含 "通过"/"不通过" | 不适用 |
| build_report 摘要 | test_report_service::test_build_report_summary | `pytest tests/test_services_exam/test_report_service.py::test_build_report_summary -v` | PASSED — total_students==3 | 不适用 |
| grade_trend 升序 | test_report_service::test_grade_trend | `pytest tests/test_services_exam/test_report_service.py::test_grade_trend -v` | PASSED — points[0]="月考1", points[1]="期中", avg 递增 | 不适用 |
| student_trend 分数 | test_report_service::test_student_trend | `pytest tests/test_services_exam/test_report_service.py::test_student_trend -v` | PASSED — points[0].score==80, points[1].score==85 | 不适用 |
| metrics 角色白名单 | test_analytics_report::test_report_query_restricted_metrics | `pytest tests/test_api_exam/test_analytics_report.py::test_report_query_restricted_metrics -v` | PASSED — ranking/top_bottom 被裁剪，summary 保留 | 不适用 |
| 学生可见性 403 | test_analytics_report::test_student_trend_forbidden_for_other_class | `pytest tests/test_api_exam/test_analytics_report.py::test_student_trend_forbidden_for_other_class -v` | PASSED — status_code==403 | 不适用 |
| export 创建 Studio Document | test_analytics_report::test_export_report | `pytest tests/test_api_exam/test_analytics_report.py::test_export_report -v` | PASSED — status_code==201, document_id 存在 | 不适用 |
| AI 工具缺 exam_ids | test_tools_analytics_report::test_compare_exams_missing_exam_ids | `pytest tests/test_ai/test_tools_analytics_report.py::test_compare_exams_missing_exam_ids -v` | PASSED — success==False, "exam_ids" in error | 不适用 |

### 验证清单自检
- ✅ ScoreSegmentConfig 有 school_id + subject_code 唯一约束（partial index in migration, upsert in service）
- ✅ 默认值 [85,70,60] + ["优秀","良好","及格","不及格"]
- ✅ compute_segments 按百分比阈值正确分段
- ✅ get_segment_config 三级 fallback（科目→学校→硬编码）
- ✅ upsert 校验：labels 比 boundaries 多 1 / boundaries 降序 / 值在 0-100
- ✅ exam_distribution 无配置时行为与原始兼容（hardcoded fallback）
- ✅ build_report 按 metrics 列表选择性执行
- ✅ 三个趋势按 exam_date 升序排列
- ✅ class_trend 有 subject_code 时跳过 ClassExamReport 快照（R3-F001）
- ✅ student_trend 无科目过滤时只取 _total 快照（AR2-R2-04）
- ✅ POST /report/query 角色 metrics 白名单裁剪
- ✅ GET /report/trend/grade 仅限校级+角色
- ✅ GET /report/trend/student 显式校验班级可见性 + guardian
- ✅ POST /report/export 串起 Studio draft→reviewed→executed
- ✅ StudioService 方法名 transition_status（非 transition）
- ✅ 3 个 AI Agent 工具注册完成（42 tools total）
- ✅ 前端路由在 analytics/:examId 之前（避免参数捕获）
- ✅ 前端 5 个角色添加侧栏项
- ✅ 路由数断言更新 22→24
- ✅ CLAUDE.md 已同步（48 表 / 171 路由 / 42 AI tools / 1192+73 tests）

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: scores=[], max_score=100, boundaries=[85,70,60]
  运行命令: `pytest tests/test_services_exam/test_segment_service.py::test_compute_segments_empty -v`
  实际输出:
  ```
  PASSED — all segments count==0
  ```
  结论: 空分数列表正确处理

- 状态变量/锁的异常路径：
  构造输入: max_score=0.0, scores=[0,0]
  运行命令: `pytest tests/test_services_exam/test_segment_service.py::test_compute_segments_max_score_zero -v`
  实际输出:
  ```
  PASSED — result[-1]["count"]==2 (all in lowest segment)
  ```
  结论: 零分满分正确处理（除零保护）

- 字符串匹配/条件判断的假阴性：
  构造输入: homeroom_teacher 请求 ranking+top_bottom metrics
  运行命令: `pytest tests/test_api_exam/test_analytics_report.py::test_report_query_restricted_metrics -v`
  实际输出:
  ```
  PASSED — ranking/top_bottom 被裁剪，summary 保留
  ```
  结论: 角色白名单正确过滤受限指标

### 测试统计
- 后端新增: 26 tests（11 segment + 5 report_service + 1 analytics + 7 API + 2 AI tools）
- 前端新增: 1 test（AnalyticsReportPage 渲染）
- 旧测试回归: 0 failures（22 analytics 旧测试全绿）
- 已知预存失败: test_alembic_migration (2 failures) — 之前 migration 的 SQLite 不兼容问题，非本次引入
