---
name: grading
status: active
owner: backend
layer: business

owns_tables:
  - rubrics
  - grading_tasks
  - grading_results
  - grading_assignments
  - grading_quality_checks

owns_routes:
  - /api/v1/grading
structure_pattern: multi-router
max_router_loc: 1100
routers: [router.py, assignment_router.py, quality_router.py, grading_review_router.py]

exposes:
  services:
    - LLMClient
    - GradingAssignmentService
    - QualityCheckService
  events: []

depends_on:
  modules:
    - exam
    - scan
  services: []
  ai_tools: []

created: 2026-03-16
last_reviewed: 2026-04-16
design_docs:
  - docs/plans/2026-04-12-grading-dispatch-design.md
  - docs/plans/2026-03-16-ai-agent-design.md
---

# grading 模块

## 职责

AI 阅卷 + 人工校对 全链路：为主观题定义评分标准（Rubric）、生成阅卷任务、调用 LLM 打分、教师审核改分，最终维护单一权威分数源 `GradingResult`。

## 边界

- **做什么**：
  - Rubric（评分标准）CRUD
  - GradingTask（阅卷任务）生命周期管理：创建 → enqueue → 进度追踪 → 完成
  - GradingResult（单一权威评分记录）AI 生成、教师审核/改分/人工评分 共用同一表
  - GradingAssignment（阅卷任务分块分配到教师）按班别/科目分派，支持双阅
  - GradingQualityCheck（AI 判分质量抽样）报告
  - 阅卷调度中心 `/api/v1/grading/dispatch/status` 科目阶段聚合
- **不做什么**：
  - 选择题（客观题）判分 → 由 `scan` 在扫描阶段完成（`scan/objective_grading.py`）
  - 考后数据流水线（题库入库/错题收集/知识点掌握）→ `pipeline` 模块
  - Paper 写作 → `paper` 模块（外部服务客户端）

**注意**：marking 模块（教师手动阅卷工作流 `/api/v1/marking/*`）仅作为面向教师的 UI 入口，最终写入同一张 `GradingResult` 表。marking/models.py 不再持有任何模型（旧 MarkingScore/MarkingAssignment 已并入 grading）。

## GradingResult 状态机

```
ai_pending  →  ai_done  →  confirmed
                              ↑
                          (纯人工评分直接落)
```

- `status='ai_pending'`：AI 任务已建但未跑完（worker 成功前的瞬态，实际极少出现）
- `status='ai_done'`：AI 评分完成，等待教师审核。`final_score` 默认 = `ai_score`
- `status='confirmed'`：已确认；`source` 必填：
  - `ai`：教师 approve，`final_score == ai_score`
  - `ai_override`：教师改分，`final_score != ai_score`
  - `manual`：纯人工评分（`ai_score IS NULL`）

统一"有效分" = `GradingResult.final_score`（单一字段，无多层 fallback）；客观题自动判分则 fallback 到 `StudentAnswer.score`。

## 使用方式

### 外部 / 上游

- **前端 `GradingDispatchPage.vue`** → `GET /api/v1/grading/dispatch/status?exam_id=...` 获取各科目阅卷阶段
- **前端 `MarkingAssignPage.vue`** → `POST /api/v1/grading/assignments` 创建教师复核分派
- **外部调用代码**：
  - `workers/grading.py`: 使用 `grading.llm_client.LLMClient` 处理 AI 阅卷任务，写 `GradingResult(status='ai_done')`（arq worker）
  - `api/app.py`: 挂载 `grading.router` / `assignment_router` / `quality_router`
  - `ai/tools/grading_ops.py`: 导入 `GradingAssignmentService` / `QualityCheckService` 提供给 Agent
  - `modules/pipeline/service.py`: 读取 `GradingResult.final_score` 计算有效分
  - `modules/analytics/__init__.py`: 读取 `GradingResult.final_score` 做分析
  - `modules/marking/*`: 教师 UI 写入 `GradingResult`（AI 校对 或 纯人工）
  - `modules/exam/publish_service.py`: 读取 `GradingAssignment` + `GradingQualityCheck` 做发布前校验
  - `ai/workflow/w6_patrol.py`: 读取 `GradingTask` 做巡检

### 典型 API 使用

```bash
# 1. 创建评分标准
POST /api/v1/grading/rubrics  { "question_id": "...", "criteria": [...] }

# 2. 创建 AI 阅卷任务（前置校验 4 项）
POST /api/v1/grading/tasks    { "subject_id": "..." }

# 3. 查询阅卷进度
GET  /api/v1/grading/dispatch/status?exam_id=...

# 4. 教师审核（approve/override）
POST /api/v1/grading/review/{result_id}
  { "action": "approve" }
  { "action": "override", "adjusted_score": 6.0, "comment": "扣分原因" }
```

## 数据流

```
scan.StudentAnswer（学生答案切图 + 缺考标记）
       │
       ▼
grading.GradingTask.create
       │
       ▼  (arq worker: workers.grading.process_grading_task)
grading.LLMClient.grade  →  GradingResult(status=ai_done, ai_score, final_score=ai_score)
       │
       ▼
教师审核 POST /review/{id}
  approve  → status=confirmed, source=ai           (final_score 不变)
  override → status=confirmed, source=ai_override  (final_score=adjusted)
       │
       ▼
pipeline.service._get_effective_score → 读 GradingResult.final_score
```

纯人工阅卷路径（无 AI 预评）：教师通过 `/api/v1/marking/score` 直接写 `GradingResult(status=confirmed, source=manual, ai_score=None)`。

## 变更历史

- 2026-04-16: Phase 0-A 表合并 — `AIGradingResult` + `TeacherReview` + `MarkingScore` + `MarkingAssignment` 4 表合并为单一权威 `GradingResult` + `GradingAssignment`；禁止多版本并行
- 2026-04-12: `GET /api/v1/grading/dispatch/status` 接入，统一前端调度中心（grading-dispatch 设计）
- 2026-04-12: `POST /api/v1/grading/tasks` 新增 4 项前置校验（Subject 归属 / 主观题存在 / Rubric 存在 / StudentAnswer 存在），enqueue 失败清理 orphan task 返回 503
- 2026-03-16: 从 exam-ai 迁入 edu-cloud
