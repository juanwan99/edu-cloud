# DB Migration + Runtime Takeover Design — 2026-06-10

> Status: **design / investigation only** (no runtime mutation performed in this window).
> Executor authority this window: read-only evidence collection +
> `docs/plans/2026-06-10-db-migration-design.md`, `docs/context/NOW.md`,
> `docs/context/ACTIVE_INDEX.md` only. **No** alembic upgrade/downgrade, **no**
> `db_migrate`, **no** service restart/stop, **no** kill/pkill, **no** edits to
> `src/`, `frontend/`, `alembic/`, **no** direct DB writes.
> This document specifies the work for a *later* governed execution window; it
> does not perform it.

This design supersedes nothing; it operationalizes the "DB migration design
window first, then the runtime operation window" recommendation in
`docs/plans/2026-06-10-runtime-foundation-recovery.md` into an executable,
verifiable, reversible runbook.

---

## Fresh Evidence Pack (2026-06-10, Asia/Shanghai)

Repo: `/home/ops/projects/edu-cloud` · Branch: `feat/module-governance-repair` · worktree clean.

### EV-GIT — `git status --short --branch` / `git log --oneline --decorate -8`

```
## feat/module-governance-repair        # clean (no dirty tracked files)
44d3e62 (HEAD) docs: 同步 2026-06-10 运行态地基恢复状态
41a8ced feat(ai): productize coze-first agent provider
ebf7934 chore(guardian): disable automatic Claude model review
a478b34 docs: 持久化 Portal Phase 1 条件解锁裁定
56ccd03 docs: 持久化 Phase 0.8 地基验收与 Portal 解锁裁定
...
```

`git show --stat 44d3e62` → **docs-only** (`docs/context/NOW.md`,
`docs/context/ACTIVE_INDEX.md`, `docs/plans/2026-06-10-runtime-foundation-recovery.md`,
+191/-11). **Code-effective HEAD = `41a8ced`**; `44d3e62` adds no `src/`/`frontend/` change.

### EV-ALEMBIC — `alembic current` / `alembic heads` / `alembic history`

```
current : a1b2_chat_msgs
heads   : e1f2_import_sess (head)
history : a1b2_chat_msgs -> e1f2_import_sess (head), add exam_import_sessions table
```

The DB is **exactly one revision behind head**. The single step `a1b2_chat_msgs → e1f2_import_sess` is linear, no branches.

### EV-DB-DOCTOR — `scripts/db_doctor.py --json` (exit 1)

```json
{
  "db_path": "./edu_cloud.db",
  "alembic_version": "a1b2_chat_msgs",
  "orm_tables": 96, "db_tables": 97,
  "hard": 1, "warn": 1,
  "findings": [
    {"severity":"HARD","category":"missing_table","table":"exam_import_sessions",
     "detail":"ORM declares table 'exam_import_sessions' (16 cols) but DB has no such table"},
    {"severity":"WARN","category":"orphan_table","table":"_audit_log",
     "detail":"DB has table '_audit_log' (7 cols) not declared in ORM"}
  ]
}
```

### EV-MIGRATION — `alembic/versions/e1f2_add_exam_import_sessions.py`

`revision = "e1f2_import_sess"`, `down_revision = "a1b2_chat_msgs"`.
`upgrade()` = single `op.create_table("exam_import_sessions", …)` with **16 columns**
(`id, school_id→schools.id, exam_name, exam_type, grade_scope, import_mode, status,
file_path, preview_data, mapping_data, result_summary, committed_by, exam_id→exams.id,
exam_date, created_at, updated_at`). `downgrade()` = `op.drop_table("exam_import_sessions")`.
No data transform. Both parent FK tables (`schools`, `exams`) already exist.

### EV-ORM — `src/edu_cloud/modules/exam_import/models.py`

`class ExamImportSession(Base, IdMixin, TimestampMixin)` → `__tablename__ = "exam_import_sessions"`.
`IdMixin` (`id`) + `TimestampMixin` (`created_at`, `updated_at`) + 13 explicit columns = **16 columns**,
name/type-aligned column-by-column with the migration. ✅ migration ≡ ORM.

### EV-AUDIT — `_audit_log` provenance (READ-ONLY `mode=ro` query)

```
_audit_log: id INTEGER PK AUTOINCREMENT, table_name, operation, row_id,
            old_data JSON NOT NULL, created_at (strftime '+08:00','+8 hours'), session_info
            rows = 6330
audit_logs (ORM table, separate): rows = 0
triggers feeding _audit_log (4 total in DB):
  _audit_log_cleanup           ON _audit_log        (housekeeping)
  audit_grading_results_update ON grading_results
  audit_grading_results_delete ON grading_results
  audit_student_answers_update ON student_answers
```

`_audit_log` is an **intentional trigger-based audit table** capturing pre-change
`old_data` snapshots for `grading_results` (UPDATE/DELETE) and `student_answers`
(UPDATE). The leading underscore marks it as a deliberate system/internal table,
never intended as an ORM model. It holds **6330 rows of real grading-rollback data**.
The ORM-declared `audit_logs` (plural, app-level, written by `audit_service.py`) is a
*different*, currently-empty table.

`db_doctor` allowlist (`scripts/db_doctor.py:29-33`): `ALLOWLIST_TABLES = {"alembic_version"}`,
pattern `^_backup_.*_\d{8}$`. `_audit_log` matches neither → reported as orphan WARN.

### EV-RUNTIME — `/api/v1/version` + `systemctl is-active`

```
version : {"version":"0.1.0","boot_time":"2026-06-09 17:02:19",
           "git_hash":"ebf7934","source_dirty":true,"pid":391900}
services: edu-cloud.service          inactive   ← main backend NOT under systemd
          edu-cloud-worker.service   active
          edu-cloud-guardian.service active
```

Port 9000 is owned by an **orphan manual uvicorn** (pid 391900, booted 2026-06-09,
running `ebf7934` with `source_dirty=true`), while the systemd `edu-cloud.service`
unit is installed but **inactive**. (`systemctl cat edu-cloud.service` → permission
denied without sudo; unit exists since `is-active` resolves it.)

### EV-WRAPPER — `scripts/db_migrate` + stale lock

`scripts/db_migrate` is the sanctioned migration path: **backup → dry-run on a temp
DB copy → `db_doctor --strict` → real upgrade**, guarded by an `fcntl.flock` on
`data/.db_migrate.lock`. A stale `data/.db_migrate.lock` (0 bytes, May 13) exists;
because the lock is advisory `flock` (released on process exit), the leftover empty
file is harmless — but the execution window must confirm **no live holder** before migrating.

---

## Root Cause

Two independent drifts, same window, must not be conflated:

1. **DB schema drift (HARD).** Source advanced to migration head `e1f2_import_sess`
   (adds `exam_import_sessions`) but the live `edu_cloud.db` was never upgraded past
   `a1b2_chat_msgs`. ORM expects the table; DB lacks it. Root cause: a new migration
   shipped in source without the corresponding DB upgrade being applied to the live DB.

2. **Runtime drift (operational, surfaced as guardian SERVICE_BYPASS / GHOST_PROCESS /
   PORT_OWNER_MISMATCH).** The backend on :9000 is a hand-launched uvicorn (pid 391900,
   `ebf7934`, `source_dirty`) instead of the systemd-managed `edu-cloud.service` (which
   is inactive). Root cause: a manual restart bypassed systemd and was never handed back.

The `_audit_log` WARN is **not** a drift to repair — it is a recognized, data-bearing
system table that `db_doctor`'s allowlist has simply never been told about.

---

## Required Answers

### Q1 — Is the missing `exam_import_sessions` table solved by `e1f2_import_sess`?

**Yes, fully and exactly.** `e1f2_import_sess` is the single head revision directly
above the live `a1b2_chat_msgs`. Its `upgrade()` creates `exam_import_sessions` with
the same 16 columns (verified name-and-type against the ORM in EV-MIGRATION/EV-ORM).
Applying `a1b2 → e1f2` creates the table → the HARD `missing_table` finding clears. No
other migration touches this table. Fully reversible via `downgrade()` (`drop_table`),
which is safe because the freshly created table is empty.

### Q2 — How to dispose of the `_audit_log` orphan?

**KEEP it; register it; do NOT drop it.** Evidence (EV-AUDIT) shows `_audit_log` is an
intentional trigger-backed audit table with **6330 rows** of pre-change `old_data`
snapshots for `grading_results` and `student_answers`, plus its own cleanup trigger.
Dropping it would (a) destroy 6330 rows of grading-rollback/audit data and (b) break 4
triggers, after which `UPDATE`/`DELETE` on `grading_results` and `student_answers`
would fail at the DB layer. It is deliberately not an ORM model (underscore = system table).

Correct disposition: in the execution window, add `"_audit_log"` to
`ALLOWLIST_TABLES` in `scripts/db_doctor.py:29-31` so the orphan WARN clears as a
"recognized system table". This is a tooling-config change, **not** part of the alembic
migration, **not** a DB write, and trivially reversible by reverting the edit.
(Optional follow-up: a one-paragraph schema/runbook note documenting the table + its triggers.)

> Decision flag for the designer: whether C1 ("DB doctor red→green") requires the
> `_audit_log` WARN to be allowlisted (truly 0/0) or whether HARD=0 with a single
> documented WARN already satisfies the gate. Recommendation: allowlist it so the gate
> is unambiguous green.

### Q3 — Can the next window execute DB migration + backend systemd takeover?

**Yes — conditionally, in a separate governed window** whose contract explicitly
authorizes (a) a DB write via `scripts/db_migrate` and (b) systemd service control +
the controlled stop of orphan pid 391900. (This current window forbids all of these.)
Both operations belong in one window because the migration is a single isolated,
reversible `CREATE TABLE` (no data transform) and the systemd restart is its natural
tail — it both brings the backend to HEAD code and lets it see the new table. The
order is strict: **migrate first, restart second** (a restart alone does not clear the
DB red — the `41a8ced` code would still query a missing table).

Preconditions before that window opens:

- worktree clean on `feat/module-governance-repair` (currently clean apart from this
  window's doc edits, which should be committed/landed first).
- `alembic current` = `a1b2_chat_msgs`, `alembic heads` = `e1f2_import_sess` (single forward step).
- a DB backup is captured (the `db_migrate` wrapper does this automatically; also keep an
  independent `sqlite3 .dump`).
- no live `flock` holder on `data/.db_migrate.lock`.
- the installed unit's `ExecStart`/`WorkingDirectory` (via `sudo systemctl cat
  edu-cloud.service`) is confirmed to point at `/home/ops/projects/edu-cloud` current checkout.

### Q4 — Execution order, verification commands, failure/rollback strategy

**Pre-flight (read-only):**

```bash
git status --short --branch                                  # clean on feat/module-governance-repair
.venv/bin/alembic current                                    # == a1b2_chat_msgs
.venv/bin/alembic heads                                      # == e1f2_import_sess (head)
.venv/bin/python scripts/db_doctor.py --json                 # HARD=1 missing exam_import_sessions, WARN=1 _audit_log
lsof data/.db_migrate.lock 2>/dev/null || echo "no live holder"   # confirm no running db_migrate
```

**Step 1 — DB migration (sanctioned wrapper, NOT raw `alembic upgrade`).**
Rollback point **R1** = the automatic pre-migration backup written to `backups/`
(verify it exists & is non-empty before trusting the upgrade).

```bash
scripts/db_migrate          # backup → dry-run on temp DB copy → db_doctor --strict → real upgrade to head
# verify:
.venv/bin/alembic current                                    # == e1f2_import_sess
.venv/bin/python scripts/db_doctor.py --json                 # HARD=0; exam_import_sessions present (16 cols)
```

Rollback if Step 1 fails:

```bash
.venv/bin/alembic downgrade a1b2_chat_msgs   # clean drop_table; loses no business data (table was empty)
# OR restore from the R1 pre-migration backup (sqlite3 .dump restore) if state is ambiguous
```

**Step 2 — `_audit_log` disposition (tooling, same window or immediate follow-up).**

```bash
# edit scripts/db_doctor.py:29-31 → add "_audit_log" to ALLOWLIST_TABLES
.venv/bin/python scripts/db_doctor.py --json                 # WARN=0 → fully green
```

Rollback: revert the one-line edit. No DB change.

**Step 3 — Backend systemd takeover (tail of the rollout).**
Rollback point **R2** = current orphan-backend state (explicitly *not* a state we want
to revive — fix-forward only).

```bash
sudo systemctl cat edu-cloud.service                         # confirm ExecStart/WorkingDirectory
# controlled stop of orphan pid 391900 via the contract-authorized stop path, then:
sudo systemctl restart edu-cloud.service
# verify:
systemctl is-active edu-cloud.service                        # == active
ss -ltnp 'sport = :9000'                                     # owner = systemd unit's uvicorn (NOT pid 391900)
curl -s http://127.0.0.1:9000/api/v1/version                 # git_hash == HEAD, source_dirty=false, new pid
scripts/truth-status.sh /home/ops/projects/edu-cloud         # no "BROKEN AT:" line (exit 0)
scripts/guardian-watch --once --no-network --no-model-review # no SERVICE_BYPASS / GHOST_PROCESS / PORT_OWNER_MISMATCH
```

Rollback if Step 3 fails:

```bash
sudo systemctl stop edu-cloud.service
journalctl -u edu-cloud.service -n 100      # diagnose bind/boot failure → fix-forward
```

If systemd cannot bind, **do NOT silently relaunch a manual uvicorn** — return to the
planner. nginx static + frontend stay up regardless; only `/api/*` is degraded during
the gap, so keep the verify loop tight.

**Final acceptance (all green):**

```
db_doctor:     HARD=0, WARN=0 (after Step 2)
alembic:       current == e1f2_import_sess == head
truth-status:  source == build == nginx == backend, no "BROKEN AT:"
version:       git_hash == HEAD (44d3e62 / code 41a8ced), source_dirty=false
```

### Q5 — When does Portal Phase 1 unlock?

Portal Phase 1 is already adjudicated **CONDITIONAL UNLOCK**
(`docs/plans/2026-06-07-phase09-portal-unlock-decision.md`, `56ccd03`), gated by three
runtime conditions. This design + the next execution window directly clear two of them:

| Cond | Description | Cleared by |
|---|---|---|
| C1 | DB doctor red→green | Step 1 (`exam_import_sessions`) + Step 2 (`_audit_log` allowlist) |
| C2 | deploy/runtime hash aligned to HEAD (**3 surfaces: backend + dist + nginx**) | backend via Step 3 (systemd takeover → backend at HEAD, `source_dirty=false`); **dist/nginx via the "Frontend dist / BUILD_DRIFT Alignment" section** — local dist already at code-HEAD `41a8ced`, but the nginx surface is unverified and a docs-only HEAD trips a *false* `BUILD_DRIFT`; both must be cleared there, **not assumed** |
| C3 | online module gating / portal services fail-closed intact | verified independently (guardian + module-gating tests); unaffected by this migration |

Therefore Portal Phase 1 unlocks **after** the next execution window verifies C1+C2
green and re-confirms C3 — and the unlock itself is a **designer/planner decision, not
an executor self-unlock**. The executor delivers the green evidence; the designer then
authorizes Phase 1 implementation start. Earliest realistic point: immediately after a
clean execution-window closeout (db_doctor 0/0 + truth-status no-`BROKEN AT` +
version == HEAD), pending designer sign-off.

---

## Frontend dist / BUILD_DRIFT Alignment (Portal C2 — dist sub-track)

The runtime-takeover steps above clear **backend** hash drift only. Portal C2
("deploy/runtime hash aligned to HEAD") is a **three-surface** gate — backend **and**
frontend dist **and** nginx — and the dist/nginx surface was previously asserted
"already aligned" without evidence. This section supplies the missing evidence and the
dist-side next-execution requirements.

### EV-DIST — `frontend/dist/version.json` + nginx (2026-06-10, read-only)

```
HEAD                       : 44d3e62 (docs-only; code-effective 41a8ced)
frontend/dist/version.json : git_hash=41a8ced, source_dirty=false,
                             build_time=2026-06-09T10:07:40Z, build_id=build-1780999232395
nginx-served version.json  : NOT VERIFIED this window
                             (127.0.0.1:9000/version.json → {"detail":"Not Found"} = backend API, no such route;
                              127.0.0.1/version.json → 502; authoritative source is the external
                              https://mcu.asia/version.json — deferred to the exec window)
phase09 last-measured (2026-06-07, guardian.watch.v1): dist_hash=bfdbd50, nginx_hash=bfdbd50 (both ≠ HEAD)
```

The dist fingerprint has **already advanced** from phase09's `bfdbd50` to `41a8ced`
(= code-effective HEAD), `source_dirty=false`. That is the entire basis of the earlier
"dist already aligned" claim — but it is **only the local-dist-vs-code half**, and it is
undercut by the two unresolved facts below.

### BUILD_DRIFT gates (all `blocks_completion=True`)

`scripts/guardian_runtime.py:196-235` raises, on **raw HEAD** comparison:

| Gate | Condition | Fix command |
|---|---|---|
| `BUILD_DRIFT` | `dist.source_dirty == true` | `cd frontend && npm run build` |
| `BUILD_DRIFT` | `dist_hash != HEAD` | `scripts/codex-verify frontend` |
| `NGINX_DRIFT` | `nginx_hash != dist_hash` | `scripts/codex-verify frontend` |

`scripts/truth-status.sh` ([Build]/[Nginx] sections) and `scripts/codex-verify`
(`frontend_version_alignment_errors`) use the **same raw-HEAD** basis.

### Two unresolved facts (why "dist already aligned" is not yet provable green)

1. **nginx surface unverified.** Local `dist/version.json=41a8ced` does NOT prove the
   nginx document root *serves* that build. phase09 measured nginx at the stale
   `bfdbd50`; this window could not reach the authoritative `https://mcu.asia/version.json`.
   Until that hash is read, `NGINX_DRIFT` (`nginx_hash != dist_hash`) and C2's
   "`https://mcu.asia/version.json` == HEAD" leg remain **open**.

2. **docs-only HEAD trips a *false* BUILD_DRIFT.** HEAD `44d3e62` is docs-only, so
   `dist_hash=41a8ced != HEAD=44d3e62` → guardian raises `BUILD_DRIFT` **red,
   blocks_completion**, even though code is identical (truth-status / codex-verify
   agree). This is R-6's docs-only effect surfacing on the **dist/guardian** surface,
   where — unlike the informational backend version line — it **hard-blocks the
   execution window's closeout**. It must be resolved, not merely noted.

### Next-execution requirements (dist sub-track — governed exec window; parallelizable with backend takeover)

**Pre-flight (read-only):**

```bash
git rev-parse --short HEAD                                   # code-effective HEAD
python3 -c "import json;d=json.load(open('frontend/dist/version.json'));print(d['git_hash'],d['source_dirty'])"
curl -s https://mcu.asia/version.json | python3 -c "import json,sys;print(json.load(sys.stdin)['git_hash'])"  # nginx_hash (AUTH)
```

**Decision tree:**

- **If** `nginx_hash == dist_hash == code-effective-HEAD` and `source_dirty=false`
  → nginx already serves the correct dist; **no rebuild/redeploy needed**. Only the
  docs-only false-positive (below) remains.
- **If** `nginx_hash` is stale (e.g. `bfdbd50`) `!= dist_hash`
  → redeploy the local `dist/` to the nginx document root (frontend **source unchanged**;
  if a fresh fingerprint is needed, `scripts/codex-verify frontend` runs lint+build —
  it *refuses* if `frontend/src` build inputs are dirty). Then re-confirm
  `https://mcu.asia/version.json` == dist_hash.

**Resolve the docs-only false BUILD_DRIFT (required for a green closeout):**
After this window's 3 docs land (HEAD advances by one more docs-only commit), the exec
window should **rebuild dist on the then-current HEAD** so `dist.git_hash == HEAD`
exactly. The build is content-identical (docs commits change no `frontend/src`); only
the fingerprint advances. This is the sanctioned way to clear the `dist_hash != HEAD`
gate — do **not** patch guardian to special-case docs commits.

**Acceptance (dist sub-track green):**

```
frontend/dist/version.json    : git_hash == HEAD, source_dirty=false
https://mcu.asia/version.json : git_hash == dist_hash == HEAD
truth-status.sh               : [Build] + [Nginx] no "BROKEN AT: SOURCE→BUILD" / "BUILD→NGINX"
guardian                      : BUILD_DRIFT=0, NGINX_DRIFT=0
```

**Ordering:** the dist sub-track is **independent of and parallelizable with** the DB
migration + backend takeover; all three surfaces (DB green, backend at HEAD, dist+nginx
at HEAD) must be green before Portal C2 is judged cleared. Recommended: migrate DB →
(parallel) backend systemd takeover + dist rebuild/redeploy → re-verify all three hashes.

---

## Risk Register

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R-1 | Migration corrupts DB | Low | Single empty `CREATE TABLE`, no data transform; `db_migrate` wrapper backs up + dry-runs first; fully reversible via `downgrade`. |
| R-2 | FK targets missing | Low | `schools` and `exams` both exist; new table is empty → no orphan rows possible. |
| R-3 | `_audit_log` dropped by mistake | High-if-occurs | Explicit "KEEP, allowlist not drop" policy (Q2); 4 triggers + 6330 rows depend on it. |
| R-4 | Takeover API downtime / bind race | Medium | Tight verify loop (`ss`/`version`/`truth-status`); nginx static stays up; fix-forward, never revive orphan. |
| R-5 | Stale `.db_migrate.lock` blocks/false-locks | Low | Advisory `flock`, auto-released; verify no live holder pre-flight; leftover empty file harmless. |
| R-6 | HEAD docs-only advance confuses the **backend** version line | Low | `44d3e62` is docs-only; backend reports `git_hash=44d3e62`, code ≡ `41a8ced`. Informational only — expected, accept. (The dist/guardian surface is R-7, which is **not** acceptable as-is.) |
| R-7 | docs-only HEAD trips guardian `BUILD_DRIFT` (`dist_hash 41a8ced != HEAD 44d3e62`), which **blocks_completion** | Medium | Hard-blocks the exec-window closeout (unlike informational R-6). Resolve by rebuilding dist on the post-docs HEAD (content-identical, fingerprint-only) so `dist_hash == HEAD`; never special-case guardian. See "Frontend dist / BUILD_DRIFT Alignment". |
| R-8 | nginx still serves stale dist (`bfdbd50`) despite local dist at code-HEAD | Medium | Local `dist/version.json` does not prove what nginx serves. Read `https://mcu.asia/version.json` first; if stale, redeploy dist to the nginx root, then re-verify `NGINX_DRIFT=0`. |

---

## Scope Boundary For The Execution Window

- **Touch:** live `edu_cloud.db` (via `scripts/db_migrate` only), `scripts/db_doctor.py`
  (allowlist line only), `edu-cloud.service` (systemctl), orphan pid 391900 (controlled
  stop), and **`frontend/dist/` build output** (rebuild via `scripts/codex-verify frontend`
  + redeploy to the nginx document root, to clear `BUILD_DRIFT`/`NGINX_DRIFT` — dist sub-track).
- **Do NOT touch:** `src/`, **`frontend/src/` · `frontend/public/` · `frontend/package.json`
  · `frontend/vite.config*` (frontend *source* / build inputs — rebuild only, never edit)**,
  `alembic/versions/**` (the migration is already correct — do not edit it), `DEFAULT_ENABLED`
  / module middleware / authGuard / module-semantics (frozen foundation per phase09).
- **Do NOT** drop `_audit_log`, run raw `alembic upgrade` (use the wrapper), or relaunch a
  manual uvicorn as a takeover fallback.
