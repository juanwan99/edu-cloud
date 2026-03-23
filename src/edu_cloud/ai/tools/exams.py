"""考试域工具（3 个）。L1_exam 类别。"""
from edu_cloud.ai.registry import tools


@tools.register(
    name="get_exam_list",
    description="获取考试列表。可按状态过滤（draft/scanning/grading/reviewing/completed）。",
    category="L1_exam",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "可选，考试状态过滤"},
        },
        "required": [],
    },
)
async def get_exam_list(
    status: str | None = None,
    _school_id: str = "",
    _db=None,
) -> dict:
    from edu_cloud.modules.exam.service import list_exams
    exams = await list_exams(_db, school_id=_school_id)
    if status:
        exams = [e for e in exams if e.status == status]
    return {
        "exams": [
            {"id": e.id, "name": e.name, "status": e.status, "card_title": e.card_title}
            for e in exams
        ]
    }


@tools.register(
    name="get_exam_detail",
    description="获取考试详情，包括科目列表。",
    category="L1_exam",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
    },
)
async def get_exam_detail(
    exam_id: str,
    _school_id: str = "",
    _visible_subjects: list[str] | None = None,
    _db=None,
) -> dict:
    from edu_cloud.modules.exam.service import get_exam, list_subjects
    exam = await get_exam(_db, exam_id=exam_id, school_id=_school_id)
    subjects = await list_subjects(_db, exam_id=exam_id, school_id=_school_id)
    if _visible_subjects is not None:
        subjects = [s for s in subjects if s.code in _visible_subjects]
    return {
        "id": exam.id,
        "name": exam.name,
        "status": exam.status,
        "subjects": [
            {"id": s.id, "name": s.name, "code": s.code}
            for s in subjects
        ],
    }


@tools.register(
    name="get_subject_questions",
    description="获取某科目的题目列表。",
    category="L1_exam",
    parameters={
        "type": "object",
        "properties": {
            "subject_id": {"type": "string", "description": "科目 ID"},
        },
        "required": ["subject_id"],
    },
)
async def get_subject_questions(
    subject_id: str,
    _school_id: str = "",
    _visible_subjects: list[str] | None = None,
    _db=None,
) -> dict:
    if _visible_subjects is not None:
        from sqlalchemy import select
        from edu_cloud.modules.exam.models import Subject
        subj_result = await _db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.school_id == _school_id)
        )
        subj = subj_result.scalar_one_or_none()
        if subj and subj.code not in _visible_subjects:
            return {"error": "无权访问该科目"}
    from edu_cloud.modules.exam.service import list_questions
    questions = await list_questions(_db, subject_id=subject_id, school_id=_school_id)
    return {
        "questions": [
            {"id": q.id, "name": q.name, "question_type": q.question_type, "max_score": q.max_score}
            for q in questions
        ]
    }
