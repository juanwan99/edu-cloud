"""Tests for the module-external cold-data owner service (D-03I).

冷数据生成 owner（考试快照 / 知识点掌握度 / 错误模式 / 有效分权威规则 /
`run_full_pipeline`）已从 pipeline 模块上移到 `services.post_exam_cold_data`，使
pipeline 模块不再直接 import exam/scan/grading/knowledge/knowledge_tree/profile/
student —— 一次拆掉 7 条直接依赖边。本测试覆盖三层契约：
- 结构守护：pipeline 模块源码无对上述 7 个冷数据模块的直接 import。
- 兼容守护：`pipeline.service.*` 是对 owner 的纯 re-export（同一函数对象），无重复定义。
- 行为守护：`post_exam_cold_data.run_full_pipeline` 直接产出 5 个冷数据步骤并落库。
"""
import ast
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.profile.models import StudentExamSnapshot

from edu_cloud.services import post_exam_cold_data
from edu_cloud.modules.pipeline import service as pipeline_service


# 冷数据 owner 移出 pipeline 模块后，pipeline 模块不得再直接 import 这些模块。
_COLD_DATA_MODULES = {
    "exam", "scan", "grading", "knowledge", "knowledge_tree", "profile", "student",
}


def test_pipeline_module_has_no_cold_data_module_imports():
    """静态扫描 pipeline 模块源码，确认无对 7 个冷数据模块的直接 import（D-03I 不变量）。"""
    pipeline_dir = Path(__file__).resolve().parents[2] / "src" / "edu_cloud" / "modules" / "pipeline"
    offenders: list[str] = []
    for py in pipeline_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                targets = [node.module or ""]
            elif isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            else:
                continue
            for mod in targets:
                if not mod.startswith("edu_cloud.modules."):
                    continue
                parts = mod.split(".")
                if len(parts) >= 3 and parts[2] in _COLD_DATA_MODULES:
                    offenders.append(f"{py.name}:{node.lineno} -> {parts[2]}")
    assert not offenders, f"pipeline 模块仍直接 import 冷数据模块: {offenders}"


def test_facade_reexports_owner_identity():
    """pipeline.service.* 是对 post_exam_cold_data owner 的纯 re-export（同一对象）。"""
    for name in (
        "_get_effective_score",
        "_get_effective_scores_for_subject",
        "generate_exam_snapshots",
        "update_knowledge_mastery",
        "update_error_patterns",
        "run_full_pipeline",
    ):
        assert getattr(pipeline_service, name) is getattr(post_exam_cold_data, name), (
            f"pipeline.service.{name} 不是 post_exam_cold_data 的 re-export"
        )


@pytest.fixture
async def cold_data_exam(db: AsyncSession):
    """1 class, 2 students, 1 exam, 1 subject (2 KP-linked questions), graded answers."""
    from datetime import datetime, timezone

    school = School(name="Cold Data School", code="CD01")
    db.add(school)
    await db.flush()

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

    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    user = User(username="cd_admin", display_name="Admin")
    user.set_password("p")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))

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

    return {"school_id": school.id, "exam_id": exam.id, "s1_id": s1.id, "s2_id": s2.id}


async def test_cold_data_owner_run_full_pipeline(db: AsyncSession, cold_data_exam):
    """post_exam_cold_data.run_full_pipeline 独立产出 5 个冷数据步骤并落库快照。"""
    results = await post_exam_cold_data.run_full_pipeline(
        db, exam_id=cold_data_exam["exam_id"], school_id=cold_data_exam["school_id"],
    )

    # 5 个 pipeline 自有冷数据步骤；不含跨模块编排的 adaptive / analytics
    assert set(results) == {
        "bank_questions", "error_books", "exam_snapshots",
        "knowledge_mastery", "error_patterns",
    }
    assert results["exam_snapshots"] == 2  # 2 students
    assert "adaptive_mastery" not in results
    assert "exam_analysis" not in results

    snaps = (await db.execute(
        select(StudentExamSnapshot).where(StudentExamSnapshot.exam_id == cold_data_exam["exam_id"])
    )).scalars().all()
    assert len(snaps) == 2
