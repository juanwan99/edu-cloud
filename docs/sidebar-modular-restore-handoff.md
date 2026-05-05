# 侧边栏板块分组恢复 + 元能力体系家务管理加强

> **交接时间**: 2026-04-27 08:37 UTC+8
> **来源会话**: e27fc29b（审计+排查）
> **宏观目标**: 恢复用户确认的侧边栏板块分组 → 加强元能力体系防丢失机制 → 回到项目开发
> **完成状态（2026-05-05 确认）**：Part A/B 已完成——sidebarConfig.js 已恢复 5 板块分组结构（考试阅卷/教研教学/教务管理/学生管理/学校管理），getSidebarGroups() 驱动动态过滤。Part C dirty_worktree_guard 增强已由元能力体系 hook 实装。

---

## Part A: 事故调查报告（完整证据链）

### 事故概述

用户在 04-26 18:00~20:19 确认的侧边栏板块分组（5 组：考试阅卷/教研教学/教务管理/学生管理/学校管理）在 04-26 22:15 被丢弃，回退到扁平列表。

### 事故时间线

| 时间 (UTC+8) | 操作 | 会话 | commit | 影响 |
|------|------|------|--------|------|
| 04-26 18:06 | 第一次写入 `SIDEBAR_GROUPS` + `getSidebarGroups` | `6859f3fe` | 无 | sidebarConfig.js 改为分组结构 |
| 04-26 18:07 | AppSidebar.vue 改为分组渲染（折叠/展开） | `6859f3fe` | 无 | 侧边栏显示 5 个板块 |
| 04-26 18:12 | dashboardConfig.js 恢复 10 角色独立配置 | `6859f3fe` | 无 | 仪表盘也恢复 |
| 04-26 20:19 | 修复 T14 agent 的 GROUP_DEFS 硬编码，确认分组正常 | `6859f3fe` | 无 | **用户确认满意** |
| 04-26 ~21:00 | session 结束，**未 commit**（"均未提交 commit，待你确认"） | `6859f3fe` | — | **致命遗漏** |
| 04-26 21:30 | Sprint 0 审计开始，发现 working tree dirty | `e27fc29b` | — | 检测到未提交修改 |
| 04-26 21:32 | `878d1a7` 修改 4 个测试文件匹配未提交的分组代码（`getSidebarGroups`） | `e27fc29b` | `878d1a7` | 测试对齐了未提交代码 |
| 04-26 22:15 | `0efe1e8` revert 测试 + 清理 dirty working tree | `e27fc29b` | `0efe1e8` | **板块分组代码永久丢失** |

### 责任归属

| 角色 | 责任 | 具体错误 |
|------|------|---------|
| session `6859f3fe` | **主要责任** | 做了 40 次编辑但没 commit。会话结束时说"待你确认后统一提交"但没有写 handoff 提醒用户 commit |
| session `e27fc29b` (Sprint 0 审计) | **次要责任** | 发现 `getSidebarItems→getSidebarGroups` 差异时，选择了 revert 测试而非 commit 源码。它不知道这些修改是用户确认过的功能 |
| 元能力体系 | **系统性缺陷** | 没有机制检测"用户确认的功能修改未 commit"并阻止后续会话丢弃 |

### 根因

**未 commit 的功能代码 + 跨会话 working tree 清理 = 丢失**。这是一个系统性缺陷：元能力体系有 `dirty_worktree_guard`（SessionStart 提醒 dirty 状态），有 `build_clean_guard`（构建前检查 dirty），但没有**跨会话的未提交功能代码保护机制**。

---

## Part B: 恢复任务

### B-1: 恢复 sidebarConfig.js 板块分组

**源码**：从 session `6859f3fe` transcript 完整恢复，保存在 `/tmp/sidebarConfig_recovered.js`（100 行）。

**5 组结构**：
```
考试阅卷 (exam): 考试管理 / 阅卷调度 / AI阅卷 / 人工阅卷 / 阅卷分配 / 阅卷进度 / 成绩分析
教研教学 (research): 知识图谱 / 作业管理 / 题库管理 / 错题本 / 教学计划
教务管理 (academic): 教师分配 / 选科管理 / 学期管理 / 课程表
学生管理 (student): 学生信息 / 德育9项 / 家校沟通
学校管理 (school): 教师管理 / 学校管理 / 学校配置 / 联考管理 / 校历管理
```

**操作**：
1. `cp /tmp/sidebarConfig_recovered.js frontend/src/config/sidebarConfig.js`
2. 检查路由路径是否与当前 `router/index.js` 一致（`/semesters` → `/academic/semesters` 等，需对齐）
3. 验证 `getSidebarGroups` 和 `getSidebarItems` 都 export 了（兼容旧调用方）

### B-2: 恢复 AppSidebar.vue 分组渲染

**源码**：`/tmp/AppSidebar_recovered.vue`（286 行）。

**关键功能**：
- 分组折叠/展开（`expandedGroups` reactive）
- 当前路由自动展开所属组（`watch route`）
- 折叠模式下只显示组图标
- `slide` transition 动画

**操作**：
1. `cp /tmp/AppSidebar_recovered.vue frontend/src/components/shell/AppSidebar.vue`
2. 检查 `handleGroupClick` 函数是否完整（transcript 截断了，可能需要补全）
3. 运行 `npx vitest run` 确认测试

### B-3: 更新测试文件

`878d1a7` 改了 4 个测试匹配分组结构但被 `0efe1e8` revert 了。恢复后需要：

1. `frontend/src/__tests__/AppSidebar.test.js` — mock `getSidebarGroups` 而非 `getSidebarItems`
2. `frontend/src/__tests__/config.test.js` — parent sidebar items 上限调整
3. `frontend/src/__tests__/router.test.js` — 路由数量 41→44+
4. `frontend/src/__tests__/sidebarConfig.conduct.test.js` — 从 `SIDEBAR_GROUPS` 提取 conduct 项

可参考 `878d1a7` 的 diff：`git show 878d1a7`

### B-4: 路由对齐检查

recovered sidebarConfig 中有些路径可能与当前 router 不一致：

| recovered 路径 | 当前 router 路径 | 需要 |
|------|------|------|
| `/semesters` | `/academic/semesters` | 对齐到当前 |
| `/timetable` | `/academic/timetable` | 对齐到当前 |
| `/teaching-plans` | `/academic/teaching-plans` | 对齐到当前 |
| `/analytics` | 无单独入口 | 检查是否需要加路由 |
| `/knowledge-tree` | 当前 router 缺失 | **需要加回路由** |
| `/parent-comm` | 当前 router 缺失 | 检查页面是否存在 |

### B-5: vite build + 浏览器验证

恢复完成后必须：
1. `cd frontend && npx vitest run` — 全绿
2. `npx vite build` — 构建成功
3. 浏览器硬刷新 mcu.asia — 确认侧边栏显示 5 个板块
4. 切换角色验证不同角色看到不同板块

---

## Part C: 元能力体系家务管理加强

### C-1: 问题定义

当前体系能检测 dirty working tree（`dirty_worktree_guard`），能检测脏构建（`build_clean_guard`），但**不能防止跨会话丢弃用户确认的功能代码**。

核心缺口：**session 结束时有大量未 commit 的功能代码 → 下一个 session 不知道这些代码是用户确认的 → 清理 dirty state 时一起丢弃**。

### C-2: 设计方案

**方案：dirty_worktree_guard 增强 — 分级 dirty 检测**

当前 `dirty_worktree_guard`（SessionStart hook）只报告"有 N 个未提交变更"。改为：

1. **检测 dirty 文件数量和类型**（已有）
2. **新增：检测 SessionState 中的 `_edit_trace`**
   - 如果 dirty 文件出现在**任何 session 的 `_edit_trace` 中**（说明是 Claude 编辑的，不是用户手动改的）
   - 且该 session 的 `_tool_calls` > 20（说明是实质性工作，不是试探性编辑）
   - → 输出**强警告**："这些文件由 session {sid} 编辑但未 commit，可能是用户确认的功能。清理前请先确认"
3. **新增：block `git stash` / `git checkout -- .` / `git restore .`**
   - 如果 working tree 有 session edit_trace 中的文件
   - → block："检测到其他会话的未提交工作，禁止批量清理。请逐文件确认或先 commit"

**方案：session 结束提醒 commit**

`handoff_format_guard` 或新 hook：
- session `_edit_trace` > 5 且没有对应的 `git commit`
- → SessionStart 时的 `dirty_worktree_guard` 输出："上一个会话编辑了 {N} 个文件但未 commit，建议先 `git diff --stat` 查看后决定 commit 或 discard"

### C-3: 实现范围

| 文件 | 改动 | 复杂度 |
|------|------|--------|
| `dirty_worktree_guard.py` | 增加 edit_trace 交叉检查 | 中 |
| `destructive_git_guard.py` | 增加 `git stash`/`git checkout --`/`git restore .` 对 edit_trace 文件的保护 | 低 |
| `governance.yaml` | 新增 WF-012 clause | 低 |

---

## 宏观目标约束

1. **恢复优先于加强**：先 Part B（恢复侧边栏），再 Part C（加强体系）
2. **Part B 是前端任务**：改 2 个文件 + 更新 4 个测试 + 路由对齐 + build + 浏览器验证
3. **Part C 是元能力任务**：改 2-3 个 hook + governance
4. **Part B 完成后必须 commit**：这正是本次事故的教训——不 commit 就丢
5. **Part C 改动后也必须 commit + 全量测试**
6. **不要扩大范围**：只恢复已确认的板块分组，不要顺手加新模块/新功能

---

## 关键文件位置

| 文件 | 用途 |
|------|------|
| `/tmp/sidebarConfig_recovered.js` | 从 transcript 恢复的板块分组配置（100 行） |
| `/tmp/AppSidebar_recovered.vue` | 从 transcript 恢复的分组渲染组件（286 行，可能截断需检查） |
| `frontend/src/config/sidebarConfig.js` | 当前扁平版（需替换） |
| `frontend/src/components/shell/AppSidebar.vue` | 当前扁平版（需替换） |
| `frontend/src/router/index.js` | 当前路由（需补 `/knowledge-tree`） |
| Session `6859f3fe` transcript | `/home/ops/.claude/projects/-home-ops/6859f3fe-f133-435b-be44-0ea1e1fa4bff.jsonl` |
| Commit `878d1a7` | 测试文件的分组版 diff，`git show 878d1a7` 可参考 |
| Commit `0efe1e8` | 回退操作，完整 commit message 记录了事故经过 |
