# R-H1 Worker Runtime Fingerprint Closeout

Date: 2026-06-22 Asia/Shanghai
Branch: `feat/module-governance-repair`
Evidence HEAD: `f18a5076f697b636fc3d758a76d974b6eccebac9`
Runtime activation: 2026-06-22 22:33 Asia/Shanghai

Scope: close the R-H1 worker freshness blind spot. This packet records the code,
CI, runtime, and guardian evidence that worker process version/boot freshness is
now observable and checked. It does not change product behavior, DB data,
module semantics, auth guards, or Portal contracts.

## Decision

R-H1 后半 is closed for the current baseline.

The original R-H1 stale-worker incident was already corrected on 2026-06-10 by
restarting the worker, but the system still lacked a mechanical probe that could
prove the currently running worker matched source HEAD. Commit `f18a507` adds
that missing edge: the worker now writes a runtime fingerprint, truthline reads
it, and guardian fails on missing/stale/drifted worker state.

## Root Cause Closed

- Symptom: backend/build/nginx could be aligned while the ARQ worker had no
  version/boot freshness truthline.
- Root cause: worker startup did not publish a runtime identity, so guardian
  could not compare worker git hash, boot time, dirty flag, and service PID
  against source and systemd.
- Leverage point: make the worker emit `logs/worker-runtime.json` at startup and
  teach truthline/guardian/codex context to treat worker drift as first-class
  runtime evidence.

## Fresh Evidence

### Code And Test Surface

Commit:

```bash
git show --stat --oneline --decorate --no-renames f18a507 -- \
  src/edu_cloud/worker.py \
  scripts/codex_support.py \
  scripts/guardian_runtime.py \
  scripts/truth-status.sh \
  scripts/codex-context \
  tests/test_workers/test_worker_startup.py \
  tests/governance/test_codex_scripts.py
```

Result: `7 files changed, 358 insertions(+), 12 deletions(-)`.

Key changes:

- `src/edu_cloud/worker.py` records worker runtime fingerprint on startup.
- `scripts/truth-status.sh` reports worker pid, service pid, boot time,
  recorded time, and git hash, then compares worker hash to source.
- `scripts/guardian_runtime.py` raises worker-specific issues for missing,
  stale, drifted, or dirty worker runtime state.
- `scripts/codex_support.py` and `scripts/codex-context` expose worker truthline
  data to local governance checks.
- Worker startup and governance tests cover the new fingerprint and drift paths.

### GitHub Actions Exact-HEAD

Command:

```bash
gh run view 27958619284 --json status,conclusion,headSha,jobs,url
```

Result:

- run URL: `https://github.com/juanwan99/edu-cloud/actions/runs/27958619284`
- status: `completed`
- conclusion: `success`
- head SHA: `f18a5076f697b636fc3d758a76d974b6eccebac9`
- jobs: `governance=success`, `frontend=success`, `backend=success`

### Runtime Activation

Operator command executed on ECS:

```bash
cd /home/ops/projects/edu-cloud
git fetch origin
git merge --ff-only origin/feat/module-governance-repair
cd frontend && npm run build && cd ..
sudo systemctl restart edu-cloud.service edu-cloud-worker.service
sleep 5
scripts/truth-status.sh /home/ops/projects/edu-cloud
scripts/truth-doctor.sh
scripts/guardian-watch --once --no-network --no-model-review --json > /tmp/rh1-guardian.json
```

Result:

- source HEAD: `f18a507`
- frontend build `git_hash=f18a507`
- nginx serves `version.json` with `git_hash=f18a507`
- backend pid `887585`, boot `2026-06-22 22:33:05`, git `f18a507`
- worker pid `887586`, service pid `887586`, boot `2026-06-22T14:33:05Z`,
  recorded `2026-06-22T14:33:05Z`, git `f18a507`
- diagnosis: `ALL ALIGNED - source, build, nginx, backend, worker versions match`
- truth doctor: `HEALTHY - no issues found`

### Artifact Cleanup And Final Guardian

The first post-activation guardian run was `yellow` only because two stale local
artifacts were present: `data/.db_migrate.lock` and `.codex/`. Investigation
showed `.codex/context/CODEX_CONTEXT.md` was generated on 2026-05-18 and
contained obsolete dirty-state context; the lock file was zero bytes from
2026-06-10 and had no active migration owner. Both were moved, not discarded, to:

```text
/home/ops/backups/edu-cloud/rh1-runtime-artifact-cleanup-20260622T143821Z/
```

Final command:

```bash
cd /home/ops/projects/edu-cloud
scripts/guardian-watch --once --no-network --no-model-review --json > /tmp/rh1-guardian-after-clean.json
```

Final result:

```json
{
  "overall": "green",
  "red_count": 0,
  "yellow_count": 0,
  "issues": []
}
```

## Boundaries Preserved

R-H1 closeout did not change:

- business logic
- database schema or data
- module dependency policy
- module semantics
- frontend route gating
- Portal API contract
- runtime service topology

The only live cleanup was moving stale local execution artifacts to a repo-external
backup directory so guardian could report the real current state without local
context contamination.

## Closeout State

Status: `closed/evidence-recorded/runtime-green`.

Residual debt intentionally not closed by this packet:

- D-02 L2 historical review-gap: 16 historical commits still require independent
  review-gap handling.
- R-M5/R-M6/R-M7 and low-risk hygiene items remain separate debt-ledger entries.
