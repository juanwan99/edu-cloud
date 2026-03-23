# Batch 2 Code Review Handoff

## 概要

**批次**: Batch 2 — Domain Models & Services（Task 6-11c）
**Commits**: `f539913..b8bdd05`（8 commits）
**计划**: `docs/plans/2026-03-22-platform-merge-plan.md` §Batch 2
**基线**: 281 tests (Batch 1) → 275 tests（删除 6 个 sync_students 测试，新增 5 个 exam 模块测试）

## 已完成 Task

| Task | 内容 | 关键文件 |
|------|------|---------|
| 6 | Exam 模块 — Exam/Subject/Question + ExamResult + JointExam 系列 + ExamService | `modules/exam/models.py`, `service.py`, `joint_exam_service.py`, `results_service.py` |
| 7 | Student 模块 — Class+ClassGroup 合并 + StudentService | `modules/student/models.py`, `service.py` |
| 8 | Card+Scan 模块 — Template/CardSkeleton + 13 card files + ScanTask/StudentAnswer | `modules/card/`, `modules/scan/` |
| 9 | Grading+Marking 模块 — 4 grading models + LLMClient + 3 marking services | `modules/grading/`, `modules/marking/` |
| 10 | Analytics+Bank+Profile+Pipeline — effective_score + 题库 + 画像 + 数据流水线 | `modules/analytics/`, `modules/bank/`, `modules/profile/`, `modules/pipeline/` |
| 11a | Knowledge 模块合并 — DB 模型 + service + store/loader 移动 | `modules/knowledge/` |
| 11b | Studio+Calendar 重组 — models+services 移入 modules/ | `modules/studio/`, `modules/calendar/` |
| 11c | Paper/Workspace/School/AI Session 重组 + sync_students 删除 | `modules/paper/`, `modules/school/`, `ai/models.py` |

## 架构决策

1. **Re-export stub 模式**：所有移动的 models/ 和 services/ 文件在旧位置留 re-export stub。API 路由（Batch 3）和 tests 仍通过旧路径导入，stub 透明转发。Task 22 统一清理。

2. **ClassGroup → Class alias**：`models/class_group.py` 导出 `Class as ClassGroup`。tablename 从 "class_groups" 变为 "classes"。测试使用 in-memory SQLite 不受影响，生产需 Alembic migration（Batch 5）。

3. **ExamResult 保留**：作为聚合视图移入 `modules/exam/models.py`，保持 `ai/tools/analytics.py` 和 `workspace_service.py` 不断裂。

4. **exceptions.py 方向**：canonical 仍留在 `services/exceptions.py`，`core/exceptions.py` 是 re-export。避免全局 import 链断裂。

5. **sync_students 删除**：路由 + 测试文件删除，app.py 取消注册。sync 功能在统一平台中废弃。

## 计划偏差

1. **Knowledge models 提前创建**：Task 10 的 pipeline/profile 依赖 KnowledgePoint，因此在 Task 10 中提前创建了 `modules/knowledge/models.py`，而非等到 Task 11a。

2. **Studio/Calendar models 保留原位**：models/document.py、models/approval.py 等仍保留原始定义（不是 stub），modules/studio/models.py 通过 re-export 聚合它们。这避免了改动 app.py 的 lifespan 大量 import。

3. **analytics/__init__.py 覆盖**：原 `modules/analytics/__init__.py` 是空文件，被替换为 `get_effective_scores()` 函数（从 exam-ai 迁入的核心评分逻辑）。

## 测试覆盖

- 新增 5 个测试：`tests/test_modules/test_exam/test_models.py`（CRUD + school_id 隔离 + ExamResult 保留）
- 删除 6 个测试：`tests/test_api/test_sync_students.py`（sync 废弃）
- 修改 6 个测试：`tests/test_services/test_paper_service.py`（patch 路径更新）
- 全量：275 tests passing

## 审查重点

1. **模型字段完整性**：exam-ai 的 TenantMixin(school_id) 是否都替换为显式 `school_id: Mapped[str] = mapped_column(..., ForeignKey("schools.id"))`
2. **Import 链**：re-export stub 是否完整覆盖所有需要的导出名（Batch 1 R1 的 APPROVAL_CHAINS 遗漏教训）
3. **data_pipeline.py**（567 LOC）：最复杂的迁入文件，5 个流水线步骤的 import 路径是否都正确更新
4. **Card 模块 13 文件**：sed 批量替换是否遗漏了非标准 import 模式
5. **Student.class_id FK 变更**：从无 FK 变为 `ForeignKey("classes.id")`，是否影响现有 fixtures
