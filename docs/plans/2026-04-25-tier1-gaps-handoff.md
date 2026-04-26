---
topic: tier1-business-gaps
tier: T2
handoff_type: executor
created: "2026-04-25 20:00:00"
blocked_by: []
blocks: []
---

=== 生成块开始 ===

# 第一梯队业务缺口填充 — 执行交接卡

**上下文**: edu 项目管理大师会话完成 4 个模块打穿（analytics/profile/academic/homework），
深度调研发现 5 个"后端完整+有数据+前端零覆盖"的缺口。本卡指导新会话逐个填充。

**核心原则**: 模块化整合，不铺摊子。增强已有代码，不新建平行系统。
所有前端工作在 `frontend/`（不碰 frontend-nuxt/，已删除）。
改完必须 `cd frontend && npx vite build` 让 mcu.asia 生效。
Playwright 已安装（Firefox），可用 `/tmp/e2e-verify.mjs` 模板截图验证。

=== 生成块结束 ===

---

## G1. 错题本页面（优先级最高）

**后端**: `src/edu_cloud/modules/bank/router.py` — 4 端点
- `GET /api/v1/bank/error-book/{student_id}` — 学生错题列表（支持 mastery_status 筛选）
- `GET /api/v1/bank/error-book/{student_id}/stats` — 错题统计（按 mastery_status 分组）
- `GET /api/v1/bank/questions` — 题库列表
- `GET /api/v1/bank/questions/{id}` — 题目详情

**数据**: student_error_books 76,758 条（pipeline 考后自动填充）

**模型字段**: student_id, question_id, exam_id, student_score, max_score, correct_answer,
ai_feedback, error_type, knowledge_point_ids (JSON), mastery_status (unmastered/practicing/mastered),
retry_count, is_starred, source

**执行**:
1. 新建 `frontend/src/api/bank.js` — 接入 4 个端点
2. 新建 `frontend/src/pages/ErrorBookPage.vue`:
   - 从学生画像页链入，或侧边栏独立入口
   - 筛选: mastery_status + subject_code
   - 展示: 题目内容 + AI 反馈 + 知识点标签 + 掌握状态 Tag
   - 统计卡: 未掌握/练习中/已掌握 数量
3. 路由 `/error-book/:studentId`，权限 `view_scores`
4. 侧边栏加入"错题本"或在 StudentProfilePage 加入 Tab

---

## G2. Dashboard 数据填充

**现状**: DashboardPage.vue 已有 KPI 卡片框架 + dashboardConfig.js 角色配置，
但 `GET /api/v1/dashboard/summary` 返回实际数据（total_students/classes/exams/pending_grading）。
前端已绑定，理论上切到学校角色就能看到数据。

**验证**: 先 curl 测试 `/api/v1/dashboard/summary`（需切学校角色），确认是否真的返回空。
如果返回有数据，可能只是 admin primary role school_id=None 导致的。

**如果需要增强**:
- 添加更多 KPI: 本周作业完成率、本月考试场次、班级排名变化
- 在 DashboardPage 添加 ECharts 图表（考试成绩趋势、班级对比）
- 最近动态列表填充真实数据（考试发布、作业布置、成绩分析等事件）

---

## G3. 联考管理页面

**后端**: `src/edu_cloud/api/joint_exam_api.py` — 9 端点完整
- CRUD + 参与学校管理 + 下发 + 强制完成 + 成绩查询 + 校际对比
- 权限: CREATE_JOINT_EXAM / VIEW_JOINT_EXAM

**模型**: JointExam（name/subjects/status/template） + JointExamParticipant（school/status） + JointExamStudentResult（scores）

**数据**: 0 条（需创建测试联考或从 UI 创建）

**执行**:
1. `frontend/src/api/jointExams.js` — 9 个端点
2. `JointExamPage.vue` — 联考列表 + 创建弹窗 + 详情面板（参与学校/状态/成绩）
3. `JointExamDetailPage.vue` — 成绩汇总 + 校际对比图表
4. 路由 `/joint-exams` + `/joint-exams/:id`，侧边栏"联考管理"
5. 仅 platform_admin / district_admin 可见

---

## G4. 通知系统

**后端**: `GET /api/v1/notifications` — 列表查询（status/since 筛选）
**模型**: Notification（channel/status/target_scope） + NotificationRule（event_id/days_before/template）
**前端**: `notifications.js` API 已存在，NotificationBell 组件是占位符

**执行**:
1. 增强 NotificationBell 组件 — 绑定真实数据、显示未读数
2. 可选: 新建通知管理页面（列表+标记已读）

---

## G5. 校历/日程

**后端**: `src/edu_cloud/modules/calendar/router.py` — 3 端点（create/list/delete）
**模型**: CalendarEvent（type/title/event_date） + NotificationRule（自动提醒）

**执行**:
1. `frontend/src/api/calendar.js` — 3 个端点
2. `CalendarPage.vue` — 月视图日历 + 事件列表 + 创建弹窗
3. 侧边栏"校历管理"

---

## 技术要点

- **当前分支**: `feat/analytics-report`，master 已同步到 `9f6faf6`
- **前端测试**: 255/255 通过，路由数 25（每加路由需更新 router.test.js 中的 toHaveLength）
- **后端测试基线**: 2185 passed / 1 failed (dispatch_status deferred) / 23 skipped
- **Playwright**: Firefox 已安装，脚本模板在 `/tmp/e2e-verify.mjs`
  ```bash
  cd /tmp && node -e "import('playwright').then(async({firefox})=>{...})"
  ```
- **nginx serve**: dist/ 静态文件，改代码后 `npx vite build`
- **admin 切学校**: primary role 无 school_id，需 switch-role 到 974d3221（school 31c17116）
- **doc-sync-guard**: 改 router/api/page 时必须同步更新 CLAUDE.md 路由数和端点列表

## 执行顺序建议

G1（错题本）→ G2（Dashboard）→ G3（联考）→ G4（通知）→ G5（校历）

G1 数据最多最直观，G2 影响首屏体验，G3 是 edu-cloud 定位核心，G4/G5 可后置。
