---
name: profile
status: active
owner: backend
layer: business

owns_tables:
  - student_exam_snapshots
  - student_knowledge_mastery
  - student_error_patterns

owns_routes:
  - /api/v1/profile
structure_pattern: standard
max_router_loc: 150
routers: [router.py]

exposes:
  services:
    - get_student_trend
    - get_student_knowledge_map
    - get_student_error_pattern
    - get_class_knowledge_weakness
    - student_ai_diagnosis
  events: []

depends_on:
  modules:
    - knowledge_tree
  services: []
  ai_tools:
    - ai/tools/profile.py
    - ai/tools/student_diagnosis.py
    - ai/tools/student_profile_tool.py

created: "2026-05-05"
last_reviewed: "2026-06-17"
design_docs: []
---

# profile 模块

## 职责

学生学情画像查询：成绩趋势（历次考试快照）、知识点掌握度（per concept 维度）、错误模式分析（per subject 维度）、班级薄弱知识点 TOP-N、个体 AI 诊断（模板拼接，ORC-007 不调 LLM）。

## 边界

- **做什么**：查询 student_exam_snapshots/student_knowledge_mastery/student_error_patterns 三张表的聚合数据；班级维度薄弱知识点聚合（avg mastery 排序）；个体 AI 诊断端点（profile 自有 `diagnosis_service`，模板拼接 ORC-007，仅消费上述三表，D-03A 已从 analytics 迁回，无跨模块依赖）
- **不做什么**：数据写入由 `pipeline` 模块负责（考试发布后自动生成）；Student 实体管理由 `student` 模块负责

## 使用方式

```bash
GET /api/v1/profile/students/{id}/trend           # 成绩趋势（subject_code 过滤）
GET /api/v1/profile/students/{id}/knowledge       # 知识点掌握度（course_code 过滤）
GET /api/v1/profile/students/{id}/error-patterns  # 错误模式（subject_code 过滤）
GET /api/v1/profile/class/weakness                # 班级薄弱 TOP N（需 class_id）
GET /api/v1/profile/students/{id}/ai-diagnosis    # AI 诊断（模板拼接）
```

## 数据流

```
pipeline (exam.published) → 写入 student_exam_snapshots + student_knowledge_mastery + student_error_patterns
profile service → 读取上述三表 + join ConceptGraphNode（课程过滤）
AI tools → get_student_trend / knowledge_map / weakness / error_pattern / diagnosis / learning_profile
前端 AnalyticsPage → 调用 profile API 展示学生画像
```
