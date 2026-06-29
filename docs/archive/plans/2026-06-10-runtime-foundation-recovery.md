# Runtime Foundation Recovery — 2026-06-10

> Status: **investigation + context sync only** (no runtime mutation performed).
> Window governed by Yuanshou V2 contract `yc-20260610-d97cdbe1`
> (`sha256:d97cdbe1a36b82d048bc869285b080e80b24a8592378ab44a39ecea97ae548f1`),
> session `ef158f22`. Executor authority: read-only investigation +
> `docs/plans/2026-06-10-runtime-foundation-recovery.md`, `docs/context/NOW.md`,
> `docs/context/ACTIVE_INDEX.md` only. No code, deploy, restart, kill, DB
> migration, alembic, or Portal implementation in this window.

## Why this doc exists

`docs/context/NOW.md` was last refreshed 2026-06-07 and its runtime facts had
gone stale (live hash `d9b1c56`, "services active"). This window re-collects the
runtime truth at 2026-06-10 and freezes the real state so the next operating /
design window starts from evidence, not from the stale NOW snapshot.

## Fresh Evidence Pack (2026-06-10, Asia/Shanghai)

Repo: `/home/ops/projects/edu-cloud` · Branch: `feat/module-governance-repair`
· HEAD: `41a8cedd708f1cf3531090f42e808c85f415d4b8` (`41a8ced`) · worktree clean.

### EV-TRUTH-STATUS — `scripts/truth-status.sh` (15:45 +08)

```
[Source]  git HEAD: 41a8ced · frontend/ build inputs clean · src/ (backend) clean
[Build]   build git_hash: 41a8ced · dist/ matches current source
[Nginx]   https://mcu.asia/ returns 200 · version.json git_hash=41a8ced (matches source)
[Backend] pid=391900 boot=2026-06-09 17:02:19 git=ebf7934 · ✗ running ebf7934, source is 41a8ced
[Diagnosis] BROKEN AT: SOURCE → BACKEND (stale uvicorn, restart needed)
```

Source / build / nginx are aligned on `41a8ced`; only the **backend process is
stale** at `ebf7934`.

### EV-DB-DOCTOR — `scripts/db_doctor.py --json`

```json
{
  "db_path": "./edu_cloud.db",
  "alembic_version": "a1b2_chat_msgs",
  "orm_tables": 96,
  "db_tables": 97,
  "hard": 1,
  "warn": 1,
  "findings": [
    {"severity": "HARD", "category": "missing_table", "table": "exam_import_sessions",
     "detail": "ORM declares table 'exam_import_sessions' (16 cols) but DB has no such table"},
    {"severity": "WARN", "category": "orphan_table", "table": "_audit_log",
     "detail": "DB has table '_audit_log' (7 cols) not declared in ORM"}
  ]
}
```

### EV-GUARDIAN — `scripts/guardian-watch --once --no-network --no-model-review`

`overall=red`, `red=8 yellow=3`, fingerprint `1228767d7f7c63dc`:

- **BACKEND_DRIFT** (red) — backend hash `ebf7934` ≠ HEAD `41a8ced`
- **BACKEND_RUNTIME_DIRTY** ×2 (red) — `/api/v1/version` and running backend report `source_dirty=true`
- **DB_DOCTOR_FAILED** (red) — db doctor status=failed (driven by the HARD missing-table finding)
- **DB_SCHEMA_DRIFT** (red) — db_doctor `--strict` fails to run clean
- **PARALLEL_RUNTIME_DIRTY** (red) — backend on port 9000 reports `source_dirty=true`
- **PARALLEL_VERSION_DRIFT** (red) — port 9000 reports `ebf7934`, source HEAD `41a8ced`
- **PORT_OWNER_MISMATCH** (red) — port 9000 owned by `None`, expected `edu-cloud`
- **GHOST_PROCESS** (yellow) — port 9000 listener PID `391900` is an orphan
- **RISKY_ARTIFACT** (yellow) — `data/.db_migrate.lock`, `.codex` present
- **SERVICE_BYPASS** (yellow) — `edu-cloud.service` inactive while uvicorn `:9000` runs manually

## Blocker Verdict (vs the standing diagnosis)

| Standing blocker | 2026-06-10 verdict | Evidence |
|---|---|---|
| backend stale / orphan uvicorn / service inactive | **STILL BLOCKED** | truth-status `BROKEN AT: SOURCE → BACKEND`; guardian BACKEND_DRIFT + GHOST_PROCESS (PID 391900) + SERVICE_BYPASS + PORT_OWNER_MISMATCH + PARALLEL_VERSION_DRIFT |
| DB doctor missing `exam_import_sessions` + orphan `_audit_log` | **STILL BLOCKED** | db_doctor HARD missing_table `exam_import_sessions` (16 ORM cols, absent in DB) + WARN orphan_table `_audit_log` (7 cols); guardian DB_DOCTOR_FAILED + DB_SCHEMA_DRIFT |
| context stale | **CONFIRMED → fixed this window** | NOW.md was at 2026-06-07 with live hash `d9b1c56` + "services active"; both are false at 2026-06-10 (live `41a8ced`, `edu-cloud.service` inactive). NOW.md + ACTIVE_INDEX.md re-synced in this window. |

All three standing blockers are real and unchanged on the runtime side. Source,
build, and nginx are healthy at `41a8ced`; the foundation break is entirely in
**(a) the backend process** and **(b) the DB schema**.

## Root-cause assessment (no mutation performed)

1. **Backend stale** — A manually-started uvicorn (PID 391900, booted
   2026-06-09 17:02 at `ebf7934`) owns port 9000 while `edu-cloud.service` is
   inactive. This is an orphan/service-bypass condition, not a code defect.
   Mechanical fix is "restart through systemd", but see the ordering below.
2. **DB schema drift** — `exam_import_sessions` (declared by ORM, 16 cols) is
   absent from `edu_cloud.db`; `_audit_log` (7 cols) exists in the DB but is not
   declared by the ORM. `alembic_version = a1b2_chat_msgs`. A stale
   `data/.db_migrate.lock` is present. This requires a **migration design
   decision** (which revision creates `exam_import_sessions`; what to do with the
   orphan `_audit_log`; how to clear the stale lock safely) — it is explicitly
   NOT something to fix by `alembic upgrade` blindly (NOW.md "Do not run direct
   Alembic migration commands").

## Portal Phase 1 gating (unchanged)

Portal Phase 1 is **CONDITIONAL UNLOCK**
(`docs/plans/2026-06-07-phase09-portal-unlock-decision.md`). Both runtime
preconditions are still red as of 2026-06-10:

- ① DB doctor red → green: **still red** (missing table + orphan).
- ② deploy/runtime hash aligned to HEAD: **still drifted** (backend `ebf7934` ≠
  HEAD `41a8ced`; the prior NOW snapshot's `b763888`/`bfdbd50`/`56ccd03` hashes
  are themselves stale and have been corrected).

No Portal code may start until both go green.

## What this window did NOT do (boundary)

- No restart, no `kill` of PID 391900, no systemd action.
- No DB migration, no alembic command, no `.db_migrate.lock` removal.
- No source/code/frontend/backend edits.
- Only `docs/plans/2026-06-10-runtime-foundation-recovery.md`,
  `docs/context/NOW.md`, `docs/context/ACTIVE_INDEX.md` were written.

## Recommended next window

**DB migration design window first, then the R1-B runtime operation window.**

Rationale:

- A backend restart alone does NOT clear DB doctor red — `41a8ced` code would
  come up against a DB still missing `exam_import_sessions` (a table its ORM
  declares), so Portal precondition ① stays red regardless and exam-import code
  paths risk runtime errors. Restart-first buys nothing for the gate.
- The DB drift is the higher-risk, decision-bearing blocker (missing-table
  revision path, orphan `_audit_log` disposition, stale `data/.db_migrate.lock`)
  and must be designed before any runtime mutation touches the schema.
- The backend-stale fix (stop orphan PID 391900, restart through systemd, restore
  `edu-cloud.service` ownership of port 9000) is mechanically simple and is best
  executed as the **tail** of the migration rollout (apply migration → restart
  through systemd → re-run truth-status + db_doctor + guardian to confirm green),
  rather than as a separate earlier R1-B window that would leave the DB red.

So: design the DB migration first; fold the runtime restart into the rollout step
of that same plan's execution window.

## Window quality findings (self-audit)

- **QF-BRANCH-MISMATCH (execution-quality, severity: low)** — The active
  contract `yc-20260610-d97cdbe1` declared `branch: "main"` (carried over from
  the contract template default), while the actual edu-cloud worktree is on
  `feat/module-governance-repair` (EV-GIT-STATUS). The mismatch did **not**
  breach the write boundary — the validator confines writes by `repo` /
  `authority_paths`, not by `branch`, and all three writes stayed in
  `docs/plans` + `docs/context` — so it is a contract-authoring accuracy defect,
  not a scope violation. **Corrective guidance for the next contract author:**
  set `branch` from `git -C <repo> rev-parse --abbrev-ref HEAD` before
  validating, do not inherit the template's `main` default. Recorded in the
  closeout via a `plan_review` receipt (`finding-id QF-BRANCH-MISMATCH`).
