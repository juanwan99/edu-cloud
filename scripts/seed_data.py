"""
P0 种子数据：创建管理员 + 教师 + 学校 + 班级 + 学生 + 考试 + 成绩
用于演示：班主任登录 -> 选考试 -> 看成绩分布
"""
import asyncio
import random
import sys
import os

# Allow running from project root or scripts/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from edu_cloud.config import get_settings
from edu_cloud.models.base import Base
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import RegisteredSchool
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.student import Student
from edu_cloud.models.exam import Exam, ExamResult

# Register all models so Base.metadata includes all tables
import edu_cloud.models.platform_user  # noqa: F401
import edu_cloud.models.joint_exam  # noqa: F401


async def seed():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        # 1. School
        school = RegisteredSchool(
            name="实验中学",
            code="SYZX",
            district="城区",
            api_key_hash="placeholder",
        )
        db.add(school)
        await db.flush()

        # 2. Admin
        admin = User(username="admin", display_name="平台管理员")
        admin.set_password("123456")
        db.add(admin)
        await db.flush()
        db.add(UserRole(user_id=admin.id, role="platform_admin", is_primary=True))

        # 3. Teacher (homeroom_teacher for class cls-7-2)
        teacher = User(username="zhanglaoshi", display_name="张老师")
        teacher.set_password("123456")
        db.add(teacher)
        await db.flush()
        db.add(UserRole(
            user_id=teacher.id,
            role="homeroom_teacher",
            school_id=school.id,
            class_ids=["cls-7-2"],
            is_primary=True,
        ))

        # 4. Class
        cls = ClassGroup(
            id="cls-7-2",
            name="七年级2班",
            grade="七年级",
            grade_number=7,
            school_id=school.id,
        )
        db.add(cls)

        # 5. Students (45)
        students = []
        for i in range(1, 46):
            s = Student(
                name=f"学生{i:02d}",
                student_number=f"S{i:03d}",
                school_id=school.id,
                class_id="cls-7-2",
                grade="七年级",
            )
            db.add(s)
            students.append(s)
        await db.flush()

        # 6. Exam
        exam = Exam(
            name="2025-2026 第二学期期中考试",
            subject_code="SX",
            subject_name="数学",
            max_score=150,
            school_id=school.id,
            semester="2025-2026-2",
        )
        db.add(exam)
        await db.flush()

        # 7. Results (normal distribution, clamped to [0, 150])
        random.seed(42)
        for s in students:
            score = round(random.gauss(105, 20), 1)
            score = max(0.0, min(150.0, score))
            db.add(ExamResult(
                exam_id=exam.id,
                student_id=s.id,
                school_id=school.id,
                total_score=score,
            ))

        await db.commit()
        print(
            "Seed data created: 1 school, 2 users (admin + zhanglaoshi), "
            "1 class, 45 students, 1 exam, 45 results"
        )
        print("Login: admin/123456 (platform_admin) or zhanglaoshi/123456 (homeroom_teacher)")


if __name__ == "__main__":
    asyncio.run(seed())
