---
baseline_command: "cd ~/projects/edu-cloud && .venv/bin/python -m pytest --collect-only -q"
baseline_verified_at: "2026-04-26 06:29"
baseline_count: 2227
---

# 好分数业务吸收 — 延续规划（新窗口接替）

**Date**: 2026-04-26
**Branch**: `feat/analytics-report`
**Last commit**: `5b78af2`
**前端基线**: 35 files / 344 vitest passed
**后端基线**: 2227 collected（2218 passed / 2 failed 既有债 / 23 skipped）

---

## 一、上一会话完成了什么

### 研究产出
- 四轴对照调研（A 阅卷 100% / B 学情 60% / C 教学 20% / D 行政 89%）
- docs/plans 归档（161→15 个活跃文件）
- Phase 2 总设计 `2026-04-24-haofenshu-vs-edu-phase2-design.md` 仍为活跃总纲

### 前端增强（4 批 27 个页面，全部已提交）

| 批次 | 页面数 | 关键 commit |
|------|--------|------------|
| 教务模块 | 4 | `c110686` 排课 / `76b7727` 学期 / `b0f154a` 课表 / `b68cd13` 选考 |
| 考试主链路 | 3 | `5b788e3` 考试列表 / `ec9572c` 阅卷结果 / `d7c6313` 仪表盘 |
| 阅卷链路 | 3 | `b19eb0f` 选题 / `56d815e` 分配 / `0e4442e` 进度 |
| 家长端 | 7 | `f0b3b83` 一次提交 |
| 学校/联考/德育 | 10 | `5b78af2` 一次提交 |

### 当前全平台页面状态
- 49 个页面中 44 个 🟢（≥200 行）、3 个 🟡（150-199）、2 个 🔴
- 仅剩 CardEditorDevPage(54 行，薄壳入口不需增强) 和 LoginPage(41 行) 为骨架

---

## 二、待执行工作（按优先级排序）

### P0: 服务层半成品恢复与修补（stash@{0}）

**背景**: 上一会话派发了 5 个服务层 WP（题库搜索/错题推荐/作业推送/年级分析/教学计划），agent 因限流被截断，半成品暂存在 `git stash@{0}`。

**stash 内容（22 文件，+2818 行）**:

| 工作包 | 后端文件 | 前端页面 | 测试文件 | 状态 |
|--------|---------|---------|---------|------|
| WP-A 题库搜索 | bank service+router 已 commit `6271301` | QuestionBankPage.vue 344 行 | test_bank_search.py 254 行 | 后端已提交，前端+测试在 stash |
| WP-B 错题推荐 | bank service 有 diff | — | test_bank_recommendations.py 176 行 | 部分完成 |
| WP-C 作业推送 | homework service+router | HomeworkPage.vue 改动 | test_homework_remedial.py 270 行 | 部分完成 |
| WP-D 年级分析 | grade_service.py 360 行 + router | GradeAnalyticsPage.vue 226 行 | test_analytics_grade.py 254 行 | 代码就位未提交 |
| WP-E 教学计划 | teaching_plan_service.py 157 行 + router | TeachingPlanPage.vue 257 行 | test_teaching_plans.py 184 行 | 代码就位未提交 |

**执行步骤**:
1. `git stash pop stash@{0}` 恢复半成品
2. 逐个 WP 检查代码质量：
   - 读每个新建/修改的 .py 文件，确认 import 路径、model 引用、service 方法签名正确
   - 特别注意 teaching_plan_service.py 的 TeachingPlan import 路径：`from edu_cloud.models.teaching_plan import TeachingPlan`
   - academic/router.py 新增端点需确认 `teaching_plan_service` import 正确（pyright 曾报 `reportAttributeAccessIssue`）
3. 逐个 WP 跑测试：`.venv/bin/python -m pytest tests/test_api/test_bank_search.py tests/test_api/test_teaching_plans.py -v`
4. 修复失败的测试
5. 前端：`cd frontend && npx vitest run && npx vite build`
6. 确认无回归后，按 WP 分开 commit（或合并提交）

**风险点**:
- stash 基于 `b0f154a` 时的 working tree，之后有 10+ 个 commit，pop 可能有 merge conflict
- 冲突最可能出现在 `frontend/src/router/index.js` 和 `frontend/src/config/sidebarConfig.js`（stash 改了这两个文件，后续 commit 也改了）
- 如果冲突太多，建议放弃 stash，从零重做（方案在 `2026-04-25-haofenshu-service-layer-dispatch.md`）

### P1: LoginPage 品牌化（T1，10 分钟）

LoginPage 当前 41 行极简。增强内容：
- 品牌 Logo 区（校名+副标题）
- 角色选择（教师/管理员 Tab）
- 记住用户名 checkbox
- 暗色适配（当前 LoginPage.vue 自身样式可能和暗色主题不协调）
- 参考 ParentLogin 的品牌化写法

### P2: 浏览器端到端验收

所有前端增强都只经过 vitest + vite build 验证，未在浏览器实际验收。需要：
1. `cd /home/ops/projects/edu-cloud/frontend && npx vite build`（确保 dist/ 是最新）
2. 在 mcu.asia 逐页走查：
   - 教务 4 页：/academic/semesters, /academic/timetable, /assignments, /selections
   - 考试 3 页：/(dashboard), /exams, /grading/tasks/{id}
   - 阅卷 3 页：/marking, /marking/assign, /marking/progress
   - 家长 7 页：/parent/login → /parent → /parent/scores → ...
   - 学校 2 页：/schools, /school-settings
   - 联考+分析 3 页：/joint-exams, /analytics/report, /analytics/trend
   - 德育 5 页：/conduct/* 各子页面
3. 每页检查：数据加载、暗色主题、交互响应、空状态
4. 记录问题清单

### P3: 好分数 Phase 2 S2-S4（中期，需设计会话）

四轴调研中识别的 C 轴教学资源域仍有 6 个 🔴 Gap：
- 题库+组卷生态（S2，需 S1-B 知识点 L3 层级先完成）
- 作业内容编辑器（S2）
- 错题→推荐→作业闭环（S3）
- 备课资源库（S4）
- 试卷权限分级（S4）
- 教学计划→资源绑定（S4）

这些需要独立的 T3 brainstorming + writing-plans 会话。总设计在：
`/home/ops/projects/edu-cloud/docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md`

### P4: 技术债清理

- `edu-knowledge-base` 目录未被 git 追踪（检查是否需要 .gitignore 排除）
- `stash@{1}` ~ `stash@{3}` 是历史残留，确认不需要后 `git stash drop`
- CLAUDE.md 中的测试基线数字需更新（当前文档写 2190，实际 2227 collected）
- 前端 chunk 过大警告（index.js 1.5MB），考虑 manualChunks 拆包

---

## 三、活跃文档索引

| 文件 | 用途 | 状态 |
|------|------|------|
| `haofenshu-vs-edu-phase2-design.md` | Phase 2 总设计（S1-S4 分层） | 活跃总纲 |
| `haofenshu-research-axis-{a,b,c,d}.md` | 四轴对照调研报告 | 参考文档 |
| `haofenshu-service-layer-dispatch.md` | WP-A~E 服务层方案 | P0 执行依据 |
| `parent-portal-enhancement-plan.md` | Phase C 家长端方案 | 已完成 |
| `phase-bde-enhancement-plan.md` | Phase B+D+E 方案 | 已完成 |
| `haofenshu-absorption-handoff.md` | 上会话交接卡 | 历史参考 |
| `card-editor-merge-design.md` | 答题卡编辑器合入设计 | 待执行 |
| `frontend-migration-roadmap-design.md` | 前端迁移路线图 | 待执行 |
| `architecture-brief-for-codex.md` | Codex 审查用架构摘要 | 工具文件 |
| `compat-router-deprecation.md` | 兼容路由退役（截止 2026-07-31） | 活跃 |

---

## 四、启动 prompt

```
读 /home/ops/projects/edu-cloud/docs/plans/2026-04-26-continuation-plan.md。

当前分支 feat/analytics-report，commit 5b78af2。

按 P0 执行：
1. git stash pop stash@{0}（恢复 WP-A~E 服务层半成品）
2. 如有 merge conflict，先解决冲突
3. 逐个 WP 检查后端代码质量（重点 import 路径和 pyright 报错）
4. 跑 .venv/bin/python -m pytest tests/test_api/test_bank_search.py tests/test_api/test_teaching_plans.py tests/test_api/test_analytics_grade.py tests/test_api/test_bank_recommendations.py tests/test_api_exam/test_homework_remedial.py -v
5. 修复失败测试
6. cd frontend && npx vitest run && npx vite build
7. 无回归后 commit

如果 stash pop 冲突太多（>5 个文件），放弃 stash 走 B 方案：
读 /home/ops/projects/edu-cloud/docs/plans/2026-04-25-haofenshu-service-layer-dispatch.md，
按 5 个 WP 重新派发 executor agent。

P0 完成后，按 P1→P2→P3 顺序继续。
覆盖: 后端 pytest + 前端 vitest + vite build。未覆盖: mcu.asia 浏览器端到端（P2 专门做）。
```
