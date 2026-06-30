---
title: NOW
owner: liang
last_review_date: "2026-06-30"
expiration_in_days: 7
---

# NOW

Last refreshed: 2026-06-30 08:32 Asia/Shanghai

## Current Goal

Use `docs/context/REQUIREMENTS_BASELINE.md` as the current requirements and task
baseline. Old session reports and old plan documents are historical evidence
only unless `ACTIVE_INDEX.md` or the baseline promotes them.

## Fresh State

- Current master: `437ef6a974da907841822245def0416cd9ecd313`.
- Current open PRs: none.
- Recent merged work: #57 calendar range validation, #58 calendar scope
  closeout, #59 token revocation fail-closed production behavior.
- Latest master GitHub runs are green.
- Module dependency gate is clean: `0 edges, 0 cycles`.
- `keel-token-revocation-fail-closed-2026-06-30.yml` is still `status: active`
  and needs a closeout PR.

## Next Work Queue

1. Close the #59 token revocation Keel scope.
2. Fix P1 silent degradation in chat message persistence.
3. Fix P1 grading JSON truncation repair behavior.
4. Fix P1 OCR uncertainty being converted to `unanswered`.
5. Keep module decoupling as a guardrail, not a broad refactor, until a concrete
   product task exposes a boundary problem.

## Keel Baseline

Current governed PR flow:

1. create one task branch/worktree;
2. add one fresh scope file under `control/steward/scopes/`;
3. change only paths allowed by that scope;
4. include `Steward-Scope: <scope_id>` and real dispatch-review evidence in the
   PR body;
5. let GitHub required checks, CODEOWNERS, and human review decide merge.

The retired Yuanqi task-contract workflow is historical evidence only. Do not
create `.yuanqi/tasks`, `Yuanqi-Task:` PR markers, Yuanqi task windows, or
Yuanqi registry/scope/overlap gates for current work.

## Live Verification Commands

Use live commands for volatile facts. Do not trust old timestamps in historical
handoffs.

```bash
git status --short --branch
git rev-parse HEAD
gh pr list --repo juanwan99/edu-cloud --state open
gh run list --repo juanwan99/edu-cloud --branch master --limit 5
python scripts/governance/check_module_dependencies.py --check
```

Runtime, ECS services, DB state, and public URL facts were not reverified in
this baseline pass. Recheck them with project runtime commands before any
runtime, deploy, migration, or production claim.
