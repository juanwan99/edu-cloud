---
title: NOW
owner: liang
last_review_date: "2026-06-29"
expiration_in_days: 7
---

# NOW

Last refreshed: 2026-06-29 09:24 Asia/Shanghai

## Current Goal

Keep edu-cloud development fast and bounded under Keel 双核治理:

- use GitHub as hard merge authority;
- keep active docs small, indexed, owner-tagged, and review-dated;
- prevent old plans, handoffs, and Yuanqi task-contract material from becoming
  current instructions;
- return to real edu-cloud business work once the hygiene baseline stays quiet.

## Fresh State

- `master` includes the Keel document lifecycle gate from PR #35 and the Tier A
  `doc-stale` scheduled sweep from PR #36.
- The manual `keel doc stale sweep` run on `master` succeeded and created no
  `doc-stale` issue.
- There are no open edu-cloud PRs at this refresh.
- The local Keel worktree was fast-forwarded to `origin/master` at
  `f9a94678b284efecc501413b6cbeca793525e944`.
- Merged local Keel feature worktrees and local feature branches were removed.

## Keel Baseline

Current governed PR flow:

1. create one task worktree;
2. add one fresh scope file under `control/steward/scopes/`;
3. change only paths allowed by that scope;
4. include `Steward-Scope: <scope_id>` in the PR body;
5. let GitHub required checks, CODEOWNERS, and human review decide merge.

The retired Yuanqi task-contract workflow is historical evidence only. Do not
create `.yuanqi/tasks`, `Yuanqi-Task:` PR markers, Yuanqi task windows, or
Yuanqi registry/scope/overlap gates for current work.

## Current Hygiene Status

- Active docs are controlled by `docs/context/ACTIVE_INDEX.md`.
- Active context docs must carry lifecycle frontmatter and pass
  `frontmatter.schema.json` through GitHub Actions.
- `docs/context/NOW.md` is now a short current-state page. Older runtime and
  governance snapshots must be read from their source docs or git history only
  when explicitly needed.
- `docs/plans/archived/**` and `docs/superpowers/**` were removed from the
  working tree; use git history for explicit historical evidence.

## Open Follow-Ups

- Watch the next scheduled `doc-stale` run. If it remains quiet, keep it as the
  deterministic Tier A document lifecycle baseline.
- Defer Tier B git-age `doc-maybe-stale` and Tier C code-doc drift checks until
  real usage shows they are worth the noise.
- For the next business pilot, prefer a small user-visible edu-cloud change so
  Keel is tested against delivery, not more governance construction.

## Live Verification Commands

Use live commands for volatile facts. Do not trust old timestamps in historical
handoffs.

```bash
git status --short --branch
gh pr list --repo juanwan99/edu-cloud --state open
gh run list --repo juanwan99/edu-cloud --branch master --limit 5
scripts/codex-check
scripts/codex-context --no-network
scripts/meta-check --json --strict --task "current user task"
scripts/codex-verify safety --repo-wide
```

Runtime, ECS services, DB state, and public URL facts were not reverified in
this hygiene pass. Recheck them with project runtime commands before any
runtime, deploy, migration, or production claim.
