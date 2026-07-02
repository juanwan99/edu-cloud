---
title: Command Manual
owner: liang
last_review_date: "2026-07-02"
expiration_in_days: 30
---

# Command Manual

Authoritative command reference for current Codex work in `edu-cloud`.

## Start Of Work

```bash
scripts/codex-check
scripts/codex-context --no-network
git status --short --branch
```

`scripts/codex-check` and `scripts/codex-context` are read-only. They do not
replace reading the relevant source files before editing.

## Keel PR Flow

```bash
git switch -c keel/<short-task>-YYYY-MM-DD
# create control/steward/scopes/<scope_id>.yml
# keep changed files inside allowed_paths
# include this exact marker in the PR body:
Steward-Scope: <scope_id>
# include Codex/non-implementer review evidence issued before implementation:
Codex-Dispatch-Review: <CDR-id-or-GitHub-comment-url>
```

The scope file is a one-time authorization for that PR. Do not reuse it after
merge. Its lifecycle boundary is the fresh scope file newly added in the PR and
an `expires_at` that stays in the future while the scope is active. Closeout-only
PRs remain supported for historical compatibility or explicit maintenance, but
they are not the normal post-merge path.

The default PR template contains `Steward-Scope: REQUIRED`. Replace `REQUIRED`
with the exact scope id before opening or updating the PR.

The default PR template also contains `Codex-Dispatch-Review: REQUIRED`.
Replace it with the CDR id or GitHub comment URL issued before implementation.

`steward/dispatch-review` enforces a fresh `keel/` branch from latest
`origin/master`, non-placeholder CDR evidence, a completed Dispatch Review
checklist, and no retired `batch/*` branch reuse.

## Dispatch Review Preflight

Before multi-worker, deletion/retirement, governance, central-context, or
protected-path work, Codex must complete Dispatch Review:

```bash
git status --short --branch
git diff --name-status origin/master...HEAD
```

For deletion or retirement work, collect reachability evidence before editing:

```bash
git grep -n "<filename-or-command>" -- .github scripts tests docs/context docs/governance
git grep -n "<basename>" -- . ":!docs/archive"
git show origin/master:.github/workflows/test.yml
```

If a file is still referenced by scripts, tests, workflows, active docs, or
governance registries, do not delete it in that worker. First retire or update
the referencing contract in a scoped PR.

## Local Safety

```bash
scripts/codex-verify safety
scripts/codex-verify safety --repo-wide
```

The safety scan checks changed script files for direct Alembic mutation,
SQLite-copy shell commands, destructive git cleanup, probable API keys, and
private key blocks. `--repo-wide` also scans non-ignored repo files for secrets
and shell-level SQLite copy commands.

## Backend

Targeted pytest:

```bash
.venv/bin/python -m pytest tests/path/test_file.py::test_name -q
```

No-new-failures gate:

```bash
scripts/codex-verify backend
```

`scripts/codex-verify backend` with no targets runs the CI-aligned backend
profile from `scripts/codex-verify`. Pass targeted pytest args after `--`:

```bash
scripts/codex-verify backend -- tests/test_api/test_health.py -q
```

## Frontend

```bash
cd frontend
npm ci --ignore-scripts
npx vitest run
npm run build
npm audit --audit-level=high
```

Preferred completion gate:

```bash
scripts/codex-verify frontend
```

`localhost:*` is debug evidence only. User-visible completion evidence uses
`https://mcu.asia` when the task requires live frontend verification.

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

Do not run direct `alembic upgrade` or `alembic downgrade` on the project DB.
Use `scripts/db_migrate`.

## GitHub CI

Post-push check:

```bash
scripts/codex-verify github-ci --wait
```

This binds the GitHub Actions result to the current branch and exact HEAD SHA,
so an older green run cannot mask a new red push.

## Claude Auxiliary Reviewer

Claude is optional and read-only unless the user explicitly starts a separate
implementation flow.

```bash
scripts/codex-consult-claude --auth-status
scripts/codex-consult-claude review "review the current governance migration"
scripts/codex-consult-claude design "critique this implementation plan"
scripts/codex-consult-claude tests "find missing regression tests"
scripts/codex-consult-claude risk "look for migration/data/secret/delivery risks"
```

Codex must apply changes and run verification. Claude review is not merge
authority.

## Claude Worker Profiles

Use Claude as an executor only after the steward issues a scoped startup packet.
Generated module profiles are the permission source of truth:

```bash
python scripts/governance/gen_worker_profile.py --check
python scripts/governance/gen_worker_profile.py --write
```

The default native Windows worker profile is no-shell and allowlist based.
Standard startup loads the generated settings file and must not pass
`--permission-mode`, `--dangerously-skip-permissions`, or
`--allow-dangerously-skip-permissions`:

```powershell
claude --safe-mode --no-session-persistence `
  --settings control\steward\worker-profiles\modules\grading.settings.json `
  --tools Read,Edit,Write `
  -p "<worker startup packet>"
```

Rules for this profile:

- select the exact module settings file from
  `control/steward/worker-profiles/modules/`;
- the settings file sets `defaultMode: dontAsk`,
  `disableBypassPermissionsMode: disable`, `Read` plus exact module/test write
  paths, and denies Bash, PowerShell, `.claude/**`, sibling modules, and central
  protected paths;
- do not use `--permission-mode`, `--dangerously-skip-permissions`,
  `--allow-dangerously-skip-permissions`, or `bypassPermissions`;
- do not make `acceptEdits` the worker default;
- do not grant Bash or any shell-equivalent tool;
- before first real use of a profile, perform an out-of-bound write probe and
  paste the deny output into the PR;
- the worker does not run shell commands, tests, or git locally; Codex, the
  steward, or CI runs verification and git operations;
- if shell or test authority is required, use a WSL2/container sandbox profile
  instead of the native Windows no-shell profile.

## Full Verification

```bash
scripts/codex-verify full
scripts/codex-verify full --schema
```

`full` runs safety, backend, and frontend gates. `--schema` adds DB/Alembic
verification.

## CI Governance Job

`.github/workflows/test.yml` includes a lightweight `governance` job that runs
the current Codex/Keel smoke checks:

```bash
python -m py_compile scripts/codex_support.py scripts/codex-context scripts/codex-check scripts/codex-verify scripts/run-arq-worker
python scripts/governance/check_execution_policy.py
python -m pytest tests/governance/test_codex_scripts.py -q
python scripts/governance/check_legacy_quarantine.py --check
python scripts/governance/check_doc_pollution.py --check
python scripts/governance/check_ai_tool_modules.py --check
python scripts/governance/check_module_dependencies.py --check
python scripts/governance/check_permission_mirror.py --check
python scripts/governance/module_governance_guard.py --check
scripts/codex-check --no-network
scripts/codex-context --no-network
scripts/codex-verify safety --repo-wide
scripts/codex-verify full --dry-run --schema --no-network
```

`steward-hard-gates.yml` runs `scripts/governance/steward_scope_gate.py` with
the GitHub PR event and changed-file list. Task completion still needs the real
mode-specific verification command and GitHub required checks.
