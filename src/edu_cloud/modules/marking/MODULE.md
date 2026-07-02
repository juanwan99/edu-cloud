---
name: marking
status: active
owner: backend
layer: business

owns_tables: []

owns_routes:
  - /api/v1/marking
owns_services:
  - src/edu_cloud/services/marking_workflow.py
structure_pattern: standard
max_router_loc: 600
routers: [router.py]

exposes:
  services:
    - get_next_answer
    - submit_score
    - get_subjects_with_progress
    - get_progress
  events: []

depends_on:
  modules: []
  services:
    - marking_workflow
  ai_tools: []

created: 2026-03-16
last_reviewed: 2026-06-21
design_docs: []
---

# marking 模块

## 职责

教师人工阅卷工作流：逐份批改学生答卷，支持 AI 预测校对和纯人工评分。是 grading 模块的前端入口层。

## 边界

- **做什么**：
  - 教师逐份批改流程（取下一份 → 看图 → 打分 → 下一份）
  - 阅卷分配（管理员将题目分配给指定教师，含配额）
  - 阅卷进度统计和导出
  - 从文件夹导入切割好的答题图片
  - AI 复核模式（mode=ai_review，浏览 AI 已评但未确认的答卷）
- **不做什么**：
  - AI 阅卷任务管理 → `grading` 模块
  - 评分细则（Rubric）管理 → `grading` 模块
  - 选择题判分 → `scan` 模块

**注意**：marking 不持有任何 ORM 模型，所有数据写入 `grading.GradingResult` 表。`marking/models.py` 仅为空占位。

## 使用方式

### 典型 API 使用

```bash
# 1. 管理员分配阅卷任务
POST /api/v1/marking/assign  { "exam_id": "...", "question_id": "...", "teacher_id": "...", "answer_count": 50 }

# 2. 教师获取下一份待批改答卷（含 AI 预测）
GET  /api/v1/marking/next?question_id=...&mode=ungraded

# 3. 教师提交评分（自动返回下一份）
POST /api/v1/marking/score  { "answer_id": "...", "score": 8.0, "comment": "..." }

# 4. AI 复核模式：浏览 AI 已评答卷（仅管理员）
GET  /api/v1/marking/next?question_id=...&mode=ai_review

# 5. 查看阅卷进度
GET  /api/v1/marking/progress?exam_id=...

# 6. 导出成绩
GET  /api/v1/marking/export?exam_id=...
```

## 数据流

```
管理员 POST /assign → GradingAssignment（配额）
     │
     ▼
教师 GET /next → StudentAnswer（未 confirmed）+ GradingResult.ai_score（若有）
     │
     ▼
教师 POST /score → GradingResult(status=confirmed, source=ai|ai_override|manual)
     │
     ▼
GET /progress → 统计 GradingResult.status=='confirmed' 的数量
```

## 变更历史

- 2026-06-21（D-03K）: 阅卷工作流对 `exam` / `grading` / `scan` 的跨模块 ORM 模型
  （`Exam` / `Subject` / `Question` / `StudentAnswer` / `GradingAssignment` / `GradingResult`）
  与 grading 详情解析助手（`flatten_llm_details` / `parse_raw_content`）访问上移至模块外服务
  `services.marking_workflow`，marking（router/scorer/importer/exporter）不再直接 import
  上述 3 个模块，一次拆掉 `marking -> {exam, grading, scan}` 3 条直接依赖边。基线
  **35→32 edges、0 cycles 不变**（3 条边均不参与任何环；各目标模块仍有其它入边，不孤立）。
  `depends_on.modules` 清零（3→0）、`depends_on.services` 登记 `marking_workflow`；service 为
  纯 re-export facade（对外符号与 owner 模块同一对象），既有路由/打分/导入导出调用点与测试
  行为零变更，新增结构守护单测固定「marking 无直接目标模块 import + facade 纯 re-export」不变量。
- 2026-04-27: GET /next 增加 mode=ai_review 参数（浏览 AI 已阅答卷，仅管理员）
- 2026-04-16: MarkingScore/MarkingAssignment 合并入 grading.GradingResult/GradingAssignment
- 2026-03-16: 从 exam-ai 迁入 edu-cloud
