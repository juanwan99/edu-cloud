---
type: handoff
created: 2026-04-12 09:43:59
project_dir: C:\Users\Administrator\edu-cloud-f003
design: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-design.md
plan: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-plan.md
plan_review: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-plan-review.md
gates: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-gates.json
state: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-state.json
parent_handoff: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-handoff-exec.md
tier: T4
phase: execution
gate1_status: pass_r7
worktree_branch: f003-question-writeback-exec
worktree_base: 6cc6b30
---

# 交接卡：B1 F003 Question 写入责任链 — worktree 执行会话

> **本文件是增量叠加**。parent_handoff (`2026-04-11-f003-question-writeback-handoff-exec.md`) 是真源——R1-R7 历史教训、禁止事项、完整启动 prompt 都在那里。本文件只写 worktree 隔离带来的新增约束和路径修正。
>
> **执行顺序**: 先完整读 parent_handoff (241 行) → 再读本文件 → 再按本文件「启动 Prompt」段执行。

## Tier 声明

**T4** — design → plan → Gate 1 PASS(R7) → **worktree 隔离新会话执行** → 逐批 codex-review → reconciliation

## 为什么走 worktree 方案

主 repo `C:\Users\Administrator\edu-cloud` 工作区有 5 个未提交修改文件，**全部命中** parent_handoff §禁止事项第 1 条的 card 模块清单：

```
frontend/public/card-editor/styles.css
frontend/src/card-editor/render.js
src/edu_cloud/ai/tools/card_layout.py
src/edu_cloud/modules/card/answer_parser.py
src/edu_cloud/modules/card/answer_standardizer.py
```

这些是 card v2 小微排版的 WIP（parent_handoff §前置阻塞段明确警告不得触碰）。直接在主 repo 起执行会话会：
1. 任何 git commit 都会污染 scope（scope_guard 硬拦截）
2. T9/T10 改 `frontend/src/card-editor/export.js` 时和 WIP `render.js` 同目录，极易冲突

**解决方案**: 在 `6cc6b30`（Gate 1 PASS R7 commit）基础上创建独立分支 worktree，完全隔离 WIP。card v2 那条线留在主 repo 待 T4 收尾后独立处理。

## Worktree 环境参数

| 项 | 值 |
|---|---|
| 路径 | `C:\Users\Administrator\edu-cloud-f003` |
| 分支 | `f003-question-writeback-exec`（新建） |
| 基于 | `6cc6b30` — "review: B1 F003 Plan Review R7 PASS — Gate 1 闭合" |
| 工作区起始态 | clean (`git status --short` 空) |
| 已检出 tracked 文件 | 3133 个（含 `docs/plans/` 全套 7 个 f003 文件） |
| 主 repo WIP | 不会跟过来（worktree 基于 HEAD，不继承 unstaged） |

## 环境自举清单（新会话 Executor 第一步，顺序不可乱）

1. **cwd 校验**: `pwd` → 必须是 `C:\Users\Administrator\edu-cloud-f003`，不是主 repo
2. **分支校验**: `git branch --show-current` → 必须是 `f003-question-writeback-exec`
3. **worktree 校验**: `git worktree list` → 必须含本路径
4. **HEAD 校验**: `git log --oneline -1` → 必须是 `6cc6b30 review: B1 F003 Plan Review R7 PASS — Gate 1 闭合`
5. **Python 包注册**: `python -c "import edu_cloud; print(edu_cloud.__file__)"`
   - 若报 ModuleNotFoundError → `python -m pip install -e .`
   - 若路径指向主 repo `C:\Users\Administrator\edu-cloud\src\edu_cloud\...` → `python -m pip install -e . --force-reinstall --no-deps`（强制重绑到 worktree 源）
   - pyproject 锁 Python 3.11.9，Windows 本地 `C:\Program Files\Python311\python`
6. **前端依赖**（T9/T10 才需要，batch1 可暂缓）: `cd frontend && test -d node_modules || npm install`
7. **基线测试**: `python -m pytest --tb=short -q` → 应全绿 ≥1582 tests；任何 fail 先停下报告用户
8. **SessionState T4 声明**（parent_handoff §技术限制 #3 完整命令模板）:
   - 找当前 session_id: `ls -lt C:/Users/Administrator/.claude/hooks/state/` 看最新非 `blk_/unknown/test-` 的文件
   - 取前 8 位写入 `declared_tier=T4 / effective_tier=T4 / task_tier=T4 / current_topic=f003-question-writeback / current_gates_file=C:/Users/Administrator/edu-cloud-f003/docs/plans/2026-04-11-f003-question-writeback-gates.json`
9. **Gate 1 回执核对**: 读 `docs/plans/2026-04-11-f003-question-writeback-gates.json` → `plan_review.status=pass, plan_review.round=7, subject_hash=e47297a10c329b14762edf09f2dd56b8bdeedf99e88c66948a6441c28ec2bea3`

## Worktree 特有约束（parent_handoff 之外的新增）

1. **禁止 push 到 origin**: 本分支是临时执行分支，不要 `git push`。T4 收尾后由 reconciliation 流程决定合并策略
2. **禁止触碰主 repo**: 新会话只在 `C:\Users\Administrator\edu-cloud-f003` 范围内操作，禁止任何对 `C:\Users\Administrator\edu-cloud` 的读/写/cd（避免触发主 repo 的 WIP 或 scope_guard 冲突）
3. **跨 worktree import 风险**: 若 step 5 发现 `edu_cloud.__file__` 指向主 repo，必须 `pip install -e .` 强制重绑，否则 T1-T4 改 worktree 源码但 pytest 跑主 repo 源码，表现为"改了没效果"
4. **scope_guard 仍然生效**: T4 的 scope_guard 基于 plan §Task N Files 段判定可动文件范围，在 worktree 内部同样拦截越界。每批次开始前读 plan Task 文件清单
5. **分支 reconciliation**: 所有批次通过 Gate 3 Integration Review 后，reconciliation 阶段由 Planner 决策合并回 master 的方式（直接 FF / rebase / squash）

## 与 parent_handoff 的等价关系

本文件**不复述**以下内容（全部在 parent_handoff 中）：
- Gate 1 R1-R7 演进过程与 finding 收敛轨迹
- R4-F001 / R4-F002 / R4-F003 / R4-F004 / R5-F001 / R5-F002 / R6-F001 技术根因详解
- monkey-patch / expire_all / tracked_factory / 工厂签名 regions / V3 前端 mock 的具体陷阱
- 禁止事项完整清单（9 条）
- T4 批次审查流程（交接单→codex-review→gates.json 回执→下一批）

**执行者必须先读 parent_handoff 全文**，本文件只覆盖 worktree 层的增量约束。

## 启动 Prompt（复制到新窗口 `cd C:\Users\Administrator\edu-cloud-f003 && claude` 后的第一条消息）

```
[edu-cloud] Executor | 2026-04-12 09:43:59
项目目录: C:\Users\Administrator\edu-cloud-f003
重要: 这是 worktree, 不是主 repo (C:\Users\Administrator\edu-cloud)
worktree 分支: f003-question-writeback-exec (基于 master@6cc6b30 — Gate 1 PASS R7 commit)
隔离原因: 主 repo 有 card 模块 WIP 未提交, 触发 parent_handoff §禁止事项第 1 条, 故 T4 执行会话走 worktree 隔离

读取顺序 (必须按此顺序):
1. 本 worktree 交接卡 (增量约束): C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-12-f003-question-writeback-worktree-handoff.md
2. parent_handoff (真源, 含 R1-R7 历史和所有禁止事项): C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-handoff-exec.md
3. plan: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-plan.md
4. design: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-design.md
5. plan-review (必读 R3-R7 四段): C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-plan-review.md
6. state: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-state.json
7. gates: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-gates.json

角色: T4 Executor (batch1 起步)。Gate 1 Plan Review R7 PASS (commit 7a7fa1e, subject_hash e47297a1)。

环境自举 (worktree 交接卡 §环境自举清单 9 步, 按顺序执行):
1. pwd 校验 = C:\Users\Administrator\edu-cloud-f003
2. git branch --show-current = f003-question-writeback-exec
3. git worktree list 含本路径
4. git log --oneline -1 = 6cc6b30 review: B1 F003 Plan Review R7 PASS
5. python -c "import edu_cloud; print(edu_cloud.__file__)" — 不在 worktree 下则 pip install -e . --force-reinstall --no-deps
6. 前端依赖 (T9/T10 才用, batch1 可暂缓): frontend/node_modules 不存在则 npm install
7. python -m pytest --tb=short -q (应全绿 >=1582 tests, 任何 fail 停下报告用户)
8. SessionState T4 显式声明 (parent_handoff §技术限制 #3 完整命令):
   ls -lt C:/Users/Administrator/.claude/hooks/state/ 找最新非 blk_/unknown/test- 的文件, 取前 8 位
   写入 declared_tier=effective_tier=task_tier=T4, current_topic=f003-question-writeback,
   current_gates_file=C:/Users/Administrator/edu-cloud-f003/docs/plans/2026-04-11-f003-question-writeback-gates.json
9. 核对 gates.json: plan_review.status=pass / round=7 / subject_hash=e47297a1

任务路径 (plan Task 顺序严格, batch 内不并行):
- batch1: T0 (StudentAnswer 唯一约束调查) -> T1 (render.js 4 处 .page data-side + V1) ->
  T2 (extract_skeleton integration 验证 side 穿透) -> T3 (upsert_questions_from_skeleton + S2/S3/S4) ->
  T4 (upsert_template_both_sides + S5/S5b)
- batch2: T5 (Alembic migration) -> T6 (publish_card_atomic + S6/S6b) ->
  T7 (IntegrityError retry + S7a/S7b, S7c 延期 PostgreSQL CI) -> T8 (card router publish_card 接入 service)
- batch3: T9 (前端 publishCard 重写 + V2) -> T10 (ExamDetailPage 签名 + V3) ->
  T11 (pipeline_router 工厂 + S8a/b/c/d-a/d-b) -> T12 (E2E S9 + 回归 + CLAUDE.md + [实现完成])

每批次完成后 (T4 规范 — review-templates.md §T4 流程):
1. 使用 executing-plans skill 规范输出审查交接单 (review-templates.md「审查交接单」段)
2. 写入 docs/plans/2026-04-11-f003-question-writeback-review-handoff-batch{N}.md
3. git commit 审查交接单 (scope 不违反 plan Task 范围)
4. 停下等待 Planner (主 repo 另一会话) 调 codex-review skill 跑 GPT 代码审查
5. Planner 写 gates.json code_review_batch{N} 回执
6. PASS -> 下一批 / FAIL -> Round 循环 (每批最多 3 轮, Round 2 后 Planner 分类处置 code-bug vs design-concern)

batch3 完成后: Integration Review (Gate 3, 可用扩展批次审查替代) -> reconciliation skill (Gate 4)

约束 (违反直接 FAIL, 详细规则在 parent_handoff §T4 约束段和 review-templates.md):
- review-templates.md 流程编排 + 三态 finding 模型 (verified / contested / suggestion)
- plan 头部「现实代码锚点」CR-1/CR-2/CR-3/CR-4 是字节级真源, 实现时直接对照源文件
- Python 3.11.9 unittest.mock 无 spy_return, S8d 必须用 tracked_factory + factory_returns 模式
- pipeline_router 必须 import edu_cloud.database as db_mod (R4-F001 根因)
- 测试里 db.expire_all() 不带 await (R4-F002 同步 API)
- 工厂函数接 regions: list[dict] 不接 Template ORM (R3-F005)
- V3 前端测试分别 mock api/exams 和 api/subjects 两个模块

Worktree 特有约束 (worktree 交接卡 §Worktree 特有约束):
- 禁止 git push (分支为临时执行分支, 收尾后由 reconciliation 决定合并)
- 禁止读写主 repo C:\Users\Administrator\edu-cloud (scope 冲突 + WIP 污染)
- Python 包必须绑定到 worktree 源 (step 5 校验)
- scope_guard 在 worktree 内同样生效

禁止 (parent_handoff §禁止事项完整 9 条):
- 碰 card 模块源码 (render.js / answer_parser.py / answer_standardizer.py / styles.css / card_layout.py)
- 修改 plan.md 头部锚点段 (Gate 1 已字节级对齐)
- 修改 plan-review.md R1-R7 历史段
- 修改 design.md 已有段 (design_freeze_guard)
- from edu_cloud.database import async_session
- await db.expire_all()
- spy_factory.spy_return / callable 弱断言
- 工厂签名接 Template ORM
- 跳过 gates.json 回执直接进入下一批次

关键提示:
- 13 tasks / 3 batches, batch 内严格顺序, 不并行
- T0 调查结论影响 T5 migration 走向, 必须最先完成
- Gate 1 经 7 轮审查才 PASS, R3-R7 教训已写进锚点段和 Contract Pack, 尊重约束
- 本执行会话只改 plan 声明的文件范围 (scope_guard 硬拦截), 越界修改须先用户同意
- 完成批次后不要继续下一批, 停下等待 Planner 审查回执

完成后输出审查交接单。
```

## 审查规范提醒（T4）

**Executor（本文件指向的新会话）**: 每批次完成后输出审查交接单（review-templates.md「审查交接单」段），git commit，停下等待 Planner。

**Planner（主 repo 另一会话）**: 接收审查交接单后调 codex-review skill 跑 GPT 代码审查，写 gates.json `code_review_batch{N}` 回执。GPT 不可用 → gates.json 写 `blocked` + reason，等用户指令。

**Gate 3 Integration Review**: 所有批次完成后强制执行（单批次 T4 可用扩展批次审查替代，须包含最小集成清单）。

**Gate 4 Reconciliation**: Integration Review PASS 后由 Planner 调 reconciliation skill 对齐 design.md `[实现完成]` 标记 + 决定合并策略回 master。

完成后输出审查交接单。
