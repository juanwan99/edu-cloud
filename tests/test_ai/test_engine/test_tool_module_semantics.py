"""AI tool module-code semantic gating tests."""


def _allowed_names(*, role: str, enabled_modules: frozenset[str]) -> set[str]:
    from edu_cloud.ai.engine.tools import collect_all_tools, filter_tools_for_role

    return {
        getattr(fn, "_edu_meta").name
        for fn in filter_tools_for_role(
            collect_all_tools(),
            role=role,
            enabled_modules=enabled_modules,
        )
        if getattr(fn, "_edu_meta", None)
    }


def test_study_analytics_tools_follow_study_analytics_switch() -> None:
    exam_only = _allowed_names(role="academic_director", enabled_modules=frozenset({"exam"}))
    study_only = _allowed_names(role="academic_director", enabled_modules=frozenset({"study_analytics"}))

    assert "get_exam_summary" not in exam_only
    assert "get_student_trend" not in exam_only
    assert "get_exam_summary" in study_only
    assert "get_student_trend" in study_only


def test_research_tools_follow_research_switch() -> None:
    exam_only = _allowed_names(role="academic_director", enabled_modules=frozenset({"exam"}))
    research_only = _allowed_names(role="academic_director", enabled_modules=frozenset({"research"}))

    assert "get_student_error_book" not in exam_only
    assert "search_curriculum" not in exam_only
    assert "get_student_error_book" in research_only
    assert "search_curriculum" in research_only


def test_base_student_and_system_tools_do_not_follow_exam_switch() -> None:
    no_modules = _allowed_names(role="academic_director", enabled_modules=frozenset())

    assert "get_class_list" in no_modules
    assert "get_class_roster" in no_modules
    assert "search_students" in no_modules
    assert "get_student_profile" in no_modules
    assert "query_artifact" in no_modules
    assert "aggregate_artifact" in no_modules
    assert "memory_read" in no_modules
    assert "memory_write" in no_modules


def test_studio_actions_follow_primary_and_required_modules() -> None:
    studio_only = _allowed_names(role="academic_director", enabled_modules=frozenset({"studio"}))
    studio_exam = _allowed_names(role="academic_director", enabled_modules=frozenset({"studio", "exam"}))

    assert "generate_comment" in studio_only
    assert "generate_report" not in studio_only
    assert "generate_report" in studio_exam


def test_conduct_notification_requires_studio() -> None:
    conduct_only = _allowed_names(role="academic_director", enabled_modules=frozenset({"conduct"}))
    conduct_studio = _allowed_names(role="academic_director", enabled_modules=frozenset({"conduct", "studio"}))

    assert "draft_parent_notification" not in conduct_only
    assert "draft_parent_notification" in conduct_studio
