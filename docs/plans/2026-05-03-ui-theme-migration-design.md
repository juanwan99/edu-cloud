# UI 主题迁移设计：冷暖撞色全系统推广

> Status: Draft v2 (GPT R1 findings addressed) | T4 | 2026-05-03

## 目标

将 ui-demo.html 确认的冷暖撞色设计语言（深墨 #09061B + 金黄 #F4DA4C + 冷紫 #644CF0 + 橙 #ED9A51）迁移为 edu-cloud 全系统正式 UI 主题，替换当前 V3.2 Wells Collins 翠绿体系。

---

## 现有资产盘点

### Q1. 项目里已经有什么

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| Token 定义 | V3.2 翠绿体系（primary #1a7a4f, accent #c8e64a） | `src/assets/styles/variables.css:1-143` | 全量 CSS 变量 |
| Naive UI 主题 | 翠绿主题覆盖（15 组件 + common） | `src/theme.js:1-131` | primaryColor #1a7a4f, successColor #10b981 |
| 全局样式 | 工具类 + 表头 + 统计卡 + 标签 | `src/assets/styles/global.css:1-226` | .stat-card/.tag-*/.text-kpi |
| AppHeader | 深色顶栏（#1a1a1a） | `src/components/shell/AppHeader.vue:49` | hardcoded |
| AppSidebar | 翠绿底 var(--color-sidebar-bg)=#1a7a4f | `src/components/shell/AppSidebar.vue:108` | active=#c8e64a |
| LoginPage | 独立蓝色体系（#111C33/#1F5BD7/#1849B0） | `src/pages/LoginPage.vue:176,300` | 6 个蓝色值 |
| ParentLayout | 独立 darkTheme + #63e2b7 绿色硬编码 | `src/layouts/ParentLayout.vue` | 不传 themeOverrides |
| Parent 页面 | 8 页大量 #63e2b7/#18a058 硬编码 | 15 文件（grep 结果） | darkTheme 绿 |
| CardEditor | 独立 CSS（public/card-editor/styles.css）绿系 | `public/card-editor/styles.css:77,85` | #2d5a3d/#1a2e1f |
| DashboardPage | macaron 柔彩 + ECharts 色板 | `src/pages/DashboardPage.vue:374` | var(--macaron-*) |
| KnowledgeTree | G6 节点色 + heatmapUtils 色阶 | `src/components/knowledge-tree/heatmapUtils.js` | 独立色系 |
| CSS 别名 | --primary-color/--border-color 等散落引用 | 11 个文件 | 非 root 定义但在用 |
| 设计 Demo | ui-demo.html（已确认方案） | `frontend/ui-demo.html` | 冷暖撞色完整实现 |

### Q2. 为什么不增强已有

本次是 **Token 替换**而非平行系统。在已有的 variables.css + theme.js + global.css 三层架构上直接替换色值和组件样式，不新建文件、不新建目录。

### Q3. 交付路径

- 目标目录：`frontend/src/`（已有，Vite build 产出 dist/）
- 生产 serving：nginx 443 → `frontend/dist/`（已建立）
- 用户访问 URL：https://mcu.asia
- 验证方式：vite build → 硬刷 mcu.asia → 逐页确认

---

## 色值映射表（完整覆盖所有旧值源）

### 核心 4 色语义定义

| 角色 | 色值 | 用途 | 配对前景 |
|------|------|------|---------|
| **Primary（紫）** | #644CF0 | 主操作按钮、链接、选中态、数据图表主线 | #fff（深底）/ #644CF0（浅底文字） |
| **Accent（金）** | #F4DA4C | 强调 CTA、导航激活、品牌标识、进度 | #09061B（金底配深墨文字） |
| **Warning（橙）** | #ED9A51 | 待处理、提醒、中等优先级 | #fff（橙底）/ #9A5E20（浅底文字） |
| **Success（翠）** | #22C55E | 完成、正向趋势、通过、掌握 | #fff（绿底）/ #166534（浅底文字） |
| **Error（红）** | #dc2626 | 错误、危险、失败 | 不变 |
| **Info（浅紫）** | #8B7AF5 | 提示、中性状态、次要信息 | #fff（紫底）/ #4F3EC9（浅底文字） |
| **Ink（深墨）** | #09061B | 深色底、顶栏、侧栏、深色按钮 | #F4DA4C 或 #fff |

> **R1-F002 修复**：success 保留绿色（#22C55E），不与 primary 混同。info 用浅紫（#8B7AF5）区分于 primary 深紫。

### variables.css 映射

| 变量 | 旧值 | 新值 |
|------|------|------|
| --color-primary | #1a7a4f | #644CF0 |
| --color-primary-dark | #145f3d | #4F3EC9 |
| --color-primary-light | #22956a | #7B68F5 |
| --color-accent | #c8e64a | #F4DA4C |
| --color-accent-hover | #b8d63a | #E8CF40 |
| --color-bg | #f5f5f3 | #F4F5F9 |
| --color-bg-alt | #f0f0ee | #EDEDF3 |
| --color-bg-card | #ffffff | #ffffff |
| --color-text | #1a1a1a | #09061B |
| --color-text-secondary | #555550 | #5a5a68 |
| --color-text-muted | #72726c | #A0A0A8 |
| --color-border | #deded9 | #E8E8EF |
| --color-border-light | #e8e8e4 | #F1F2F6 |
| --color-success | #1a7a4f | #22C55E |
| --color-danger | #dc2626 | #dc2626 |
| --color-warning | #d97706 | #ED9A51 |
| --color-info | #2563eb | #8B7AF5 |
| --color-bg-deep | #1a1a1a | #09061B |
| --color-sidebar-bg | #1a7a4f | #09061B |
| --color-sidebar-active | #c8e64a | #F4DA4C |
| --color-table-header | #f0f0ee | #F4F5F9 |
| --color-table-hover | #f0f8f4 | rgba(100,76,240,.04) |

### Macaron 柔彩 → 冷暖撞色浅底

| 旧变量 | 旧值 | 新变量 | 新值 |
|--------|------|--------|------|
| --macaron-mint / -light | #a7f3d0 / #d1fae5 | --surface-success / -light | #dcfce7 / #f0fdf4 |
| --macaron-yellow / -light | #fde68a / #fef3c7 | --surface-accent / -light | #fef5d0 / #fffbeb |
| --macaron-coral / -light | #fecaca / #fee2e2 | --surface-danger / -light | #fee2e2 / #fef2f2 |
| --macaron-purple / -light | #c4b5fd / #ede9fe | --surface-primary / -light | #ede9fe / #f5f3ff |
| --macaron-blue / -light | #bae6fd / #e0f2fe | --surface-info / -light | #e8e4fd / #f5f3ff |

### 语义色 hover/pressed 完整态

| Token | 值 |
|-------|-----|
| --color-primary-hover | #7B68F5 |
| --color-primary-pressed | #4F3EC9 |
| --color-success-hover | #16A34A |
| --color-success-pressed | #15803D |
| --color-warning-hover | #D4842E |
| --color-warning-pressed | #B86E1A |
| --color-info-hover | #A196F8 |
| --color-info-pressed | #6C5CE0 |

### LoginPage 蓝色体系映射

| 旧值 | 新值 | 用途 |
|------|------|------|
| #111C33 | #09061B | 背景深色 |
| #1a2744 | #12102a | 背景中间 |
| #1F3A5F | #1A1540 | 背景浅档 |
| #1F5BD7 | #644CF0 | 主按钮 |
| #1849B0 | #4F3EC9 | 按钮 hover |
| #6B7A90 | #A0A0A8 | 弱文字 |
| rgba(31,91,215,*) | rgba(100,76,240,*) | 光晕 |

### 家长端 darkTheme 绿 → 新色

| 旧值 | 新值 | 出现位置 |
|------|------|---------|
| #63e2b7 | #F4DA4C | Naive dark primaryColor（金黄） |
| #18a058 | #644CF0 | 手写 primary 引用 |
| #36ad6a | #7B68F5 | primary hover |

### CardEditor 绿系映射

| 旧值 | 新值 | 说明 |
|------|------|------|
| #2d5a3d | #644CF0 | 按钮/强调 |
| #1a2e1f | #09061B | 深色文字 |
| #5a6b5e | #5a5a68 | 次文字 |
| #e8f8ee | #ede9fe | 状态浅底 |
| #f0f4f1 | #F4F5F9 | 面板背景 |
| #f9fafb | #FBFBFD | 输入框底 |

---

## Naive UI 主题覆盖（完整）

```javascript
export const themeOverrides = {
  common: {
    primaryColor: '#644CF0',
    primaryColorHover: '#7B68F5',
    primaryColorPressed: '#4F3EC9',
    primaryColorSuppl: '#7B68F5',
    successColor: '#22C55E',
    successColorHover: '#16A34A',
    successColorPressed: '#15803D',
    successColorSuppl: '#4ADE80',
    errorColor: '#dc2626',
    errorColorHover: '#ef4444',
    errorColorPressed: '#b91c1c',
    errorColorSuppl: '#f87171',
    warningColor: '#ED9A51',
    warningColorHover: '#D4842E',
    warningColorPressed: '#B86E1A',
    warningColorSuppl: '#F5B77A',
    infoColor: '#8B7AF5',
    infoColorHover: '#A196F8',
    infoColorPressed: '#6C5CE0',
    infoColorSuppl: '#B4A8F8',
    fontSize: '16px',
    fontSizeMini: '12px',
    fontSizeTiny: '13px',
    fontSizeSmall: '14px',
    fontSizeMedium: '16px',
    fontSizeLarge: '18px',
    fontSizeHuge: '18px',
    borderRadius: '12px',
    borderRadiusSmall: '8px',
    borderColor: '#E8E8EF',
    bodyColor: '#F4F5F9',
    cardColor: '#ffffff',
    tableHeaderColor: '#F4F5F9',
    textColor1: '#09061B',
    textColor2: '#5a5a68',
    textColor3: '#A0A0A8',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
  },
  Button: {
    borderRadiusMedium: '12px',
    borderRadiusLarge: '14px',
    borderRadiusSmall: '8px',
    fontWeightStrong: '700',
    fontSizeMedium: '16px',
    fontSizeLarge: '18px',
    fontSizeSmall: '14px',
    heightMedium: '40px',
    heightLarge: '44px',
    heightSmall: '36px',
    paddingMedium: '0 24px',
    paddingLarge: '0 28px',
  },
  Card: {
    borderRadius: '18px',
    borderColor: '#F1F2F6',
    boxShadow: '0 2px 8px rgba(9,6,27,0.04)',
    paddingSmall: '18px 22px',
    paddingMedium: '22px 26px',
    titleFontSizeMedium: '18px',
    titleFontSizeSmall: '16px',
    titleFontWeight: '700',
  },
  DataTable: {
    borderRadius: '14px',
    thColor: '#F4F5F9',
    thTextColor: '#A0A0A8',
    thFontWeight: '700',
    tdColor: '#ffffff',
    thPaddingSmall: '14px 20px',
    thPaddingMedium: '16px 24px',
    tdPaddingSmall: '14px 20px',
    tdPaddingMedium: '16px 24px',
    fontSize: '14px',
  },
  Tag: {
    borderRadius: '999px',
    fontSizeSmall: '12px',
    fontSizeMedium: '13px',
    fontSizeTiny: '12px',
    heightSmall: '28px',
    heightMedium: '28px',
    heightTiny: '24px',
  },
  Input: {
    borderRadius: '12px',
    fontSizeMedium: '16px',
    fontSizeLarge: '16px',
    heightMedium: '44px',
    heightLarge: '48px',
    border: '1px solid #E8E8EF',
    borderHover: '1px solid #644CF0',
    borderFocus: '1px solid #644CF0',
  },
  Select: {
    borderRadius: '12px',
    fontSizeMedium: '16px',
    fontSizeLarge: '16px',
    heightMedium: '44px',
    heightLarge: '48px',
  },
  Dialog: {
    borderRadius: '18px',
    titleFontSize: '20px',
    fontSize: '16px',
  },
  Modal: {
    borderRadius: '18px',
  },
  Message: {
    borderRadius: '12px',
    fontSize: '16px',
  },
  Menu: {
    borderRadius: '8px',
    itemTextColor: '#5a5a68',
    itemTextColorActive: '#644CF0',
    fontSize: '16px',
  },
  Progress: {
    railColor: '#F4F5F9',
    fillColor: '#644CF0',
  },
  Statistic: {
    valueFontSize: '32px',
    labelFontSize: '14px',
  },
  Tabs: {
    tabBorderRadius: '8px',
    tabFontSizeMedium: '16px',
    tabFontSizeLarge: '18px',
    tabFontSizeSmall: '14px',
    colorSegment: '#F4F5F9',
  },
  Pagination: {
    itemFontSize: '14px',
    buttonFontSize: '14px',
  },
  Form: {
    labelFontSizeTopMedium: '14px',
    feedbackFontSizeMedium: '14px',
  },
  Empty: {
    textColor: '#A0A0A8',
    fontSize: '14px',
  },
  Dropdown: {
    fontSize: '16px',
    optionTextColor: '#5a5a68',
    borderRadius: '12px',
  },
  Alert: {
    borderRadius: '12px',
  },
}
```

## ECharts 全局色板

```javascript
// src/config/chartTheme.js（新建）
export const CHART_PALETTE = ['#644CF0', '#F4DA4C', '#ED9A51', '#22C55E', '#8B7AF5', '#09061B']
export const CHART_TEXT_COLOR = '#A0A0A8'
export const CHART_SPLIT_COLOR = '#F1F2F6'
export const CHART_BG = 'transparent'
```

## G6 节点色板

```javascript
// 更新 heatmapUtils.js
export const NODE_COLORS = {
  default: '#644CF0',
  highlight: '#F4DA4C',
  warning: '#ED9A51',
  success: '#22C55E',
  muted: '#A0A0A8',
}
```

---

## 执行计划

### T0：前置 — 全量色值 Inventory + 截图基线

| 步骤 | 内容 |
|------|------|
| T0.1 | grep 所有旧色值（#1a7a4f/#c8e64a/#10b981/#145f3d/#22956a/#72726c/#555550/#1a1a1a/#63e2b7/#18a058/#2d5a3d/#1F5BD7/#111C33），输出完整文件:行号清单 |
| T0.2 | grep CSS 别名变量引用（--primary-color/--border-color/--body-color/--text-color-*），确认无未定义变量 |
| T0.3 | 关键 10 页截图基线（Login/Dashboard/ExamList/GradingDispatch/AiGrading/Analytics/KnowledgeTree/Conduct/Parent/CardEditor） |

**质量门禁**：每 Wave 结束后执行 `grep -rn "旧色值列表" src/ --include="*.vue" --include="*.js" --include="*.css"` 确认零残留。

### Wave 1：全局基础设施 + 共享 Palette

| Task | 文件 | 内容 |
|------|------|------|
| T1 | `variables.css` | 全量替换（映射表），含语义色扩展、表格色、侧栏色 |
| T2 | `variables.css` | 补充 CSS 别名兼容层：`--primary-color: var(--color-primary)` 等，让散落引用自动跟随 |
| T3 | `theme.js` | Naive UI 完整覆盖（上方 theme 全文），含 hover/pressed 全状态 |
| T4 | `global.css` | 工具类色值 + 统计卡 + 标签 + 表头 + 硬编码色值 |
| T5 | `src/config/chartTheme.js`（新建） | ECharts 全局色板 + 导出常量 |
| T6 | `index.html` | Inter 字体 preload + Google Fonts link |
| T7 | `heatmapUtils.js` | G6 节点色板替换 |

**Wave 1 门禁**：`npx vitest run` 全绿 + grep 旧值在 variables.css/theme.js/global.css 中零残留。

### Wave 2：壳层 + 登录 + 家长端主题注入

| Task | 文件 | 内容 |
|------|------|------|
| T8 | `AppHeader.vue` | #1a1a1a → #09061B，加 pill 导航样式（可选，或保持当前深色顶栏微调） |
| T9 | `AppSidebar.vue` | 翠绿底 → 深墨底，激活态金黄，hover 态调整 |
| T10 | `AppShell.vue` | body 背景确认为 var(--color-bg)，可选加渐变光晕 |
| T11 | `LoginPage.vue` | 6 个蓝色值按映射表替换 → 深墨渐变 + 紫色主按钮 |
| T12 | `ParentLayout.vue` | 注入 themeOverrides（金黄主色版），去掉裸 darkTheme |
| T13 | Parent 8 页 | #63e2b7/#18a058 → var(--color-primary) 或 #F4DA4C/#644CF0 |
| T14 | `public/card-editor/styles.css` | 绿系 6 值替换（映射表 CardEditor 段） |

**Wave 2 门禁**：vite build 成功 + Login/Parent/CardEditor 页面视觉确认。

### Wave 3：业务页面（按域分批）

| Task | 域 | 文件 | 重点 |
|------|-----|------|------|
| T15 | 仪表盘 | `DashboardPage.vue` | macaron → surface-* 变量，ECharts 用 chartTheme |
| T16 | 分析 | `AnalyticsPage.vue` / `AnalyticsReportPage.vue` / `AnalyticsTrendPage.vue` | 硬编码色 + ECharts 配色统一 |
| T17 | 阅卷 | `GradingDispatchPage.vue` + 3 子组件 / `AiGradingPage.vue` + 3 子组件 | 阶段状态色、CSS 别名引用 |
| T18 | 考试 | `ExamListPage.vue` / `ExamDetailPage.vue` + 5 子 Tab | 标签/状态色 |
| T19 | 手动阅卷 | `MarkingSelectPage.vue` / `MarkingPage.vue` / `MarkingAssignPage.vue` / `MarkingProgressPage.vue` | 操作按钮 |
| T20 | 知识图谱 | `KnowledgeTreePage.vue` / `ConceptMapPanel.vue` / `ColorModeToggle.vue` / G6 相关 | G6 节点色 + heatmap + 面板 |
| T21 | 德育 | `conduct/` 9 页 + `ConductDashboard.vue` | #63e2b7 替换 + 积分色 |
| T22 | 教务 | `SchoolsPage` / `StudentsPage` / `TeachersPage` / `SchoolSettingsPage` / `SubjectSelectionsPage` / `TeacherAssignmentsPage` | 表格密集页，主要跟随 theme.js |
| T23 | 组件层 | `analytics/` 下 StatCard/TrendLine/RadarChart/KnowledgeHeatmap 等 | 内嵌色值 |
| T24 | 其他 | `CardEditorDevPage` / `GradingResultsPage` / `TeacherReviewPage` / `ReviewPage` | 零散硬编码 |

**Wave 3 门禁**：每完成一个域，跑 `npx vitest run` + grep 该域文件旧色零残留。

### Wave 4：收尾验证

| Task | 内容 |
|------|------|
| T25 | 全量 grep 扫描确认零残留旧色值 |
| T26 | `npx vitest run` 全量通过 |
| T27 | `npx vite build` 成功 |
| T28 | 关键 10 页截图 vs T0 基线对比 |
| T29 | WCAG 对比度验证：金黄文字在深底（≥4.5:1）、浅底前景色验证 |
| T30 | 删除 ui-demo.html / ui-demo-v2.html（demo 使命完成） |

---

## 排除范围

- `dist/` — 构建产物，不手改
- `_frozen/` — 冻结路由历史
- `ui-demo*.html` — Wave 4 T30 删除
- 后端代码 — 不涉及
- 布局/路由/交互逻辑 — 不改

## 纳入范围（显式声明）

- `public/card-editor/styles.css` — Wave 2 T14
- `src/layouts/ParentLayout.vue` — Wave 2 T12
- `src/components/knowledge-tree/heatmapUtils.js` — Wave 1 T7
- `index.html` — Wave 1 T6（字体）

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Naive UI 组件内部色值不完全跟随 theme.js | T3 覆盖全状态色 + Wave 3 逐组件验证 |
| 家长端 darkTheme 隔离 | T12 显式注入 themeOverrides |
| CardEditor 打印/导出样式不一致 | T14 同步 public CSS |
| ECharts 页面级硬编码 | T5 先建共享色板，T15-T16 替换引用 |
| G6 独立色系 | T7 + T20 统一 |
| CSS 别名未定义但在用 | T2 补充兼容层 |
| 金黄文字对比度不达 WCAG | 定义配对 token（金底→深墨文字），T29 验证 |
| 44 页同时变脸回归 | 分 Wave + 每 Wave 门禁 |

## 验收标准

1. grep 旧色值（完整清单）→ 零结果
2. `npx vitest run` 全量通过（0 failed）
3. `npx vite build` 成功
4. mcu.asia 全页面视觉一致（冷暖撞色）
5. WCAG AA 对比度（正文 ≥ 4.5:1，大文字 ≥ 3:1）
6. 家长端/制卡器/知识图谱无色彩断裂
