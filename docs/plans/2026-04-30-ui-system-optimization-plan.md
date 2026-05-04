---
baseline_command: "grep -Erohn '#[0-9a-fA-F]{6}' src/ --include='*.vue' --include='*.css' --include='*.js' | grep -v node_modules | grep -v _backup | grep -v _frozen | wc -l"
baseline_verified_at: "2026-04-30T22:32:12+08:00"
baseline_count: 666
---

# edu-cloud 前端 UI 系统性优化计划

> 2026-04-30 | Claude×GPT 双模型共识方案 | T3
> 调研基础：6 路并行调研（48 次 WebSearch + 12 次 WebFetch）+ 3 轮双模型辩论

## 背景与动机

edu-cloud 前端（Vue 3.5 + Vite 7 + Naive UI 2.44）经历快速迭代后积累了大量样式技术债：

| 问题 | 量化 |
|------|------|
| 字号不规则（含 17px 无意义档） | 449 处 font-size 声明 |
| 字重偏重（600/700/800） | 60 处 font-weight 700/800 |
| 语义色不统一（成功色 5 种变体） | success: #10b981/#16a34a/#2a9d8f/#4ade80/#6ee7a0 |
| 硬编码颜色 | 666 处 hex 色值（排除 backup/frozen） |
| text-muted 对比度不达标 | 2.8:1（WCAG AA 要求 4.5:1） |
| 图标方案混用 | 5 种方案并存 |
| 圆角偏大且档位混乱 | 12/16/20/24/50px 共 5 档 |

**目标**：建立统一的设计 Token 体系，分 5 阶段渐进优化，最终达到视觉一致、可维护、可扩展。

## 用户画像约束

- 教师/教务/班主任：年龄 40+
- 场景：数据表格密集（成绩/考试）、阅卷操作、分析报告
- 微软雅黑只有 400/700 两档字重，500/600 在部分系统字体上会降级到 400
- **字号不能过小**，14px 仅用于辅助信息，正文保持 16px

## 关键决策（Claude×GPT 共识）

| 决策点 | Claude 原案 | GPT 意见 | 最终共识 |
|--------|------------|---------|---------|
| 基础字号 | 14px | 16px | **三基准：正文 16 / 控件 15 / 数据密集 14** |
| 字体栈 | Inter + HarmonyOS Sans | 系统字体 | **Phase 1 不动，Phase 2 观察 Inter** |
| 圆角 | 4/8/16 | 6/10/16 | **4/8/12/16 + full** |
| rgba 文字色 | rgba(0,0,0) | rgba(15,26,18) 绿调 | **实测对比；有色背景必须实色** |
| 暗色模式 | Phase 3 | Phase 5 | **Phase 5，先考虑护眼模式** |
| 硬编码清理 | 一次性 | 渐进式 | **随页面改造同步清理** |

## 待实测项

| 项目 | 对比方案 | 决定阶段 |
|------|---------|---------|
| rgba 基底色 | `rgba(0,0,0,a)` vs `rgba(15,26,18,a)` | Phase 1 实测 |
| Inter 前置 | 加 vs 不加（截图对比） | Phase 2 |
| 统计数字字号 | 32px vs 36px | Phase 2 Dashboard |

---

## Phase 1：基础 Token + Naive UI 主题对齐

### 目标
重建 variables.css / theme.js / global.css，建立统一 Token 体系，不改页面组件。

### 改动文件（4 个）

| 文件 | 行数 | 改动类型 |
|------|------|---------|
| `src/main.js` | — | 确认/补充 variables.css + global.css 导入（P-001） |
| `src/assets/styles/variables.css` | 70 | 重写 Token 定义 + 旧变量兼容 alias（P-004） |
| `src/theme.js` | 122 | 重写 Naive UI 主题覆盖 |
| `src/assets/styles/global.css` | 140 | 更新工具类引用 Token |

### 前置验证（P-001 修复）

当前 `main.js` 可能未导入 `variables.css` / `global.css`。Phase 1 第一步必须验证导入链：
```bash
grep -n "variables.css\|global.css" src/main.js src/App.vue
```
如果未导入，在 `src/main.js` 顶部添加：
```javascript
import './assets/styles/variables.css'
import './assets/styles/global.css'
```
验证方式：浏览器 DevTools 检查 `document.documentElement` 的 computed style 中 `--fs-base` 是否为 `16px`。

### 旧变量兼容策略（P-004 + P-011 修复）

**策略**：Phase 1 **不重命名任何现有变量**。新 Token 作为新增定义添加到 `variables.css`，旧变量原地保留原值不变。Phase 2/3 页面改造时逐步将旧变量引用替换为新 Token，Phase 3 结束后删除无引用的旧变量。

**具体做法**：
- 旧 `variables.css` 的 70 行全部保留，不修改、不删除
- 新 Token（`--fs-*`、`--fw-*`、`--lh-*`、`--r-xs/sm/md/lg/full`、`--text-primary` 等）**追加**到文件末尾
- 旧圆角 `--radius-sm: 12px` 与新 `--r-xs: 4px` 并存（名称不冲突）
- 唯一需要修改旧值的是 `--color-success`（从 `#16a34a` → `#10b981`，与 theme.js 统一）和 `--color-danger`（从 `#dc2626` → `#ef4444`）
- 旧 `--shadow-sm/md/lg/xl` 保留原值；新阴影用新名 `--shadow-elevation-sm/md/lg`（或暂不引入新阴影名，直接就地更新旧变量值）
- `--font-sans`、`--macaron-*`、`--space-*`、`--z-*`、`--transition` 全部保留不动

**旧变量完整保留清单**（来自当前 `src/assets/styles/variables.css`，共 51 个，逐条对齐文件 :1~:70）：

| 行号 | 变量名 | 处理 |
|------|--------|------|
| 3 | `--color-primary` | 原值保留 |
| 4 | `--color-primary-dark` | 原值保留 |
| 5 | `--color-primary-light` | 原值保留 |
| 6 | `--color-accent` | 原值保留 |
| 7 | `--color-accent-hover` | 原值保留 |
| 8 | `--color-bg` | 原值保留 |
| 9 | `--color-bg-alt` | 原值保留 |
| 10 | `--color-bg-card` | 原值保留 |
| 11 | `--color-text` | 原值保留（Phase 2 逐步迁移到 --text-primary） |
| 12 | `--color-text-secondary` | 原值保留 |
| 13 | `--color-text-muted` | 原值保留 |
| 14 | `--color-border` | 原值保留 |
| 15 | `--color-border-light` | 原值保留 |
| 18 | `--color-success` | **值修改** `#16a34a` → `#10b981`（与 theme.js 统一） |
| 19 | `--color-danger` | **值修改** `#dc2626` → `#ef4444`（统一） |
| 20 | `--color-warning` | 原值保留 `#f59e0b` |
| 21 | `--color-info` | **值修改** `#2080f0` → `#3b82f6`（统一为 Tailwind blue-500） |
| 22 | `--color-bg-deep` | 原值保留 |
| 25-34 | `--macaron-*`（10 个） | 全部原值保留 |
| 37 | `--radius-sm` | 原值保留 `12px`（新 Token 用 `--r-sm: 8px`，不冲突） |
| 38 | `--radius-md` | 原值保留 `16px`（新 Token 用 `--r-md: 12px`） |
| 39 | `--radius-lg` | 原值保留 `20px`（新 Token 用 `--r-lg: 16px`） |
| 40 | `--radius-xl` | 原值保留 `24px` |
| 41 | `--radius-pill` | 原值保留 `50px` |
| 44 | `--shadow-sm` | **值修改** → 中性阴影 |
| 45 | `--shadow-md` | **值修改** → 中性阴影 |
| 46 | `--shadow-lg` | **值修改** → 中性阴影 |
| 47 | `--shadow-xl` | 原值保留 |
| 50 | `--font-sans` | 原值保留 |
| 53-60 | `--space-1` ~ `--space-10`（8 个） | 全部原值保留 |
| 63 | `--transition` | 原值保留 |
| 66-69 | `--z-sidebar/header/overlay/modal`（4 个） | 全部原值保留 |

**总计**：51 个旧变量中，3 个值修改（success/danger/info 统一语义色）+ 3 个阴影值更新 = 6 个修改；其余 45 个原值完整保留。

**新 Token 命名策略**（避免冲突）：

| 新 Token | 旧变量（保留） | 说明 |
|----------|---------------|------|
| `--r-xs/sm/md/lg/full` | `--radius-sm/md/lg/xl/pill` | 前缀 `r-` vs `radius-`，不冲突 |
| `--fs-xs/sm/md/base/lg/xl/2xl/display` | 无旧变量 | 全新 |
| `--fw-regular/medium/semibold` | 无旧变量 | 全新 |
| `--lh-tight/snug/normal/relaxed` | 无旧变量 | 全新 |
| `--text-primary/secondary/tertiary/disabled` | `--color-text/text-secondary/text-muted` | 新名并存，不冲突 |
| `--color-success-bg-subtle` ~ `--color-info-text-strong` | 无旧变量 | 全新扩展 |

### 回滚策略（P-007 修复）

Phase 1 拆为 3 个可独立回滚的提交：
1. **Commit 1**: `variables.css` Token 定义 + 兼容 alias → `git tag ui-opt-p1-tokens`
2. **Commit 2**: `theme.js` Naive UI 覆盖 → `git tag ui-opt-p1-theme`
3. **Commit 3**: `global.css` 工具类更新 + `main.js` 导入确认 → `git tag ui-opt-p1-global`

回滚命令：`git revert <commit>` 即可独立回退某层改动。

### Task 1.1：字号体系重建

**Before**: 16/17/18/20/24/30/36px（7 档不规则）
**After**: 12/14/15/16/18/20/24/32px（8 档三基准）

```css
/* variables.css */
--fs-xs: 12px;       /* badge, tooltip, 图例 */
--fs-sm: 14px;       /* 表格内容, 辅助说明, 紧凑控件 */
--fs-md: 15px;       /* 控件默认（Naive UI common.fontSize） */
--fs-base: 16px;     /* 正文, 报告, 详情页 */
--fs-lg: 18px;       /* 卡片标题, 分组标题 */
--fs-xl: 20px;       /* 模块标题, 侧栏区块标题 */
--fs-2xl: 24px;      /* 页面一级标题 */
--fs-display: 32px;  /* 统计主数字, 大看板 */
```

**theme.js 对应变更**:
```javascript
common: {
  fontSize: '15px',        // 控件基准（原 16px）
  fontSizeMini: '12px',    // 原 16px → 恢复层级
  fontSizeTiny: '12px',    // 原 16px
  fontSizeSmall: '14px',   // 原 16px
  fontSizeMedium: '15px',  // 原 16px
  fontSizeLarge: '16px',   // 原 17px
  fontSizeHuge: '18px',    // 原 18px → 保留
}
```

**测试契约**:
- 入口：打开 Dashboard、ExamList、AnalyticsPage
- 反例：如果 fontSizeMini 仍为 16px，badge/tooltip 文字与正文无区分
- 边界：14px 中文在不同系统字体下是否清晰（需截图确认）
- 回归：全量 vitest run 确认无断言依赖字号
- 命令：`npm run build && npm run test`

### Task 1.2：字重收敛

**Before**: 600/700/800（偏重，缺 400/500）
**After**: 400/500/600（3 档）

```css
/* variables.css */
--fw-regular: 400;    /* 正文, 表格内容 */
--fw-medium: 500;     /* 按钮, 强调文字 */
--fw-semibold: 600;   /* 页面标题, 卡片标题 */
```

**影响面**：60 处 font-weight 700/800 需逐步替换（Phase 2/3 同步）

**theme.js 变更**:
- DataTable.thFontWeight: '600' → 保留
- 移除 global.css 中 `.page-title` 的 `font-weight: 800` → `600`
- 移除 `.stat-card .stat-value` 的 `font-weight: 800` → `600`

**测试契约**:
- 入口：Dashboard 页面标题、KpiCard 数字、DataTable 表头
- 反例：如果字重仍为 800，标题在系统字体下显得过于粗重
- 边界：font-weight 500 在 PingFang SC 下是否有效果（Mac 有，部分系统字体可能降级到 400）
- 回归：`npx vitest run` 确认无断言依赖 font-weight 值
- 命令：`npx vitest run && npx vite build`

### Task 1.3：行高系统

**Before**: 1.1/1.2/1.6（跳跃大）
**After**: 1.2/1.4/1.5/1.6（4 档渐进）

```css
/* variables.css */
--lh-tight: 1.2;     /* 大标题(>=24px), 统计数字 */
--lh-snug: 1.4;      /* 表格单元格, 按钮, 标签 */
--lh-normal: 1.5;    /* 描述, 帮助文字, 卡片内容 */
--lh-relaxed: 1.6;   /* 正文段落（body 默认） */
```

**测试契约**:
- 入口：global.css body line-height、.page-title、.stat-card
- 反例：如果 body 行高变为 1.4，正文段落会显得拥挤
- 边界：line-height 1.2 在多行中文标题场景是否过紧（超过 2 行时需验证）
- 回归：`npx vitest run`
- 命令：`npx vitest run && npx vite build`

### Task 1.4：圆角收敛

**Before**: 12/16/20/24/50px（5 档偏大）
**After**: 4/8/12/16px + full（4 档 + 圆形）

```css
/* variables.css — 新圆角 Token（不与旧 --radius-sm/md/lg 冲突） */
--r-xs: 4px;      /* 表格内部元素, 小 Tag, Badge, Tooltip */
--r-sm: 8px;      /* 按钮, 输入框, Select, DatePicker */
--r-md: 12px;     /* 卡片, 面板, Dropdown */
--r-lg: 16px;     /* Modal, Drawer, 大容器 */
--r-full: 999px;  /* 头像, 开关, 纯图标按钮 */
/* 旧 --radius-sm(12px)/--radius-md(16px)/--radius-lg(20px)/--radius-xl(24px)/--radius-pill(50px) 保留不变 */
```

**theme.js 变更**（Naive UI 组件内置圆角覆盖，不依赖 CSS 变量名）:
```javascript
common: {
  borderRadius: '8px',       // 原 12px → 对应新 --r-sm 设计值
},
Button: {
  borderRadiusMedium: '8px', // 原 50px → 核心收敛
  borderRadiusSmall: '8px',
  borderRadiusLarge: '8px',
},
Card: { borderRadius: '12px' },  // 原 16px → 对应新 --r-md
Dialog: { borderRadius: '16px' }, // 原 20px → 对应新 --r-lg
Input: { borderRadius: '8px' },   // 原 12px → 对应新 --r-sm
Tag: { borderRadius: '4px' },     // 原 50px → 对应新 --r-xs
```

注意：Naive UI 的 themeOverrides 使用像素值字符串，不引用 CSS 变量。CSS 变量 `--r-*` 用于自定义组件的 scoped style 中。

**测试契约**:
- 入口：Button 圆角、Tag 形态、Card 边角、Dialog 弹窗
- 反例：如果 Button.borderRadius 仍为 50px，按钮在行内会显得突兀（药丸形）
- 边界：Tag 4px 圆角在极短文本（1-2 字）下是否视觉协调
- 回归：`npx vitest run`
- 命令：`npx vitest run && npx vite build`

### Task 1.5：语义色统一

**Before**: 成功色 5 种变体、危险色 3 种变体
**After**: 每个语义色 7 个 Token（bg-subtle / bg / border / base / text-muted / text / text-strong）

```css
/* variables.css — Success */
--color-success-bg-subtle: #ecfdf5;
--color-success-bg: #d1fae5;
--color-success-border: #6ee7b7;
--color-success: #10b981;
--color-success-text-muted: #059669;
--color-success-text: #047857;         /* AA 4.5:1 */
--color-success-text-strong: #065f46;  /* AAA 7:1 */

/* Danger */
--color-danger-bg-subtle: #fef2f2;
--color-danger-bg: #fee2e2;
--color-danger-border: #fca5a5;
--color-danger: #ef4444;
--color-danger-text-muted: #dc2626;
--color-danger-text: #b91c1c;          /* AA */
--color-danger-text-strong: #991b1b;

/* Warning */
--color-warning-bg-subtle: #fffbeb;
--color-warning-bg: #fef3c7;
--color-warning-border: #fcd34d;
--color-warning: #f59e0b;
--color-warning-text-muted: #d97706;
--color-warning-text: #b45309;         /* AA */
--color-warning-text-strong: #92400e;

/* Info */
--color-info-bg-subtle: #eff6ff;
--color-info-bg: #dbeafe;
--color-info-border: #93c5fd;
--color-info: #3b82f6;
--color-info-text-muted: #2563eb;
--color-info-text: #1d4ed8;            /* AA */
--color-info-text-strong: #1e40af;
```

**theme.js 变更**:
```javascript
common: {
  successColor: '#10b981',
  successColorHover: '#059669',
  successColorPressed: '#047857',
  errorColor: '#ef4444',
  warningColor: '#f59e0b',
  infoColor: '#3b82f6',
}
```

### Task 1.6：文字色体系

**Before**: 3 档实色（#0f1a12 / #3d4f42 / #6b7d70），text-muted 不达标
**After**: 4 档 rgba + 语义实色

```css
/* 中性文字（中性背景专用） */
--text-primary: rgba(15, 26, 18, 0.88);    /* ~13:1 */
--text-secondary: rgba(15, 26, 18, 0.68);  /* ~7.5:1 */
--text-tertiary: rgba(15, 26, 18, 0.48);   /* ~4.9:1 AA */
--text-disabled: rgba(15, 26, 18, 0.28);   /* 豁免 */
--text-placeholder: rgba(15, 26, 18, 0.38);

/* 反色（深色背景） */
--text-inverse: rgba(255, 255, 255, 0.92);

/* 语义文字色（有色背景 override） */
--text-success: var(--color-success-text);
--text-danger: var(--color-danger-text);
--text-warning: var(--color-warning-text);
--text-info: var(--color-info-text);
```

### Task 1.7：阴影收敛

**Before**: 4 级，基于绿色 rgba(26,46,31)
**After**: 4 级中性阴影

```css
--shadow-none: none;
--shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
--shadow-md: 0 4px 8px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.03);
--shadow-lg: 0 8px 24px rgba(0,0,0,0.08), 0 4px 8px rgba(0,0,0,0.03);
```

### Task 1.8：间距 Token 保留

当前 4px 倍数体系（4~40px 共 8 档）保持不变，不做调整。

### Phase 1 验收标准

- [ ] `variables.css` 所有 Token 定义完成
- [ ] `theme.js` Naive UI 主题覆盖更新
- [ ] `global.css` 工具类引用新 Token
- [ ] `npm run build` 成功
- [ ] `npm run test` 2404 测试全绿
- [ ] Dashboard / ExamList / LoginPage 截图对比，无严重视觉回归
- [ ] rgba 文字色 vs 纯黑 rgba 实测对比截图

---

## Phase 2：Shell + 5 核心页面试点

### 目标
在 6 个高影响区域落地新 Token，清理相关硬编码颜色，验证体系可行性。

### 页面范围（6 个）

| 优先序 | 页面/组件 | 原因 | 预估硬编码色值 |
|--------|----------|------|--------------|
| 1 | **Shell**：AppShell + AppHeader + AppSidebar + RoleSwitcher | 全局观感入口 | ~30 处 |
| 2 | **DashboardPage** + KpiCard + DashboardCard + ActivityFeed | 首页第一印象 | ~50 处 |
| 3 | **ExamListPage** | 考试管理核心列表 | ~20 处 |
| 4 | **ExamDetailPage** + SubjectsTab + QuestionsTab | 考试详情核心链路 | ~30 处 |
| 5 | **AiGradingPage** + GradingPanel + QuestionList | 高频阅卷操作 | ~40 处 |
| 6 | **AnalyticsPage** + 图表组件 | 数据分析，图表密集 | ~50 处 |

### 每个页面的改造流程

```
1. 截图基线（改前 — Playwright MCP 截全页）
2. grep 该文件中的硬编码色值 → 映射到 Token
3. 替换 font-size / font-weight / border-radius → Token
4. 替换硬编码颜色 → CSS 变量
5. npm run test（确认无断言失败）
6. npm run build
7. 截图对比（改后 — 同一视口同一数据）
8. 视觉回归检查：字号 / 颜色 / 圆角 / 间距 / 对齐
```

### Task 2.1：Shell 改造

**文件清单**：
- `src/layouts/AppShell.vue`
- `src/components/shell/AppHeader.vue`（font-weight 800 → 600）
- `src/components/shell/AppSidebar.vue`（SidebarIcons 保留但对齐新尺寸）
- `src/components/shell/RoleSwitcher.vue`
- `src/components/shell/SchoolContext.vue`

**关注点**：侧栏宽度 220px/64px 不变；头部毛玻璃效果保留；导航图标尺寸统一到 20px。

### Task 2.2：Dashboard 改造

**文件清单**：
- `src/pages/DashboardPage.vue`
- `src/components/dashboard/KpiCard.vue`（stat-value 36→32px, weight 800→600）
- `src/components/dashboard/DashboardCard.vue`（Data URI mask 图标保留，圆角 → 12px）
- `src/components/dashboard/ActivityFeed.vue`
- `src/components/dashboard/WidgetGrid.vue`

**关注点**：KPI 数字 `tabular-nums` 保留；统计数字字号实测 32px vs 36px 后决定；马卡龙标签颜色保持，但确认文字色对比度。

### Task 2.3：ExamList 改造

**文件清单**：`src/pages/ExamListPage.vue`

**关注点**：DataTable 应用紧凑/默认密度；状态 Tag 圆角 50px → 4px。

### Task 2.4：ExamDetail 改造

**文件清单**：
- `src/pages/ExamDetailPage.vue`
- `src/pages/exam-detail/SubjectsTab.vue`
- `src/pages/exam-detail/QuestionsTab.vue`
- `src/pages/exam-detail/AnswersTab.vue`
- `src/pages/exam-detail/CardMakerTab.vue`
- `src/pages/exam-detail/VisualEditorTab.vue`

### Task 2.5：AiGrading 改造

**文件清单**：
- `src/pages/AiGradingPage.vue`
- `src/pages/ai-grading/GradingPanel.vue`
- `src/pages/ai-grading/QuestionList.vue`
- `src/pages/ai-grading/ExamSubjectSelector.vue`

**关注点**：左右分栏布局不变；阅卷操作区域可读性优先。

### Task 2.6：Analytics 改造

**文件清单**：
- `src/pages/AnalyticsPage.vue`
- `src/pages/AnalyticsTrendPage.vue`
- `src/pages/AnalyticsReportPage.vue`
- `src/pages/GradeAnalyticsPage.vue`

**关注点**：ECharts 配色需建立统一 viz palette；图表标注/图例字号 12px；数字全部 `tabular-nums`。

### Task 2.7：Inter 字体实测（可选）

- 在 `variables.css` 的 `--font-sans` 前面加入 `'Inter'`
- 截图对比（Dashboard + ExamList + Analytics）
- 检查中英混排基线对齐
- 根据结果决定保留或回滚

### Phase 2 验收标准

- [ ] 6 个区域改造完成，相关文件硬编码颜色清零
- [ ] 每个页面有 before/after 截图对比
- [ ] `npm run test` 全绿
- [ ] `npm run build` 成功

---

## Phase 3：推广 + Lint 规则

### 目标
将 Token 体系推广到第二批高频页面，建立自动化约束防止回退。

### 页面范围

**第二批（12 个）**：
- `LoginPage.vue`（品牌展示入口）
- `MarkingAssignPage.vue` / `MarkingSelectPage.vue` / `MarkingProgressPage.vue`（阅卷分配链路）
- `GradingDispatchPage.vue`（扫描调度）
- `GradingResultsPage.vue`（成绩结果）
- `ReviewPage.vue`（人工复核）
- `HomeworkPage.vue`（作业管理）
- `JointExamPage.vue` / `JointExamDetailPage.vue`（联考）
- `StudentsPage.vue` / `TeachersPage.vue`（人员管理）
- `SchoolSettingsPage.vue`（学校设置）

**第三批（视需要）**：
- `CalendarPage.vue` / `SemesterPage.vue` / `TimetablePage.vue` / `TeachingPlanPage.vue`
- `KnowledgeTreePage.vue` + 14 个 knowledge-tree 组件
- `conduct/*`（9 个德育页面）
- `parent/*`（9 个家长端页面）

### Task 3.1：第二批页面改造

每页同 Phase 2 流程：截图基线 → 替换 → 测试 → 对比。

### Task 3.2：自定义扫描脚本（P-006 修复）

不引入 Stylelint（当前项目无此依赖），改为自定义 shell 扫描脚本 `scripts/lint-styles.sh`（P-012 修复：排除 token 定义文件和 backup 目录）：

```bash
#!/bin/bash
# 扫描 Vue SFC <style> 中的违规模式（排除 token 定义文件）
# 只扫描 .vue 文件，不扫描 variables.css / global.css（token 定义文件必然含 hex）
EXIT=0
echo "=== Vue 组件硬编码颜色 ==="
grep -Ern '#[0-9a-fA-F]{6}' src/ --include="*.vue" \
  | grep -v node_modules | grep -v _backup | grep -v _frozen \
  | grep -v 'card-editor/' | grep -v 'CardEditor.vue' && EXIT=1

echo "=== font-size: 17px ==="
grep -rn 'font-size.*17px' src/ --include="*.vue" | grep -v node_modules && EXIT=1

echo "=== font-weight: 700/800 ==="
grep -Ern 'font-weight.*(700|800)' src/ --include="*.vue" | grep -v node_modules | grep -v _backup && EXIT=1

echo "=== border-radius: 50px ==="
grep -rn 'border-radius.*50px' src/ --include="*.vue" | grep -v node_modules | grep -v _backup && EXIT=1

[ $EXIT -eq 0 ] && echo "PASS: 未发现违规模式" || echo "WARN: 发现上述违规（当前为警告级）"
exit 0  # 不阻断构建，仅报告
```

**关键设计**：只扫描 `*.vue` 文件（组件级），不扫描 `*.css`（token 定义文件）。`variables.css` 和 `global.css` 作为 token 定义源，必然包含 hex 色值，不属于"硬编码"。同时排除 `card-editor/` 目录（独立原生 JS 模块，Scope 排除项）。

**package.json 新增脚本**：`"lint:styles": "bash scripts/lint-styles.sh"`

**测试契约**:
- 入口：`npm run lint:styles`
- 反例：如果脚本扫描 `variables.css`，会产生 30+ 条假阳性
- 边界：card-editor 内的 hex 应被排除
- 回归：不影响现有 ESLint 配置
- 命令：`npm run lint:styles`

### Task 3.3：颜色残留扫描

```bash
# Phase 3 结束时运行，目标：666 → <100
grep -rohn '#[0-9a-fA-F]\{6\}' src/ --include="*.vue" --include="*.css" --include="*.js" \
  | grep -v node_modules | grep -v _backup | grep -v _frozen | wc -l
```

### Phase 3 验收标准

- [ ] 第二批 12 个页面改造完成
- [ ] Lint 规则生效（warn 级）
- [ ] 硬编码颜色从 666 降到 <100
- [ ] `npm run test` 全绿

---

## Phase 4：图标系统迁移

### 目标
从 5 种图标方案收敛到统一的 AppIcon 体系。

### Task 4.1：基础设施

**安装依赖**：
```bash
npm install -D unplugin-icons @iconify/json
npm install lucide-vue-next
```

**Vite 插件配置**（`vite.config.js`）：
```javascript
import Icons from 'unplugin-icons/vite'
import { FileSystemIconLoader } from 'unplugin-icons/loaders'

plugins: [
  vue(),
  Icons({
    compiler: 'vue3',
    customCollections: {
      custom: FileSystemIconLoader('./src/assets/icons')
    }
  }),
]
```

### Task 4.2：AppIcon 组件封装

**`src/components/AppIcon.vue`**：
- Props：`name`(string) / `size`(number, default 20) / `color`(string, default 'currentColor')
- 内部注册表：name → 组件映射
- 渐进兼容：优先查 lucide，fallback 到 @vicons/ionicons5

**尺寸规范**：

| 尺寸 | 使用场景 |
|------|---------|
| 16px | 表格行内, Badge 前缀, Tag 前缀 |
| 20px | 按钮, 输入框前缀, 菜单项, 导航 |
| 24px | 页面标题区, 卡片头部, Tab |
| 32px | 空状态, 功能入口大图标 |

### Task 4.3：分批迁移

| 批次 | 范围 | 替换内容 |
|------|------|---------|
| Batch 1 | Shell（AppSidebar + AppHeader） | SidebarIcons.vue 16 个 SVG → lucide |
| Batch 2 | Dashboard（DashboardCard + DashboardPage） | 16 个 Data URI mask → AppIcon；DashboardPage.vue 快捷操作 ICON_SVGS 同步清理（P-009） |
| Batch 3 | SchoolSettingsPage + MarkingProgressPage | @vicons/ionicons5 → AppIcon；同步更新 SchoolSettingsPage.test.js 导入断言（P-008） |
| Batch 4 | ParentLayout + ParentBind | emoji → AppIcon + macaron 背景 |
| Batch 5 | 其他分散使用 | 逐文件替换 |

**保留项**：
- `CardEditor.vue` 内部图标（答题卡编辑器独立模块，不迁移）
- KaTeX 数学符号（不是 UI 图标）

### Task 4.4：清理旧依赖

Batch 5 完成后：
```bash
npm uninstall @vicons/ionicons5
# 删除 src/components/icons/SidebarIcons.vue
# 删除 DashboardCard.vue 中的 ICON_SVGS 常量
# 删除 DashboardPage.vue 中的 ICON_SVGS 常量（P-009）
```

**测试迁移（P-008 修复）**：
- `SchoolSettingsPage.test.js`：将 `from '@vicons/ionicons5'` 导入断言改为验证 AppIcon 渲染行为
- `DashboardPage.test.js`：将 DashboardCard icon prop 断言改为 AppIcon name prop
- 验证命令：`npx vitest run --reporter=verbose`

### Phase 4 验收标准

- [ ] AppIcon.vue 组件可用
- [ ] Shell + Dashboard 图标迁移完成
- [ ] 图标风格统一为 lucide stroke 风格
- [ ] 所有图标 currentColor，跟随父元素颜色
- [ ] `npm run test` 全绿
- [ ] `npm run build` 成功

---

## Phase 5：护眼/暗色模式

### 前提条件
- Phase 3 硬编码颜色 <100 处
- Token 体系稳定运行 >=2 周

### Task 5.0：前置依赖安装（P-005 修复）

```bash
npm install @vueuse/core
```

验证：`node -e "require('@vueuse/core')"` 或 `npx vitest run`

### Task 5.1：护眼浅色模式（优先）

降低对比度和亮度的"柔和模式"：

```css
[data-theme="soft"] {
  --color-bg: #faf9f7;
  --color-bg-alt: #f0efed;
  --text-primary: rgba(15,26,18,0.82);
  --text-secondary: rgba(15,26,18,0.60);
}
```

### Task 5.2：完整暗色模式（评估后决定）

**Naive UI 暗色覆盖模板**：
```javascript
import { darkTheme } from 'naive-ui'

const darkOverrides = {
  common: {
    primaryColor: '#34d399',
    bodyColor: '#141416',
    cardColor: '#1e1e22',
    modalColor: '#242428',
    textColorBase: 'rgba(255,255,255,0.87)',
    textColor1: 'rgba(255,255,255,0.87)',
    textColor2: 'rgba(255,255,255,0.65)',
    textColor3: 'rgba(255,255,255,0.45)',
    borderColor: '#303038',
    tableHeaderColor: '#242428',
  }
}
```

**切换机制**：
```javascript
import { useDark, useToggle } from '@vueuse/core'
const isDark = useDark()
const toggleDark = useToggle(isDark)
```

### Task 5.3：ECharts 暗色适配

```javascript
const darkVizPalette = [
  '#34d399', '#60a5fa', '#fbbf24', '#a78bfa',
  '#f87171', '#22d3ee', '#fb923c', '#a3e635'
]
```

### Phase 5 验收标准

- [ ] 护眼模式可切换
- [ ] 暗色模式下所有 Token 正确映射
- [ ] ECharts 图表暗色配色可读
- [ ] 无硬编码颜色导致的"穿透"
- [ ] 家长端现有 darkTheme 与新体系统一

---

## 风险管理

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Phase 1 全局 token+theme 改动影响全站布局 | **高** | **高** | 拆 3 个可独立回滚的提交（P-010）+ 每个提交后截图 Dashboard/ExamList/Login 三页基线 |
| 硬编码颜色替换语义误用 | 中 | 高 | 替换前列出 before→after 映射表 |
| 部分系统字体字重降级导致层级丢失 | 高 | 低 | 层级区分靠字号+颜色，不仅靠字重 |
| unplugin-icons 与现有 Vite 配置冲突 | 低 | 中 | Phase 4 先在分支验证 |
| ECharts 暗色适配不完整 | 中 | 中 | Phase 5 单独处理图表主题 |

## 不做的事（Scope 排除）

- 不做响应式/移动端适配（B 端后台以桌面为主）
- 不做国际化（纯中文系统）
- 不做动画/Micro-interaction 优化（当前已有基础动效）
- 不改 CardEditor 内部样式（独立原生 JS 模块）
- 不改 knowledge-tree G6 图表样式（Phase 3 酌情评估）
- 不引入 Tailwind（保持原生 CSS Variables 方案）

## 依赖关系

```
Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4
                                  \
                                   ──→ Phase 5
```

- Phase 2 依赖 Phase 1（Token 必须先定义）
- Phase 3 依赖 Phase 2（验证 Token 体系可行）
- Phase 4 独立于 Phase 3（图标不依赖颜色治理）
- Phase 5 依赖 Phase 3（硬编码清理 <100 后才能做暗色）
- Phase 4 和 Phase 5 可并行

## 度量指标

| 指标 | 当前 | Phase 1 后 | Phase 3 后 | Phase 5 后 |
|------|------|-----------|-----------|-----------|
| 硬编码颜色数 | 666 | 666（不变） | <100 | <20 |
| font-size 17px | 3 | 0 | 0 | 0 |
| font-weight 700/800 | 60 | 60（不变） | <10 | <5 |
| border-radius 50px | 4 | 0 | 0 | 0 |
| 图标方案数 | 5 | 5（不变） | 5→3 | 1 |
| WCAG AA 文字色达标率 | 部分 | 100%（token 层） | >90%（页面层） | 100% |
