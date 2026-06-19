---
name: pipeline
status: active
owner: backend
layer: business

owns_tables: []

owns_routes:
  - /api/v1/pipeline
structure_pattern: standard
max_router_loc: 50
routers: [router.py]

exposes:
  services:
    - run_full_pipeline
    - populate_bank_questions
    - populate_error_books
    - generate_exam_snapshots
    - update_knowledge_mastery
    - update_error_patterns
  events: []

depends_on:
  modules: []
  services:
    - post_exam_adaptive
    - post_exam_bank_artifacts
    - post_exam_cold_data
  ai_tools: []

created: 2026-03-16
last_reviewed: 2026-04-13
design_docs:
  - docs/plans/2026-03-29-business-logic-backfill-design.md
  - docs/plans/2026-04-06-adaptive-learning-design.md
---

# pipeline 模块

## 职责

考试发布后的数据流水线对外 owner 命名空间：聚合生成考试快照、知识点掌握度、错误模式等冷数据。冷数据生成的 owner 逻辑（考试快照 / 知识点掌握度 / 错误模式 / 有效分权威规则 `_get_effective_score` / 一键编排 `run_full_pipeline`）已移出本模块，由模块外服务 `services.post_exam_cold_data` 承载（D-03I，经 pipeline.service re-export 保持导入与测试 patch 命名空间兼容）；题库/错题本制品（`BankQuestion` / `StudentErrorBook`）的读写由模块外服务 `services.post_exam_bank_artifacts` 承载（D-03H）；自适应学习 BKT 更新由模块外服务 `services.post_exam_adaptive` 承载（D-03E）。本模块自此不再直接 import `exam` / `scan` / `grading` / `knowledge` / `knowledge_tree` / `profile` / `student` —— 一次拆掉 7 条直接依赖边，`depends_on.modules` 清零。

## 边界

- **做什么**：
  - `run_full_pipeline(exam_id, school_id)` 一键执行 5 个 pipeline 自有冷数据阶段（adaptive BKT 更新已移至模块外服务，D-03E）
  - 单步函数：`populate_bank_questions` / `populate_error_books` / `generate_exam_snapshots` / `update_knowledge_mastery` / `update_error_patterns`
  - 订阅 `exam.published` EventBus 事件 → 自动触发流水线（在 `__init__.py` 注册 handler）
  - 有效分规则：`GradingResult.final_score`（单一权威值，含 AI/override/manual 统一来源）> `StudentAnswer.score`（客观题自动判分 fallback）
  - 幂等保证 DF-007：`try/except IntegrityError` 兜底重复写入
- **不做什么**：
  - 扫描切割流水线（前期处理）→ `scan` 模块的 `scan/pipeline_router.py`（命名近似但阶段完全不同）
  - AI 阅卷 → `grading` 模块
  - 成绩发布的前置校验 → `exam/publish_service.py`（`populate_bank_questions` 会被 publish 时调用）
  - 手动 AI 工具调用 → 通过 AI tool 间接使用本模块 services

## 使用方式

### 自动触发（EventBus）

当 `exam/service.py` 发布考试（`exam.published` 事件）后，本模块 `on_exam_published` handler 自动运行：
1. `update_knowledge_mastery` → `student_knowledge_mastery` 表
2. `update_error_patterns` → `student_error_patterns` 表
3. `services.post_exam_adaptive.update_adaptive_mastery` → `answer_logs` + `student_da_mastery` 表（模块外服务，失败不阻塞，D-03E）

### 手动触发（API）

```bash
POST /api/v1/pipeline/run/{exam_id}   # 管理员权限
```

### 外部调用

- 考后完整编排（冷数据 + adaptive BKT 更新 + analytics 预聚合）经模块外应用服务
  `services.post_exam_pipeline.run_post_exam_pipeline` 串联，pipeline 不再直接依赖 analytics（D-03B）/ adaptive（D-03E）
- `workers/grading.py`、`exam/service.py`（completed 触发）、`modules/pipeline/router.py`（手动 API）、
  `data/seed_demo.py`：均通过上述编排服务调用，不直接调 `run_full_pipeline`
- `exam/publish_service.py`: 发布前直接调用 `generate_exam_snapshots` 和 `populate_error_books` 冷数据单步

## 数据流

```
exam.Exam (completed/published) ─── event: exam.published ──▶ pipeline.on_exam_published
                                                                       │
         ┌─────────────────────────────────────────────────────────────┘
         ▼
pipeline.service（兼容 facade，零模块直接 import）re-export 模块外 owner：

冷数据 owner ◀── services.post_exam_cold_data（模块外，D-03I）读多模块数据：
  ├─ scan.StudentAnswer (答题切图 + 缺考标记)
  ├─ grading.GradingResult.final_score (单一权威评分源)
  ├─ exam.Subject + Question (题目元信息)
  ├─ knowledge.QuestionKnowledgePoint (知识点关联)
  ├─ knowledge_tree.ConceptGraphNode (知识点名称)
  └─ student.Student (班级映射)
         │
         ▼
       聚合写入 profile.StudentExamSnapshot + StudentKnowledgeMastery + StudentErrorPattern

bank.BankQuestion + StudentErrorBook (题库 + 错题本) ◀── services.post_exam_bank_artifacts（模块外，D-03H）
adaptive.AnswerLog + (BKT 更新 student_da_mastery) ◀── services.post_exam_adaptive（模块外，D-03E）
```

**本模块不拥有任何表，也不直接 import 任何依赖模块** — 所有读写对象与读写逻辑均归属模块外服务，pipeline 仅保留对外 owner 命名空间（re-export facade）。

## 变更历史

- 2026-06-19（D-03I）: 考后冷数据生成 owner 逻辑（`generate_exam_snapshots` / `update_knowledge_mastery` / `update_error_patterns`、有效分权威规则 `_get_effective_score` / `_get_effective_scores_for_subject`、一键编排 `run_full_pipeline`）上移至模块外服务 `services.post_exam_cold_data`（调用期局部 import exam/scan/grading/knowledge/knowledge_tree/profile/student 模型 + `services.student_identity` canonical 身份归一 + `services.post_exam_bank_artifacts` 制品函数）——pipeline 模块自此不再直接 import 上述 7 个冷数据模块，一次性消除 `pipeline -> {exam, grading, knowledge, knowledge_tree, profile, scan, student}` 7 条依赖边。基线 **48→41 edges、0 cycles 不变**（这 7 条边均不参与任何环；各目标模块仍有其它入边，不孤立）。pipeline MODULE.md `depends_on.modules` 清零（7→0），`depends_on.services` 删 `student_identity`（已移入 cold_data）、登记 `post_exam_cold_data`。`pipeline.service` 退化为纯 re-export facade（`_get_effective_score` / `_get_effective_scores_for_subject` / `generate_exam_snapshots` / `update_knowledge_mastery` / `update_error_patterns` / `run_full_pipeline` 经 cold_data re-export，`populate_bank_questions` / `populate_error_books` 经 bank_artifacts re-export）——既有调用点（exam `publish_service`、exam_import、编排服务 `services.post_exam_pipeline` / `services.exam_publish_pipeline`）与测试 patch（`pipeline.service.*` 命名空间）行为零变更；`services.post_exam_adaptive` / `services.post_exam_bank_artifacts` 对 `_get_effective_score` 的依赖改自 `services.post_exam_cold_data`（避免 services 反向 import pipeline.service）。返回契约、有效分权威规则、canonical 身份归一、幂等（DF-007）与非阻塞降级行为不变。
- 2026-06-18（D-03H）: 题库条目 `BankQuestion` 与学生错题本 `StudentErrorBook` 两类制品的读写（原 `populate_bank_questions` / `populate_error_books` / `_compute_question_stats`，以及 `update_error_patterns` 的错题本读查询）上移至模块外服务 `services.post_exam_bank_artifacts`（调用期局部 import bank/exam/scan/grading/knowledge 模型 + pipeline `_get_effective_score` 权威有效分规则）——pipeline 模块不再直接 import `edu_cloud.modules.bank`，消除 `pipeline -> bank` 依赖边。基线 **49→48 edges、0 cycles 不变**（该边不参与任何环；bank 仍有 conduct/homework 等入边，不孤立）。pipeline MODULE.md `depends_on.modules` 删 bank，`depends_on.services` 登记 `post_exam_bank_artifacts`；`populate_bank_questions` / `populate_error_books` 经 pipeline.service re-export 保持公共导入兼容（既有调用点 exam/exam_import/编排服务与测试 patch 命名空间不变），`update_error_patterns` 经错题本读模型聚合、`run_full_pipeline` 返回契约与幂等行为不变。
- 2026-06-18（D-03E）: adaptive BKT 掌握度更新（原 `_update_adaptive_mastery`）上移至模块外服务 `services.post_exam_adaptive.update_adaptive_mastery`，pipeline 不再直接 import `edu_cloud.modules.adaptive`，删除 `pipeline -> adaptive` 依赖边（51→50 edges、0 cycles 不变）。编排路径（`services.post_exam_pipeline`）与 `on_exam_published` event handler 改调该服务，`adaptive_mastery` 返回值、幂等、非阻塞降级与有效分权威规则不变；`run_full_pipeline` 自此只产 5 个冷数据步骤
- 2026-06-17（D-03B ask-fix）: 修复 D-03B 引入的 canonical 身份回归——`_get_effective_scores_for_subject` 此前按 raw `StudentAnswer.student_id` 分组，同一学生的 UUID 答题与条码答题被拆成两个 `StudentExamSnapshot`；现复用模块外共享 resolver `services.student_identity.resolve_student_identities`（与 analytics `get_effective_scores` 同一归一化规则），按 `canonical_student_id` 聚合。pipeline 仍不 import analytics，跨模块依赖边不变
- 2026-06-17: D-03B 核心解耦——`run_full_pipeline` 去掉 analytics 考后预聚合调用、`_get_effective_scores_for_subject` 改 pipeline 自有局部有效分查询；考后编排上移至模块外 `services.post_exam_pipeline`，删除 `pipeline -> analytics` 依赖边及其参与的 8 个环
- 2026-04-06: 接入 adaptive 模块 BKT 更新（`_update_adaptive_mastery`），失败降级为非阻塞（R5 finding）
- 2026-03-29: 从 exam-ai 迁入，拆分 6 个独立 service 函数
- 2026-03-16: 初始版本，含题库入库 + 错题收集 + 知识点掌握度
