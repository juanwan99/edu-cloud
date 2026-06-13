# Q3 地基债务台账校准记录（W2 后）

> 日期：2026-06-13（read_only 调查）→ 2026-06-14（docs-only 持久化）
> 窗口性质：Q3 read_only 调查 → docs-only 台账校准（持久化 sid:8d106de4 结论）
> 校准窗合同：`yc-20260614-39eac63d`（docs-only，allowed scope = `debt-ledger.md` /
>   `NOW.md` / `ACTIVE_INDEX.md` / 本文件）
> 校准对象：`feat/module-governance-repair` @ `6b1bdd3`（clean，与 origin 0/0 同步）
> 承接：`docs/reviews/2026-06-12-w1-governance-acceptance.md`（W1 验收 accept）+
>   W2 元守侧机械硬闸落地

---

## 1. 校准目的

W1 验收（2026-06-12）把**过程治理层**判为 🔴——两个零兜底洞：洞 A（runtime
operation 未绑合同）、洞 B（review receipt 未绑 commit）——并把 D-01/D-02 登记为
**open（闸门未建）**。W2（元守侧 writer，yuanshou 仓）此后已落地两个机械硬闸。

本窗 Q3 read_only 调查复核三件事并把结论持久化进台账：① W2 闸门是否 live；
② 洞 A/洞 B 的历史债是否仍开放；③ 台账口径是否已过期。**本窗不改任何业务代码、
不跑 codex-review、不补审历史 commit。**

校准的核心动作：把 D-01/D-02 从单一「open」**拆成两层**——

- **机械闸门层**：W2 已 gate-built → **closed**；运行态操作与 commit 此后机械强制
  绑合同 / 带 receipt-waiver，事故面已闭合。
- **历史债层**：洞 B 的 review-gap 历史事故**仍 open**，且从 W1 记录的 **13 commit
  增至 16 commit**（W1 后新增 `3c2b7e2` / `c0057df` / `6b1bdd3`），需独立 review-gap
  合同窗口补审，**机械闸门关闭 ≠ 历史债自动清账**。

## 2. Fresh Evidence Pack（2026-06-13/14 实测）

| 证据 | 命令 | 结论 |
|---|---|---|
| 工作树基线 | `git status --short --branch` | `feat/module-governance-repair`，clean，与 origin 0/0 同步 |
| W2 运行态对齐 | `scripts/yc doctor`（yuanshou 仓） | READY `can_start=True`；`source=origin=live=c5770d0`，`dirty_source=False dirty_live=False`，health ok=12/warn=0/fail=0 |
| W2 硬闸门绿 | `pytest -q tests/v2/test_runtime_ops.py tests/v2/test_git_rules.py tests/v2/test_review_receipt.py tests/v2/test_boundary_guard_hook.py` | **96 passed**——运行态操作绑合同（洞 A）+ commit 绑 receipt（洞 B）+ git rules + boundary guard 四闸全绿、live |
| review-gap 边界 | `tail -1 .review-receipts.jsonl` | 末条 receipt = `2026-06-07T14:40:06` `engine_review` `PASS` `reviewed_sha=3688f32`，findings=0 |
| review-gap 计数 | `git log --oneline 3688f32..HEAD \| wc -l` | **16**（范围 `3688f32..6b1bdd3`） |
| D-07 三口径 | `rg 'Known pytest baseline\|12 failed\|Last updated: 2026-05-06\|22 failed' CLAUDE.md .quality/known-pytest-failures.txt NOW.md` | 仍分裂：CLAUDE.md「12 failed」(05-19) / known-failures 26 条 (05-06 后未刷新) / NOW.md「22 failed」(0.7E 实跑)——D-07 仍 open |

review-gap 16 commit 明细（`3688f32` 之后，oldest→newest）：

```
56ccd03 docs: 持久化 Phase 0.8 地基验收与 Portal 解锁裁定
a478b34 docs: 持久化 Portal Phase 1 条件解锁裁定
ebf7934 chore(guardian): disable automatic Claude model review
41a8ced feat(ai): productize coze-first agent provider
44d3e62 docs: 同步 2026-06-10 运行态地基恢复状态
6f90994 docs: 收口 DB migration 设计三文档 + 补 BUILD_DRIFT/dist 对齐要求
41ae47a fix(runtime): R1 地基接管收口 — _audit_log allowlist + 上下文同步
c26379d fix(ai): coze required_action 工具结果回传 fail-closed 门控收口
dafa6f8 fix(card): editor layout falls back to subject defaults
d981e52 docs: define Codex stewardship and parallel policy
47106fd docs: record foundation audit and worker alignment
77fa6f5 fix(card): harden answer-card canonical template governance
26d98eb fix(card): lock final answer card canonical layouts   ← W1 时台账截止点（13 commit）
3c2b7e2 docs(governance): align truth with Q1 V2 roles, archive W1 evidence, land debt ledger
c0057df data(ai-grading): refresh static grading report
6b1bdd3 fix(ai): wire Coze required_action submit setting     ← 现 HEAD（16 commit）
```

## 3. Root Cause Ladder（D-01/D-02 双层根因）

两个洞同源（治理通道无机械闸门），但事故有「机制缺失」与「历史残留」两层根因，
W2 只能闭合前者：

| 层 | 洞 A（D-01 runtime-op） | 洞 B（D-02 receipt-commit） |
|---|---|---|
| **L1 机制根因**（闸门缺失） | 运行态操作（restart/rebuild/deploy）不经 V2 合同即可执行，零兜底 | commit 落地不强制 receipt/waiver，零兜底 |
| **L1 处置** | W2 `tests/v2/test_runtime_ops.py` 硬闸 live → **closed/gate-built** | W2 `tests/v2/test_review_receipt.py` 硬闸 live → **closed/gate-built** |
| **L2 历史根因**（已发生残留） | R-M2 已实际发生 2 次（06-10 `6f90994→c26379d` 对齐；06-11 21:19 push 后 restart+rebuild），均无留痕 | 06-07 后零 receipt 的 commit 残留——**16 commit**（`3688f32..6b1bdd3`，含 coze provider +2,946 行、answer-card canonical +3,634 行） |
| **L2 处置** | 历史事故已在 NOW/audit 留痕（R-M2），无补审动作需求；机械层关闭后不再新增 → **背景化** | **仍 open**：需独立 review-gap 合同窗按 W1 §3 处置表（两次 `codex-review range` 补审 + waiver/授权留痕/签认）执行 |

**口径铁律**：机械闸门 closed（L1）只保证「此后不再发生」；历史 16 commit（L2）是
**独立债项**，不因闸门建成而自动清零。台账必须同时表达两层，避免把 L1 的 closed
误读为 L2 也已清账。

## 4. 三层地基进度（W1 → W2 后）

| 层 | W1 验收（2026-06-12） | W2 后（2026-06-13 本窗校准） |
|---|---|---|
| **运行态** | 🟢 backend/dist/nginx/worker 四面对齐 HEAD `c26379d` | 🟢 不变（运行态操作此后机械绑合同，D-01 L1 闭合反哺） |
| **过程治理** | 🔴 两个零兜底洞（洞 A / 洞 B） | **拆两层**：机械层 🟢（D-01/D-02 闸门 gate-built，96 passed）/ 历史债层 🔴（16 commit review-gap 仍 open，待独立合同补审） |
| **结构耦合** | 🟡 55 边 30 环零 burn-down | 🟡 不变（D-03 未动，W2 不触结构层；burn-down 排在 W5+） |

**净进度**：过程治理层从「整体 🔴」前进到「机械层 🟢 + 历史债层 🔴」——这是
W2 的真实 delta，不是「过程治理已转绿」。把它写成单一颜色任一侧都是失真。

## 5. 下一阶段排序

按「风险 × 可独立性」排，本窗（docs-only 校准）之后：

1. **review-gap 补审窗（最高优先，独立 read+review 合同）**：处置 D-02 L2 的 16
   commit——按 W1 §3 处置表跑两次 `codex-review range`（coze 线 `41a8ced..c26379d`
   ∪ 后续 ai 线、card 线 `dafa6f8..26d98eb` ∪ 后续）+ waiver/授权留痕/签认。
   **本窗不跑，留给带 review 授权的独立合同。**
2. **W4 Portal C3 复验窗（read_only + 线上凭据）**：D-08 解锁前置——mcu.asia 带凭据
   验证非默认模块缺行 403 + portal services 按校过滤 + R-H5 生产 SchoolModule 行
   完整性核查 → 设计者签发 → Portal Phase 1 解锁。**本窗不解锁 Portal。**
3. **D-07 测试基线统一小窗**：重启 `pytest_delta`、刷新 known-pytest-failures，
   三口径收敛为单一自动刷新真源。
4. **W5+ 结构耦合 burn-down**：D-03 拆环批次（独占窗串行，每窗 2–3 环 + 依赖图
   diff 证据）。

## 6. 证据指针

- W1 验收（承接）：`docs/reviews/2026-06-12-w1-governance-acceptance.md`（§3 = 13
  commit 处置表，本窗校准为 16 commit）
- 深度调查（证据底座）：`docs/reviews/2026-06-11-edu-foundation-deep-investigation.md`
- 风险登记：`docs/reviews/2026-06-10-foundation-stability-audit.md`（R-H1..R-L6、R-M2）
- review-gap 边界：`.review-receipts.jsonl` 末条 = 06-07 14:40 `PASS@3688f32`
- W2 硬闸门：yuanshou 仓 `tests/v2/test_runtime_ops.py` / `test_review_receipt.py`
  / `test_git_rules.py` / `test_boundary_guard_hook.py`（96 passed），`scripts/yc
  doctor` READY
- 债务台账（本窗校准落地）：`docs/governance/debt-ledger.md`
