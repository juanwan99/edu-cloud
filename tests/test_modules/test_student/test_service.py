"""Student 服务测试 — TG-01 修复。"""
import pytest
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.student.service import list_classes, list_students, search_students, get_student
from edu_cloud.models.school import School
from edu_cloud.models.user import User


@pytest.mark.asyncio
async def test_list_classes_school_filter(db):
    """list_classes 只返回本校班级。"""
    s1 = School(name="A", code="SC_A", district="X")
    s2 = School(name="B", code="SC_B", district="X")
    db.add_all([s1, s2])
    await db.flush()
    db.add(Class(name="1班", grade="七年级", school_id=s1.id))
    db.add(Class(name="2班", grade="七年级", school_id=s2.id))
    await db.commit()
    classes = await list_classes(db, school_id=s1.id)
    assert len(classes) == 1
    assert classes[0].name == "1班"


@pytest.mark.asyncio
async def test_list_classes_visible_filter(db):
    """visible_class_ids 过滤。"""
    school = School(name="VF", code="VF01", district="X")
    db.add(school)
    await db.flush()
    c1 = Class(name="1班", grade="七年级", school_id=school.id)
    c2 = Class(name="2班", grade="七年级", school_id=school.id)
    db.add_all([c1, c2])
    await db.flush()
    classes = await list_classes(db, school_id=school.id, visible_class_ids=[c1.id])
    assert len(classes) == 1


@pytest.mark.asyncio
async def test_list_classes_empty(db):
    """无班级时返回空列表。"""
    school = School(name="EC", code="EC01", district="X")
    db.add(school)
    await db.flush()
    classes = await list_classes(db, school_id=school.id)
    assert classes == []


@pytest.mark.asyncio
async def test_list_students_class_filter(db):
    """按班级过滤学生。"""
    school = School(name="SF", code="SF01", district="X")
    db.add(school)
    await db.flush()
    c1 = Class(name="1班", grade="七年级", school_id=school.id)
    c2 = Class(name="2班", grade="七年级", school_id=school.id)
    db.add_all([c1, c2])
    await db.flush()
    db.add(Student(name="张三", student_number="S001", class_id=c1.id, school_id=school.id))
    db.add(Student(name="李四", student_number="S002", class_id=c2.id, school_id=school.id))
    await db.commit()
    students = await list_students(db, school_id=school.id, class_id=c1.id)
    assert len(students) == 1
    assert students[0].name == "张三"


@pytest.mark.asyncio
async def test_search_students(db):
    """按姓名搜索。"""
    school = School(name="SS", code="SS01", district="X")
    db.add(school)
    await db.flush()
    cls = Class(name="1班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.flush()
    db.add(Student(name="张三", student_number="S001", class_id=cls.id, school_id=school.id))
    db.add(Student(name="李四", student_number="S002", class_id=cls.id, school_id=school.id))
    await db.commit()
    results = await search_students(db, school_id=school.id, query="张")
    assert len(results) == 1
    assert results[0].name == "张三"


@pytest.mark.asyncio
async def test_get_student_wrong_school(db):
    """跨校查找学生返回 None。"""
    s1 = School(name="GS1", code="GS_1", district="X")
    s2 = School(name="GS2", code="GS_2", district="X")
    db.add_all([s1, s2])
    await db.flush()
    cls = Class(name="1班", grade="七年级", school_id=s1.id)
    db.add(cls)
    await db.flush()
    stu = Student(name="王五", student_number="S003", class_id=cls.id, school_id=s1.id)
    db.add(stu)
    await db.commit()
    await db.refresh(stu)
    result = await get_student(db, student_id=stu.id, school_id=s2.id)
    assert result is None
