---
type: handoff
created: 2026-04-11 19:58:58
project_dir: C:\Users\Administrator\edu-cloud
design: (无 — 探索测试阶段，无 design/plan，只有 exploration-notes)
plan: (无 — 探索测试阶段)
notes: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-exploration-notes.md
prev_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-edu-cloud-exploration-handoff.md
---

# edu-cloud 全量测试 Round 2+ 交接卡

## 背景

上一会话承接 `2026-04-11-edu-cloud-exploration-handoff.md`，执行用户指令「使用调试浏览器深度测试答题卡生成/分割/阅卷/AI 阅卷整条管道」并持续扩展。

**已完成 16 个子项**（S1-S8 主管道 + R1-R8 扩展模块）：
- S1-S8：试卷制作 → 扫描切割 → 人工阅卷 → AI 阅卷完整管道
- R1-R8：F003 根因深挖 + 知识图谱 + Analytics + AI Chat + Adaptive + Studio + 教务管理 + 通知

**产出**：
- `docs/plans/2026-04-11-exploration-notes.md`（26KB，**13 个 finding 全部记录在此，含源码行号**）
- 4 张 Playwright 截图：`.playwright-mcp/{card-editor-math-a,pipeline-preview-math-a,marking-page-academic-director,marking-grade-empty-state,knowledge-tree-molecular-cell,knowledge-tree-review-workbench}.png`
- 未 commit（用户未要求）

## 当前运行中的服务

| 服务 | 端口 | 启动方式 | 状态 |
|------|------|---------|------|
| 后端 uvicorn | 9000 | `python ~/.claude/scripts/serve.py python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload` | health 200 |
| 前端 vite | 5273 | `python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev`（frontend/ 目录下） | 5273 200 |

**重启规则**：改后端代码后必须用 serve.py 重启，`uvicorn --reload` 有时漏识别新 router。改前端可 HMR。

## Tier 声明

**T1（探索测试 + 文档记录）**。判据：只读 API + Playwright 浏览器交互 + 追加 exploration-notes.md，不动代码。任何修 bug 或补 feature 的动作必须重新按 rules 定级（问题 1 权限过滤 T2；F003 管道断裂 T3/T4）。

## 约束与偏好（仅增量，不重复 notes 已记）

### 用户工作偏好（从上一会话观察）
- **不要跳开「拆单 + 汇报」节奏**：每一轮新任务开始前先列路线图让用户确认，不要整包自治
- **发现问题立即记录到 notes，不自己动手修**：F003/F006/F011 等都是 T2+ 起步，需要走 design→plan 流程
- **禁止全绿汇总表**：用 completed/⚠️/🔴 混合标，不要纯 ✓（completion_guard 会 block）
- **纠正后立即停**：用户语气升级后禁止再改，先说"错在哪 + 新方案"
- **时间戳精确到秒**：交接卡和 notes 的 ts 必须 `date '+%Y-%m-%d %H:%M:%S'`

### 已验证的环境 quirks

- **t_yw_001 ~ t_yw_005 存在** 且密码 123456，角色 subject_teacher（语文教师），覆盖上一版交接卡「t_* 不存在」的错误说法
- 教务主任账号 `admin_academic_director_2 / 123456`（李明华，育才实验中学）
- 平台超管 `admin / 123456`
- **Git Bash curl 发 JSON 中文 body 会挂** → 用 `python -c 'import httpx; ...'` 或 Playwright MCP `browser_evaluate` 内 fetch
- **端口已占** → serve.py 走 port_guard，不要手工 kill
- **Playwright MCP snapshot depth** 默认浅，遇到嵌套表格用 depth=12~18
- **localStorage 直接 setItem 不触发 Pinia reactivity** → 必须走 UI login 让 auth store 同步，否则 router guard 会重定向到 `/`
- **G6 canvas 点击模拟事件不触发节点 handler** → 需要真实鼠标坐标（Playwright 原生 click + 元素 ref），JS 模拟无效
- `marking/subjects` 的 questions 数据由 marking/scorer.py:12 生成，**只过滤 school_id 未过滤 visible_subject_codes**（F009 精确位置）

### 已跑过的测试数据现状
- **育才实验中学**：36 班 1500 学生 200 教师
- **5 个考试**：33 / 2026年春季期中考试 / 2026年春季月考 / 2026年春季期末考试 / 2026第一次月考
- **测试主力考试**：`2026第一次月考`，`exam_id=80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c`，草稿→scanning 状态（已发布答题卡）
- **数学切图已落盘**：`C:\Users\Administrator\edu-cloud\storage\31c17116-8182-429b-b38d-47c89eec39ef\80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c\1974216e-8aef-4a0b-b9c2-0432488d6b80\` 含 367 学生目录 × 6 PNG = 2202 切图（**但 Question/StudentAnswer 表无数据**）
- **9 科目** 中 5 科有种子 question，4 科 (数学/物理/语文/英语) questions 为空
- **地理第 1 题**有 1 个 answer 且已被种子批改，其他全空

## 13 个已识别 Finding（notes 中有完整详情 + 源码行号）

优先级排序：

| ID | 严重度 | 摘要 | 位置 |
|----|--------|------|------|
| F003 | 🔴 HIGH | 切割流水线产物完全不入 Question/StudentAnswer | `frontend/src/card-editor/export.js:177-215` + `modules/scan/pipeline_router.py:147` |
| F003a | 🔴 HIGH | publishCard 只写 A 面 Template，B 面从不写 | `frontend/src/card-editor/export.js:205` 只 PUT `/templates/{subjectId}/A` |
| F006 | 🔴 HIGH | 问题 1 复现：科任教师看到全部 9 科 | （交接卡原问题 1 确认） |
| F008 | 🔴 HIGH | 交接卡问题 2/3 (选择题识别 + anchor/affine) 被 F003 遮蔽，无法独立验证 | — |
| F009 | 🔴 HIGH | F006 精确根因：`get_subjects_with_progress` 无 visible_subject_codes 过滤 | `src/edu_cloud/modules/marking/scorer.py:12-18` |
| F011/F012 | 🔴 HIGH-UX | 4 个侧栏导航是 Placeholder：`/studio`/`/paper`/`/calendar`/`/notifications` | `frontend/src/router/index.js:56-60` 源码注释 |
| F002 | 🟡 MED | CardEditor skeleton 与 pipeline tpl 是双套坐标系 | — |
| F007 | 🟡 MED | grading/tasks 前置未校验返回 500 超时 | — |
| F010 | 🟡 MED | 考试列表显示 "(null)" — 前端字段绑定 bug | `frontend/src/pages/AnalysisPage.vue` |
| F013 | 🟡 MED | AI Chat 能用但 grading/tasks 11s 超时（F007 修订） | `modules/grading/llm_client.py` + `router.py`（待读） |
| F001 | 🟡 MED-LOW | Skeleton 导出 side 字段全为 A（B 面区域错标） | `frontend/src/card-editor/export/` |
| F004 | 🟢 LOW | 条形码识别失败率 2.2%（8/367 用 image_id fallback，静默无告警） | — |
| F005 | 🟢 LOW | `GET /api/v1/scan/tasks?exam_id` 返回 405 | — |

## 未测模块（用户后续可要求扩展）

- Homework 作业管理（Phase 2.2，含 task/submission CRUD + 批改）
- Profile 学情画像独立页面（Phase 3.1，trend/knowledge/error-patterns/class weakness）
- Bank 题库 + 错题本（Phase 3.1）
- Joint Exam 联考管理（创建→参与校→下发→成绩→报告）
- School Admin 管理（platform_admin 角色，学校 CRUD + API Key）
- 教研工作流 + Capability 管理
- 家长入口（parent 角色，企微登录）
- Profile 学情画像 REST 端点（S5 发现 adaptive 仅通过 Agent 工具暴露，Profile 也可能类似）
- Audit Log 查询（school/{id}/audit-logs）
- Knowledge Tree Edit 权限流程（add_node/remove_edge 等 edit 操作的审核状态机）

## 下一步建议方向（用户定夺）

1. **快速扫尾**：测剩余未测模块（Homework/Profile/Bank/JointExam），补齐 finding 清单 → 继续探索模式
2. **切换修复模式**：先对 F009 权限过滤做 T2 修复（一行改动：在 `marking/scorer.py:12-18` 注入 `get_visible_subject_codes` 过滤），然后 t2-review → commit
3. **深挖 F013**：读 `modules/grading/llm_client.py` 和 `router.py` 搞清楚 grading/tasks 为什么 11s 超时
4. **启动 F003 design**：走 brainstorming → writing-plans，重新设计 Template/Question/Answer 写入责任链（T4 起步）
5. **commit 笔记**：把 `docs/plans/2026-04-11-exploration-notes.md` + 截图 commit 归档

## 禁止事项

- 不要自己动手修 F003/F006/F011（T2+ 必须走流程）
- 不要 commit exploration-notes.md 除非用户明确说要
- 不要把切图目录 (`storage/...`) 清掉（重跑 pipeline 会花 10 秒不算痛，但其他测试依赖 scanning 状态的考试数据）
- 不要把 exam `2026第一次月考` 的 status 回滚（AI Chat 会读到它，帮助定位 R4 发现）
- 不要碰 scan-integration 已归档代码（docs/plans/2026-04-09-scan-integration-*）
- 不要启动新服务（9000/5273 已运行）
- 禁止 curl 发中文 JSON，用 httpx 或 browser_evaluate fetch
- 禁止 SSH 相关操作（本地 Windows 测试，无远程）

## 启动 Prompt

```
[edu-cloud] Explorer-R3 | 2026-04-11 19:58:58
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-exploration-handoff-round2.md 了解上下文。
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-exploration-notes.md 查看已记录的 13 个 finding 详情。

当前状态：
- 后端 :9000 + 前端 :5273 均在运行，不要重启
- 已登录态可能失效，用 admin_academic_director_2 / 123456 重新走 UI 登录
- Round 1 (S1-S8) + Round 2 (R1-R8) 共 16 个子项已完成
- 13 个 finding 已记录，未 commit
- 2026第一次月考 (exam_id=80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c) 数学切图 2202 张落盘但 DB 空

新窗口职责：
1. 先确认用户下一步意图（探索扩展 / 修复 / 深挖 F013 / F003 设计 / commit 归档）
2. 用户要继续探索 → 按「未测模块」段顺序推进：Homework/Profile/Bank/JointExam
3. 用户要修复 → F009（T2 一行改动 marking/scorer.py:12-18）可以立即做，其他 T3+ 必须 design→plan→handoff
4. 用户要 commit → 笔记 + 截图一起 commit，消息 `exploration: edu-cloud 16 子项全量测试记录 + 13 finding`
5. 每发现新 finding → 追加到 notes.md 的「Round N 新增 Finding」段，不要新建文件

节奏规则：
- 每开始一轮新任务先列路线图让用户确认，不要整包自治
- 每个子项完成就暂停汇报，不要堆到最后
- 发现问题立即记录到 notes，禁止自己动手修 T2+ 问题
- 禁止完成性符号（✓/✅ 多个并列）触发 completion_guard
- 时间戳全部 `date '+%Y-%m-%d %H:%M:%S'`

禁止事项：
- 不要启动服务（已在跑）
- 不要 commit 除非用户说
- 不要清 storage/ 目录
- 不要回滚 2026第一次月考 的 scanning 状态
- 不要 curl 发中文 JSON，用 httpx/browser_evaluate
- 不要碰 scan-integration 归档代码

关键账号：
- admin_academic_director_2 / 123456 (academic_director 李明华，主力测试账号)
- t_yw_001 / 123456 (subject_teacher 高睿皓语文，测权限过滤用)
- admin / 123456 (platform_admin)

测试数据路径：D:\试卷数据\试卷图像\191871\A3722 (9 科 A+B 面)
tpl 路径：D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984002]数学A.tpl
```
