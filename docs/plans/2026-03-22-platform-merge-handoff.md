---
type: handoff
created: 2026-03-22 23:21:27
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-plan.md
---

# exam-ai → edu-cloud 合并交接卡

## 约束与偏好

**T4 流程** — 每 Batch 完成后必须 codex-review (code)，Batch 5 额外 codex-review (integration)。

1. **Re-export stub 策略是生命线**：移动文件时必须在旧位置留 re-export stub，否则中间态测试全崩。Task 22 统一清理。不要提前删除 stub。

2. **ExamResult 保留决策（计划覆盖设计文档）**：设计文档说删除 ExamResult，但计划决定保留为聚合视图。原因：ai/tools/analytics.py 和 workspace_service.py 重度依赖，重写代价远大于保留。执行时以计划为准。

3. **exam-ai models/exam.py 包含 5 个模型**：Exam, Subject, Question, Template, CardSkeleton 全在一个文件里。Task 6 提取前 3 个到 exam 模块，Task 8 提取后 2 个到 card 模块。不要遗漏。

4. **用户偏好**：用户信任 Claude 做全部技术决策，但要求"任何决策必须基于全局最优，必须先调研清楚"。遇到不确定的地方先调研再动手。

5. **测试基线**：当前 267 tests 全 PASS。每个 Task 完成后跑 `python -m pytest --tb=short -q` 确认不回归。

6. **exam-ai 源码路径**：`C:\Users\Administrator\exam-ai\src\exam_ai\`（13,375 LOC / 97 files）。测试在 `C:\Users\Administrator\exam-ai\tests\`（8,901 LOC / 78 files）。

## 启动 Prompt

```
读取交接卡 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-handoff.md，然后读取计划文件（plan 字段路径）。

这是 T4 任务的执行会话。使用 executing-plans skill，从 Batch 1 Task 1 开始执行。

计划共 5 个 Batch / 22 个 Task。本次会话执行 Batch 1（Task 1-5: Foundation）。

关键约束：
- 移动文件时在旧位置留 re-export stub（计划"迁移策略"章节）
- ExamResult 保留（计划覆盖设计文档的删除决策）
- exam-ai 源码在 C:\Users\Administrator\exam-ai\src\exam_ai\
- 每个 Task 完成后跑 python -m pytest --tb=short -q 确认不回归

Batch 1 完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
