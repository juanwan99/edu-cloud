---
name: exam_import
status: active
owner: backend
layer: business

owns_tables:
  - exam_import_sessions

owns_routes:
  - /api/v1/exam-imports

structure_pattern: standard
max_router_loc: 400
routers:
  - router.py

exposes:
  services:
    - match_students
    - commit_import
    - run_post_import_pipeline
  events: []

depends_on:
  modules: []
  services:
    - exam_import_materialization
  ai_tools: []

created: 2026-05-19
last_reviewed: 2026-06-21
design_docs:
  - docs/plans/archived/2026-05/2026-05-19-exam-import-pipeline-design.md
---

# exam_import 模块

## 职责

导入外部考试 Excel/ZIP 成绩数据，完成文件解析、学生匹配、考试写入、导入会话追踪和导入后画像/错题流水线处理。

## 边界

- **做什么**：上传并解析外部成绩文件、预览学生匹配、确认映射、写入 Exam/Subject/Question/StudentAnswer/GradingResult/ExamResult 链路、记录导入状态、触发导入后 pipeline。
- **不做什么**：考试常规 CRUD（exam）、扫描切割（scan）、AI 阅卷调度（grading）、学情统计报表（analytics）、学生基础档案维护（student）。

## 使用方式

前端通过 `/api/v1/exam-imports` 完成上传、映射、提交、查询和取消；其他模块不应直接调用 router，必要时只调用 `service.match_students`、`service.commit_import` 或 `service.run_post_import_pipeline`。

## 数据流

```
上传 xlsx/zip
  -> parser 解析 ParsedExamData
  -> match_students 匹配 student
  -> commit_import 写入 exam/scan/grading 相关表
  -> run_post_import_pipeline 生成 snapshot/error_book/error_pattern
  -> ExamImportSession 记录状态和结果
```

## 变更历史

- 2026-06-21（D-03J）: 学生匹配 + 写入链 + 导入后流水线 owner 逻辑（`match_students` /
  `commit_import` / `run_post_import_pipeline` 及私有 upsert 助手）上移至模块外服务
  `services.exam_import_materialization`，exam_import 不再直接 import
  `exam` / `grading` / `pipeline` / `profile` / `scan` / `student`，一次拆掉 6 条直接依赖边。
  `service.py` 退化为纯 re-export facade，`depends_on.modules` 清零（6→0）、
  `depends_on.services` 登记 `exam_import_materialization`；router 调用点与测试行为零变更。
- 2026-06-04: 补齐 MODULE.md，登记表/路由/服务/依赖边界，纳入模块治理聚合。
- 2026-05-19: 新增外部考试导入模块。
