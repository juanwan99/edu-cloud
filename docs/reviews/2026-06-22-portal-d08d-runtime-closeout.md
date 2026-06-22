# Portal D-08D Runtime Closeout

Date: 2026-06-22 Asia/Shanghai
Branch: `feat/module-governance-repair`
Runtime HEAD: `332862a0e3a621f7dd4ac8ae122b339867e3ec49`

Scope: runtime and online closeout evidence for D-08D Portal Phase 1 first cut.
No product code, DB data, module semantics, auth guard, middleware, or runtime
process configuration was changed by this documentation closeout.

## Decision

D-08D source/runtime/online API closeout is green for the evidence captured here:

- local source, origin, ECS source, frontend build, nginx, and backend runtime
  are aligned on `332862a0`.
- all five authenticated Portal aggregation endpoints return HTTP `200`.
- `/api/v1/portal/services` returns only enabled module codes for the verified
  role/school context: `exam`, `grading`, `homework`, `calendar`, `studio`,
  `conduct`.
- disabled non-default modules `teaching`, `research`, and `study_analytics`
  do not leak from Portal services (`blocked_leaks=[]`).

Remaining external status: GitHub Actions exact-HEAD status is still unknown
from local evidence. This remains a Phase B closeout item and must not be
silently treated as green.

## Fresh Evidence

### Local Source And Origin

Command:

```powershell
git status --short --branch
git branch --show-current
git rev-parse HEAD
git rev-parse --abbrev-ref --symbolic-full-name '@{u}'
git rev-parse '@{u}'
```

Result:

- `## feat/module-governance-repair...origin/feat/module-governance-repair`
- branch: `feat/module-governance-repair`
- source HEAD: `332862a0e3a621f7dd4ac8ae122b339867e3ec49`
- upstream: `origin/feat/module-governance-repair`
- upstream HEAD: `332862a0e3a621f7dd4ac8ae122b339867e3ec49`

### ECS Runtime Truthline

Command:

```bash
cd /home/ops/projects/edu-cloud
git status --short --branch
git branch --show-current
git rev-parse HEAD
./scripts/truth-status.sh
```

Result:

- branch: `feat/module-governance-repair`
- source HEAD: `332862a0e3a621f7dd4ac8ae122b339867e3ec49`
- frontend build inputs clean
- backend `src/` clean
- frontend build `git_hash=332862a`, build time `2026-06-22T08:20:11.198Z`
- nginx returns HTTP `200` and serves `version.json` with `git_hash=332862a`
- backend PID `4175795`, boot `2026-06-22 16:20:12`, git `332862a`
- diagnosis: `ALL ALIGNED`

### Authenticated Online Portal API

Verification used a short-lived token created from `create_access_token(...)`
for:

- user: `ee244994-b320-4fe0-b079-09bf5572bc89`
- role: `academic_director`
- role id: `c447cb8e-0938-4e77-ac28-73283cbebf97`
- school: `d5d960fc-6668-4c61-bde6-bb61f6895bb8`

Command shape:

```bash
cd /home/ops/projects/edu-cloud
PYTHONPATH=src python3 - <online-portal-readonly-probe>
```

Result:

| Endpoint | Status | Key Result |
|---|---:|---|
| `/api/v1/portal/summary` | 200 | keys include `calendar_count`, `enabled_modules`, `service_count`, `todo_count`, `unread_message_count` |
| `/api/v1/portal/services` | 200 | codes: `exam`, `grading`, `homework`, `calendar`, `studio`, `conduct`; `blocked_leaks=[]` |
| `/api/v1/portal/todos` | 200 | count `0` |
| `/api/v1/portal/messages` | 200 | count `0` |
| `/api/v1/portal/calendar-digest` | 200 | count `0` |

## Prior Validation Carried Forward

These checks were captured in the D-08D source/runtime slice before this
closeout:

- targeted frontend tests:
  `src/__tests__/version-fingerprint.test.js` +
  `src/pages/__tests__/DashboardPage.test.js` = `47 passed`.
- `npm run lint` = 0 errors, with the pre-existing
  `frontend/src/components/workspace/ChatPanel.vue` `vue/no-v-html` warning.
- `npm run build` passed locally and during ECS live-sync.
- governance/meta/module semantic gates and DB doctor were clean.

## Boundaries Preserved

D-08D did not change:

- `DEFAULT_ENABLED`
- module middleware
- `authGuard`
- `docs/governance/module-semantics.yaml`
- production DB data
- Portal API contract or backend service semantics

`studio-frontend-entry-missing` remains registered and is not falsely closed:
the dashboard only renders service cards with mounted frontend targets.

## Closeout State

Status: `runtime-online-closed; external-ci-unknown`.

Next required closeout: Phase B must establish GitHub Actions exact-HEAD
visibility for `332862a0e3a621f7dd4ac8ae122b339867e3ec49` or document the
smallest CI-observability fix. This is tracked under R-H2 rather than hidden
inside D-08D.
