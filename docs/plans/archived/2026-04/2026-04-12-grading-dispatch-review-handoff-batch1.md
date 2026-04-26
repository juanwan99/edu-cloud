[edu-cloud] Executor→Reviewer | 2026-04-12 22:53:37
## 审查交接单: Task 1-10
计划: C:/Users/Administrator/edu-cloud/docs/plans/2026-04-12-grading-dispatch-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | 选择题判分共享函数 | commit 7566b0a, grade_objective_answer + 10 tests | ✅ | |
| T2 | pipeline_service 扩展选择题识别 | commit e813ceb, process_one_image + save_objective_fn + 3 tests | ✅ | |
| T3 | pipeline_router 构造 save_objective_fn | commit 9f81d3b, build_pipeline_save_objective_fn + 3 tests (INV-002) | ✅ | |
| T4 | pipeline 多科目串行队列 + HTTP 入口 | commit 17983e5, enqueue_pipeline + run_queue + _queue_stopped + 4 tests | ✅ | |
| T5 | 科目阅卷状态聚合 API | commit 5c99875, GET /grading/dispatch/status + 4 tests (INV-003) | ✅ | |
| T6 | 前端 API 层 + 路由更新 | commit d28f337, grading.js + router index | ✅ | |
| T7 | GradingDispatchPage.vue 新建 | commit d1ef039, 完整调度页面 473 行 | ✅ | |
| T8 | 移除 ExamDetailPage 扫描 tab | commit bbf239d, 删除 scan tab 130 行 + 删除 GradingTasksPage | ✅ | |
| T9 | scan/router.py 共享判分函数 | commit e740884, router.py + compat_router.py 替换内联逻辑 | 🔀 | 发现 router.py 中删除旧变量后残留引用 `correct`，修复为 `question.correct_answer or ""` |
| T10 | 全量测试 + 前端验证 | 42 直接相关 tests passed, 前端 186 passed | ✅ | 前端 2 failed 为 pre-existing permissions.test.js |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| 单选正确判分 | test_objective_grading::test_correct_single | `pytest tests/test_services_exam/test_objective_grading.py -v` | 10 passed in 0.25s | 不适用：新增函数 |
| choice_group 识别 | test_pipeline_objective::test_choice_group_recognized | `pytest tests/test_services_exam/test_pipeline_objective.py -v` | 3 passed in 1.03s | 不适用：新增功能 |
| (group_id,row_index) 映射 | test_pipeline_save_objective::test_save_objective_multi_group | `pytest tests/test_api_exam/test_pipeline_save_objective.py -v` | 3 passed in 0.96s | 不适用：新增功能 |
| 队列串行执行 | test_pipeline_queue::test_queue_runs_both_subjects | `pytest tests/test_services_exam/test_pipeline_queue.py -v` | 4 passed in 0.83s | 不适用：新增功能 |
| dispatch status idle | test_dispatch_status::test_idle_stage | `pytest tests/test_api_exam/test_dispatch_status.py -v` | 4 passed in 4.96s | 不适用：新增 API |
| scan router 回归 | test_objective_upload::test_normal_grading | `pytest tests/ -k "objective" -v` | 33 passed in 10.33s | 不适用：重构不改行为 |

### 验证清单自检
- ✅ INV-001: 选择题判分逻辑与 upload_objective 一致（大小写+排序不敏感）— grade_objective_answer 统一了两处
- ✅ INV-002: choice_group → Question 映射通过 (group_id, row_index) — test_multi_group_no_cross_contamination 验证
- ✅ INV-003: dispatch/status ready 需 subjective_answer + rubric + subjective_questions — test_objective_only_not_ready 验证
- ✅ INV-004: pipeline 队列 stop 用 _queue_stopped 独立标志 — test_stop_halts_entire_queue 验证
- ✅ INV-005: 前端路由更新后 Vitest 无回归 — 186 passed
- ✅ F009: 每个队列项携带自己的 save_fn — test_each_subject_uses_own_save_fn 验证
- ✅ F010: questions_by_group 从 region.question_ids 显式关联
- ✅ F011: subjective_total 查询在 stage 推导之前
- ✅ CE-002 防护: 只有选择题答案时 stage=idle 不是 ready
- ✅ CE-003 防护: GradingTask failed 显式显示 stage=failed

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: grade_objective_answer(None, "A", 3.0)
  运行命令: `pytest tests/test_services_exam/test_objective_grading.py::TestGradeObjectiveAnswer::test_none_detected -v`
  实际输出:
  ```
  PASSED
  ```
  结论: None 输入正确处理为空字符串，返回 (0.0, False)

- 状态变量/锁的异常路径：
  构造输入: 3 科目入队后立即 request_stop()
  运行命令: `pytest tests/test_services_exam/test_pipeline_queue.py::TestPipelineQueue::test_stop_halts_entire_queue -v`
  实际输出:
  ```
  PASSED — total_processed < 60
  ```
  结论: _queue_stopped 独立标志正确传播到整个队列

- 字符串匹配/条件判断的假阴性：
  构造输入: 只有选择题答案（image_path=None），无主观题答卷
  运行命令: `pytest tests/test_api_exam/test_dispatch_status.py::TestDispatchStatus::test_objective_only_not_ready -v`
  实际输出:
  ```
  PASSED — stage=idle
  ```
  结论: ready 判定正确排除纯选择题场景
