"""学生/班级域工具（4 个）。L1_student 类别。"""
from edu_cloud.ai.registry import tools


@tools.register(
    name="get_class_list",
    description="获取班级列表。可按年级过滤。返回班级 ID、名称、年级。",
    category="L1_student",
    domain="student",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    parameters={
        "type": "object",
        "properties": {
            "grade": {"type": "string", "description": "可选，年级过滤（如'高二'）"},
        },
        "required": [],
    },
)
async def get_class_list(
    grade: str | None = None,
    _school_id: str = "",
    _visible_classes: list[str] | None = None,
    _db=None,
) -> dict:
    from edu_cloud.modules.student.service import list_classes
    classes = await list_classes(_db, school_id=_school_id, visible_class_ids=_visible_classes)
    if grade:
        classes = [c for c in classes if c.grade == grade]
    return {
        "classes": [
            {"id": c.id, "name": c.name, "grade": c.grade}
            for c in classes
        ]
    }


@tools.register(
    name="get_class_roster",
    description="获取某班级的学生名单（姓名会被脱敏为代号）。",
    category="L1_student",
    domain="student",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    parameters={
        "type": "object",
        "properties": {
            "class_id": {"type": "string", "description": "班级 ID"},
        },
        "required": ["class_id"],
    },
)
async def get_class_roster(
    class_id: str,
    _school_id: str = "",
    _visible_classes: list[str] | None = None,
    _db=None,
) -> dict:
    if _visible_classes is not None and class_id not in _visible_classes:
        return {"error": "无权访问该班级", "students": []}
    from edu_cloud.modules.student.service import list_students
    students = await list_students(_db, school_id=_school_id, class_id=class_id, visible_class_ids=_visible_classes)
    return {
        "students": [
            {"id": s.id, "student_name": s.name, "student_number": s.student_number, "class_id": s.class_id}
            for s in students
        ]
    }


@tools.register(
    name="search_students",
    description="按姓名模糊搜索学生。",
    category="L1_student",
    domain="student",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    parameters={
        "type": "object",
        "properties": {
            "query_string": {"type": "string", "description": "搜索关键词"},
        },
        "required": ["query_string"],
    },
)
async def search_students(
    query_string: str,
    _school_id: str = "",
    _visible_classes: list[str] | None = None,
    _db=None,
) -> dict:
    from edu_cloud.modules.student.service import search_students as svc_search
    students = await svc_search(_db, school_id=_school_id, query=query_string, visible_class_ids=_visible_classes)
    return {
        "students": [
            {"id": s.id, "student_name": s.name, "student_number": s.student_number, "class_id": s.class_id}
            for s in students
        ]
    }


@tools.register(
    name="get_student_profile",
    description="获取学生个人信息。",
    category="L1_student",
    domain="student",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    parameters={
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "学生 ID"},
        },
        "required": ["student_id"],
    },
)
async def get_student_profile(
    student_id: str,
    _school_id: str = "",
    _visible_classes: list[str] | None = None,
    _db=None,
) -> dict:
    from edu_cloud.modules.student.service import get_student
    student = await get_student(_db, student_id=student_id, school_id=_school_id)
    if not student:
        return {"error": "学生不存在"}
    if _visible_classes is not None and student.class_id not in _visible_classes:
        return {"error": "无权访问该学生信息"}
    return {
        "id": student.id,
        "student_name": student.name,
        "student_number": student.student_number,
        "class_id": student.class_id,
    }
