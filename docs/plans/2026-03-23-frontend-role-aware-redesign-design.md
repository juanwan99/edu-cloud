# edu-cloud 前端角色感知重设计

> **snapshot: 2026-03-23**
> **覆盖**: 当前 exam-ai 移植的扁平前端 → 多校多角色分层 UI

## §0 问题陈述

后端实现了 8 角色分层权限体系（platform_admin → district_admin → principal → academic_director → grade_leader → homeroom_teacher → subject_teacher → parent），支持多校、多角色、scope 过滤（school_id / class_ids / subject_codes）。

前端是从 exam-ai（单校阅卷工具）直接复制的 15 个页面，没有体现权限层级：
- 品牌仍叫"智能阅卷"
- 导航是扁平菜单，不区分角色
- 无学校上下文显示
- 无角色切换的视觉反馈
- 所有角色看到相同的 dashboard
- AI 助手锁死在三栏布局内

## §1 设计调研

### 行业 UI 趋同（2026）

调研飞书、钉钉教育、企业微信、PowerSchool/Clever，结论：

1. **宏观布局趋同**：左侧栏 + 顶栏 + 角色定制主区域
2. **钉钉教育验证了我们的角色体系**：教师工作台/校长驾驶舱/局校家平台
3. **角色决定内容**：不同角色看到完全不同的 dashboard，不只是隐藏菜单
4. **AI 助手是浮窗**：从任何页面可调出，不锁死在固定面板
5. **通知中心**：铃铛 + badge + 下拉面板是标准模式

### momowan 设计语言

采用 momowan-website 的视觉风格系统：

| Token | Value | 用途 |
|-------|-------|------|
| `--color-primary` | #1a2e1f | 按钮、链接、强调文字 |
| `--color-bg` | #ffffff | 页面背景 |
| `--color-bg-alt` | #f9fafb | 区块交替背景 |
| `--color-text` | #1a2e1f | 主文字 |
| `--color-text-secondary` | #5a6b5e | 次要文字 |
| `--color-border-light` | #f0f4f1 | 卡片边框 |
| `--radius-xl` | 24px | 卡片圆角 |
| `--radius-pill` | 50px | 按钮、badge |
| `--shadow-lg` | 0 12px 32px rgba(26,46,31,0.08) | 卡片 hover |
| `--transition` | all 0.25s cubic-bezier(0.4,0,0.2,1) | 所有动效 |
| macaron 柔彩 | mint/yellow/coral/purple/blue | KPI 卡片、功能区分 |

图标：SVG mask-image + currentColor（不用 emoji）。
字体：系统字体栈 -apple-system, BlinkMacSystemFont, "Segoe UI", ...

## §2 架构决策

### 改造策略：壳层改造 + 角色定制 Dashboard

**方案对比**：

| 方案 | 工作量 | 效果 | 选择 |
|------|--------|------|------|
| A. 只改壳层 | 小 | 导航有层级感，但首页仍是通用的 | 否 |
| B. 角色定制 Dashboard | 中 | 登录即看到角色专属视图 | 否 |
| **A+B 组合** | **中** | **壳层 + Dashboard 双重角色感知** | **选定** |
| C. 全面重设计 | 大 | 每个页面都重做 | 否（过度工程） |

**决策理由**：
- 壳层（顶栏+侧栏）让用户一眼看出"我是谁、管什么"
- 角色 Dashboard 让用户一登录就看到最相关的信息
- 功能页面（阅卷、分析等）保持现有逻辑，只补角色感知
- 模块卡片模式支持未来扩展（师资、后勤、家校等）

### 不做什么

- 不重写 15 个功能页面的内部逻辑
- 不做移动端适配（后续独立设计）
- 不实现"师资人事""后勤安全"等规划中板块的业务逻辑
- 不实现 parent-child 绑定（家长端为简化版，后续独立设计）

### 需要新增的后端变更（FR-03/FR-04/FR-08 修复）

设计依赖以下后端变更，需在实现计划中安排：

| 变更 | 原因 | 端点 |
|------|------|------|
| login/switch-role 返回 school_name | 顶栏显示学校名（教师/家长无 VIEW_SCHOOLS 权限） | `POST /auth/login`, `POST /auth/switch-role` |
| dashboard summary API | KPI 卡片数据源（学生数/班级数/考试数/待批改数） | `GET /api/v1/dashboard/summary` |
| notification list API | 通知中心下拉面板 | `GET /api/v1/notifications` |

这些是轻量扩展，不涉及架构变更。

## §3 导航壳层设计

### 3.1 顶栏 Header

68px 高，毛玻璃效果（`rgba(255,255,255,0.92)` + `backdrop-filter: blur(12px)`），固定顶部。

```
┌──────────────────────────────────────────────────────────────┐
│ [Logo] edu-cloud  │ [学校名] ▾  │  [搜索]  │ [铃铛 3] │ [头像]▾ │
└──────────────────────────────────────────────────────────────┘
```

| 区域 | 行为 |
|------|------|
| Logo + 品牌 | 「edu-cloud 智能平台」，点击回首页 |
| 学校上下文 | 显示当前角色所属学校名（从 login/switch-role 响应的 `school_name` 字段获取）。platform_admin 的 `school_id` 为 null，此时显示「全平台」；district_admin 显示管辖区名。角色切换自动更新学校名。**不做独立的学校切换器**——平台/区级用户通过切换角色（同一用户可有多校角色）来切换上下文 |
| 搜索 | 全局搜索入口（后期可接 AI 语义搜索） |
| 通知铃 | 红色 badge 显示未读数。点击展开下拉面板，分 tab：待审批/消息/系统 |
| 头像菜单 | 显示名 + 当前角色 tag。展开：角色切换列表 + 登出 |

### 3.2 左侧栏 Sidebar

220px 宽，可折叠至 64px（只显示图标）。白底，右边框 `--color-border-light`。
导航项按角色动态渲染，使用 `sidebarConfig.js` JSON 配置驱动。

**平台管理员（platform_admin）**：
- 平台概览（dashboard）
- 学校管理
- 联考管理
- 用户管理（规划中）
- 系统设置

**区管理员（district_admin）**：
- 区域概览（dashboard）
- 学校管理
- 联考管理
- 跨校分析
- 用户管理（规划中）

**校长（principal）**：
- 校务概览（dashboard）
- 考试管理
- 数据分析
- 文档中心
- 校历通知

**教务主任（academic_director）**：
- 教务概览（dashboard）
- 考试管理
- 联考管理
- 阅卷调度
- 数据分析
- 文档中心
- 系统设置（LLM 配置）

**年级组长（grade_leader）**：
- 年级概览（dashboard）
- 考试管理
- 数据分析（本年级 scope）
- 文档

**班主任（homeroom_teacher）**：
- 我的工作台（dashboard）
- 考试管理
- 阅卷（我的任务/批改）
- 成绩分析（本班 scope）
- 通知管理
- 文档

**科任教师（subject_teacher）**：
- 我的工作台（dashboard）
- 考试管理
- 阅卷（我的任务/批改）
- 成绩分析（本科 scope）
- 论文写作
- 文档

**家长（parent）**：
- 孩子成绩
- 学校通知

**Legacy 别名处理**：auth store 中 role normalization — `admin` → `platform_admin`，`teacher` → `subject_teacher`，`head_teacher` → `homeroom_teacher`。Config 查找统一用 canonical 角色名。

**AI 助手入口**：侧栏中仅对具备 `USE_AI_CHAT` 权限的角色显示（即除 parent 外所有角色）。AI 浮窗按钮同理。

导航项样式：`padding: 10px 16px`，active 态左边框 3px `--color-primary` + 背景 `--color-bg-alt`。
分组标题：12px，`--color-text-muted`，uppercase，`margin-top: 24px`。

### 3.3 角色切换

头像下拉菜单中展示所有可用角色：

```
┌────────────────────────┐
│ 王芳                    │
│ [tag] 校长 · 测试一校    │  ← 当前激活（高亮）
│ ──────────────────────  │
│ 切换角色:                │
│   ○ 教务主任 · 测试一校   │
│   ○ 科任教师 · 测试二校   │
│ ──────────────────────  │
│ 退出登录                 │
└────────────────────────┘
```

切换时：
1. 调用 `POST /api/v1/auth/switch-role`
2. 更新 token + currentRole
3. 侧栏导航项重新渲染
4. Dashboard widgets 重新请求数据
5. 顶栏学校名更新

## §4 角色 Dashboard 设计

### 4.1 设计原则

| 原则 | 说明 |
|------|------|
| 角色决定卡片集 | `dashboardConfig.js` 定义每个角色的 widget 列表 |
| scope 决定数据 | 同一 API，后端按 school_id/class_ids 过滤 |
| 操作权下沉 | 校长只"查看"，教务"调度"，教师"批改" |
| 模块可扩展 | 新功能 = 新卡片，不改框架 |
| 规划中板块灰度展示 | 告诉用户系统在成长，不留空白 |

### 4.2 平台管理员 Dashboard（platform_admin）

**视角**：跨校管理。school_id 为 null。

**KPI 行**：学校总数 / 活跃学校 / 联考进行中 / 系统用户数（规划中）

**模块卡片**：学校管理 / 联考管理 / 系统设置 / 用户管理（规划中）

**数据源**：`GET /api/v1/schools`（学校数）、`GET /api/v1/joint-exams`（联考数）

### 4.3 区管理员 Dashboard（district_admin）

**视角**：管辖区内学校。scope = district。

**KPI 行**：管辖学校数 / 联考进行中 / 跨校均分 / 待处理

**模块卡片**：学校管理 / 联考管理 / 跨校分析 / 用户管理（规划中）

**数据源**：`GET /api/v1/schools?district=X`、`GET /api/v1/joint-exams`

### 4.4 校长 Dashboard（principal）

**视角**：全校健康度概览。教学只是一个板块。

**KPI 行（4 列）**：
- 在校学生（mint）— 数字 + "N个班级"
- 教职工（yellow）— 数字 + "N名班主任"
- 待审批（purple）— 数字
- 本周通知（coral）— 数字

**模块卡片行（2×N 网格）**：
每张卡片 = 板块标题 + SVG 图标 + 2-3 行状态摘要 + "查看详情 →" 链接

| 卡片 | 状态摘要示例 | 链接 |
|------|-------------|------|
| 教学质量 | 本学期 3 次考试 / 全校均分 89.2（↑2.1）/ 薄弱：物理 72% | → /analytics |
| 校务行政 | 近期校历 2 件 / 待审批通知 3 件 / 已发送 12 件 | → /calendar |
| AI 助手 | 引导语 + 示例问题 | → /analysis |
| 文档中心 | 本月报告 N 份 / 草稿 N 份 | → /studio |
| 师资人事 | 规划中（灰度） | — |
| 后勤安全 | 规划中（灰度） | — |

**动态流（全宽）**：按时间倒序的事件列表，带日期分组。

### 4.5 教务主任 Dashboard（academic_director）

**视角**：执行调度。比校长多操作入口。

**KPI 行**：本学期考试数 / 待阅卷科目 / 联考进行中 / AI批改完成率

**模块卡片**：考试管理 / 联考管理 / 阅卷调度 / 数据分析 / 文档中心 / AI 助手

### 4.6 年级组长 Dashboard（grade_leader）

**视角**：本年级。scope = grade_ids。

**KPI 行**：年级班级数 / 年级学生数 / 年级均分 / 最近考试

**模块卡片**：年级成绩概览 / 考试管理 / 数据分析 / 文档

**数据源**：`GET /api/v1/dashboard/summary`（后端按 grade scope 过滤）

### 4.7 班主任 Dashboard（homeroom_teacher）

**视角**：我的班级。scope = class_ids。

**KPI 行**：我的班级名 / 班级人数 / 班级均分 / 待批改

**模块卡片**：我的班级（学生列表入口）/ 待办事项 / 成绩分析 / 通知管理 / AI 助手 / 文档中心

### 4.8 科任教师 Dashboard（subject_teacher）

**视角**：我的学科 + 我教的班。scope = class_ids + subject_codes。

**KPI 行**：教授班级数 / 学科均分 / 待批改数 / AI工具数

**模块卡片**：我的阅卷 / 学科成绩 / AI 助手 / 论文写作

### 4.9 家长 Dashboard（parent）

**视角**：简化版。parent-child 绑定机制待后续设计。

**当前实现**：显示学校通知列表（`GET /api/v1/calendar/events`）。成绩和画像功能待 parent-child 绑定后启用，当前显示"功能开发中"占位卡片。

**模块卡片**：学校通知（全宽列表） / 孩子成绩（规划中）/ 学习画像（规划中）

## §5 AI 助手设计

### 5.1 浮窗模式（仅限有 USE_AI_CHAT 权限的角色）

右下角悬浮按钮（48px 圆形，墨绿色，`--shadow-lg`），hover 上浮。仅对具备 `USE_AI_CHAT` 权限的角色显示（即除 `parent` 外所有角色）。`parent` 角色不渲染浮窗按钮。
点击从右侧滑出面板（400px 宽，`--shadow-xl`，左上/左下 `--radius-lg` 圆角）。

面板内容：
- 标题栏：「AI 助手」 + 关闭按钮 + "展开"按钮（跳转三栏分析页）
- 对话区：消息列表（用户/助手），工具调用折叠展示
- 输入框：底部固定，回车发送

技术：复用现有 `aiChat.js` store + `sseParser.js`，UI 从 ChatPanel 提取重构。

### 5.2 三栏深度分析页（保留）

路由 `/analysis`，使用现有 WorkbenchLayout：
- 左：上下文面板（班级/考试/日历选择器）
- 中：数据面板（KPI + 图表 + AI 对话）
- 右：Studio 面板（文档模板/我的文档/论文状态）

定位：沉浸式数据分析场景，和 Dashboard 的"快速概览"互补。

## §6 组件架构

### 6.1 新增/重构文件清单

```
src/
  layouts/
    AppShell.vue              # 新：顶栏 + 侧栏 + 主区域 + AI浮窗
    WorkbenchLayout.vue       # 保留：三栏分析页专用
  components/
    shell/
      AppHeader.vue           # 新：顶栏
      AppSidebar.vue          # 新：左侧栏（角色过滤导航）
      NotificationBell.vue    # 新：通知铃 + 下拉面板
      RoleSwitcher.vue        # 新：角色切换下拉
      SchoolContext.vue       # 新：学校名显示/切换
    dashboard/
      DashboardCard.vue       # 新：统一模块卡片
      KpiCard.vue             # 新：KPI 指标卡
      ActivityFeed.vue        # 新：动态流列表
      WidgetGrid.vue          # 新：widget 网格容器
    ai/
      AiFloatingButton.vue    # 新：右下角浮窗按钮
      AiSlidePanel.vue        # 新：侧滑 AI 面板
      ChatPanel.vue           # 重构：独立于布局
  pages/
    DashboardPage.vue         # 重写：角色定制 widget dashboard
    AnalysisPage.vue          # 重命名 WorkbenchPage → 三栏分析
  config/
    dashboardConfig.js        # 新：角色 → widget 配置
    sidebarConfig.js          # 新：角色 → 导航项配置
  router/
    index.js                  # 修改：路由结构调整
```

### 6.2 路由结构调整

```javascript
// AppShell 包裹所有需要导航的页面
// meta.roles: 允许访问的角色列表（空 = 所有已认证用户）
// meta.permissions: 允许访问的权限列表（可选，更细粒度）
{
  path: '/',
  component: AppShell,
  meta: { requiresAuth: true },
  children: [
    // Dashboard（所有角色，内容由 config 决定）
    { path: '', name: 'Dashboard', component: DashboardPage },

    // 考试管理（现有页面，保留）
    { path: 'exams', component: ExamListPage },
    { path: 'exams/:id', component: ExamDetailPage },
    { path: 'card-dev/:examId', component: CardEditorDevPage },
    { path: 'analytics/:examId', component: AnalyticsPage },  // examId 必填

    // 阅卷（现有页面，保留）
    { path: 'marking', component: MarkingSelectPage },
    { path: 'marking/grade/:questionId', component: MarkingPage },
    { path: 'marking/assign', component: MarkingAssignPage, meta: { roles: SCHOOL_ADMIN_ROLES } },
    { path: 'marking/progress', component: MarkingProgressPage },

    // AI 阅卷（现有页面，保留）
    { path: 'grading/tasks', component: GradingTasksPage, meta: { roles: SCHOOL_ADMIN_ROLES } },
    { path: 'grading/tasks/:id', component: GradingResultsPage },
    { path: 'grading/review', component: TeacherReviewPage },

    // 三栏深度分析（原 WorkbenchPage 重命名）
    { path: 'analysis', component: AnalysisPage },

    // 学校管理（现有页面，保留）
    { path: 'schools', component: SchoolsPage, meta: { permissions: ['MANAGE_SCHOOLS'] } },

    // Dashboard（现有页面，保留）
    { path: 'dashboard', component: DashboardOldPage },  // 旧 dashboard 暂保留
  ]
}
```

**路由守卫增强**：`router.beforeEach` 除检查 token 外，还检查 `meta.roles`（角色白名单）和 `meta.permissions`（权限白名单）。不匹配则重定向到 Dashboard 并提示无权限。

**注意**：CalendarPage、StudioPage、SettingsPage 暂不新增——这些功能通过 Dashboard 卡片直接链接到现有组件或三栏分析页。后续需要独立页面时再添加。

### 6.3 数据流

```
登录 → auth store（user + roles + currentRole + isAdmin）
     → router guard 检查 token + 角色权限
     → AppShell 渲染：
         AppHeader（学校名、通知、头像）
         AppSidebar（根据 sidebarConfig[role] 渲染导航）
         <router-view>
     → DashboardPage 根据 dashboardConfig[role] 渲染 widgets
     → 每个 widget 独立调 API（后端按 scope 过滤）
     → 角色切换 → role 变 → sidebar 重渲染 + dashboard 重加载
```

### 6.4 复用与影响范围

| 现有组件 | 处置 |
|---------|------|
| AppNavbar.vue | 删除，功能拆分到 AppHeader + AppSidebar |
| DashboardLayout.vue | 删除，被 AppShell 替代 |
| WorkbenchLayout.vue | 保留，AnalysisPage 专用 |
| WorkbenchPage.vue | 重命名为 AnalysisPage，内容不变 |
| ChatPanel.vue | 重构为独立组件，浮窗和三栏页共用 |
| ContextPanel/DataView/StudioPanel | 保留，三栏分析页使用 |
| 所有 exam-ai 功能页面 | 保留，移入 AppShell children |
| LoginPage.vue | 保留，不在 AppShell 内 |

## §7 KPI 数据源矩阵

每个 KPI widget 的数据来源必须有明确的 API 映射：

| KPI | 角色 | API 端点 | 字段 | 状态 |
|-----|------|---------|------|------|
| 学校总数 | platform_admin | `GET /api/v1/schools` | `len(response)` | 已有 |
| 联考进行中 | platform_admin, district_admin | `GET /api/v1/joint-exams` | filter `status=in_progress` | 已有 |
| 在校学生 | principal+ | `GET /api/v1/dashboard/summary` | `total_students` | **需新增** |
| 教职工 | principal | `GET /api/v1/dashboard/summary` | `total_staff` | **需新增** |
| 班级数 | principal+ | `GET /api/v1/workspace/context` | `len(classes)` | 已有 |
| 考试数 | all | `GET /api/v1/workspace/context` | `len(exams)` | 已有 |
| 待批改 | teacher+ | `GET /api/v1/marking/my-assignments` | filter `status=pending` | 已有 |
| 班级均分 | homeroom_teacher | `GET /api/v1/workspace/exams/{id}/dashboard` | `stats.avg` | 已有 |
| 待审批 | principal+ | `GET /api/v1/notifications?status=pending` | `len(response)` | **需新增** |
| 本周通知 | principal+ | `GET /api/v1/notifications?since=week` | `len(response)` | **需新增** |

**需新增 API（2 个）**：
1. `GET /api/v1/dashboard/summary` — 返回角色 scope 内的聚合统计（学生数/班级数/教职工数/考试数/待批改数）
2. `GET /api/v1/notifications` — 通知列表（支持 status/since 过滤），校长看全校，教师看自己相关

对于无法立即支撑的 KPI（如教职工数），widget 显示为 `--`（加载中/无数据），不隐藏卡片。

## §8 样式规范（momowan 对齐）

### 卡片

```css
.dashboard-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-xl);  /* 24px */
  padding: 32px;
  transition: var(--transition);
}
.dashboard-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}
```

### KPI 卡片

```css
.kpi-card {
  border-radius: var(--radius-xl);
  padding: 28px;
}
.kpi-card--mint { background: var(--macaron-mint-light); }
.kpi-card--yellow { background: var(--macaron-yellow-light); }
.kpi-card--coral { background: var(--macaron-coral-light); }
.kpi-card--purple { background: var(--macaron-purple-light); }

.kpi-value {
  font-size: 36px;
  font-weight: 800;
  color: var(--color-primary);
}
.kpi-label {
  font-size: 14px;
  color: var(--color-text-secondary);
}
```

### 侧栏

```css
.sidebar {
  width: 220px;
  background: var(--color-bg);
  border-right: 1px solid var(--color-border-light);
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.sidebar--collapsed { width: 64px; }

.nav-item {
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 500;
}
.nav-item--active {
  color: var(--color-primary);
  background: var(--color-bg-alt);
  font-weight: 700;
  border-left: 3px solid var(--color-primary);
}
```

### 图标

```css
.icon {
  display: inline-flex;
  width: 20px;
  height: 20px;
  background: currentColor;
  mask-size: contain;
  mask-repeat: no-repeat;
  mask-position: center;
  flex-shrink: 0;
}
/* 每个图标用 mask-image: url("data:image/svg+xml,...") */
```

### 完整 CSS Token 表

variables.css 需补齐以下 token（当前缺失）：

```css
:root {
  /* 颜色 */
  --color-primary: #1a2e1f;
  --color-primary-dark: #0f1c13;
  --color-primary-light: #2d5a3d;
  --color-bg: #ffffff;
  --color-bg-alt: #f9fafb;
  --color-bg-card: #ffffff;
  --color-text: #1a2e1f;
  --color-text-secondary: #5a6b5e;
  --color-text-muted: #8a9a8e;
  --color-border: #e2e8e4;
  --color-border-light: #f0f4f1;

  /* Macaron 柔彩 */
  --macaron-mint: #c8f0d4;
  --macaron-mint-light: #e8f8ee;
  --macaron-yellow: #fef3c7;
  --macaron-yellow-light: #fdf6e3;
  --macaron-coral: #fde8e8;
  --macaron-coral-light: #fef0f0;
  --macaron-purple: #ede9fe;
  --macaron-purple-light: #f3f0ff;
  --macaron-blue: #e0f2fe;
  --macaron-blue-light: #ecf6ff;

  /* 圆角 */
  --radius-sm: 10px;
  --radius-md: 14px;
  --radius-lg: 20px;
  --radius-xl: 24px;
  --radius-pill: 50px;

  /* 阴影 */
  --shadow-sm: 0 1px 3px rgba(26, 46, 31, 0.04);
  --shadow-md: 0 4px 12px rgba(26, 46, 31, 0.06);
  --shadow-lg: 0 12px 32px rgba(26, 46, 31, 0.08);
  --shadow-xl: 0 24px 48px rgba(26, 46, 31, 0.1);

  /* 动效 */
  --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
```

### Naive UI 主题处理

当前 App.vue 启用了 Naive UI `darkTheme`，与 momowan 白底风格冲突。实现时：

1. 移除 `darkTheme`，切换为 light theme
2. 通过 `theme.js` 的 `themeOverrides` 将 Naive UI 组件颜色对齐 momowan token
3. Naive UI 组件（NButton, NCard, NDropdown 等）的 border-radius、色值通过 overrides 统一
