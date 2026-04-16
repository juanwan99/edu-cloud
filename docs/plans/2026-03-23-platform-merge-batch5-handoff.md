---
type: handoff
created: 2026-03-23 14:28:01
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-plan.md
---

# exam-ai → edu-cloud 合并 Batch 5 交接卡

## Batch 4 完成状态

- **6 commits**: 590b7de..f1d4052
- **GPT 审查**: R1 FAIL(4 findings) → R2 FAIL(1 finding) → R3 PASS（3 轮）
- **测试基线**: 384 tests, all PASS
- **已完成**: Task 16-18（Agent 核心合并 + 31 工具/9 RBAC 类别 + Workers/grading/pipeline）
- **变更规模**: 27 源文件 + 5 测试文件，+2900/-400 lines

## 约束与偏好

**T4 流程** — Batch 5 完成后必须 codex-review (code) + codex-review (integration)。

1. **exam-ai 前端路径**：`C:\Users\Administrator\exam-ai\exam-ai-frontend\src\`（注意：不是 `exam-ai/frontend/`，而是 `exam-ai/exam-ai-frontend/`）。14 个页面组件、11 个 API 模块、2 个 stores、5 个 card-editor 文件。

2. **edu-cloud 前端现有文件**：`frontend/src/` 已有 LoginPage.vue、WorkbenchPage.vue、4 个 stores（auth/aiChat/context/studio）、1 个 API client.js。auth.js 保持 edu-cloud 多角色版本不替换。

3. **Re-export stubs 待清理**：Batch 2/3 留下的 re-export stubs（Task 22 清理）：
   - `models/`: exam.py, joint_exam.py, student.py, class_group.py, ai_session.py（5 个 stub）
   - `services/`: joint_exam_service.py, results_service.py, school_service.py, paper_service.py, calendar_service.py, notification_service.py, approval_service.py（7 个 stub）
   - `knowledge/`: store.py, loader.py（2 个 stub，目录整体删除）
   - 清理前用 Grep 确认无残留引用

4. **Alembic 现有 migration**：`alembic/versions/bdd523549077_initial_all_tables.py`，需删除后重新生成。无生产数据，直接 autogenerate。

5. **data/ 目录空**：edu-cloud 无 data/ 目录，exam-ai 也没有 data/ 目录。计划说迁入 seed 脚本（seed_demo.py, seed_knowledge_math.py, import_real_exam.py），需要确认 exam-ai 中这些文件的实际位置。如果不存在可跳过。

6. **exam-ai 测试**：78 个测试文件。迁入后需按 modules/ 结构重组，删除 sync 相关测试，批量替换 `from exam_ai.` → `from edu_cloud.modules.`。目标 ~680 tests。

7. **sync.py 和 sync_students.py 已删除**：Batch 2 删了 sync_students.py，Batch 3 删了 sync.py。Task 22 跳过这两个文件的删除。

8. **L014 风险**：Task 19 前端合并是大规模变更（14 页面 + 28K 卡片编辑器），属于 L014 警示范围。严格按 Task 步骤执行，`npm run build` 必须通过。

9. **Integration Review 要求**：这是最后一个 Batch，除了常规 code review 外，还需要 codex-review (integration) 检查跨批次一致性。

## 启动 Prompt

```
读取交接卡 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-23-platform-merge-batch5-handoff.md，然后读取计划文件 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-plan.md。

这是 T4 任务的执行会话。使用 executing-plans skill，从 Batch 5 Task 19 开始执行。

Batch 5 范围：Task 19（前端合并 — 14 页面 + 28K 卡片编辑器）→ Task 20（测试迁移 — exam-ai 78 测试文件）→ Task 21（Alembic 迁移 + Docker 更新）→ Task 22（清理 re-export stubs + 文档更新）。

关键约束：
- exam-ai 前端在 C:\Users\Administrator\exam-ai\exam-ai-frontend\src\（不是 exam-ai/frontend/）
- auth.js 保持 edu-cloud 多角色版本，aiChat.js 取 exam-ai 版本
- Task 22 清理 14 个 re-export stubs（5 models + 7 services + 2 knowledge），清理前 Grep 确认零残留引用
- Alembic: 删旧 migration 重新 autogenerate（无生产数据）
- sync.py 和 sync_students.py 已在 Batch 2/3 删除
- exam-ai 测试源码在 C:\Users\Administrator\exam-ai\tests\（78 文件）
- 测试基线 384 tests，目标 ~680 tests
- npm run build 必须通过

Batch 5 完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查（code + integration）。
```
