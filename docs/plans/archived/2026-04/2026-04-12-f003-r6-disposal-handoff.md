---
type: handoff
created: 2026-04-12 07:15:00
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan.md
plan_review: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan-review.md
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-gates.json
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-state.json
r5_raw_log: C:\Users\Administrator\edu-cloud\docs\plans\.codex-f003-plan-review-r5-raw.log
tier: T4
---

# 交接卡：B1 F003 Plan Review R6 处置 → Gate 1 收尾（第三次扩展）

**Tier**: T4 — **本会话不是执行会话**。Gate 1 循环 R1(6)→R2(5)→R3(5)→R4(5)→R5(2)。用户授权第三次扩展 R6。新窗口任务：修 R5 的 2 个 finding → 跑 R6 → 解析结果。

**前置阻塞（执行会话启动前必须确认，与本会话无关）**: card 模块 WIP 小微排版 v2 视觉验收回主线。本会话**不碰 card 模块源码**。

## Round 循环状态

| Round | 结果 | finding | commit |
|-------|------|---------|--------|
| R1 | FAIL | 6 | `406af8b` 处置 |
| R2 | FAIL | 5 | `f4053b9` 处置 |
| R3 | FAIL | 5 | `0c7c0c4` 处置 |
| R4 | FAIL | 5 | `40da245` 处置 |
| R5 | **FAIL** | **2** (1 HIGH / 1 MED) | **待处置** |
| R6 | pending | - | - |

R5 raw log SHA256: `000335e00b33911b15939eb1ae7bda320b1fe945e0b310e1fa6894bcd3623013`

## R5 的 2 个 Finding（完整细节在 plan-review.md §Round 5）

### R5-F001 MED code-bug — 锚点段字节级重写

**根因**：plan.md 头部"现实代码锚点"段 CR-1..CR-4 不是字节级原文，混入 `...` 省略、改写注释、HTML 注释标签。GPT 要求用源码原文替换 4 个 CR 代码块。

**修复方向**：
- 用 `Read` 工具分别读取下面 4 个文件的**指定行范围**
- 字节级原样粘贴进 CR 代码块（保留原注释、保留原 docstring、保留空行）
- 禁止 `...` 省略符
- 禁止改写或新增注释
- 禁止插入 HTML 注释标签
- 代码块**外部**的解释性文字可以保留，但代码块**内部**必须是纯原文
- CR-4 `api/subjects.js` 全文 5 行，已经是原文，无需改动

**具体源文件和行范围**：

| 锚点 | 源文件 | 行范围 | 目标 plan 位置 |
|------|--------|--------|----------------|
| CR-1 | `C:\Users\Administrator\edu-cloud\tests\conftest.py` | L46-L102 | plan.md L43-L85 的代码块 |
| CR-2 | `C:\Users\Administrator\edu-cloud\src\edu_cloud\modules\scan\pipeline_router.py` | L25-L29（请求模型）+ L90-L181（start_pipeline 函数） | plan.md L109-L182 的代码块 |
| CR-3 | `C:\Users\Administrator\edu-cloud\frontend\src\pages\ExamDetailPage.vue` | L242-L263（发布按钮）+ L446-L471（import 和 examId）+ L652-L662（loadExam）+ L848-L881（handlePublishCard） | plan.md L199-L259 的代码块 |
| CR-4 | `C:\Users\Administrator\edu-cloud\frontend\src\api\subjects.js` | L1-L5（全文） | plan.md 对应段（已对齐，检查即可） |

**注意**：CR-3 是 Vue 文件，但源码是 HTML 模板 + `<script setup>` — 原样粘贴时要区分模板段和脚本段。不要插入 `<!-- L446-447 -->` 这种说明标签。如果必须标注位置，写在代码块外面的解释段落。

### R5-F002 HIGH test-gap — S8d spy 改用 tracked_factory

**根因**：R4-F004 修复方案用了 `spy_factory.spy_return`，但该属性在 Python 3.11.9 的 `unittest.mock.MagicMock` 上**不存在**。GPT 实测 `patch.object(..., wraps=...)` 返回的 MagicMock 没有 `spy_return`，断言会 `AttributeError`。

**修复方向**：不依赖 `spy_return`。改用**自定义 tracked_factory + 外部列表捕获**：

```python
# S8d-a 的正确模板
from edu_cloud.modules.scan import pipeline_router as pr_mod

original_factory = pr_mod.build_pipeline_save_answer_fn
factory_returns = []  # 外部列表捕获真实返回闭包

def tracked_factory(**kwargs):
    result = original_factory(**kwargs)
    factory_returns.append(result)
    return result

captured_kwargs = {}

async def fake_run_pipeline(**kwargs):
    captured_kwargs.update(kwargs)

with patch.object(
    pr_mod, "build_pipeline_save_answer_fn",
    side_effect=tracked_factory,     # ← 用 side_effect 不用 wraps
) as spy_factory, \
     patch("edu_cloud.modules.scan.pipeline_service.is_running", return_value=False), \
     patch("edu_cloud.modules.scan.pipeline_service.list_scan_images",
           return_value=[...]), \
     patch("edu_cloud.modules.scan.pipeline_service.run_pipeline",
           side_effect=fake_run_pipeline):
    # 调 POST /api/v1/scan/pipeline/start
    resp = await client.post(...)
    import asyncio
    await asyncio.sleep(0.05)

# 断言 1: spy 被调用
assert spy_factory.called
assert spy_factory.call_count == 1

# 断言 2: spy call_args 含正确 regions
call_kwargs = spy_factory.call_args.kwargs
assert isinstance(call_kwargs["regions"], list)
assert call_kwargs.get("exam_id") == fx["subject"].exam_id

# 断言 3 (R5-F002 核心 identity): 工厂真实返回值被捕获
assert len(factory_returns) == 1, "tracked_factory 应被调一次"

# 断言 4 (identity 透传): run_pipeline 收到的 save_answer_fn 是工厂返回值本身
assert captured_kwargs["save_answer_fn"] is factory_returns[0], (
    "run_pipeline 收到的 save_answer_fn 必须 identity-equal 于工厂真实返回值 —— "
    "哑闭包 / 另造 closure / None placeholder 都会在此失败"
)
```

**关键技术点**（新会话 reviewer 必须理解）：
- `side_effect=tracked_factory` 让 patched 对象在被调时运行 tracked_factory（tracked_factory 内部调真工厂并捕获返回值）
- `spy_factory.called` / `spy_factory.call_args` / `spy_factory.call_count` 这些属性**在 side_effect 模式下仍然工作**（unittest.mock 标准行为，无需 spy_return）
- `factory_returns[0]` 是真工厂的真实返回值，与 patched 对象的返回值**同一对象**（side_effect return value 会被 MagicMock 透传）
- `captured_kwargs["save_answer_fn"] is factory_returns[0]` 是**对象 identity 比较**——只有 `start_pipeline` 把真工厂的返回值直接传给 `run_pipeline` 才通过

**禁止模式**：
- ❌ `spy_factory.spy_return`（Python 3.11 不存在，AttributeError）
- ❌ 退回 `callable(save_answer_fn)` 或 `is not None`（R4-F004 禁止的弱断言）
- ❌ `patch.object(..., wraps=original)` 然后指望 `spy_return` 自动填充（wraps 模式下 spy 本身也可能触发各种行为，不推荐）
- ❌ 另造 closure 然后 `is` 断言（必然失败，测试无意义）

**覆盖范围**：S8d-a（DB 分支）和 S8d-b（tpl_path 分支）**两个测试函数**都必须改用 tracked_factory 模式。

## 修复路径（按此顺序）

1. **R5-F001**（机械操作，先做）：
   - Read 工具读 4 个源文件的指定行范围
   - Edit 工具字节级替换 plan.md 的 4 个 CR 代码块
   - 检查无 `...` / 无改写注释 / 无 HTML 注释标签

2. **R5-F002**（改测试代码）：
   - Grep `spy_factory.spy_return` 定位所有引用（plan.md 里只有 S8d-a / S8d-b 的两个测试函数）
   - 整段替换为 tracked_factory 模式
   - 同步更新 Task 11 测试契约表和审查清单（删除 `spy.spy_return` 描述，改为 `factory_returns` + identity）

3. **Contract Pack 同步**：INV-009 的 note 字段可能需要更新（提到 tracked_factory 方案）

4. **CLAUDE.md 参考文档表行**：`~/CLAUDE.md` 的 B1 F003 行更新 R5 → R6 状态

5. **Commit**：一次 commit 涵盖上述 plan.md + CLAUDE.md

6. **R6 codex-review**：见下方启动命令

## R6 codex-review 启动命令

参照前面 R4/R5 的 prompt 模板，重点让 GPT 核实 R5-F001 / R5-F002 两条修复：

```bash
source ~/.bashrc && source ~/.claude/hooks/env_init.sh 2>/dev/null

export PLAN_FILE="C:/Users/Administrator/edu-cloud/docs/plans/2026-04-11-f003-question-writeback-plan.md"
export DESIGN_FILE="C:/Users/Administrator/edu-cloud/docs/plans/2026-04-11-f003-question-writeback-design.md"
export PROJECT_CLAUDE_MD="C:/Users/Administrator/edu-cloud/CLAUDE.md"
export PROJECT_DIR="C:/Users/Administrator/edu-cloud"

cat > /tmp/codex-plan-review-prompt.tpl <<'PROMPT_EOF'
You are a senior architect reviewing an implementation plan — **Round 6 of Plan Review**.

Read these files:
1. ${PLAN_FILE} — Round 6 draft
2. ${DESIGN_FILE}
3. ${PROJECT_CLAUDE_MD}

**Round history (do NOT re-report resolved findings):**
- R1(6)→R2(5)→R3(5)→R4(5)→R5(2). All prior findings resolved except R5-F001 MED + R5-F002 HIGH.
- User approved 3rd extension (R6) to fix the remaining 2 findings.

**R5 fix claims to verify (this commit):**

1. **R5-F001 resolved**: CR-1..CR-4 anchor code blocks rewritten with byte-level-accurate source excerpts. No `...`, no rewritten/added comments, no HTML comment tags inside code blocks. Source files:
   - CR-1 ← tests/conftest.py:46-102
   - CR-2 ← pipeline_router.py:25-29 + 90-181
   - CR-3 ← ExamDetailPage.vue:242-263 + 446-471 + 652-662 + 848-881
   - CR-4 ← api/subjects.js:1-5
   **Verify byte-level match** by diffing plan's CR blocks against actual source files.

2. **R5-F002 resolved**: S8d-a and S8d-b both replaced `spy_factory.spy_return` with `factory_returns` external list + `side_effect=tracked_factory` pattern. Assertions: `spy_factory.called` + `spy_factory.call_args.kwargs` + `len(factory_returns) == 1` + `captured_kwargs["save_answer_fn"] is factory_returns[0]`. No `spy_return` references remain. **Verify** the identity assertion pattern matches unittest.mock semantics under Python 3.11 (tracked_factory return value propagates through MagicMock side_effect to captured_kwargs).

**Your job in R6:**
1. For R5-F001: byte-level diff plan CR blocks against source files. Any single-character deviation → defect_fix.
2. For R5-F002: verify the new S8d pattern is runnable under Python 3.11. Mental-execute the code path: does `side_effect=tracked_factory` make spy_factory.called work? Does tracked_factory's return value correctly propagate as the patched object's return?
3. Independently check for new holes introduced by R5 dispositions.
4. Do NOT re-report R1-R5 resolved findings.
5. R6 is the user's 3rd and likely final extension. If R6 still FAILs, user must decide accepted-risk / design abandonment.

**Review checklist:** A 自洽性 / B 代码库对齐 (anchor byte-level) / C 架构适配 / D 完整性 / D+ 测试契约质量 / E 风险评估 / F Contract Pack 完整性

**审查规范（必读）：** ~/.claude/rules-t3/review-templates.md 各锚点段。

Output structured findings: ID / Severity / Category / Type / Before-behavior / After-behavior / Evidence (file:line) / Impact / Repair hypothesis.

Write in Chinese. Conclude with explicit **PASS** or **FAIL**.
PROMPT_EOF

envsubst < /tmp/codex-plan-review-prompt.tpl > /tmp/codex-plan-review-prompt.txt

cd "C:/Users/Administrator/edu-cloud" && codex exec -s danger-full-access -C "C:/Users/Administrator/edu-cloud" "$(cat /tmp/codex-plan-review-prompt.txt)" > "C:/Users/Administrator/edu-cloud/docs/plans/.codex-f003-plan-review-r6-raw.log" 2>&1 &
```

预计 5-15 分钟出结果。用 `run_in_background: true` 跑，等通知。

## R6 结果分支

| R6 结果 | 处置路径 |
|---------|---------|
| **PASS** | 写 plan-review.md Round 6 段 → gates.json `plan_review=pass round=6 report_path+SHA256` → 调 `handoff-card` skill 生成**执行**交接卡 `-handoff-exec.md` → 本会话结束，汇报用户 |
| **FAIL 仅 LOW/suggestion** | 同 PASS 流程（不阻塞） |
| **FAIL 仍有 HIGH/MED code-bug/test-gap** | **必须向用户汇报请求决策**（第四次）：(a) R7 循环（非常不推荐，4 轮扩展后流程成本远大于价值）(b) accepted-risk 降级 — 具体说明哪条风险可接受 (c) 推翻方案 D 重新 design |
| **behavior_change finding** | 逐条单独呈现给用户确认（L017）|
| **GPT 超时/不可用** | gates.json 写 `blocked` + reason，等用户指令 |

## 必读文件清单（按此顺序）

1. 本交接卡（你正在读）
2. `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan-review.md` §Round 5 段（含 R5-F001 / R5-F002 完整 finding + GPT 的 repair hypothesis 草稿）
3. `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan.md` 当前状态（尤其是"现实代码锚点"段 L35-260 和 Task 11 Step 1b 的 S8d-a / S8d-b 测试代码）
4. 锚点源文件（为 R5-F001 重写做准备）：
   - `C:\Users\Administrator\edu-cloud\tests\conftest.py` L46-102
   - `C:\Users\Administrator\edu-cloud\src\edu_cloud\modules\scan\pipeline_router.py` L25-29 + L90-181
   - `C:\Users\Administrator\edu-cloud\frontend\src\pages\ExamDetailPage.vue` 相关片段
   - `C:\Users\Administrator\edu-cloud\frontend\src\api\subjects.js` 全文

## 约束与偏好（只记增量，未在 design/plan 记录的）

### 用户偏好

1. **defect_fix 批量处置**：R6 若 PASS / 仅 LOW，无需逐条确认
2. **behavior_change 必须逐条**：L017 硬要求（R6 预期无 behavior_change）
3. **短回复文化**："a/b/c"、"可以"、"开始" 表示接受
4. **真值裁判权在用户**：禁止伪装 PASS；禁止 accepted-risk 不说理由
5. **Finding 收敛信号**：R5 降到 2 条表明流程在收敛，用户愿意给 R6 机会但不会无限扩展
6. **本会话一定不碰 card 模块源码**（小微排版 v2 WIP 冲突区，归属另一个交接）

### 技术限制 / 环境 quirks

1. **Python 版本锁定 3.11.9**：`pyproject.toml` 指定 Python 3.11。`unittest.mock.MagicMock` 的 `spy_return` 属性**不存在**，必须用 `tracked_factory` + 外部列表模式（R5-F002 根因）
2. **SQLite in-memory 单 connection**：conftest.py `db` fixture 的 in-memory SQLite 无法模拟真实跨 session race；SAVEPOINT flush 拦截不稳定（S7c test_debt 原因）
3. **client fixture monkey-patch 语义**：`edu_cloud.database.async_session` 必须通过 `import ... as db_mod` + 运行时查找才能被 patch 到（R4-F001 根因）
4. **AsyncSession.expire_all() 是同步 API**：不 await（R4-F002 根因）
5. **codex exec PowerShell 乱码**：Windows tee 日志可能有 gbk 乱码，但 GPT 的 MCP filesystem 读文件不受影响，verdict 可信
6. **SessionState declared_tier 显式声明**：调 T3/T4 skill 前必须手动写到 `~/.claude/hooks/state/{session_id[:8]}_state.json`：
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
7. **doc-sync-guard 硬拦截**：修改 design.md 时必须同步更新 `edu-cloud/CLAUDE.md`。本次不改 design.md，所以只需改 `CLAUDE.md` 参考文档表行
8. **write-guard 200 行阈值**：plan.md 已 >3000 行，禁止 Write 全量重写，必须 Edit 增量；本交接卡 ~300 行，若要改也必须 Edit 或先 rm 再 Write

### 禁止事项

- ❌ 启动 `executing-plans` skill（那是真正执行会话的职责，本会话是 Plan Review 处置）
- ❌ 碰 card 模块源码（render.js / answer_parser.py / answer_standardizer.py / styles.css / card_layout.py）
- ❌ 改 T2 快修区（B2/B3a/B6a/B6c 已 commit：`d5cedb4` / `bbeeb8f` / `2ce070b` / `75922c7`）
- ❌ 修改 plan-review.md R1/R2/R3/R4/R5 历史段（只追加 R6 段）
- ❌ 删除任何 `.codex-raw-plan_review-*.log` / `.codex-f003-plan-review-*.log`
- ❌ 写"R6 手动自审通过"绕过 GPT（GPT 不可用必须 blocked）
- ❌ R6 新增 behavior_change 而不向用户逐条确认
- ❌ R6 FAIL 时伪装 PASS
- ❌ 把 R5-F001 的锚点改写成"更清晰"的版本（必须字节级原文）
- ❌ R5-F002 用 `spy_return` 或弱断言（`callable` / `is not None`）

## 启动 Prompt（复制到新窗口）

```
[edu-cloud] Gate1-R6-Disposer | 2026-04-12 07:15:00
项目目录: C:\Users\Administrator\edu-cloud
读取本交接卡: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-f003-r6-disposal-handoff.md
读取 R5 审查报告（含 2 个 finding 完整细节 + 修复草稿）:
  C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-plan-review.md（§Round 5 段）

角色: B1 F003 Plan Review R6 处置会话。Gate 1 第 6 轮（用户第 3 次扩展）。不是执行会话。Tier T4。

前置声明（第一步执行）: 显式声明 T4 tier 到 SessionState（见交接卡 §技术限制 第 6 条）。
  先 `ls -lt ~/.claude/hooks/state/ | head -5` 找出当前 session 的 state 文件（最新更新的非 blk_/unknown/test- 开头）
  用 session_id 前 8 位写入 declared_tier/effective_tier/task_tier=T4 + current_topic=f003-question-writeback

任务路径（按此顺序）:

1. 读取现实源文件（为 R5-F001 锚点重写做准备）:
   - C:\Users\Administrator\edu-cloud\tests\conftest.py 的 L46-102
   - C:\Users\Administrator\edu-cloud\src\edu_cloud\modules\scan\pipeline_router.py 的 L25-29 + L90-181
   - C:\Users\Administrator\edu-cloud\frontend\src\pages\ExamDetailPage.vue 的 L242-263 + L446-471 + L652-662 + L848-881
   - C:\Users\Administrator\edu-cloud\frontend\src\api\subjects.js 全文 L1-5

2. R5-F001 机械修复: 用 Edit 工具字节级替换 plan.md 的 CR-1/CR-2/CR-3 代码块（CR-4 已对齐检查即可）
   - 禁止 ... 省略符 / 改写注释 / 新增 HTML 注释标签
   - 保留源文件原有注释 / docstring / 空行
   - 说明性文字放代码块外部

3. R5-F002 修复 S8d 测试: Grep 定位所有 spy_return 引用（在 Task 11 Step 1b 的 S8d-a / S8d-b 两个测试函数内）
   - 整段替换为 tracked_factory + 外部列表 factory_returns 模式（模板见交接卡 §R5-F002 修复方向）
   - 断言: spy_factory.called + spy_factory.call_args.kwargs + len(factory_returns)==1 + captured["save_answer_fn"] is factory_returns[0]
   - 同步更新 Task 11 测试契约表和审查清单, 删除 spy.spy_return 描述改为 factory_returns + identity

4. Contract Pack 同步: INV-009 的 note 字段更新提到 tracked_factory 方案（若原 note 提了 spy_return）

5. CLAUDE.md 同步: C:\Users\Administrator\edu-cloud\CLAUDE.md 参考文档表 B1 F003 行更新 R5 FAIL → R6 pending

6. Commit R5 处置:
   git add CLAUDE.md docs/plans/2026-04-11-f003-question-writeback-plan.md
   git commit -m "fix(plan): B1 F003 Plan Review R5 处置 2 findings → R6 draft"

7. 跑 R6 codex-review（见交接卡 §R6 codex-review 启动命令）:
   后台运行, 输出到 docs/plans/.codex-f003-plan-review-r6-raw.log
   等通知（不轮询）

8. 解析 R6 结果:
   - PASS 或仅 LOW: 保存 raw log + SHA256 → 追加 plan-review.md Round 6 段 →
     写 gates.json 回执 plan_review=pass round=6 (用 gates_lib.write_receipt) →
     调 handoff-card skill 生成 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-f003-question-writeback-handoff-exec.md（执行交接卡，给真正的 T4 执行会话用）
   - FAIL 有 HIGH/MED: 向用户汇报 + 请求决策（第 4 次，accepted-risk / R7 / 推翻）
   - behavior_change 出现: 逐条单独呈现给用户确认
   - GPT 超时/不可用: gates.json 写 blocked + reason 等用户指令

9. 最终输出: Gate 1 状态 + 执行 handoff-card 路径（若 R6 PASS）+ 给用户的下一步指示

约束:
- review-templates.md PASS/FAIL 判定 + 三态 finding 模型
- Finding Type 保持 GPT 原标注, 红旗模式命中 → 重分类为 behavior_change
- plan-review.md 只追加 R6 段不覆盖历史
- GPT 原始输出 SHA256 必须传入 write_receipt raw_output_hash
- design.md 修改 → CLAUDE.md 必须同步 (doc-sync-guard) — 本次不改 design.md
- write-guard: plan.md >3000 行禁止 Write 全量重写, 用 Edit

禁止（完整列表见交接卡 §禁止事项）:
- executing-plans skill
- 碰 card 模块源码
- 改 T2 快修区
- 修改 plan-review.md R1-R5 历史段
- 删除 .codex-raw-*.log
- spy_return 或弱断言
- 锚点段改写
- R6 FAIL 时伪装 PASS
- 手动自审绕过 GPT
- 新增 behavior_change 不单独确认

关键提示:
- R5 只剩 2 条 finding, 流程在收敛但还没到 PASS
- R5-F001 是纯抄写（从源码原文粘贴）, 无设计讨论
- R5-F002 是已知 Python 3.11 unittest.mock API 限制, GPT 已给完整修复模板
- 本会话目标: Gate 1 最终状态（PASS / blocked / 仍需用户决策）+ 给用户明确下一步
- 本会话不是执行会话 — 不碰 card 模块 / 不跑业务测试 / 只改 plan.md 和 CLAUDE.md
- 如果 R6 再 FAIL, 诚实汇报不伪装, 让用户决策 accepted-risk / R7 / 推翻

完成后应输出:
- Gate 1 最终状态
- 如果 PASS: 执行 handoff-card 路径 + 给用户的启动新会话 prompt（含 card WIP 阻塞前提）
- 如果需用户决策: 列出具体选项 + 每项影响 + 客观评估
```
