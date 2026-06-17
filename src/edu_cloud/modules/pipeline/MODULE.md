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
  modules:
    - bank
    - adaptive
    - exam
    - grading
    - knowledge
    - knowledge_tree
    - profile
    - scan
    - student
  services:
    - student_identity
  ai_tools: []

created: 2026-03-16
last_reviewed: 2026-04-13
design_docs:
  - docs/plans/2026-03-29-business-logic-backfill-design.md
  - docs/plans/2026-04-06-adaptive-learning-design.md
---

# pipeline 模块

## 职责

考试发布后的数据流水线：读取 scan/grading 产出的学生答题和判分，聚合生成题库条目、错题本、考试快照、知识点掌握度、错误模式、自适应学习 BKT 更新。

## 边界

- **做什么**：
  - `run_full_pipeline(exam_id, school_id)` 一键执行 6 个阶段的完整数据生成
  - 单步函数：`populate_bank_questions` / `populate_error_books` / `generate_exam_snapshots` / `update_knowledge_mastery` / `update_error_patterns` / `_update_adaptive_mastery`
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
3. `_update_adaptive_mastery` → `answer_logs` + `student_da_mastery` 表（失败不阻塞）

### 手动触发（API）

```bash
POST /api/v1/pipeline/run/{exam_id}   # 管理员权限
```

### 外部调用

- 考后完整编排（冷数据 + analytics 预聚合）经模块外应用服务
  `services.post_exam_pipeline.run_post_exam_pipeline` 串联，pipeline 不再直接依赖 analytics（D-03B）
- `workers/grading.py`、`exam/service.py`（completed 触发）、`modules/pipeline/router.py`（手动 API）、
  `data/seed_demo.py`：均通过上述编排服务调用，不直接调 `run_full_pipeline`
- `exam/publish_service.py`: 发布前直接调用 `generate_exam_snapshots` 和 `populate_error_books` 冷数据单步

## 数据流

```
exam.Exam (completed/published) ─── event: exam.published ──▶ pipeline.on_exam_published
                                                                       │
         ┌─────────────────────────────────────────────────────────────┘
         ▼
pipeline 读取多模块数据：
  ├─ scan.StudentAnswer (答题切图 + 缺考标记)
  ├─ grading.GradingResult.final_score (单一权威评分源)
  ├─ exam.Subject + Question (题目元信息)
  ├─ knowledge.QuestionKnowledgePoint (知识点关联)
  └─ student.Student (班级映射)
         │
         ▼
聚合写入：
  ├─ bank.BankQuestion + StudentErrorBook (题库 + 错题本)
  ├─ profile.StudentExamSnapshot + StudentKnowledgeMastery + StudentErrorPattern
  └─ adaptive.AnswerLog + (BKT 更新 student_da_mastery)
```

**本模块不拥有任何表** — 所有读写对象归属于依赖模块。

## 变更历史

- 2026-06-17（D-03B ask-fix）: 修复 D-03B 引入的 canonical 身份回归——`_get_effective_scores_for_subject` 此前按 raw `StudentAnswer.student_id` 分组，同一学生的 UUID 答题与条码答题被拆成两个 `StudentExamSnapshot`；现复用模块外共享 resolver `services.student_identity.resolve_student_identities`（与 analytics `get_effective_scores` 同一归一化规则），按 `canonical_student_id` 聚合。pipeline 仍不 import analytics，跨模块依赖边不变
- 2026-06-17: D-03B 核心解耦——`run_full_pipeline` 去掉 analytics 考后预聚合调用、`_get_effective_scores_for_subject` 改 pipeline 自有局部有效分查询；考后编排上移至模块外 `services.post_exam_pipeline`，删除 `pipeline -> analytics` 依赖边及其参与的 8 个环
- 2026-04-06: 接入 adaptive 模块 BKT 更新（`_update_adaptive_mastery`），失败降级为非阻塞（R5 finding）
- 2026-03-29: 从 exam-ai 迁入，拆分 6 个独立 service 函数
- 2026-03-16: 初始版本，含题库入库 + 错题收集 + 知识点掌握度
