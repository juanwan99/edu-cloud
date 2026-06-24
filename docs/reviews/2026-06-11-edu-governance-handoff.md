<!-- archived: 2026-06-12 W3 governance context closeout, Yuanshou V2 contract yc-20260612-899ea9ce -->
<!-- source: /home/ops/edu-governance-handoff-to-codex-20260611.md -->
<!-- provenance: 2026-06-11 深夜 no-contract window consensus capture (设计者↔Claude↔Codex 三轮裁定); W1 read_only acceptance (docs/reviews/2026-06-12-w1-governance-acceptance.md) accepted it; this archived copy is the repo-visible evidence record. The 证据底座 referenced as /tmp/... is archived alongside at docs/reviews/2026-06-11-edu-foundation-deep-investigation.md. -->

# edu 治理交接包：调查 → Codex 规划（2026-06-11 深夜）

> 用途：Codex（元策）启动下一阶段规划的唯一输入入口。
> 证据底座：`/tmp/edu-deep-investigation-report-20260611.md`（约 250 行完整调查报告，**建议第一时间 cp 出 /tmp 防重启丢失**；设计者已裁定"条件认可——高质量草案，非权威真源，待合同窗口审查归档"）。
> 本包性质：调查之后三轮"设计者 ↔ Claude ↔ Codex 裁定"讨论的共识固化 + 待裁定清单 + 建议窗口序列。本包同样来自无合同调查窗口，**与报告一并在 W1 验收归档，归档前不是权威真源**。
> 基线：`feat/module-governance-repair` @ `26d98eb`（clean，origin 0/0）；truth-status ALL ALIGNED；db_doctor HARD=0 WARN=0；known_drift=1（studio）。

---

## 1. 已收敛共识（三方一致，不需再议）

1. **三层地基判断**：运行态🟢（已修复）/ 过程治理🔴（两个零兜底洞）/ 结构耦合🟡（55 边 30 环零 burn-down）。当前主矛盾 = 执行治理与收口纪律，不是代码。
2. **过程地基的两个零兜底洞**（事故已实际发生，机械化优先级最高）：
   - 洞 A：运行态操作（restart/rebuild/deploy）不绑合同 —— R-M2 已发生 2 次（06-10 `6f90994→c26379d`；06-11 21:19 紧跟 push 的 restart+rebuild，均无留痕）
   - 洞 B：review receipt 不绑 commit —— 06-07 后 13 提交零 receipt
   - 入口缺口（裸 Claude 能存在）有 boundary guard + doctor 兜底（本调查窗口亲测被 `PROTECTED_NO_CONTRACT` 拦截），**优先级排在 A/B 之后**
3. **治理效能病根**（数据：92 receipt 中 FINDINGS 64:PASS 7；59 提交中治理/文档类 78%；06-08/09 双线抢带宽停摆）：选题被 finding/应激驱动。改法五刀——债务台账驱动 / 审查分级（HIGH 清零、MED 限 2 轮、LOW 一律 waiver 终态）/ 加大批量摊薄窗口固定成本 / 三线并行 / 文档瘦身（状态只留语义指针）。
4. **深度仪表盘**（每窗口收口报 delta，数字不动=没深度）：开放 HIGH 数（现 3：R-H3/H4/H5）｜依赖环数（30）｜AI 工具语义错挂（~46 个挤 exam 码）｜测试基线口径（3 套）｜无 receipt 提交（13）。
5. **地基完工判据**（治理冲刺终点线，全绿即转常态开发）：① doctor 常态 READY ② commit 必带 receipt/waiver（机械强制）③ 运行态操作必在合同窗口内（机械强制）④ 环数下降且 gate 防回弹 ⑤ 基线单一真源自动刷新。预期量级：**2–3 周、约 10 个合同窗口**；设计者只出裁定/waiver/签发（每天分钟级）。
6. **分工定论**（设计者已认可）：设计者=裁定；Codex=债务台账/packet/range 审查/验收，**不直接编辑**；Claude=全部写操作，**仅在 `yc start` + 合同内**（理由：机械闸门只覆盖 Claude 通道；06-09 后 Codex steward 模式试运行期恰是 receipt 空窗与窗口外操作的发生期——非代码质量问题，是通道无闸门问题）。
7. **模块化方向三校准**：平台共享域白名单 import、业务模块间才强制 API/事件；工程量在存量拆环 burn-down 不在新规则；并行天花板在独占面（已正确列于 PARALLEL_DEVELOPMENT.md）。

## 2. 对 Codex 裁定的两处校准（已与设计者过堂，写进 W1 输入）

1. **NOW.md "过期"的修法**：HEAD 落后**不是病**（NOW.md:5-7 自声明 HEAD 用 live 命令查，正是 0.7B scope_gap 教训后的设计）。真缺口 = 06-11 工作的**语义**未登记：答题卡 canonical 治理（布局真源从"用户保存优先"翻转为"canonical 锁定+漂移拒绝"，属架构决策，无 plan 文档）+ coze provider 线。**禁止**改回"每 commit 同步 hash"的文档税模式。
2. **机械化顺序**：运行态绑合同 ≥ receipt 绑 commit > 入口强制（入口有兜底层且零实际越权写；前两者零兜底且事故已发生）。

## 3. 13 个无 receipt 提交的精确处置表（`3688f32..26d98eb`）

| 处置 | 提交 | 动作 |
|---|---|---|
| 补审（range 1：coze 线） | `41a8ced`(+2946, 22 代码文件) + `c26379d`(6) | 一次 `codex-review range` 覆盖 |
| 补审（range 2：card 线） | `dafa6f8`(2) + `77fa6f5`(+3634, 14) + `26d98eb`(26) | 一次 `codex-review range` 覆盖；同时验收 canonical 真源翻转的设计合理性 + scope 核查（是否全在 card 域）+ 漂移拒绝回归证据 |
| 合同豁免登记 | `41ae47a`（R1 运行态收口） | 有 V2 合同 `yc-20260610-a2979c86` + evidence 链，登记"合同已覆盖"waiver |
| 授权留痕 | `ebf7934`（关闭 guardian 自动 model review） | 治理能力降级开关；背景合理（model review 06-08 超时 rc=124），补一行授权记录 |
| 签认 | `d981e52`（CODEX_STEWARD.md 权力定义） | 设计者签认或随 §4-Q1 裁定一并处置 |
| docs-only 豁免 | `56ccd03`/`a478b34`/`44d3e62`/`6f90994`/`47106fd` | 按惯例豁免（多为裁定持久化载体） |

## 4. 待裁定项清单（Codex 起草提案、设计者拍板）

- **Q1（最高优先，阻塞角色定义）**：`CODEX_STEWARD.md`（d981e52，无签认）与元守 V2 全局架构（Codex=planner / Claude=executor）**冲突**。建议：修订 CODEX_STEWARD 对齐 V2（Codex 司规划审查、不直接编辑），或设计者明确签认推翻 V2——二选一，不得两份权威并存。共识 §1.6 倾向前者。
- Q2：R-M3 coze 死开关（`AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED` 未入 Settings，env 被静默吞）——接线还是裁定永久关闭。
- Q3：modular-arch-restore 分支 7 commit 唯一副本——是否授权 push 留档（一条命令；含 Plan 1 交接卡与边界 gate 资产，拆环主线的准备层在此）。
- Q4：paper-seg pip 缓存清理方式（commit 删除 206 文件 + 补 .gitignore；是否清 origin 历史另议）。
- Q5：周期性 DB 备份机制（564MB 库现仅 2 份 06-10 手动备份）+ 迁移备份轮转（R-M5）。

## 5. 建议窗口序列（供 Codex 起草 packet；批量经济学：一窗多事）

- **W0（设计者本人，分钟级，今晚）**：cp 出 /tmp 报告 → 关闭调查窗口（pid 3832839 即该窗口）→ `scripts/yc cleanup --end-stale` → `scripts/yc doctor` 确认 READY。顺手清挂死 bash 孤儿（无 tty，安全；guardian "11 进程"告警即其 pgrep 误报=R-L2 实锤）。
- **W1（read_only 验收窗，一窗五事）**：① 本报告+交接包审查归档（建议收编 `docs/reviews/`）② 按 §3 表处置 13 提交（两次 range 审查 + 三行留痕/waiver）③ 产出 NOW/ACTIVE_INDEX 语义补登记清单（按 §2.1 口径）④ Q1 角色冲突裁定提案 ⑤ 答题卡 canonical 线补设计意图登记草案。
- **W2（元守侧 writer，yuanshou 仓，与 edu 零冲突可并行）**：洞 A 运行态操作绑合同 + 洞 B receipt 绑 commit，两个机械硬闸（设计→实现→测试→live 化）。
- **W3（edu writer）**：执行 W1 清单——context 语义补登记 + 债务台账文件落地（合并 R-H/M/L + known_drift + AI 工具债 + 环 + 口径为单一台账，建议 `docs/governance/debt-ledger.md` 或 yaml）+ 基线口径统一（重启 pytest_delta，刷新 known-pytest-failures）。
- **W4（C3 复验窗，read_only + 线上凭据）**：① mcu.asia 带凭据验证非默认模块（teaching/research/study_analytics）缺行 403 ② portal services 按校过滤、禁用入口不可见不可达 ③ **生产 SchoolModule 行完整性核查（=R-H5，最易漏）** → 设计者签发留痕 → Portal Phase 1 解锁。
- **W5+（结构债主线，独占窗串行）**：拆环 burn-down 批次（每窗 2–3 环，附依赖图 diff 证据）∥（module-writer 并行）AI 工具 module 重分类批次（foundation-boundaries.md 已列为 Next batch 2）。
- 随时穿插：Q3 push（一条命令）、Q4 paper-seg 小窗、guardian worker 探针（R-H1 后半）。

## 6. 约束与红线提醒（规划时不得违反）

- **Portal 前地基冻结**：禁改 `DEFAULT_ENABLED` / module middleware（resolve_module_code/_longest_prefix_match/module_enabled_default/ROUTE_MODULE_MAP/EXEMPT_PREFIXES）/ authGuard / module-semantics 语义；studio drift 留待 Portal 真提供入口后关闭。
- **并发禁区**（独占面，writer 不得并行触碰）：router registry、权限码、菜单配置、DB 迁移链、`docs/context/**`、AGENTS.md、依赖基线——按 `PARALLEL_DEVELOPMENT.md` 分类后再开窗。
- **审查分级即日生效**：HIGH/security 清零；MED 限 2 轮；LOW 直接 waiver 终态。任一窗口审查轮次 >2 且 finding 不降级 → 停窗回报，不得无限收敛。
- 文档纪律：状态写语义指针归机器真源（receipts/gates），禁逐轮叙述；handoff 仅跨窗口写。
- 验证纪律：完成声明必须带命令+路径+范围（truth-status / db_doctor / 守卫 --check / 目标测试套件），localhost 不可验收，权威 URL = https://mcu.asia。

## 7. 关键证据指针（复核入口）

- 完整报告：`/tmp/edu-deep-investigation-report-20260611.md`（附录含全部命令级证据索引）
- 状态真源：`docs/context/NOW.md`（06-10 20:42 态）｜`docs/context/ACTIVE_INDEX.md`｜`docs/reviews/2026-06-10-foundation-stability-audit.md`（R-H1..R-L6）｜`docs/plans/2026-06-07-phase09-portal-unlock-decision.md`（C1/C2/C3+签发口径）｜`docs/plans/2026-06-10-db-migration-design.md`（runbook+回滚点）
- 结构债真源：`docs/governance/foundation-boundaries.md`（55 边/30 环、modular monolith first、AI 工具 exam 46、权限 16 vs 11）｜`docs/governance/module-semantics.yaml`（known_drift=1）
- 机器真源：`legacy receipt log`（92 条，空窗边界 06-07 14:40 PASS@3688f32）｜`docs/plans/2026-06-04-module-governance-repair-gates.json`（两 gate pass）
- 本轮统计命令：`git log --since=2026-06-05`（59 提交分类/按日）｜`git log 3688f32..HEAD`（13 提交分解）｜receipt verdict 统计（64/7/10/11）
