<!-- legacy-format -->
# haofenshu S1-A 后续新 session 启动 Prompt

> 配套 `docs/plans/2026-04-24-haofenshu-s1-bank-session-handoff.md`。
> 新 session 启动时，用下方对应 prompt 替换 `{启动时间}` 占位为真实时间戳后粘贴。
> 获取真实时间：`date '+%Y-%m-%d %H:%M:%S'`。

---

## 新 session A — 执行 S1-A plan（Executor）

必须新 session；`session_guard` 硬拦同 session writing→executing。S1-C 写作可与此并行。

```
[edu-cloud] Executor | {启动时间}
读 docs/plans/2026-04-24-haofenshu-s1-bank-plan.md。

第一步 SessionState T3 声明：查当前 session_id（tail /home/ops/.claude/hooks/state/session_registry.jsonl 或看第一个 hook block 时打印的 session_id 字段；不要用历史 id 如 9169fd05/289ac325/f929d05d）。然后执行：
  python3 -c "import sys; sys.path.insert(0,'/home/ops/.claude/hooks'); from hook_lib import SessionState; ss=SessionState('<当前 session_id 前 8 位>'); ss.write('effective_tier','T3'); ss.write('task_tier','T3'); ss.write('declared_tier','T3')"

第二步：用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 推进 Task 1→2→3→4。每个 Task 完成后触发 codex-review code R1/R2，R3+ 禁止。

硬约束（ORC，违反一条即视为 plan 破坏）：
- ORC-S1A-001: migration down_revision 必须是 'a8c7d2e4f135'（2026-04-24 R2 后基线漂移修正锚点；禁 'f7a3b2c1d456' 分支根 / 禁 '36e25241e55d' plan 初稿时 head — 已被 a8c7d2e4f135 取代）
- ORC-S1A-002: alembic/env.py 和 src/edu_cloud/api/app.py 零改动（已含 bank 注册）
- ORC-S1A-003: bank_questions 现有字段只加不改（tags JSON / bloom_level String(20) 不动）
- ORC-S1A-004: migration 用 sa.JSON()，禁 postgresql.JSONB

Gate G1-S1A-1~6 全绿后 Task 4 Step 4.3 写 handoff.md 交接 S1-C。handoff 模板已压到 13 行（plan Step 4.3），不要加行。

7 天 deadline：2026-05-01 前完成所有 Task，否则 haofenshu-s1-bank/plan_review 的 manual_override 过期。
```

---

## 新 session B — 写 S1-C haofenshu-s1-admin plan（Planner）

**前置状态（2026-04-24T19:31 后更新）**: S1-A 已闭环 — plan_review=manual_override(7d) + code_review_batch1=PASS。S1-A T2 migration slug 实测为 `a88094ee4ea6`，链首 `down_revision=a8c7d2e4f135`。本 B 启动时 S1-C 需要以 `a88094ee4ea6` 作为 linear chain 第 2 环的 down_revision。

```
[edu-cloud] Planner | {启动时间}
按 parent design §4.1 deliverable 1.3/1.4/1.5 写 S1-C plan：
- 1.3 grades 表新增 + Class.grade_id FK（Class 表加 FK，遵守 ORC 守旧字段不动）
- 1.4 teaching_plans 表骨架（仅 schema，不含 FK 到 lesson_plans 等未建表）
- 1.5 PaperAccessLevel 枚举常量
- 闭环 TD-S1A-002：补 bank_questions.grade_id FK constraint（batch_alter_table + create_foreign_key）

F009（subject_code vs course_code 参数语义）不归本 S1-C，归 S1-D（StudentProfileView VO）。

第一步 SessionState T3 声明（同 session A 指引）。

第二步：用 superpowers:writing-plans。linear chain 第 2 环 down_revision='a88094ee4ea6'（S1-A T2 migration slug 实测，commit a3731d6），实施前建议跑一次 `alembic heads` 验证当前仍是 `a88094ee4ea6 (head)` 确认无漂移（若已被后续 session 推进，取最新 head 为准）。

Contract Pack 严格按 ~/.claude/config/contract-pack-schema.md 真源（S1-A R2 曾因此 contested，不要重犯）：
- invariants: id / statement / verification(existing_test|pending_test|uncovered) / test_ref（仅 existing_test）
- counter_examples: id / scenario / tests_that_still_pass / mitigation
- risk_modules: module / reason（不是 path/risk/mitigation）
- test_debt: item / reason / deadline（YYYY-MM-DD，不是"S1-D 会话"之类）

ORC 至少 3 条（linear chain 衔接 / Class 表加 FK 守旧字段不动 / teaching_plans 骨架不含外部 FK）。

commit plan 后走 codex-review plan R1；R2 FAIL → manual_override 或拆更细 topic，禁 R3+。

输出 plan 文件: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md。

7 天 deadline：2026-05-01 前 S1-A/B/C/D 全 R1 PASS 关闭 parent haofenshu-s1-l1-data-layer 的 manual_override。
```

---

## 通用禁区

- **R3+ 禁止**：`gates_lib.write_receipt(round>=3, status!='blocked')` 直接 raise ValueError；R2 FAIL → 拆 topic / WONTFIX / manual_override 三选一
- **session_guard**：同 session 禁 writing-plans + executing-plans
- **baseline 基线**（`pytest --tb=no -q` 实测 2026-04-24T11:04:27）：2064 通过 / 22 失败 / 1 错误 / 23 跳过 —— CLAUDE.md L87 + plan frontmatter L2 双真源已统一；S1-A Gate G1-S1A-5 要求通过数 ≥ 2073（+9 新测试）
- **22 失败 + 1 错误既有测试债**：pre-S1-A 状态，独立 T3 调研议题，不在 S1-A/B/C/D scope
- **Stop hook 软提醒**：其他 3 个历史 topic gate（conduct-roadmap / ai-grading-b-end / kg-phase1）按方案 A 不处置，可忽略
- **7 天双 manual_override**：2026-04-24 起至 2026-05-01；过期则 `check_gate` False 硬拦后续 skill
