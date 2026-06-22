# Portal C3 Online Verification and Sign-off Packet (D-08C)

Date: 2026-06-22 Asia/Shanghai
Branch: `feat/module-governance-repair`
Verified HEAD: `0228fe6deb1407d8a6b3a7493f225b5d562b47e8`
Scope: evidence-only closeout for Portal Phase 1 unlock preconditions. No product code, middleware, auth guard, module semantics, or DB data was changed.

## Decision

Portal Phase 1 implementation remains gated by designer sign-off, but the operational prerequisites that were blocking sign-off are now verified:

- C1 DB doctor: green.
- C2 source/build/nginx/backend runtime alignment: green.
- C3 online module-gating and portal-services fail-closed behavior: green.
- R-H5 production `SchoolModule` row integrity: green.

This packet does not self-unlock Portal Phase 1. It provides the evidence needed for designer sign-off. After sign-off, the next implementation slice is the already frozen first cut: frontend homepage aggregation consuming existing `/api/v1/portal/*`, with service cards gated by `moduleGateFromAuth`.

## Fresh Evidence

### Repo and runtime alignment

Command:

```bash
cd /home/ops/projects/edu-cloud
git status --short --branch
git log --oneline --decorate -5
bash ./scripts/truth-status.sh
python3 scripts/db_doctor.py --strict
```

Result:

- Branch clean and aligned with `origin/feat/module-governance-repair`.
- HEAD: `0228fe6`.
- `truth-status.sh`: `ALL ALIGNED` - source, build, nginx, and backend versions match.
- Backend pid: `4082406`, booted at `2026-06-22 15:39:56`, git `0228fe6`.
- Nginx serves `version.json` with `git_hash=0228fe6`.
- DB Doctor: Alembic `e1f2_import_sess`; ORM tables `96`, DB tables `98`; `No drift detected`.

### Governance gates

Command:

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python scripts/governance/check_module_semantics.py --check
.venv/bin/python scripts/governance/check_ai_tool_modules.py
.venv/bin/python scripts/governance/check_module_dependencies.py --check
```

Result:

- `Module semantics baseline clean`.
- `AI tool module baseline clean: 67 tools`.
- `Module dependency baseline clean: 0 edges, 0 cycles`.

### R-H5 production SchoolModule row integrity

Read-only SQLite inspection against `/home/ops/projects/edu-cloud/edu_cloud.db`:

- `school_count`: `3`
- `school_modules_count`: `27`
- distinct module codes: `calendar`, `conduct`, `exam`, `grading`, `homework`, `research`, `studio`, `study_analytics`, `teaching`
- rows per school:
  - school `e6a1d0d7-b566-46ce-9a1d-dd255b2e7ccc`: `9`
  - school `66d695f2-b9a6-4557-9f72-665c5c9f5e97`: `9`
  - school `d5d960fc-6668-4c61-bde6-bb61f6895bb8`: `9`
- `integrity_issues`: `0`

Conclusion: every production school has exactly the expected nine `SchoolModule` rows; no missing or extra module code was found.

### Online C3 fail-closed behavior

Verification used a short-lived token for a real `academic_director` role in school `d5d960fc-6668-4c61-bde6-bb61f6895bb8`, where `research`, `study_analytics`, and `teaching` are disabled.

Command shape:

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python - <<'PY'
# Creates a short-lived token with create_access_token(...)
# Calls https://mcu.asia with Authorization: Bearer <token>
# Asserts disabled module endpoints return 403
# Asserts /api/v1/portal/services does not include disabled module codes
PY
```

Result:

- `/api/v1/academic/teaching-plans` -> HTTP `403`
- `/api/v1/knowledge-tree` -> HTTP `403`
- `/api/v1/analytics/report` -> HTTP `403`
- `/api/v1/portal/services` -> HTTP `200`
- `portal_service_codes`: `exam`, `grading`, `homework`, `calendar`, `studio`, `conduct`
- `blocked_leaks`: `[]`

Conclusion: online module gating remains fail-closed, and portal services do not leak disabled module entries for the tested school role.

### Target regression tests

Command:

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/test_api/test_module_middleware.py tests/test_modules/test_portal/test_service.py -q
```

Result:

- `32 passed, 6 warnings`

## Boundaries Preserved

No change was made to:

- `DEFAULT_ENABLED`
- `src/edu_cloud/api/module_middleware.py`
- `frontend/src/router/index.js`
- `docs/governance/module-semantics.yaml`
- `scripts/governance/check_module_semantics.py`
- D-06 `studio-frontend-entry-missing`
- Portal frontend implementation code

## Sign-off State

Status: `pending-designer-signoff`

Evidence is sufficient to move from "blocked on W4 + sign-off" to "C3/R-H5 verified; waiting for designer sign-off." Executor/Codex does not self-unlock Portal Phase 1.

After designer sign-off, the next slice may start:

- frontend homepage aggregation,
- consume existing `/api/v1/portal/*`,
- service cards gated by `moduleGateFromAuth`,
- no changes to foundation module semantics.
