[edu-cloud] GPT Reviewer | 2026-03-18 19:43:15
## 审查报告: Task 1-11
结论: FAIL

### 第一段：测试充分性（Test Adequacy）
Phase 1 未通过，存在 3 HIGH + 1 MED test-gap。未进入 Phase 2/3。

### 发现清单

| ID | Severity | Category | Evidence | Impact | Suggested action |
|----|----------|----------|----------|--------|-----------------|
| T001 | HIGH | test-gap | plan:1196-1199; tests/test_services/test_joint_exam_service.py | 计划声明的 3 个边界条件无测试：空 student_results→ValidationError、已 completed 联考再提交→StateError、上传非联考科目模板→ValidationError | 补齐 3 个独立失败用例 |
| T002 | HIGH | test-gap | plan:1465-1466; tests/test_api/test_sync_v2.py | "非参与校调用 /sync/scores 应返回 403"无测试覆盖 | 新增第三所非参与校，用其 key 调 /sync/scores 断言 403 |
| T003 | HIGH | test-gap | plan:1483; tests/test_services/test_results_service.py:50 | test_rankings_all_subjects fixture 只有 1 科目，无法验证跨科汇总 | 改为 2 科目 + 构造"单科第一 ≠ 总分第一"数据 |
| T004 | MED | test-gap | plan:548; tests/test_api/test_deps.py | 计划要求的 test_observer_cannot_create_school 未落地 | 增加 observer fixture + 403 断言 |
