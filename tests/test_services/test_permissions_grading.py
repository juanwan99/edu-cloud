from edu_cloud.core.permissions import Permission, has_permission


def test_lesson_prep_leader_has_view_grading():
    assert has_permission("lesson_prep_leader", Permission.VIEW_GRADING)


def test_lesson_prep_leader_has_manage_grading():
    assert has_permission("lesson_prep_leader", Permission.MANAGE_GRADING)


def test_lesson_prep_leader_has_manage_exams():
    assert has_permission("lesson_prep_leader", Permission.MANAGE_EXAMS)


def test_academic_director_still_has_grading():
    """ORC-005: 现有角色权限不回归。"""
    assert has_permission("academic_director", Permission.MANAGE_GRADING)
    assert has_permission("academic_director", Permission.VIEW_GRADING)


def test_subject_teacher_no_manage_grading():
    assert not has_permission("subject_teacher", Permission.MANAGE_GRADING)
