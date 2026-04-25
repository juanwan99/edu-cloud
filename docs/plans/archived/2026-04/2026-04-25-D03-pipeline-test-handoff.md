---
topic: tech-debt-D03-pipeline-test
tier: T1
handoff_type: executor
created: "2026-04-25 10:25:37"
blocked_by: null
blocks: [D04]
---

=== 生成块开始 ===

# D-03 Pipeline Worker 测试修复 — 执行交接卡

**目标**: 修复 `test_run_post_exam_pipeline_stub` 失败。

**定位**:
```
cd ~/projects/edu-cloud
.venv/bin/python -m pytest tests/test_workers/test_grading_worker.py::test_run_post_exam_pipeline_stub -v --tb=long
```

**可能根因**: Mock 路径不匹配 / 函数签名变更 / Task 注册方式变更（S1-A 重构引入）。

**关键文件**:
- 测试: `tests/test_workers/test_grading_worker.py`
- 实现: `src/edu_cloud/workers/grading.py` — `run_post_exam_pipeline`
- 注册: `src/edu_cloud/worker.py`

**验收**: `test_run_post_exam_pipeline_stub` PASS + 其他 worker 测试不受影响

=== 生成块结束 ===

T1 级别，读 traceback 判断根因后直接修 stub 对齐签名，不改业务代码。
