# Codex Meta Guardian Deep Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Codex 元守双核心从“模型自律调用脚本”升级为“证据闭环 + 事件账本 + 异步守护事实 + 完成门禁”的 Codex-native 体系；不复制 Claude 57 hooks，只移植 Claude 证据中 87.3% block 来源的高收益规则。
**Architecture:** `scripts/meta_runtime.py` 增加 closeout 门禁；`scripts/codex_governance.py` 提供规则注册、事件账本、验证收据；`scripts/codex-verify` 写入收据；`scripts/guardian_runtime.py` 继续采集 runtime truth 并写入同一治理账本；`docs/context/safety_matrix.json` 成为机器可读规则源，`docs/context/SAFETY_MATRIX.md` 保留人工视图。
**Tech Stack:** Python stdlib, Bash/Python entrypoints, pytest, existing edu-cloud scripts, JSON/JSONL state files under `logs/`.

---

## Evidence Basis

- Claude evidence report: `/home/ops/.claude/docs/meta-reviews/2026-05-07-meta-guardian-evidence-audit.md`.
- Claude hard data: 49 hook files, 12,275 hook LOC, 1,643 Guardian LOC, 15,463 events across 19 days and 136 sessions.
- Claude block distribution: `completion_guard` 785, `build_clean_guard` 424, `doc_sync_guard` 115, `code_review_gate_guard` 107, `write_guard` 103; top 5 account for 87.3% of blocks.
- Claude evidence gaps: no `latency_ms`, only about 2 days Guardian history, zero-event hook execution is not clearly observable.
- Codex existing assets: `scripts/meta_runtime.py`, `scripts/guardian_runtime.py`, `scripts/codex-verify`, `docs/context/SAFETY_MATRIX.md`, `tests/governance/test_codex_scripts.py`.
- Codex current gap: rules are clear and scripts exist, but completion evidence, receipts, and blocking handoff gates are not yet machine-enforced.
- Upgrade decision: implement closeout gate, receipts, ledger, and Guardian facts; do not clone Claude's synchronous 57-hook runtime.

## Non-Goals

- Do not auto-kill processes, clean ports, reset git, delete files, deploy, migrate DB, or restart services.
- Do not grant Claude write or Bash authority; Claude remains read-only advisory.
- Do not recreate Claude's PreToolUse/PostToolUse hook fleet.
- Do not touch unrelated dirty analytics, frontend, or generated report files already present in the worktree.
- Do not treat network absence as success; record network checks as `skipped`.

## Write Scope

- Create `scripts/codex_governance.py`.
- Create `scripts/codex-closeout`.
- Create `docs/context/safety_matrix.json`.
- Modify `scripts/meta_runtime.py`.
- Modify `scripts/codex-verify`.
- Modify `scripts/guardian_runtime.py`.
- Modify `tests/governance/test_codex_scripts.py`.
- Modify `docs/context/GOVERNANCE_MODEL.md`.
- Modify `docs/context/META_RUNTIME.md`.
- Modify `docs/context/GUARDIAN_RUNTIME.md`.
- Modify `docs/context/COMMANDS.md`.
- Modify `docs/context/SAFETY_MATRIX.md`.
- Runtime-generated files are not committed: `logs/governance-events.jsonl`, `logs/governance-receipts.jsonl`.

## Rule And Evidence Model

Governance event schema:

```json
{"schema":"codex.governance.event.v1","ts":"2026-05-07T00:00:00Z","session_id":"...","core":"meta|guardian|verify","rule_id":"...","action":"allow|info|warn|shadow|block|resolved","reason":"...","target_path":"...","command_hash":"sha256:...","latency_ms":12,"evidence":{}}
```

Verification receipt schema:

```json
{"schema":"codex.governance.receipt.v1","ts":"2026-05-07T00:00:00Z","receipt_id":"...","check":"safety|backend|frontend|schema|meta|guardian|review","returncode":0,"git_head":"...","dirty_fingerprint":"...","paths":["..."],"command_hash":"sha256:...","network":"enabled|disabled|skipped"}
```

- `allow`: rule evaluated and passed.
- `info`: rule emitted non-blocking evidence.
- `warn`: issue exists but does not block closeout.
- `shadow`: would block after promotion, but currently records only.
- `block`: strict mode exits nonzero.
- `resolved`: previously active fingerprint disappeared.

## Initial Rule Registry

- `M-CLOSEOUT-EVIDENCE`: completion or handoff requires fresh receipts for changed path categories.
- `M-DIRTY-BUILD`: frontend build artifacts cannot be claimed clean when source/build fingerprints drift.
- `M-DOC-SYNC`: docs and context drift are tracked first in shadow mode.
- `M-REVIEW-GATE`: review requirement is tracked first in shadow mode.
- `M-WRITE-GUARD`: changed script or governance file requires safety and governance test receipts.
- `G-RUNTIME-DRIFT`: backend/runtime hash, PID, boot time, dirty state, and working-tree drift.
- `G-PORT-PROCESS`: public bind, parallel backend, duplicate worker, duplicate Guardian, and port ownership issues.
- `G-LEDGER-HEALTH`: ledger write failure, stale Guardian snapshot, or missing receipt store.
- Source mapping must reference existing S-001 through S-018 in `docs/context/SAFETY_MATRIX.md`.

## Implementation Steps

### Phase 0: Baseline

- [ ] Run `git status --short` and record only upgrade files as allowed write scope.
- [ ] Run `.venv/bin/python -m py_compile scripts/meta_runtime.py scripts/guardian_runtime.py scripts/codex-verify`.
- [ ] Run `.venv/bin/python -m pytest tests/governance/test_codex_scripts.py -q`.
- [ ] Run `.venv/bin/python scripts/guardian_runtime.py --once --no-network --no-model-review --json > /tmp/guardian.before.json`.
- [ ] Run `scripts/meta-check --json > /tmp/meta.before.json`.
- [ ] Expected: `py_compile` has no output; governance tests pass or failure is captured before edits; both JSON files include a `schema` key.

### Phase 1: Shared Governance Module

- [ ] Add `scripts/codex_governance.py`.
- [ ] Implement `load_rules`, `append_event`, `append_receipt`, `read_recent_receipts`, `dirty_fingerprint`, `changed_paths`, `command_hash`, `latest_guardian_snapshot`, and `redact_command`.
- [ ] Add env overrides: `CODEX_GOVERNANCE_LEDGER`, `CODEX_GOVERNANCE_RECEIPTS`, `CODEX_GOVERNANCE_SESSION_ID`.
- [ ] Default runtime paths are `logs/governance-events.jsonl` and `logs/governance-receipts.jsonl`.
- [ ] Reuse Guardian JSONL rotation limits so the ledger cannot grow unbounded.

### Phase 2: Machine Safety Matrix

- [ ] Add `docs/context/safety_matrix.json` with all existing S-001 through S-018 and new rule IDs.
- [ ] Update `docs/context/SAFETY_MATRIX.md` to state the JSON file is the machine source of truth.
- [ ] Add a test that every emitted Guardian, Meta, and Verify rule exists in JSON or in an explicit legacy allowlist.

### Phase 3: Verification Receipts

- [ ] Wrap every `scripts/codex-verify` mode so it writes a receipt on success and failure while preserving stdout and exit code.
- [ ] Add `--no-receipt` only for emergency/debug and tests that intentionally suppress writes.
- [ ] Bind each receipt to `git_head`, `dirty_fingerprint`, check mode, network state, and changed path categories.
- [ ] Record network checks as `skipped`, not absent, when `--no-network` is used.

### Phase 4: Meta Closeout Gate

- [ ] Extend `scripts/meta_runtime.py` with `--closeout`, `--shadow`, `--ledger`, `--receipts`, `--receipt-max-age-minutes 120`, `--guardian-max-age-seconds 60`, and `--no-network`.
- [ ] Implement `build_closeout_snapshot()` that merges existing meta checks, changed path categories, recent receipts, and the latest Guardian snapshot.
- [ ] Block completion if changed scripts lack fresh `safety --repo-wide`, `py_compile`, and governance pytest receipts.
- [ ] Block completion if backend changes lack a fresh backend or targeted pytest receipt.
- [ ] Block completion if frontend changes lack a fresh frontend receipt.
- [ ] Block completion on Guardian red issues; warn on Guardian yellow issues.
- [ ] Output `schema: meta.closeout.v1`, `required_receipts`, `latest_receipts`, `guardian_freshness`, `issues`, and `actions`.

### Phase 5: Closeout Entrypoint

- [ ] Add executable `scripts/codex-closeout`.
- [ ] It runs `.venv/bin/python scripts/meta_runtime.py --closeout --json --strict "$@"`.
- [ ] Keep `scripts/meta-check --closeout` equivalent through the existing runtime entrypoint.

### Phase 6: Guardian Event Ledger

- [ ] Update `scripts/guardian_runtime.py` to append governance events only when the issue fingerprint changes.
- [ ] Emit one event per active issue with normalized `rule_id`, issue severity, blocking flag, `mode`, `no_network`, and `snapshot_id`.
- [ ] Emit a `resolved` info event when a previous issue code or fingerprint disappears.
- [ ] Include `latency_ms` for snapshot collection and event writing.
- [ ] Preserve Guardian's advisory policy: no kill, no cleanup, no build, no deploy, no migration.

### Phase 7: Shadow Rollout

- [ ] Enforce by default: `M-CLOSEOUT-EVIDENCE`, `M-DIRTY-BUILD`, `M-WRITE-GUARD`, `G-RUNTIME-DRIFT` red issues, and `G-PORT-PROCESS` red issues.
- [ ] Shadow by default: `M-DOC-SYNC`, `M-REVIEW-GATE`, non-critical docs freshness, and yellow Guardian issues.
- [ ] Add `--enforce-shadow` for tests and future promotion.

### Phase 8: Governance Tests

- [ ] Add tests in `tests/governance/test_codex_scripts.py` for JSON rule loading.
- [ ] Test receipt write with temp `CODEX_GOVERNANCE_LEDGER` and `CODEX_GOVERNANCE_RECEIPTS`.
- [ ] Test closeout blocks a changed script when no fresh safety receipt exists.
- [ ] Test closeout accepts a fresh receipt matching current `dirty_fingerprint`.
- [ ] Test Guardian emits events on fingerprint transition, not on identical repeated snapshots.
- [ ] Test Guardian emits `resolved` after an issue clears.
- [ ] Test shadow issues do not produce nonzero exit.
- [ ] Test `--no-network` records skipped network evidence.

### Phase 9: Docs

- [ ] Update `docs/context/GOVERNANCE_MODEL.md` with “Codex uses closeout gates, not PreToolUse hooks.”
- [ ] Update `docs/context/META_RUNTIME.md` with closeout JSON schema and commands.
- [ ] Update `docs/context/GUARDIAN_RUNTIME.md` with governance ledger and port/process/version lifecycle.
- [ ] Update `docs/context/COMMANDS.md` with the exact completion sequence.
- [ ] Update `docs/context/SAFETY_MATRIX.md` with the JSON source-of-truth note and new rule IDs.

### Phase 10: Verification

- [ ] Run `.venv/bin/python -m py_compile scripts/codex_governance.py scripts/meta_runtime.py scripts/guardian_runtime.py scripts/codex-verify`.
- [ ] Run `.venv/bin/python -m pytest tests/governance/test_codex_scripts.py -q`.
- [ ] Run `scripts/codex-verify safety --repo-wide`.
- [ ] Run `.venv/bin/python scripts/guardian_runtime.py --once --no-network --no-model-review --json`.
- [ ] Run `scripts/meta-check --closeout --no-network --json`.
- [ ] Run `scripts/codex-closeout --no-network --json`.
- [ ] Expected: `py_compile` has no output; governance tests pass; safety reports no dangerous changed-script patterns; Guardian JSON has `schema = guardian.watch.v1`; closeout may be red in the current dirty repo until unrelated analytics/frontend receipts exist, and that red result must be reported as live-state gate evidence rather than implementation failure.

## Acceptance Criteria

- `tests/governance/test_codex_scripts.py` passes.
- New tests cover rule registry, receipts, closeout blocking, closeout acceptance, Guardian ledger transitions, resolved events, shadow mode, and `--no-network`.
- `scripts/codex-closeout --no-network --json` returns actionable issue codes instead of prose-only advice.
- `docs/context/safety_matrix.json` maps every new rule and issue code used by Meta, Guardian, and Verify.
- Guardian remains advisory and never mutates process, port, git, database, build, or deployment state.
- Existing unrelated dirty analytics, frontend, and generated report files remain untouched.

## Rollback

- Delete `scripts/codex_governance.py`.
- Delete `scripts/codex-closeout`.
- Delete `docs/context/safety_matrix.json`.
- Revert the touched sections in `scripts/meta_runtime.py`, `scripts/codex-verify`, `scripts/guardian_runtime.py`, `tests/governance/test_codex_scripts.py`, and `docs/context/*.md`.
- Ignore or remove runtime-only `logs/governance-events.jsonl` and `logs/governance-receipts.jsonl`; they are not source files.

## Risks And Controls

- Codex still has no true PreToolUse hook; closeout catches completion and handoff, not every command.
- Stale receipts can lie; bind receipts to `git_head`, `dirty_fingerprint`, path categories, command hash, and max age.
- Review and doc-sync gates can over-block; ship them in shadow mode first.
- Ledger spam can hide signal; write Guardian events only on fingerprint transition and rotate JSONL.
- `--no-network` can hide remote drift; represent it as explicit skipped evidence and warn when relevant.

## Execution Order

- First batch: Phase 0 through Phase 4.
- Second batch: Phase 5 through Phase 8.
- Closeout batch: Phase 9 through Phase 10.
