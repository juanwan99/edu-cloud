"""静态治理规则：防止新代码引入租户隔离漏洞。"""
from pathlib import Path

ROUTER_DIRS = [
    Path("src/edu_cloud/modules"),
    Path("src/edu_cloud/api"),
]

# Files known to use raw role.school_id — allowed until migrated.
# Files touched by Phase 3 Tasks 2/4/5/6 have been removed (must migrate on touch).
ALLOWLIST_RAW_SCHOOL_ID = {
    "src/edu_cloud/api/auth.py",
    "src/edu_cloud/api/impersonate.py",
    "src/edu_cloud/api/compat_router.py",
    "src/edu_cloud/api/ai.py",
    "src/edu_cloud/api/notifications_api.py",
    "src/edu_cloud/modules/academic/router.py",
    "src/edu_cloud/modules/analytics/router.py",
    "src/edu_cloud/modules/bank/router.py",
    "src/edu_cloud/modules/calendar/router.py",
    "src/edu_cloud/modules/card/card_export_router.py",
    "src/edu_cloud/modules/card/card_template_router.py",
    "src/edu_cloud/modules/card/router.py",
    "src/edu_cloud/modules/conduct/admin_router.py",
    "src/edu_cloud/modules/exam/llm_config_router.py",
    "src/edu_cloud/modules/exam/router.py",
    "src/edu_cloud/modules/grading/assignment_router.py",
    "src/edu_cloud/modules/grading/grading_review_router.py",
    "src/edu_cloud/modules/grading/quality_router.py",
    "src/edu_cloud/modules/grading/router.py",
    "src/edu_cloud/modules/knowledge_tree/router.py",
    "src/edu_cloud/modules/marking/router.py",
    "src/edu_cloud/modules/menu/router.py",
    "src/edu_cloud/modules/pipeline/router.py",
    "src/edu_cloud/modules/profile/router.py",
    "src/edu_cloud/modules/scan/router.py",
    "src/edu_cloud/modules/school/assignment_router.py",
    "src/edu_cloud/modules/school/audit_router.py",
    "src/edu_cloud/modules/school/capability_router.py",
    "src/edu_cloud/modules/school/selection_router.py",
    "src/edu_cloud/modules/school/settings_router.py",
    "src/edu_cloud/modules/student/router.py",
    "src/edu_cloud/modules/student/teacher_router.py",
    "src/edu_cloud/modules/studio/router.py",
}


def _find_router_files():
    files = []
    for d in ROUTER_DIRS:
        if d.exists():
            for f in d.rglob("*router*.py"):
                if "__pycache__" not in str(f):
                    files.append(f)
            for f in d.rglob("*.py"):
                if f.name in ("dashboard.py", "ai.py") and "__pycache__" not in str(f):
                    files.append(f)
    return sorted(set(files))


def test_no_new_raw_school_id_in_routers():
    """新增 router 文件不得直接使用 role.school_id，必须走 get_school_id 或 TenantContext。"""
    violations = []
    for f in _find_router_files():
        rel = str(f)
        if rel in ALLOWLIST_RAW_SCHOOL_ID:
            continue
        content = f.read_text()
        has_school_id = '.school_id' in content
        has_tenant_guard = (
            'get_school_id' in content
            or 'TenantContext' in content
            or 'get_visible_subject_codes' in content
            or 'get_visible_class_ids' in content
            or 'CROSS_SCHOOL_ROLES' in content
        )
        if has_school_id and not has_tenant_guard:
            violations.append(rel)
    assert not violations, f"新增 router 使用了裸 role.school_id: {violations}"


def test_scope_filter_no_falsy_check():
    """ScopeFilter 不得用 if self.X 检查 scope 列表（空列表 fail-open）。"""
    content = Path("src/edu_cloud/core/scope_filter.py").read_text()
    lines = content.split("\n")
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for attr in ("class_ids", "grade_ids", "subject_codes"):
            if f"if self.{attr}" in stripped and "is not None" not in stripped:
                violations.append(f"scope_filter.py:{i}: {stripped}")
    assert not violations, f"ScopeFilter 使用了 falsy check: {violations}"
