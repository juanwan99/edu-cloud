# R-H3 Frontend Gating Regression Closeout

Date: 2026-06-22 Asia/Shanghai
Branch: `feat/module-governance-repair`
Default branch: `master`
Evidence HEAD: `e52f86d6c3c4c8352f1155fd1cd3adabbfd7ae4f`

Scope: close the R-H3 evidence gap for frontend module-gating regression
coverage. This closeout records verification evidence only. It does not change
product code, frontend route semantics, backend module middleware, database
data, or runtime process configuration.

## Decision

R-H3 is closed for the current default-branch baseline.

The original R-H3 risk was not that a known frontend gate was failing; it was
that the 2026-06-10 foundation audit only had focused/backend evidence while the
frontend module-gating surfaces from Phase 0.6 to 0.7A were protected by Vitest
tests whose full-suite result was stale. The default branch now has exact-HEAD
GitHub Actions evidence for the full frontend suite, build, lint, and audit.

## Fresh Evidence

### Git And CI Binding

Command:

```bash
cd /home/ops/projects/edu-cloud
git status --short --branch
git rev-parse --short HEAD
git rev-parse --short origin/master
gh run view 27953800524 --json status,conclusion,headSha,jobs,url
```

Result:

- working tree clean on `feat/module-governance-repair`.
- `HEAD = origin/master = origin/feat/module-governance-repair = e52f86d`.
- GitHub Actions run: `27953800524`.
- run URL: `https://github.com/juanwan99/edu-cloud/actions/runs/27953800524`.
- run status: `completed`, conclusion: `success`.
- run head SHA: `e52f86d6c3c4c8352f1155fd1cd3adabbfd7ae4f`.
- jobs: `backend=success`, `frontend=success`, `governance=success`.

### Frontend Full Regression

Workflow authority: `.github/workflows/test.yml` frontend job runs:

```bash
cd frontend && npm ci --ignore-scripts
cd frontend && npx vitest run
cd frontend && npm run build
cd frontend && npm audit --audit-level=high
```

GitHub frontend job: `82716953796`.

Result excerpt from the job log:

- `npm ci --ignore-scripts`: `found 0 vulnerabilities`.
- `npx vitest run`: `Test Files 117 passed (117)`.
- `npx vitest run`: `Tests 2525 passed (2525)`.
- Vitest duration: `165.04s`.
- `npm run build`: lint ran first and reported `0 errors, 1 warning`.
- pre-existing warning: `frontend/src/components/workspace/ChatPanel.vue` uses
  `v-html` (`vue/no-v-html`). This is not part of the R-H3 module-gating
  surface and did not fail the job.
- `vite build`: `built in 4.98s`.
- `npm audit --audit-level=high`: `found 0 vulnerabilities`.

### Gate Surface Coverage

The full suite includes the frontend module-gating surfaces that R-H3 called
out:

- `frontend/src/__tests__/routeAccess.test.js` covers fail-closed module gate
  semantics and `moduleGateFromAuth`.
- `frontend/src/__tests__/router.test.js` covers `authGuard` direct URL module
  gating, including dynamic-route `meta.moduleCode` behavior.
- `frontend/src/__tests__/AppSidebar.test.js` covers sidebar visibility using
  the shared module gate.
- `frontend/src/__tests__/AppHeader.test.js` covers header navigation filtering.
- `frontend/src/__tests__/RoleSwitcher.test.js` covers role switching through
  `canAccessMatchedRoute(..., moduleGateFromAuth(auth))`.
- `frontend/src/pages/__tests__/DashboardPage.test.js` covers the Portal / dashboard
  service-card path using `moduleGateFromAuth` and shared route requirements.

Fresh count: the repository currently has `117` frontend test files under
`frontend/src`, and the listed gate-surface files contain `161` `describe`/`it`
entries. The CI full-suite result above proves those files were not merely
present; they ran as part of exact-HEAD frontend verification.

## Status

R-H3 moves from `open` to `closed/evidence-recorded`.

Residual risks intentionally not closed by this packet:

- R-H1 后半: guardian still lacks a worker version/boot freshness probe.
- D-02 L2: historical 16-commit review gap remains a separate historical debt.
- `ChatPanel.vue` `v-html` warning remains a pre-existing frontend lint warning,
  not a module-gating regression.
