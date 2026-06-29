package steward.scope

valid_status := {"active", "closed"}

required_forbidden_paths := {
  ".yuanqi/",
  "scripts/yuanqi/",
  "tests/yuanqi/",
}

deny[msg] {
  input.schema == "steward-pr-scope.v1"
  not input.scope_id
  msg := "steward scope must declare scope_id"
}

deny[msg] {
  input.schema == "steward-pr-scope.v1"
  not valid_status[input.status]
  msg := "steward scope status must be active or closed"
}

deny[msg] {
  input.schema == "steward-pr-scope.v1"
  count(input.allowed_paths) == 0
  msg := "steward scope must declare allowed_paths"
}

deny[msg] {
  input.schema == "steward-pr-scope.v1"
  count(input.allowed_paths) > 20
  msg := "steward scope allowed_paths must contain at most 20 entries"
}

deny[msg] {
  input.schema == "steward-pr-scope.v1"
  path := input.allowed_paths[_]
  is_legacy_yuanqi_path(path)
  msg := sprintf("steward scope must not allow legacy Yuanqi path: %s", [path])
}

deny[msg] {
  input.schema == "steward-pr-scope.v1"
  required := required_forbidden_paths[_]
  not path_list_contains(input.forbidden_paths, required)
  msg := sprintf("steward scope must forbid legacy path: %s", [required])
}

deny[msg] {
  input.schema == "steward-pr-scope.v1"
  input.status == "active"
  path := input.allowed_paths[_]
  is_high_risk_governance_path(path)
  not is_governance_scope
  msg := sprintf("active non-governance scope must not allow high-risk governance path: %s", [path])
}

path_list_contains(paths, target) {
  paths[_] == target
}

is_legacy_yuanqi_path(path) {
  path == ".yuanqi/"
}

is_legacy_yuanqi_path(path) {
  startswith(path, ".yuanqi/")
}

is_legacy_yuanqi_path(path) {
  startswith(path, "scripts/yuanqi/")
}

is_legacy_yuanqi_path(path) {
  startswith(path, "tests/yuanqi/")
}

is_high_risk_governance_path(path) {
  startswith(path, ".github/workflows/")
}

is_high_risk_governance_path(path) {
  path == ".github/CODEOWNERS"
}

is_governance_scope {
  contains(input.scope_id, "governance")
}

is_governance_scope {
  contains(input.scope_id, "hard-gate")
}

is_governance_scope {
  contains(input.scope_id, "codeowners")
}
