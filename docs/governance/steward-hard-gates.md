# Steward Hard Gates

This target repo is governed by external Engineering Audit Steward Loop records.

Required checks to configure in GitHub:

- `steward/pr-scope`
- `steward/schema-and-docs`
- `steward/semgrep-governance`
- `steward/gitleaks`
- `steward/conftest-policy`
- `steward/codeql`

`steward/pr-scope` requires each pull request to declare `Steward-Scope: <id>` and keeps changed files inside `control/steward/scopes/<id>.yml`. The scope file supports `allowed_paths` and `forbidden_paths`; forbidden paths fail even if they also match an allowed prefix.

`steward/codeql` runs CodeQL analysis in artifact mode (`upload: never`) and fails when CodeQL reports findings in files changed by the pull request. This keeps the gate usable before GitHub Code Security or code scanning is enabled for the private repository. If GitHub Code Security is later enabled, SARIF upload can be turned on as a second-stage enhancement.

Ruleset expectations:

- Pull requests are required.
- Required checks must pass before merge.
- CODEOWNERS review is required for governance, CI, auth, DB, runtime, and deployment paths.
- Merge Queue is recommended for parallel module work.
- Admin bypass should be disabled or separately logged as a human waiver.

Process-heavy investigation reports belong in `C:/Users/liang/Documents/engineering-audit-office`, not in this target repository.
