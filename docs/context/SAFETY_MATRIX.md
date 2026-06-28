---
title: Safety Matrix
owner: liang
last_review_date: "2026-06-28"
expiration_in_days: 30
---

# Safety Matrix

Each row maps a valuable Claude-era rule to Codex-native enforcement. The `ID`
column is the lightweight governance registry for 双核治理.

| ID | Risk | Source | Current Defense | Completion Evidence | Gap |
|---|---|---|---|---|---|
| S-001 | Dirty or audit-red frontend ships unreviewed code | L021 / delivery contract + GitHub CI incident 2026-06-21 | `scripts/codex-verify frontend` blocks dirty frontend inputs and mirrors the CI frontend job (`npm ci`, `vitest`, build, `npm audit --audit-level=high`) | `scripts/codex-verify frontend`; post-push `scripts/codex-verify github-ci --wait`; `scripts/truth-status.sh`; `curl https://mcu.asia/version.json` | CI does not verify live `https://mcu.asia`; completion still requires production URL evidence |
| S-002 | Source/build/nginx/backend drift | L013 / truthline | `scripts/truth-status.sh`, `scripts/codex-context`, `scripts/codex-verify frontend`, `scripts/truth doctor --json` | Truthline output shows matching hashes and exits 0 only when aligned; Guardian doctor emits issue/action JSON | Add historical drift/event trend tracking if repeated incidents appear |
| S-003 | Direct Alembic mutation | Migration gate repair | `scripts/db_migrate`, `alembic/env.py` prod DB guard, `scripts/codex-verify safety`, CI governance job, CI Alembic smoke | `scripts/codex-verify schema`; safety scan has no direct `alembic upgrade/downgrade` hits | Expand safety scan to changed docs if needed |
| S-004 | Active SQLite copy | L016 | AGENTS hard ban, artifact policy, `scripts/codex-verify safety`, CI governance job | Safety scan has no shell-level SQLite copy commands; use backup API | Repo-wide DB-copy scan is enabled for non-ignored files |
| S-005 | Secret leakage | Claude secret guard | `.gitignore` covers `.env` and `.secrets`; AGENTS ban; `scripts/codex-verify safety --repo-wide` scans changed scripts plus non-ignored repo files for secrets | Safety scan has no probable key/private-key hits | Rotate any credentials that ever appeared in historical docs; current-tree redaction is not history rewriting |
| S-006 | Destructive git cleanup | Claude destructive git guard | AGENTS hard ban; `scripts/codex-verify safety` scans changed scripts; CI governance job runs safety | Safety scan has no destructive cleanup hits; user approval required for any real destructive git command | Optional local git hook installer in P2 |
| S-007 | Retired Claude auxiliary accidentally becomes active again | Keel legacy quarantine | `scripts/governance/check_legacy_quarantine.py --check` blocks `codex-consult-claude` and `--model-review claude` from active CI/runtime surfaces | CI governance job runs the quarantine gate; unit tests prove active CI/runtime detection | Historical references may remain as evidence, but they must not be execution entrypoints |
| S-008 | Historical docs polluting current work | L018 / takeover cleanup | `ACTIVE_INDEX.md`, AGENTS ban | Active document path appears in index | Needs periodic freshness review |
| S-009 | Completion without evidence | Completion guard | `scripts/codex-verify` commands, CI governance dry-run | Final answer includes command and result | No automatic stop hook in Codex; rely on explicit verifier |
| S-010 | Artifact noise | Current untracked state | `ARTIFACT_POLICY.md`, `.gitignore` updates | `git status` separates source changes from local artifacts; user-approved local AI grading artifacts are ignored | Periodic cleanup can archive ignored artifacts after explicit approval |
| S-011 | Fix-loop or rapid patch drift | Claude trajectory/fix-loop discipline | AGENTS and `GOVERNANCE_MODEL.md` require stopping after repeated failed fixes; `scripts/codex-context` exposes dirty scope before work | Final answer states root cause and verification after repeated fixes | Add structured edit/verification event counter before automating |
| S-012 | Evidence-less decisions or negative assertions | Claude decision-evidence discipline | Meta Core requires grep/read/file-line evidence for scope, negative assertions, and architecture choices | Design/plan/final answer cites concrete files, commands, or outputs | Add template checks only if this becomes noisy |
| S-013 | Existing asset bypass or parallel systems | Claude planning-inventory discipline | Meta Core requires existing asset inventory before new subsystem work; `ACTIVE_INDEX.md` controls active docs | Design/plan lists existing backend/frontend/test assets and delivery path | Add a future design-doc linter if repeated |
| S-014 | Work-time drift goes unseen between manual checks | Guardian realtime requirement | `scripts/guardian-watch` runs once or continuously; systemd template `deploy/systemd/edu-cloud-guardian.service` writes latest state and JSONL history; model review is rate-limited and read-only | `systemctl is-active edu-cloud-guardian.service`; `scripts/guardian-watch --once --json --no-network --no-model-review`; `logs/guardian-state.json` has fresh `guardian.watch.v1` | GPT model review needs a working local GPT CLI/API wrapper before it can be enabled safely |
| S-015 | Multi-step user instruction loss, role drift, or compact forgetting | L022 | `scripts/meta-check --task ...` emits explicit `task_contract.obligations`; `scripts/meta-check --check-drift` compares against baseline obligations; `scripts/codex-context` shows latest Meta runtime state | `scripts/meta-check --json --task "..."`; `scripts/meta-check --task "..." --check-drift --baseline-state logs/meta-state.json`; final answer maps work to extracted obligations | No automatic Codex stop hook; run at task start and before completion |
| S-016 | Independent review evidence optimizes the wrong local problem | L017 | Meta Core extracts independent-review obligations without invoking the retired Claude auxiliary path; any external reviewer must be explicit, human/GitHub-backed, or passed through a vetted read-only command | `scripts/meta-check --json --task "审查..."` includes `INDEPENDENT_REVIEW_EVIDENCE`, not `CLAUDE_REVIEW` | External model review remains disabled unless a vetted wrapper is explicitly supplied |
| S-017 | Live task truth is absent during long execution | L019 / behavior audit | `scripts/meta-check --write-state` writes `logs/meta-state.json`; changed and recent plans are checked for evidence or delivery path; local/manual `scripts/codex-verify full` runs `scripts/meta-check --fail-on-blocking` outside GitHub Actions | `scripts/meta-check --json --fail-on-blocking`; `scripts/meta-check --check-recent-plans`; `scripts/codex-context --no-network` shows `Meta Runtime` | Meta is synchronous by design; Guardian remains the continuous process watcher |
| S-018 | Parallel backend/dev process serves a different version than the one Codex is editing | Current Guardian 1/2/3 upgrade | `scripts/guardian-watch` records structured `ports`, `processes`, and `versions`; flags `PARALLEL_BACKEND_PROCESS`, `PARALLEL_FRONTEND_DEV_SERVER`, `PARALLEL_VERSION_DRIFT`, `PARALLEL_RUNTIME_DIRTY`, `DUPLICATE_WORKER_PROCESS`, `PORT_CONFLICT`, `PORT_PUBLIC_BIND`, `PORT_OWNER_MISMATCH`, and `BACKEND_HOT_RELOAD` | `scripts/guardian-watch --once --json`; `tests/governance/test_codex_scripts.py::test_guardian_runtime_flags_parallel_backend_and_duplicate_worker`; `tests/governance/test_codex_scripts.py::test_guardian_runtime_flags_port_conflict_and_backend_hot_reload` | Still advisory: it reports process/port/version ownership, but Codex or user must inspect before stopping workers or debug backends |
| S-019 | Push accepted while GitHub Actions is red or still pending | R-H2 / GitHub CI incident 2026-06-21 | `scripts/codex-verify github-ci` binds the Tests workflow result to the current branch and exact HEAD SHA; with `--wait` it exits non-zero until GitHub reports success | After every authorized push: `scripts/codex-verify github-ci --wait`; if it fails, inspect `gh run view <run-id> --log-failed` | Private repo branch protection is unavailable without GitHub Pro/public repo, so this remains a local/post-push gate rather than a server-side block |

## Enforcement Strength

- Hard script gate: command exits non-zero and blocks completion.
- Advisory script gate: command reports risk, may exit 0 for preflight.
- Documentation rule: must be obeyed, but not machine-enforced yet.
- P2 CI: planned long-term enforcement.

## Guardian Issue Codes

Guardian Core should use these stable issue codes when reporting environment
health:

- `BUILD_DRIFT`
- `NGINX_DRIFT`
- `BACKEND_DRIFT`
- `FRONTEND_DIRTY`
- `BACKEND_DIRTY`
- `GHOST_PROCESS`
- `BACKEND_DOWN`
- `PORT_DANGER`
- `SERVICE_BYPASS`
- `CLAUDE_SESSION_RISK`
- `DB_SCHEMA_DRIFT`
- `UNPUSHED_COMMITS`
- `WORKTREE_DIRTY`
- `RISKY_ARTIFACT`
- `GUARDIAN_DOCTOR_FAILED`
- `DB_DOCTOR_FAILED`
- `PARALLEL_BACKEND_PROCESS`
- `PARALLEL_FRONTEND_DEV_SERVER`
- `PARALLEL_VERSION_DRIFT`
- `PARALLEL_RUNTIME_DIRTY`
- `DUPLICATE_WORKER_PROCESS`
- `DUPLICATE_GUARDIAN_PROCESS`
- `PORT_CONFLICT`
- `PORT_PUBLIC_BIND`
- `PORT_OWNER_MISMATCH`
- `BACKEND_HOT_RELOAD`
- `EXPECTED_PORT_MISSING`
- `PORT_INVENTORY_FAILED`
- `PROCESS_INVENTORY_FAILED`

Each issue should eventually carry `severity`, `summary`, `blocks_completion`,
and `command_hint`.

## Meta Issue Codes

Meta Core should use these stable issue codes when reporting direction,
context, and evidence-contract health:

- `ACTIVE_INDEX_MISSING`
- `ACTIVE_DOC_MISSING`
- `STALE_FACTS`
- `META_LESSON_GAP`
- `META_RUNTIME_UNREGISTERED`
- `LEGACY_CLAUDE_AUX_ACTIVE`
- `PLAN_EVIDENCE_GAP`
- `PLAN_SCAN_INCONCLUSIVE`
- `TASK_CONTRACT_DRIFT`

Each issue carries `severity`, `summary`, `blocks_completion`,
`required_before`, and `command_hint`.
