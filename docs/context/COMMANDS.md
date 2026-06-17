# Command Manual

Authoritative command reference for Codex work in `edu-cloud`.

## Start Of Work

```bash
cd /home/ops/projects/edu-cloud
scripts/codex-check
scripts/meta-check --task "current user task" --write-state
scripts/codex-context --no-network
git status --short --branch
```

`codex-check` is read-only. Default mode reports risks and exits 0. Use `--strict` when a non-zero exit is wanted for automation.

`scripts/codex-context` prints the 元守双核心 summary:
Meta Core / 元控核 covers direction, facts, task boundaries, context, Claude
read-only counter-review, and the completion evidence contract. Guardian Core /
守护核 covers dirty state, truthline, DB/migration gates, safety scanning,
frontend/backend build-runtime consistency, and environment hygiene.

## Meta Runtime

One-shot task-contract check:

```bash
scripts/meta-check --task "current user task"
scripts/meta-check --json --task "current user task"
```

Write the latest task-contract state for `scripts/codex-context`:

```bash
scripts/meta-check --task "current user task" --write-state
```

Exit gates:

```bash
# Legacy strict (local/dev): any non-green snapshot exits non-zero,
# including a non-blocking yellow such as a stale-but-recent NOW.md.
scripts/meta-check --strict --task "current user task"

# CI-safe: exit non-zero only for red or blocks_completion issues;
# a non-blocking yellow exits zero. Used by CI and codex-verify full.
scripts/meta-check --json --fail-on-blocking
```

Deep checks for long-running or design-heavy work:

```bash
scripts/meta-check --task "current user task" --write-state
scripts/meta-check --task "current user task" --check-drift --baseline-state logs/meta-state.json
scripts/meta-check --check-recent-plans
```

`scripts/meta-check` emits `meta.core.v1`. It checks active-context documents,
`NOW.md` freshness, migrated Meta lessons, Meta runtime registration, Claude
read-only boundaries, changed and recent plan/design/handoff evidence sections,
baseline task-contract drift, and task obligations inferred from the current
user instruction. It is synchronous and advisory: it may block completion when
red issues exist, but it does not edit files, run migrations, build, deploy, or
declare completion.

## Truthline

```bash
scripts/truth status
scripts/truth doctor
scripts/truth doctor --json
scripts/truth-status.sh /home/ops/projects/edu-cloud
scripts/truth-doctor.sh /home/ops/projects/edu-cloud
```

`truth status` checks source -> build -> nginx -> backend alignment. `truth doctor` checks ports, ghost processes, dist permissions, systemd state, Claude process count, and DB schema drift.
`truth doctor --json` emits Guardian Core issue/action data with schema
`guardian.doctor.v1`.

`scripts/truth-status.sh` exits 0 only when the diagnosis is aligned. Any
`BROKEN AT:` diagnosis exits non-zero and must block completion evidence.

## Guardian Runtime

One-shot local inspection:

```bash
scripts/guardian-watch --once --no-network --no-model-review
scripts/guardian-watch --once --json --no-network --no-model-review
```

Continuous runtime:

```bash
scripts/guardian-watch --watch --interval 15 --model-review claude
```

Optional GPT review requires an explicit read-only local wrapper:

```bash
scripts/guardian-watch --watch --model-review gpt --model-review-command "path/to/read-only-gpt-review risk"
```

Systemd install/update path:

```bash
sudo cp deploy/systemd/edu-cloud-guardian.service /etc/systemd/system/edu-cloud-guardian.service
sudo systemctl daemon-reload
sudo systemctl enable --now edu-cloud-guardian.service
systemctl is-active edu-cloud-guardian.service
```

The runtime writes `logs/guardian-state.json`, `logs/guardian-watch.jsonl`, and
rate-limited `logs/guardian-model-review-*.txt` reports. These are runtime logs
and are intentionally ignored by git.

Boundary:

- It is advisory and continuous.
- It does not auto-kill services, workers, port listeners, or Claude sessions.
- It does not auto-delete DB/WAL/SHM, dirty source files, backups, screenshots,
  experiment data, `.env`, or `.secrets`.
- It can schedule Claude only through the read-only
  `scripts/codex-consult-claude` wrapper.
- GPT review is supported only through `--model-review-command`; no GPT command
  is assumed safe by default.

## Frontend

```bash
cd /home/ops/projects/edu-cloud/frontend
npm run lint
npm run build
```

Preferred completion gate:

```bash
cd /home/ops/projects/edu-cloud
scripts/codex-verify frontend
```

Rules:

- `https://mcu.asia` is the only user-visible frontend verification URL.
- `localhost:*` is debug-only evidence.
- `scripts/codex-verify frontend` refuses dirty frontend build inputs by default.
- `--allow-dirty-build` is only for debug and must not be used for completion claims.
- The frontend gate validates local `frontend/dist/version.json` against HEAD
  and, with network enabled, validates `https://mcu.asia/version.json` against
  local dist.

## Backend

Targeted pytest:

```bash
.venv/bin/python -m pytest tests/path/test_file.py::test_name -q
```

No-new-failures gate:

```bash
.venv/bin/python scripts/pytest_delta.py
scripts/codex-verify backend
```

Pass extra pytest args through `codex-verify backend` after `--`:

```bash
scripts/codex-verify backend -- tests/test_api/test_health.py -q
```

Known failures baseline:

```bash
.quality/known-pytest-failures.txt
```

## Schema And Migrations

Read-only:

```bash
scripts/db_migrate --current
scripts/db_migrate --history
.venv/bin/python scripts/db_doctor.py --json
```

Mutating migration path:

```bash
scripts/db_migrate head
scripts/db_migrate <revision>
```

Schema verification:

```bash
scripts/codex-verify schema
```

Rules:

- Do not run direct `alembic upgrade` or `alembic downgrade` on the project DB.
- `scripts/db_migrate` performs lock -> backup -> dry-run -> doctor -> real upgrade -> doctor.
- If code touches ORM models or Alembic versions, run `scripts/codex-verify schema`.

## Safety Scan

```bash
scripts/codex-verify safety
scripts/codex-verify safety --repo-wide
```

The safety scan checks changed script files for:

- direct `alembic upgrade/downgrade`
- `cp` or `rsync` against `.db` files
- destructive git cleanup commands
- probable hardcoded API keys or private keys

`--repo-wide` additionally scans all non-ignored repository files for probable
API keys, private key blocks, and shell-level SQLite copy commands. Use it for
governance completion evidence and CI smoke.

## Claude Auxiliary Reviewer

This wrapper is the **optional read-only auxiliary path** only. Governed write
execution is a different channel: a Claude Code window opened via `yc start`
with an active Yuanshou V2 contract (see `AGENTS.md` "Claude Channels" and
`docs/context/CLAUDE_AUX.md`). Do not conflate the two.

Check auth:

```bash
scripts/codex-consult-claude --auth-status
```

Use Claude as a full-repo read-only reviewer:

```bash
scripts/codex-consult-claude review "review the current governance migration"
scripts/codex-consult-claude design "critique this implementation plan"
scripts/codex-consult-claude history "triage historical handoffs for active facts"
scripts/codex-consult-claude tests "find missing regression tests"
scripts/codex-consult-claude risk "look for migration/data/secret/delivery risks"
```

Boundary:

- Claude can read the repo with `Read`, `Grep`, `Glob`, and `LS`.
- Claude cannot write files or run Bash.
- Claude runs without session persistence.
- Codex must apply changes and run verification.

## Full Verification

```bash
scripts/codex-verify full
scripts/codex-verify full --schema
```

`full` runs backend and frontend gates. `--schema` adds DB/Alembic verification.

## CI Governance Job

`.github/workflows/test.yml` includes a lightweight `governance` job that runs:

```bash
python -m py_compile scripts/codex_support.py scripts/codex-context scripts/codex-check scripts/codex-consult-claude scripts/codex-verify scripts/meta_runtime.py scripts/meta-check scripts/guardian_runtime.py scripts/guardian-watch scripts/run-arq-worker
python -m pytest tests/governance/test_codex_scripts.py -q
scripts/codex-check --no-network
scripts/meta-check --json --fail-on-blocking
scripts/codex-context --no-network
scripts/codex-consult-claude --dry-run review CI smoke
scripts/codex-verify safety --repo-wide
scripts/codex-verify full --dry-run --schema --no-network
```

This CI job validates the Codex governance layer itself. It is intentionally smoke-level; task completion still needs the real mode-specific verification command.

The existing CI backend/frontend jobs also include:

```bash
python -m pytest tests/test_alembic_migration.py -q
cd frontend && npm run build
```
