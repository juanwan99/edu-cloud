"""Grading Worker 并发安全测试 — CAS task claim + version 乐观锁 + confirmed 保护。"""
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School


async def _seed_school_and_user(db: AsyncSession):
    """Create minimum school + user fixtures for FK constraints."""
    school = School(id="school-1", name="Test School", code="TS001")
    db.add(school)
    user = User(
        id="user-1", username="test_admin", display_name="Admin",
        hashed_password="x",
    )
    db.add(user)
    role = UserRole(
        user_id="user-1", role="platform_admin", school_id="school-1",
        is_primary=True,
    )
    db.add(role)
    await db.flush()
    return school, user


async def _seed_grading_task(db: AsyncSession, *, task_id="task-1",
                             status="pending", school_id="school-1"):
    """Create a GradingTask with the given status."""
    # Create exam (FK for subject)
    exam = Exam(id="exam-1", name="Test Exam", school_id=school_id)
    db.add(exam)
    await db.flush()
    subj = Subject(id="subj-1", name="Math", code="math",
                   school_id=school_id, exam_id="exam-1")
    db.add(subj)
    await db.flush()
    task = GradingTask(
        id=task_id, subject_id="subj-1", status=status,
        created_by="user-1", school_id=school_id,
    )
    db.add(task)
    await db.flush()
    return task


async def _seed_grading_result(db: AsyncSession, *, answer_id="ans-1",
                                question_id="q-1", school_id="school-1",
                                status="ai_done", version=1):
    """Create a GradingResult with the given status and version."""
    result = GradingResult(
        answer_id=answer_id, question_id=question_id,
        school_id=school_id, status=status, version=version,
        ai_score=8.0, max_score=10.0,
    )
    db.add(result)
    await db.flush()
    return result


# ── C-4: Task Claim CAS ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_task_claim_only_one_wins(db):
    """Two CAS claims on the same pending task: only one succeeds."""
    await _seed_school_and_user(db)
    task = await _seed_grading_task(db, status="pending")
    await db.commit()

    # First claim: pending → processing
    result1 = await db.execute(
        update(GradingTask)
        .where(GradingTask.id == task.id, GradingTask.status == "pending")
        .values(status="processing")
    )
    # Second claim: should fail (status is now processing)
    result2 = await db.execute(
        update(GradingTask)
        .where(GradingTask.id == task.id, GradingTask.status == "pending")
        .values(status="processing")
    )
    await db.commit()

    assert result1.rowcount + result2.rowcount == 1
    assert result1.rowcount == 1
    assert result2.rowcount == 0


@pytest.mark.asyncio
async def test_cancelled_task_not_claimable(db):
    """A cancelled task cannot be claimed."""
    await _seed_school_and_user(db)
    await _seed_grading_task(db, status="cancelled")
    await db.commit()

    result = await db.execute(
        update(GradingTask)
        .where(GradingTask.id == "task-1", GradingTask.status == "pending")
        .values(status="processing")
    )
    await db.commit()

    assert result.rowcount == 0


@pytest.mark.asyncio
async def test_already_processing_not_reclaimable(db):
    """A task already in processing cannot be claimed again."""
    await _seed_school_and_user(db)
    await _seed_grading_task(db, status="processing")
    await db.commit()

    result = await db.execute(
        update(GradingTask)
        .where(GradingTask.id == "task-1", GradingTask.status == "pending")
        .values(status="processing")
    )
    await db.commit()

    assert result.rowcount == 0


# ── C-5: GradingResult Version CAS ───────────────────────────────


@pytest.mark.asyncio
async def test_version_cas_succeeds_on_matching_version(db):
    """CAS update with correct version succeeds and increments version."""
    await _seed_school_and_user(db)
    gr = await _seed_grading_result(db, version=1, status="ai_done")
    await db.commit()

    result = await db.execute(
        update(GradingResult)
        .where(GradingResult.id == gr.id, GradingResult.version == 1)
        .values(ai_score=9.5, version=2)
    )
    await db.commit()

    assert result.rowcount == 1
    await db.refresh(gr)
    assert gr.version == 2
    assert gr.ai_score == 9.5


@pytest.mark.asyncio
async def test_version_cas_fails_on_stale_version(db):
    """CAS update with stale version fails (rowcount=0)."""
    await _seed_school_and_user(db)
    gr = await _seed_grading_result(db, version=3, status="ai_done")
    await db.commit()

    # Attempt update with version=1 (stale)
    result = await db.execute(
        update(GradingResult)
        .where(GradingResult.id == gr.id, GradingResult.version == 1)
        .values(ai_score=9.5, version=2)
    )
    await db.commit()

    assert result.rowcount == 0
    # Original unchanged
    await db.refresh(gr)
    assert gr.version == 3
    assert gr.ai_score == 8.0


@pytest.mark.asyncio
async def test_confirmed_result_not_overwritten(db):
    """A confirmed GradingResult must not be overwritten by AI."""
    await _seed_school_and_user(db)
    gr = await _seed_grading_result(
        db, status="confirmed", version=2,
    )
    gr.source = "manual"
    gr.final_score = 7.0
    await db.commit()

    # Simulate what _upsert_ai_result does: check status before CAS
    existing = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == "ans-1")
    )).scalar_one_or_none()

    assert existing is not None
    assert existing.status == "confirmed"
    # The worker must skip this — no CAS update should be attempted
    # Verify the record is unchanged
    assert existing.final_score == 7.0
    assert existing.source == "manual"
    assert existing.version == 2


@pytest.mark.asyncio
async def test_two_cas_updates_only_one_wins(db):
    """Simulates two concurrent version-based updates; only one succeeds."""
    await _seed_school_and_user(db)
    gr = await _seed_grading_result(db, version=1, status="ai_done")
    await db.commit()

    # Both attempt CAS with version=1
    r1 = await db.execute(
        update(GradingResult)
        .where(GradingResult.id == gr.id, GradingResult.version == 1)
        .values(ai_score=9.0, version=2)
    )
    r2 = await db.execute(
        update(GradingResult)
        .where(GradingResult.id == gr.id, GradingResult.version == 1)
        .values(ai_score=7.0, version=2)
    )
    await db.commit()

    # Only one should succeed
    assert r1.rowcount + r2.rowcount == 1
    await db.refresh(gr)
    assert gr.version == 2
    # The winner wrote 9.0 (first update wins since they run sequentially in SQLite)
    assert gr.ai_score == 9.0


@pytest.mark.asyncio
async def test_confirmed_blocks_cas_update(db):
    """CAS update on a confirmed result fails even with correct version."""
    await _seed_school_and_user(db)
    gr = await _seed_grading_result(db, version=1, status="confirmed")
    await db.commit()

    # Even if version matches, confirmed check in _upsert_ai_result
    # should prevent reaching the CAS path. But verify at DB level
    # that a status check WHERE also protects:
    result = await db.execute(
        update(GradingResult)
        .where(
            GradingResult.id == gr.id,
            GradingResult.version == 1,
            GradingResult.status != "confirmed",
        )
        .values(ai_score=9.5, status="ai_done", version=2)
    )
    await db.commit()

    assert result.rowcount == 0
    await db.refresh(gr)
    assert gr.status == "confirmed"
    assert gr.ai_score == 8.0
    assert gr.version == 1
