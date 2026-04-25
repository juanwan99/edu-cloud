---
type: handoff
created: 2026-03-23 10:39:49
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-plan.md
---

# exam-ai → edu-cloud 合并 Batch 3 交接卡

## Batch 2 完成状态

- **12 commits**: f539913..75d6c7d
- **GPT 审查**: R1 FAIL(3 test-gap) → R2 FAIL(2: schema+pipeline) → R3 FAIL(2 MED) → 修复后 PASS（4 轮）
- **测试基线**: 302 tests, all PASS
- **已完成**: Task 6-11c（Exam/Student/Card/Scan/Grading/Marking/Analytics/Bank/Profile/Pipeline/Knowledge/Studio/Calendar/Paper/Workspace/School/AI Session 全部 models+services 迁入 modules/）
- **迁入规模**: ~50 个新文件，~7,000 LOC

## 约束与偏好

**T4 流程** — Batch 3 完成后必须 codex-review (code)。

1. **sync_students.py 已删除**：计划 Task 14 说删除 `api/sync_students.py`，但 Batch 2 Task 11c 已经删除。执行时跳过此步骤。

2. **api/ai.py 不动**：`src/edu_cloud/api/ai.py` 是 AI Agent 路由，属于 Batch 4 (Task 16-18) 范围。Batch 3 不迁移此文件。

3. **Re-export stubs 已就位**：Batch 2 在 `models/`、`services/`、`knowledge/` 等旧位置建立了 re-export stub。Task 14 移动路由后，app.py 和路由文件的 import 应改为直接引用 `modules/` 路径。Task 22 才统一清理 stubs。

4. **api_key_hash 仍为 Optional**：`sync.py` 仍存在且依赖 api_key_hash。Task 14 删除 `sync.py` 时，api_key_hash 的必要性降低，但字段本身保留到 Batch 5 清理。

5. **llm_config_router 命名**：计划写 `llm_config_router.py`，但 PMR-009 已将内部逻辑改名为 `slot_selector.py`。路由文件命名根据实际 exam-ai 源码决定（检查 `C:\Users\Administrator\exam-ai\src\exam_ai\routes\` 下的实际文件名）。

6. **Batch 3 scope**: Task 12-15，共 4 个 Task。全部是 API 路由迁入/重组 + app factory 改造。

7. **测试策略**：Task 12 有完整测试契约（多租户隔离：school_id 注入 + 跨 school 越权 + 资源不存在）。每个迁入模块至少覆盖：成功路径 + 跨 school 越权 + 资源不存在。每个 Task 完成后跑 `python -m pytest --tb=short -q` 确认 302+ tests 不回归。

8. **exam-ai 源码路径**: `C:\Users\Administrator\exam-ai\src\exam_ai\routes\`

9. **风险矩阵 Batch 3 重点**：路由挂载（~107 端点），每个端点至少 1 个可达测试。

## 启动 Prompt

```
读取交接卡 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-23-platform-merge-batch3-handoff.md，然后读取计划文件 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-platform-merge-plan.md。

这是 T4 任务的执行会话。使用 executing-plans skill，从 Batch 3 Task 12 开始执行。

Batch 3 范围：Task 12（迁入 Exam/Student/Card/Scan 路由）→ Task 13（迁入 Grading/Marking/Analytics/Knowledge/Pipeline/LLMConfig 路由）→ Task 14（重组已有路由到模块 + 删除 sync）→ Task 15（App factory 改造 + Middleware 统一）。

关键约束：
- sync_students.py 已在 Batch 2 删除，Task 14 跳过此步骤
- api/ai.py 属于 Batch 4，不动
- 路由文件 import 应改为直接引用 modules/ 路径
- Task 12 测试契约：成功路径 + 跨 school 越权 + 资源不存在（多租户隔离验证）
- Task 14 删除 sync.py 后，api_key_hash 字段保留不删
- exam-ai 路由源码在 C:\Users\Administrator\exam-ai\src\exam_ai\routes\
- 测试基线 302 tests，每个 Task 后跑 python -m pytest --tb=short -q

Batch 3 完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
