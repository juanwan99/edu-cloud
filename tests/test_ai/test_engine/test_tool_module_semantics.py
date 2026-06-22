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
