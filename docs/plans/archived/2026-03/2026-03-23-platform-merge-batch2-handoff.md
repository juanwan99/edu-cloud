---
type: handoff
created: 2026-03-23 08:24:10
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-plan.md
---

# exam-ai → edu-cloud 合并 Batch 2 交接卡

## Batch 1 完成状态

- **8 commits**: a958bcb..b71e6c6
- **GPT 审查**: R1 FAIL → R2 PASS（3 轮）
- **测试基线**: 271 tests, all PASS
- **已完成**: Task 1-5（模块目录 + School 重命名 + PlatformUser 删除 + Auth 改造 + Config 合并 + LLMSlot）

## 约束与偏好

**T4 流程** — Batch 2 完成后必须 codex-review (code)。

1. **api_key_hash 偏差**：计划说删除 School.api_key_hash，但 Batch 1 执行时发现 sync 认证深度依赖，改为 Optional 保留。Batch 3 删除 sync 路由时一并处理。执行时注意不要再尝试删除此字段。

2. **Re-export stub 必须留**：Batch 1 已在 `models/school.py`, `models/platform_user.py` 等建立了 re-export stub 模式。Batch 2 移动 models/services 时同样必须留 stub，Task 22 统一清理。

3. **ExamResult 保留**：设计文档已更新。ExamResult 保留为聚合视图，移入 `modules/exam/models.py`。ai/tools/analytics.py 和 workspace_service.py 不需要重写。

4. **exam-ai models/exam.py 含 5 个模型**：Exam, Subject, Question（Task 6 提取到 exam 模块）+ Template, CardSkeleton（Task 8 提取到 card 模块）。不要遗漏。

5. **Batch 2 scope**: Task 6-11c，共 8 个 Task（原 Task 11 已拆为 11a/11b/11c）。全部是 models + services 迁入/重组，不涉及 API 路由（路由在 Batch 3）。

6. **测试策略**：迁入模型后写基础 CRUD 测试。每个 Task 完成后跑 `python -m pytest --tb=short -q` 确认 271+ tests 不回归。

7. **exam-ai 源码路径**: `C:\Users\Administrator\exam-ai\src\exam_ai\`

## 启动 Prompt

```
读取交接卡 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-23-platform-merge-batch2-handoff.md，然后读取计划文件 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-plan.md。

这是 T4 任务的执行会话。使用 executing-plans skill，从 Batch 2 Task 6 开始执行。

Batch 2 范围：Task 6（Exam 模块）→ Task 7（Student）→ Task 8（Card+Scan）→ Task 9（Grading+Marking）→ Task 10（Analytics+Bank+Profile+Pipeline）→ Task 11a（Knowledge）→ Task 11b（Studio+Calendar 重组）→ Task 11c（Paper/Workspace/School/AI Session 重组）。

关键约束：
- 移动文件时在旧位置留 re-export stub（计划"迁移策略"章节）
- ExamResult 保留为聚合视图（移入 modules/exam/models.py）
- exam-ai models/exam.py 含 5 个模型：Task 6 取 Exam/Subject/Question，Task 8 取 Template/CardSkeleton
- api_key_hash 已改为 Optional 保留，不要尝试删除
- exam-ai 源码在 C:\Users\Administrator\exam-ai\src\exam_ai\
- 测试基线 271 tests，每个 Task 后跑 python -m pytest --tb=short -q

Batch 2 完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
