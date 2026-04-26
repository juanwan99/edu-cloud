---
type: handoff
created: 2026-04-11 22:22:00
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan.md
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-state.json
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-gates.json
plan_review: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan-review.md
exploration_notes: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-exploration-notes.md
r1_raw_log: C:\Users\Administrator\edu-cloud\docs\plans\.codex-raw-plan_review-r1-20260411-215737.log
r2_raw_log: C:\Users\Administrator\edu-cloud\docs\plans\.codex-raw-plan_review-r2-20260411-221835.log
---

# 交接卡：B1 F003 Plan Review R3 处置 → Gate 1 收尾

**Tier**: T4 — **本次不是执行会话**。Gate 1 R1 FAIL 6 findings → R2 FAIL 5 new findings。新会话要处置 R2 finding → 跑 R3 → 收尾 Gate 1。真正的 T4 执行需 Gate 1 PASS + card 模块 WIP 回主线之后另启新会话。

## 会话分工

- **上一会话**: exploration + 4 批 T2 (B2/B3a/B6a/B6c) + B1 F003 brainstorming → design `7ad6416` → plan draft `0e3d247` → Plan Review R1 FAIL 6 findings `d742310` → R1 处置 `406af8b` → R2 FAIL 5 new findings（已写入 plan-review.md 但未 commit）
- **本交接会话**: 处置 R2 的 5 个 finding → commit → 跑 R3 → Gate 1 PASS 或进入 conditional pass → 生成执行 handoff-card
- **未来执行会话**: card 模块 WIP 回主线 + Gate 1 PASS 后启动，走 executing-plans

## Round 循环状态

| Round | 结果 | finding | 类型 | commit |
|-------|------|---------|------|--------|
| R1 | FAIL | 6 (F001-F006) | 全 defect_fix | `d742310` |
| R1 处置 | - | 全部 resolved | - | `406af8b` |
| R2 | **FAIL** | **5 new (F001-F005)** | **code-bug x2 + test-gap x3** | **待 commit** |
| R3 | pending | - | - | - |

还剩 1 轮 (R3) 硬额度。R3 仍 FAIL 需按 review-templates 分类处置或用户介入决策。

## 当前 git 状态（新会话第一步要核对）

```
未 commit:
  M docs/plans/2026-04-11-f003-question-writeback-plan-review.md  (追加了 R2 段)
  ?? docs/plans/.codex-raw-plan_review-r2-20260411-221835.log     (R2 原始日志)
  ?? docs/plans/2026-04-11-f003-question-writeback-handoff.md     (本交接卡)

已 commit:
  7ad6416 design.md
  0e3d247 plan draft + state.json + gates.json
  d742310 plan-review.md R1 report + R1 raw log
  406af8b plan.md + design.md + CLAUDE.md (R1 6 findings 全部处置)
```

R2 原始日志 SHA256: `132098bc14685d3c99617d27a8a211bf7b4e36ee4b7f92d78048e68e6e7a432e`

## R2 的 5 个 Finding 摘要（完整细节在 plan-review.md § Round 2 段）

### R2-F001 HIGH code-bug — S7 retry 破坏事务完整性

**根因**: Task 7 的 `upsert_questions_from_skeleton` 在单题 IntegrityError 时调 `await db.rollback()`。但此函数被 `publish_card_atomic` (T6) 包在**同一事务内**，rollback 会连带回滚前面已 upsert 成功的其他 Question，但循环只补救当前冲突题。

**修复方向**: 用 SQLAlchemy `async with db.begin_nested():` (SAVEPOINT) 让单题 retry 只回滚子事务，不破坏外层 publish 事务。

**涉及文件**: `plan.md Task 7 Step 3` retry 代码 + `plan.md Task 6 / design.md §6.1 §6.2` 事务边界说明

**Forbidden**: 循环内全局 rollback / 吞冲突不重建 state / 无限重试

### R2-F002 HIGH code-bug — Task 11 exam_id 字段契约不一致

**根因**: plan Task 11 示例代码读 `body.exam_id`，但现有 `pipeline_router.py:25` 的 `PipelineStartRequest` 只有 `subject_id/side/image_dir/tpl_path`，没有 exam_id。现有实现 L145 用 `subject.exam_id` 派生。

**修复方向**: Task 11 示例代码改回通过 `SELECT Subject WHERE id=body.subject_id` 派生 exam_id（保持现有 API 契约不变）。

**涉及文件**: `plan.md Task 11 Step 1` S8 测试 + `plan.md Task 11 Step 3` 示例代码

### R2-F003 HIGH test-gap — S9b 绕开 pipeline_router 闭包装配

**根因**: Task 12 的 S9b 测试手工 `db.add(StudentAnswer)` 绕过 T11 的 pipeline_router save_answer_fn 构建路径。Contract Pack CE-002 缓解失效。

**修复方向**（推荐方案 B）: 在 Task 11 Step 3 抽出独立工厂函数：

```python
def build_pipeline_save_answer_fn(
    template: Template, exam_id: str, subject_id: str, school_id: str
) -> Callable:
    """从 Template 构建 region_map + 返回 save_answer_fn 闭包。pipeline_router 和 tests 共用。"""
    region_map = {r["id"]: r["question_id"] for r in template.regions or [] if r.get("question_id")}
    async def save_answer(exam_id, subject_id, student_id, question_id, image_path, school_id):
        real_qid = region_map.get(question_id)  # question_id 参数实际接 region_id（pipeline_service 命名遗留）
        if not real_qid:
            logger.warning("orphan_crop: region_id=%s not in region_map", question_id)
            return
        async with async_session() as db2:
            db2.add(StudentAnswer(exam_id=exam_id, subject_id=subject_id, student_id=student_id,
                                  question_id=real_qid, image_path=image_path, school_id=school_id))
            try:
                await db2.commit()
            except IntegrityError:
                await db2.rollback()  # 幂等，已存在则 skip
    return save_answer
```

然后：
- pipeline_router `start_pipeline` 调 `build_pipeline_save_answer_fn(tpl, exam_id, subject_id, school_id)` 拿闭包
- S8 (Task 11) 调工厂函数 + 直接调闭包验证 orphan skip
- S9b (Task 12) 调工厂函数 + 调闭包写 StudentAnswer + 查 marking/subjects.total_answers

**涉及文件**: `plan.md Task 11 Step 3` + `plan.md Task 11 Step 1` S8 + `plan.md Task 12` S9b + `plan.md Contract Pack CE-002 mitigation`

### R2-F004 MED test-gap — Task 10 V3 未挂载 ExamDetailPage

**根因**: V3 测试直接 import publishCard 三参调用，没 mount ExamDetailPage 组件，无法检测 L868 真实调用点是否已改。

**修复方向**: 用 `@vue/test-utils` mount + mock fetch + 触发发布按钮 click + 断言 publishCard 被调用时含正确 examId：

```js
import { mount } from '@vue/test-utils'
import ExamDetailPage from '../ExamDetailPage.vue'
// 用 vi.spyOn 替代直接 import publishCard
const publishCardSpy = vi.fn().mockResolvedValue({ pdf: new Blob() })
vi.mock('../../card-editor/export.js', () => ({ publishCard: publishCardSpy, getCleanHTML: () => '<html/>' }))
// mount 时注入 route params + 触发 click
```

**涉及文件**: `plan.md Task 10 Step 3` V3 代码重写

### R2-F005 HIGH test-gap — S8 含 skip + TODO + "FAIL 或 skip"

**根因**: Contract Pack INV-006 映射 S8，但 S8 方案含 `pytest.skip(...)` + TODO + "FAIL 或 skip" 不确定预期。不是确定性可执行测试。

**修复方向**: 移除 skip 占位，用 R2-F003 抽出的 `build_pipeline_save_answer_fn` 工厂函数来写确定性断言。

**涉及文件**: `plan.md Task 11 Step 1` S8 代码重写

**R2-F003 和 R2-F005 应合并处置**（都依赖同一个工厂函数抽出）。

## R2 处置建议顺序

新会话按此顺序做：

1. **commit R2 review 当前未 commit 的文件**（plan-review.md R2 段 + R2 raw log + 本交接卡）
2. **R2-F002**（最简单，纯字段改回）— `plan.md Task 11` 所有 `body.exam_id` 改为 SELECT Subject 派生
3. **R2-F003 + R2-F005 合并**（同一工厂函数）— `plan.md Task 11 Step 3` 定义 `build_pipeline_save_answer_fn` 工厂；`Task 11 Step 1` S8 + `Task 12` S9b 都改用该工厂函数
4. **R2-F001**（事务边界重设）— `plan.md Task 7 Step 3` retry 改用 `async with db.begin_nested():`；`design.md §6.1 §6.2` 同步更新事务边界描述；`CLAUDE.md` 参考文档表可能需要追加说明（doc-sync-guard 硬拦截）
5. **R2-F004**（Vue Test Utils mount）— `plan.md Task 10 Step 3` V3 改用 `mount(ExamDetailPage)` + spy publishCard + click 触发
6. **更新 Contract Pack**：`plan.md §Contract Pack`
   - `INV-006` test_ref 可能变（若 S8 函数名改）
   - `CE-002 mitigation` 改为"S9b 通过工厂函数触达装配路径"
7. **commit R2 处置**（一个 commit，信息注明处置 5 个 R2 finding）
8. **跑 R3 codex-review**（下方命令）
9. **解析 R3 结果**（下方分支）

## R3 codex-review 启动命令

`/tmp/codex-plan-review-prompt.txt` 可能已失效，R3 前重新生成：

```bash
source ~/.bashrc && source ~/.claude/hooks/env_init.sh 2>/dev/null
export PLAN_FILE="C:/Users/Administrator/edu-cloud/docs/plans/2026-04-11-f003-question-writeback-plan.md"
export DESIGN_FILE="C:/Users/Administrator/edu-cloud/docs/plans/2026-04-11-f003-question-writeback-design.md"
export PROJECT_CLAUDE_MD="C:/Users/Administrator/edu-cloud/CLAUDE.md"
export PROJECT_DIR="/c/Users/Administrator/edu-cloud"

cat > /tmp/codex-plan-review-prompt.tpl <<'PROMPT_EOF'
You are a senior architect reviewing an implementation plan.

Read these files:
1. ${PLAN_FILE}
2. ${DESIGN_FILE}
3. ${PROJECT_CLAUDE_MD}

This is Round 3 of Plan Review. R1 (6 findings) and R2 (5 findings) already resolved.
R2 findings were:
- R2-F001 HIGH code-bug: S7 retry rollback destroys publish transaction (fixed with savepoint/begin_nested)
- R2-F002 HIGH code-bug: Task 11 body.exam_id not in PipelineStartRequest (fixed by deriving from subject.exam_id)
- R2-F003 HIGH test-gap: S9b bypasses pipeline_router assembly (fixed with factory function)
- R2-F004 MED test-gap: Task 10 V3 doesn't mount ExamDetailPage (fixed with @vue/test-utils mount)
- R2-F005 HIGH test-gap: Task 11 S8 had pytest.skip + TODO (fixed with factory function)

Verify all 5 R2 findings are properly resolved. Do NOT re-report R1 findings (already resolved).
Check Contract Pack INV-006 test_ref and CE-002 mitigation reflect new factory function strategy.

Perform full plan review per checklist A-F from ~/.claude/rules-t3/review-templates.md
- A 自洽性 / B 代码库对齐 / C 架构适配 / D 完整性 / D+ 测试契约质量
- E 风险评估 / F Contract Pack 完整性

Output structured findings: ID / Severity / Category / Type / Before-behavior / After-behavior /
Evidence (file:line) / Impact / Repair hypothesis (advisory).

If a finding touches invariants, risk_modules, or red-flag patterns, describe:
1. likely repair direction
2. forbidden fix patterns
3. "requires independent fix design + Semantic Regression Gate"

Write in Chinese. Conclude with PASS or FAIL.
PROMPT_EOF

envsubst < /tmp/codex-plan-review-prompt.tpl > /tmp/codex-plan-review-prompt.txt

REVIEW_LOG="$PROJECT_DIR/docs/plans/.codex-f003-plan-review-r3-raw.log"
codex exec -s danger-full-access -C "$PROJECT_DIR" "$(cat /tmp/codex-plan-review-prompt.txt)" 2>&1 | tee "$REVIEW_LOG"
```

预期 5-15 分钟出结果。

## R3 结果分支

| R3 结果 | 处置路径 |
|---------|---------|
| **PASS** | 写 plan-review.md Round 3 段 → gates.json plan_review=pass round=3 + report_path + SHA256 → 调 handoff-card skill 生成**执行**交接卡 → 本会话结束 |
| **FAIL 仅 design-concern/suggestion** | 同上 PASS 流程（review-templates 规则：design-concern 不阻塞，Planner 在 design.md §待处置段记录） |
| **FAIL 仍有 code-bug / test-gap HIGH/MED** | **必须向用户汇报 + 请求决策**：(a) 降级为 deferred/accepted-risk（需具体 reason）(b) 重启 R4 循环（review-templates 允许但非标准）(c) 推翻方案 D 整体重做设计 |
| **behavior_change finding 出现** | 逐条单独呈现 before/after/inv_conflict 给用户，禁止批量确认（L017） |
| **GPT Codex 超时/不可用** | gates.json 写 blocked 状态 + reason → 等用户指令，不降级不自审 |

## 生成执行 handoff-card（R3 PASS 后）

Gate 1 PASS 后调用 handoff-card skill 生成 `docs/plans/2026-04-11-f003-question-writeback-handoff-exec.md`——这份是给真正的 T4 执行会话用的。

执行交接卡必须包含：
- **启动前置阻塞**: `cd C:\Users\Administrator\edu-cloud && git status frontend/src/card-editor/ src/edu_cloud/modules/card/` 若有未 commit 修改 → 暂停等用户完成小微排版 v2 视觉验收
- **Tier T4** 声明命令（SessionState write）
- **Skill**: superpowers:executing-plans
- **批次**: Batch 1 (T0-T4) → code review Gate 2 → Batch 2 (T5-T8) → code review Gate 2 → Batch 3 (T9-T12) → code review Gate 2 → integration review Gate 3
- **指向**: state.json + plan.md 绝对路径
- **说明**: T0 是锚定验证，直接通过；T1 F001 render.js 首个实质改动，触碰 card 模块 WIP 冲突区

## 约束与偏好（只记增量）

### 用户偏好

1. **defect_fix 批量处置**：无需逐条确认
2. **behavior_change 必须逐条**：L017 硬要求
3. **短回复文化**：用"同意 / 可以 / B / I / 授权"等字母或短语表达接受
4. **路径处置 Q1=C**：card 模块 WIP 必须先完成视觉验收回主线

### 技术限制 / 环境 quirks

1. **codex exec PowerShell 乱码**：`codex exec -C` 在 Windows 的 tee 日志会混乱码，但 GPT 的 MCP filesystem 读文件不受影响，verdict 可信
2. **SessionState declared_tier 显式声明**：调 T3/T4 skill 前必须写
   ```python
   cd /c/Users/Administrator/.claude/hooks && python -c "
   import sys; sys.path.insert(0, '.')
   import hook_lib
   ss = hook_lib.SessionState('<new_session_id>')
   ss.write('declared_tier', 'T4')
   ss.write('effective_tier', 'T4')
   ss.write('task_tier', 'T4')
   "
   ```
3. **doc-sync-guard 硬拦截**：commit 含 design.md 修改时必须同步更新 `edu-cloud/CLAUDE.md`（至少追加 design 引用行）。参考 commit `406af8b` 对 CLAUDE.md L600 的追加方式
4. **write-guard 200 行阈值**：已有文件 >200 行禁止 Write 全量重写，必须 Edit 增量。本交接卡约 300 行，新会话若要改必须 Edit 或先 rm 再 Write

## 禁止事项

- ❌ 启动 executing-plans skill（那是执行交接的职责）
- ❌ 碰 card 模块源码（render.js / answer_parser.py / answer_standardizer.py / styles.css / card_layout.py 都是小微排版 v2 WIP 冲突区）
- ❌ 重跑 T2 快修（B2/B3a/B6a/B6c 已 commit 完成：d5cedb4 / bbeeb8f / 2ce070b / 75922c7）
- ❌ 修改 R1/R2 plan-review.md 已写入的历史段（只追加 R3 段）
- ❌ 删除任何 `.codex-raw-plan_review-*.log`
- ❌ 写 "R3 手动自审通过" 绕过 GPT（GPT 不可用必须 blocked）
- ❌ 在 R3 新增 behavior_change 而不向用户逐条确认
- ❌ R3 FAIL 时伪装 PASS

## 启动 Prompt（复制到新窗口）

```
[edu-cloud] Gate1-R3-Disposer | 2026-04-11 22:22:00
项目目录: C:\Users\Administrator\edu-cloud
读取本交接卡: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-handoff.md
读取 R2 报告（含 5 个新 finding 完整细节）: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan-review.md

角色: B1 F003 Plan Review R3 处置会话。Gate 1 循环第 3 轮（最后 1 轮硬额度）。不是执行会话。Tier T4。

前置声明（第一步执行）: 显式声明 T4 tier 到 SessionState
  cd /c/Users/Administrator/.claude/hooks && python -c "
  import sys; sys.path.insert(0, '.')
  import hook_lib
  ss = hook_lib.SessionState('<new_session_id>')
  ss.write('declared_tier', 'T4')
  ss.write('effective_tier', 'T4')
  ss.write('task_tier', 'T4')
  "

任务路径:

1. git status 确认当前状态，commit 未 commit 的 R2 review 内容:
   git add docs/plans/2026-04-11-f003-question-writeback-plan-review.md
   git add docs/plans/.codex-raw-plan_review-r2-20260411-221835.log
   git add docs/plans/2026-04-11-f003-question-writeback-handoff.md
   git commit -m "review: B1 F003 Plan Review R2 FAIL — 5 new findings + R3 处置交接卡"

2. 按依赖顺序处置 R2 的 5 个 finding (全部 defect_fix):
   a. R2-F002: plan.md Task 11 所有 body.exam_id 改为 SELECT Subject 派生
   b. R2-F003 + R2-F005 合并: plan.md Task 11 Step 3 抽 build_pipeline_save_answer_fn 工厂函数;
      Task 11 Step 1 S8 + Task 12 S9b 改用工厂函数;
      Contract Pack CE-002 mitigation + INV-006 test_ref 同步更新
   c. R2-F001: plan.md Task 7 Step 3 retry 改 async with db.begin_nested();
      design.md §6.1/§6.2 事务边界同步更新;
      CLAUDE.md 参考文档表可能需要追加（doc-sync-guard 硬拦截 design.md commit）
   d. R2-F004: plan.md Task 10 Step 3 V3 改用 @vue/test-utils mount(ExamDetailPage) + spy + click

3. Commit R2 处置:
   git add plan.md [design.md] [CLAUDE.md]
   git commit -m "fix(plan): B1 F003 Plan Review R2 处置 5 findings → R3 draft"

4. 跑 R3 codex-review (见 handoff.md §R3 codex-review 启动命令):
   输出到 docs/plans/.codex-f003-plan-review-r3-raw.log
   后台运行 (run_in_background), 预期 5-15 分钟
   期间可准备 R3 报告追加模板

5. 解析 R3 结果:
   - PASS 或仅 design-concern: 保存 raw log + SHA256 → 追加 plan-review.md Round 3 段 →
     写 gates.json 回执 plan_review=pass (用 gates_lib.write_receipt) →
     调 handoff-card skill 生成 docs/plans/2026-04-11-f003-question-writeback-handoff-exec.md
   - FAIL 有 code-bug/test-gap HIGH/MED: 向用户汇报 + 请求决策 (deferred/R4/推翻)
   - behavior_change 出现: 逐条单独呈现给用户确认
   - GPT 超时/不可用: gates.json 写 blocked + reason 等用户指令

6. 最终输出: Gate 1 状态 + 执行 handoff-card 路径 (若 R3 PASS) + 给用户的下一步指示

约束:
- review-templates.md PASS/FAIL 判定 + 三态 finding 模型
- Finding Type 保持 GPT 原标注，红旗模式命中 → 重分类为 behavior_change
- plan-review.md 只追加 R3 段不覆盖 R1/R2 历史
- GPT 原始输出 SHA256 必须传入 write_receipt raw_output_hash
- design.md 修改 → CLAUDE.md 必须同步 (doc-sync-guard)
- write-guard: 已有 >200 行文件禁止 Write 全量重写, 用 Edit 或先 rm 再 Write

禁止:
- executing-plans skill (执行交接的职责)
- 碰 card 模块源码 (render.js/answer_parser/answer_standardizer/styles.css/card_layout.py)
- 重跑 T2 快修 (d5cedb4/bbeeb8f/2ce070b/75922c7)
- 修改 plan-review.md R1/R2 历史段
- 删除 .codex-raw-plan_review-*.log
- 新增 behavior_change 不向用户逐条确认
- R3 FAIL 时伪装 PASS
- 手动自审绕过 GPT

关键提示:
- R2 的 5 个 finding 是 GPT 发现 Claude 在 R1 处置时自己引入的缺陷 — 事务边界/契约一致性/测试触达都被重新暴露
- R2-F003 + R2-F005 根因同一: S9b/S8 都不真经过 pipeline_router 装配 → 抽工厂函数是两全解
- R2-F001 savepoint 在 SQLAlchemy async 里用 async with db.begin_nested(), 不是 db.rollback()
- R2-F002 现有 PipelineStartRequest 只有 4 个字段 (subject_id/side/image_dir/tpl_path)
- R2-F004 ExamDetailPage.vue:471 const examId = route.params.id, L868 是调用点
- 本会话的成功定义: Gate 1 最终状态 (PASS/conditional pass/blocked) + 给用户明确的下一步指示

完成后应输出:
- Gate 1 最终状态
- 如果 PASS: 执行 handoff-card 路径 + 给用户的启动新会话 prompt (含 card WIP 阻塞前提)
- 如果需用户决策: 列出具体选项 + 每项影响 + 推荐项
```
