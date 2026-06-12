# edu-cloud Foundation Debt Ledger（地基债务台账）

> 创建：2026-06-12（W3 governance context closeout，Yuanshou V2 合同
> `yc-20260612-899ea9ce`）
> 用途：**单一债务真源**——把散落在 audit / handoff / review 中的过程债与结构债
> 合并为一张台账，取代 finding 驱动 / 应激驱动的选题方式；元策每窗口从此「领一批」。
> 性质：只登记，不修业务代码。条目处置须经独立合同窗口，收口后在此更新状态。
> 更新纪律：每个合同窗口收口时报仪表盘 delta；数字不动 = 没深度。
> 证据底座：`docs/reviews/2026-06-11-edu-foundation-deep-investigation.md` +
> `docs/reviews/2026-06-10-foundation-stability-audit.md`（R-H1..R-L6）+
> `docs/reviews/2026-06-12-w1-governance-acceptance.md`。

## 深度仪表盘（每窗口收口报 delta）

| 指标 | 现值（2026-06-12） | 完工线 |
|---|---|---|
| 开放 HIGH 风险 | 3（R-H3 / R-H4 / R-H5） | 0 |
| 跨模块依赖环 | 30（55 edges） | 持续下降 + gate 防回弹 |
| AI tool 语义错挂 | ~46 个挤 `exam` 码 | 按 owner 归位 |
| 测试基线口径 | 3 套 | 1 套、自动刷新 |
| 无 receipt 提交 | 13（`3688f32..26d98eb`） | 0 且机械不可再发生 |

地基完工判据（全绿即转常态开发）：① doctor 常态 READY ② commit 必带
receipt/waiver（机械强制）③ 运行态操作必在合同窗口内（机械强制）④ 环数下降且
gate 防回弹 ⑤ 测试基线单一真源自动刷新。

## 债务条目

### D-01 runtime operation 未绑合同（洞 A）— HIGH · 过程

- 内容：运行态操作（restart / rebuild / deploy）不经 V2 合同即可执行，零兜底。
  R-M2 已实际发生 2 次（06-10 `6f90994→c26379d` 对齐；06-11 21:19 紧跟 push 的
  restart+rebuild，均无留痕）。
- 处置路径：W2（元守侧 writer，yuanshou 仓）实现「运行态操作绑合同」机械硬闸。
- 状态：**open**（机械化优先级最高，与 D-02 并列）。

### D-02 review receipt 未绑 commit（洞 B）— HIGH · 过程

- 内容：commit 落地不强制 receipt/waiver，零兜底。实际事故：06-07 后 13 个 commit
  零 receipt（`3688f32..26d98eb`，含 coze provider +2,946 行、answer-card
  canonical +3,634 行）。
- 处置路径：① W2 实现「receipt 绑 commit」机械硬闸；② 13 commit 按
  `docs/reviews/2026-06-12-w1-governance-acceptance.md` §3 处置表执行
  （两次 `codex-review range` 补审 + waiver/留痕/签认），在独立 review-gap
  合同窗口跑，不在 W3。
- 状态：**open**（闸门未建；13 commit 处置路径已登记待执行）。

### D-03 跨模块耦合 55 edges / 30 cycles（R-H4）— HIGH · 结构

- 内容：模块依赖基线 55 条跨模块边、30 个历史环，gate
  （`scripts/governance/check_module_dependencies.py`）只防新增、零 burn-down。
  禁用模块代码可借其他模块端点执行（门控逃逸面）。
- 处置路径：W5+ 拆环 burn-down 批次（独占窗串行，每窗 2–3 环，附依赖图 diff
  证据）；准备层在 `modular-arch-restore` worktree（Plan 1 边界 gate，见 D-09 Q3）。
- 状态：**open**（基线冻结，零 burn-down 记录）。

### D-04 AI tool module_code 语义债 — MED · 结构

- 内容：~46 个 AI tool 挤 `module_code="exam"`（analytics/profile/bank/knowledge/
  student-facing 工具语义错挂），真源 `docs/governance/ai-tool-module-codes.yaml`。
  门控语义失真：模块开关对这些工具不表达真实归属。
- 处置路径：module-writer 并行批次重分类（foundation-boundaries.md「Next
  Governance Batches」第 2 条），按 owner 归位 + 同批 role/scope 测试。
- 状态：**open**。

### D-05 Coze required_action 死开关（R-M3）— MED · 配置

- 内容：`AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED` 未声明进 `config.py` Settings
  （pydantic `extra="ignore"` 静默吞 env）→ 文档承诺的「显式开启」不可达。方向
  安全（永远 fail-closed）但开关无效。
- 处置路径：等 Q2 裁定——接线进 Settings vs 裁定永久关闭并删开关叙述。
- 状态：**open**（待裁定）。

### D-06 known_drift = studio-frontend-entry-missing — LOW · 登记内

- 内容：`docs/governance/module-semantics.yaml` 仅存 1 条 known_drift：studio
  前端入口缺失（ux 级）。
- 处置路径：设计者已裁定留待 Portal services 真正提供 studio 入口后关闭；
  不阻塞 Portal Phase 1 解锁。
- 状态：**open by design**（有意保留，禁提前修）。

### D-07 测试基线三口径分裂（R-M4）— MED · 过程

- 内容：CLAUDE.md「12 failed」（05-19）/ `.quality/known-pytest-failures.txt`
  26 条（05-06 后未刷新，`pytest_delta` 闸门未持续运转）/ NOW.md 22 条 env 失败
  （0.7E 全量实跑）。失败集合无单一真源。
- 处置路径：W3 后续批次/独立小窗——重启 `pytest_delta`，刷新
  known-pytest-failures，统一为单一自动刷新口径。
- 状态：**open**。

### D-08 Portal Phase 1 解锁前置条件 — 阻塞性 · 流程

- 内容：Portal Phase 1 = CONDITIONAL UNLOCK（`docs/plans/2026-06-07-phase09-portal-unlock-decision.md`，
  sid:a4e5781a）。C1（DB 红→绿）✅、C2（四面 hash 对齐）✅；**未完成**：
  C3 线上 fail-closed 复验（带凭据验证非默认模块缺行 403 + portal services
  按校过滤）+ **R-H5 生产 SchoolModule 行完整性核查**（最易漏）+ 设计者签发留痕
  （executor does not self-unlock）。
- 处置路径：W4（C3 复验窗，read_only + 线上凭据）→ 设计者签发 → 解锁。
- 状态：**blocked on W4 + sign-off**。

### D-09 其余开放风险（指针登记，真源在 audit/调查报告）

| 项 | 级别 | 一句话 | 处置路径 |
|---|---|---|---|
| R-H1 后半 | HIGH | guardian 对 worker 无版本/boot 新鲜度探针（stale 已闭合，盲区开放） | worker /version 探针小窗 |
| R-H2 | HIGH | 全量验证层休眠（CI 实跑证据缺） | push 后核验 CI 实跑 |
| R-H3 | HIGH | 前端门控面零全量回归记录（0.6→0.7A 收口全在 vitest） | 全量回归记录窗 |
| R-M1 | MED | portal 5 端点零消费者、过滤无守卫 | Portal Phase 1 实装时同批 |
| R-M5 | MED | 迁移备份 564MB/次无轮转、失败无自动回滚 | 与 Q5 周期备份一并 |
| R-M6 | MED | 守卫解析 src、交付面是 dist，commit 时不强制链上 | 靠 truth-status 弥补，待闸门化 |
| R-M7 | MED | `/uploads` StaticFiles 在门控分母外 | 门控分母补登记窗 |
| R-L1..L6 | LOW | coze resume 无测试 / pgrep 噪音（已实锤）/ 日志轮转序 / 0 字节 DB / docs-only false BUILD_DRIFT / 前端守卫硬编码 | 批量小窗 |
| Q3 | 数据安全 | `modular-arch-restore` 7 commit 唯一副本（origin 无此分支，含 Plan 1 资产） | 一条 push，需用户授权 |
| Q4 | 卫生 | paper-seg pip 缓存事故（206 文件入仓 + .gitignore 缺条目） | 独立小窗 commit 删除 |
| Q5 | 数据安全 | DB 564MB 无周期性备份机制（仅 2 份 06-10 手动备份） | 备份机制设计窗 |

## 使用规则

1. 新发现的债务**先登记后处置**：写入本台账（含级别、证据指针、处置路径），
   由元策按「风险 × 批量 × 可并行性」排窗，不接受窗口内顺手扩 scope。
2. 条目收口必须引用合同窗口 + 证据命令，状态改为 closed 并在仪表盘更新 delta。
3. 本台账与 `docs/governance/debt-report.md`（模块合同生成物）互不替代：
   debt-report 是生成的模块债快照，本台账是跨域治理债的人工裁定真源。
