# W1 read_only 治理验收记录

> 日期：2026-06-12
> 窗口性质：W1 read_only 验收窗（承接 2026-06-11 深度调查 + 治理交接包）
> 本记录归档窗口：W3 governance context closeout（Yuanshou V2 合同 `yc-20260612-899ea9ce`）
> 验收对象：`feat/module-governance-repair` @ `26d98eb`（clean，与 origin 0/0 同步）

---

## 1. 验收结论：accept

W1 对以下材料和状态作出 **accept** 裁定：

1. **深度调查报告**（`docs/reviews/2026-06-11-edu-foundation-deep-investigation.md`）——
   接受为权威证据记录。三层地基判断成立：运行态 🟢 / 过程治理 🔴（两个零兜底洞）/
   结构耦合 🟡（55 边 30 环零 burn-down）。
2. **治理交接包**（`docs/reviews/2026-06-11-edu-governance-handoff.md`）——
   接受其共识固化、13 commit 处置表、待裁定清单（Q1–Q5）与窗口序列（W0–W5+）。
3. 两份材料原产自无合同调查窗口，按设计者「条件认可」裁定，经本验收后归档
   `docs/reviews/`，自归档起成为 repo 可见的权威证据真源。

## 2. Q1 角色裁定（设计者已批准）

`CODEX_STEWARD.md`（`d981e52`，无签认）与元守 V2 全局架构冲突的处置：
采纳交接包 §4-Q1 的**前一选项**——修订治理真源对齐 Yuanshou V2 分工，
不保留两份并存权威：

- **Codex/元策（Yuance）= 规划、审查、验收层**：负责证据收集、根因诊断、范围冻结、
  Planner Contract / V2 Task Contract / Executor Packet 起草，以及 range 审查与
  完成验收。**不是默认写代码通道**。
- **Claude Code = 执行者**：承担全部写操作，但**只能在 `yc start` + V2 contract
  生命周期内**执行（边界、证据、closeout 由运行时机械守卫）。
- **Yuanshou V2 = 运行边界守卫**：管执行边界、证据覆盖、closeout，不判断计划质量。
- `scripts/codex-consult-claude` **保留**为可选的只读辅助审查路径（Codex 调用的
  read-only reviewer），与受治理执行的 Claude Code 写通道是两条互不混淆的路径。
- **完成声明由 Codex/用户验收**，Claude Code 返回 Completion Return Packet，
  不自行宣布完成。

裁定理由（调查证据）：机械闸门（boundary guard / commit 闸 / evidence / closeout）
只覆盖 Claude 通道；06-09 后 Codex steward 模式试运行期恰是 receipt 空窗与窗口外
运行态操作的发生期——是通道无闸门问题，非代码质量问题。

本裁定的真源落地（W3 执行）：`AGENTS.md`、`docs/context/CODEX_STEWARD.md`、
`docs/context/GOVERNANCE_MODEL.md`、`docs/context/CLAUDE_AUX.md` 已按上述分工修订。

## 3. 13 commit review gap（`3688f32..26d98eb`）

`.review-receipts.jsonl` 最后一条 receipt = 06-07 14:40 PASS@`3688f32`；其后 13 个
commit 零 receipt（含 coze provider +2,946 行、answer-card canonical +3,634 行）。
处置表（交接包 §3，W1 验收采纳；**本 W3 窗口只登记处置路径，不跑 codex-review**，
补审在独立 review-gap 合同窗口执行）：

| 处置 | 提交 | 动作 |
|---|---|---|
| 补审 range 1（coze 线） | `41a8ced` + `c26379d` | 一次 `codex-review range` 覆盖 |
| 补审 range 2（card 线） | `dafa6f8` + `77fa6f5` + `26d98eb` | 一次 `codex-review range` 覆盖；同窗验收 canonical 真源翻转设计合理性 + scope 核查 + 漂移拒绝回归证据 |
| 合同豁免登记 | `41ae47a` | V2 合同 `yc-20260610-a2979c86` + evidence 链已覆盖，登记 waiver |
| 授权留痕 | `ebf7934` | guardian 自动 model review 关闭（背景：06-08 超时 rc=124），补一行授权记录 |
| 签认 | `d981e52` | 随本 Q1 裁定一并处置（CODEX_STEWARD 已按 V2 修订，原权力定义不再有效） |
| docs-only 豁免 | `56ccd03`/`a478b34`/`44d3e62`/`6f90994`/`47106fd` | 按惯例豁免（多为裁定持久化载体） |

## 4. answer-card canonical 真源翻转（登记设计意图）

`dafa6f8`/`77fa6f5`/`26d98eb`（tag `answer-card-canonical-usable-2026-06-12`）：
9 学科权威模板 JSON 锁入 `rendering/canonical_layouts/`；已保存布局偏离 canonical
即拒绝并回退；12 个运行时布局 JSON 移出版控。**布局真源从「用户保存优先」翻转为
「canonical 锁定 + 漂移拒绝」**——这是架构级决策，此前无 plan 文档（依据仅在
commit message/docstring），本验收补登记其设计意图。设计合理性验收与回归证据
随补审 range 2 一并处置。

## 5. Coze required_action 死开关风险（R-M3）

`AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED` 未声明进 `config.py` Settings（pydantic
`extra="ignore"` 静默吞 env）→ 文档承诺的「显式开启」路径不可达。方向安全
（永远 fail-closed），但开关本身无效。处置：登记入债务台账
（`docs/governance/debt-ledger.md` D-05），等 Q2 裁定（接线 vs 永久关闭），
本窗不改代码。

## 6. 后续窗口序列

- **W3（本窗，edu writer）**：context 语义补登记（NOW/ACTIVE_INDEX）+ Q1 真源修订 +
  W1 证据归档 + 债务台账落地（`docs/governance/debt-ledger.md`）。
- **W2（元守侧 writer，yuanshou 仓，与 edu 零冲突可并行）**：洞 A（运行态操作绑合同）+
  洞 B（receipt 绑 commit）两个机械硬闸。
- **W4（C3 复验窗，read_only + 线上凭据）**：mcu.asia 带凭据验证非默认模块缺行 403 +
  portal services 按校过滤 + 生产 SchoolModule 行完整性核查（R-H5）→ 设计者签发留痕 →
  Portal Phase 1 解锁。
- 随时穿插：review-gap 补审窗（§3 两次 range）、Q3 modular-arch push、Q4 paper-seg
  清理、guardian worker 探针（R-H1 后半）。

## 7. 证据指针

- 调查报告（归档）：`docs/reviews/2026-06-11-edu-foundation-deep-investigation.md`
- 交接包（归档）：`docs/reviews/2026-06-11-edu-governance-handoff.md`
- receipt 空窗边界：`.review-receipts.jsonl` 末条 = 06-07 14:40 PASS@`3688f32`
- 债务台账：`docs/governance/debt-ledger.md`（W3 落地）
- 风险登记：`docs/reviews/2026-06-10-foundation-stability-audit.md`（R-H1..R-L6）
