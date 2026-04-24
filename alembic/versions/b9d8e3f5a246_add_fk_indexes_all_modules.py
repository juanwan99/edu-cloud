"""add FK indexes across all modules

Revision ID: b9d8e3f5a246
Revises: a8c7d2e4f135
Create Date: 2026-04-24

"""
from alembic import op

revision: str = 'b9d8e3f5a246'
down_revision: str = 'a8c7d2e4f135'
branch_labels = None
depends_on = None

_FK_INDEXES = [
    ("ix_user_roles_user_id", "user_roles", ["user_id"]),
    ("ix_user_roles_school_id", "user_roles", ["school_id"]),
    ("ix_calendar_events_school_id", "calendar_events", ["school_id"]),
    ("ix_calendar_events_created_by", "calendar_events", ["created_by"]),
    ("ix_notification_rules_event_id", "notification_rules", ["event_id"]),
    ("ix_notifications_document_id", "notifications", ["document_id"]),
    ("ix_notifications_school_id", "notifications", ["school_id"]),
    ("ix_documents_created_by", "documents", ["created_by"]),
    ("ix_documents_assigned_to", "documents", ["assigned_to"]),
    ("ix_documents_approved_by", "documents", ["approved_by"]),
    ("ix_documents_school_id", "documents", ["school_id"]),
    ("ix_document_versions_document_id", "document_versions", ["document_id"]),
    ("ix_document_versions_edited_by", "document_versions", ["edited_by"]),
    ("ix_approval_flows_document_id", "approval_flows", ["document_id"]),
    ("ix_approval_steps_flow_id", "approval_steps", ["flow_id"]),
    ("ix_approval_steps_approver_id", "approval_steps", ["approver_id"]),
    ("ix_score_segment_config_created_by", "score_segment_config", ["created_by"]),
    ("ix_time_periods_semester_id", "time_periods", ["semester_id"]),
    ("ix_timetable_slots_semester_id", "timetable_slots", ["semester_id"]),
    ("ix_timetable_slots_period_id", "timetable_slots", ["period_id"]),
    ("ix_timetable_slots_teacher_id", "timetable_slots", ["teacher_id"]),
    ("ix_class_analysis_exam_id", "class_analysis", ["exam_id"]),
    ("ix_class_analysis_subject_id", "class_analysis", ["subject_id"]),
    ("ix_class_analysis_class_id", "class_analysis", ["class_id"]),
    ("ix_class_analysis_school_id", "class_analysis", ["school_id"]),
    ("ix_student_analysis_student_id", "student_analysis", ["student_id"]),
    ("ix_student_analysis_exam_id", "student_analysis", ["exam_id"]),
    ("ix_student_analysis_school_id", "student_analysis", ["school_id"]),
    ("ix_student_knp_mastery_student_id", "student_knp_mastery", ["student_id"]),
    ("ix_student_knp_mastery_exam_id", "student_knp_mastery", ["exam_id"]),
    ("ix_student_knp_mastery_school_id", "student_knp_mastery", ["school_id"]),
    ("ix_bank_questions_source_exam_id", "bank_questions", ["source_exam_id"]),
    ("ix_bank_questions_source_question_id", "bank_questions", ["source_question_id"]),
    ("ix_bank_questions_school_id", "bank_questions", ["school_id"]),
    ("ix_student_error_books_question_id", "student_error_books", ["question_id"]),
    ("ix_student_error_books_bank_question_id", "student_error_books", ["bank_question_id"]),
    ("ix_student_error_books_exam_id", "student_error_books", ["exam_id"]),
    ("ix_student_error_books_school_id", "student_error_books", ["school_id"]),
    ("ix_templates_subject_id", "templates", ["subject_id"]),
    ("ix_templates_school_id", "templates", ["school_id"]),
    ("ix_card_skeletons_school_id", "card_skeletons", ["school_id"]),
    ("ix_exams_school_id", "exams", ["school_id"]),
    ("ix_subjects_exam_id", "subjects", ["exam_id"]),
    ("ix_subjects_school_id", "subjects", ["school_id"]),
    ("ix_questions_subject_id", "questions", ["subject_id"]),
    ("ix_questions_school_id", "questions", ["school_id"]),
    ("ix_exam_results_exam_id", "exam_results", ["exam_id"]),
    ("ix_exam_results_student_id", "exam_results", ["student_id"]),
    ("ix_exam_results_school_id", "exam_results", ["school_id"]),
    ("ix_joint_exams_created_by", "joint_exams", ["created_by"]),
    ("ix_joint_exams_creator_school_id", "joint_exams", ["creator_school_id"]),
    ("ix_joint_exam_participants_joint_exam_id", "joint_exam_participants", ["joint_exam_id"]),
    ("ix_joint_exam_participants_school_id", "joint_exam_participants", ["school_id"]),
    ("ix_joint_exam_student_results_joint_exam_id", "joint_exam_student_results", ["joint_exam_id"]),
    ("ix_joint_exam_student_results_school_id", "joint_exam_student_results", ["school_id"]),
    ("ix_rubrics_school_id", "rubrics", ["school_id"]),
    ("ix_grading_tasks_subject_id", "grading_tasks", ["subject_id"]),
    ("ix_grading_tasks_question_id", "grading_tasks", ["question_id"]),
    ("ix_grading_tasks_created_by", "grading_tasks", ["created_by"]),
    ("ix_grading_tasks_school_id", "grading_tasks", ["school_id"]),
    ("ix_grading_results_question_id", "grading_results", ["question_id"]),
    ("ix_grading_results_ai_task_id", "grading_results", ["ai_task_id"]),
    ("ix_grading_results_reviewer_id", "grading_results", ["reviewer_id"]),
    ("ix_grading_quality_checks_original_result_id", "grading_quality_checks", ["original_result_id"]),
    ("ix_homework_tasks_class_id", "homework_tasks", ["class_id"]),
    ("ix_homework_tasks_exam_id", "homework_tasks", ["exam_id"]),
    ("ix_homework_submissions_graded_by", "homework_submissions", ["graded_by"]),
    ("ix_knowledge_points_parent_id", "knowledge_points", ["parent_id"]),
    ("ix_student_exam_snapshots_exam_id", "student_exam_snapshots", ["exam_id"]),
    ("ix_student_exam_snapshots_school_id", "student_exam_snapshots", ["school_id"]),
    ("ix_student_knowledge_mastery_kp_id", "student_knowledge_mastery", ["knowledge_point_id"]),
    ("ix_student_knowledge_mastery_school_id", "student_knowledge_mastery", ["school_id"]),
    ("ix_student_error_patterns_school_id", "student_error_patterns", ["school_id"]),
    ("ix_scan_tasks_subject_id", "scan_tasks", ["subject_id"]),
    ("ix_scan_tasks_school_id", "scan_tasks", ["school_id"]),
    ("ix_student_answers_exam_id", "student_answers", ["exam_id"]),
    ("ix_student_answers_subject_id", "student_answers", ["subject_id"]),
    ("ix_student_answers_question_id", "student_answers", ["question_id"]),
    ("ix_student_answers_school_id", "student_answers", ["school_id"]),
    ("ix_classes_head_teacher_id", "classes", ["head_teacher_id"]),
    ("ix_classes_school_id", "classes", ["school_id"]),
    ("ix_students_class_id", "students", ["class_id"]),
    ("ix_students_school_id", "students", ["school_id"]),
    ("ix_students_selection_id", "students", ["selection_id"]),
]


def upgrade() -> None:
    for ix_name, table, columns in _FK_INDEXES:
        try:
            op.create_index(ix_name, table, columns)
        except Exception:
            pass


def downgrade() -> None:
    for ix_name, table, _ in reversed(_FK_INDEXES):
        try:
            op.drop_index(ix_name, table_name=table)
        except Exception:
            pass
