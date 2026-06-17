"""Tests for the module-external post-exam orchestration service (D-03B).

`services.post_exam_pipeline.run_post_exam_pipeline` 编排 pipeline 冷数据步骤 +
analytics 考后预聚合，使 pipeline 模块不再直接依赖 analytics。
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.analytics.models import ClassAnalysis, StudentAnalysis
from edu_cloud.modules.profile.models import StudentExamSnapshot

from edu_cloud.services.post_exam_pipeline import run_post_exam_pipeline
from edu_cloud.modules.pipeline.service import run_full_pipeline


@pytest.fixture
async def exam_data(db: AsyncSession):
    """1 class, 2 students, 1 exam, 1 subject (2 KP-linked questions), graded answers."""
    from datetime import datetime, timezone

    school = School(name="Orchestrate School", code="OS01")
    db.add(school)
    await db.flush()

    user = User(username="orch_admin", display_name="Admin")
    user.set_password("p")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))

    cls = Class(name="高一1班", grade="高一", school_id=school.id)
    db.add(cls)
    await db.flush()

    s1 = Student(name="张三", student_number="001", class_id=cls.id, school_id=school.id)
    s2 = Student(name="李四", student_number="002", class_id=cls.id, school_id=school.id)
    db.add_all([s1, s2])
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    db.add(subj)
    await db.flush()

    q1 = Question(subject_id=subj.id, name="M1", question_type="choice", max_score=60.0, school_id=school.id)
    q2 = Question(subject_id=subj.id, name="M2", question_type="essay", max_score=40.0, school_id=school.id)
    db.add_all([q1, q2])
    await db.flush()

    kp = ConceptGraphNode(
        id="ALG", name="代数", knowledge_level="L1", primary_module="M1",
        synced_at=datetime.now(timezone.utc),
    )
    db.add(kp)
    await db.flush()
    db.add_all([
        QuestionKnowledgePoint(question_id=q1.id, concept_id=kp.id),
        QuestionKnowledgePoint(question_id=q2.id, concept_id=kp.id),
    ])

    task = GradingTask(
        subject_id=subj.id, school_id=school.id,
        status="completed", total=4, completed=4, failed=0, created_by=user.id,
    )
    db.add(task)
    await db.flush()

    scores = {s1.id: [(q1, 50), (q2, 32)], s2.id: [(q1, 30), (q2, 18)]}
    for sid, items in scores.items():
        for q, score in items:
            a = StudentAnswer(
                exam_id=exam.id, subject_id=subj.id, student_id=sid,
                question_id=q.id, image_path=f"/fake/{sid}_{q.id}.png", school_id=school.id,
            )
            db.add(a)
            await db.flush()
            db.add(GradingResult(
                ai_task_id=task.id, answer_id=a.id, question_id=q.id,
                school_id=school.id, ai_score=float(score), final_score=float(score),
                max_score=q.max_score, ai_feedback="ok", ai_confidence=0.95, status="confirmed",
            ))
    await db.commit()

    return {"school_id": school.id, "exam_id": exam.id, "subj_id": subj.id,
            "cls_id": cls.id, "s1_id": s1.id, "s2_id": s2.id}


async def test_orchestrator_runs_cold_data_and_analytics(db: AsyncSession, exam_data):
    """run_post_exam_pipeline 同时产出 pipeline 冷数据 + analytics 考后分析。"""
    results = await run_post_exam_pipeline(
        db, exam_id=exam_data["exam_id"], school_id=exam_data["school_id"],
    )

    # 冷数据步骤（pipeline 自有）
    assert "bank_questions" in results
    assert results["exam_snapshots"] == 2  # 2 students
    assert "knowledge_mastery" in results
    assert "error_patterns" in results
    assert "adaptive_mastery" in results

    # analytics 考后分析（编排服务追加，pipeline 不再直接依赖）
    assert "exam_analysis" in results
    assert results["exam_analysis"]["class_analysis"] == 1  # 1 class × 1 subject
    assert results["exam_analysis"]["student_analysis"] == 2  # 2 students

    # 落库验证：snapshot（pipeline）+ 分析表（analytics）都写入
    snaps = (await db.execute(
        select(StudentExamSnapshot).where(StudentExamSnapshot.exam_id == exam_data["exam_id"])
    )).scalars().all()
    assert len(snaps) == 2

    ca = (await db.execute(
        select(ClassAnalysis).where(ClassAnalysis.exam_id == exam_data["exam_id"])
    )).scalars().all()
    assert len(ca) == 1

    sa = (await db.execute(
        select(StudentAnalysis).where(StudentAnalysis.exam_id == exam_data["exam_id"])
    )).scalars().all()
    assert len(sa) == 2


async def test_run_full_pipeline_excludes_exam_analysis(db: AsyncSession, exam_data):
    """解耦后契约：pipeline 的 run_full_pipeline 只产冷数据，不含 exam_analysis。"""
    results = await run_full_pipeline(
        db, exam_id=exam_data["exam_id"], school_id=exam_data["school_id"],
    )
    assert "exam_snapshots" in results
    assert "exam_analysis" not in results

    # analytics 预聚合表未被 run_full_pipeline 触碰
    ca = (await db.execute(
        select(ClassAnalysis).where(ClassAnalysis.exam_id == exam_data["exam_id"])
    )).scalars().all()
    assert ca == []
