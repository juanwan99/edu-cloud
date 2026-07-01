Steward-Scope: REQUIRED
Codex-Dispatch-Review: REQUIRED
Integration-Lane: REQUIRED
Write-License: REQUIRED

## Summary

## Verification

## Dispatch Review

- [ ] Codex Dispatch Review evidence above was issued before implementation by the non-implementing steward/reviewer.
- [ ] Branch was created from latest `origin/master`; no stale worktree or branch was reused.
- [ ] Replaced `REQUIRED` above with the exact scope id.
- [ ] Replaced `Codex-Dispatch-Review: REQUIRED` above with a real CDR id or GitHub comment URL.
- [ ] Declared `Integration-Lane` as `independent`, `guarded`, or `exclusive`.
- [ ] Declared `Write-License` with draft PR permission, CI self-fix permission, and stop condition.
- [ ] Added one fresh scope file under `control/steward/scopes/`.
- [ ] Changed files stay inside scope `allowed_paths`; no `forbidden_paths` were touched.
- [ ] For file deletion or retirement, reachability was checked across `scripts/`, `tests/`, `.github/workflows/`, active docs, and governance registries.

## Independent Review

Reviewer / evidence URL:

Verdict: PENDING

Raw Claude/manual review may be pasted to Codex; Codex will post the concise
evidence comment and update this section.
Before marking the PR ready to merge, set `Verdict: PASS` and replace the
reviewer/evidence placeholder with the exact review comment or review URL.
The approving GitHub review should also include that evidence URL in its body.

- [ ] Review body/comment is non-empty and written by a non-author.
- [ ] Reviewer checked the production call path, not only the touched function.
- [ ] New fields, flags, parameters, fallbacks, or fail-closed paths have named production consumers.
- [ ] Tests cover the caller path or the PR explains why focused unit coverage is sufficient.
- [ ] Residual risk is stated, with explicit PASS or FAIL.
