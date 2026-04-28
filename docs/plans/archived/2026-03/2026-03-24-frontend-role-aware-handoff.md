---
type: handoff
created: 2026-03-24 07:01:09
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-23-frontend-role-aware-redesign-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-24-frontend-role-aware-plan.md
---

# 前端角色感知重设计 — 会话交接卡

## 约束与偏好

**T3 流程**。设计已通过 3 轮 GPT spec review。计划通过 1 轮 GPT plan review（R1 发现 8 个问题，尚未修复到计划文档中）。

### 计划 R1 未修复项（执行前必须先修计划）

| ID | 核心问题 | 修复方向 |
|----|---------|---------|
| F-01 | 缺 notifications API Task | 补独立 Task：`GET /api/v1/notifications`（路由+过滤+前端封装+Bell/ActivityFeed 接线） |
| F-02 | dashboard/summary 字段不全 | 完善 schema：加 `total_staff`/`pending_subjects`，暂缓字段返回 `null`，补契约测试 |
| F-03 | 页面刷新后 auth 状态丢失 | 补 auth bootstrap：roles/currentRoleIndex/context 持久化到 localStorage，启动时恢复 |
| F-04 | 测试 fixture 角色不匹配 | Task 2 测试分 principal/grade_leader/homeroom_teacher 三组，各自断言 scope |
| F-05 | AppShell 引用未创建组件 | Task 6 创建 AppSidebar/AiFloatingButton 的空占位组件 |
| F-06 | 前端 permission 常量缺失 | 新增 `config/permissions.js`：角色→权限映射，`hasPermission` 用小写 value（与后端 enum 一致） |
| F-07 | 测试文件路径错误 | Task 1 改为扩展 `tests/test_api/test_auth_v2.py`，删除错误的 seed_school 补 name 说明 |
| F-08 | AnalysisPage 双层头部 | Task 13 补步骤：WorkbenchPage 重命名后移除 header slot 中的身份控件 |

### 用户偏好

- **视觉风格必须使用 [已清理-旧项目] 的设计语言**：深墨绿 #1a2e1f + macaron 柔彩 + 大圆角 24px + SVG mask-image 图标（不用 emoji）+ 系统字体栈
- **质量第一**：每个 Batch 完成后必须跑 GPT code review
- **校长关心全校健康度，教学只是一个板块**：dashboard 不要堆阅卷/批改细节
- **未来扩展**：师资人事、后勤安全等板块用灰度占位卡片，不留空白

### 技术约束

- 后端 SQLite in-memory（dev 模式），无 .env 文件
- 前端 Vitest 4 + happy-dom（不用 jsdom）
- Naive UI 当前启用 darkTheme，需切换为 light 并对齐 edu-cloud token
- 现有 770 后端 + 27 前端测试必须保持全绿

## 启动 Prompt

```
读取交接卡 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-24-frontend-role-aware-handoff.md 了解上下文。

你的任务：
1. 先修复计划文档中 GPT R1 审查的 8 个 finding（F-01~F-08），修复后重新提交 GPT plan review
2. Plan review 通过后，按 4 Batch 顺序执行实现计划

计划文件：C:\Users\Administrator\edu-cloud\docs\plans\2026-03-24-frontend-role-aware-plan.md
设计文件：C:\Users\Administrator\edu-cloud\docs\plans\2026-03-23-frontend-role-aware-redesign-design.md

使用 superpowers:executing-plans skill 逐 Task 执行。每个 Batch 完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
