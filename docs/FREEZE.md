# 系统冻结与逐步开放记录

> 创建日期：2026-04-18
> 状态：已全面开放（2026-05-05 确认）

## 背景

edu-cloud 系统功能模块众多（21 模块、320 路由、52 前端路由），初期尚未逐一验证可用性。
决定采用"**整体冻结 + 逐步开放**"策略：先将所有功能锁定，再按业务优先级逐个解冻、验证、放行。

## 冻结范围

### 前端冻结（2026-04-18 实施）

**已冻结的路由/功能：**

| 功能 | 原路由 | 状态 |
|------|--------|------|
| 家长端（登录/注册/概览/排行等） | `/parent/*` | 冻结 |
| 德育管理（9 个子页面） | `/conduct/*` | 冻结 |
| 成绩分析 | `/analytics/*` | 冻结 |
| AI 分析工作台 | `/analysis` | 冻结 |
| 知识图谱 | `/knowledge-tree` | 冻结 |
| 文档中心 | `/studio` | 冻结 |
| 校历通知 | `/calendar` | 冻结 |
| 通知管理 | `/notifications` | 冻结 |
| 论文写作 | `/paper` | 冻结 |
| 学校管理 | `/schools` | 冻结 |
| 系统设置 | `/settings` | 冻结 |
| 学校配置 | `/school-settings` | 冻结 |
| 排课管理 | `/assignments` | 冻结 |
| 选考组合 | `/selections` | 冻结 |

**当前开放的路由（第一批 — 考试阅卷链路）：**

| 功能 | 路由 | 角色 |
|------|------|------|
| 登录 | `/login` | 所有 |
| 首页仪表盘 | `/` | 已登录 |
| 考试列表 | `/exams` | EXAM_ROLES |
| 考试详情 | `/exams/:id` | EXAM_ROLES |
| 答题卡编辑 | `/card-dev/:examId` | EXAM_ROLES |
| 阅卷调度 | `/grading/tasks` | SCHOOL_ADMIN_ROLES |
| 阅卷结果 | `/grading/tasks/:id` | SCHOOL_ADMIN_ROLES |
| 阅卷选题 | `/marking` | MARKING_ROLES |
| 阅卷界面 | `/marking/grade/:questionId` | MARKING_ROLES |
| 阅卷分配 | `/marking/assign` | SCHOOL_ADMIN_ROLES |
| 阅卷进度 | `/marking/progress` | MARKING_ROLES |

### 侧栏冻结

所有角色的侧栏只显示：平台概览 + 考试管理 + 阅卷调度 + 阅卷 + 阅卷分配 + 阅卷进度。
管理角色（教务/校长/平台管理员/备课组长）额外显示"阅卷调度"和"阅卷分配"。

### 后端

后端 API 未冻结（路由仍然注册），但前端入口全部封堵，用户无法触达冻结功能。
后续如需后端也冻结，可在 `module_middleware.py` 中增加模块级别拦截。

## 文件变更清单

| 文件 | 变更 | 备份位置 |
|------|------|---------|
| `frontend/src/router/index.js` | 路由精简为 10 条 + catch-all 重定向 | `frontend/src/router/_frozen/index.full.js` |
| `frontend/src/config/sidebarConfig.js` | 侧栏精简为考试+阅卷 | `frontend/src/config/_frozen/sidebarConfig.full.js` |
| `frontend/src/config/dashboardConfig.js` | 仪表盘卡片精简为考试+阅卷 | `frontend/src/config/_frozen/dashboardConfig.full.js` |
| `frontend/src/__tests__/router.test.js` | 测试适配冻结状态 | `frontend/src/__tests__/_frozen/router.test.js.bak` |
| `frontend/src/__tests__/sidebarConfig.conduct.test.js` | 测试适配冻结状态 | `frontend/src/__tests__/_frozen/sidebarConfig.conduct.test.js.bak` |
| `frontend/src/__tests__/config.test.js` | dashboard 测试适配冻结状态 | （原文件内联修改，备份见 git） |

## 解冻步骤

当需要开放新模块时：

1. 从 `_frozen/` 目录参考原始文件
2. 将目标路由从 `_frozen/index.full.js` 复制回 `router/index.js`
3. 将目标侧栏项从 `_frozen/sidebarConfig.full.js` 复制回 `sidebarConfig.js`
4. 更新对应测试
5. 运行 `npx vitest run` 确认全绿
6. 用 Playwright 截图验证页面可访问
7. 在本文档"开放记录"章节追加记录

## 开放记录

### 第一批：考试阅卷链路（2026-04-18）

- **范围**：考试管理 + 答题卡 + 扫描切割 + 选择题判分 + AI/手动阅卷 + 成绩发布
- **验证状态**：前端 Vitest 234/234 通过；Playwright 截图确认侧栏精简、冻结路由重定向正常

### 后续逐步全面开放（2026-04 ~ 2026-05）

截至 2026-05-05，**全部模块已解冻**。sidebarConfig.js 恢复为 5 板块分组完整结构：
- 考试阅卷（考试管理 / 阅卷调度 / AI 阅卷 / 人工阅卷 / 成绩分析）
- 教研教学（知识图谱 / 作业管理 / 题库管理 / 错题本 / 教学计划）
- 教务管理（教师分配 / 选科管理 / 学期管理 / 课程表）
- 学生管理（学生档案 / 德育工作台 / 德育设置）
- 学校管理（教师管理 / 学校管理 / 学校配置 / 联考管理 / 校历管理）

router/index.js 已恢复 52 路由（含 parent 系列独立布局）。
前端 Vitest 2421 tests / 0 failed（ECS 实测 @ 2026-05-04）。

**本文档已完成其历史使命。** `_frozen/` 目录中的备份文件仍保留供参考。
