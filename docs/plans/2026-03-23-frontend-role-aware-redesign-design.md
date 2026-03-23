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
- 不新增后端 API（全部使用已有 endpoint）

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
| 学校上下文 | 显示当前角色所属学校名。platform_admin/district_admin 可切换学校（下拉选择）；其他角色只读显示 |
| 搜索 | 全局搜索入口（后期可接 AI 语义搜索） |
| 通知铃 | 红色 badge 显示未读数。点击展开下拉面板，分 tab：待审批/消息/系统 |
| 头像菜单 | 显示名 + 当前角色 tag。展开：角色切换列表 + 登出 |

### 3.2 左侧栏 Sidebar

220px 宽，可折叠至 64px（只显示图标）。白底，右边框 `--color-border-light`。
导航项按角色动态渲染，使用 `sidebarConfig.js` JSON 配置驱动。

**校长/教务主任**：
- 校务概览（dashboard）
- 考试管理
- 数据分析
- 文档中心
- 校历通知
- 学校管理（仅 admin）
- 系统设置

**班主任/科任教师**：
- 我的工作台（dashboard）
- 考试管理
- 阅卷（我的任务/批改）
- 成绩分析
- 文档
- AI 助手

**家长**：
- 孩子成绩
- 学习画像
- 学校通知

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

### 4.2 校长 Dashboard

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

### 4.3 教务主任 Dashboard

**视角**：执行调度。比校长多操作入口。

**KPI 行**：本学期考试数 / 待阅卷科目 / 联考进行中 / AI批改完成率

**模块卡片**：考试管理 / 联考管理 / 阅卷调度 / 数据分析 / 文档中心 / AI 助手

### 4.4 班主任 Dashboard

**视角**：我的班级。scope = class_ids。

**KPI 行**：我的班级名 / 班级人数 / 班级均分 / 待批改

**模块卡片**：我的班级（学生列表入口）/ 待办事项 / 成绩分析 / 通知管理 / AI 助手 / 文档中心

### 4.5 科任教师 Dashboard

**视角**：我的学科 + 我教的班。scope = class_ids + subject_codes。

**KPI 行**：教授班级数 / 学科均分 / 待批改数 / AI工具数

**模块卡片**：我的阅卷 / 学科成绩 / AI 助手 / 论文写作

### 4.6 家长 Dashboard

**视角**：只看自己孩子。最简洁。

**顶部**：孩子姓名 + 班级 + 准考证号（信息条）

**模块卡片**：最近成绩 / 学习画像 / 学校通知（全宽列表）

## §5 AI 助手设计

### 5.1 浮窗模式（全局）

右下角常驻悬浮按钮（48px 圆形，墨绿色，`--shadow-lg`），hover 上浮。
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
{
  path: '/',
  component: AppShell,
  children: [
    { path: '', name: 'Dashboard', component: DashboardPage },
    { path: 'exams', component: ExamListPage },
    { path: 'exams/:id', component: ExamDetailPage },
    { path: 'analytics/:examId?', component: AnalyticsPage },
    { path: 'analysis', component: AnalysisPage },  // 三栏
    { path: 'marking', component: MarkingSelectPage },
    { path: 'marking/grade/:questionId', component: MarkingPage },
    { path: 'marking/assign', component: MarkingAssignPage },
    { path: 'marking/progress', component: MarkingProgressPage },
    { path: 'grading/tasks', component: GradingTasksPage },
    { path: 'grading/tasks/:id', component: GradingResultsPage },
    { path: 'grading/review', component: TeacherReviewPage },
    { path: 'calendar', component: CalendarPage },
    { path: 'studio', component: StudioPage },
    { path: 'schools', component: SchoolsPage },
    { path: 'settings', component: SettingsPage },
  ]
}
```

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

## §7 样式规范（momowan 对齐）

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
