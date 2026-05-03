"""unify_knowledge_fk

Unify knowledge FK references from knowledge_points (UUID) to
concept_graph_nodes (String(64)).

- question_knowledge_points.knowledge_point_id -> concept_id
- student_knowledge_mastery.knowledge_point_id -> concept_id
- student_knp_mastery.knp_id -> concept_id
- Drop questions.knowledge_points JSON column
- Drop knowledge_points table

SQLite requires table recreation for FK/constraint changes, so we use
CREATE TABLE AS ... pattern with explicit schema definition.

Revision ID: ed1f8408241c
Revises: a3f7e1c2d456
Create Date: 2026-05-04 07:45:29.016590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed1f8408241c'
down_revision: Union[str, Sequence[str], None] = 'a3f7e1c2d456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Unify all knowledge FK references to concept_graph_nodes."""
    conn = op.get_bind()

    # ── 1. question_knowledge_points ──────────────────────────────
    # Map knowledge_point_id (UUID FK→knowledge_points) to concept_id
    # (String(64) FK→concept_graph_nodes) via name-based join.
    # Rows that cannot be mapped (no CGN match) are discarded.

    conn.execute(sa.text("""
        CREATE TABLE question_knowledge_points_new (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            question_id VARCHAR(36) NOT NULL REFERENCES questions(id),
            concept_id VARCHAR(64) NOT NULL REFERENCES concept_graph_nodes(id),
            is_primary BOOLEAN NOT NULL,
            UNIQUE (question_id, concept_id)
        )
    """))

    # Data migration: UUID → concept_id via knowledge_points.name = concept_graph_nodes.name
    # Only concept-type nodes are valid targets (not module/study_unit).
    conn.execute(sa.text("""
        INSERT INTO question_knowledge_points_new
            (id, created_at, updated_at, question_id, concept_id, is_primary)
        SELECT qkp.id, qkp.created_at, qkp.updated_at, qkp.question_id, cgn.id, qkp.is_primary
        FROM question_knowledge_points qkp
        JOIN knowledge_points kp ON kp.id = qkp.knowledge_point_id
        JOIN concept_graph_nodes cgn ON cgn.name = kp.name AND cgn.node_type = 'concept'
    """))

    conn.execute(sa.text("DROP TABLE question_knowledge_points"))
    conn.execute(sa.text("ALTER TABLE question_knowledge_points_new RENAME TO question_knowledge_points"))
    conn.execute(sa.text(
        "CREATE INDEX ix_question_knowledge_points_question_id ON question_knowledge_points(question_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX ix_question_knowledge_points_concept_id ON question_knowledge_points(concept_id)"
    ))

    # ── 2. student_knowledge_mastery ──────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE student_knowledge_mastery_new (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            student_id VARCHAR(100) NOT NULL,
            concept_id VARCHAR(64) NOT NULL REFERENCES concept_graph_nodes(id),
            mastery_level FLOAT NOT NULL,
            confidence FLOAT NOT NULL,
            attempt_count INTEGER NOT NULL,
            correct_count INTEGER NOT NULL,
            partial_count INTEGER NOT NULL,
            trend VARCHAR(20) NOT NULL,
            recent_scores JSON,
            last_exam_id VARCHAR(36),
            last_exam_date DATETIME,
            school_id VARCHAR(36) NOT NULL REFERENCES schools(id),
            UNIQUE (student_id, concept_id)
        )
    """))

    conn.execute(sa.text("""
        INSERT INTO student_knowledge_mastery_new
            (id, created_at, updated_at, student_id, concept_id,
             mastery_level, confidence, attempt_count, correct_count, partial_count,
             trend, recent_scores, last_exam_id, last_exam_date, school_id)
        SELECT skm.id, skm.created_at, skm.updated_at, skm.student_id, cgn.id,
               skm.mastery_level, skm.confidence, skm.attempt_count, skm.correct_count,
               skm.partial_count, skm.trend, skm.recent_scores, skm.last_exam_id,
               skm.last_exam_date, skm.school_id
        FROM student_knowledge_mastery skm
        JOIN knowledge_points kp ON kp.id = skm.knowledge_point_id
        JOIN concept_graph_nodes cgn ON cgn.name = kp.name AND cgn.node_type = 'concept'
    """))

    conn.execute(sa.text("DROP TABLE student_knowledge_mastery"))
    conn.execute(sa.text("ALTER TABLE student_knowledge_mastery_new RENAME TO student_knowledge_mastery"))
    conn.execute(sa.text(
        "CREATE INDEX ix_student_knowledge_mastery_concept_id ON student_knowledge_mastery(concept_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX ix_student_knowledge_mastery_school_id ON student_knowledge_mastery(school_id)"
    ))

    # ── 3. student_knp_mastery: rename knp_id → concept_id ────────
    # knp_id stores UUIDs (knowledge_points.id), same mapping needed.
    conn.execute(sa.text("""
        CREATE TABLE student_knp_mastery_new (
            id INTEGER NOT NULL PRIMARY KEY,
            student_id VARCHAR(36) NOT NULL REFERENCES students(id),
            exam_id VARCHAR(36) NOT NULL REFERENCES exams(id),
            concept_id VARCHAR(64) NOT NULL,
            school_id VARCHAR(36) NOT NULL REFERENCES schools(id),
            stu_rate NUMERIC(4, 3),
            class_rate NUMERIC(4, 3),
            grade_rate NUMERIC(4, 3),
            CONSTRAINT uq_student_knp_mastery UNIQUE (student_id, exam_id, concept_id)
        )
    """))

    conn.execute(sa.text("""
        INSERT INTO student_knp_mastery_new
            (id, student_id, exam_id, concept_id, school_id, stu_rate, class_rate, grade_rate)
        SELECT sknp.id, sknp.student_id, sknp.exam_id, cgn.id, sknp.school_id,
               sknp.stu_rate, sknp.class_rate, sknp.grade_rate
        FROM student_knp_mastery sknp
        JOIN knowledge_points kp ON kp.id = sknp.knp_id
        JOIN concept_graph_nodes cgn ON cgn.name = kp.name AND cgn.node_type = 'concept'
    """))

    conn.execute(sa.text("DROP TABLE student_knp_mastery"))
    conn.execute(sa.text("ALTER TABLE student_knp_mastery_new RENAME TO student_knp_mastery"))
    conn.execute(sa.text(
        "CREATE INDEX ix_student_knp_mastery_student_id ON student_knp_mastery(student_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX ix_student_knp_mastery_exam_id ON student_knp_mastery(exam_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX ix_student_knp_mastery_school_id ON student_knp_mastery(school_id)"
    ))

    # ── 4. Drop questions.knowledge_points JSON column ────────────
    # SQLite requires batch_alter_table for column drops.
    with op.batch_alter_table("questions") as batch_op:
        batch_op.drop_column("knowledge_points")

    # ── 5. Drop knowledge_points table (FKs already removed) ─────
    op.drop_table("knowledge_points")


def downgrade() -> None:
    """Irreversible: knowledge_points table dropped, data lost."""
    raise NotImplementedError("Irreversible migration: knowledge_points table dropped")
