"""merge grading+marking into single grading_result table

Revision ID: a7e9c4b8d123
Revises: 46b200fa9704
Create Date: 2026-04-16

合并四张并行分数/分配表为单一权威源：
  - ai_grading_results   → grading_results (status='ai_done' 或 'confirmed')
  - teacher_reviews      → grading_results (并入 AI 记录的 reviewer 字段)
  - marking_scores       → grading_results (source='manual', status='confirmed')
  - marking_assignments  → grading_assignments (question_ids=[question_id])

同步重建 grading_quality_checks.original_result_id FK → grading_results.id。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7e9c4b8d123'
down_revision: Union[str, Sequence[str], None] = '46b200fa9704'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# SQLite v4 UUID generator (used in raw SQL migrations)
_UUID_EXPR = """
  lower(
    hex(randomblob(4)) || '-' ||
    hex(randomblob(2)) || '-' ||
    '4' || substr(hex(randomblob(2)), 2) || '-' ||
    substr('89ab', 1 + (abs(random()) % 4), 1) || substr(hex(randomblob(2)), 2) || '-' ||
    hex(randomblob(6))
  )
""".strip()


def upgrade() -> None:
    # ── 1. Create grading_results ─────────────────────────────────────────
    op.create_table(
        'grading_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('answer_id', sa.String(length=36), nullable=False),
        sa.Column('question_id', sa.String(length=36), nullable=False),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('ai_task_id', sa.String(length=36), nullable=True),
        sa.Column('ai_score', sa.Float(), nullable=True),
        sa.Column('ai_confidence', sa.Float(), nullable=True),
        sa.Column('ai_feedback', sa.Text(), nullable=True),
        sa.Column('ai_raw_response', sa.JSON(), nullable=True),
        sa.Column('final_score', sa.Float(), nullable=True),
        sa.Column('max_score', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('reviewer_id', sa.String(length=36), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_comment', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['answer_id'], ['student_answers.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.ForeignKeyConstraint(['ai_task_id'], ['grading_tasks.id']),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('answer_id'),
    )
    op.create_index('ix_grading_results_school_id', 'grading_results', ['school_id'])
    op.create_index('ix_grading_result_school_status', 'grading_results', ['school_id', 'status'])
    op.create_index('ix_grading_result_question', 'grading_results', ['question_id'])
    op.create_index('ix_grading_result_task', 'grading_results', ['ai_task_id'])

    # ── 2. Migrate ai_grading_results + teacher_reviews → grading_results ──
    op.execute(f"""
        INSERT INTO grading_results (
            id, answer_id, question_id, school_id,
            ai_task_id, ai_score, ai_confidence, ai_feedback, ai_raw_response,
            final_score, max_score,
            status, source,
            reviewer_id, reviewed_at, review_comment,
            version, created_at, updated_at
        )
        SELECT
            {_UUID_EXPR} AS id,
            a.answer_id, a.question_id, a.school_id,
            a.task_id, a.score, a.confidence, a.feedback, a.raw_response,
            CASE
                WHEN a.review_status = 'overridden' AND tr.adjusted_score IS NOT NULL
                    THEN tr.adjusted_score
                ELSE a.score
            END AS final_score,
            a.max_score,
            CASE
                WHEN a.review_status = 'pending' THEN 'ai_done'
                ELSE 'confirmed'
            END AS status,
            CASE
                WHEN a.review_status = 'approved' THEN 'ai'
                WHEN a.review_status = 'overridden' THEN 'ai_override'
                ELSE NULL
            END AS source,
            tr.reviewer_id,
            CASE WHEN tr.reviewer_id IS NOT NULL THEN tr.created_at ELSE NULL END AS reviewed_at,
            tr.comment,
            1 AS version,
            a.created_at, a.updated_at
        FROM ai_grading_results a
        LEFT JOIN teacher_reviews tr ON tr.result_id = a.id
    """)

    # ── 3. Migrate marking_scores → grading_results (answer_id 未被 AI 占用) ─
    op.execute(f"""
        INSERT INTO grading_results (
            id, answer_id, question_id, school_id,
            final_score, max_score, status, source,
            reviewer_id, reviewed_at, review_comment,
            version, created_at, updated_at
        )
        SELECT
            {_UUID_EXPR} AS id,
            ms.answer_id, ms.question_id, ms.school_id,
            ms.score, ms.max_score, 'confirmed', 'manual',
            ms.marker_id, ms.created_at, ms.comment,
            1, ms.created_at, ms.updated_at
        FROM marking_scores ms
        WHERE ms.answer_id NOT IN (SELECT answer_id FROM grading_results)
    """)

    # ── 4. Migrate marking_assignments → grading_assignments ───────────────
    op.execute(f"""
        INSERT INTO grading_assignments (
            id, exam_id, subject_id, question_ids, assigned_to,
            status, graded_count, total_count, started_at, completed_at,
            school_id, is_second_grading, paired_assignment_id,
            created_at, updated_at
        )
        SELECT
            {_UUID_EXPR} AS id,
            ma.exam_id,
            q.subject_id,
            '["' || ma.question_id || '"]' AS question_ids,
            ma.teacher_id,
            ma.status, 0, 0, NULL, NULL,
            ma.school_id, 0, NULL,
            ma.created_at, ma.updated_at
        FROM marking_assignments ma
        JOIN questions q ON q.id = ma.question_id
    """)

    # ── 5. Rebuild grading_quality_checks (FK original_result_id → new table) ──
    op.drop_table('grading_quality_checks')
    op.create_table(
        'grading_quality_checks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('exam_id', sa.String(length=36), nullable=False),
        sa.Column('subject_id', sa.String(length=36), nullable=False),
        sa.Column('question_id', sa.String(length=36), nullable=False),
        sa.Column('check_type', sa.String(length=20), nullable=False),
        sa.Column('original_result_id', sa.String(length=36), nullable=True),
        sa.Column('original_grader_id', sa.String(length=36), nullable=True),
        sa.Column('checker_id', sa.String(length=36), nullable=True),
        sa.Column('original_score', sa.Float(), nullable=False),
        sa.Column('check_score', sa.Float(), nullable=True),
        sa.Column('deviation', sa.Float(), nullable=True),
        sa.Column('severity', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id']),
        sa.ForeignKeyConstraint(['original_result_id'], ['grading_results.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_grading_quality_checks_exam_id', 'grading_quality_checks', ['exam_id'])
    op.create_index('ix_grading_quality_checks_subject_id', 'grading_quality_checks', ['subject_id'])
    op.create_index('ix_grading_quality_checks_school_id', 'grading_quality_checks', ['school_id'])

    # ── 6. Drop old tables (FK 依赖顺序：teacher_reviews 先) ───────────────
    op.drop_table('teacher_reviews')
    op.drop_table('ai_grading_results')
    op.drop_table('marking_scores')
    op.drop_table('marking_assignments')


def downgrade() -> None:
    # ── 1. Recreate old tables ────────────────────────────────────────────
    op.create_table(
        'ai_grading_results',
        sa.Column('task_id', sa.String(length=36), nullable=False),
        sa.Column('answer_id', sa.String(length=36), nullable=False),
        sa.Column('question_id', sa.String(length=36), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('max_score', sa.Float(), nullable=False),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('raw_response', sa.JSON(), nullable=True),
        sa.Column('review_status', sa.String(length=20), nullable=False),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['grading_tasks.id']),
        sa.ForeignKeyConstraint(['answer_id'], ['student_answers.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('answer_id'),
    )
    op.create_table(
        'teacher_reviews',
        sa.Column('result_id', sa.String(length=36), nullable=False),
        sa.Column('reviewer_id', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('adjusted_score', sa.Float(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['result_id'], ['ai_grading_results.id']),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id']),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('result_id'),
    )
    op.create_table(
        'marking_scores',
        sa.Column('answer_id', sa.String(length=36), nullable=False),
        sa.Column('question_id', sa.String(length=36), nullable=False),
        sa.Column('marker_id', sa.String(length=36), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('max_score', sa.Float(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['answer_id'], ['student_answers.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.ForeignKeyConstraint(['marker_id'], ['users.id']),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('answer_id', 'marker_id'),
    )
    op.create_table(
        'marking_assignments',
        sa.Column('exam_id', sa.String(length=36), nullable=False),
        sa.Column('question_id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id']),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_id', 'teacher_id'),
    )

    # ── 2. Rebuild grading_quality_checks FK back to ai_grading_results ────
    op.drop_table('grading_quality_checks')
    op.create_table(
        'grading_quality_checks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('exam_id', sa.String(length=36), nullable=False),
        sa.Column('subject_id', sa.String(length=36), nullable=False),
        sa.Column('question_id', sa.String(length=36), nullable=False),
        sa.Column('check_type', sa.String(length=20), nullable=False),
        sa.Column('original_result_id', sa.String(length=36), nullable=True),
        sa.Column('original_grader_id', sa.String(length=36), nullable=True),
        sa.Column('checker_id', sa.String(length=36), nullable=True),
        sa.Column('original_score', sa.Float(), nullable=False),
        sa.Column('check_score', sa.Float(), nullable=True),
        sa.Column('deviation', sa.Float(), nullable=True),
        sa.Column('severity', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id']),
        sa.ForeignKeyConstraint(['original_result_id'], ['ai_grading_results.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_grading_quality_checks_exam_id', 'grading_quality_checks', ['exam_id'])
    op.create_index('ix_grading_quality_checks_subject_id', 'grading_quality_checks', ['subject_id'])
    op.create_index('ix_grading_quality_checks_school_id', 'grading_quality_checks', ['school_id'])

    # ── 3. Drop grading_results ───────────────────────────────────────────
    op.drop_index('ix_grading_result_task', table_name='grading_results')
    op.drop_index('ix_grading_result_question', table_name='grading_results')
    op.drop_index('ix_grading_result_school_status', table_name='grading_results')
    op.drop_index('ix_grading_results_school_id', table_name='grading_results')
    op.drop_table('grading_results')
