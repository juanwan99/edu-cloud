"""Tests for analytics filter parameters (T0.5): subject_id / class_id on 4 APIs.

ORC-006: all new params are Optional; omitting them yields identical behaviour.
"""
import pytest
from datetime import date, datetime

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.analytics.models import StudentKnpMastery
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint


# ---------------------------------------------------------------------------
# Shared fixture: school + 2 classes + 2 subjects + students + scores + KNP
# ---------------------------------------------------------------------------

@pytest.fixture
async def filter_data(db):
    """Two classes, two subjects, 4 students (2 per class), scores + KNP."""
    school = School(name="FilterSchool", code="FLT01")
    db.add(school)
    await db.commit()

    cls_a = Class(name="一班", grade="七年级", school_id=school.id)
    cls_b = Class(name="二班", grade="七年级", school_id=school.id)
    db.add_all([cls_a, cls_b])
    await db.commit()

    # 4 students: 2 in cls_a, 2 in cls_b
    stu_a1 = Student(name="A1", student_number="SA1", class_id=cls_a.id, school_id=school.id)
    stu_a2 = Student(name="A2", student_number="SA2", class_id=cls_a.id, school_id=school.id)
    stu_b1 = Student(name="B1", student_number="SB1", class_id=cls_b.id, school_id=school.id)
    stu_b2 = Student(name="B2", student_number="SB2", class_id=cls_b.id, school_id=school.id)
    db.add_all([stu_a1, stu_a2, stu_b1, stu_b2])
    await db.commit()

    user = User(username="flt_teacher", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()

    exam = Exam(name="Filter Exam", school_id=school.id, status="completed", exam_date=date(2026, 5, 1))
    db.add(exam)
    await db.commit()

    subj_math = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    subj_chin = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add_all([subj_math, subj_chin])
    await db.commit()

    q_math = Question(subject_id=subj_math.id, name="M1", question_type="essay", max_score=100.0, school_id=school.id)
    q_chin = Question(subject_id=subj_chin.id, name="C1", question_type="essay", max_score=100.0, school_id=school.id)
    db.add_all([q_math, q_chin])
    await db.commit()

    task = GradingTask(
        subject_id=subj_math.id, school_id=school.id,
        status="completed", total=4, completed=4, failed=0, created_by=user.id,
    )
    db.add(task)
    await db.commit()

    # Concept nodes for KNP
    kp_math = ConceptGraphNode(
        id="kp_math_001", name="函数", knowledge_level="L1",
        primary_module="M1", node_type="concept", synced_at=datetime.now(),
    )
    kp_chin = ConceptGraphNode(
        id="kp_chin_001", name="文言文", knowledge_level="L1",
        primary_module="M2", node_type="concept", synced_at=datetime.now(),
    )
    db.add_all([kp_math, kp_chin])
    await db.commit()

    # QKP: link questions to concepts
    db.add(QuestionKnowledgePoint(question_id=q_math.id, concept_id="kp_math_001"))
    db.add(QuestionKnowledgePoint(question_id=q_chin.id, concept_id="kp_chin_001"))
    await db.commit()

    students = [stu_a1, stu_a2, stu_b1, stu_b2]
    scores_math = [90, 70, 80, 60]
    scores_chin = [85, 75, 65, 55]

    for stu, m_score, c_score in zip(students, scores_math, scores_chin):
        # Math answer + result
        sa_m = StudentAnswer(
            exam_id=exam.id, subject_id=subj_math.id, student_id=stu.id,
            question_id=q_math.id, school_id=school.id,
        )
        db.add(sa_m)
        await db.flush()
        db.add(GradingResult(
            ai_task_id=task.id, answer_id=sa_m.id, question_id=q_math.id,
            school_id=school.id, final_score=float(m_score), max_score=100.0,
            status="confirmed", source="manual",
            ai_raw_response={"details": [{"blanks": [{"correct": m_score >= 80, "reason": "计算错误" if m_score < 80 else ""}]}]},
        ))

        # Chinese answer + result
        sa_c = StudentAnswer(
            exam_id=exam.id, subject_id=subj_chin.id, student_id=stu.id,
            question_id=q_chin.id, school_id=school.id,
        )
        db.add(sa_c)
        await db.flush()
        db.add(GradingResult(
            ai_task_id=task.id, answer_id=sa_c.id, question_id=q_chin.id,
            school_id=school.id, final_score=float(c_score), max_score=100.0,
            status="confirmed", source="manual",
            ai_raw_response={"details": [{"blanks": [{"correct": c_score >= 70, "reason": "审题不清" if c_score < 70 else ""}]}]},
        ))

    await db.commit()

    # KNP mastery records (per student per concept)
    knp_rates_math = [0.90, 0.70, 0.80, 0.60]
    knp_rates_chin = [0.85, 0.75, 0.65, 0.55]
    for stu, m_rate, c_rate in zip(students, knp_rates_math, knp_rates_chin):
        db.add(StudentKnpMastery(
            student_id=stu.id, exam_id=exam.id, concept_id="kp_math_001",
            school_id=school.id, stu_rate=m_rate,
        ))
        db.add(StudentKnpMastery(
            student_id=stu.id, exam_id=exam.id, concept_id="kp_chin_001",
            school_id=school.id, stu_rate=c_rate,
        ))
    await db.commit()

    return {
        "school_id": school.id,
        "exam_id": exam.id,
        "subj_math_id": subj_math.id,
        "subj_chin_id": subj_chin.id,
        "cls_a_id": cls_a.id,
        "cls_b_id": cls_b.id,
        "students": students,
    }


# ===========================================================================
# 1. diagnosis_service — subject_id filter
# ===========================================================================

class TestClassDiagnosisSubjectFilter:
    """class_diagnosis: subject_id now filters KNP by concept->question->subject."""

    @pytest.mark.asyncio
    async def test_no_subject_id_returns_all_concepts(self, db, filter_data):
        from edu_cloud.modules.analytics.diagnosis_service import class_diagnosis
        result = await class_diagnosis(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
        )
        # Without subject filter, both kp_math_001 and kp_chin_001 should appear
        all_concept_ids = set()
        for key in ["worstKnowledges", "unmasterMaxCntKnowledges", "maxScoreDiffKnowledges"]:
            for item in result[key]:
                all_concept_ids.add(item["concept_id"])
        assert "kp_math_001" in all_concept_ids
        assert "kp_chin_001" in all_concept_ids
        assert "filtered_by_subject" not in result

    @pytest.mark.asyncio
    async def test_subject_id_filters_to_math_concepts(self, db, filter_data):
        from edu_cloud.modules.analytics.diagnosis_service import class_diagnosis
        result = await class_diagnosis(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
            subject_id=filter_data["subj_math_id"],
        )
        all_concept_ids = set()
        for key in ["worstKnowledges", "unmasterMaxCntKnowledges", "maxScoreDiffKnowledges"]:
            for item in result[key]:
                all_concept_ids.add(item["concept_id"])
        assert "kp_math_001" in all_concept_ids
        assert "kp_chin_001" not in all_concept_ids
        assert result.get("filtered_by_subject") is True

    @pytest.mark.asyncio
    async def test_nonexistent_subject_id_returns_empty(self, db, filter_data):
        from edu_cloud.modules.analytics.diagnosis_service import class_diagnosis
        result = await class_diagnosis(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
            subject_id="nonexistent_subject",
        )
        assert result["worstKnowledges"] == []
        assert result["weakKnpCount"] == 0
        assert result.get("filtered_by_subject") is True


# ===========================================================================
# 2. insights_service — class_id filter
# ===========================================================================

class TestQuestionInsightsClassFilter:
    """question_insights: class_id narrows to single class."""

    @pytest.mark.asyncio
    async def test_no_class_id_returns_all_students(self, db, filter_data):
        from edu_cloud.modules.analytics.insights_service import question_insights
        result = await question_insights(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
        )
        # All 4 students' data should be included
        total_graded = sum(q["graded_count"] for q in result["questions"])
        # 4 students x 2 subjects = 8 total
        assert total_graded == 8

    @pytest.mark.asyncio
    async def test_class_id_filters_to_class_a(self, db, filter_data):
        from edu_cloud.modules.analytics.insights_service import question_insights
        result = await question_insights(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
            class_id=filter_data["cls_a_id"],
        )
        # Only 2 students in cls_a, across 2 subjects = 4 total
        total_graded = sum(q["graded_count"] for q in result["questions"])
        assert total_graded == 4

    @pytest.mark.asyncio
    async def test_nonexistent_class_id_returns_empty(self, db, filter_data):
        from edu_cloud.modules.analytics.insights_service import question_insights
        result = await question_insights(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
            class_id="nonexistent_class",
        )
        # No students match, but questions may still appear with 0 graded_count
        total_graded = sum(q["graded_count"] for q in result["questions"])
        assert total_graded == 0


# ===========================================================================
# 3. layer_service — subject_id + class_id filter
# ===========================================================================

class TestLayerAnalysisFilters:
    """layer_analysis: subject_id and class_id filters."""

    @pytest.mark.asyncio
    async def test_no_filters_returns_all(self, db, filter_data):
        from edu_cloud.modules.analytics.layer_service import layer_analysis
        result = await layer_analysis(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
        )
        total_students = sum(layer["count"] for layer in result["layers"])
        assert total_students == 4

    @pytest.mark.asyncio
    async def test_class_id_filters_to_class_b(self, db, filter_data):
        from edu_cloud.modules.analytics.layer_service import layer_analysis
        result = await layer_analysis(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
            class_id=filter_data["cls_b_id"],
        )
        total_students = sum(layer["count"] for layer in result["layers"])
        assert total_students == 2

    @pytest.mark.asyncio
    async def test_subject_id_filters_scores(self, db, filter_data):
        from edu_cloud.modules.analytics.layer_service import layer_analysis
        result_all = await layer_analysis(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
        )
        result_math = await layer_analysis(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
            subject_id=filter_data["subj_math_id"],
        )
        # Same number of students, but score distribution may differ
        total_all = sum(layer["count"] for layer in result_all["layers"])
        total_math = sum(layer["count"] for layer in result_math["layers"])
        assert total_all == total_math == 4

    @pytest.mark.asyncio
    async def test_nonexistent_class_id_returns_empty_layers(self, db, filter_data):
        from edu_cloud.modules.analytics.layer_service import layer_analysis
        result = await layer_analysis(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
            class_id="nonexistent_class",
        )
        total_students = sum(layer["count"] for layer in result["layers"])
        assert total_students == 0


# ===========================================================================
# 4. ranking_service — class_error_patterns class_id filter
# ===========================================================================

class TestClassErrorPatternsClassFilter:
    """class_error_patterns: class_id narrows to single class."""

    @pytest.mark.asyncio
    async def test_no_class_id_returns_both_classes(self, db, filter_data):
        from edu_cloud.modules.analytics.ranking_service import class_error_patterns
        result = await class_error_patterns(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
        )
        class_ids_returned = {c["class_id"] for c in result["classes"]}
        assert filter_data["cls_a_id"] in class_ids_returned
        assert filter_data["cls_b_id"] in class_ids_returned

    @pytest.mark.asyncio
    async def test_class_id_filters_to_single_class(self, db, filter_data):
        from edu_cloud.modules.analytics.ranking_service import class_error_patterns
        result = await class_error_patterns(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
            class_id=filter_data["cls_a_id"],
        )
        class_ids_returned = {c["class_id"] for c in result["classes"]}
        assert class_ids_returned == {filter_data["cls_a_id"]}

    @pytest.mark.asyncio
    async def test_nonexistent_class_id_returns_empty(self, db, filter_data):
        from edu_cloud.modules.analytics.ranking_service import class_error_patterns
        result = await class_error_patterns(
            db, exam_id=filter_data["exam_id"], school_id=filter_data["school_id"],
            class_id="nonexistent_class",
            visible_class_ids=["nonexistent_class"],
        )
        assert result["classes"] == []
