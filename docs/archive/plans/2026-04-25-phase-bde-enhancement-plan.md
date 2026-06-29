---
baseline_command: "cd ~/projects/edu-cloud/frontend && npx vitest run"
baseline_verified_at: "2026-04-25 23:30"
baseline_count: 344
---

# Phase B+D+E 合并方案：学校管理 + 联考分析 + 德育补齐

**Date**: 2026-04-25
**Scope**: 10 个骨架页面纯前端增强，不动后端
**Tier**: T1（页面增强，消费已有 API）
**执行方式**: 新窗口，4 个并行 agent

---

## 1. 全局资产盘点

### 后端 API（全就位，不动）

**学校管理端点**（5 端点）：
- `POST/GET /api/v1/schools` — 创建/列表
- `GET/PATCH /api/v1/schools/{id}` — 详情/更新
- `POST /api/v1/schools/{id}/rotate-key` — 轮换 API Key

**学校配置端点**（8 端点）：
- `GET/PATCH /api/v1/schools/{id}/settings` — KV 配置
- `GET/PATCH /api/v1/schools/{id}/modules/{code}` — 模块开关
- `GET /api/v1/schools/{id}/modules/enabled` — 已启用列表
- `GET/PATCH /api/v1/schools/{id}/capabilities` — 能力矩阵
- `POST /api/v1/schools/{id}/capabilities/init` — 初始化

**联考端点**（7 端点）：
- `POST/GET /api/v1/joint-exams` — 创建/列表
- `GET /api/v1/joint-exams/{id}` — 详情（含参与校）
- `POST/DELETE /api/v1/joint-exams/{id}/participants` — 管理参与校
- `POST /api/v1/joint-exams/{id}/distribute` — 下发
- `POST /api/v1/joint-exams/{id}/force-complete` — 强制截止

**分析端点**（29 端点，只列本次相关的）：
- `GET /api/v1/analytics/report/trend/{grade|class|student}` — 三维趋势
- `GET /api/v1/analytics/power-options` — 级联筛选树
- `POST /api/v1/analytics/report/export` — 导出
- `GET /api/v1/analytics/exam/{id}/*` — 单考试多维分析

**德育端点**（30+ 端点，管理端）：
- `GET/POST /api/v1/conduct/classes/{id}/records` — 记录 CRUD
- `GET /api/v1/conduct/classes/{id}/rankings/{students|groups}` — 排行
- `GET /api/v1/conduct/classes/{id}/semesters` — 学期
- `POST /api/v1/conduct/classes/{id}/export/{records|rankings}` — 导出
- `GET /api/v1/conduct/classes/{id}/parents` — 家长列表
- `DELETE /api/v1/conduct/classes/{id}/parents/{uid}` — 移除家长

### 前端 API 层（全就位）

| 模块 | 文件 | 方法数 |
|------|------|--------|
| schools.js | 已有 | 3（list/create/get） |
| schoolSettings.js | 已有 | 4（modules/settings/toggle/capabilities） |
| jointExams.js | 已有 | 11（CRUD/participants/distribute/results） |
| analytics.js | 已有 | 20+（trend/report/segments/export） |
| conduct.js | 已有 | 28+（records/rankings/semesters/export/parents） |

### 10 个页面现状

| Phase | 页面 | 行数 | 现状诊断 |
|-------|------|------|---------|
| B | SchoolsPage | 77 | 纯表格+创建弹窗，无搜索/筛选/统计/学区过滤/状态标签 |
| B | SchoolSettingsPage | 116 | 3 Tab 结构已有但简陋；模块行白色硬编码；settings 纯表格无编辑；缺能力矩阵 Tab |
| D | JointExamPage | 163 | 状态筛选+表格+创建弹窗；缺统计卡/参与校数量/科目 JSON 输入太原始 |
| D | AnalysisPage | 23 | 三栏布局壳（WorkbenchLayout），无实际内容 |
| D | AnalyticsTrendPage | 154 | 考试多选+维度切换+折线图；缺导出/对比选择/双 Y 轴 |
| E | ConductDashboard | 162 | 4 统计卡+TOP/BOTTOM 学生+最近记录；缺趋势图/时间段切换 |
| E | ConductExport | 130 | 记录/排行 2 类导出+日期/学期筛选；功能基本完整，增强空间小 |
| E | ConductParents | 96 | 家长表格+移除；缺搜索/统计/邀请码管理入口 |
| E | ConductRankings | 173 | 学生/小组 Tab+学期筛选+奖牌；缺积分分布图/趋势 |
| E | ConductRecords | 175 | 分页表格+姓名搜索+日期筛选+删除；缺类型筛选/统计卡/批量操作 |

---

## 2. 增强方案（按 Agent 分组）

### Agent 1: 学校管理（SchoolsPage + SchoolSettingsPage）

**SchoolsPage（77→~200 行）**
1. 搜索栏：NInput 按学校名搜索（前端过滤）
2. 学区筛选：NSelect 按 district 过滤
3. 统计卡片：3 个 NStatistic（总学校数/活跃数/学区数）
4. 表格增强：加 district 列 + is_active 状态标签（NTag） + 学区列
5. 卡片视图切换：NRadioGroup 切换表格/卡片两种视图；卡片视图每校一张 NCard（名称+代码+学区+创建时间+状态）
6. 创建表单增强：加联系人、联系电话字段（如果后端支持）

**SchoolSettingsPage（116→~280 行）**
1. 暗色适配：`.module-row` border-bottom 白色硬编码→rgba
2. 模块管理增强：每个模块加描述文字+图标（MODULE_DESCRIPTIONS 映射表）
3. settings Tab 增强：KV 配置支持 inline 编辑（双击 value 弹出 NInput 编辑，调 PATCH settings）
4. 能力矩阵 Tab：新增第 4 个 Tab "能力矩阵"，调 capabilities API 展示角色×域×操作的 grid（NCheckbox 矩阵）
5. 统计摘要：顶部显示"已启用 N/M 模块"

### Agent 2: 联考+分析入口（JointExamPage + AnalysisPage + AnalyticsTrendPage）

**JointExamPage（163→~280 行）**
1. 统计卡片：3 个 NStatistic（总联考数/进行中/已完成），从列表 computed
2. 参与校数量：表格加"参与校数"列
3. 创建表单增强：科目输入从 JSON textarea 改为 NSelect multiple（固定科目列表选择），更友好
4. 进度指示：active 状态的联考行显示 NProgress（已完成校数/总参与校数）
5. 操作列增强：加"下发"按钮（draft→active）、"强制截止"按钮（active→done）
6. 空状态：无联考时引导创建

**AnalysisPage（23→~120 行）**
- 当前是空壳 WorkbenchLayout（三栏），实际组件（ContextPanel/DataView/StudioPanel）可能也是空的
- 改造为**分析中心入口页**：
1. 考试选择器（NSelect，从 /exams 获取列表）
2. 分析功能卡片网格（4 张卡片）：
   - "考试分析" → /analytics/{examId}
   - "成绩趋势" → /analytics/trend
   - "分析报告" → /analytics/report
   - "学生画像" → /profile/student/{id}（需先选学生）
3. 最近分析历史（如果有 API）
4. 保留 WorkbenchLayout import 但不作为默认视图

**AnalyticsTrendPage（154→~250 行）**
1. 图表暗色适配：ECharts textStyle/splitLine 用暗色变量
2. 双 Y 轴：左轴分数、右轴百分比（及格率/优秀率），参考 DashboardPage 的写法
3. 导出按钮：图表右上角"导出图片"按钮（ECharts getDataURL → download）
4. 对比模式：支持选择 2 个班级/学生同图对比（多系列 line）
5. 指标选择器：NCheckboxGroup 选择显示哪些指标（均分/最高/最低/中位数/及格率/优秀率）

### Agent 3: 德育概览+排行+记录（ConductDashboard + ConductRankings + ConductRecords）

**ConductDashboard（162→~280 行）**
1. 积分走势图：ECharts 折线图（最近 4 周的周汇总加分/扣分趋势），从 records API 按周聚合
2. 时间段切换：NRadioGroup（本周/本月/本学期），切换后重新加载数据
3. 加分/扣分比例饼图：ECharts donut（加分总额 vs 扣分总额）
4. TOP/BOTTOM 学生卡片增强：加积分柱图（小 NProgress 横条）
5. 快捷操作：底部加"记积分"/"查排行"/"导出"3 个快捷按钮

**ConductRankings（173→~260 行）**
1. 排名分布图：ECharts bar（积分区间分布，如 0-10/10-30/30-50/50+）
2. 积分趋势：点击某学生→展开行显示该生最近积分变化 sparkline
3. 搜索：NInput 按学生姓名搜索（前端过滤）
4. 导出按钮：调 exportRankings 导出当前排行
5. 小组排行增强：加小组平均分/人数列

**ConductRecords（175→~250 行）**
1. 统计卡片：顶部 3 个 NStatistic（本周记录数/加分总额/扣分总额）
2. 类型筛选：NSelect（全部/加分/扣分）
3. 班规项筛选：NSelect 按 rule_name 筛选（从记录中 distinct 提取）
4. 批量删除：NCheckbox 选中多行 + 底部"批量删除"按钮（NPopconfirm 确认）
5. 暗色适配检查

### Agent 4: 德育导出+家长（ConductExport + ConductParents）

**ConductExport（130→~200 行）**
1. 导出预览：点击"导出"前显示预览区（前 5 行数据表格）
2. 格式选择：NRadioGroup（Excel/CSV），默认 Excel
3. 字段选择：NCheckboxGroup 选择导出哪些字段（姓名/积分/日期/原因/操作人）
4. 导出历史：底部显示最近 3 次导出记录（时间+文件名，localStorage 存储）

**ConductParents（96→~180 行）**
1. 统计卡片：2 个 NStatistic（已注册家长数/已绑定学生数）
2. 搜索：NInput 按姓名/手机号搜索
3. 邀请码管理：顶部显示当前班级邀请码 + "复制邀请链接"按钮 + "重新生成"按钮（调 regenerateInviteCode）
4. 绑定状态列：表格加"绑定学生数"列
5. 批量操作：全选 + 批量移除（NPopconfirm 确认）

---

## 3. 执行约束

- **纯前端，禁止改后端 .py 文件**
- **不动 router/index.js 和 sidebarConfig.js**（路由和导航已存在）
- **不新增 API 端点**（全部消费已有端点）
- ECharts 导入方式：`import VChart from 'vue-echarts'` + 按需 use（参考 DashboardPage）
- 暗色主题：rgba 透明色，不用硬编码白色/灰色
- 改完跑 `cd frontend && npx vitest run && npx vite build`
- 每个逻辑单元完成后 commit

---

## 4. Agent 分组与文件清单

```
Agent 1（学校管理，2 页面）:
  - frontend/src/pages/SchoolsPage.vue
  - frontend/src/pages/SchoolSettingsPage.vue
  不碰其他文件

Agent 2（联考+分析，3 页面）:
  - frontend/src/pages/JointExamPage.vue
  - frontend/src/pages/AnalysisPage.vue
  - frontend/src/pages/AnalyticsTrendPage.vue
  不碰其他文件

Agent 3（德育核心，3 页面）:
  - frontend/src/pages/conduct/ConductDashboard.vue
  - frontend/src/pages/conduct/ConductRankings.vue
  - frontend/src/pages/conduct/ConductRecords.vue
  不碰其他文件

Agent 4（德育辅助，2 页面）:
  - frontend/src/pages/conduct/ConductExport.vue
  - frontend/src/pages/conduct/ConductParents.vue
  不碰其他文件

四组互不交叉，可并行。
```

---

## 5. 验收标准

- 前端测试通过（npx vitest run，基线 344 tests）
- 前端构建通过（npx vite build）
- 10 个页面行数均 > 150 行（消除所有骨架状态）
- 暗色主题兼容（无白色背景硬编码）
- ECharts 图表暗色适配（透明背景 + 浅色文字）

---

## 6. 启动 prompt

```
读 /home/ops/projects/edu-cloud/docs/plans/2026-04-25-phase-bde-enhancement-plan.md，
按 §4 的 4 个 Agent 分组并行执行。
每组只改自己的文件，不碰其他组的页面。
每组完成后独立 commit，改完跑 cd frontend && npx vitest run && npx vite build 验证。
覆盖: 前端 vitest + vite build。未覆盖: 浏览器端到端（需用户 mcu.asia 手工验证）。
```
