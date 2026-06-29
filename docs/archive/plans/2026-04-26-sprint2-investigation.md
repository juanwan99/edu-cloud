# Sprint 2 提前调研：homework / academic / calendar

> 调研时间：2026-04-27
> 调研人：Sprint 1 T4
> 结论：**三模块前后端全部已存在**，Sprint 2 scope 应从"新建"缩减为"加固+增强"

---

## 资产盘点

| 模块 | 后端端点 | 前端页面 | API 客户端 | 路由注册 | 测试 |
|------|---------|---------|----------|---------|------|
| homework | 14 端点 (router.py) | HomeworkPage.vue (200+ 行) | homework.js 13 方法 | router/index.js:58 | 8 API + 16+ Service |
| academic | 15 端点 (router.py) | SemesterPage.vue + TimetablePage.vue + TeachingPlanPage.vue (各 200+ 行) | academic.js 13 方法 | router/index.js:64-66 | 14 API |
| calendar | 3 端点 (router.py) | CalendarPage.vue + CalendarPanel.vue | calendar.js 3 方法 | router/index.js:61 | 7 API + 6+ Service |

### homework 详细

**后端端点：**
| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| POST | `/api/v1/homework/tasks` | 创建作业 | MANAGE_HOMEWORK |
| GET | `/api/v1/homework/tasks` | 列表（class_id/subject_code/status/task_type 过滤） | VIEW_HOMEWORK |
| GET | `/api/v1/homework/tasks/{id}` | 详情（含 stats） | VIEW_HOMEWORK |
| PATCH | `/api/v1/homework/tasks/{id}` | 更新（仅 draft） | MANAGE_HOMEWORK |
| POST | `/api/v1/homework/tasks/{id}/publish` | 发布（自动创建提交记录） | MANAGE_HOMEWORK |
| POST | `/api/v1/homework/tasks/{id}/close` | 关闭 | MANAGE_HOMEWORK |
| DELETE | `/api/v1/homework/tasks/{id}` | 删除（仅 draft） | MANAGE_HOMEWORK |
| GET | `/api/v1/homework/tasks/{id}/submissions` | 提交记录 | VIEW_HOMEWORK |
| POST | `/api/v1/homework/tasks/{id}/submissions/{sub_id}/submit` | 学生提交 | VIEW_HOMEWORK |
| POST | `/api/v1/homework/tasks/{id}/submissions/{sub_id}/grade` | 单个批改 | MANAGE_HOMEWORK |
| POST | `/api/v1/homework/tasks/{id}/grade-batch` | 批量批改 | MANAGE_HOMEWORK |
| GET | `/api/v1/homework/tasks/{id}/stats` | 统计 | VIEW_HOMEWORK |
| POST | `/api/v1/homework/tasks/from-exam` | 从考试生成补救作业 | MANAGE_HOMEWORK |
| GET | `/api/v1/homework/tasks/{id}/content-detail` | 解析 JSON 题目信息 | VIEW_HOMEWORK |

**模型：** HomeworkTask（12 字段，4 状态 draft→active→expired→closed，4 类型 regular/pre_exam/post_exam/remedial） + HomeworkSubmission（9 字段）

### academic 详细

**后端端点：**
| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| POST/GET | `/api/v1/academic/semesters` | 学期 CRUD | MANAGE_SCHEDULING / 已登录 |
| GET | `/api/v1/academic/semesters/current` | 当前学期 | 已登录 |
| PATCH | `/api/v1/academic/semesters/{id}` | 更新学期 | MANAGE_SCHEDULING |
| POST | `/api/v1/academic/semesters/{id}/activate` | 激活 | MANAGE_SCHEDULING |
| PUT/GET | `/api/v1/academic/periods` | 节次时间 | MANAGE_SCHEDULING / 已登录 |
| GET | `/api/v1/academic/timetable` | 查询课表 | 已登录 |
| PUT | `/api/v1/academic/timetable/{class_id}` | 保存课表 | MANAGE_SCHEDULING |
| GET | `/api/v1/academic/timetable/stats` | 覆盖率统计 | 已登录 |
| POST/GET/PATCH/DELETE | `/api/v1/academic/teaching-plans` | 教学计划 CRUD | MANAGE_SCHEDULING |

**模型：** Semester（7 字段） + TimePeriod（6 字段） + TimetableSlot（7 字段）

### calendar 详细

**后端端点：**
| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| POST | `/api/v1/calendar/events` | 创建校历事件 | GENERATE_NOTIFICATION |
| GET | `/api/v1/calendar/events` | 列出事件 | 已登录 |
| DELETE | `/api/v1/calendar/events/{id}` | 删除事件 | GENERATE_NOTIFICATION |

**模型：** CalendarEvent（9 字段） + NotificationRule（6 字段）

---

## 关键发现

1. **三模块前后端全部已存在**（与 Sprint 1 ErrorBookPage/QuestionBankPage/DashboardPage 情况一致）
2. homework 最完整（14 端点 + 补救作业特性 + 前端完整页面）
3. academic 有 3 个前端页面（学期 + 课表 + 教学计划），路由 3 条
4. calendar 最轻量（3 端点），但 notification_rules 到实际发送的完整链路需确认

## Sprint 2 范围建议

基于调研结果，Sprint 2 应从"新建教务教学链路"调整为：
1. 加固测试覆盖（特别是前端 vitest）
2. 端到端联调（homework from-exam 依赖 exam/scan/bank 三模块数据）
3. calendar notification 完整链路验证
4. 查缺补漏：确认所有端点是否有对应的前端交互
