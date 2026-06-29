<!-- INVALID: 资产盘点错误 — plan 声称页面"❌不存在"但实际全部已存在（commit 400fb5d, 07:11）。
     基于错误前提执行的代码已产生功能降级（ErrorBookPage 等）。2026-04-26 审计废弃。 -->
---
baseline_command: "cd /home/ops/projects/edu-cloud/frontend && npx vite build"
baseline_verified_at: "2026-04-26T18:55:12+08:00"
baseline_count: "6235 modules transformed, 61 JS chunks, built in 20s"
---

# 前端模块补全计划

> 状态: **废弃（资产盘点错误）** | 创建: 2026-04-26 | 废弃: 2026-04-26 审计

## 背景

侧边栏已从 20+ 平铺菜单重构为 6 组嵌套结构（概览/考试阅卷/教研教学/教务管理/学生管理/学校管理），
路由和德育/分析/知识图谱页面已解冻。但多个模块后端 API 已就绪、前端页面缺失。

## 现有资产盘点

| 模块 | 后端端点 | 后端注册 | 前端 API client | 前端页面 | 前端路由 |
|------|---------|---------|----------------|---------|---------|
| homework | 10 端点(CRUD+提交+批改+统计) | app.py ✅ | ❌ | ❌ | ❌ |
| academic/semester | 5 端点(CRUD+激活) | app.py ✅ | ❌ | ❌ | ❌ |
| academic/timetable | 3 端点(查/存/统计) | app.py ✅ | ❌ | ❌ | ❌ |
| academic/period | 2 端点(查/批量替换) | app.py ✅ | ❌ | ❌ | ❌ |
| calendar | 3 端点(创建/列表/删除) | app.py ✅ | ❌ | CalendarPanel 85 行(非独立页) | 占位→DashboardPage |
| bank/questions | 2 端点(列表/详情) | app.py ✅ | ❌ | ❌ | ❌ |
| bank/error-book | 2 端点(列表/统计) | app.py ✅ | ❌ | ❌ | ❌ |
| joint-exams | 7 端点(CRUD+参与校+下发) | app.py ✅ | ❌ | ❌ | ❌ |
| dashboard | 1 端点(summary 6 字段) | app.py ✅ | 内联调用 | 102 行(KPI+Widget+硬编码 Activity) | ✅ |

## 增量 vs 新建论证

全部为新建前端���面，消费已有的后端 API。不涉及新建后端模块或平行系统。
已有后端 API 全部在 app.py 中注册并通过测试（2102 passed）。

## 交付路径

nginx 443 → `frontend/dist/` → 用户浏览器（`https://mcu.asia`）。
每个 Task 完成后必须 `cd frontend && npx vite build`。

---

## Batch 1: 基础活化（让已有的东西先有用）

### T1: 概览页角色化改造

**目标**: DashboardPage 按角色显示不同 KPI 和 Widget，替换硬编码 Activity Feed。

**现状调研**:
- `dashboardConfig.js` 已有 10 角色完整配置(KPI+Widget)，每角色 4 KPI + 3-4 Widget
- `DashboardPage.vue` 102 行，`getKpiValue()` 只识别 `dashboard_summary` source，其他返回 `--`
- 后端 `GET /dashboard/summary` 仅返回 6 字段: total_students, total_classes, total_exams, total_staff(null), pending_subjects(null), pending_grading(0)
- Activity Feed 硬编码 1 条占位文本
- 后端 `dashboard.py` 位于 `src/edu_cloud/api/dashboard.py`，scope 过滤逻辑已有(get_visible_class_ids)

**实施步骤**:
1. **后端** `dashboard.py` 补齐返回字段:
   - `total_staff`: 查 users 表 count (school_id 过滤)
   - `pending_grading`: 查 grading_tasks WHERE status='pending' (school_id 过滤)
   - `pending_subjects`: 查 grading dispatch status 中 stage != 'done' 的科目数
2. **前端** DashboardPage.vue:
   - `getKpiValue()` 统一走 `kpiData.value[kpi.id]`（去掉 source 判断，后端一个接口返回全部）
   - Activity Feed: 调 `GET /exams?limit=5` 渲染最近考试事件列表（替换硬编码）
   - 确认 Widget 卡片的 route 与新路由表一致
3. **build + 验证**: platform_admin / academic_director / subject_teacher / homeroom_teacher 四角色

**文件清单**: `src/edu_cloud/api/dashboard.py` (后端) + `frontend/src/pages/DashboardPage.vue` (前端)

### T2: 校历管理页

**目标**: 独立 CalendarPage 替换占位，支持事件 CRUD + 月份筛选。

**现状调研**:
- 后端 3 端点: `POST /calendar/events` (创建+通知规则) / `GET /calendar/events?start=&end=` (列表) / `DELETE /calendar/events/{id}` (软删除)
- CalendarEvent 模型: type(holiday/exam/parent_meeting/deadline) + title + event_date + description + semester + notification_rules(1:N)
- CalendarPanel.vue 85 行: 有创建弹窗+事件列表，**无删除 UI、无日期过滤、无 description/semester 输入**
- 路由 `/calendar` 当前指向 DashboardPage(占位)
- 权限: 创建/删除需 `GENERATE_NOTIFICATION`，列表所有已登录用户可看

**实施步骤**:
1. 新建 `frontend/src/api/calendar.js`: getEvents(params) / createEvent(data) / deleteEvent(id)
2. 新建 `frontend/src/pages/CalendarPage.vue`:
   - 顶部: 月份选择器(上月/下月) + 新增事件按钮
   - 主体: 事件列表(类型标签+标题+日期+描述)，按日期分组
   - 每条事件: 删除按钮(带 NPopconfirm 确认)
   - 创建弹窗: 类型+标题+日期+描述+学期+提前通知天数
   - 加载时传 start/end 参数按当月过滤
3. 路由 `/calendar` 改指向 CalendarPage
4. build + 验证

**文件清单**: `frontend/src/api/calendar.js` (新) + `frontend/src/pages/CalendarPage.vue` (新) + `frontend/src/router/index.js` (改路由)

### T3: 侧边栏补齐菜单占位

**目标**: 把 Batch 2-4 的所有菜单项提前加入侧边栏，路由指向通用占位页，用户能看到完整导航骨架。

**实施步骤**:
1. 新建 `frontend/src/pages/ComingSoonPage.vue`: 简单提示"功能开发中，敬请期待"
2. `sidebarConfig.js` 添加菜单项:
   - 教研教学: 作业管理(perm: view_homework) / 题库管理(perm: view_question_bank) / 错题本(perm: view_scores)
   - 教务管理: 学期管理(perm: manage_scheduling) / 课程表(perm: manage_scheduling)
   - 学校管理: 联考管理(perm: view_joint_exam)
3. `router/index.js` 添加 6 条路由，全部指向 ComingSoonPage
4. build + 验证侧边栏各角色显示正确

**文件清单**: `frontend/src/pages/ComingSoonPage.vue` (新) + `frontend/src/config/sidebarConfig.js` (改) + `frontend/src/router/index.js` (改)

---

## Batch 2: 教师日常工作流

### T4: 作业管理页

**后端 API ���研** (homework/router.py 255 行, service.py 290 行):
- 10 端点: Task CRUD(7) + Submission(3) + Stats(1)
- 模型: HomeworkTask(title/task_type/subject_code/class_id/deadline/status/content/grading_mode) + HomeworkSubmission(student_id/status/score/feedback)
- 状态机: draft → active(publish) → expired/closed; 提交: pending → submitted → graded
- 权限: MANAGE_HOMEWORK(创建/批改) / VIEW_HOMEWORK(查看)

**实施步骤**:
1. 新建 `frontend/src/api/homework.js` (12 函数)
2. 新建 `frontend/src/pages/HomeworkPage.vue`:
   - 列表: 作业卡片(标��/科目/班级/截止日期/状态标签/提交率进度条)
   - 创建抽屉: 表单(标题/类型select/科目/班级/截止日期/内容textarea)
   - 详情面板: 作业信息 + 提交列表表格 + 统计卡片(提交率/均分/待批改)
   - 批改: 行内打分(NInputNumber) + 反馈(NInput)
3. 路由 `/homework` 替换 ComingSoonPage

### T5: 课程表页

**后端 API 调研** (academic/router.py 191 行, service.py 267 行):
- Timetable: GET(查) + PUT(存) + GET stats; Period: GET(查) + PUT(批量替换)
- TimetableSlot 模型: weekday(1-7) + period_id + subject_code + teacher_id + room
- TimePeriod 模型: period_number + name + start_time + end_time + period_type(class/break/activity)
- 冲突检查: ��教师同时段不能有两个班

**实施步骤**:
1. 新建 `frontend/src/api/academic.js` (10 函数: semester 5 + period 2 + timetable 3)
2. 新建 `frontend/src/pages/TimetablePage.vue`:
   - 周视图网格: 行=时段, 列=周一至周五, 单元格=科目+教师
   - 顶部切���: 按班级 / 按教师
   - 编辑模式: 点击单元格选择科目+教师(NSelect)
   - 保存按钮: 调 PUT /timetable/{class_id}
3. 路由 `/timetable` 替换 ComingSoonPage

### T6: 学期管理页

**后端 API 调研**:
- 5 端点: CRUD + activate; Semester 模型: name/school_year/term(1|2)/start_date/end_date/is_current
- 唯一约束: (school_id, school_year, term); 激活时其他学期自动停用

**实施步骤**:
1. 复用 `api/academic.js`
2. 新建 `frontend/src/pages/SemesterPage.vue`:
   - 表格: 名称/学年/学期/日期范围/当前标签
   - 创建弹窗
   - 激活按钮(带确认提示: "切换当前学期将停用其他学期")
3. 路由 `/semesters` 替换 ComingSoonPage

---

## Batch 3: 教研 + 校级管理

### T7: 题库管理页

**后端 API 调研** (bank/router.py, service.py):
- 2 端点: GET /bank/questions (列表,支持 question_type/difficulty 过滤) + GET /bank/questions/{id} (详情)
- BankQuestion 模型: content_text + content_image + question_type + max_score + difficulty(0-1) + discrimination + tags + bloom_level + knowledge_point_ids + common_errors(JSON)
- 数据来源: 考试题目自动入库(source_exam_id + source_question_id)
- 权限: VIEW_QUESTION_BANK

**实施步骤**:
1. 新建 `frontend/src/api/bank.js` (4 函数)
2. 新建 `frontend/src/pages/QuestionBankPage.vue`
3. 路由 `/question-bank` 替换 ComingSoonPage

### T8: 错题本页

**后端 API 调研**:
- 2 端点: GET /bank/error-book/{student_id} (列表) + GET /bank/error-book/{student_id}/stats (统计)
- StudentErrorBook 模型: student_answer_image + student_score + ai_feedback + error_type + mastery_status(unmastered/practicing/mastered) + retry_count + is_starred
- 权限: VIEW_SCORES

**实施步骤**:
1. 复用 `api/bank.js` 扩展
2. 新建 `frontend/src/pages/ErrorBookPage.vue`
3. 路由 `/error-book` 替换 ComingSoonPage

### T9: 联考管理页

**后端 API 调研** (joint_exam_router.py + joint_exam_service.py):
- 7 端点: CRUD + 参与校管理 + 下发 + 强制截止
- JointExam 模型: name/status/subjects(JSON)/creator_school_id; 状态机: draft→templates_ready→distributed→collecting→completed→archived
- JointExamParticipant: school_id/status/is_creator/student_count/score_upload_count
- 成绩查询在 results_router.py: GET /joint-exams/{id}/results (排名) + /results/by-school (按校对比) + /results/students/{number} (学生明细)
- ⚠️ 缺口: 模板上传和成绩上报端点(service 有但未暴露 HTTP)，前端先做 CRUD+下发

**实施步骤**:
1. 新建 `frontend/src/api/jointExams.js` (8+ 函数)
2. 新建 `frontend/src/pages/JointExamPage.vue`
3. 路由 `/joint-exams` 替换 ComingSoonPage
4. 仅 platform_admin / district_admin 可见

### T10: 教学计划页 (MVP)

**说明**: 后端无专门端点。先做最简版(学期+科目维度的周教学进度文本)，数据可先存 localStorage 或后续补后端。

**实施步骤**:
1. 新建 `frontend/src/pages/TeachingPlanPage.vue` (MVP: 选学期+科目，按周显示可编辑文本)
2. 路由 `/teaching-plans` 替换 ComingSoonPage
3. 标记 MVP，后续迭代

---

## Batch 4: 聚合页面 + 体验

### T11: 学生档案聚合页

**数据来源**(全部已有后端 API):
- 基本信息: GET /students
- 成绩趋势: GET /profile/students/{id}/trend
- 德育积分: GET /conduct/classes/{class_id}/rankings/students
- 错题统计: GET /bank/error-book/{student_id}/stats
- 知识掌握: GET /profile/students/{id}/knowledge

**实施**: 新建 `pages/StudentProfilePage.vue`，路由 `/students/:id`，多入口可达。

### T12: 班级看板

**实施**: 新建 `pages/ClassDashboardPage.vue`，聚合班级成绩+德育+出勤，路由 `/classes/:id`。

### T13: 家校沟通页

**实施**: 新建 `pages/ParentCommPage.vue`，查看家长绑定+推送，路由 `/parent-comm`。

### T14: 侧边栏折叠态 hover 弹出

**实施**: AppSidebar.vue 折叠态 hover 组图标弹出浮层。纯前端。

---

## 执行策略

| Batch | Tasks | 依赖 | 预估 | 会话建议 |
|-------|-------|------|------|---------|
| B1 | T1+T2+T3 | 无 | 1-2 天 | 1 个执行会话 |
| B2 | T4+T5+T6 | B1.T3(占位路由) | 2-3 天 | 1 个执行会话(共享 academic.js) |
| B3 | T7+T8+T9+T10 | B1.T3 | 2-3 天 | 可拆 2 个会话并行(T7+T8 / T9+T10) |
| B4 | T11+T12+T13+T14 | B2+B3 完成 | 3-4 天 | 2 个会话(T11+T12 / T13+T14) |

每个 Task 完成后: build → 浏览器验证 → 多角色权限验证。
