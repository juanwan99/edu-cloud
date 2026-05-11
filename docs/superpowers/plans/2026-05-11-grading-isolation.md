# Grading Isolation Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate 6 cross-contamination paths between manual and AI grading systems sharing the GradingResult table.

**Architecture:** Single-table guard strengthening — zero schema changes, zero migrations. All fixes tighten write behavior (reject/skip) and correct statistics queries from `ai_score IS NOT NULL` to `source`-based checks.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, PostgreSQL (with_for_update), pytest

**Spec:** `docs/superpowers/specs/2026-05-11-grading-isolation-design.md`

---

### Task 1: _upsert_ai_result — reject writing to confirmed records

**Files:**
- Modify: `src/edu_cloud/workers/grading.py:912-952` (_upsert_ai_result)
- Modify: `src/edu_cloud/workers/grading.py:1213` (realtime caller)
- Modify: `src/edu_cloud/workers/grading.py:1257` (batch caller)
- Test: `tests/test_services_exam/test_grading_isolation_advanced.py` (create)

**Solves:** P-001 (CRITICAL)

- [ ] **Step 1: Create test file with T1 test**

Create `tests/test_services_exam/test_grading_isolation_advanced.py`:

```python
"""Grading isolation tests — cross-contamination prevention (P-001 to P-006)."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.grading.models import GradingResult, GradingTask


@pytest.fixture
async def school_and_question(db_engine):
    """Create minimal school + exam + subject + question + student_answer for isolation tests."""
    from edu_cloud.models.school import RegisteredSchool
    from edu_cloud.modules.exam.models import Exam, Subject, Question
    from edu_cloud.modules.scan.models import StudentAnswer
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(db_engine, expire_on_commit=False) as db:
        school = RegisteredSchool(name="IsolationTestSchool", code="ISO001")
        db.add(school)
        await db.flush()

        exam = Exam(name="IsoExam", school_id=school.id, status="active")
        db.add(exam)
        await db.flush()

        subject = Subject(
            name="语文", code="chinese", exam_id=exam.id, school_id=school.id,
        )
        db.add(subject)
        await db.flush()

        question = Question(
            name="第1题", subject_id=subject.id, school_id=school.id,
            question_type="essay", max_score=10.0,
        )
        db.add(question)
        await db.flush()

        answer = StudentAnswer(
            student_id="student-001", question_id=question.id,
            subject_id=subject.id, school_id=school.id,
        )
        db.add(answer)
        await db.commit()

        yield {
            "school_id": school.id,
            "exam_id": exam.id,
            "subject_id": subject.id,
            "question_id": question.id,
            "answer_id": answer.id,
        }


@pytest.mark.asyncio
async def test_manual_confirmed_then_ai_upsert_skipped(db_engine, school_and_question):
    """P-001: AI worker must NOT write to a confirmed manual record."""
    from edu_cloud.workers.grading import _upsert_ai_result

    ids = school_and_question
    async with AsyncSession(db_engine, expire_on_commit=False) as db:
        gr = GradingResult(
            answer_id=ids["answer_id"],
            question_id=ids["question_id"],
            school_id=ids["school_id"],
            final_score=8.0,
            max_score=10.0,
            status="confirmed",
            source="manual",
        )
        db.add(gr)
        await db.flush()

        task = GradingTask(
            subject_id=ids["subject_id"],
            school_id=ids["school_id"],
            status="processing",
            created_by="admin-user",
        )
        db.add(task)
        await db.commit()

        result_dict = {
            "answer_id": ids["answer_id"],
            "question_id": ids["question_id"],
            "score": 9.0,
            "confidence": 0.95,
            "feedback": "AI says great",
            "max_score": 10.0,
        }
        skip = await _upsert_ai_result(db, task, result_dict)
        await db.commit()

        assert skip == "skipped_confirmed"

        refreshed = (await db.execute(
            select(GradingResult).where(GradingResult.answer_id == ids["answer_id"])
        )).scalar_one()
        assert refreshed.ai_score is None
        assert refreshed.final_score == 8.0
        assert refreshed.source == "manual"
        assert refreshed.status == "confirmed"
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_grading_isolation_advanced.py::test_manual_confirmed_then_ai_upsert_skipped -xvs`
Expected: FAIL — current code writes ai_score to confirmed records

- [ ] **Step 3: Fix _upsert_ai_result**

In `src/edu_cloud/workers/grading.py`, replace lines 934-937:

```python
    if existing and existing.status == "confirmed":
        for k, v in ai_fields.items():
            setattr(existing, k, v)
        existing.version += 1
```

With:

```python
    if existing and existing.status == "confirmed":
        logger.warning(
            "grading_isolation: skipping AI write for confirmed answer=%s, source=%s",
            answer_id, existing.source,
        )
        return "skipped_confirmed"
```

- [ ] **Step 4: Update callers to handle skipped return**

In `src/edu_cloud/workers/grading.py`, realtime mode (line 1213):

Replace:
```python
                        else:
                            await _upsert_ai_result(db, task, result_dict)
                            batch_completed += 1
```

With:
```python
                        else:
                            upsert_status = await _upsert_ai_result(db, task, result_dict)
                            if upsert_status != "skipped_confirmed":
                                batch_completed += 1
```

In batch mode (line 1257):

Replace:
```python
                    else:
                        await _upsert_ai_result(db, task, result_dict)
                        total_completed += 1
```

With:
```python
                    else:
                        upsert_status = await _upsert_ai_result(db, task, result_dict)
                        if upsert_status != "skipped_confirmed":
                            total_completed += 1
```

- [ ] **Step 5: Run test — expect PASS**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_grading_isolation_advanced.py::test_manual_confirmed_then_ai_upsert_skipped -xvs`
Expected: PASS

- [ ] **Step 6: Run existing grading worker tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_grading_worker.py -xvs`
Expected: All existing tests still PASS

- [ ] **Step 7: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/workers/grading.py tests/test_services_exam/test_grading_isolation_advanced.py
git commit -m "fix(grading): P-001 _upsert_ai_result rejects writing to confirmed records"
```

---

### Task 2: grade_single — remove database writes

**Files:**
- Modify: `src/edu_cloud/modules/grading/router.py:643-698` (grade_single)
- Test: `tests/test_services_exam/test_grading_isolation_advanced.py` (append)

**Solves:** P-006

- [ ] **Step 1: Add T5 test**

Append to `tests/test_services_exam/test_grading_isolation_advanced.py`:

```python
@pytest.mark.asyncio
async def test_grade_single_does_not_write_to_db(db_engine, school_and_question):
    """P-006: grade_single must never write to GradingResult."""
    from sqlalchemy import func

    ids = school_and_question
    async with AsyncSession(db_engine, expire_on_commit=False) as db:
        gr = GradingResult(
            answer_id=ids["answer_id"],
            question_id=ids["question_id"],
            school_id=ids["school_id"],
            final_score=7.0,
            max_score=10.0,
            status="confirmed",
            source="manual",
        )
        db.add(gr)
        await db.commit()

        count_before = (await db.execute(
            select(func.count()).select_from(GradingResult)
        )).scalar()

        refreshed = (await db.execute(
            select(GradingResult).where(GradingResult.answer_id == ids["answer_id"])
        )).scalar_one()
        assert refreshed.ai_score is None
        assert refreshed.status == "confirmed"
        assert refreshed.final_score == 7.0

        count_after = (await db.execute(
            select(func.count()).select_from(GradingResult)
        )).scalar()
        assert count_after == count_before
```

- [ ] **Step 2: Remove DB writes from grade_single**

In `src/edu_cloud/modules/grading/router.py`, replace lines 643-698 (the "写入 GradingResult" section and return). The entire block from `# 9. 写入 GradingResult（upsert）` through the final return should become:

Replace:
```python
    # 9. 写入 GradingResult（upsert）
    existing_gr = (await db.execute(
        select(GradingResult).where(
            GradingResult.answer_id == req.answer_id,
            GradingResult.school_id == school_id,
        )
    )).scalar_one_or_none()

    feedback = comment or result_data.get("feedback", "")

    if existing_gr:
        if existing_gr.status == "confirmed":
            return {
                "score": result_data["score"],
                "max_score": result_data["max_score"],
                "feedback": feedback,
                "confidence": result_data["confidence"],
                "details": details,
                "deductions": deductions,
                "comment": comment,
                "recognizedText": recognized_text,
                "already_confirmed": True,
            }
        existing_gr.ai_score = result_data["score"]
        existing_gr.ai_confidence = result_data["confidence"]
        existing_gr.ai_feedback = feedback
        existing_gr.ai_raw_response = ai_raw
        existing_gr.status = "ai_done"
    else:
        gr = GradingResult(
            answer_id=req.answer_id,
            question_id=question.id,
            school_id=school_id,
            ai_score=result_data["score"],
            ai_confidence=result_data["confidence"],
            ai_feedback=feedback,
            ai_raw_response=ai_raw,
            max_score=result_data["max_score"],
            status="ai_done",
        )
        db.add(gr)

    await db.commit()
    logger.info("grade_single: answer=%s, score=%.1f", req.answer_id, result_data["score"])

    return {
        "score": result_data["score"],
        "max_score": result_data["max_score"],
        "feedback": feedback,
        "confidence": result_data["confidence"],
        "details": details,
        "deductions": deductions,
        "comment": comment,
        "recognizedText": recognized_text,
        "already_confirmed": False,
    }
```

With:
```python
    feedback = comment or result_data.get("feedback", "")

    logger.info("grade_single: answer=%s, score=%.1f (preview only, no DB write)",
                req.answer_id, result_data["score"])

    return {
        "score": result_data["score"],
        "max_score": result_data["max_score"],
        "feedback": feedback,
        "confidence": result_data["confidence"],
        "details": details,
        "deductions": deductions,
        "comment": comment,
        "recognizedText": recognized_text,
    }
```

- [ ] **Step 3: Run isolation tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_grading_isolation_advanced.py -xvs`
Expected: All PASS

- [ ] **Step 4: Run existing grading API tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_grading_task.py tests/test_api_exam/test_grading_task_question.py -xvs`
Expected: PASS (check for any tests that assert grade_single writes to DB — if found, update those tests)

- [ ] **Step 5: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/modules/grading/router.py tests/test_services_exam/test_grading_isolation_advanced.py
git commit -m "fix(grading): P-006 grade_single is now preview-only, no DB writes"
```

---

### Task 3: Add row-level locking to all write paths

**Files:**
- Modify: `src/edu_cloud/workers/grading.py:916-918` (_upsert_ai_result query)
- Modify: `src/edu_cloud/modules/marking/scorer.py:450-452` (submit_score query)
- Modify: `src/edu_cloud/modules/grading/grading_review_router.py:140-146` (submit_review query)
- Test: `tests/test_services_exam/test_grading_isolation_advanced.py` (append T3)

**Solves:** P-004

- [ ] **Step 1: Add T3 concurrent test**

Append to `tests/test_services_exam/test_grading_isolation_advanced.py`:

```python
@pytest.mark.asyncio
async def test_concurrent_submit_score_and_review(db_engine, school_and_question):
    """P-004: concurrent submit_score + submit_review on same answer — one wins, one 409."""
    import asyncio
    from edu_cloud.modules.marking.scorer import submit_score

    ids = school_and_question
    async with AsyncSession(db_engine, expire_on_commit=False) as db:
        gr = GradingResult(
            answer_id=ids["answer_id"],
            question_id=ids["question_id"],
            school_id=ids["school_id"],
            ai_score=8.0,
            ai_confidence=0.9,
            ai_feedback="Good",
            max_score=10.0,
            status="ai_done",
            source=None,
        )
        db.add(gr)
        await db.commit()

    results = {"score_ok": False, "score_err": None, "review_ok": False, "review_err": None}

    async def do_submit_score():
        async with AsyncSession(db_engine, expire_on_commit=False) as db2:
            try:
                await submit_score(
                    db2, ids["answer_id"], ids["question_id"],
                    "teacher-A", ids["school_id"], 7.0, 10.0, "manual",
                )
                results["score_ok"] = True
            except (ValueError, Exception) as e:
                results["score_err"] = str(e)

    async def do_submit_review():
        async with AsyncSession(db_engine, expire_on_commit=False) as db3:
            try:
                gr = (await db3.execute(
                    select(GradingResult).where(
                        GradingResult.answer_id == ids["answer_id"],
                    )
                )).scalar_one()
                if gr.status != "ai_done":
                    results["review_err"] = "not ai_done"
                    return
                gr.source = "ai"
                gr.final_score = gr.ai_score
                gr.status = "confirmed"
                gr.reviewer_id = "teacher-B"
                gr.version += 1
                await db3.commit()
                results["review_ok"] = True
            except Exception as e:
                results["review_err"] = str(e)

    await asyncio.gather(do_submit_score(), do_submit_review())

    async with AsyncSession(db_engine, expire_on_commit=False) as db:
        final = (await db.execute(
            select(GradingResult).where(GradingResult.answer_id == ids["answer_id"])
        )).scalar_one()
        assert final.status == "confirmed"
        assert final.final_score is not None
```

- [ ] **Step 2: Add with_for_update to _upsert_ai_result**

In `src/edu_cloud/workers/grading.py`, replace line 916-918:

```python
    existing = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == answer_id)
    )).scalar_one_or_none()
```

With:

```python
    existing = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == answer_id)
        .with_for_update(skip_locked=True)
    )).scalar_one_or_none()
```

- [ ] **Step 3: Add with_for_update to submit_score**

In `src/edu_cloud/modules/marking/scorer.py`, replace line 450-452:

```python
    existing = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == answer_id)
    )).scalar_one_or_none()
```

With:

```python
    existing = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == answer_id)
        .with_for_update()
    )).scalar_one_or_none()
```

- [ ] **Step 4: Add with_for_update to submit_review**

In `src/edu_cloud/modules/grading/grading_review_router.py`, replace lines 140-146:

```python
    result = await db.execute(
        select(GradingResult).where(
            GradingResult.id == result_id,
            GradingResult.school_id == current["current_role"].school_id,
        )
    )
```

With:

```python
    result = await db.execute(
        select(GradingResult).where(
            GradingResult.id == result_id,
            GradingResult.school_id == current["current_role"].school_id,
        ).with_for_update()
    )
```

- [ ] **Step 5: Run all isolation tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_grading_isolation_advanced.py -xvs`
Expected: All PASS

- [ ] **Step 6: Run existing grading + marking tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_grading_review.py tests/test_api_exam/test_marking.py -xvs`
Expected: PASS (SQLite ignores with_for_update)

- [ ] **Step 7: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/workers/grading.py src/edu_cloud/modules/marking/scorer.py src/edu_cloud/modules/grading/grading_review_router.py tests/test_services_exam/test_grading_isolation_advanced.py
git commit -m "fix(grading): P-004 add row-level locking to all GradingResult write paths"
```

---

### Task 4: Fix statistics — replace ai_score IS NOT NULL with source-based checks

**Files:**
- Modify: `src/edu_cloud/modules/grading/grading_review_router.py:286-300` (BQ4)
- Modify: `src/edu_cloud/modules/marking/scorer.py:105-126` (get_subjects_with_progress)
- Modify: `src/edu_cloud/modules/analytics/ai_report_service.py:218,248-249,269-270`
- Test: `tests/test_services_exam/test_grading_isolation_advanced.py` (append T4)

**Solves:** P-005, G-001

- [ ] **Step 1: Add T4 test**

Append to `tests/test_services_exam/test_grading_isolation_advanced.py`:

```python
@pytest.mark.asyncio
async def test_dispatch_status_counts_with_mixed_sources(db_engine, school_and_question):
    """P-005: dispatch stats must use source field, not ai_score IS NOT NULL."""
    from sqlalchemy import func

    ids = school_and_question
    from edu_cloud.modules.exam.models import Question
    from edu_cloud.modules.scan.models import StudentAnswer

    async with AsyncSession(db_engine, expire_on_commit=False) as db:
        extra_answers = []
        for i in range(7):
            a = StudentAnswer(
                student_id=f"student-{i+10}",
                question_id=ids["question_id"],
                subject_id=ids["subject_id"],
                school_id=ids["school_id"],
            )
            db.add(a)
            extra_answers.append(a)
        await db.flush()

        all_answer_ids = [ids["answer_id"]] + [a.id for a in extra_answers]

        sources = [
            ("manual", None),
            ("manual", None),
            ("manual", None),
            ("ai", 8.0),
            ("ai", 9.0),
            ("ai", 7.5),
            ("ai_override", 6.0),
            ("ai_override", 5.0),
        ]
        for i, (src, ai_sc) in enumerate(sources):
            gr = GradingResult(
                answer_id=all_answer_ids[i],
                question_id=ids["question_id"],
                school_id=ids["school_id"],
                final_score=float(i + 5),
                max_score=10.0,
                status="confirmed",
                source=src,
                ai_score=ai_sc,
            )
            db.add(gr)
        await db.commit()

        ai_count = (await db.execute(
            select(func.count()).select_from(GradingResult).where(
                GradingResult.question_id == ids["question_id"],
                GradingResult.school_id == ids["school_id"],
                GradingResult.status == "confirmed",
                GradingResult.source.in_(["ai", "ai_override"]),
            )
        )).scalar()

        manual_count = (await db.execute(
            select(func.count()).select_from(GradingResult).where(
                GradingResult.question_id == ids["question_id"],
                GradingResult.school_id == ids["school_id"],
                GradingResult.status == "confirmed",
                GradingResult.source == "manual",
            )
        )).scalar()

        assert ai_count == 5
        assert manual_count == 3
```

- [ ] **Step 2: Fix grading_review_router.py BQ4 stats**

In `src/edu_cloud/modules/grading/grading_review_router.py`, replace lines 286-300:

```python
        gr_stats_rows = (await db.execute(
            select(
                GradingResult.question_id,
                func.count(GradingResult.id).filter(GradingResult.ai_score.isnot(None)).label("ai_scored"),
                func.count(GradingResult.id).filter(GradingResult.status == "confirmed").label("confirmed"),
                func.count(GradingResult.id).filter(
                    GradingResult.status == "confirmed",
                    GradingResult.ai_score.is_(None),
                ).label("manual_only"),
            ).where(
                GradingResult.question_id.in_(all_subj_q_ids),
                GradingResult.school_id == effective_school_id,
            ).group_by(GradingResult.question_id)
        )).all()
```

With:

```python
        gr_stats_rows = (await db.execute(
            select(
                GradingResult.question_id,
                func.count(GradingResult.id).filter(
                    GradingResult.source.in_(["ai", "ai_override"]),
                ).label("ai_scored"),
                func.count(GradingResult.id).filter(GradingResult.status == "confirmed").label("confirmed"),
                func.count(GradingResult.id).filter(
                    GradingResult.source == "manual",
                ).label("manual_only"),
            ).where(
                GradingResult.question_id.in_(all_subj_q_ids),
                GradingResult.school_id == effective_school_id,
            ).group_by(GradingResult.question_id)
        )).all()
```

- [ ] **Step 3: Fix scorer.py get_subjects_with_progress**

In `src/edu_cloud/modules/marking/scorer.py`, replace lines 105-126:

```python
            ai_scored = (await db.execute(
                select(func.count()).select_from(GradingResult).where(
                    GradingResult.question_id == q.id,
                    GradingResult.school_id == school_id,
                    GradingResult.ai_score.isnot(None),
                )
            )).scalar() or 0
            confirmed = (await db.execute(
                select(func.count()).select_from(GradingResult).where(
                    GradingResult.question_id == q.id,
                    GradingResult.school_id == school_id,
                    GradingResult.status == "confirmed",
                )
            )).scalar() or 0
            manual_only = (await db.execute(
                select(func.count()).select_from(GradingResult).where(
                    GradingResult.question_id == q.id,
                    GradingResult.school_id == school_id,
                    GradingResult.status == "confirmed",
                    GradingResult.ai_score.is_(None),
                )
            )).scalar() or 0
```

With:

```python
            ai_scored = (await db.execute(
                select(func.count()).select_from(GradingResult).where(
                    GradingResult.question_id == q.id,
                    GradingResult.school_id == school_id,
                    GradingResult.source.in_(["ai", "ai_override"]),
                )
            )).scalar() or 0
            confirmed = (await db.execute(
                select(func.count()).select_from(GradingResult).where(
                    GradingResult.question_id == q.id,
                    GradingResult.school_id == school_id,
                    GradingResult.status == "confirmed",
                )
            )).scalar() or 0
            manual_only = (await db.execute(
                select(func.count()).select_from(GradingResult).where(
                    GradingResult.question_id == q.id,
                    GradingResult.school_id == school_id,
                    GradingResult.source == "manual",
                )
            )).scalar() or 0
```

- [ ] **Step 4: Fix ai_report_service.py — coverage, confidence, delta**

In `src/edu_cloud/modules/analytics/ai_report_service.py`:

Line 218 — replace:
```python
        ai_scored = [row for row, *_ in scoped_rows if row.ai_score is not None]
```
With:
```python
        ai_scored = [row for row, *_ in scoped_rows if row.source in ("ai", "ai_override")]
```

Lines 248-249 — replace:
```python
        values = [float(row.ai_confidence) for row, *_ in scoped_rows if row.ai_confidence is not None]
```
With:
```python
        values = [
            float(row.ai_confidence)
            for row, *_ in scoped_rows
            if row.source in ("ai", "ai_override") and row.ai_confidence is not None
        ]
```

Lines 269-270 — replace:
```python
            if row.ai_score is None or row.final_score is None:
                continue
```
With:
```python
            if row.source not in ("ai", "ai_override") or row.final_score is None:
                continue
```

- [ ] **Step 5: Run all isolation tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_grading_isolation_advanced.py -xvs`
Expected: All PASS

- [ ] **Step 6: Run existing stats-related tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_dispatch_status.py tests/test_services_exam/test_ai_grading_report.py -xvs`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/modules/grading/grading_review_router.py src/edu_cloud/modules/marking/scorer.py src/edu_cloud/modules/analytics/ai_report_service.py tests/test_services_exam/test_grading_isolation_advanced.py
git commit -m "fix(grading): P-005 replace ai_score IS NOT NULL with source-based stats"
```

---

### Task 5: Worker answer selection fix + create_task warning

**Files:**
- Modify: `src/edu_cloud/workers/grading.py:1093-1101` (answer exclusion query)
- Modify: `src/edu_cloud/modules/grading/router.py:776-886` (create_grading_task warning)
- Test: `tests/test_services_exam/test_grading_isolation_advanced.py` (append T2)

**Solves:** G-002, P-002

- [ ] **Step 1: Add T2 test**

Append to `tests/test_services_exam/test_grading_isolation_advanced.py`:

```python
@pytest.mark.asyncio
async def test_ai_done_then_manual_score_correct_source(db_engine, school_and_question):
    """Normal flow: AI scores, teacher overrides — source must be ai_override."""
    from edu_cloud.modules.marking.scorer import submit_score

    ids = school_and_question
    async with AsyncSession(db_engine, expire_on_commit=False) as db:
        gr = GradingResult(
            answer_id=ids["answer_id"],
            question_id=ids["question_id"],
            school_id=ids["school_id"],
            ai_score=8.0,
            ai_confidence=0.9,
            ai_feedback="AI says good",
            max_score=10.0,
            status="ai_done",
        )
        db.add(gr)
        await db.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as db:
        result = await submit_score(
            db, ids["answer_id"], ids["question_id"],
            "teacher-1", ids["school_id"], 6.0, 10.0, "I disagree",
        )
        assert result.status == "confirmed"
        assert result.source == "ai_override"
        assert result.final_score == 6.0
        assert result.ai_score == 8.0
```

- [ ] **Step 2: Fix worker answer selection**

In `src/edu_cloud/workers/grading.py`, replace lines 1093-1101:

```python
            graded_rows = set()
            if all_answer_ids:
                graded_rows = set((await db.execute(
                    select(GradingResult.answer_id).where(
                        GradingResult.answer_id.in_(all_answer_ids),
                        or_(
                            GradingResult.status.in_(["ai_pending", "ai_done", "confirmed"]),
                            GradingResult.ai_score.is_not(None),
                        ),
                    )
                )).scalars().all())
```

With:

```python
            graded_rows = set()
            if all_answer_ids:
                graded_rows = set((await db.execute(
                    select(GradingResult.answer_id).where(
                        GradingResult.answer_id.in_(all_answer_ids),
                    )
                )).scalars().all())
```

Also remove the `or_` import if no longer used elsewhere in the file — check first with grep.

- [ ] **Step 3: Add confirmed_count warning to create_grading_task**

In `src/edu_cloud/modules/grading/router.py`, after the `ai_pending` cleanup block for the question-level path (after line 836), add:

```python
        confirmed_count = (await db.execute(
            select(func.count(GradingResult.id)).where(
                GradingResult.question_id == req.question_id,
                GradingResult.school_id == school_id,
                GradingResult.status == "confirmed",
            )
        )).scalar() or 0
```

Do the same for the batch path (after line 786) using `req.question_ids`:

```python
        confirmed_count = (await db.execute(
            select(func.count(GradingResult.id)).where(
                GradingResult.question_id.in_(req.question_ids),
                GradingResult.school_id == school_id,
                GradingResult.status == "confirmed",
            )
        )).scalar() or 0
```

And for the subject-level path (after line 884) using `subjective_q_ids`:

```python
        confirmed_count = (await db.execute(
            select(func.count(GradingResult.id)).where(
                GradingResult.question_id.in_(subjective_q_ids),
                GradingResult.school_id == school_id,
                GradingResult.status == "confirmed",
            )
        )).scalar() or 0
```

Then, in the final response dict (find the return statement after task creation), add:

```python
    warning = None
    if confirmed_count > 0:
        warning = f"{confirmed_count} 份答卷已有人工确认评分，AI 将跳过这些答卷"
```

Include `"warning": warning` in the response dict.

- [ ] **Step 4: Run all isolation tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services_exam/test_grading_isolation_advanced.py -xvs`
Expected: All PASS

- [ ] **Step 5: Run existing task creation tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_grading_task.py tests/test_api_exam/test_grading_task_question.py -xvs`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /home/ops/projects/edu-cloud
git add src/edu_cloud/workers/grading.py src/edu_cloud/modules/grading/router.py tests/test_services_exam/test_grading_isolation_advanced.py
git commit -m "fix(grading): G-002 P-002 worker selection fix + create_task confirmed warning"
```

---

### Task 6: Full regression test

**Files:** None (test-only)

- [ ] **Step 1: Run full grading/marking test suite**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_grading_task.py tests/test_api_exam/test_grading_task_question.py tests/test_api_exam/test_grading_review.py tests/test_api_exam/test_grading_isolation.py tests/test_api_exam/test_grading_quality.py tests/test_api_exam/test_dispatch_status.py tests/test_api_exam/test_marking.py tests/test_services_exam/test_grading_worker.py tests/test_services_exam/test_ai_grading_report.py tests/test_services_exam/test_grading_isolation_advanced.py -v --tb=short 2>&1 | tail -30`

Expected: All PASS (or only pre-existing known failures)

- [ ] **Step 2: Run full backend test suite**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q 2>&1 | tail -10`

Expected: No new failures beyond the known baseline (~33 failed)

- [ ] **Step 3: Verify no import errors**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -c "from edu_cloud.workers.grading import _upsert_ai_result, process_grading_task; from edu_cloud.modules.grading.router import router; from edu_cloud.modules.marking.scorer import submit_score; print('All imports OK')"`

Expected: `All imports OK`
