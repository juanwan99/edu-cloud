"""学生/班级域工具（4 个）。L1_student 类别。"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="get_class_list",
    description="获取班级列表。可按年级过滤。返回班级 ID、名称、年级。",
    category="L1_student",
    domain="student",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
    parameters={
        "type": "object",
        "properties": {
            "grade": {"type": "string", "description": "可选，年级过滤（如'高二'）"},
        },
        "required": [],
    },
)
async def get_class_list(input: dict, ctx: ToolContext) -> ToolResult:
    grade = input.get("grade")
    try:
        from edu_cloud.modules.student.service import list_classes
        classes = await list_classes(ctx.db, school_id=ctx.school_id, visible_class_ids=ctx.class_ids)
        if grade:
            classes = [c for c in classes if c.grade == grade]
        return ToolResult(success=True, data={
            "classes": [
                {"id": c.id, "name": c.name, "grade": c.grade}
                for c in classes
            ]
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_class_roster",
    description="获取某班级的学生名单（姓名会被脱敏为代号）。",
    category="L1_student",
    domain="student",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
    parameters={
        "type": "object",
        "properties": {
            "class_id": {"type": "string", "description": "班级 ID"},
        },
        "required": ["class_id"],
    },
)
async def get_class_roster(input: dict, ctx: ToolContext) -> ToolResult:
    class_id = input.get("class_id", "")
    try:
        if ctx.class_ids is not None and class_id not in ctx.class_ids:
            return ToolResult(success=False, error="无权访问该班级", data={"students": []})
        from edu_cloud.modules.student.service import list_students
        students = await list_students(ctx.db, school_id=ctx.school_id, class_id=class_id, visible_class_ids=ctx.class_ids)
        return ToolResult(success=True, data={
            "students": [
                {"id": s.id, "student_name": s.name, "student_number": s.student_number, "class_id": s.class_id}
                for s in students
            ]
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="search_students",
    description="按姓名模糊搜索学生。",
    category="L1_student",
    domain="student",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
    parameters={
        "type": "object",
        "properties": {
            "query_string": {"type": "string", "description": "搜索关键词"},
        },
        "required": ["query_string"],
    },
)
async def search_students(input: dict, ctx: ToolContext) -> ToolResult:
    query_string = input.get("query_string", "")
    try:
        from edu_cloud.modules.student.service import search_students as svc_search
        students = await svc_search(ctx.db, school_id=ctx.school_id, query=query_string, visible_class_ids=ctx.class_ids)
        return ToolResult(success=True, data={
            "students": [
                {"id": s.id, "student_name": s.name, "student_number": s.student_number, "class_id": s.class_id}
                for s in students
            ]
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_student_profile",
    description="获取学生个人信息。",
    category="L1_student",
    domain="student",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
    parameters={
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "学生 ID"},
        },
        "required": ["student_id"],
    },
)
async def get_student_profile(input: dict, ctx: ToolContext) -> ToolResult:
    student_id = input.get("student_id", "")
    try:
        from edu_cloud.modules.student.service import get_student
        student = await get_student(ctx.db, student_id=student_id, school_id=ctx.school_id)
        if not student:
            return ToolResult(success=False, error="学生不存在")
        if ctx.class_ids is not None and student.class_id not in ctx.class_ids:
            return ToolResult(success=False, error="无权访问该学生信息")
        return ToolResult(success=True, data={
            "id": student.id,
            "student_name": student.name,
            "student_number": student.student_number,
            "class_id": student.class_id,
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
