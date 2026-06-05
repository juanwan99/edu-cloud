---
name: academic
status: experimental
owner: backend
layer: infrastructure

owns_tables:
  - semesters
  - time_periods
  - timetable_slots

owns_routes: []
structure_pattern: standard
max_router_loc: 300
routers: [router.py]

exposes:
  services: []
  events: []

depends_on:
  modules:
    - calendar
    - student
  services: []
  ai_tools: []

created: 2026-04-24
last_reviewed: 2026-04-24
design_docs:
  - docs/plans/2026-04-24-academic-infrastructure-plan.md
---

# academic 模块

## 职责
提供学校级学期、作息时段、课表基础数据，作为考试排期 / 选修走班 / 考勤等上层业务的时间轴底座。

## 边界
- **做什么**：Semester（学年+学期）/ TimePeriod（作息时段）/ TimetableSlot（班级课表）的 ORM 定义与后续 CRUD 服务
- **不做什么**：不负责考试调度本身（exam 模块用 Subject.exam_start/exam_end 字段记录具体考试时间）；不负责课程资源管理

## 使用方式
当前仅包含 ORM models，router/service 待后续 Task 添加。其他模块通过 `from edu_cloud.modules.academic.models import Semester, TimePeriod, TimetableSlot` 引用表定义。

## 数据流
学期/作息/课表数据由教务人员维护 → 本模块存储 → 考试模块、选修走班、课堂考勤等业务引用。

## 变更历史
- 2026-04-24: 新建模块，加入 Semester / TimePeriod / TimetableSlot 三个表。Subject 表同步增加 exam_start/exam_end/exam_room/proctor_ids 四个可空字段（由 exam 模块拥有）。
