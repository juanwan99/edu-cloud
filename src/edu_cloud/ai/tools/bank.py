"""题库 + 错题本工具（2 个）。L5_bank 类别。"""
from edu_cloud.ai.registry import tools


@tools.register(
    name="get_student_error_book",
    description="获取某学生的错题本。返回该学生做错的题目列表，含 AI 反馈和掌握状态。",
    category="L5_bank",
    domain="bank",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    parameters={
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "学生 ID"},
            "mastery_status": {"type": "string", "description": "过滤掌握状态：unmastered/practicing/mastered"},
        },
        "required": ["student_id"],
    },
)
async def get_student_error_book(student_id: str, mastery_status: str | None = None, _school_id="", _db=None, **_):
    from edu_cloud.modules.bank.service import get_student_error_book as svc_error_book, get_error_book_stats
    errors = await svc_error_book(
        _db, student_id=student_id, school_id=_school_id, mastery_status=mastery_status,
    )
    stats = await get_error_book_stats(_db, student_id=student_id, school_id=_school_id)
    return {
        "stats": stats,
        "errors": [
            {
                "question_id": e.question_id, "exam_id": e.exam_id,
                "score": e.student_score, "max_score": e.max_score,
                "ai_feedback": e.ai_feedback, "error_type": e.error_type,
                "mastery_status": e.mastery_status, "retry_count": e.retry_count,
            }
            for e in errors[:20]
        ],
    }


@tools.register(
    name="get_question_stats",
    description="获取题库中某道题的统计属性：难度、区分度、常见错误分布。",
    category="L5_bank",
    domain="bank",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    parameters={
        "type": "object",
        "properties": {
            "bank_question_id": {"type": "string", "description": "题库题目 ID"},
        },
        "required": ["bank_question_id"],
    },
)
async def get_question_stats(bank_question_id: str, _school_id="", _db=None, **_):
    from edu_cloud.modules.bank.service import get_bank_question
    bq = await get_bank_question(_db, bank_question_id=bank_question_id, school_id=_school_id)
    return {
        "id": bq.id, "question_type": bq.question_type, "max_score": bq.max_score,
        "difficulty": bq.difficulty, "discrimination": bq.discrimination,
        "sample_count": bq.sample_count, "common_errors": bq.common_errors,
    }
