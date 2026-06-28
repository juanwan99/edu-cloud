# Active Document Index

Use this index before reading historical `docs/plans/**`. Anything not listed here is historical or candidate context, not active truth.

## Active

| Path | Status | Use |
|---|---|---|
| `AGENTS.md` | active | Codex entrypoint and hard rules |
| `docs/context/GOVERNANCE_MODEL.md` | active | 双核治理 model |
| `docs/context/CODEX_STEWARD.md` | active | Codex project stewardship and planning memory |
| `docs/context/PARALLEL_DEVELOPMENT.md` | active | Safe parallel development modes, launch rules, and exclusive scopes |
| `docs/context/META_RUNTIME.md` | active | Meta Core task-contract runtime |
| `docs/context/GUARDIAN_RUNTIME.md` | active | Guardian Core realtime runtime contract |
| `docs/context/NOW.md` | active | Current facts and risks. D-09S refreshed volatile truth at `4fe53fd`: source/build/nginx/backend/worker aligned, exact-HEAD CI green, Meta/Guardian/truthline green; next active work is D-09M guard hardening before broader parallel writers. |
| `docs/context/COMMANDS.md` | active | Command reference |
| `docs/context/LESSONS.md` | active | Project-specific migrated lessons |
| `docs/context/CLAUDE_AUX.md` | active | Claude Code read-only auxiliary model protocol |
| `docs/context/SAFETY_MATRIX.md` | active | Rule enforcement map |
| `docs/context/ARTIFACT_POLICY.md` | active | Local artifact, backup, screenshot, and scratch-script policy |
| `docs/governance/foundation-boundaries.md` | active | Module boundary, coupling debt, and parallel development direction |
| `docs/governance/debt-ledger.md` | active | 地基债务台账（单一跨域债务真源，窗口选题驱动）：过程洞 A（D-01 runtime-op）/洞 B（D-02 receipt-commit）**机械闸门已 W2 gate-built closed**，洞 B 历史 review-gap **16 commit（3688f32..6b1bdd3，L2 仍 open，闸门关闭≠历史债清账）**；D-03/R-H4 跨模块依赖边已 0 edges / 0 cycles gate-built；D-04 AI tool module_code 语义债 closed；D-07 测试基线 resolved；Portal Phase 1 D-08C/D-08D runtime/online closed；R-H2 exact-HEAD CI closed by master run `27953800524`; R-H3 frontend full regression closed by `docs/reviews/2026-06-22-rh3-frontend-gating-regression-closeout.md`; R-H1 worker freshness probe closed by `docs/reviews/2026-06-22-rh1-worker-runtime-fingerprint-closeout.md`; current remaining mainline debts are D-02 L2 historical review-gap plus D-09 MED/LOW guard debts (R-M5/R-M6/R-M7/Q5)。**D-08C 证据见 `docs/reviews/2026-06-22-portal-c3-online-verification.md`；D-08D runtime closeout 见 `docs/reviews/2026-06-22-portal-d08d-runtime-closeout.md`；R-H1 closeout 见 `docs/reviews/2026-06-22-rh1-worker-runtime-fingerprint-closeout.md`；R-H3 closeout 见 `docs/reviews/2026-06-22-rh3-frontend-gating-regression-closeout.md`；Q3 W2-后校准见 `docs/reviews/2026-06-13-q3-foundation-debt-reconcile.md`** |
| `docs/reviews/2026-06-13-q3-foundation-debt-reconcile.md` | active | Q3 地基债务台账校准记录（W2 后，合同 `yc-20260614-39eac63d`，sid:8d106de4）：D-01/D-02 拆两层——机械闸门 L1 = closed/gate-built（W2 96 passed + doctor READY）、历史 review-gap L2 = open（13→16 commit `3688f32..6b1bdd3`）；含 Fresh Evidence Pack / Root Cause Ladder（双层根因）/ 三层地基进度（运行态🟢 / 过程治理 机械层🟢+历史债层🔴 / 结构耦合🟡）/ 下一阶段排序。D-07/D-08 本窗不动 |
| `docs/reviews/2026-06-12-w1-governance-acceptance.md` | reference | Historical Q1 role ruling and evidence. Its Yuanqi execution-channel language is superseded by current Keel scope-file workflow in `AGENTS.md` and `docs/context/GOVERNANCE_MODEL.md`. |
| `.github/workflows/test.yml` | active | CI smoke checks for the Codex governance layer plus existing backend/frontend jobs |

## Candidate Active Work

| Path | Status | Notes |
|---|---|---|
| `docs/essay-scoring-handoff.md` | candidate-active | AI作文评分/锚点/盲测 facts are current and match dirty AI grading area. |
| `docs/2026-05-02-grading-pipeline-optimization-handoff.md` | candidate-active | Earlier AI grading pipeline context; likely partly superseded by essay-scoring handoff. |
| `docs/plans/2026-05-05-grading-progress-split-plan.md` | candidate-active | Recent grading progress plan; verify implementation state before using. |
| `docs/plans/2026-05-05-logging-system-redesign.md` | candidate-active | Logging redesign design; not part of Codex migration P0. |
| `docs/plans/2026-05-06-choice-scan-handoff.md` | candidate-active | User-provided handoff for Jingyan biology/geography choice-scan recovery; not part of the current Dual-Core governance task. Verify DB/template state before execution. |
| `docs/scan-calibration-handoff.md` | candidate-active | 2026-05-17 OMR calibration results and current `calibrate_scan.py` / `calibrate_universal.py` commands; verify DB and scan files before execution. |
| `scripts/governance/check_module_semantics.py` + `docs/governance/module-semantics.yaml` + `frontend/src/router/index.js` | candidate-active | Phase 0.5 static guard + 0.6 runtime authGuard gating (main body `f51342a`/`8606ac6`/`bf421e8`/`bd8be46`) + **0.6C coverage-completeness implemented** (`70eeac2`/`b1a6d09`/`61ed166`): router_meta 升完整门控面、profile 前后端门控补齐、F-001/F-002 收口。Guard clean + tests green. R5 复审确认 R4 三 finding FIXED（0.6C 达标）；R5 新报 R5 F-001=**MED security_design**（前端 surface fail-open，非可延期 design_concern）+ F-002=LOW design_concern。**Phase 0.7A 已完成**：4 surface 统一门控上下文 fail-closed，对齐 authGuard；复审 R6→R8 收口（R6/R7 RoleSwitcher 动态路由 module/permission 两 MED 已修，R8 零 MED/security）。**Phase 0.7B 已执行**：中间件最长前缀对齐守卫（R5-DC2）+ conduct/exam-imports 补门控 + 5 hygiene 入 exempt + CRLF 收口，known_drift 11→3。**Phase 0.7D 已执行**（`4002d56`/`bfdbd50`）：academic 双面 fail-open 收口——前端三 surface 接 teaching + 后端 /api/v1/academic 补门控，academic-backend-fail-open + teaching-frontend-unwired drift 删除，known_drift 3→1（仅余 studio）；**Phase 0.7E 已收口 F-001**：缺 `SchoolModule` 行的非默认模块（teaching/research/study_analytics）fail-closed 403（`module_enabled_default` 镜像前端 `get_all_modules`，后端 403 面与前端可见性同源），正常 init 学校有全行行为不变。See NOW.md "Phase 0.7D"。**Portal Phase 1 解锁=设计者决策**（执行工程师不自解锁）。 |
| `docs/plans/2026-06-06-phase06-coverage-handoff.md` | candidate-active | Phase 0.6C coverage-completeness sub-task handoff (**done**, R4 findings FIXED & R5-confirmed). Root-cause fix for R4 F-002 (guard enforces moduleCode on every controlled route) + F-001 (`/profile/student/:studentId` direct-URL fail-open). Goal/Must Preserve/Must Not Change inside. |
| `docs/plans/2026-06-06-phase07-drift-burndown.md` | candidate-active | Phase 0.7 模块门控 drift burn-down（R5 carve-out）。R5-DC1/F-001（MED security_design 前端 surface fail-open）已于 Phase 0.7A 处置。**Phase 0.7B 已执行（`fd89f10`/`0d78f55`/`90c8a93`/`c989e09`）**：① gate 回执文件收口；② CRLF→LF（router.test.js+auth.js，R8 LOW）；③ R5-DC2 中间件最长前缀对齐守卫（item3）；④ 后端 fail-open 收口——conduct/exam-imports 补门控，academic 当时保留 known_drift；⑤ 5 hygiene 路由入 exempt。known_drift 11→3。**Phase 0.7D 已执行（`4002d56`/`bfdbd50`）**：撤销 0.7B「academic 不补门控」——前端三 surface 接 teaching + 后端 /api/v1/academic 补门控，academic-backend-fail-open + teaching-frontend-unwired drift 删除，known_drift 3→1（仅余 studio）；**Phase 0.7E 已收口 F-001**：缺 `SchoolModule` 行的非默认模块（teaching/research/study_analytics）fail-closed 403（`module_enabled_default` 镜像前端 `get_all_modules`，后端 403 面与前端可见性同源），正常 init 学校有全行行为不变。守卫 --check clean、governance 55+中间件 15 passed、academic 后端+route_snapshot 21 passed、frontend 106 passed、meta-check green。codex-review 状态以机器真源为准（legacy receipt log；本表只述工作项，不叙述复审轮次 verdict——逐轮叙述每轮都过时并复发 scope_gap）。**Portal Phase 1 解锁=设计者决策**（0.7D 后仅余 studio 已登记 drift + Portal 解锁本身，执行工程师不自解锁）。 |
| `docs/plans/2026-06-07-phase08-acceptance-decision.md` | candidate-active | Phase 0.8 地基总体验收 + Portal 解锁裁定包（HEAD `3688f32`，sid:6be633a5）。结论：源码地基 **PASS**（最新 codex-review PASS/0 finding，机器真源 `legacy receipt log` receipt 绑定 reviewed_sha `3688f32`）；**Portal Phase 1 仍 BLOCKED**（设计者裁定 3 项：验收口径 / studio drift / Portal 范围）；truthline/DB 红灯为**运行态阻塞**（live `d9b1c56`≠HEAD + `exam_import_sessions` 缺表 + orphan `_audit_log`）。含 Fresh Evidence Pack / Risk Register / Portal Unlock Decision / Next Executor Packet。 |
| `docs/plans/2026-06-07-phase09-portal-unlock-decision.md` | candidate-active | Phase 0.9 Portal Phase 1 **条件解锁裁定**（HEAD `56ccd03`，裁定来源 sid:a4e5781a，承接 phase08 三待裁定）。结论：Portal Phase 1 = **CONDITIONAL UNLOCK**（非 unconditional、非 KEEP BLOCKED）；解锁裁定成立但**实现 gated by 运行态/DB cleanup** 三条件——① DB doctor 红→绿（现红：`exam_import_sessions` 缺表 + orphan `_audit_log`）② 部署/运行态 hash 对齐 HEAD（现运行态 backend `b763888`/dist `bfdbd50` ≠ HEAD，guardian.watch.v1 实测）③ 线上 module gating / portal services fail-closed 不破坏。第一刀范围：前端聚合首页 + 消费现有 `/api/v1/portal/*`（5 端点已实装 `portal/router.py:25-57`）+ 服务卡片按 `moduleGateFromAuth` 门控。地基冻结：禁改 `DEFAULT_ENABLED` / module middleware / authGuard / module-semantics 语义。studio drift 不阻塞解锁，仅在 Portal services 真正提供 studio 入口后再关闭。 |
| `docs/reviews/2026-06-22-portal-c3-online-verification.md` | active | D-08C Portal Phase 1 unlock prerequisite evidence packet. Fresh HEAD `0228fe6`: C1 DB doctor green, C2 source/build/nginx/backend `ALL ALIGNED`, governance gates clean, R-H5 production `SchoolModule` integrity green (3 schools x 9 rows, 27 total, 0 issues), online C3 fail-closed green (disabled teaching/research/study_analytics return 403; portal services leak none). User/designer signed D-08C in Codex thread on 2026-06-22; D-08D source/runtime/online closeout is green, and Phase B/R-H2 exact-HEAD CI is now closed by master run `27953800524` at `e52f86d`. |
| `docs/reviews/2026-06-22-portal-d08d-runtime-closeout.md` | active | D-08D Portal Phase 1 runtime/online closeout packet. Fresh HEAD `332862a0`: local/origin/ECS source aligned, frontend build/nginx/backend `ALL ALIGNED`, authenticated `/api/v1/portal/*` online probes all HTTP 200, services expose only `exam`/`grading`/`homework`/`calendar`/`studio`/`conduct`, disabled `teaching`/`research`/`study_analytics` leak none. Later master exact-HEAD run `27953800524` at `e52f86d` closes the external CI evidence gap. |
| `docs/reviews/2026-06-22-rh3-frontend-gating-regression-closeout.md` | active | R-H3 closeout evidence. Master exact-HEAD run `27953800524` at `e52f86d` is green; frontend job `82716953796` ran full `npx vitest run` with 117 files / 2525 tests passed, `npm run build`, and `npm audit --audit-level=high`. Closes the frontend module-gating full-regression evidence gap while preserving module middleware/authGuard semantics. |
| `docs/reviews/2026-06-22-rh1-worker-runtime-fingerprint-closeout.md` | active | R-H1 worker freshness closeout evidence. Commit `f18a507` adds worker runtime fingerprint, truthline/guardian enforcement, and tests; GitHub Actions run `27958619284` is green; ECS live truthline/doctor/guardian are green after stale local artifact cleanup. |

| `docs/plans/2026-06-10-db-migration-design.md` | candidate-active | Historical DB migration and systemd takeover runbook. R1 evidence uses retired historical contract `yc-20260610-a2979c86`; verify live DB/service/runtime state before any new execution. |
| `docs/plans/2026-06-10-runtime-foundation-recovery.md` | candidate-active | 运行态地基恢复调查 + context 同步（2026-06-10，HEAD `41a8ced`，合同 `yc-20260610-d97cdbe1`）。结论：三类标准阻塞**运行态仍全部成立**——① backend stale（PID 391900 跑 `ebf7934` ≠ HEAD，`edu-cloud.service` inactive + orphan uvicorn :9000）② DB schema drift（`exam_import_sessions` 缺表 + orphan `_audit_log`，alembic `a1b2_chat_msgs`，stale `data/.db_migrate.lock`）③ context stale（NOW.md 旧停 2026-06-07/`d9b1c56`/"services active"，本窗已纠正）。source/build/nginx 健康在 `41a8ced`。**下一步建议：先 DB migration 设计窗口，再 R1-B 运行态操作窗口**（restart 折叠进 migration rollout；单纯 restart 不解 DB 红灯 → 不解 Portal）。含 Fresh Evidence Pack（truth-status/db_doctor/guardian-watch）。 |

## Completed / Reference

| Path | Status | Notes |
|---|---|---|
| `docs/reviews/2026-06-11-edu-foundation-deep-investigation.md` | reference | 2026-06-11 深度调查报告归档（W1 验收 accept；三层地基判断、风险登记、治理效能数据的证据真源） |
| `docs/reviews/2026-06-11-edu-governance-handoff.md` | reference | 2026-06-11 治理交接包归档（W1 验收 accept；共识固化、13 commit 处置表、Q1–Q5 待裁定清单、W0–W5+ 窗口序列） |
| `docs/sidebar-modular-restore-handoff.md` | completed-reference | Header says Part A/B completed and Part C hook work implemented. |
| `docs/marking-assign-handoff.md` | completed-reference | Header says assignment redesign implemented. |
| `docs/plans/2026-04-29-truthline-p0-handoff.md` | reference | Truthline context only; current command is `scripts/truth`. |
| `docs/plans/2026-04-29-truthline-p0-review-report.md` | reference | Review evidence only. |
| `docs/plans/2026-05-12-agent-optimization-design-v2.md` | reference | Pydantic AI engine design referenced by `2026-05-12-agent-pydantic-ai-handoff.md`; current code imports pydantic_ai. |

## Historical

- The former `retired-archived-plan-history` tree was removed from the working tree on 2026-06-28; use git history for explicit historical evidence.
- The former `retired-superpowers-history` tree was removed from the working tree on 2026-06-28; do not treat superpowers plans/specs as active inputs.
- Pre-takeover plans marked `<!-- pre-takeover: archived for history, not active spec -->`
- Windows-era handoff numbers, paths, and timelines
- Old review logs not explicitly listed above

## Rule

When a task cites an old plan or handoff, first add it here with status `candidate-active` or `reference`, including why it is safe to read.
