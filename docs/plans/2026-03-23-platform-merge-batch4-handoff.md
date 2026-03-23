---
type: handoff
created: 2026-03-23 12:17:11
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-plan.md
---

# exam-ai → edu-cloud 合并 Batch 4 交接卡

## Batch 3 完成状态

- **3 commits**: 723505c..19cf399
- **GPT 审查**: R1 FAIL → R2 FAIL → R3 PASS（3 轮）
- **测试基线**: 332 tests, all PASS
- **已完成**: Task 12-15（18 个路由文件迁入 modules/、6 个旧路由 re-export stubs、sync.py 删除、app factory 统一挂载 118 routes）

## 约束与偏好

**T4 流程** — Batch 4 完成后必须 codex-review (code)。

1. **edu-cloud ai/ 已有文件**：edu-cloud 的 `ai/` 目录在 P0-P4 阶段已建立了基础版本：agent.py, llm.py, context.py, schemas.py, anonymizer.py, audit.py, registry.py, models.py。计划要求用 exam-ai 更完整的版本**替换**部分文件（agent.py ← loop.py, llm.py, context.py），不是追加。替换前先对比两边内容，保留 edu-cloud 独有的功能（如 school_id 注入）。

2. **exam-ai Agent 源码路径**：`C:\Users\Administrator\exam-ai\src\exam_ai\agent\`（loop.py, llm.py, context.py, schemas.py, anonymizer.py, audit.py）。工具在 `agent/tools/`（7 个文件：analytics_compare, analytics_score, bank, exams, knowledge, profile, students）。

3. **exam-ai 路由源码**：`C:\Users\Administrator\exam-ai\src\exam_ai\api\ai.py`（228 LOC，含 session CRUD）。

4. **exam-ai Workers 源码**：`C:\Users\Administrator\exam-ai\src\exam_ai\workers\grading.py`。

5. **knowledge_db.py 不在 exam-ai 中**：计划说创建 `ai/tools/knowledge_db.py`（L3_knowledge_db），但 exam-ai 没有此文件。可能需要基于 `modules/knowledge/models.py`（Batch 2 Task 11a 创建）新写，或从 exam-ai 的 `knowledge.py` 工具中拆分 DB 查询部分。执行时先对比 exam-ai 和 edu-cloud 的 knowledge.py，确定内容来源。

6. **ROLE_TOOL_CATEGORIES 在 agent.py**：PMR-001 已确认此常量定义在 `ai/agent.py` 而非 `permissions.py`。更新时按设计文档 §5.2 的 9 类别映射。

7. **edu-cloud 独有文件保留**：`ai/registry.py`、`ai/models.py`、`ai/audit.py` 是 edu-cloud P0-P4 产出，exam-ai 可能也有 audit.py。合并时保留更完整的版本。

8. **api/ai.py 位置**：Batch 3 保留了 `api/ai.py` 在原位。Task 16 Step 2 合并后，此文件应移到 `modules/` 还是保留在 `api/`，根据计划决定（计划写的是 Modify `api/ai.py`，不是 Move）。

9. **测试策略**：Task 17 验证每个角色可访问的工具数量正确。Worker 测试 mock Redis。每个 Task 后跑 `python -m pytest --tb=short -q` 确认 332+ tests 不回归。

## 启动 Prompt

```
读取交接卡 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-23-platform-merge-batch4-handoff.md，然后读取计划文件 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-plan.md。

这是 T4 任务的执行会话。使用 executing-plans skill，从 Batch 4 Task 16 开始执行。

Batch 4 范围：Task 16（AI Agent 合并 — 替换 agent core + 合并路由）→ Task 17（AI 工具合并 — 迁入 7 工具 + 更新 RBAC）→ Task 18（Workers 合并 — grading worker + pipeline 任务注册）。

关键约束：
- edu-cloud ai/ 已有基础版本，用 exam-ai 更完整版本替换（不是追加），保留 edu-cloud 独有功能
- exam-ai Agent 源码在 C:\Users\Administrator\exam-ai\src\exam_ai\agent\
- exam-ai 路由在 C:\Users\Administrator\exam-ai\src\exam_ai\api\ai.py
- exam-ai Workers 在 C:\Users\Administrator\exam-ai\src\exam_ai\workers\grading.py
- knowledge_db.py 不在 exam-ai 中，需基于 modules/knowledge/models.py 新写或从 exam-ai knowledge.py 拆分
- ROLE_TOOL_CATEGORIES 在 agent.py 不在 permissions.py（PMR-001）
- 测试基线 332 tests，每个 Task 后跑 python -m pytest --tb=short -q

Batch 4 完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
