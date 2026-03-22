import pytest
from edu_cloud.ai.tools.analytics import get_exam_scores, get_class_stats, compare_classes, get_student_profile


@pytest.mark.asyncio
async def test_get_exam_scores(db, seed_exam_with_results):
    exam_id = seed_exam_with_results["exam_id"]
    school_id = seed_exam_with_results["school_id"]
    result = await get_exam_scores(exam_id=exam_id, _db=db, _school_id=school_id, _class_ids=None)
    assert "students" in result
    assert len(result["students"]) > 0
    assert "total_score" in result["students"][0]
    assert "stats" in result


@pytest.mark.asyncio
async def test_get_exam_scores_with_class_filter(db, seed_exam_with_results):
    exam_id = seed_exam_with_results["exam_id"]
    school_id = seed_exam_with_results["school_id"]
    class_id = seed_exam_with_results["class_id"]
    result = await get_exam_scores(exam_id=exam_id, _db=db, _school_id=school_id, _class_ids=[class_id])
    assert len(result["students"]) > 0
    for s in result["students"]:
        assert s["class_id"] == class_id


@pytest.mark.asyncio
async def test_get_class_stats(db, seed_exam_with_results):
    exam_id = seed_exam_with_results["exam_id"]
    class_id = seed_exam_with_results["class_id"]
    result = await get_class_stats(exam_id=exam_id, class_id=class_id, _db=db, _school_id=seed_exam_with_results["school_id"])
    assert "avg" in result
    assert "max" in result
    assert "min" in result
    assert "count" in result


@pytest.mark.asyncio
async def test_compare_classes(db, seed_exam_with_results):
    exam_id = seed_exam_with_results["exam_id"]
    school_id = seed_exam_with_results["school_id"]
    result = await compare_classes(exam_id=exam_id, _db=db, _school_id=school_id, _class_ids=None)
    assert "classes" in result
    assert len(result["classes"]) >= 1
    assert "avg" in result["classes"][0]
    assert "count" in result["classes"][0]


@pytest.mark.asyncio
async def test_get_student_profile(db, seed_exam_with_results):
    school_id = seed_exam_with_results["school_id"]
    result = await get_student_profile(student_number="T000", _db=db, _school_id=school_id)
    assert "name" in result
    assert "exams" in result
    assert len(result["exams"]) >= 1


@pytest.mark.asyncio
async def test_get_student_profile_not_found(db, seed_exam_with_results):
    result = await get_student_profile(student_number="NONEXIST", _db=db, _school_id=seed_exam_with_results["school_id"])
    assert "error" in result


@pytest.mark.asyncio
async def test_get_exam_scores_empty(db, seed_exam_with_results):
    result = await get_exam_scores(exam_id="nonexistent", _db=db, _school_id="none", _class_ids=None)
    assert result["students"] == []
    assert result["stats"]["count"] == 0
