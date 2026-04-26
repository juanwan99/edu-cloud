---
type: handoff
created: 2026-03-18 18:45:58
design: docs/plans/2026-03-18-joint-exam-mvp-design.md
plan: docs/plans/2026-03-18-joint-exam-mvp-plan.md
---

## 约束与偏好

**T3 流程** — design→plan→新会话执行→codex-review。

- 用户明确表示"技术细节你决定"，不需要逐步确认实现细节
- edu-cloud 项目极新（4 commits），无遗留代码负担，可大胆改造
- 测试环境用 SQLite in-memory（conftest.py 已有 fixture），生产用 PostgreSQL
- median 计算用 Python statistics.median()（兼容 SQLite），不用 PostgreSQL 专有函数
- upsert 用 select→update/insert 两步法（兼容 SQLite），不用 ON CONFLICT
- Task 5 models/joint_exam.py 全量重写合规（现有 49 行 < 200 行）
- Task 8 sync.py 改造时必须 Grep 确认 JointExamScore 零残留
- Task 10（exam-ai 侧）开始前先 Grep GradingResult 模型字段，确认与 detail_scores 映射
- Phase 5（Task 10）在 exam-ai 项目目录执行，不在 edu-cloud
- paper-skill-local 有 4 commits 未推送（与本任务无关，不处理）

## 启动 Prompt

```
[edu-cloud] Executor | 2026-03-18
项目: C:/Users/Administrator/edu-cloud  读取 docs/plans/2026-03-18-joint-exam-mvp-handoff.md，按 docs/plans/2026-03-18-joint-exam-mvp-plan.md Task 1-11 执行。使用 executing-plans skill。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
