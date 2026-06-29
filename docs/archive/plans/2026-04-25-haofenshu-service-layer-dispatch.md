---
baseline_command: "cd ~/projects/edu-cloud && .venv/bin/python -m pytest --collect-only -q"
baseline_verified_at: "2026-04-25 22:30"
baseline_count: 2215
---

# 好分数业务逻辑吸收 — 服务层批量执行派发

**Date**: 2026-04-25
**Strategy**: 跳过 S1 剩余数据层（S1-B/S1-D），直接在现有 schema 上构建业务服务+前端
**Scope**: 5 个 T2 级独立工作包，全部可并行

---

## 现有基础设施（已验证）

| 资产 | 状态 | 证据 |
|------|------|------|
| bank_question 扩展字段 | S1-A 完成 | source/explanation/knowledge_point_ids/difficulty_level/tags/bloom_level |
| Grade 独立表 | S1-C 完成 | grades(school_id, name, grade_level, xueduan, sort_order) |
| TeachingPlan 骨架 | S1-C 完成 | teaching_plans(school_id, subject_code, grade_id, semester, weeks_json) |
| PaperAccessLevel 枚举 | S1-C 完成 | paper/constants.py |
| homework CRUD | 12 端点 | create/list/get/update/publish/close/delete/submissions/grade |
| bank 端点 | 4 端点 | questions list/detail + error-book/stats |
| profile 端点 | 5 端点 | trend/knowledge/error-patterns/weakness/ai-diagnosis |
| analytics | 29 端点 | 全维度分析已完成 |
| adaptive | BKT 引擎 | diagnose_and_recommend + path_planner + question_selector |

---

## 工作包清单

### WP-A: 题库搜索与智能筛选

**目标**: 让教师能按知识点/难度/题型/来源搜索题库，支持组卷选题基础能力
**对标好分数**: B 轴 Gap#1（题库+组卷生态）的第一步

**后端**:
- `bank/service.py` 新增 `search_questions()` — 支持 knowledge_point_ids / difficulty_level / question_type / source / tags 多维筛选 + 全文搜索
- `bank/router.py` 新增 `GET /api/v1/bank/questions/search` — 分页 + 多条件过滤
- `bank/router.py` 新增 `GET /api/v1/bank/questions/stats/overview` — 题库统计概览（按题型/难度/来源分组）

**前端**:
- 增强 `ErrorBookPage.vue` 或新建 `QuestionBankPage.vue` — 搜索栏 + 筛选面板 + 结果列表
- 路由 `/question-bank` + 侧边栏挂载

**测试**: 3-5 个 service 单测 + 2 个 API 测试

---

### WP-B: 错题→知识点→推荐练习联动

**目标**: 打通"错题本→知识聚合→智能推荐→重做"闭环
**对标好分数**: C 轴 Gap#2（错题→推荐资源完整流程）

**后端**:
- `bank/service.py` 新增 `get_error_knowledge_summary(student_id)` — 按知识点聚合错题，返回薄弱知识点 TOP N
- `bank/service.py` 新增 `get_recommended_practice(student_id)` — 调用 adaptive.diagnose_and_recommend 获取推荐题目
- `bank/router.py` 新增:
  - `GET /api/v1/bank/error-book/{student_id}/knowledge-summary` — 错题知识聚合
  - `GET /api/v1/bank/error-book/{student_id}/recommendations` — 推荐练习题

**前端**:
- `ErrorBookPage.vue` 增加"知识薄弱点"统计卡 + "推荐练习"Tab
- 推荐题目点击→跳转到题目详情或直接展示

**测试**: 3 个 service 单测 + 2 个 API 测试

---

### WP-C: 作业考后推送 + 内容增强

**目标**: 考试发布后自动生成针对性作业（基于错题分析），丰富作业内容结构
**对标好分数**: C 轴 Gap#1（作业内容编辑闭环）+ C 轴（精准教学推送）

**后端**:
- `homework/service.py` 新增 `create_remedial_task(exam_id, class_id)` — 基于考试错题分析自动生成补救作业
  - 读取 analytics 错题数据 → 筛选高错误率题目 → 从 bank 匹配同知识点题目 → 创建作业
- `homework/service.py` 新增 `get_task_content_detail(task_id)` — 返回作业关联的题目详情（从 bank 读取）
- `homework/router.py` 新增:
  - `POST /api/v1/homework/tasks/from-exam` — 考后一键生成补救作业
  - `GET /api/v1/homework/tasks/{id}/content-detail` — 作业题目详情

**前端**:
- `HomeworkPage.vue` 增加"考后推送"入口按钮（选择考试→选择班级→预览错题→一键生成）
- 作业详情增加题目列表展示（而不只是纯文本 content）

**测试**: 4 个 service 单测 + 2 个 API 测试

---

### WP-D: 年级聚合分析 + 考情趋势

**目标**: 基于 Grade 表提供年级维度统计，增加跨考试的考情趋势追踪
**对标好分数**: D 轴 Gap#1（年级聚合）+ B 轴 Gap#3（考情分析）

**后端**:
- `analytics/grade_service.py` 新建 — 年级级别聚合
  - `get_grade_overview(school_id, grade_id)` — 年级各班均分/及格率/优秀率对比
  - `get_grade_exam_trend(school_id, grade_id)` — 年级历次考试趋势
  - `get_grade_subject_comparison(school_id, grade_id, exam_id)` — 年级各科对比
- `analytics/router.py` 新增:
  - `GET /api/v1/analytics/grade/{grade_id}/overview`
  - `GET /api/v1/analytics/grade/{grade_id}/trend`
  - `GET /api/v1/analytics/grade/{grade_id}/subjects`

**前端**:
- `AnalyticsTrendPage.vue` 增加"年级维度"Tab（Grade 选择器 + 年级对比图表）
- 或新建 `GradeAnalyticsPage.vue`

**测试**: 3 个 service 单测 + 3 个 API 测试

---

### WP-E: 教学计划 CRUD + 前端管理页

**目标**: 让教师能创建和管理教学计划（学期→周次→知识点映射）
**对标好分数**: C 轴 Gap#6（教学计划管理）

**后端**:
- `modules/calendar/teaching_plan_service.py` 新建（或独立 teaching_plan module）
  - `create_plan(school_id, subject_code, grade_id, semester, weeks_json, created_by)`
  - `list_plans(school_id, filters)` — 支持按学期/科目/年级过滤
  - `get_plan(plan_id)` — 详情含 weeks 展开
  - `update_plan(plan_id, weeks_json)` — 更新周次内容
  - `delete_plan(plan_id)`
- 路由挂载到 `academic` router:
  - `POST/GET /api/v1/academic/teaching-plans`
  - `GET/PATCH/DELETE /api/v1/academic/teaching-plans/{id}`

**前端**:
- 新建 `TeachingPlanPage.vue` — 学期/科目选择 + 周次时间轴/表格编辑
- 路由 `/academic/teaching-plans` + 侧边栏挂载

**测试**: 5 个 service 单测 + 3 个 API 测试

---

## 执行约束

- 每个 WP 独立 T2 scope，不跨模块建依赖
- TDD-lite：先写 1-3 个失败测试，再实现
- 改完跑 `pytest --tb=short -q` 确认不新增 fail
- 前端改完跑 `npx vitest run` + `npx vite build`
- commit 后 `git diff --stat` 确认无计划外文件
