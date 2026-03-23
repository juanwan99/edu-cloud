"""Behavior tests for AI tools — mock service layer, verify real function logic.

Tests cover: status filtering, permission gating (_visible_subjects/_visible_classes),
not-found handling, and correct delegation to service functions.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: lightweight fake domain objects (SimpleNamespace with attrs)
# ---------------------------------------------------------------------------

def _exam(id="e1", name="期中考试", status="grading", card_title="期中"):
    return SimpleNamespace(id=id, name=name, status=status, card_title=card_title)


def _subject(id="s1", name="数学", code="SX"):
    return SimpleNamespace(id=id, name=name, code=code)


def _class(id="c1", name="七年级1班", grade="七年级"):
    return SimpleNamespace(id=id, name=name, grade=grade)


def _student(id="stu1", name="张三", student_number="T001", class_id="c1"):
    return SimpleNamespace(id=id, name=name, student_number=student_number, class_id=class_id)


def _kp(id="kp1", code="SX-001", name="函数", level=1, grade_hint="高一"):
    return SimpleNamespace(id=id, code=code, name=name, level=level, grade_hint=grade_hint)


# ---------------------------------------------------------------------------
# 1. get_exam_list — empty result
# ---------------------------------------------------------------------------

@patch("edu_cloud.modules.exam.service.list_exams", new_callable=AsyncMock)
async def test_get_exam_list_empty(mock_list):
    mock_list.return_value = []
    from edu_cloud.ai.tools.exams import get_exam_list
    result = await get_exam_list(_db="mock_db", _school_id="s1")
    assert result == {"exams": []}
    mock_list.assert_awaited_once_with("mock_db", school_id="s1")


# ---------------------------------------------------------------------------
# 2. get_exam_list — status filter
# ---------------------------------------------------------------------------

@patch("edu_cloud.modules.exam.service.list_exams", new_callable=AsyncMock)
async def test_get_exam_list_with_status_filter(mock_list):
    mock_list.return_value = [
        _exam(id="e1", status="grading"),
        _exam(id="e2", status="completed"),
    ]
    from edu_cloud.ai.tools.exams import get_exam_list
    result = await get_exam_list(status="completed", _db="mock_db", _school_id="s1")
    assert len(result["exams"]) == 1
    assert result["exams"][0]["id"] == "e2"
    assert result["exams"][0]["status"] == "completed"


# ---------------------------------------------------------------------------
# 3. get_exam_detail — _visible_subjects filtering
# ---------------------------------------------------------------------------

@patch("edu_cloud.modules.exam.service.list_subjects", new_callable=AsyncMock)
@patch("edu_cloud.modules.exam.service.get_exam", new_callable=AsyncMock)
async def test_get_exam_detail_filters_subjects(mock_get_exam, mock_list_subjects):
    mock_get_exam.return_value = _exam(id="e1", name="期中考试", status="grading")
    mock_list_subjects.return_value = [
        _subject(id="s1", name="数学", code="SX"),
        _subject(id="s2", name="语文", code="YW"),
        _subject(id="s3", name="英语", code="YY"),
    ]
    from edu_cloud.ai.tools.exams import get_exam_detail

    # Only allow SX and YY — YW should be filtered out
    result = await get_exam_detail(
        exam_id="e1",
        _school_id="s1",
        _visible_subjects=["SX", "YY"],
        _db="mock_db",
    )
    assert result["id"] == "e1"
    assert len(result["subjects"]) == 2
    codes = {s["code"] for s in result["subjects"]}
    assert codes == {"SX", "YY"}
    assert "YW" not in codes


@patch("edu_cloud.modules.exam.service.list_subjects", new_callable=AsyncMock)
@patch("edu_cloud.modules.exam.service.get_exam", new_callable=AsyncMock)
async def test_get_exam_detail_no_filter_returns_all(mock_get_exam, mock_list_subjects):
    """When _visible_subjects is None, all subjects are returned."""
    mock_get_exam.return_value = _exam(id="e1")
    mock_list_subjects.return_value = [
        _subject(id="s1", code="SX"),
        _subject(id="s2", code="YW"),
    ]
    from edu_cloud.ai.tools.exams import get_exam_detail

    result = await get_exam_detail(exam_id="e1", _school_id="s1", _visible_subjects=None, _db="mock_db")
    assert len(result["subjects"]) == 2


# ---------------------------------------------------------------------------
# 4. get_class_list — grade filter
# ---------------------------------------------------------------------------

@patch("edu_cloud.modules.student.service.list_classes", new_callable=AsyncMock)
async def test_get_class_list_filters_by_grade(mock_list):
    mock_list.return_value = [
        _class(id="c1", name="七年级1班", grade="七年级"),
        _class(id="c2", name="八年级1班", grade="八年级"),
    ]
    from edu_cloud.ai.tools.students import get_class_list

    result = await get_class_list(grade="七年级", _db="mock_db", _school_id="s1")
    assert len(result["classes"]) == 1
    assert result["classes"][0]["id"] == "c1"
    assert result["classes"][0]["grade"] == "七年级"


@patch("edu_cloud.modules.student.service.list_classes", new_callable=AsyncMock)
async def test_get_class_list_no_filter_returns_all(mock_list):
    mock_list.return_value = [
        _class(id="c1", grade="七年级"),
        _class(id="c2", grade="八年级"),
    ]
    from edu_cloud.ai.tools.students import get_class_list

    result = await get_class_list(_db="mock_db", _school_id="s1")
    assert len(result["classes"]) == 2


# ---------------------------------------------------------------------------
# 5. get_student_profile — not found
# ---------------------------------------------------------------------------

@patch("edu_cloud.modules.student.service.get_student", new_callable=AsyncMock)
async def test_get_student_profile_not_found(mock_get):
    mock_get.return_value = None
    from edu_cloud.ai.tools.students import get_student_profile

    result = await get_student_profile(student_id="nonexistent", _db="mock_db", _school_id="s1")
    assert "error" in result
    assert result["error"] == "学生不存在"


# ---------------------------------------------------------------------------
# 6. get_student_profile — permission denied (class_id outside _visible_classes)
# ---------------------------------------------------------------------------

@patch("edu_cloud.modules.student.service.get_student", new_callable=AsyncMock)
async def test_get_student_profile_permission_denied(mock_get):
    mock_get.return_value = _student(id="stu1", class_id="c99")
    from edu_cloud.ai.tools.students import get_student_profile

    # Teacher can only see class c1, but student is in c99
    result = await get_student_profile(
        student_id="stu1",
        _school_id="s1",
        _visible_classes=["c1"],
        _db="mock_db",
    )
    assert "error" in result
    assert result["error"] == "无权访问该学生信息"


@patch("edu_cloud.modules.student.service.get_student", new_callable=AsyncMock)
async def test_get_student_profile_permission_allowed(mock_get):
    """When student's class_id IS in _visible_classes, return profile."""
    mock_get.return_value = _student(id="stu1", class_id="c1")
    from edu_cloud.ai.tools.students import get_student_profile

    result = await get_student_profile(
        student_id="stu1",
        _school_id="s1",
        _visible_classes=["c1", "c2"],
        _db="mock_db",
    )
    assert "error" not in result
    assert result["id"] == "stu1"
    assert result["student_name"] == "张三"
    assert result["class_id"] == "c1"


# ---------------------------------------------------------------------------
# 7. get_knowledge_tree — structure verification
# ---------------------------------------------------------------------------

@patch("edu_cloud.modules.knowledge.service.list_knowledge_points", new_callable=AsyncMock)
async def test_get_knowledge_tree(mock_list):
    mock_list.return_value = [
        _kp(id="kp1", code="SX-001", name="函数", level=1, grade_hint="高一"),
        _kp(id="kp2", code="SX-002", name="导数", level=1, grade_hint="高二"),
    ]
    from edu_cloud.ai.tools.knowledge_db import get_knowledge_tree

    result = await get_knowledge_tree(course_code="SX", _db="mock_db", _school_id="s1")
    assert "knowledge_points" in result
    kps = result["knowledge_points"]
    assert len(kps) == 2
    assert kps[0] == {"id": "kp1", "code": "SX-001", "name": "函数", "level": 1, "grade_hint": "高一"}
    assert kps[1]["code"] == "SX-002"
    mock_list.assert_awaited_once_with("mock_db", course_code="SX", parent_id=None, school_id="s1")


@patch("edu_cloud.modules.knowledge.service.list_knowledge_points", new_callable=AsyncMock)
async def test_get_knowledge_tree_with_parent(mock_list):
    """When parent_id is specified, it's passed through to the service."""
    mock_list.return_value = [
        _kp(id="kp3", code="SX-001-01", name="一次函数", level=2, grade_hint="高一"),
    ]
    from edu_cloud.ai.tools.knowledge_db import get_knowledge_tree

    result = await get_knowledge_tree(course_code="SX", parent_id="kp1", _db="mock_db", _school_id="s1")
    assert len(result["knowledge_points"]) == 1
    mock_list.assert_awaited_once_with("mock_db", course_code="SX", parent_id="kp1", school_id="s1")


# ---------------------------------------------------------------------------
# 8. search_students — delegates to service
# ---------------------------------------------------------------------------

@patch("edu_cloud.modules.student.service.search_students", new_callable=AsyncMock)
async def test_search_students_delegates_to_service(mock_search):
    mock_search.return_value = [
        _student(id="stu1", name="张三", student_number="T001", class_id="c1"),
        _student(id="stu2", name="张四", student_number="T002", class_id="c2"),
    ]
    from edu_cloud.ai.tools.students import search_students

    result = await search_students(
        query_string="张",
        _school_id="s1",
        _visible_classes=["c1", "c2"],
        _db="mock_db",
    )
    assert len(result["students"]) == 2
    assert result["students"][0]["student_name"] == "张三"
    assert result["students"][1]["student_number"] == "T002"
    mock_search.assert_awaited_once_with(
        "mock_db", school_id="s1", query="张", visible_class_ids=["c1", "c2"],
    )
