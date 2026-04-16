# edu-cloud 项目全景状态盘点

> 创建: 2026-04-13 23:53:30
> 作者: Claude (Opus 4.6) — Planner 角色
> 用途: 接替 module-governance Planner 的系统性梳理产物；**B 深度版**调研
> 方法: 6 维并行调研（docs/plans/ 扫描 + 近 50 commits + 后端模块 + 前端 pages + agent_findings DB + 全量测试），Planner 交叉核验后综合

---

## §0 方法与数据来源

本盘点由 5 个独立 Explore agent 并行产出初稿，Planner 做了关键事实核查（L013 反向防御）：
- agents 对 haofenshu-phase1 状态表述有出入（agent 4 说"待 Executor"、agent 6 说"Batch 2 完成"），以 `gates.json` 为**唯一权威**
- agent 1 列出的 phase1b/1c/1d/2.1/2.2 历史 topic 确实存在于 docs/plans/ 根目录，但其 state.json 陈旧
- 全量测试由后台 pytest 跑完（22:42），5 failures 定位到 3 文件

引用文件均已读实物，非 agent 叙述。

---

## §1 项目宏观状态（一句话）

edu-cloud 后端 20 模块 / 前端 38 pages（+ frontend-nuxt/ 骨架）/ PostgreSQL 79 表 / 1983 tests pass + 5 pre-existing fail；最近一周重心：**haofenshu-phase1 / knowledge-graph-phase1 / conduct-module / module-governance** 四条并行线；三条已收尾，一条（haofenshu Batch 2 code review）待发起。

---

## §2 测试与 drift

### 2.1 全量测试（pytest）

- **1983 passed / 5 failed**（22:42 秒）
- CLAUDE.md 声明 1976 — **+7 test drift**（应更新）
- 5 failures 全部 pre-existing，来自 3 个文件：

| 文件 | 失败测试 | 推测原因（未深查） |
|------|---------|-----------|
| `tests/test_ai/test_tool_access_fail_closed.py` | `test_no_capability_record_rejects` / `test_partial_capability_match_rejects` | fail-closed 行为测试 — 需 diagnose |
| `tests/test_api_exam/test_pipeline_save_answer.py` | `test_S8a_factory_orphan_logs_warning` | orphan 日志 warning 检查 — 可能 logger 配置漂移 |
| `tests/test_services_exam/test_scan_pipeline.py` | `TestBarcodeFallbackObservability::test_barcode_exception_logs_warning` + `test_barcode_returns_none_logs_fallback` | barcode fallback 日志可观测性 |

**建议**：发起一个 T2 bug fix 批次定位这 5 failures 的根因（"pre-existing"不构成接受理由——可能是迁移期间 logger 配置/mock 不稳定导致的假阳性，也可能掩盖真 bug）。

### 2.2 结构 drift 清单

| 维度 | CLAUDE.md 声明 | 实际 | drift |
|------|---------------|-----|------|
| 后端模块数 | 19 | **20**（含 `menu/`） | +1（menu 漏写） |
| 后端测试数 | 1896（conduct 后更新） / 1976 | **1983** | +7 |
| Python 路由数 | 223 | ~126（`@router.*` grep）| 统计口径不同（含 re-export stub 可能） |
| 前端 pages (.vue) | 未直接声明 | **38**（含 parent/ 8 + conduct/ 9 + 根 21） | — |
| 前端路由 | 44 | 43-45（嵌套 children 计数语义） | ±1 |
| `frontend-nuxt/` pages | 声明 "初始化阶段" | 3 pages (index/login/home) + layouts + stores + composables | 骨架完成符合声明 |
| 模块 MODULE.md | 2/19 | **2/20 = 10%** | 分母差 1 |

---

## §3 Topic 状态（按 gates.json 权威）

### 3.1 已收尾 topic（design [实现完成] + gates 全 PASS）

最近（近两周）：

| Topic | Design 日期 | 收尾日期 | 主要产物 |
|-------|------------|---------|---------|
| f003-question-writeback | 2026-04-11 | 2026-04-11 | publish_service.py + 原子事务 |
| grading-dispatch | 2026-04-12 | 2026-04-12 | GradingDispatchPage + 阶段聚合 |
| conduct-module | 2026-04-12 | 2026-04-13 | 22 Task / AES-256-GCM / parent+admin |
| knowledge-graph-phase1 | 2026-04-13 | 2026-04-13 | Graph API v2 + edge review_status + 审查工作台 |
| migration-gate-repair | 2026-04-13 | 2026-04-13 | 6 migration 双方言兼容 |
| module-governance | 2026-04-13 | 2026-04-13 | MODULE.md 纲领 + aggregate + guard |

更早的完成 topic（2026-04-10 前）涵盖：teacher-workbench (Phase 2 / 2.5) / knowledge-graph-restructure / scan-integration / scan-pipeline / bio-demo / adaptive-learning / analytics-report / agent-runtime / agent-evolution / edu-agent / memory-system (Phase 2) 等 — 详情见项目 CLAUDE.md「已完成设计」段（单一真源，不重复）。

### 3.2 未收尾 topic（重点）

| Topic | 卡在哪 | 下一步 | 优先级 |
|-------|-------|-------|--------|
| **haofenshu-phase1** | `code_review_batch2` + `code_review_batch3` 待审查；Batch 2 工作 T4-T9（frontend-nuxt T4-T9: init / stores / useApi / navigation / layouts / pages）commit 08d86f0..674cd99 **已落盘** | **发起 GPT code_review_batch2** | **HIGH**（已经是 blocker） |

无其他卡死的 topic。

### 3.3 历史状态 drift（state.json 陈旧）

以下 topic design.md 已标 [实现完成]，但 state.json 仍显示 pending（agent 1 误判为"未收尾"，实际是状态同步漏做）：

- `2026-03-29-phase1b-base-info`
- `2026-03-30-phase1c-permission-engine`
- `2026-03-30-phase1d-agent-instantiation`
- `2026-03-30-phase2.1-exam-workflow`
- `2026-03-30-phase2.2-homework-system`

**建议**：T1 清理批次，把 state.json 全部 task status 改为 completed（或直接删除 state.json，因为 design [实现完成] 是权威标记）。

### 3.4 孤立/异常文档

| 文件 | 异常 | 处置 |
|------|-----|-----|
| `docs/plans/.conduct-fix-intent-F002-F003.md` | 隐藏文件未归档 | 移入 archived/ 或显式保留 |
| `docs/plans/.conduct-fix-intent-F002r3-N001.md` | 同上 | 同上 |

### 3.5 已识别 deferred / accepted-risk

| ID | Topic | Severity | Deadline | 内容 |
|----|-------|---------|---------|------|
| R2-NEW-02 | module-governance | LOW design-concern | 2026-05-15 | `_checkout_staged_index` 全仓 2.75s/commit，优化为 scoped checkout |
| F001 Alembic SQLite | conduct-module | — | haofenshu-phase1 Migration Gate | **已在 migration-gate-repair 处置**（已完成） |
| F003 conduct scope | grading-dispatch | — | conduct 模块 | **已在 conduct-module 处置**（已完成） |

---

## §4 最近一周工作重心（近 50 commits）

| 日期 | 主题 | 关键产物 |
|------|------|---------|
| 2026-04-13 (今天) | **5 topic Gate 收敛** + module-governance 收尾 | knowledge-graph-phase1 batch2 PASS / module-governance R2 PASS / conduct-module R3 PASS / haofenshu batch1 R2 PASS / **haofenshu batch2 T4-T9 frontend-nuxt 落盘**（待审） |
| 2026-04-12 | conduct + grading-dispatch 实现 | conduct 前后端完整 / GradingDispatchPage / haofenshu plan R1 FAIL 处置 |
| 2026-04-11 | f003-question-writeback 多轮 Plan Review | R1 FAIL → R7 PASS（7 轮 Plan Review，R6 才过） |

**超级并行迹象**：2026-04-13 一天内 4 个 topic 收尾 + 1 个 Batch 2 工作落盘，Planner 上下文分散为风险源。交接卡记录 12+ 次 handoff。

---

## §5 Agent 巡检（agent_findings / agent_tasks）

**SQLite DB**: `edu_cloud.db` 86MB（本地测试/种子库），数据查询结果：

- `agent_findings` 表：**0 条**（Schema 就绪，无运行时数据）
- `agent_tasks` 表：**0 条**
- `agent_runs` 表：13 条（历史执行记录存在，但巡检产物无持久化）

**判断**：W1 / W6 工作流代码已有 `AgentFinding(status="new")` 创建逻辑，但**未被定时触发或未接入生产 DB**。若需要 Agent 巡检发挥价值，需要：
- （a）接入定时任务 / cron 触发
- （b）或手动触发 W6 巡检一次看产物

这属于 T3 候选（需要评估是否要上线巡检定时任务）。

---

## §6 遗留与下一步优先级（Planner 提议，待用户裁定）

### 🔴 HIGH（需尽快处理，影响当前 blocker）

1. **haofenshu-phase1 Batch 2 GPT code review**
   - 状态：T4-T9 frontend-nuxt 工作已落盘，`code_review_batch2` 未发起
   - 动作：走 codex-review (code) gate 2 流程，产出 review-report-batch2.md + 写 gates.json 回执
   - 预估：1-2 轮 GPT 审查 + 修复（类似 Batch 1）

2. **5 pre-existing test failures 定性**
   - 状态：CLAUDE.md 称"与 governance 零交集"，但未做根因调查
   - 动作：一个 T2 bug fix 批次，systematic-debugging skill 走根因声明 + 修复（3 个文件）
   - 预估：2-3 小时

### 🟡 MEDIUM（近期但不紧急）

3. **conduct-module Gate 1 Plan Review 遗漏的审计追认**
   - 状态：conduct gates.json 显式标 `plan_review: skipped`，本 topic 已 Code Review PASS 收尾
   - 动作：补一篇 plan-review-posthoc.md 追认（或显式接受不补），记入审计
   - 目的：流程纪律硬化（下次 T3/T4 不能再跳 Gate 1）

4. **CLAUDE.md drift 修正（T1 轻量）**
   - 19 → 20 模块（补 menu）
   - 1896/1976 → 1983 tests
   - 修 `src/edu_cloud/modules/` 列表

5. **18 模块 MODULE.md 债务**
   - 策略：**严格自愈式**（不批量）。debt-report.md 已列清单
   - 高优先（近期触碰）：`conduct` / `knowledge_tree` / `exam`
   - 触碰时由 hook ask，顺手补

### 🟢 LOW（可延）

6. **R2-NEW-02**（deadline 2026-05-15）：`_checkout_staged_index` 全仓 2.75s → scoped
7. **phase1b/c/d/2.1/2.2 state.json 清理**（T1 批量改为 completed）
8. **Fix Intent 隐藏文件归档**（T1 move 2 files）
9. **Agent 巡检（W1/W6）上线定时任务**（若业务需要）

### 🟣 新 T3 候选（需 brainstorming 才能裁定）

- **haofenshu Phase 1 Batch 3**：45 页面 stub 复刻（Batch 2 收尾后触发）
- **memory-system 活跃度评估**：Phase 2 已完成，是否有 Phase 3 需求？
- **5 failures 的修复若涉及结构性问题** → 升 T3

---

## §7 Planner 纪律提醒（自我约束）

- 所有 T3/T4 新 topic 必须 brainstorming → writing-plans → Gate 1 codex-review（conduct-module 的 Gate 1 遗漏是反面教材）
- 行为变更类 GPT finding 必须单独审批（L017）
- 事实核查优先于规划（L013，本盘点多处修正了 agent 幻觉）
- 禁止把 triage 推给用户（feedback_research_over_rules，本盘点由 Opus 主导判定）
- 禁止虚假完成声明（L015）

---

## §8 可选动作清单（用户挑）

1. **A**：立即启动 haofenshu Phase 1 Batch 2 code review（发起 codex-review）
2. **B**：启动 5 failures 定性 T2 批次（systematic-debugging）
3. **C**：执行 CLAUDE.md drift T1 修正 + state.json 清理（轻量维护）
4. **D**：启动 Agent 巡检上线评估 brainstorming
5. **E**：其他你想推进的方向

**默认推荐**：A（是最紧的 blocker——Batch 2 工作已落盘，审查滞后会导致后续 Batch 3 无法启动）。

---

## §9 Event Log 2026-04-14（追加于 12:14:39）

本段由同一 Planner 会话在 session resume 后追加，记录自 §8 以来的事实变更。

### 9.1 haofenshu-phase1 —— Batch 2 收尾 + Batch 3 就绪

- **07:35:32**: GPT Gate 2 R2 审查结论 **FAIL**（authoritative）
  - B2-F001 contested：`npm ci` 仍产 6+ EBADENGINE 警告（lockfile 锁定的 dep 要求 Node `>=20.19.0` 或 `>=22.12.0`，环境 Node `v20.18.0`）
  - B2-F002 verified
  - B2-F003 contested：R2 handoff line 171 仍出现 "WSL 后端 hot-reload 失效" 旧措辞引用
- **07:38:09**: 本 Planner 二次独立 codex-review 产出 PASS，但漏检 EBADENGINE 与 line 171 残留；L013/L017 防御下取 FAIL 权威，保留 PASS log 为 SECONDARY 参考
- **07:45**: gates.json `code_review_batch2.raw_output_hash` 修正（原 PASS log hash → authoritative FAIL log hash `b1fcde8b...`），新增 `raw_output_path` + `reason` 记录双审查 audit trail（commit `f539a5f`）
- **08:10:39**: Planner 产出 R3 Executor 交接卡 `2026-04-14-haofenshu-phase1-batch2-r3-handoff.md`（commit `2701bf1`），方案 **A + X**（user approved）：
  - B2-F001 方案 A: Node floor 升级到 `>=22.12.0`（behavior_change，用户 approved）
  - B2-F003 方案 X: 删除 handoff line 171 旧措辞
  - Planner 独立验证 lockfile 所有 node engine 交集 = `>=22.12.0`（非另一并行会话的 `>=20.19.0`——rollup-plugin-visualizer 要求 `>=22`）
- **08:12**: 并行会话产出重复 executor-handoff（Node `>=20.19.0` 不足以覆盖）；Planner 确认冲突后由另一 session cleanup staged `D`
- **08:15**: 另一 session commit `155e225 docs(haofenshu): 收敛 R3 交接卡至权威版本 + CLAUDE.md Node floor 修正`
- **09:10:19**: Executor 完成 R3 修复（commit `6ddb19c`）—— Node portable `v22.22.2` 切换（不覆盖系统 Node 20.18，`~/bin/` + `~/.bashrc` PATH 前置）+ `package.json engines.node ">=22.12.0"` + `frontend-nuxt/.nvmrc` 锁定
- **09:30:00**: GPT Gate 2 R3 **PASS**（commit `ce6bce9`）：7 项断言全通（npm ci 零 EBADENGINE / npm ls 零 invalid / Vitest 24/24 / hot-reload grep=0 / INV-01~06 + ORC-NODE-01/02 成立）；gates.json `code_review_batch2.status=pass`，`report_path` 锚定 R3 报告
- **09:30:30**: Batch 3 Executor 交接卡派发 `2026-04-14-haofenshu-phase1-batch3-handoff.md`（Task 10-12：usePowerOptions/PowerFilter + 45 页面 stub + 端到端验证），含 3 项前置修复（R4 useMenus startsWith 分隔符 / R1 9000 进程陈旧重启 / plan risk_modules 追认）

**haofenshu-phase1 当前状态**：Batch 1/2 PASS，**Batch 3 待 Executor 启动**（新窗口使用 `2026-04-14-haofenshu-phase1-batch3-handoff.md`）。

### 9.2 kg-phase1 —— Batch 3.a PASS + Batch 3.b 就绪（并行轨道）

- T9-T10 Batch 3.a：前端热力色 + ColorModeToggle + ConceptMapPanel 视觉升级
- R1 FAIL 3 finding（F001 KnowledgeTreePage `selectedStudentId` 状态分裂 / F002 mount.test.js stub 吞新 prop / F003 ConceptMapPanel.test.js G6 mock 无 setData）
- **R2 PASS**（commit `2ab10a2..c5bff80`）：Planner 纠正 Executor R1 对 F001 的 scope 误判（composable 已导出 ref，修复仅需页面解构），mount.test.js 补 1 文件 scope 扩容由用户 L017 批准
- Batch 3.b 交接卡已派发 `f9ab3a1 handoff: kg-phase1 batch 3.b session transition card (T11-T12)`
- **kg-phase1 当前状态**：Batch 3.a PASS，**Batch 3.b 待 Executor 启动**（新窗口使用 `2026-04-13-knowledge-graph-phase1-handoff-batch3b.md`），Batch 3.c (T13-T14 + P001 + Phase 1 收尾) pending

### 9.3 conduct-roadmap —— Plan Review R2 又 FAIL（plan 修订轨道受阻）

- R1 FAIL → R2 修订（commit `1bc2339`）
- **R2 Plan Review FAIL** 6 findings（报告 `2026-04-14-conduct-roadmap-batch1-plan-review.md`, 08:45:51）：
  - **G1-001 HIGH**: state.json 生命周期错（Task 6 创建 → 应 Gate 1 后建 + 每 Task 迁移）→ requires independent fix design + Semantic Regression Gate
  - **G1-002 HIGH**: Contract Pack 不符 schema（用 `rule` 不是 `statement` / `verification` 值 `new_test` 不在枚举 / `deadline` 非纯日期）→ requires independent fix design + Semantic Regression Gate
  - **G1-003 HIGH**: Task 4 主步骤/git add 指向错文件（`test_admin_api.py` vs 实际 `test_admin_crud_api.py`）
  - **G1-004 HIGH**: T2 UX 缺口（ConductPoints.vue 无日期控件，API 契约修好但用户不可达）
  - **G1-005 MED test-gap**: T1/T3 入口级测试缺（`has_permission` / `getSidebarItems` 不是用户可触达入口）
  - **G1-006 MED code-bug**: F005 审批状态双口径（gates.json 已 approved，正文仍"待二次确认"）
- **conduct-roadmap 当前状态**：Plan Review Gate 1 **blocked**，需 Planner 决定 R3 修订范围 — 特别是 G1-001/G1-002 需要独立 Fix Intent 设计

### 9.4 元状态整理

- gates.json audit 一致性恢复（f539a5f）
- Planner 本会话 `effective_tier=T4`（SessionState 内已升级）
- 并行会话冲突已处理 2 次（R2 / R3 executor-handoff 重复），均由事实核查 + 后续 session cleanup 收敛
- Stop hook 触发 2 次、session_guard 触发 2 次、`completion_blocked=true`（状态持续存在）

### 9.5 平行 MEDIUM 轨道仍未启动

- 5→**2 稳定 failures** 定性（`test_tool_access_fail_closed.py` 2 tests）
- conduct-module Gate 1 `plan_review=skipped` 追认
- CLAUDE.md drift T1 维护（19→20 模块 / 1976→1983 tests / menu 补写）
- phase1b/c/d/2.1/2.2 state.json 陈旧清理
- R2-NEW-02 deadline 2026-05-15（module-governance 全仓 checkout-index 优化）
- 18 模块 MODULE.md 自愈式债务
- 2 个 `.conduct-fix-intent-*` 隐藏文件归档
