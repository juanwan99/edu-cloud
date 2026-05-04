"""W3 student profile steps 1-2 tests."""
import pytest
from sqlalchemy import select

from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, ExamResult
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.profile.models import StudentExamSnapshot, StudentKnowledgeMastery
from edu_cloud.modules.student.models import Class, Student


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def seeded_exam_for_w3(db):
    """Create school + students + exam + results for W3 testing."""
    school = School(name="W3测试校", code="W3TEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    student = Student(
        name="张三", student_number="W3001", school_id=school.id,
        class_id=None, grade="七年级",
    )
    db.add(student)
    await db.flush()

    exam = Exam(name="W3测试考试", school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()

    # Create exam result with detail_scores but NO knowledge data
    db.add(ExamResult(
        exam_id=exam.id, student_id=student.id, school_id=school.id,
        total_score=85.0,
        detail_scores={"math": 85.0},
    ))

    # Create a StudentExamSnapshot so Step 2 has data to enrich
    db.add(StudentExamSnapshot(
        student_id=student.id, exam_id=exam.id, subject_code="math",
        total_score=85.0, max_score=100.0, score_rate=0.85,
        school_id=school.id,
    ))

    await db.commit()
    from types import SimpleNamespace
    return SimpleNamespace(school_id=school.id, exam_id=exam.id, student_id=student.id)


@pytest.fixture
async def seeded_exam_with_knowledge(db):
    """Create school + student + exam + results WITH knowledge scores."""
    school = School(name="W3K测试校", code="W3KTEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    # Seed a knowledge point so FK constraint is satisfied
    from datetime import datetime, timezone
    kp = ConceptGraphNode(id="MATH-001", name="一元一次方程", knowledge_level="L1", primary_module="M1", synced_at=datetime.now(timezone.utc), course_code="math")
    db.add(kp)
    await db.flush()

    student = Student(
        name="李四", student_number="W3K01", school_id=school.id,
        class_id=None, grade="七年级",
    )
    db.add(student)
    await db.flush()

    exam = Exam(name="W3K测试考试", school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()

    # detail_scores with knowledge_scores mapping
    db.add(ExamResult(
        exam_id=exam.id, student_id=student.id, school_id=school.id,
        total_score=90.0,
        detail_scores={
            "math": 90.0,
            "knowledge_scores": {kp.id: {"score": 0.8, "max": 1.0}},
        },
    ))

    db.add(StudentExamSnapshot(
        student_id=student.id, exam_id=exam.id, subject_code="math",
        total_score=90.0, max_score=100.0, score_rate=0.9,
        school_id=school.id,
    ))

    await db.commit()
    from types import SimpleNamespace
    return SimpleNamespace(
        school_id=school.id, exam_id=exam.id,
        student_id=student.id, kp_id=kp.id,
    )


def _make_ctx(db, school_id, exam_id) -> WorkflowContext:
    return WorkflowContext(
        db=db, school_id=school_id,
        trigger_ref=exam_id, run_id="test-run",
        step_outputs={},
    )


# ---------------------------------------------------------------------------
# Step 1 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_knowledge_mastery_graceful_no_knowledge(db, seeded_exam_for_w3):
    """No knowledge data in detail_scores → updated_count=0."""
    from edu_cloud.ai.workflow.w3_student_profile import update_knowledge_mastery

    ctx = _make_ctx(db, seeded_exam_for_w3.school_id, seeded_exam_for_w3.exam_id)
    result = await update_knowledge_mastery(ctx)
    assert result["updated_count"] == 0


@pytest.mark.asyncio
async def test_update_knowledge_mastery_creates_record(db, seeded_exam_with_knowledge):
    """Knowledge data present → creates mastery record."""
    from edu_cloud.ai.workflow.w3_student_profile import update_knowledge_mastery

    data = seeded_exam_with_knowledge
    ctx = _make_ctx(db, data.school_id, data.exam_id)
    result = await update_knowledge_mastery(ctx)
    assert result["updated_count"] == 1

    # Verify record created
    row = (await db.execute(
        select(StudentKnowledgeMastery).where(
            StudentKnowledgeMastery.student_id == data.student_id,
            StudentKnowledgeMastery.concept_id == data.kp_id,
        )
    )).scalars().first()
    assert row is not None
    assert row.attempt_count == 1
    assert row.confidence == 0.3
    assert row.mastery_level == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_update_knowledge_mastery_idempotent_same_exam(db, seeded_exam_with_knowledge):
    """F3: Running the same exam twice should NOT double attempt_count."""
    from edu_cloud.ai.workflow.w3_student_profile import update_knowledge_mastery

    data = seeded_exam_with_knowledge
    ctx = _make_ctx(db, data.school_id, data.exam_id)

    await update_knowledge_mastery(ctx)
    result = await update_knowledge_mastery(ctx)
    # Second run skips already-processed records
    assert result["updated_count"] == 0

    row = (await db.execute(
        select(StudentKnowledgeMastery).where(
            StudentKnowledgeMastery.student_id == data.student_id,
            StudentKnowledgeMastery.concept_id == data.kp_id,
        )
    )).scalars().first()
    assert row.attempt_count == 1  # NOT 2


# ---------------------------------------------------------------------------
# Step 2 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_student_profiles_adds_trend(db, seeded_exam_for_w3):
    """After running step 2, error_summary has trend data."""
    from edu_cloud.ai.workflow.w3_student_profile import update_student_profiles

    ctx = _make_ctx(db, seeded_exam_for_w3.school_id, seeded_exam_for_w3.exam_id)
    result = await update_student_profiles(ctx)
    assert result["profile_count"] == 1

    snap = (await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == seeded_exam_for_w3.exam_id,
        )
    )).scalars().first()
    assert snap.error_summary is not None
    assert "trend" in snap.error_summary
    assert "exam_count" in snap.error_summary


@pytest.mark.asyncio
async def test_update_student_profiles_no_snapshots(db):
    """Empty DB → profile_count=0."""
    from edu_cloud.ai.workflow.w3_student_profile import update_student_profiles

    # Create a minimal school for a valid context
    school = School(name="空校", code="EMPTY", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    exam = Exam(name="空考试", school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()
    await db.commit()

    ctx = _make_ctx(db, school.id, exam.id)
    result = await update_student_profiles(ctx)
    assert result["profile_count"] == 0


@pytest.mark.asyncio
async def test_update_student_profiles_trend_with_history(db, seeded_exam_for_w3):
    """With multiple exam snapshots, trend data reflects history."""
    from edu_cloud.ai.workflow.w3_student_profile import update_student_profiles

    data = seeded_exam_for_w3

    # Add a second historical exam + snapshot (same student, same subject)
    # Use exam_date to ensure proper chronological ordering
    from datetime import datetime, timedelta, timezone
    old_date = datetime(2025, 12, 1, tzinfo=timezone.utc)
    new_date = datetime(2026, 1, 15, tzinfo=timezone.utc)

    exam2 = Exam(name="历史考试", school_id=data.school_id, semester="2025-2026-1")
    db.add(exam2)
    await db.flush()

    db.add(StudentExamSnapshot(
        student_id=data.student_id, exam_id=exam2.id, subject_code="math",
        total_score=78.0, max_score=100.0, score_rate=0.78,
        school_id=data.school_id, exam_date=old_date,
    ))

    # Update the current exam snapshot to have a later exam_date
    current_snap = (await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == data.exam_id,
        )
    )).scalars().first()
    current_snap.exam_date = new_date

    await db.commit()

    ctx = _make_ctx(db, data.school_id, data.exam_id)
    result = await update_student_profiles(ctx)
    assert result["profile_count"] == 1

    snap = (await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == data.exam_id,
        )
    )).scalars().first()
    assert snap.error_summary["exam_count"] == 2
    assert snap.error_summary["trend"] == "improving"  # 78 → 85


# ---------------------------------------------------------------------------
# Step 3 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_class_weakness_no_data(db):
    """No mastery data → class_count=0."""
    from edu_cloud.ai.workflow.w3_student_profile import compute_class_weakness

    school = School(name="空校3", code="EMPTY3", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    await db.commit()

    ctx = _make_ctx(db, school.id, "daily")
    result = await compute_class_weakness(ctx)
    assert result["class_count"] == 0


@pytest.mark.asyncio
async def test_compute_class_weakness_finds_low_mastery(db):
    """Low mastery records → class weakness findings created."""
    from edu_cloud.ai.workflow.w3_student_profile import compute_class_weakness
    from edu_cloud.models.agent_finding import AgentFinding

    school = School(name="弱校", code="WEAK1", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls = Class(name="七(1)班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.flush()

    student = Student(
        name="王五", student_number="WK01", school_id=school.id,
        class_id=cls.id, grade="七年级",
    )
    db.add(student)
    await db.flush()

    from datetime import datetime, timezone
    kp = ConceptGraphNode(id="MATH-W1", name="方程", knowledge_level="L1", primary_module="M1", synced_at=datetime.now(timezone.utc), course_code="math")
    db.add(kp)
    await db.flush()

    # Low mastery (0.2 < 0.4 threshold)
    db.add(StudentKnowledgeMastery(
        student_id=student.id, concept_id=kp.id,
        mastery_level=0.2, confidence=0.5, attempt_count=3,
        correct_count=0, partial_count=1, trend="declining",
        school_id=school.id,
    ))
    await db.commit()

    ctx = _make_ctx(db, school.id, "daily")
    result = await compute_class_weakness(ctx)
    assert result["class_count"] == 1

    # Verify AgentFinding created
    findings = (await db.execute(
        select(AgentFinding).where(
            AgentFinding.finding_type == "class_weakness",
            AgentFinding.school_id == school.id,
        )
    )).scalars().all()
    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].target_id == cls.id


@pytest.mark.asyncio
async def test_compute_class_weakness_ignores_high_mastery(db):
    """Mastery >= 0.4 → not counted as weakness."""
    from edu_cloud.ai.workflow.w3_student_profile import compute_class_weakness

    school = School(name="强校", code="STRONG1", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls = Class(name="七(2)班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.flush()

    student = Student(
        name="赵六", student_number="ST01", school_id=school.id,
        class_id=cls.id, grade="七年级",
    )
    db.add(student)
    await db.flush()

    from datetime import datetime, timezone
    kp = ConceptGraphNode(id="MATH-S1", name="函数", knowledge_level="L1", primary_module="M1", synced_at=datetime.now(timezone.utc), course_code="math")
    db.add(kp)
    await db.flush()

    # Mastery at threshold (0.4) → NOT weak
    db.add(StudentKnowledgeMastery(
        student_id=student.id, concept_id=kp.id,
        mastery_level=0.4, confidence=0.6, attempt_count=5,
        correct_count=2, partial_count=1, trend="stable",
        school_id=school.id,
    ))
    await db.commit()

    ctx = _make_ctx(db, school.id, "daily")
    result = await compute_class_weakness(ctx)
    assert result["class_count"] == 0


# ---------------------------------------------------------------------------
# Step 4 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_learning_advice_no_data(db):
    """No low mastery students → advice_count=0."""
    from edu_cloud.ai.workflow.w3_student_profile import generate_learning_advice

    school = School(name="空校4", code="EMPTY4", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    await db.commit()

    ctx = _make_ctx(db, school.id, "daily")
    result = await generate_learning_advice(ctx)
    assert result["advice_count"] == 0


@pytest.mark.asyncio
async def test_generate_learning_advice_creates_tasks(db):
    """Creates AgentTask records for students with low mastery."""
    from edu_cloud.ai.workflow.w3_student_profile import generate_learning_advice
    from edu_cloud.models.agent_finding import AgentTask

    school = School(name="建议校", code="ADV1", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls = Class(name="七(3)班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.flush()

    student = Student(
        name="钱七", student_number="ADV01", school_id=school.id,
        class_id=cls.id, grade="七年级",
    )
    db.add(student)
    await db.flush()

    from datetime import datetime, timezone
    kp = ConceptGraphNode(
        id="MATH-A1", name="几何", course_code="math",
        node_type="concept", knowledge_level="L1", primary_module="M1",
        synced_at=datetime.now(timezone.utc),
    )
    db.add(kp)
    await db.flush()

    db.add(StudentKnowledgeMastery(
        student_id=student.id, concept_id=kp.id,
        mastery_level=0.15, confidence=0.4, attempt_count=4,
        correct_count=0, partial_count=1, trend="declining",
        school_id=school.id,
    ))
    await db.commit()

    ctx = _make_ctx(db, school.id, "daily")
    result = await generate_learning_advice(ctx)
    assert result["advice_count"] == 1

    # Verify AgentTask created
    tasks = (await db.execute(
        select(AgentTask).where(
            AgentTask.task_type == "learning_advice",
            AgentTask.school_id == school.id,
        )
    )).scalars().all()
    assert len(tasks) == 1
    assert tasks[0].assignee_role == "homeroom_teacher"
    assert tasks[0].status == "pending"
    assert tasks[0].payload["student_id"] == student.id


# ---------------------------------------------------------------------------
# W3 Definition test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_w3_definition_has_4_steps():
    from edu_cloud.ai.workflow.w3_student_profile import W3_STUDENT_PROFILE
    assert len(W3_STUDENT_PROFILE.steps) == 4
    assert W3_STUDENT_PROFILE.steps[2].name == "compute_class_weakness"
    assert W3_STUDENT_PROFILE.steps[3].name == "generate_learning_advice"
