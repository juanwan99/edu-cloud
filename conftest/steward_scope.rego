package steward.scope

deny[msg] {
  input.schema == "audit-office-case.v1"
  count(input.allowed_paths) == 0
  msg := "audit-office case must declare allowed_paths"
}

deny[msg] {
  input.schema == "audit-office-case.v1"
  input.write_policy != "audit_office_only_for_audit"
  msg := "audit case write_policy must remain audit_office_only_for_audit"
}

deny[msg] {
  input.schema == "audit-office-review-lineage.v1"
  some i
  review := input.reviews[i]
  review.reviewer == "codex-cloud"
  review.type == "independent_audit"
  msg := "cloud Codex called by Claude cannot be independent audit"
}
