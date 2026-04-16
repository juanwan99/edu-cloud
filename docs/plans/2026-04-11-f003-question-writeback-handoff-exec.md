---
type: handoff
created: 2026-04-12 08:29:46
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan.md
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-gates.json
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-state.json
plan_review: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan-review.md
tier: T4
phase: execution
gate1_status: pass_r7
---

# 交接卡：B1 F003 Question 写入责任链重设 — 执行会话

**Tier**: T4 — design → plan → Gate 1 PASS(R7) → **新会话执行** → 逐批 codex-review → reconciliation

## Gate 1 最终状态（R7 PASS，commit `7a7fa1e`）

| 项 | 值 |
|---|---|
| plan commit | `7a7fa1e`（R6 处置 + R7 PASS）|
| plan subject_hash | `e47297a10c329b14762edf09f2dd56b8bdeedf99e88c66948a6441c28ec2bea3` |
| plan_review round | 7 |
| raw_output_hash (R7) | `38d0f392575b034c6178e8b419ba7f15124eb1e28301e6248c842c4cd6996d8f` |
| finding 收敛 | 6 → 5 → 5 → 5 → 2 → 1 → **0** |
| 用户扩展次数 | 4（R4/R5/R6/R7 均用户授权）|

**审查历史真源**: `docs/plans/2026-04-11-f003-question-writeback-plan-review.md` §Round 1..7。新会话开始前**必须通读 R3-R7 四段**（前两段已被后续修复覆盖）。

## 前置阻塞（执行会话启动前必须确认）

**card 模块 WIP 小微排版 v2 视觉验收必须已回主线**。本计划触及 `frontend/src/card-editor/export.js` 的 `publishCard()` 函数（T9/T10），若 v2 WIP 仍在冲突区会引发合并冲突。验证命令：

```bash
cd C:/Users/Administrator/edu-cloud && git log --oneline -20 | grep -i "xiaowei\|card-editor\|小微"
```

确认 v2 已合入 master 后才可启动本计划的 T9/T10。同时本执行会话**绝对不允许碰 card 模块源码**（`render.js` / `answer_parser.py` / `answer_standardizer.py` / `styles.css` / `card_layout.py`），只能动 `card-editor/export.js` 的 `publishCard()` 函数。

## 批次与任务路径

| batch | 描述 | Task IDs | Gate |
|-------|------|---------|------|
| batch1 | 纯函数 + 前置修复（Slice A+B+C） | T0-T4 | code_review_batch1 |
| batch2 | 事务层 + migration + router（Slice D+E+F）| T5-T8 | code_review_batch2 |
| batch3 | 前端 + pipeline + E2E（Slice G+H+I）| T9-T12 | code_review_batch3 + integration_review |

**T0 前置决策**：StudentAnswer 唯一约束调查 + 决策落地（plan §T0 有具体方案）。T0 的调查结论影响 T5 migration 走向，必须先完成。

**batch 内顺序**：按 T0 → T12 严格顺序执行。不允许跳跃或并行。

## 关键历史教训（R1-R7 汇总，plan-review.md 详细段为真源）

执行 T11（pipeline_router）和 T3/T4/T6/T7（publish_service）时必须理解这些陷阱：

### 1. monkey-patch 语义（R4-F001 根因）

`tests/conftest.py` `client` fixture 通过 `_db_mod.async_session = session_factory` 对 `edu_cloud.database.async_session` 属性做 monkey-patch。被测模块**必须**用 `import edu_cloud.database as db_mod` 然后在运行时调 `db_mod.async_session()`，**禁止**用 `from edu_cloud.database import async_session`（import-time 绑定抓到旧引用，monkey-patch 对其无效）。

详见 plan §现实代码锚点 CR-1 关键事实 2。

### 2. `AsyncSession.expire_all()` 是同步 API（R4-F002 根因）

SQLAlchemy 源码 `sqlalchemy/ext/asyncio/session.py` 中 `expire_all` 直接 `self.sync_session.expire_all()`，**不返回 coroutine**。测试里必须写 `db.expire_all()` **不带 `await`**，否则 `TypeError: object NoneType can't be used in 'await' expression`。

### 3. S8d tracked_factory 模式（R4-F004 → R5-F002）

Python 3.11.9 `unittest.mock.MagicMock` **没有** `spy_return` 属性。`patch.object(..., wraps=original)` + `spy.spy_return` 会在断言阶段抛 `AttributeError`。

**正确模式**（plan Task 11 Step 1b）：
```python
original_factory = pr_mod.build_pipeline_save_answer_fn
factory_returns = []

def tracked_factory(**kwargs):
    result = original_factory(**kwargs)
    factory_returns.append(result)
    return result

with patch.object(pr_mod, "build_pipeline_save_answer_fn",
                  side_effect=tracked_factory) as spy_factory:
    # ...
    
assert captured_kwargs["save_answer_fn"] is factory_returns[0]
```

**禁止模式**：`spy_factory.spy_return` / `callable(save_answer_fn)` 弱断言 / 另造 closure 后 `is` 断言。

### 4. SQLite in-memory 单 connection 限制（S7c test_debt 原因）

`conftest.py` `db` fixture 用 `sqlite+aiosqlite:///:memory:`，**无法模拟真实跨 session race**（单 connection 池 + in-memory 数据库），SAVEPOINT flush 拦截不稳定。**S7c (SAVEPOINT retry 分支) 已延期到 PostgreSQL CI**（plan §T7 test_debt 段）。本执行会话的 S7a/S7b 是 Gate 1 PASS 护栏（纯 SAVEPOINT 语义 + SELECT-first 主路径），不需要模拟 race。

### 5. 工厂函数签名 `regions: list[dict]` 不接 Template ORM（R3-F005 根因）

`pipeline_router.py` `start_pipeline` 有两条模板加载分支：
- `tpl_path` 分支：只有 `template = parse_tpl_file(...)` 一个 dict，**无 tpl 变量**
- DB 分支：`tpl` 是 Template ORM + `template` 是手工 dict，**两个不同变量**

统一装配点是 `template["regions"]`（list[dict]）。工厂必须接 `regions: list[dict]` 参数，**不能接 Template ORM**。

### 6. 锚点段字节级真源（R5-F001 → R6-F001）

`plan §现实代码锚点` CR-1..CR-4 已字节级对齐源文件（R7 GPT 用 PowerShell `BYTE_EQUAL_LF` 验证通过）。**实现时直接读源文件**，不要把锚点段当作"简化摘录"——锚点保留了源码所有注释/空行/docstring。

### 7. V3 前端测试 ExamDetailPage 真实结构（R3-F004 根因）

`ExamDetailPage.vue` import 分两个模块：`api/exams` 导出 `getExam, updateExam`；`api/subjects` 导出 `listSubjects, createSubject`。V3 mock 必须分两个模块 mock。发布按钮 `disabled` 双条件：`!visualEditorSubjectId || exam?.status !== 'draft'`。`handlePublishCard` 通过 `dialog.warning({onPositiveClick})` 中转，V3 mock `useDialog` 让 `warning` 立即同步调用 `onPositiveClick`。

详见 plan §现实代码锚点 CR-3 关键事实 1-7。

## 技术限制与环境 quirks

1. **Python 版本**: 3.11.9（`pyproject.toml` 锁定）
2. **codex exec PowerShell 乱码**: Windows tee 日志可能有 gbk 乱码，但 GPT MCP filesystem 读文件不受影响
3. **SessionState declared_tier 显式声明**: 新执行会话启动时第一步必须手动声明 T4 到 SessionState：
   ```bash
   cd "C:/Users/Administrator/.claude/hooks" && python -c "
   import sys; sys.path.insert(0, '.')
   import hook_lib
   # 找当前 session_id: ls -lt ~/.claude/hooks/state/ 看最新非 blk_/unknown/test- 的文件
   ss = hook_lib.SessionState('<session_id_first_8_chars>')
   ss.write('declared_tier', 'T4')
   ss.write('effective_tier', 'T4')
   ss.write('task_tier', 'T4')
   ss.write('current_topic', 'f003-question-writeback')
   ss.write('current_gates_file', 'C:/Users/Administrator/edu-cloud/docs/plans/2026-04-11-f003-question-writeback-gates.json')
   "
   ```
4. **scope_guard**: T4 git commit 必须在 plan Task 声明的文件范围内。每批次开始前 Executor 读 plan §Task N Files 段确认可动文件列表
5. **write-guard 200 行阈值**: plan.md 已 >3000 行，禁止 Write 全量重写；本次不改 plan.md 但须知
6. **design_freeze_guard**: design.md 已冻结（Gate 1 PASS 之后），禁止修改已有设计段；若执行中发现 design 缺陷，记入 design.md §待处置段（追加而非修改）

## 审查流程（T4 规范）

每批次完成后：
1. Executor 输出审查交接单（`docs/plans/2026-04-11-f003-question-writeback-review-handoff-batch{N}.md`）
2. Planner 调 codex-review skill 跑 GPT 审查（`docs/plans/2026-04-11-f003-question-writeback-review-report-batch{N}.md`）
3. Planner 写 gates.json `code_review_batch{N}` 回执
4. PASS → 下一批 / FAIL → Round 循环（每批最多 3 轮，Round 2 后 Planner 分类处置 code-bug vs design-concern）

所有 3 批次完成后：
5. Planner 调 codex-review skill 跑 Integration Review（batch3 可用"扩展批次审查"替代，须包含最小集成清单）
6. Integration Review PASS → reconciliation skill 对齐 design.md + handoff 更新 [实现完成] 标记
7. gates.json 全部 gate pass → Gate 4 reconciliation 收尾

**审查规范真源**: `~/.claude/rules-t3/review-templates.md` 各锚点段

## 已处置 finding（历史记录）

所有 R1-R7 finding 均 `terminal: resolved-correct`（见 gates.json `findings` 数组）。执行会话中**不得**重新触发这些旧问题：

- **R4-F001** (monkey-patch 语义) → pipeline_router.py 必须 `import ... as db_mod`
- **R4-F002** (expire_all 同步) → 测试里 `db.expire_all()` 不带 await
- **R4-F003** (S7c 伪实现) → S7c 延期 PostgreSQL CI，本次 S7a/S7b 为护栏
- **R4-F004** (callable 弱断言) → S8d 必须 identity 断言
- **R5-F001** (锚点非字节级) → CR-1..CR-4 已字节级对齐，勿改
- **R5-F002** (spy_return 不存在) → S8d 用 tracked_factory 模式
- **R6-F001** (空白行对齐) → CR-2 单空行拼接 + CR-4 import 后空行

## 禁止事项

- ❌ 碰 card 模块源码（render.js / answer_parser.py / answer_standardizer.py / styles.css / card_layout.py）
- ❌ 修改 plan.md 头部锚点段 CR-1/CR-2/CR-3/CR-4（Gate 1 已字节级对齐）
- ❌ 修改 plan-review.md R1-R7 历史段（只追加，不改写）
- ❌ 修改 design.md 已有段（design_freeze_guard 拦截）
- ❌ 使用 `from edu_cloud.database import async_session`（R4-F001 禁止）
- ❌ `await db.expire_all()`（R4-F002 禁止）
- ❌ `spy_factory.spy_return` / `callable(save_answer_fn)` 弱断言（R5-F002 禁止）
- ❌ 工厂函数签名接 Template ORM（R3-F005 禁止）
- ❌ 跳过 gates.json 回执直接进入下一批次
- ❌ 同会话内跑 Plan Review + Execution（Superpowers 覆盖规则 #2：T3/T4 writing-plans 完成后必须新会话）

## 启动 Prompt（复制到新窗口）

```
[edu-cloud] Executor | 2026-04-12 08:29:46
项目目录: C:\Users\Administrator\edu-cloud
读取本交接卡: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-handoff-exec.md
读取 plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan.md
读取 design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-design.md
读取 plan-review (R3-R7): C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan-review.md
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-state.json
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-gates.json

角色: T4 Executor（batch1 起步）。Gate 1 Plan Review R7 PASS (commit 7a7fa1e)。
前置阻塞: 验证 card 模块小微排版 v2 已回主线后才可动 T9/T10。

前置声明（第一步执行）:
1. 显式声明 T4 tier 到 SessionState（见交接卡 §技术限制 #3）
2. ls -lt ~/.claude/hooks/state/ 找当前 session_id, 前 8 位写入
   declared_tier/effective_tier/task_tier=T4 + current_topic=f003-question-writeback
   + current_gates_file 绝对路径

任务路径（按 plan §Task 顺序执行）:
- batch1: T0 (StudentAnswer 唯一约束调查) → T1 (render.js 4 处 .page data-side + V1) →
  T2 (extract_skeleton integration 验证 side 穿透) → T3 (upsert_questions_from_skeleton + S2/S3/S4) →
  T4 (upsert_template_both_sides + S5/S5b)
- batch2: T5 (Alembic migration) → T6 (publish_card_atomic + S6/S6b) →
  T7 (IntegrityError retry + S7a/S7b, S7c 延期) → T8 (card router publish_card 接入 service)
- batch3: T9 (前端 publishCard 重写 + V2) → T10 (ExamDetailPage 签名 + V3) →
  T11 (pipeline_router 工厂 + S8a/b/c/d-a/d-b) → T12 (E2E S9 + 回归 + CLAUDE.md + [实现完成])

每批次完成后:
1. 使用 executing-plans skill 的规范输出审查交接单
2. 交接单写入 docs/plans/2026-04-11-f003-question-writeback-review-handoff-batch{N}.md
3. git commit 交接单
4. 切换到 Planner 调 codex-review skill 跑 GPT 代码审查
5. 等 PASS 后进下一批; FAIL 进入 Round 循环 (最多 3 轮)

batch3 完成后执行集成审查 (可用扩展批次审查替代), 然后 reconciliation skill 对齐 design + handoff。

约束 (必读):
- review-templates.md 流程编排 + 三态 finding 模型
- plan 头部"现实代码锚点"段 CR-1/CR-2/CR-3/CR-4 为真源, 实现时按锚点对照源文件
- Python 3.11.9 unittest.mock 无 spy_return, S8d 必须用 tracked_factory + factory_returns 模式
- pipeline_router 必须 import edu_cloud.database as db_mod (R4-F001 根因)
- 测试里 db.expire_all() 不带 await (R4-F002 同步 API)
- 工厂函数接 regions: list[dict] 不接 Template ORM (R3-F005)
- V3 前端测试分别 mock api/exams 和 api/subjects 两个模块

禁止 (完整列表见交接卡 §禁止事项):
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
- T0 的调查结论影响 T5 migration 走向, 必须最先完成
- Gate 1 经过 7 轮审查才 PASS, R3-R7 的教训已写进锚点段和 Contract Pack, 实现时尊重这些约束
- 本执行会话只改 plan 声明的文件范围 (scope_guard 硬拦截), 越界修改必须先用户同意

完成后输出审查交接单。
```

## 审查规范提醒

**Executor**: 每批次完成后输出审查交接单（格式见 review-templates.md「审查交接单」段，含逐 Task 自审表 + 验证清单自检 + 自查段 + 预审自检）。

**Planner**: 读审查交接单后调 codex-review skill。GPT 不可用 → gates.json 写 `blocked` + reason，等用户指令。

**T4 Integration Review**: 所有批次完成后必须跑 Integration Review（Gate 3），然后 reconciliation（Gate 4）。
