# Steward Hard Gates

This target repo is governed by external Engineering Audit Steward Loop records.

Required checks to configure in GitHub:

- `steward/schema-and-docs`
- `steward/semgrep-governance`
- `steward/gitleaks`
- `steward/conftest-policy`
- `steward/codeql`

Ruleset expectations:

- Pull requests are required.
- Required checks must pass before merge.
- CODEOWNERS review is required for governance, CI, auth, DB, runtime, and deployment paths.
- Merge Queue is recommended for parallel module work.
- Admin bypass should be disabled or separately logged as a human waiver.

Process-heavy investigation reports belong in `C:/Users/liang/Documents/engineering-audit-office`, not in this target repository.
