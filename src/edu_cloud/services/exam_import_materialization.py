"""考试成绩导入写入链 owner 应用服务（模块外）。

将外部成绩导入的学生匹配、写入链与导入后画像/错题流水线 owner 逻辑——
`match_students`、`commit_import`、`run_post_import_pipeline` 及其私有 upsert 助手——
从 exam_import 模块上移到模块外服务边界，使 exam_import 模块不再直接 import
`exam` / `grading` / `pipeline` / `profile` / `scan` / `student`，一次性拆掉
exam_import 的 6 条直接依赖边（D-03J）。exam_import 仍是成绩导入的对外 owner 命名空间，
`exam_import.service` 经 re-export 保留旧函数/数据类名以维持公共导入与测试 patch 命名空间兼容。

对外契约保持不变：
- `match_students` / `commit_import` / `run_post_import_pipeline` 及 `MatchedStudent` /
  `MatchResult` / `_normalize_class` 经 `exam_import.service` re-export，既有调用点
  （`exam_import.router`）与测试（`exam_import.service.*` 命名空间）行为零变更。
- 学生匹配策略（number → name_class → ambiguous → unmatched）、写入链 upsert 幂等、
  缺考/正常切换、导入后 snapshot/error_book/error_pattern 覆盖语义与历史完全一致。
- 目标模块模型与 pipeline owner 函数采用调用期局部 import：既避免 services 层导入期
  耦合 modules，也与 `services.post_exam_cold_data` / `services.post_exam_adaptive` 同范式。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam_import.parser import (
    ParsedExamData,
    ParsedSubjectData,
    StudentScore,
    QuestionDef,
)

if TYPE_CHECKING:
    # Annotation-only references; the actual write-chain models are imported at
    # call time inside each function so this module-external service never couples
    # to the target modules at import time (D-03J, 与 services.post_exam_cold_data 同范式).
    from edu_cloud.modules.exam.models import Exam, Subject, Question, ExamResult
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.grading.models import GradingResult

logger = logging.getLogger(__name__)

# ── data structures ──────────────────────────────────────────────


@dataclass
class MatchedStudent:
    parsed: StudentScore
    edu_student_id: str
    edu_class_id: str | None = None
    match_method: str = ""  # number / name_class


@dataclass
class MatchResult:
    matched: list[MatchedStudent] = field(default_factory=list)
    unmatched: list[StudentScore] = field(default_factory=list)
    ambiguous: list[tuple[StudentScore, list[str]]] = field(default_factory=list)


# ── helpers ──────────────────────────────────────────────────────

_CLASS_STRIP_RE = re.compile(r"^.*?(\d{3,}).*$")


def _normalize_class(raw: str | None) -> str:
    """Extract numeric class identifier from class name strings.

    Examples:
        "2301班" → "2301"
        "高一年级2301班" → "2301"
        "2301" → "2301"
    """
    if not raw:
        return ""
    raw = raw.strip()
    m = _CLASS_STRIP_RE.match(raw)
    if m:
        return m.group(1)
    return raw


# ── match_students ───────────────────────────────────────────────


async def match_students(
    db: AsyncSession,
    students: list[StudentScore],
    school_id: str,
) -> MatchResult:
    """Match imported students against existing DB records for a school.

    Strategy (per student):
    1. Exact match on student_number == student_key → matched (method="number")
    2. Fallback: (name, normalized_class_name) → if unique → matched (method="name_class")
    3. If multiple candidates with same name+class → ambiguous
    4. Otherwise → unmatched
    """
    from edu_cloud.modules.student.models import Student, Class

    # Pre-load all students for this school with their class info
    stmt = (
        select(Student, Class)
        .outerjoin(Class, Student.class_id == Class.id)
        .where(Student.school_id == school_id)
    )
    rows = (await db.execute(stmt)).all()

    # Build lookup indices
    by_number: dict[str, tuple[Student, Class | None]] = {}
    by_name_class: dict[tuple[str, str], list[tuple[Student, Class | None]]] = {}

    for stu, cls in rows:
        if stu.student_number:
            by_number[stu.student_number] = (stu, cls)
        class_norm = _normalize_class(cls.name) if cls else ""
        key = (stu.name, class_norm)
        by_name_class.setdefault(key, []).append((stu, cls))

    result = MatchResult()

    for parsed in students:
        # Strategy 1: exact number match
        if parsed.student_key and parsed.student_key in by_number:
            stu, cls = by_number[parsed.student_key]
            result.matched.append(MatchedStudent(
                parsed=parsed,
                edu_student_id=stu.id,
                edu_class_id=cls.id if cls else None,
                match_method="number",
            ))
            continue

        # Strategy 2: name + normalized class
        class_norm = _normalize_class(parsed.class_name)
        fallback_key = (parsed.student_name, class_norm)
        candidates = by_name_class.get(fallback_key, [])

        if len(candidates) == 1:
            stu, cls = candidates[0]
            result.matched.append(MatchedStudent(
                parsed=parsed,
                edu_student_id=stu.id,
                edu_class_id=cls.id if cls else None,
                match_method="name_class",
            ))
        elif len(candidates) > 1:
            result.ambiguous.append(
                (parsed, [s.id for s, _ in candidates])
            )
        else:
            result.unmatched.append(parsed)

    return result


# ── commit_import ────────────────────────────────────────────────


async def commit_import(
    db: AsyncSession,
    *,
    parsed: ParsedExamData,
    matched_students: dict[str, MatchedStudent],  # student_key → match
    school_id: str,
    exam_name: str,
    exam_type: str,
    grade_scope: str,
    import_mode: str,  # "questions" or "totals"
    exam_date: str | None = None,
    existing_exam_id: str | None = None,
) -> dict:
    """Write parsed exam data into the full model chain.

    Returns a statistics dict with counts of created/updated records.
    """
    from edu_cloud.modules.exam.models import Exam

    source = f"import_{import_mode}"

    # ── 1. Exam (create or reuse) ────────────────────────────────
    if existing_exam_id:
        stmt = select(Exam).where(Exam.id == existing_exam_id)
        exam = (await db.execute(stmt)).scalar_one_or_none()
        if not exam:
            raise ValueError(f"Exam {existing_exam_id} not found")
    else:
        exam = Exam(
            name=exam_name,
            exam_type=exam_type,
            grade_scope=grade_scope,
            school_id=school_id,
            source=source,
            status="completed",
        )
        db.add(exam)
        await db.flush()

    stats = {
        "exam_id": exam.id,
        "subjects_created": 0,
        "questions_created": 0,
        "questions_updated": 0,
        "answers_created": 0,
        "answers_updated": 0,
        "grading_results_created": 0,
        "grading_results_updated": 0,
        "exam_results_created": 0,
        "exam_results_updated": 0,
        "absent_marked": 0,
    }

    # ── 2-3. Per-subject: upsert Subject + Questions ─────────────
    for subj_data in parsed.subjects:
        subject = await _upsert_subject(db, exam, subj_data, school_id)
        stats["subjects_created"] += 1

        question_map: dict[str, "Question"] = {}
        for qdef in subj_data.questions:
            q, created = await _upsert_question(db, subject, qdef, school_id)
            question_map[qdef.name] = q
            if created:
                stats["questions_created"] += 1
            else:
                stats["questions_updated"] += 1

        # ── 4-6. Per-student: StudentAnswer + GradingResult ──────
        for stu_score in subj_data.students:
            match = matched_students.get(stu_score.student_key)
            if not match:
                continue

            student_id = match.edu_student_id

            for qname, question in question_map.items():
                score_val = stu_score.question_scores.get(qname)

                if stu_score.is_absent:
                    # ── 6. Absent student ────────────────────────
                    answer = await _upsert_student_answer(
                        db,
                        exam_id=exam.id,
                        subject_id=subject.id,
                        student_id=student_id,
                        question_id=question.id,
                        school_id=school_id,
                        score=None,
                        detected_answer=None,
                        is_absent=True,
                    )
                    stats["absent_marked"] += 1
                    # Clear grading result for absent
                    await _upsert_grading_result_absent(
                        db,
                        answer_id=answer.id,
                        question_id=question.id,
                        school_id=school_id,
                        max_score=question.max_score,
                    )
                    stats["grading_results_updated"] += 1
                else:
                    # ── 4-5. Normal student ──────────────────────
                    detected = None
                    if (
                        question.question_type in ("choice", "multi_choice")
                        and score_val is not None
                        and score_val == question.max_score
                        and question.correct_answer
                    ):
                        detected = question.correct_answer

                    answer, ans_created = await _upsert_student_answer(
                        db,
                        exam_id=exam.id,
                        subject_id=subject.id,
                        student_id=student_id,
                        question_id=question.id,
                        school_id=school_id,
                        score=score_val,
                        detected_answer=detected,
                        is_absent=False,
                        return_created=True,
                    )
                    if ans_created:
                        stats["answers_created"] += 1
                    else:
                        stats["answers_updated"] += 1

                    gr, gr_created = await _upsert_grading_result(
                        db,
                        answer_id=answer.id,
                        question_id=question.id,
                        school_id=school_id,
                        final_score=score_val,
                        max_score=question.max_score,
                        source=source,
                    )
                    if gr_created:
                        stats["grading_results_created"] += 1
                    else:
                        stats["grading_results_updated"] += 1

            # ── 7. ExamResult (per student aggregate) ────────────
            er, er_created = await _upsert_exam_result(
                db,
                exam_id=exam.id,
                student_id=student_id,
                school_id=school_id,
                total_score=stu_score.raw_total,
                rank_in_class=stu_score.class_rank,
                rank_in_grade=stu_score.school_rank,
            )
            if er_created:
                stats["exam_results_created"] += 1
            else:
                stats["exam_results_updated"] += 1

    await db.commit()
    return stats


# ── post-import pipeline ────────────────────────────────────────


async def run_post_import_pipeline(
    db: AsyncSession,
    *,
    exam_id: str,
    school_id: str,
    import_mode: str,  # "questions" or "totals"
    parsed: ParsedExamData,
    matched_students: dict[str, MatchedStudent],
) -> dict:
    """Run post-import data generation: snapshot + error_book + score overrides.

    1. Always generate exam snapshots (rank/score_rate from actual answers).
    2. If import_mode != "totals", populate error_books and update error_patterns.
    3. Override snapshot fields with imported official values (converted_score,
       class_rank, school_rank, raw_total) — official data takes priority over
       computed values.

    Returns {"snapshots": N, "error_books": N, "error_patterns": N, "overrides": N}.
    """
    from edu_cloud.modules.pipeline.service import (
        generate_exam_snapshots,
        populate_error_books,
        update_error_patterns,
    )
    from edu_cloud.modules.profile.models import StudentExamSnapshot

    # Step 1: always generate snapshots
    snapshots = await generate_exam_snapshots(db, exam_id=exam_id, school_id=school_id)

    # Step 2: error books only for question-level imports
    errors = 0
    patterns = 0
    if import_mode != "totals":
        errors = await populate_error_books(db, exam_id=exam_id, school_id=school_id)
        patterns = await update_error_patterns(db, exam_id=exam_id, school_id=school_id)

    # Step 3: override snapshot with imported official values
    overrides = 0
    for subj_data in parsed.subjects:
        for stu_score in subj_data.students:
            match = matched_students.get(stu_score.student_key)
            if not match:
                continue
            if stu_score.converted_score is None and stu_score.class_rank is None:
                continue

            # Find the generated snapshot
            snap = (await db.execute(select(StudentExamSnapshot).where(
                StudentExamSnapshot.student_id == match.edu_student_id,
                StudentExamSnapshot.exam_id == exam_id,
                StudentExamSnapshot.subject_code == subj_data.subject_code,
                StudentExamSnapshot.school_id == school_id,
            ))).scalar_one_or_none()

            if not snap:
                continue

            if stu_score.converted_score is not None:
                snap.converted_score = stu_score.converted_score
            if stu_score.grade_level is not None:
                snap.error_summary = snap.error_summary or {}
                snap.error_summary["grade_level"] = stu_score.grade_level
            if stu_score.class_rank is not None:
                snap.class_rank = stu_score.class_rank
            if stu_score.school_rank is not None:
                snap.grade_rank = stu_score.school_rank
            # Sync official raw_total into snapshot
            if stu_score.raw_total is not None and snap.max_score and snap.max_score > 0:
                snap.total_score = stu_score.raw_total
                snap.score_rate = round(stu_score.raw_total / snap.max_score, 4)
            overrides += 1

    await db.commit()

    return {
        "snapshots": snapshots,
        "error_books": errors,
        "error_patterns": patterns,
        "overrides": overrides,
    }


# ── private upsert helpers ───────────────────────────────────────


async def _upsert_subject(
    db: AsyncSession,
    exam: "Exam",
    subj_data: ParsedSubjectData,
    school_id: str,
) -> "Subject":
    """Find or create Subject by (exam_id, code)."""
    from edu_cloud.modules.exam.models import Subject

    stmt = select(Subject).where(
        Subject.exam_id == exam.id,
        Subject.code == subj_data.subject_code,
    )
    subject = (await db.execute(stmt)).scalar_one_or_none()
    if subject:
        subject.name = subj_data.subject_name
        return subject

    subject = Subject(
        exam_id=exam.id,
        name=subj_data.subject_name,
        code=subj_data.subject_code,
        school_id=school_id,
    )
    db.add(subject)
    await db.flush()
    return subject


async def _upsert_question(
    db: AsyncSession,
    subject: "Subject",
    qdef: QuestionDef,
    school_id: str,
) -> tuple["Question", bool]:
    """Find or create Question by (subject_id, name). Returns (question, created)."""
    from edu_cloud.modules.exam.models import Question

    stmt = select(Question).where(
        Question.subject_id == subject.id,
        Question.name == qdef.name,
    )
    question = (await db.execute(stmt)).scalar_one_or_none()
    if question:
        question.max_score = qdef.max_score
        question.question_type = qdef.question_type
        if qdef.correct_answer is not None:
            question.correct_answer = qdef.correct_answer
        return question, False

    question = Question(
        subject_id=subject.id,
        name=qdef.name,
        question_type=qdef.question_type,
        max_score=qdef.max_score,
        correct_answer=qdef.correct_answer,
        school_id=school_id,
    )
    db.add(question)
    await db.flush()
    return question, True


async def _upsert_student_answer(
    db: AsyncSession,
    *,
    exam_id: str,
    subject_id: str,
    student_id: str,
    question_id: str,
    school_id: str,
    score: float | None,
    detected_answer: str | None,
    is_absent: bool,
    return_created: bool = False,
) -> "StudentAnswer | tuple[StudentAnswer, bool]":
    """Find or create StudentAnswer by (exam_id, student_id, question_id)."""
    from edu_cloud.modules.scan.models import StudentAnswer

    stmt = select(StudentAnswer).where(
        StudentAnswer.exam_id == exam_id,
        StudentAnswer.student_id == student_id,
        StudentAnswer.question_id == question_id,
    )
    answer = (await db.execute(stmt)).scalar_one_or_none()
    created = False

    if answer:
        answer.score = score
        answer.detected_answer = detected_answer
        answer.is_absent = is_absent
    else:
        answer = StudentAnswer(
            exam_id=exam_id,
            subject_id=subject_id,
            student_id=student_id,
            question_id=question_id,
            school_id=school_id,
            score=score,
            detected_answer=detected_answer,
            is_absent=is_absent,
        )
        db.add(answer)
        await db.flush()
        created = True

    if return_created:
        return answer, created
    return answer


async def _upsert_grading_result(
    db: AsyncSession,
    *,
    answer_id: str,
    question_id: str,
    school_id: str,
    final_score: float | None,
    max_score: float,
    source: str,
) -> tuple["GradingResult", bool]:
    """Find or create GradingResult by (school_id, answer_id). Returns (result, created)."""
    from edu_cloud.modules.grading.models import GradingResult

    stmt = select(GradingResult).where(
        GradingResult.school_id == school_id,
        GradingResult.answer_id == answer_id,
    )
    gr = (await db.execute(stmt)).scalar_one_or_none()

    if gr:
        gr.final_score = final_score
        gr.max_score = max_score
        gr.status = "confirmed"
        gr.source = source
        return gr, False

    gr = GradingResult(
        answer_id=answer_id,
        question_id=question_id,
        school_id=school_id,
        final_score=final_score,
        max_score=max_score,
        status="confirmed",
        source=source,
    )
    db.add(gr)
    await db.flush()
    return gr, True


async def _upsert_grading_result_absent(
    db: AsyncSession,
    *,
    answer_id: str,
    question_id: str,
    school_id: str,
    max_score: float,
) -> None:
    """Clear GradingResult for absent student."""
    from edu_cloud.modules.grading.models import GradingResult

    stmt = select(GradingResult).where(
        GradingResult.school_id == school_id,
        GradingResult.answer_id == answer_id,
    )
    gr = (await db.execute(stmt)).scalar_one_or_none()

    if gr:
        gr.final_score = None
        gr.max_score = max_score
        gr.status = "confirmed"
        gr.source = None
    # No GradingResult yet — nothing to clear for absent students


async def _upsert_exam_result(
    db: AsyncSession,
    *,
    exam_id: str,
    student_id: str,
    school_id: str,
    total_score: float | None,
    rank_in_class: int | None,
    rank_in_grade: int | None,
) -> tuple["ExamResult", bool]:
    """Find or create ExamResult by (exam_id, student_id). Returns (result, created)."""
    from edu_cloud.modules.exam.models import ExamResult

    stmt = select(ExamResult).where(
        ExamResult.exam_id == exam_id,
        ExamResult.student_id == student_id,
    )
    er = (await db.execute(stmt)).scalar_one_or_none()

    if er:
        if total_score is not None:
            er.total_score = total_score
        er.rank_in_class = rank_in_class
        er.rank_in_grade = rank_in_grade
        return er, False

    er = ExamResult(
        exam_id=exam_id,
        student_id=student_id,
        school_id=school_id,
        total_score=total_score if total_score is not None else 0.0,
        rank_in_class=rank_in_class,
        rank_in_grade=rank_in_grade,
    )
    db.add(er)
    await db.flush()
    return er, True
