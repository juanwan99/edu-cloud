"""Document templates: role-filtered template registry for AI-generated documents."""

TEMPLATES = {
    "class_report": {
        "key": "class_report",
        "name": "班级学情分析报告",
        "sections": [
            {
                "key": "overview",
                "title": "总体概况",
                "prompt": "概括本班本次考试整体表现，包括参加人数、平均分、及格率",
            },
            {
                "key": "subject_analysis",
                "title": "各题分析",
                "prompt": "分析得分率较低的题目，指出共性薄弱点",
            },
            {
                "key": "student_tiers",
                "title": "分层分析",
                "prompt": "将学生分为优秀/良好/待提高三层，各层人数和特点",
            },
            {
                "key": "suggestions",
                "title": "教学建议",
                "prompt": "针对薄弱知识点给出 2-3 条具体教学建议",
            },
        ],
        "required_context": ["exam_id", "class_id"],
        "available_roles": [
            "homeroom_teacher",
            "grade_leader",
            "academic_director",
            "school_admin",
            "principal",
        ],
        "requires_approval": False,
    },
    "subject_analysis": {
        "key": "subject_analysis",
        "name": "学科分析报告",
        "sections": [
            {
                "key": "overview",
                "title": "学科概况",
                "prompt": "本次考试该学科的整体情况",
            },
            {
                "key": "difficulty",
                "title": "难度分析",
                "prompt": "各题得分率和区分度",
            },
            {
                "key": "suggestions",
                "title": "改进建议",
                "prompt": "教学改进方向",
            },
        ],
        "required_context": ["exam_id"],
        "available_roles": ["subject_teacher", "academic_director", "school_admin", "principal"],
        "requires_approval": False,
    },
    "student_comment": {
        "key": "student_comment",
        "name": "学生评语",
        "sections": [
            {
                "key": "academic",
                "title": "学业表现",
                "prompt": "基于成绩数据评价学习情况",
            },
            {
                "key": "growth",
                "title": "成长建议",
                "prompt": "给出个性化的改进建议",
            },
        ],
        "required_context": ["student_id"],
        "available_roles": ["homeroom_teacher"],
        "requires_approval": False,
    },
    "parent_notification": {
        "key": "parent_notification",
        "name": "家长通知",
        "sections": [
            {
                "key": "greeting",
                "title": "称呼",
                "prompt": "尊敬的家长",
            },
            {
                "key": "body",
                "title": "正文",
                "prompt": "根据事件类型生成通知正文",
            },
            {
                "key": "requirements",
                "title": "注意事项",
                "prompt": "需要家长配合的事项",
            },
            {
                "key": "closing",
                "title": "落款",
                "prompt": "学校名+日期",
            },
        ],
        "required_context": ["event_type"],
        "available_roles": [
            "homeroom_teacher",
            "academic_director",
            "school_admin",
            "principal",
        ],
        "requires_approval": True,
        "approval_chain": "class_notification",
    },
    "paper": {
        "key": "paper",
        "name": "教育论文",
        "sections": [
            {"key": "topic", "title": "选题方向", "prompt": "基于教学实践的论文选题"},
        ],
        "required_context": [],
        "available_roles": ["subject_teacher"],
        "requires_approval": False,
        "external_service": "paper_skill",
    },
    "holiday_safety": {
        "key": "holiday_safety",
        "name": "假期安全通知",
        "sections": [
            {"key": "greeting", "title": "称呼", "prompt": "尊敬的家长"},
            {"key": "schedule", "title": "放假安排", "prompt": "根据事件日期生成放假时间安排"},
            {"key": "safety", "title": "安全提醒", "prompt": "假期安全注意事项（交通/防溺水/饮食）"},
            {"key": "closing", "title": "落款", "prompt": "学校名+日期"},
        ],
        "required_context": ["event_title", "event_date"],
        "available_roles": ["homeroom_teacher", "academic_director", "school_admin", "principal"],
        "requires_approval": True,
        "approval_chain": "class_notification",
    },
    "exam_reminder": {
        "key": "exam_reminder",
        "name": "考试通知",
        "sections": [
            {"key": "greeting", "title": "称呼", "prompt": "尊敬的家长"},
            {"key": "exam_info", "title": "考试信息", "prompt": "考试时间、科目、注意事项"},
            {"key": "preparation", "title": "备考建议", "prompt": "家长如何配合备考"},
            {"key": "closing", "title": "落款", "prompt": "学校名+日期"},
        ],
        "required_context": ["event_title", "event_date"],
        "available_roles": ["homeroom_teacher", "academic_director", "school_admin", "principal"],
        "requires_approval": True,
        "approval_chain": "class_notification",
    },
    "meeting_invite": {
        "key": "meeting_invite",
        "name": "家长会邀请",
        "sections": [
            {"key": "greeting", "title": "称呼", "prompt": "尊敬的家长"},
            {"key": "meeting_info", "title": "会议信息", "prompt": "时间、地点、议程"},
            {"key": "closing", "title": "落款", "prompt": "学校名+日期"},
        ],
        "required_context": ["event_title", "event_date"],
        "available_roles": ["homeroom_teacher", "academic_director", "school_admin", "principal"],
        "requires_approval": True,
        "approval_chain": "class_notification",
    },
}


def get_templates_for_role(role: str) -> list[dict]:
    """Return templates available to the given role."""
    result = []
    for tmpl in TEMPLATES.values():
        if role in tmpl["available_roles"]:
            result.append(
                {
                    "key": tmpl["key"],
                    "name": tmpl["name"],
                    "requires_approval": tmpl.get("requires_approval", False),
                    "required_context": tmpl.get("required_context", []),
                }
            )
    return result
