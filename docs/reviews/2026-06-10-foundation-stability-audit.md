# 2026-06-10 地基稳定性审计（Foundation Stability Audit）

> **性质**：只读审计报告。Yuanshou V2 合同 `yc-20260610-b3099133`（contract_hash
> `sha256:b3099133a64eef0ea8479a88c296d015153162cba465b739b7b99d83c4a8816e`）授权窗口内产出，
> 本文件是该合同 `allowed_write_scope` 内唯一写入物。**不含任何代码/配置/数据修复，发现的问题只记录证据与风险。**
> **审计目标**：判断 edu-cloud 当前"地基治理"是否真的稳定，是否足以进入 Portal Phase 1。

## 元信息

| 字段 | 值 |
|------|-----|
| 审计时间 | 2026-06-10 19:26–20:0x（Asia/Shanghai） |
| 分支 / HEAD | `feat/module-governance-repair` / `c26379d`（working tree clean，upstream: none） |
| 审计方法 | 主会话执行合同 9 项 required evidence 命令 + 6 维并行只读深挖（7 个子代理）+ 完整性批判抽查 |
| 只读边界 | 未改 src/frontend/tests/alembic/scripts/DB/构建产物；未跑 migration/systemctl 变更/kill/build/deploy；未 commit/push |
| 上游裁定 | `docs/archive/plans/2026-06-07-phase08-acceptance-decision.md`（Phase 0.8 验收）、`docs/archive/plans/2026-06-07-phase09-portal-unlock-decision.md`（Phase 0.9 CONDITIONAL UNLOCK） |

## 摘要结论（TL;DR）

1. **源码层地基：稳定（PASS 维持）。** 模块治理四守卫在当前 HEAD `c26379d` 实测全绿，focused 回归 168 全过，known_drift 仅剩 1 条 ux 级（studio），DB 迁移链单 head 健康，truth-status 四面（source/dist/nginx/backend）全部对齐 `c26379d`。Phase 0.8 的"源码 PASS"判定在两次 AI provider 提交后依然成立。
2. **Portal Phase 1：尚不可开工（程序性 + 实质性双重未满足）。** 按 Phase 0.9 裁定的三条件门控：C1（DB doctor 红→绿）✅、C2（部署 hash 对齐 HEAD）✅ 字面达标，但 **C3（线上 module-gating / portal-services fail-closed 复验）无任何执行记录，设计者开工签署（designer sign-off）缺失**——裁定原文"任一红 → 不得开写"。
3. **本审计新发现一个 C2 实质缺口：ARQ worker 跑着 12 天前的旧代码。** `edu-cloud-worker.service` MainPID 1941124 自 2026-05-29 19:42 未重启，进程内代码为 `b763888` 时代——早于全部模块治理阶段（0.5→0.7E）、DB 迁移和全部 AI provider 工作；而 C2 判据与 guardian 监控面均只覆盖 backend/dist/nginx 三面，worker 版本是监控盲区。"运行态已对齐 HEAD"的声明实质不完整。

## 一、前因后果

### 1.1 地基治理链（2026-06-05 → 06-07）

模块治理从静态对账推进到运行时 fail-closed，阶段链 0.5 → 0.6/0.6C → 0.7A → 0.7B → 0.7D → 0.7E → 0.7E-R1 全部收口（证据：CLAUDE.md 各 Phase 段 + NOW.md + 各收口 commit）。核心成果：

- 后端 403 面与前端可见性面统一为单一真源 fail-closed（`module_enabled_default` 对齐 `school_settings_service.get_all_modules`，absent-row 非默认模块 403）；
- authGuard 直达 URL 二次门控 + 4 个前端可见性 surface 同源门控（`moduleGateFromAuth`）；
- known_drift 从 11 条 burn-down 至 1 条（仅余 `studio-frontend-entry-missing`，severity: ux）。

### 1.2 Phase 0.8 验收与 Phase 0.9 裁定（2026-06-07）

- **Phase 0.8**（`56ccd03`）：源码地基 PASS（codex-review 对 `3688f32` 判 PASS/0 finding，receipt 绑定），但运行态两红（DB schema drift + truthline 未对齐）→ Portal **BLOCKED**，留 3 项待设计者裁定。
- **Phase 0.9**（`a478b34`）：设计者（sid:a4e5781a）裁决 **Portal Phase 1 = CONDITIONAL UNLOCK**——解锁裁定成立，但实现开工被三条件硬门控：①DB doctor 红→绿 ②部署/运行态 hash 对齐 HEAD ③线上验证 module gating / portal services fail-closed；另有隐含第四前置：设计者开工签署（"executor does not self-unlock"，`docs/archive/plans/2026-06-10-db-migration-design.md` Q5）。第一刀范围锁定：前端聚合首页 + 消费现有 `/api/v1/portal/*` 5 端点 + 服务卡片按 `moduleGateFromAuth` 门控；地基语义冻结（禁改 `DEFAULT_ENABLED` / module middleware / authGuard / module-semantics）。

### 1.3 R1 运行态清账（2026-06-10）

R1 执行窗口（合同 `yc-20260610-a2979c86`，commit `41ae47a`）清绿 C1 + C2：迁移 `a1b2_chat_msgs → e1f2_import_sess` 经 `scripts/db_migrate` 应用（建 `exam_import_sessions`），`_audit_log` 判定为 trigger-backed 审计表入 db_doctor allowlist；孤儿 uvicorn PID 391900 停止、systemd 接管 backend；dist+nginx 重建对齐。其后 `c26379d`（coze required_action fail-closed 收口，19:03）落地，运行态于 19:05（backend restart）/ 19:12（dist rebuild）再次对齐到新 HEAD——**但这轮对齐操作在 repo 内无窗口/合同/文档记录**（见风险 R-M2）。

## 二、本轮实测证据（9 项 required evidence）

| # | 证据项 | 命令（摘要） | 结果 | exit |
|---|--------|------------|------|------|
| 1 | EV-CONTRACT-VALIDATE | `contract validate /tmp/edu-foundation-stability-audit-contract.v2.json` | valid: `yc-20260610-b3099133` | 0 |
| 2 | EV-YUANSHOU-DOCTOR | `scripts/yc doctor` | READY can_start=True（ok=11 warn=1 fail=0；warn=runtime health 1 warning + 本审计窗口自身 active session） | 0 |
| 3 | EV-GIT-STATUS | `git status --short --branch && git log --oneline -8` | clean；HEAD `c26379d`，近 8 commit 即 0.8/0.9 裁定 + R1 清账 + coze 收口链 | 0 |
| 4 | EV-TRUTHLINE | `scripts/truth-status.sh` | **ALL ALIGNED**：source=build=nginx=backend=`c26379d`，source_dirty=false，mcu.asia 200 | 0 |
| 5 | EV-DB-DOCTOR | `scripts/db_doctor.py --json` | `hard=0 warn=0 findings=[]`，alembic_version=`e1f2_import_sess`；orm_tables=96 vs db_tables=98（差异 = `alembic_version` + `_audit_log`，均在 allowlist 内被设计性吸收，见 §五.5） | 0 |
| 6 | EV-MODULE-GOVERNANCE | semantics + aggregate + dependencies + permission_mirror 四连 | 全绿：semantics baseline clean；23 modules / 0 conflicts / 0 debt / 0 stale；55 edges / 30 cycles baseline clean；permission mirror clean | 0 |
| 7 | EV-FOUNDATION-TESTS | focused pytest 10 个文件（governance×4 + middleware + portal service + AI×4） | **168 passed**, 0 failed（22.64s） | 0 |
| 8 | EV-GUARDIAN | `guardian-watch --once --no-network --no-model-review` | overall=**yellow**，red=0 yellow=2：CLAUDE_SESSION_RISK（10 进程，实为 pgrep 子串噪音，真 claude 二进制仅 1 个）+ RISKY_ARTIFACT（`data/.db_migrate.lock`、`.codex`，均已查证为良性残留） | 0 |
| 9 | EV-AUDIT-REPORT | 本报告存在性 + 关键词检查 | 见 closeout | — |

补充只读探测（非合同 evidence，供 C3 参考）：`https://mcu.asia/version.json` → `git_hash=c26379d, source_dirty=false`；`/api/v1/portal/summary`、`/api/v1/portal/services`、`/api/v1/academic/semesters` 未认证均 401 fail-closed。

## 三、已完成地基项（证据确凿）

1. **C1 — DB doctor 红→绿**：db_doctor `HARD=0 WARN=0`（本轮实测 exit 0）；迁移链健康——49 个 revision、单根、唯一 head `e1f2_import_sess` 且与 DB 一致，历史双头已被 merge revision `874f6f9c14cc` 收口；`db_migrate` 双层守卫（wrapper flock+备份+dry-run / `alembic/env.py` 无环境变量直接 raise）成立。
2. **C2（三面）— 部署 hash 对齐**：truth-status ALL ALIGNED，backend（PID 4143044, boot 19:05:28）/dist（build 19:12+08）/nginx 全部 `c26379d`，guardian red=0。**注意：worker 面不在该判据内，见 R-H1。**
3. **模块治理守卫全绿（HEAD `c26379d` 实测）**：四守卫 exit 0。0.5→0.7E 全链成果（fail-closed 语义、known_drift 11→1）经守卫与 focused 测试双重确认未回退。
4. **focused 回归 168 全过**：governance 守卫测试、module middleware dispatch 回归（0.7E-R1 补的 4 个 HTTP 403 测试在内）、portal service、AI provider 门控（coze fail-closed 主路径含 `assert_not_awaited` 断言）。
5. **coze required_action fail-closed 收口（`c26379d`）源码层完整**：门控默认 fail-closed（`getattr(..., False)`），OpenAPI submit 唯一函数的 2 个调用点全部被门控覆盖，无绕过路径；改动文件零 TODO/FIXME 残留。
6. **nginx 静态资源缓存策略合规**：入口文件 no-cache、hash 资产 immutable，无 blanket immutable 事故面。
7. **裁定与留痕体系**：0.8/0.9 两份裁定文档 + R1 runbook/recovery 文档完备，R1 执行偏差（allowlist 先于迁移的顺序反转）有诚实记录。

## 四、未完成项（Portal Phase 1 开工前必须闭合）

1. **C3 — 线上 fail-closed 复验：未执行。** NOW.md 明文 "③ online-verify module gating / portal services keep fail-closed (still to re-confirm + designer sign-off)"；`41ae47a` 之后 git log 与 docs 均无复验记录。本审计的未认证 401 探测只覆盖认证层，不能替代带凭据的模块门控 403 验证。
2. **设计者开工签署：缺失。** repo 内无签署记录；按 phase09 与 db-migration-design Q5，执行者不得自解锁。
3. **worker 运行态对齐：未做且无监控面。** 见 R-H1。
4. **NOW.md 锚点刷新：落后。** 声明 HEAD `6f90994`/PID 4017244，实际 `c26379d`/4143044；`6f90994→c26379d` 的 rebuild+restart 无治理留痕——"context stale"是 R1 窗口刚清掉的三号阻塞，数小时内复发。

## 五、剩余风险登记

### HIGH

- **R-H1｜worker 代码 12 天 stale 且为监控盲区**：`edu-cloud-worker.service` MainPID 1941124 启动于 2026-05-29 19:42:00（本审计 `ps -o lstart` + `systemctl show` 实测；`b763888` 提交于同日 19:40:38，phase09 记载同批启动的 backend PID 1941123 即跑 `b763888`）。worker 注册 `process_grading_task` + WorkflowExecutor（`src/edu_cloud/worker.py`），意味着 0.5 之后全部 src 改动（含 41a8ced/c26379d 的 AI provider ~3100 行、DB 迁移后的 ORM 演进）在 worker 进程内不生效。C2 判据只枚举 backend/dist/nginx 三面，`guardian_runtime.py` 对 worker 仅查"进程数>1 或非 systemd"，无版本/boot 新鲜度门控——同类 BACKEND_DRIFT 在 worker 面可无限期静默存在。**"C2 GREEN" 形式成立、实质不完整。**（注：NOW.md:339-341 所称 "legacy shell-started ARQ worker" 与现状不符——当前全系统仅此一个 worker 且 systemd-managed，真问题是它本身 stale。）
  **【处置 2026-06-10 20:45】stale 部分已闭合**：同日合同 `yc-20260610-776deb92` 窗口重启 worker（PID 1941124→189590，boot 2026-06-10 20:45:48，对齐 HEAD `c26379d`；窗口内两次 restart 详见 receipt），留痕 `docs/reviews/2026-06-10-worker-runtime-alignment.md`。**监控盲区部分仍开放**（guardian 无 worker 版本/boot 新鲜度门控，需改 `scripts/`，待后续批次）。
- **R-H2｜全量验证层休眠**：CI（全量 backend pytest + vitest + build）仅 push/PR 触发，本分支无 upstream 从未跑过；最近全量后端记录止于 0.7E（2026-06-07，2481 passed / 22 env failed），其后 ~3100 行 AI 代码与运行态接管均只有定向测试证据。focused 168 绿无法排除跨模块回归。
- **R-H3｜focused 范围对前端门控面零覆盖**：0.6→0.7A 全部安全收口（authGuard 直达拦截、routeAccess fail-closed gate、RoleSwitcher `canAccessMatchedRoute`）在前端 112 个 vitest 文件中，本审计合同的 focused 范围全部是后端；full vitest 最近记录停在 0.7A 时期（2498 pass / 3 预存失败）。
- **R-H4｜模块门控只存在于 HTTP 前缀一层**：55 条跨模块 import 边、30 个循环全部落在横跨 4 个开关码（exam/grading/study_analytics/research）的 9 模块强连通分量内——"学校关闭 exam" ≠ "exam 逻辑不可达"，禁用模块代码仍可经其它已启用模块端点执行，且该状态被依赖基线永久容忍（守卫只防新增、无 burn-down 机制）。
- **R-H5｜运行时数据态零守卫**：0.7E 后缺 `SchoolModule` 行的非默认模块直接 403（by design），但无任何守卫/监控核查生产 DB 行完整性——守卫全绿与"哪些存量学校正在被 403"完全正交。Portal 聚合首页一旦上线，缺行学校将在首页集中暴露 403/服务不可见，事故只能靠报障发现。**这正是 C3 必须带数据态核查的原因。**

### MED

- **R-M1｜portal 聚合面 = 未验证的死面**：`/api/v1/portal/*` 5 端点零前端消费者（frontend/src 与 dist 全量 grep 为空）；service 层 `enabled` 运行时过滤逻辑不在任何守卫覆盖内（check_portal 只验静态 SERVICE_CATALOG）；portal 模块共 439 行仅 7+2 个 service 层单测、无 HTTP dispatch 级测试。Phase 1 将把首个真实流量建在这个面上。
- **R-M2｜context-stale 模式复发 + 运行态操作绕过留痕**：`6f90994→c26379d` 的 rebuild（19:12）+ restart（19:05）无窗口/合同/文档记录；NOW.md 易变锚点写入数小时即过期。下一个窗口若按 NOW.md 字面值做合同/验证会引用错误锚点。
- **R-M3｜coze 门控开关是"死配置边"**：`AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED` 未在 `config.py` Settings 声明，而 `model_config extra="ignore"` 会静默丢弃 env 中的未知字段；`.env.example` 与 RUNBOOK 也无此项——方向安全（永久 fail-closed）但"显式开启"语义不可达，运维按提交信息设置 env 会被无声吞掉。是有意防误开还是遗漏，无证据判定（需设计者确认）。
- **R-M4｜测试失败基线三处不一致**：CLAUDE.md 12 条@05-19 / `.quality/known-pytest-failures.txt` 26 条@05-06 / NOW.md 22 条@06-07，且 22 条无逐条名单——新回归可藏匿在 failed 集合中不被 pytest_delta 机制捕获。
- **R-M5｜迁移备份无轮转 + 失败无自动回滚**：每次迁移产出 564MB 全量备份（06-10 三分钟内两次已占 1.05GB），`backups/` 无清理逻辑；真实 upgrade 失败只打印备份路径退出，DB 可能停在中间态。
- **R-M6｜守卫面与交付面错位**：四守卫解析 `frontend/src`，交付合同的消费面是 `frontend/dist`——src 修好门控但 dist 未重建时守卫照常全绿（当前由 truth-status/guardian BUILD_DRIFT gate 弥补，但二者不在 commit 时强制链上）。
- **R-M7｜`/uploads` StaticFiles 挂载在守卫分母（`/api/v1` 正则）与模块门控之外**，鉴权姿态未审计。

### LOW

- **R-L1**｜coze resume 路径 fail-closed 分支（`coze.py:107-109`）无专项测试——门控被误删时现有套件不会失败（与 0.7E-R1 关闭的 test_gap 同类）。
- **R-L2**｜guardian CLAUDE_SESSION_RISK 为 pgrep 子串匹配噪音（计数 10 中真 claude 二进制仅 1 个，余为 wrapper/挂死孤儿 shell）；`data/.db_migrate.lock` 为 flock 咨询锁正常残留（代码从不删文件、无进程持有、不阻塞下次迁移）但按"存在即 risky"永久告警——两者合成告警疲劳，会稀释真实信号。
- **R-L3**｜日志轮转序异常：`logs/app.jsonl.2`（06-10 19:00）比 `.1`（06-08）新，疑多写者竞争（backend/worker/guardian 三 systemd 进程同项目）；JSONL 健康无守卫监控。
- **R-L4**｜`data/edu_cloud.db` 存在 0 字节迷路文件（真实 DB 在项目根），可能误导诊断/备份脚本。
- **R-L5**｜docs-only 提交会再次触发 false BUILD_DRIFT（blocks_completion），规定清账方式是新 HEAD 重建 dist——流程摩擦点，存在 patch guardian 的诱因（设计文档已明令禁止）。
- **R-L6**｜前端守卫靠正则解析 4 个硬编码文件，route/moduleCode 改用变量或拆分新文件时 surface 分母静默缩小。

## 六、Portal Phase 1 准入判定

**结论：地基"源码层"稳定、运行态基本对齐，但 Portal Phase 1 当前不可开工。**

| 门控 | 状态 | 依据 |
|------|------|------|
| 解锁裁定（CONDITIONAL UNLOCK） | ✅ 成立 | phase09 设计者裁定，持久化于 `a478b34` |
| C1 DB doctor 绿 | ✅ | 本轮实测 hard=0 warn=0，alembic 唯一 head |
| C2 hash 对齐（backend/dist/nginx） | ⚠️ 字面 ✅，实质有缺口 | 三面 ALL ALIGNED `c26379d`（实测）；但 worker 面 stale 12 天且无监控（R-H1），"运行态对齐"声明不完整 |
| C3 线上 fail-closed 复验 | ❌ 未执行 | 无任何执行记录；其要验证的 portal 面本身是零消费者+守卫盲区+数据态未核查的三重未验证面（R-M1/R-H5） |
| 设计者开工签署 | ❌ 缺失 | repo 内无记录；"executor does not self-unlock" |

按 phase09 裁定原文"① ∧ ② ∧ ③ 全绿 → 可开工；任一红 → 不得开写"：**当前 C3 红 + 签署缺失 + C2 实质缺口，三重不满足。** 任何在此状态下开写 Portal 代码都直接违反裁定。

## 七、下一步建议（按序）

1. **运维窗口（先于 C3）**：重启 `edu-cloud-worker.service` 对齐 HEAD；将 worker 版本/boot 新鲜度纳入 C2 判据与 guardian 监控面（worker 无 `/version` 等价探针，可先用 boot-time vs HEAD commit-time 规则兜底）。同窗口顺手刷新 NOW.md 锚点至当前 HEAD，并补记 `c26379d` 对齐操作的留痕（闭 R-M2）。
   *→ 2026-06-10 20:36 部分完成（合同 `yc-20260610-776deb92`）：worker 重启 + NOW.md 锚点刷新 + 对齐留痕补记已落地，见 `docs/reviews/2026-06-10-worker-runtime-alignment.md`；guardian 监控面纳入仍待办。*
2. **C3 复验窗口**：带凭据在 `https://mcu.asia` 验证 ①缺行非默认模块（teaching/research/study_analytics）线上 403 ②portal services 按学校开关过滤、禁用模块入口不可见不可达；同窗口核查生产 `SchoolModule` 行完整性（存量学校是否已 backfill 全 9 行，闭 R-H5 的数据态未知）。
3. **设计者签署**：C3 绿后取得开工签署并持久化（repo 内留痕），方可进入 Portal Phase 1 实现。
4. **全量回归补账（可与 1/2 并行）**：跑全量后端 pytest + 前端 vitest，刷新 `.quality/known-pytest-failures.txt` 至当前逐条名单，统一三处基线口径（闭 R-H2/R-M4）；推荐给分支建 upstream 让 CI 接管。
5. **设计者裁定项（非阻塞）**：coze 门控开关是否接线 Settings（R-M3）；portal service 层过滤逻辑是否纳入守卫/补 dispatch 测试（R-M1，建议在 Phase 1 实现批次内一并处理）；备份轮转策略（R-M5）。
6. **卫生项（低优先）**：清理挂死孤儿 shell（R-L2）、迷路 0 字节 DB 文件（R-L4）、guardian 计数规则改进（pgrep 子串→精确匹配 + lock 文件持有者检查）。

## 八、审计方法与边界（unknowns 诚实登记）

- 全部 9 项 required evidence 由主会话直接执行并记录精确 exit code；6 维深挖与批判抽查由只读子代理完成，关键新发现（worker stale）经主会话 `ps`/`systemctl show` 复核。
- **未能在只读边界内验证的项**：① worker 进程内实际代码版本只能由启动时间+同批进程记录强推定为 `b763888`（无 /version 探针）；② 生产 DB 各学校 `SchoolModule` 行完整性（未开活跃 SQLite）；③ C3 的带凭据线上门控行为；④ 当前全量测试套件真实状态（12/22/26 三口径未消解）；⑤ 设计者签署是否在 repo 外渠道发生过（只能判定"repo 内无证据"）；⑥ `/api/v1/portal` 是否有仓外消费者（exam-ai/移动端）。
- 本审计期间 boundary guard 两次拦截（`/tmp` 重定向、heredoc 误判）均改用合规方式完成，无越界写入。
