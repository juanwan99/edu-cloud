"""考试发布前置检查服务测试 + exam→grading 解耦静态守护（D-03D）。

D-03D：exam 不再直接 import grading，发布前置检查经模块外服务
`edu_cloud.services.exam_publish_checks`。下面区分三层：
- 服务层契约：`ensure_grading_complete` / `ensure_no_high_severity_issues` 行为
  与历史 publish_service 内联检查一致（异常类型 StateError + 错误信息语义）。
- wiring：`ExamPublishService.publish` 委托模块外服务执行前置检查。
- 结构守护：exam 模块源码不得出现直接 grading import（D-03D 不变量）。
"""
import ast
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from edu_cloud.modules.exam.models import Exam
from edu_cloud.modules.grading.models import GradingAssignment, GradingQualityCheck
from edu_cloud.services.exam_publish_checks import (
    ensure_grading_complete,
    ensure_no_high_severity_issues,
)
from edu_cloud.services.exceptions import StateError


# ---- 服务层契约：grading 前置检查 ----

@pytest.mark.asyncio
async def test_ensure_grading_complete_passes_when_no_assignments(db):
    """无阅卷任务时通过（不抛异常）。"""
    await ensure_grading_complete(db, exam_id="exam-none")


@pytest.mark.asyncio
async def test_ensure_grading_complete_passes_when_all_completed(db):
    exam = Exam(name="T", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()
    db.add(GradingAssignment(
        exam_id=exam.id, subject_id="s1", question_ids=["q1"],
        assigned_to="t1", total_count=10, graded_count=10,
        status="completed", school_id="s1",
    ))
    await db.flush()
    await ensure_grading_complete(db, exam_id=exam.id)


@pytest.mark.asyncio
async def test_ensure_grading_complete_raises_on_incomplete(db):
    """未完成阅卷任务 → StateError，信息语义与历史内联检查一致。"""
    exam = Exam(name="T", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()
    db.add(GradingAssignment(
        exam_id=exam.id, subject_id="s1", question_ids=["q1"],
        assigned_to="t1", total_count=10, graded_count=5,
        status="in_progress", school_id="s1",
    ))
    await db.flush()
    with pytest.raises(StateError, match="grading assignments not completed"):
        await ensure_grading_complete(db, exam_id=exam.id)


@pytest.mark.asyncio
async def test_ensure_no_high_severity_issues_passes_when_clean(db):
    """无 high severity 质量问题时通过（不抛异常）。"""
    await ensure_no_high_severity_issues(db, exam_id="exam-clean")


@pytest.mark.asyncio
async def test_ensure_no_high_severity_issues_raises_on_high(db):
    """存在 high severity 质量问题 → StateError，信息语义与历史内联检查一致。"""
    exam = Exam(name="T", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()
    db.add(GradingQualityCheck(
        exam_id=exam.id, subject_id="s1", question_id="q1",
        check_type="sampling", original_score=8.0, check_score=2.0,
        deviation=6.0, severity="high", status="reviewed", school_id="s1",
    ))
    await db.flush()
    with pytest.raises(StateError, match="high-severity quality issues"):
        await ensure_no_high_severity_issues(db, exam_id=exam.id)


# ---- wiring：publish 委托模块外服务前置检查 ----

@pytest.mark.asyncio
async def test_publish_delegates_precondition_checks(db):
    """publish 调用 exam_publish_checks 的两个前置检查函数，并传 exam_id。"""
    exam = Exam(name="T", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()
    with patch(
        "edu_cloud.services.exam_publish_checks.ensure_grading_complete",
        new_callable=AsyncMock,
    ) as mock_gc, patch(
        "edu_cloud.services.exam_publish_checks.ensure_no_high_severity_issues",
        new_callable=AsyncMock,
    ) as mock_hs:
        from edu_cloud.modules.exam.publish_service import ExamPublishService
        await ExamPublishService.publish(db, exam_id=exam.id, school_id="s1")
        mock_gc.assert_called_once_with(db, exam_id=exam.id)
        mock_hs.assert_called_once_with(db, exam_id=exam.id)


# ---- 结构守护：exam 模块不得直接 import grading（D-03D 不变量） ----

def test_exam_module_has_no_direct_grading_import():
    """静态扫描 exam 模块源码，确认无 `edu_cloud.modules.grading` 直接 import。"""
    exam_dir = Path(__file__).resolve().parents[2] / "src" / "edu_cloud" / "modules" / "exam"
    offenders = []
    for py in exam_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod == "edu_cloud.modules.grading" or mod.startswith(
                    "edu_cloud.modules.grading."
                ):
                    offenders.append(f"{py.name}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "edu_cloud.modules.grading" or alias.name.startswith(
                        "edu_cloud.modules.grading."
                    ):
                        offenders.append(f"{py.name}:{node.lineno}")
    assert not offenders, f"exam 模块仍直接 import grading: {offenders}"
