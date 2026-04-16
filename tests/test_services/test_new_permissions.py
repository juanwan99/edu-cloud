from edu_cloud.core.permissions import Permission, ROLE_PERMISSIONS


def test_manage_grading_permission_exists():
    assert hasattr(Permission, "MANAGE_GRADING")
    assert Permission.MANAGE_GRADING.value == "manage_grading"


def test_view_grading_permission_exists():
    assert hasattr(Permission, "VIEW_GRADING")


def test_manage_exam_results_permission_exists():
    assert hasattr(Permission, "MANAGE_EXAM_RESULTS")


def test_academic_director_has_manage_grading():
    perms = ROLE_PERMISSIONS["academic_director"]
    assert Permission.MANAGE_GRADING in perms
    assert Permission.VIEW_GRADING in perms
    assert Permission.MANAGE_EXAM_RESULTS in perms


def test_grade_leader_has_view_grading():
    perms = ROLE_PERMISSIONS["grade_leader"]
    assert Permission.VIEW_GRADING in perms
    assert Permission.MANAGE_GRADING not in perms


def test_subject_teacher_has_view_grading():
    perms = ROLE_PERMISSIONS["subject_teacher"]
    assert Permission.VIEW_GRADING in perms
    assert Permission.MANAGE_GRADING not in perms


def test_parent_no_grading_perms():
    perms = ROLE_PERMISSIONS["parent"]
    assert Permission.VIEW_GRADING not in perms
    assert Permission.MANAGE_GRADING not in perms
