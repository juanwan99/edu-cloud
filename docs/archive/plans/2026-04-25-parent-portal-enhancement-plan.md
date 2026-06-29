---
baseline_command: "cd ~/projects/edu-cloud/frontend && npx vitest run"
baseline_verified_at: "2026-04-25 23:00"
baseline_count: 323
---

# Phase C 家长端体验增强方案

**Date**: 2026-04-25
**Scope**: 7 个家长端页面纯前端增强，不动后端
**Tier**: T1-T2（页面增强，不涉及新 service/model）
**执行方式**: 新窗口执行，3 个并行 agent

---

## 1. 资产盘点

### 后端（14 端点全就位，不动）

| 端点 | 用途 | 被哪些页面消费 |
|------|------|-------------|
| `GET /invite/{code}/info` | 验证邀请码 | ParentRegister |
| `POST /parent/register` | 家长注册 | ParentRegister |
| `POST /parent/login` | 家长登录 | ParentLogin |
| `GET /parent/me` | 当前家长信息 | ParentLayout, ParentProfile |
| `POST /parent/bind` | 绑定孩子 | ParentBind |
| `GET /parent/children` | 已绑定孩子列表 | ParentLayout |
| `GET /parent/children/{id}/records` | 操行记录（分页） | ParentOverview, ParentDetails |
| `GET /parent/children/{id}/rankings` | 班级排名 | ParentRankings |
| `GET /parent/classes/{id}/rules` | 班规 | ParentRules |
| `GET /parent/children/{id}/exams` | 考试列表 | ParentScores |
| `GET /parent/children/{id}/scores` | 考试成绩快照 | ParentScores |
| `GET /parent/children/{id}/error-book` | 错题本 | ParentScores（可扩展） |
| `PUT /parent/profile` | 更新资料 | ParentProfile |
| `PUT /parent/password` | 修改密码 | ParentProfile |

前端 API 层（`frontend/src/api/conduct.js`）已有 17 个 parent 相关方法，全部对接完毕。

### 前端现状

| 页面 | 行数 | 功能现状 | 问题诊断 |
|------|------|---------|---------|
| **ParentLogin** | 72 | 手机号+密码表单 | 无品牌视觉、无记住手机号、无加载动效 |
| **ParentRegister** | 152 | 邀请码→填写资料两步 | 相对完整，增强空间小 |
| **ParentOverview** | 63 | 总积分卡+最近记录列表 | 无成绩摘要、无快捷入口、信息密度太低 |
| **ParentDetails** | 85 | 学生信息卡+分页记录表 | 无时间筛选、无类型筛选、无积分走势 |
| **ParentRankings** | 60 | 纯表格+当前孩子高亮 | 无排名变化趋势、无奖杯/勋章视觉、信息太单调 |
| **ParentRules** | 58 | 折叠面板+积分标签 | 无搜索、无正负分分类切换 |
| **ParentProfile** | 149 | 编辑姓名+改密码+绑定列表+退出 | 相对完整，增强空间小 |

### ParentLayout（144 行，不在本批范围但需了解）
- 顶栏：品牌名"家校互通" + 子女切换 NSelect + 个人按钮
- 内容区：padding 16px，底部留 72px 给 tabs
- 底部 5 Tab：概览/成绩/排行/班规/我的
- 子女数据通过 provide/inject 传递给子页面
- cp_token 独立认证，与平台 JWT 分离

---

## 2. 增强方案（按 agent 分组）

### Agent 1: 登录+概览+详情（ParentLogin + ParentOverview + ParentDetails）

**ParentLogin（72→~140 行）**
1. 品牌视觉：顶部加 Logo 区（校名/平台名+副标题"家校互通"），底部版权
2. 记住手机号：NCheckbox "记住手机号"，localStorage 存取
3. 登录中动效：按钮 loading 态 + 登录成功后 0.3s 过渡动画
4. 错误提示优化：密码错误显示 NAlert 红色提示（替代 window.$message）
5. 忘记密码提示：底部加"忘记密码？请联系班主任"灰色文案

**ParentOverview（63→~200 行）**
1. 孩子信息卡增强：头像占位（首字母圆形）+ 姓名 + 班级 + 总积分 + 排名
2. 成绩快捷摘要：调 `getChildScores` 取最近一次考试的总分/排名，显示小卡片
3. 快捷入口：4 个圆形图标按钮（成绩查询/排行榜/班规/操行记录），参考移动端常见样式
4. 最近记录增强：记录项加图标（加分=绿色上箭头，扣分=红色下箭头）
5. 无数据引导：未绑定孩子时显示引导卡片→跳转绑定页

**ParentDetails（85→~180 行）**
1. 时间筛选：NDatePicker range 选择日期范围
2. 类型筛选：NSelect 按正分/负分/全部过滤
3. 积分走势迷你图：顶部加 sparkline 折线图（最近 30 天积分累计趋势）
4. 记录项增强：加分类标签（来自 rule_category）、加操作教师名

### Agent 2: 排行榜+班规（ParentRankings + ParentRules）

**ParentRankings（60→~180 行）**
1. 排名信息卡：顶部大卡片显示当前孩子排名（"第 N 名 / 共 M 人"），带奖杯图标（前 3 名金银铜色）
2. 排名变化：如果 API 返回 previous_rank，显示上升/下降箭头+变化数字
3. 积分分布条：横向 bar 展示积分分布（前 10% / 50% / 后 40%），当前孩子位置标记
4. 表格增强：加排名变化列、加积分变化列（本周/本月）
5. 自己的行用绿色高亮+左侧色带（现有 highlight-row 增强）

**ParentRules（58→~150 行）**
1. 分类统计：顶部显示"共 N 条规则（加分 X 条 / 扣分 Y 条）"
2. 正负分切换：NRadioGroup（全部/加分项/扣分项）快速过滤
3. 搜索：NInput 搜索规则名称
4. 规则卡片增强：每条规则加分值标签颜色区分（大额加分=绿，小额=默认，扣分=红）
5. 分类图标：每个分类标题前加 emoji 或图标

### Agent 3: 绑定+个人中心（ParentBind + ParentProfile）

**ParentBind（109→~170 行）**
1. 绑定流程步骤条：NSteps 三步（填写信息→验证→完成）
2. 验证方式说明：在 verify_code 输入框下方加灰色提示文案
3. 关系选择增强：图标化关系选项（父/母/祖父/祖母/其他 各带图标）
4. 绑定成功动效：成功后显示绿色对勾 + 孩子姓名 + "3 秒后跳转概览"
5. 已绑定检测：进入页面检测如果已有孩子，提示"已绑定 N 个孩子，是否继续绑定？"

**ParentProfile（149→~220 行）**
1. 头像区：顶部圆形头像（首字母占位）+ 姓名 + 手机号脱敏显示
2. 孩子卡片增强：每个孩子显示最近积分变化（+/-）、最近考试成绩摘要
3. 退出确认：NPopconfirm 二次确认退出
4. 账号安全提示：密码修改成功后提示"所有设备已退出，请重新登录"
5. 版本信息：页面底部显示"v1.0 · 家校互通"灰色小字

---

## 3. 执行约束

- **纯前端，禁止改后端 .py 文件**
- **不动 ParentLayout.vue**（布局层稳定，不在本批范围）
- **不动 router/index.js 和 sidebarConfig.js**（路由已存在）
- **不新增 API 端点**（全部消费已有 14 端点）
- Naive UI 暗色主题（家长端已用 darkTheme）
- 移动优先设计（家长端主要在手机访问）
- 改完跑 `cd frontend && npx vitest run && npx vite build`
- 每个逻辑单元完成后 commit

---

## 4. Agent 分组与依赖关系

```
Agent 1: ParentLogin + ParentOverview + ParentDetails  (登录→概览→详情，用户主路径)
Agent 2: ParentRankings + ParentRules                   (排行+班规，独立页面)
Agent 3: ParentBind + ParentProfile                     (绑定+个人中心，独立页面)

三组互不依赖，可并行。
共享 inject 数据源: currentChild (from ParentLayout provide)
```

---

## 5. 验收标准

- 前端测试通过（vitest run）
- 前端构建通过（vite build）
- 7 个页面行数均 > 120 行（消除所有 🔴 骨架状态）
- 暗色主题兼容（无白色背景硬编码）
- 移动端 375px 宽度不破版
