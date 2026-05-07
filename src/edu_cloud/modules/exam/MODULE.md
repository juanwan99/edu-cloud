---
name: exam
status: active
owner: backend
layer: business

owns_tables:
  - exams
  - subjects
  - questions
  - exam_results
  - joint_exams
  - joint_exam_participants
  - joint_exam_student_results

owns_routes:
  - /api/v1/exams
  - /api/v1/questions
  - /api/v1/joint-exams
  - /api/v1/joint-exams/{id}/results
  - /api/v1/workspace
  - /api/v1/llm-config
  - /api/v1/exams/{id}/publish
  - /api/v1/exams/{id}/archive
  - /api/v1/exams/{id}/schedule
structure_pattern: multi-router
max_router_loc: 500
routers: [router.py, joint_exam_router.py, results_router.py, workspace_router.py, llm_config_router.py]

exposes:
  services:
    - ExamPublishService
    - JointExamService
    - ResultsService
    - WorkspaceService
    - create_exam
    - get_exam
    - create_subject
    - get_llm_config
  events: []

depends_on:
  modules:
    - grading
    - pipeline
  services: []
  ai_tools:
    - get_exam_list (exams.py)
    - get_exam_detail (exams.py)
    - get_subject_questions (exams.py)
    - get_exam_overview (exam_overview.py)

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs: []
---

# exam 模块

## 职责

考试全生命周期管理：校内考试 CRUD（Exam/Subject/Question）、联考编排与下发（JointExam）、成绩发布/归档、LLM 槽位配置、工作台上下文。

## 边界

- **做什么**：考试/科目/题目 CRUD、考试状态机（draft→scanning→grading→reviewing→completed→published→archived）、联考生命周期（创建→下发→成绩汇总→强制截止）、LLM 模型槽位管理、考试排程、工作台上下文树
- **不做什么**：扫描切割（scan）、AI 阅卷（grading）、成绩统计分析（analytics）、答题卡生成（card）

## 使用方式

其他模块通过 import `edu_cloud.modules.exam.models` 引用 Exam/Subject/Question 表；外部通过 REST API `/api/v1/exams` 系列端点。ExamPublishService.publish 是成绩发布唯一入口，触发 pipeline 考后处理。

## 数据流

```
前端创建考试 → Exam(draft)
        → Subject/Question 配置
        → scan 扫描 → grading 阅卷 → Exam(completed)
        → ExamPublishService.publish → pipeline 考后计算 → Exam(published)
```
