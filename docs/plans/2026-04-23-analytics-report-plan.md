---
baseline_command: ".venv/bin/python -m pytest --tb=short -q && cd frontend-nuxt && npx vitest run"
baseline_verified_at: "2026-04-23T22:25:00+08:00"
baseline_count: "backend 2006 passed, 23 skipped; frontend-nuxt 30 passed"
---

# 分析报告前端体系 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基础+AI 进阶双层分析报告体系：后端 8 个新 API 端点 + 前端 5 个 report 页面 + 13 个 analytics 组件 + useAnalytics composable。

**Architecture:** 后端在 `modules/analytics/` 新增 `insights_service.py`（错因聚合+诊断文本）和 `ranking_service.py`（进退步+临界生+箱线图+知识点热力），路由追加到现有 `router.py`。前端在 `frontend-nuxt/` 新增 `useAnalytics` composable + `components/analytics/` 组件库 + `pages/report/` 5 个页面。

**Tech Stack:** FastAPI / SQLAlchemy async / pytest // Nuxt 3 / Element Plus / ECharts 6 / vue-echarts / Vitest

**Design doc:** `docs/plans/2026-04-23-analytics-report-design.md`

**semantic_regression:**
- ORC-001: PowerOptions 树中每个节点必须带 id + name，禁止复合键
- ORC-002: "all" 伪班级的 student_count 等于真实班级之和
- ORC-003: analysisParams.class_id 选"全部班级"时为 null
- ORC-004: RBAC 过滤在 Service 层完成，前端不做二次过滤
- ORC-005: 等级赋分同分学生归入同一等级
- ORC-006: 进阶 Tab 数据必须懒加载，用户不点不请求
- ORC-007: 诊断文本使用模板拼接，不调用 LLM，不产生幻觉
- ORC-008: 错因分类基于 GradingResult.ai_raw_response.details，无 AI 阅卷数据时进阶 Tab 显示空态提示

---

## Batch 1: 后端新增 API + useAnalytics composable（Task 1-4）

### Task 1: insights_service — 错因聚合 + 诊断文本

**Files:**
- Create: `src/edu_cloud/modules/analytics/insights_service.py`
- Create: `tests/test_api/test_analytics_insights.py`

**参考文件（读取但不修改）：**
- `src/edu_cloud/modules/analytics/service.py` — exam_summary/grade_aggregates 模式
- `src/edu_cloud/modules/analytics/__init__.py` — get_effective_scores
- `src/edu_cloud/modules/grading/models.py:41-96` — GradingResult 字段
- `src/edu_cloud/modules/exam/models.py` — Exam/Subject/Question
- `src/edu_cloud/modules/analytics/power_options_service.py` — service 签名模式
- `tests/test_api/test_analytics_power_options.py` — 测试 fixture 模式
- `tests/conftest.py:155-168` — seed_school 返回 (school, secret) 元组

- [ ] **Step 1: 写 insights_service.py — question_insights 函数**

```python
# src/edu_cloud/modules/analytics/insights_service.py
"""AI 阅卷深度分析 — 错因聚合 + 诊断文本生成。"""
import logging
import re
from collections import Counter, defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)

# V1 关键词分类规则
_ERROR_PATTERNS = [
    (re.compile(r"概念|混淆|误写|误用|错误.*名词|名词.*错误"), "概念混淆"),
    (re.compile(r"计算|运算|数值|算错|算术"), "计算错误"),
    (re.compile(r"步骤|不完整|缺少|缺失|遗漏|不全"), "步骤不完整"),
    (re.compile(r"审题|理解|题意|看错"), "审题不清"),
]


def _classify_error(reason: str) -> str:
    for pattern, label in _ERROR_PATTERNS:
        if pattern.search(reason):
            return label
    return "其他"


async def question_insights(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """聚合每题的错因分布 + 难度/区分度。"""
    # 验证考试
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise NotFoundError("Exam not found")

    # 获取科目
    subj_q = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        subj_q = subj_q.where(Subject.id == subject_id)
    if visible_subject_codes is not None:
        subj_q = subj_q.where(Subject.code.in_(visible_subject_codes))
    subjects = list((await db.execute(subj_q)).scalars().all())
    if not subjects:
        return {"questions": []}

    subj_ids = [s.id for s in subjects]

    # 查询所有 GradingResult（有 ai_raw_response 的）
    stmt = (
        select(
            GradingResult.question_id,
            GradingResult.ai_raw_response,
            GradingResult.final_score,
            GradingResult.max_score,
        )
        .join(StudentAnswer, StudentAnswer.id == GradingResult.answer_id)
        .where(
            StudentAnswer.subject_id.in_(subj_ids),
            GradingResult.school_id == school_id,
            GradingResult.final_score.isnot(None),
        )
    )
    if visible_class_ids is not None:
        stmt = stmt.join(Student, Student.id == StudentAnswer.student_id).where(
            Student.class_id.in_(visible_class_ids)
        )

    rows = (await db.execute(stmt)).all()

    # 按题聚合
    q_scores: dict[str, list[float]] = defaultdict(list)
    q_max: dict[str, float] = {}
    q_errors: dict[str, Counter] = defaultdict(Counter)
    q_total: dict[str, int] = defaultdict(int)

    for row in rows:
        qid = row.question_id
        q_scores[qid].append(row.final_score)
        q_max[qid] = row.max_score
        q_total[qid] += 1

        # 解析 ai_raw_response 提取错因
        raw = row.ai_raw_response
        if not raw or not isinstance(raw, dict):
            continue
        details = raw.get("details", [])
        if isinstance(details, str):
            continue
        for detail in details:
            if not isinstance(detail, dict):
                continue
            for blank in detail.get("blanks", []):
                if not isinstance(blank, dict):
                    continue
                if blank.get("correct") is False and blank.get("reason"):
                    cause = _classify_error(blank["reason"])
                    q_errors[qid][cause] += 1

    # 查询题目元数据
    questions_meta = {}
    q_result = await db.execute(
        select(Question.id, Question.name, Question.question_type, Question.max_score)
        .where(Question.subject_id.in_(subj_ids), Question.school_id == school_id)
    )
    for q in q_result.all():
        questions_meta[q.id] = {"name": q.name, "type": q.question_type, "max_score": q.max_score}

    # 构建结果
    result_questions = []
    for qid, scores in q_scores.items():
        meta = questions_meta.get(qid, {"name": qid, "type": "unknown", "max_score": 0})
        max_s = q_max.get(qid, meta["max_score"])
        avg = sum(scores) / len(scores) if scores else 0
        score_rate = round(avg / max_s, 4) if max_s > 0 else 0.0
        total = q_total[qid]

        # 难度和区分度
        difficulty = score_rate
        discrimination = None
        if len(scores) >= 10:
            sorted_s = sorted(scores, reverse=True)
            n27 = max(1, len(sorted_s) * 27 // 100)
            top_avg = sum(sorted_s[:n27]) / n27
            bot_avg = sum(sorted_s[-n27:]) / n27
            discrimination = round((top_avg - bot_avg) / max_s, 4) if max_s > 0 else None

        # 错因分布
        errors = q_errors.get(qid, Counter())
        error_total = sum(errors.values())
        error_causes = []
        for cause, count in errors.most_common():
            error_causes.append({
                "cause": cause,
                "count": count,
                "pct": round(count / total, 4) if total > 0 else 0,
            })

        result_questions.append({
            "question_id": qid,
            "name": meta["name"],
            "question_type": meta["type"],
            "score_rate": score_rate,
            "graded_count": total,
            "error_causes": error_causes,
            "difficulty": difficulty,
            "discrimination": discrimination,
        })

    result_questions.sort(key=lambda x: x["score_rate"])
    return {"questions": result_questions}


async def exam_diagnosis(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """生成考试诊断文本（模板拼接，不调 LLM）。ORC-007。"""
    from edu_cloud.modules.analytics.service import exam_summary, grade_aggregates

    summary = await exam_summary(
        db, exam_id=exam_id, school_id=school_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=[class_id] if class_id else visible_class_ids,
    )
    agg = await grade_aggregates(
        db, exam_id=exam_id, school_id=school_id,
        subject_id=subject_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=visible_class_ids,
    )

    insights = await question_insights(
        db, exam_id=exam_id, school_id=school_id,
        subject_id=subject_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=[class_id] if class_id else visible_class_ids,
    )

    # 构建诊断文本
    parts = []
    grade_avg = agg.get("grade_stats", {}).get("avg_score")
    subjects = summary.get("subjects", [])
    if subjects:
        subj = subjects[0]
        class_avg = subj.get("avg_score")
        if class_avg is not None and grade_avg is not None:
            diff = round(class_avg - grade_avg, 1)
            if diff < 0:
                parts.append(f"本次考试均分 {class_avg}，低于年级均分 {abs(diff)} 分。")
            elif diff > 0:
                parts.append(f"本次考试均分 {class_avg}，高于年级均分 {diff} 分。")
            else:
                parts.append(f"本次考试均分 {class_avg}，与年级持平。")

    # 薄弱题
    weak = [q for q in insights.get("questions", []) if q["score_rate"] < 0.5]
    weak.sort(key=lambda x: x["score_rate"])
    weak_questions = []
    if weak:
        q = weak[0]
        parts.append(f"主要失分集中在第 {q['name']} 题（得分率 {q['score_rate']:.0%}）。")
        weak_questions = [{"name": w["name"], "score_rate": w["score_rate"]} for w in weak[:5]]

    # 高频错因
    all_errors: Counter = Counter()
    for q in insights.get("questions", []):
        for ec in q.get("error_causes", []):
            all_errors[ec["cause"]] += ec["count"]
    error_distribution = {}
    total_errors = sum(all_errors.values())
    if total_errors > 0:
        top_cause = all_errors.most_common(1)[0]
        pct = top_cause[1] / total_errors
        parts.append(f"{pct:.0%} 的错误为{top_cause[0]}。")
        for cause, cnt in all_errors.most_common():
            error_distribution[cause] = round(cnt / total_errors, 4)

    suggestions = []
    if weak:
        suggestions.append(f"建议重点讲解第 {weak[0]['name']} 题相关知识点。")

    return {
        "summary_text": "".join(parts) if parts else "暂无诊断数据。",
        "weak_questions": weak_questions,
        "error_distribution": error_distribution,
        "suggestions": suggestions,
    }
```

- [ ] **Step 2: 写测试 — question_insights 空数据 + 正常数据**

```python
# tests/test_api/test_analytics_insights.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from tests.conftest import *  # noqa


@pytest.fixture
async def school_admin_headers(db, seed_school):
    school, _ = seed_school
    user = User(username="insight_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(
        user_id=user.id, role="principal",
        school_id=school.id, is_primary=True,
    ))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_graded_exam(db, seed_school):
    """Seed a completed exam with AI grading results."""
    school, _ = seed_school
    cls = Class(name="高一(1)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()

    stu1 = Student(name="张三", student_number="S001", class_id=cls.id, school_id=school.id, grade="高一")
    stu2 = Student(name="李四", student_number="S002", class_id=cls.id, school_id=school.id, grade="高一")
    db.add_all([stu1, stu2])
    await db.flush()

    exam = Exam(name="期中考试", status="completed", school_id=school.id)
    db.add(exam)
    await db.flush()

    subj = Subject(name="生物", code="biology", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()

    q1 = Question(name="1", question_type="choice", max_score=3.0, subject_id=subj.id, school_id=school.id)
    q2 = Question(name="15", question_type="essay", max_score=10.0, subject_id=subj.id, school_id=school.id)
    db.add_all([q1, q2])
    await db.flush()

    # 学生 1 答题
    sa1_q1 = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu1.id, question_id=q1.id, score=3.0, school_id=school.id)
    sa1_q2 = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu1.id, question_id=q2.id, school_id=school.id)
    # 学生 2 答题
    sa2_q1 = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu2.id, question_id=q1.id, score=3.0, school_id=school.id)
    sa2_q2 = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu2.id, question_id=q2.id, school_id=school.id)
    db.add_all([sa1_q1, sa1_q2, sa2_q1, sa2_q2])
    await db.flush()

    # GradingResult for essay questions — with AI raw response
    gr1 = GradingResult(
        answer_id=sa1_q2.id, question_id=q2.id, school_id=school.id,
        ai_score=8.0, ai_confidence=0.9, final_score=8.0, max_score=10.0,
        status="confirmed", source="ai",
        ai_raw_response={"details": [{"subQuestion": "(1)", "blanks": [
            {"index": 1, "answer": "光合作用", "score": 4, "fullScore": 5, "correct": False,
             "reason": "概念混淆：将叶绿素误写为叶绿体"},
            {"index": 2, "answer": "正确答案", "score": 4, "fullScore": 5, "correct": True,
             "reason": "满足满分条件"},
        ]}]},
    )
    gr2 = GradingResult(
        answer_id=sa2_q2.id, question_id=q2.id, school_id=school.id,
        ai_score=3.0, ai_confidence=0.85, final_score=3.0, max_score=10.0,
        status="confirmed", source="ai",
        ai_raw_response={"details": [{"subQuestion": "(1)", "blanks": [
            {"index": 1, "answer": "错误答案", "score": 0, "fullScore": 5, "correct": False,
             "reason": "概念混淆：完全混淆光合作用与呼吸作用"},
            {"index": 2, "answer": "步骤不全", "score": 3, "fullScore": 5, "correct": False,
             "reason": "步骤不完整：缺少因果推导链"},
        ]}]},
    )
    # Choice questions — no AI raw response
    gr3 = GradingResult(
        answer_id=sa1_q1.id, question_id=q1.id, school_id=school.id,
        final_score=3.0, max_score=3.0, status="confirmed", source="manual",
    )
    gr4 = GradingResult(
        answer_id=sa2_q1.id, question_id=q1.id, school_id=school.id,
        final_score=3.0, max_score=3.0, status="confirmed", source="manual",
    )
    db.add_all([gr1, gr2, gr3, gr4])
    await db.commit()
    return exam, subj, [q1, q2], cls, [stu1, stu2]


@pytest.mark.asyncio
async def test_question_insights_empty(client, school_admin_headers, seed_school, db):
    school, _ = seed_school
    exam = Exam(name="空考试", status="completed", school_id=school.id)
    db.add(exam)
    await db.commit()

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/question-insights",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["questions"] == []


@pytest.mark.asyncio
async def test_question_insights_with_grading(client, school_admin_headers, seed_school, db):
    exam, subj, questions, _, _ = await _seed_graded_exam(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/question-insights",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["questions"]) == 2

    # 找 essay 题（题号 15）
    q15 = next(q for q in data["questions"] if q["name"] == "15")
    assert q15["graded_count"] == 2
    assert 0 < q15["score_rate"] < 1
    # 错因聚合应该有数据
    assert len(q15["error_causes"]) > 0
    # 概念混淆应该是最多的（2 个学生都有）
    top_cause = q15["error_causes"][0]
    assert top_cause["cause"] == "概念混淆"
    assert top_cause["count"] >= 2


@pytest.mark.asyncio
async def test_question_insights_subject_filter(client, school_admin_headers, seed_school, db):
    exam, subj, _, _, _ = await _seed_graded_exam(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/question-insights",
        params={"subject_id": subj.id},
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["questions"]) == 2


@pytest.mark.asyncio
async def test_diagnosis_text(client, school_admin_headers, seed_school, db):
    """ORC-007: 诊断文本必须是模板拼接，包含具体数据。"""
    exam, subj, _, _, _ = await _seed_graded_exam(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/diagnosis",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["summary_text"], str)
    assert len(data["summary_text"]) > 0
    assert isinstance(data["weak_questions"], list)
    assert isinstance(data["error_distribution"], dict)
    assert isinstance(data["suggestions"], list)


@pytest.mark.asyncio
async def test_diagnosis_empty_exam(client, school_admin_headers, seed_school, db):
    school, _ = seed_school
    exam = Exam(name="空诊断", status="completed", school_id=school.id)
    db.add(exam)
    await db.commit()

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/diagnosis",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    assert "暂无" in resp.json()["summary_text"]
```

- [ ] **Step 3: 在 router.py 末尾追加 question-insights 和 diagnosis 端点**

在 `src/edu_cloud/modules/analytics/router.py` 末尾（第 555 行后）追加：

```python

# --- AI 深度分析 ---

from edu_cloud.modules.analytics.insights_service import (
    question_insights, exam_diagnosis,
)


@router.get("/exam/{exam_id}/question-insights")
async def get_question_insights(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """题目错因聚合 + 难度/区分度。"""
    role = current["current_role"]
    return await question_insights(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/diagnosis")
async def get_exam_diagnosis(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """考试诊断文本（模板拼接，ORC-007 不调 LLM）。"""
    role = current["current_role"]
    return await exam_diagnosis(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        class_id=class_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )
```

- [ ] **Step 4: 运行测试**

Run: `.venv/bin/python -m pytest tests/test_api/test_analytics_insights.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/analytics/insights_service.py \
        src/edu_cloud/modules/analytics/router.py \
        tests/test_api/test_analytics_insights.py
git commit -m "feat(analytics): question-insights + diagnosis 端点（错因聚合+诊断文本）"
```

---

### Task 2: ranking_service — 进退步 + 临界生

**Files:**
- Create: `src/edu_cloud/modules/analytics/ranking_service.py`
- Modify: `src/edu_cloud/modules/analytics/router.py` (追加 2 个端点)
- Create: `tests/test_api/test_analytics_ranking.py`

**参考文件（读取但不修改）：**
- `src/edu_cloud/modules/analytics/service.py` — grade_aggregates 模式
- `src/edu_cloud/modules/analytics/segment_service.py` — get_segment_config
- `src/edu_cloud/modules/scan/models.py` — StudentAnswer
- `src/edu_cloud/modules/student/models.py` — Student/Class

- [ ] **Step 1: 写 ranking_service.py**

```python
# src/edu_cloud/modules/analytics/ranking_service.py
"""学生排名 + 进退步 + 临界生筛选 + 箱线图 + 知识点热力图。"""
import logging
import statistics
from collections import defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def _get_student_scores(
    db: AsyncSession, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_class_ids: list[str] | None = None,
) -> list[dict]:
    """聚合每个学生在某次考试的总分。"""
    subj_q = select(Subject.id).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        subj_q = subj_q.where(Subject.id == subject_id)
    subj_ids = [r[0] for r in (await db.execute(subj_q)).all()]
    if not subj_ids:
        return []

    from edu_cloud.modules.analytics import get_effective_scores
    student_totals: dict[str, float] = defaultdict(float)
    for sid in subj_ids:
        scores = await get_effective_scores(db, sid, school_id, visible_class_ids)
        for s in scores:
            student_totals[s["student_id"]] += s["effective_score"]

    # 获取学生信息
    stu_result = await db.execute(
        select(Student.id, Student.name, Student.class_id)
        .where(Student.school_id == school_id)
    )
    stu_map = {r.id: {"name": r.name, "class_id": r.class_id} for r in stu_result.all()}

    result = []
    for sid, total in student_totals.items():
        info = stu_map.get(sid, {"name": sid, "class_id": None})
        result.append({"student_id": sid, "name": info["name"], "class_id": info["class_id"], "score": total})

    result.sort(key=lambda x: x["score"], reverse=True)
    # 年级排名
    for i, r in enumerate(result):
        r["grade_rank"] = i + 1
        r["grade_size"] = len(result)
    # 班级排名
    by_class: dict[str, list] = defaultdict(list)
    for r in result:
        by_class[r["class_id"]].append(r)
    for cls_students in by_class.values():
        for i, r in enumerate(cls_students):
            r["class_rank"] = i + 1
            r["class_size"] = len(cls_students)

    return result


async def _find_prev_exam(db: AsyncSession, exam_id: str, school_id: str) -> str | None:
    """找到同校上一次考试（按 exam_date 或 created_at 倒序）。"""
    current = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not current:
        return None
    order_col = Exam.exam_date if current.exam_date else Exam.created_at
    prev = (await db.execute(
        select(Exam.id)
        .where(Exam.school_id == school_id, Exam.status == "completed", Exam.id != exam_id)
        .where(order_col < (current.exam_date or current.created_at))
        .order_by(order_col.desc())
        .limit(1)
    )).scalar_one_or_none()
    return prev


async def student_rankings(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """学生排名 + 进退步 delta。"""
    effective_class_ids = [class_id] if class_id else visible_class_ids
    current = await _get_student_scores(db, exam_id, school_id, subject_id, effective_class_ids)
    if not current:
        return {"students": []}

    # 上次考试排名
    prev_exam_id = await _find_prev_exam(db, exam_id, school_id)
    prev_map: dict[str, dict] = {}
    if prev_exam_id:
        prev_scores = await _get_student_scores(db, prev_exam_id, school_id, subject_id, effective_class_ids)
        for p in prev_scores:
            prev_map[p["student_id"]] = p

    students = []
    for s in current:
        prev = prev_map.get(s["student_id"])
        students.append({
            "student_id": s["student_id"],
            "name": s["name"],
            "score": round(s["score"], 2),
            "class_rank": s.get("class_rank"),
            "grade_rank": s["grade_rank"],
            "prev_class_rank": prev["class_rank"] if prev else None,
            "prev_grade_rank": prev["grade_rank"] if prev else None,
            "delta_class": (prev["class_rank"] - s["class_rank"]) if prev and prev.get("class_rank") else None,
            "delta_grade": (prev["grade_rank"] - s["grade_rank"]) if prev else None,
        })

    return {"students": students}


async def critical_students(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    threshold: int = 3,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """临界生筛选：差 N 分及格/优秀。"""
    from edu_cloud.modules.analytics.segment_service import get_segment_config
    from edu_cloud.modules.analytics.service import _get_max_by_subject, _get_subjects

    effective_class_ids = [class_id] if class_id else visible_class_ids
    scores = await _get_student_scores(db, exam_id, school_id, subject_id, effective_class_ids)
    if not scores:
        return {"near_pass": [], "near_excellent": []}

    # 获取满分和分数段
    subjects = await _get_subjects(db, exam_id, school_id, visible_subject_codes, subject_id)
    subj_ids = [s.id for s in subjects]
    max_by_subject = await _get_max_by_subject(db, subj_ids, school_id)
    total_max = sum(max_by_subject.values())

    subject_code = subjects[0].code if len(subjects) == 1 else None
    boundaries, labels = await get_segment_config(db, school_id, subject_code)

    # 及格线和优秀线（按百分比×满分）
    pass_line = total_max * (boundaries[-1] / 100) if boundaries else total_max * 0.6
    excellent_line = total_max * (boundaries[0] / 100) if boundaries else total_max * 0.85

    near_pass = []
    near_excellent = []
    for s in scores:
        gap_pass = pass_line - s["score"]
        gap_excellent = excellent_line - s["score"]
        if 0 < gap_pass <= threshold:
            near_pass.append({
                "student_id": s["student_id"], "name": s["name"],
                "score": round(s["score"], 2), "gap": round(gap_pass, 2),
            })
        if 0 < gap_excellent <= threshold:
            near_excellent.append({
                "student_id": s["student_id"], "name": s["name"],
                "score": round(s["score"], 2), "gap": round(gap_excellent, 2),
            })

    near_pass.sort(key=lambda x: x["gap"])
    near_excellent.sort(key=lambda x: x["gap"])
    return {"near_pass": near_pass, "near_excellent": near_excellent}


async def class_boxplot(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """各班分数箱线图数据。"""
    scores = await _get_student_scores(db, exam_id, school_id, subject_id, visible_class_ids)
    by_class: dict[str, list[float]] = defaultdict(list)
    for s in scores:
        if s["class_id"]:
            by_class[s["class_id"]].append(s["score"])

    # 获取班级名
    class_ids = list(by_class.keys())
    if not class_ids:
        return {"classes": []}
    cls_result = await db.execute(
        select(Class.id, Class.name).where(Class.id.in_(class_ids))
    )
    cls_map = {r.id: r.name for r in cls_result.all()}

    classes = []
    for cid, vals in by_class.items():
        vals.sort()
        n = len(vals)
        classes.append({
            "class_id": cid,
            "name": cls_map.get(cid, cid),
            "count": n,
            "min": round(vals[0], 2),
            "max": round(vals[-1], 2),
            "median": round(statistics.median(vals), 2),
            "p25": round(vals[n * 25 // 100], 2) if n >= 4 else round(vals[0], 2),
            "p75": round(vals[n * 75 // 100], 2) if n >= 4 else round(vals[-1], 2),
        })
    classes.sort(key=lambda x: x["name"])
    return {"classes": classes}
```

- [ ] **Step 2: 写测试**

```python
# tests/test_api/test_analytics_ranking.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from tests.conftest import *  # noqa


@pytest.fixture
async def school_admin_headers(db, seed_school):
    school, _ = seed_school
    user = User(username="ranking_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_two_exams(db, seed_school):
    """Seed two exams for delta calculation."""
    school, _ = seed_school
    cls = Class(name="高一(1)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()

    stu1 = Student(name="张三", student_number="R001", class_id=cls.id, school_id=school.id, grade="高一")
    stu2 = Student(name="李四", student_number="R002", class_id=cls.id, school_id=school.id, grade="高一")
    stu3 = Student(name="王五", student_number="R003", class_id=cls.id, school_id=school.id, grade="高一")
    db.add_all([stu1, stu2, stu3])
    await db.flush()

    from datetime import date
    exam1 = Exam(name="期中", status="completed", exam_date=date(2026, 3, 1), school_id=school.id)
    exam2 = Exam(name="期末", status="completed", exam_date=date(2026, 6, 1), school_id=school.id)
    db.add_all([exam1, exam2])
    await db.flush()

    for exam, scores_map in [
        (exam1, {stu1.id: 90, stu2.id: 80, stu3.id: 70}),
        (exam2, {stu1.id: 75, stu2.id: 85, stu3.id: 95}),
    ]:
        subj = Subject(name="数学", code="math", exam_id=exam.id, school_id=school.id)
        db.add(subj)
        await db.flush()
        q = Question(name="1", question_type="choice", max_score=100, subject_id=subj.id, school_id=school.id)
        db.add(q)
        await db.flush()
        for sid, score in scores_map.items():
            sa = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=sid, question_id=q.id, school_id=school.id)
            db.add(sa)
            await db.flush()
            gr = GradingResult(answer_id=sa.id, question_id=q.id, school_id=school.id,
                               final_score=float(score), max_score=100, status="confirmed", source="manual")
            db.add(gr)
        await db.commit()

    return exam1, exam2, cls, [stu1, stu2, stu3]


@pytest.mark.asyncio
async def test_student_rankings_with_delta(client, school_admin_headers, seed_school, db):
    exam1, exam2, _, students = await _seed_two_exams(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam2.id}/student-rankings",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["students"]) == 3

    # exam2: 王五95>#1, 李四85>#2, 张三75>#3
    # exam1: 张三90>#1, 李四80>#2, 王五70>#3
    ww = next(s for s in data["students"] if s["name"] == "王五")
    assert ww["grade_rank"] == 1
    assert ww["delta_grade"] == 2  # 从 #3 → #1，进步 2 名

    zs = next(s for s in data["students"] if s["name"] == "张三")
    assert zs["grade_rank"] == 3
    assert zs["delta_grade"] == -2  # 从 #1 → #3，退步 2 名


@pytest.mark.asyncio
async def test_critical_students(client, school_admin_headers, seed_school, db):
    school, _ = seed_school
    cls = Class(name="高一(2)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()
    # 3 学生：58 分（差 2 分及格）、61 分（及格）、84 分（差 1 分优秀）
    students_data = [("临界A", "C001", 58), ("及格B", "C002", 61), ("临界C", "C003", 84)]
    stu_objs = []
    for name, num, _ in students_data:
        s = Student(name=name, student_number=num, class_id=cls.id, school_id=school.id, grade="高一")
        db.add(s)
        stu_objs.append(s)
    await db.flush()

    exam = Exam(name="临界测试", status="completed", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(name="语文", code="chinese", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(name="1", question_type="essay", max_score=100, subject_id=subj.id, school_id=school.id)
    db.add(q)
    await db.flush()

    for stu, (_, _, score) in zip(stu_objs, students_data):
        sa = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, school_id=school.id)
        db.add(sa)
        await db.flush()
        gr = GradingResult(answer_id=sa.id, question_id=q.id, school_id=school.id,
                           final_score=float(score), max_score=100, status="confirmed", source="manual")
        db.add(gr)
    await db.commit()

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/critical-students",
        params={"threshold": "3"},
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["near_pass"]) == 1
    assert data["near_pass"][0]["name"] == "临界A"
    assert data["near_pass"][0]["gap"] == 2.0
    assert len(data["near_excellent"]) == 1
    assert data["near_excellent"][0]["name"] == "临界C"


@pytest.mark.asyncio
async def test_class_boxplot(client, school_admin_headers, seed_school, db):
    _, exam2, cls, _ = await _seed_two_exams(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam2.id}/class-boxplot",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["classes"]) >= 1
    c = data["classes"][0]
    assert "min" in c and "max" in c and "median" in c and "p25" in c and "p75" in c
    assert c["min"] <= c["median"] <= c["max"]
```

- [ ] **Step 3: 在 router.py 末尾追加 3 个端点**

在 `src/edu_cloud/modules/analytics/router.py` 末尾追加：

```python

from edu_cloud.modules.analytics.ranking_service import (
    student_rankings, critical_students, class_boxplot,
)


@router.get("/exam/{exam_id}/student-rankings")
async def get_student_rankings(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """学生排名 + 进退步 delta。"""
    role = current["current_role"]
    return await student_rankings(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id, class_id=class_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/critical-students")
async def get_critical_students(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    threshold: int = Query(3),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """临界生筛选。"""
    role = current["current_role"]
    return await critical_students(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id, class_id=class_id,
        threshold=threshold,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/class-boxplot")
async def get_class_boxplot(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """各班分数箱线图数据。"""
    role = current["current_role"]
    return await class_boxplot(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )
```

- [ ] **Step 4: 运行测试**

Run: `.venv/bin/python -m pytest tests/test_api/test_analytics_ranking.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/analytics/ranking_service.py \
        src/edu_cloud/modules/analytics/router.py \
        tests/test_api/test_analytics_ranking.py
git commit -m "feat(analytics): student-rankings + critical-students + class-boxplot 端点"
```

---

### Task 3: class-knowledge + class-error-patterns + student ai-diagnosis

**Files:**
- Modify: `src/edu_cloud/modules/analytics/ranking_service.py` (追加 class_knowledge, class_error_patterns)
- Modify: `src/edu_cloud/modules/analytics/insights_service.py` (追加 student_ai_diagnosis)
- Modify: `src/edu_cloud/modules/analytics/router.py` (追加 3 个端点)
- Create: `tests/test_api/test_analytics_advanced.py`

- [ ] **Step 1: 在 ranking_service.py 末尾追加 class_knowledge 和 class_error_patterns**

```python
# 追加到 src/edu_cloud/modules/analytics/ranking_service.py 末尾

async def class_knowledge(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """班级×知识点 掌握率热力图数据。"""
    from edu_cloud.modules.exam.models import Subject, Question
    from edu_cloud.modules.analytics import get_effective_scores

    subj_q = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        subj_q = subj_q.where(Subject.id == subject_id)
    if visible_subject_codes is not None:
        subj_q = subj_q.where(Subject.code.in_(visible_subject_codes))
    subjects = list((await db.execute(subj_q)).scalars().all())
    if not subjects:
        return {"knowledge_points": [], "classes": []}

    subj_ids = [s.id for s in subjects]

    # 获取题目→知识点映射
    q_result = await db.execute(
        select(Question.id, Question.knowledge_points, Question.max_score)
        .where(Question.subject_id.in_(subj_ids), Question.school_id == school_id)
    )
    q_kps: dict[str, list[str]] = {}
    q_max: dict[str, float] = {}
    all_kps: set[str] = set()
    for q in q_result.all():
        qid = q.id
        q_max[qid] = q.max_score
        kps = []
        if q.knowledge_points and isinstance(q.knowledge_points, dict):
            kps = q.knowledge_points.get("knowledge_ids", [])
        q_kps[qid] = kps
        all_kps.update(kps)

    if not all_kps:
        return {"knowledge_points": [], "classes": []}

    # 聚合每个学生每个知识点的得分率
    student_kp_scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for subj in subjects:
        scores = await get_effective_scores(db, subj.id, school_id, visible_class_ids)
        for s in scores:
            kps = q_kps.get(s["question_id"], [])
            max_s = q_max.get(s["question_id"], 1)
            rate = s["effective_score"] / max_s if max_s > 0 else 0
            for kp in kps:
                student_kp_scores[s["student_id"]][kp].append(rate)

    # 学生→班级映射
    all_sids = list(student_kp_scores.keys())
    stu_result = await db.execute(
        select(Student.id, Student.class_id).where(Student.id.in_(all_sids))
    )
    stu_class = {r.id: r.class_id for r in stu_result.all()}

    # 按班聚合
    class_kp_rates: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for sid, kp_data in student_kp_scores.items():
        cid = stu_class.get(sid)
        if not cid:
            continue
        for kp, rates in kp_data.items():
            avg_rate = sum(rates) / len(rates) if rates else 0
            class_kp_rates[cid][kp].append(avg_rate)

    # 班级名
    class_ids = list(class_kp_rates.keys())
    cls_result = await db.execute(select(Class.id, Class.name).where(Class.id.in_(class_ids)))
    cls_map = {r.id: r.name for r in cls_result.all()}

    kp_list = sorted(all_kps)
    classes = []
    for cid, kp_data in class_kp_rates.items():
        mastery = []
        for kp in kp_list:
            rates = kp_data.get(kp, [])
            avg = round(sum(rates) / len(rates), 4) if rates else 0
            mastery.append({"kp_id": kp, "name": kp, "rate": avg})
        classes.append({"class_id": cid, "name": cls_map.get(cid, cid), "mastery": mastery})
    classes.sort(key=lambda x: x["name"])
    return {"knowledge_points": kp_list, "classes": classes}


async def class_error_patterns(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """班级错误模式对比。"""
    from edu_cloud.modules.analytics.insights_service import question_insights, _classify_error

    insights = await question_insights(
        db, exam_id=exam_id, school_id=school_id,
        subject_id=subject_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=visible_class_ids,
    )

    # 需要按班拆分 — 重新查询带 class_id 信息的 GradingResult
    subj_q = select(Subject.id).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        subj_q = subj_q.where(Subject.id == subject_id)
    if visible_subject_codes is not None:
        subj_q = subj_q.where(Subject.code.in_(visible_subject_codes))
    subj_ids = [r[0] for r in (await db.execute(subj_q)).all()]
    if not subj_ids:
        return {"error_types": [], "classes": []}

    stmt = (
        select(
            Student.class_id,
            GradingResult.ai_raw_response,
        )
        .select_from(GradingResult)
        .join(StudentAnswer, StudentAnswer.id == GradingResult.answer_id)
        .join(Student, Student.id == StudentAnswer.student_id)
        .where(
            StudentAnswer.subject_id.in_(subj_ids),
            GradingResult.school_id == school_id,
            GradingResult.ai_raw_response.isnot(None),
        )
    )
    if visible_class_ids is not None:
        stmt = stmt.where(Student.class_id.in_(visible_class_ids))

    rows = (await db.execute(stmt)).all()

    class_errors: dict[str, Counter] = defaultdict(Counter)
    all_types: set[str] = set()
    for row in rows:
        cid = row.class_id
        raw = row.ai_raw_response
        if not isinstance(raw, dict):
            continue
        for detail in raw.get("details", []):
            if not isinstance(detail, dict):
                continue
            for blank in detail.get("blanks", []):
                if not isinstance(blank, dict):
                    continue
                if blank.get("correct") is False and blank.get("reason"):
                    cause = _classify_error(blank["reason"])
                    class_errors[cid][cause] += 1
                    all_types.add(cause)

    # 班级名
    class_ids = list(class_errors.keys())
    if not class_ids:
        return {"error_types": [], "classes": []}
    cls_result = await db.execute(select(Class.id, Class.name).where(Class.id.in_(class_ids)))
    cls_map = {r.id: r.name for r in cls_result.all()}

    error_types = sorted(all_types)
    classes = []
    for cid, counter in class_errors.items():
        total = sum(counter.values())
        dist = {t: round(counter.get(t, 0) / total, 4) if total > 0 else 0 for t in error_types}
        classes.append({"class_id": cid, "name": cls_map.get(cid, cid), "distribution": dist})
    classes.sort(key=lambda x: x["name"])
    return {"error_types": error_types, "classes": classes}
```

- [ ] **Step 2: 在 insights_service.py 末尾追加 student_ai_diagnosis**

```python
# 追加到 src/edu_cloud/modules/analytics/insights_service.py 末尾

async def student_ai_diagnosis(
    db: AsyncSession, *, student_id: str, school_id: str,
    exam_id: str | None = None,
    subject_id: str | None = None,
) -> dict:
    """学生个体 AI 诊断文本（模板拼接）。ORC-007。"""
    from edu_cloud.modules.profile.models import StudentKnowledgeMastery

    # 查询知识点掌握度
    stmt = select(StudentKnowledgeMastery).where(
        StudentKnowledgeMastery.student_id == student_id,
        StudentKnowledgeMastery.school_id == school_id,
    )
    rows = list((await db.execute(stmt)).scalars().all())

    improving = []
    declining = []
    weak_points = []

    for m in rows:
        item = {
            "kp_name": m.knowledge_point_id,
            "mastery_level": round(m.mastery_level, 4) if m.mastery_level else 0,
            "trend": m.trend or "stable",
            "recent_scores": m.recent_scores or [],
        }
        if m.trend == "improving":
            improving.append(item)
        elif m.trend == "declining":
            declining.append(item)
        if m.mastery_level is not None and m.mastery_level < 0.6:
            weak_points.append(item)

    # 构建诊断文本
    parts = []
    if declining:
        d = declining[0]
        parts.append(f"知识点'{d['kp_name']}'掌握率持续下降（当前 {d['mastery_level']:.0%}），建议重点关注。")
    if improving:
        imp = improving[0]
        parts.append(f"知识点'{imp['kp_name']}'掌握率在上升（当前 {imp['mastery_level']:.0%}），继续保持。")
    if weak_points and not declining:
        w = weak_points[0]
        parts.append(f"知识点'{w['kp_name']}'掌握率较低（{w['mastery_level']:.0%}），建议加强练习。")
    if not parts:
        parts.append("暂无足够数据生成诊断。")

    return {
        "summary": "".join(parts),
        "improving": improving[:5],
        "declining": declining[:5],
        "weak_points": weak_points[:5],
    }
```

- [ ] **Step 3: 在 router.py 末尾追加 3 个端点**

```python
# 追加到 src/edu_cloud/modules/analytics/router.py 末尾

from edu_cloud.modules.analytics.ranking_service import class_knowledge, class_error_patterns
from edu_cloud.modules.analytics.insights_service import student_ai_diagnosis


@router.get("/exam/{exam_id}/class-knowledge")
async def get_class_knowledge(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """班级×知识点 掌握率热力图。"""
    role = current["current_role"]
    return await class_knowledge(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/class-error-patterns")
async def get_class_error_patterns(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """班级错误模式对比。"""
    role = current["current_role"]
    return await class_error_patterns(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/profile/students/{student_id}/ai-diagnosis")
async def get_student_ai_diagnosis(
    student_id: str,
    exam_id: str | None = Query(None),
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """学生个体 AI 诊断（ORC-007 模板拼接）。"""
    role = current["current_role"]
    return await student_ai_diagnosis(
        db, student_id=student_id, school_id=role.school_id,
        exam_id=exam_id, subject_id=subject_id,
    )
```

> **注意**：`/profile/students/{student_id}/ai-diagnosis` 挂在 analytics router 而非 profile router，因为它依赖 analytics 模块的数据。路径以 `/profile/` 开头仅为 API 语义一致。

- [ ] **Step 4: 写测试**

```python
# tests/test_api/test_analytics_advanced.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from tests.conftest import *  # noqa


@pytest.fixture
async def school_admin_headers(db, seed_school):
    school, _ = seed_school
    user = User(username="advanced_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_knowledge_exam(db, seed_school):
    school, _ = seed_school
    cls = Class(name="高一(1)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()
    stu = Student(name="测试生", student_number="K001", class_id=cls.id, school_id=school.id, grade="高一")
    db.add(stu)
    await db.flush()
    exam = Exam(name="知识点测试", status="completed", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(name="生物", code="biology", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(name="1", question_type="essay", max_score=10, subject_id=subj.id, school_id=school.id,
                 knowledge_points={"knowledge_ids": ["光合作用", "细胞分裂"]})
    db.add(q)
    await db.flush()
    sa = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, school_id=school.id)
    db.add(sa)
    await db.flush()
    gr = GradingResult(
        answer_id=sa.id, question_id=q.id, school_id=school.id,
        final_score=6.0, max_score=10.0, status="confirmed", source="ai",
        ai_raw_response={"details": [{"subQuestion": "(1)", "blanks": [
            {"index": 1, "answer": "错误", "score": 0, "fullScore": 5, "correct": False,
             "reason": "概念混淆：细胞分裂与减数分裂混淆"},
        ]}]},
    )
    db.add(gr)
    await db.commit()
    return exam, subj, stu, cls


@pytest.mark.asyncio
async def test_class_knowledge_returns_structure(client, school_admin_headers, seed_school, db):
    exam, subj, _, _ = await _seed_knowledge_exam(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-knowledge",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "knowledge_points" in data
    assert "classes" in data


@pytest.mark.asyncio
async def test_class_error_patterns_returns_structure(client, school_admin_headers, seed_school, db):
    exam, _, _, _ = await _seed_knowledge_exam(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-error-patterns",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "error_types" in data
    assert "classes" in data


@pytest.mark.asyncio
async def test_student_ai_diagnosis(client, school_admin_headers, seed_school, db):
    exam, _, stu, _ = await _seed_knowledge_exam(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/profile/students/{stu.id}/ai-diagnosis",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["summary"], str)
    assert isinstance(data["improving"], list)
    assert isinstance(data["declining"], list)
    assert isinstance(data["weak_points"], list)
```

- [ ] **Step 5: 运行测试**

Run: `.venv/bin/python -m pytest tests/test_api/test_analytics_advanced.py -v`
Expected: 3 tests PASS

- [ ] **Step 6: 全量后端测试**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: baseline + 11 新测试全部 PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/analytics/ranking_service.py \
        src/edu_cloud/modules/analytics/insights_service.py \
        src/edu_cloud/modules/analytics/router.py \
        tests/test_api/test_analytics_advanced.py
git commit -m "feat(analytics): class-knowledge + class-error-patterns + student-ai-diagnosis 端点"
```

---

### Task 4: useAnalytics composable + useApi 追加方法

**Files:**
- Modify: `frontend-nuxt/composables/useApi.ts` (追加 8 个方法)
- Create: `frontend-nuxt/composables/useAnalytics.ts`
- Create: `frontend-nuxt/tests/composables/useAnalytics.test.ts`
- Modify: `frontend-nuxt/tests/setup.ts` (追加 mock)

**参考文件（读取但不修改）：**
- `frontend-nuxt/composables/useApi.ts` — request 函数签名
- `frontend-nuxt/composables/useMenus.ts` — composable 导出模式
- `frontend-nuxt/tests/composables/useApi.test.ts` — vitest mock 模式
- `frontend-nuxt/tests/setup.ts` — globalThis mock 模式

- [ ] **Step 1: 在 useApi.ts 追加 8 个方法**

在 `frontend-nuxt/composables/useApi.ts` 的 `deleteSegmentOverride` 后、`// === Raw ===` 前追加：

```typescript
    // === Advanced Analytics ===
    getQuestionInsights: (examId: string, subjectId?: string) =>
      request('/analytics/exam/' + examId + '/question-insights', { query: { subject_id: subjectId } }),
    getExamDiagnosis: (examId: string, subjectId?: string, classId?: string) =>
      request('/analytics/exam/' + examId + '/diagnosis', { query: { subject_id: subjectId, class_id: classId } }),
    getStudentRankings: (examId: string, subjectId?: string, classId?: string) =>
      request('/analytics/exam/' + examId + '/student-rankings', { query: { subject_id: subjectId, class_id: classId } }),
    getCriticalStudents: (examId: string, subjectId?: string, classId?: string, threshold?: number) =>
      request('/analytics/exam/' + examId + '/critical-students', { query: { subject_id: subjectId, class_id: classId, threshold } }),
    getStudentAiDiagnosis: (studentId: string, examId?: string, subjectId?: string) =>
      request('/analytics/profile/students/' + studentId + '/ai-diagnosis', { query: { exam_id: examId, subject_id: subjectId } }),
    getClassBoxplot: (examId: string, subjectId?: string) =>
      request('/analytics/exam/' + examId + '/class-boxplot', { query: { subject_id: subjectId } }),
    getClassKnowledge: (examId: string, subjectId?: string) =>
      request('/analytics/exam/' + examId + '/class-knowledge', { query: { subject_id: subjectId } }),
    getClassErrorPatterns: (examId: string, subjectId?: string) =>
      request('/analytics/exam/' + examId + '/class-error-patterns', { query: { subject_id: subjectId } }),
```

- [ ] **Step 2: 创建 useAnalytics.ts composable**

```typescript
// frontend-nuxt/composables/useAnalytics.ts
export function useAnalytics() {
  const api = useApi()
  const loading = ref(false)
  const advancedLoading = ref(false)

  const summary = ref<any>(null)
  const distribution = ref<any>(null)
  const gradeAggregates = ref<any>(null)
  const questions = ref<any>(null)

  const questionInsights = ref<any>(null)
  const diagnosis = ref<any>(null)

  async function loadBasicData(params: { exam_id: string; subject_id?: string }) {
    loading.value = true
    clearAdvancedData()
    try {
      const [s, d, g, q] = await Promise.all([
        api.getExamSummary(params.exam_id),
        api.getExamDistribution(params.exam_id, params.subject_id),
        api.getExamGradeAggregates(params.exam_id, params.subject_id),
        params.subject_id ? api.getSubjectQuestions(params.subject_id) : Promise.resolve(null),
      ])
      summary.value = s
      distribution.value = d
      gradeAggregates.value = g
      questions.value = q
    } finally {
      loading.value = false
    }
  }

  async function loadAdvancedData(params: { exam_id: string; subject_id?: string; class_id?: string }) {
    if (questionInsights.value) return
    advancedLoading.value = true
    try {
      const [qi, diag] = await Promise.all([
        api.getQuestionInsights(params.exam_id, params.subject_id),
        api.getExamDiagnosis(params.exam_id, params.subject_id, params.class_id),
      ])
      questionInsights.value = qi
      diagnosis.value = diag
    } finally {
      advancedLoading.value = false
    }
  }

  function clearAdvancedData() {
    questionInsights.value = null
    diagnosis.value = null
  }

  function clearAll() {
    summary.value = null
    distribution.value = null
    gradeAggregates.value = null
    questions.value = null
    clearAdvancedData()
  }

  return {
    loading, advancedLoading,
    summary, distribution, gradeAggregates, questions,
    questionInsights, diagnosis,
    loadBasicData, loadAdvancedData, clearAll,
  }
}
```

- [ ] **Step 3: 更新 tests/setup.ts 追加 useAnalytics mock**

在 `frontend-nuxt/tests/setup.ts` 的 `g.useApi = ...` 块后追加：

```typescript
g.useAnalytics = () => ({
  loading: ref(false),
  advancedLoading: ref(false),
  summary: ref(null),
  distribution: ref(null),
  gradeAggregates: ref(null),
  questions: ref(null),
  questionInsights: ref(null),
  diagnosis: ref(null),
  loadBasicData: vi.fn(),
  loadAdvancedData: vi.fn(),
  clearAll: vi.fn(),
})
```

- [ ] **Step 4: 写 useAnalytics 测试**

```typescript
// frontend-nuxt/tests/composables/useAnalytics.test.ts
describe('useAnalytics', () => {
  it('loadBasicData calls 4 APIs in parallel', async () => {
    const mockSummary = { exam_id: 'e1', total_students: 50, subjects: [] }
    const mockDist = { intervals: [] }
    const mockAgg = { class_rankings: [] }

    const mockFetch = vi.fn()
      .mockResolvedValueOnce(mockSummary)
      .mockResolvedValueOnce(mockDist)
      .mockResolvedValueOnce(mockAgg)
      .mockResolvedValueOnce(null)
    ;(globalThis as any).$fetch = mockFetch

    const analytics = useAnalytics()
    await analytics.loadBasicData({ exam_id: 'e1' })

    expect(analytics.summary.value).toEqual(mockSummary)
    expect(analytics.distribution.value).toEqual(mockDist)
    expect(analytics.loading.value).toBe(false)
  })

  it('loadAdvancedData is lazy — skips if already loaded', async () => {
    const mockFetch = vi.fn().mockResolvedValue({})
    ;(globalThis as any).$fetch = mockFetch

    const analytics = useAnalytics()
    analytics.questionInsights.value = { questions: [] }

    await analytics.loadAdvancedData({ exam_id: 'e1' })
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('clearAll resets all state', () => {
    const analytics = useAnalytics()
    analytics.summary.value = { test: 1 }
    analytics.questionInsights.value = { test: 2 }

    analytics.clearAll()

    expect(analytics.summary.value).toBeNull()
    expect(analytics.questionInsights.value).toBeNull()
  })
})
```

- [ ] **Step 5: 运行前端测试**

Run: `cd frontend-nuxt && npx vitest run`
Expected: baseline 30 + 3 新 = 33 tests PASS

- [ ] **Step 6: Commit**

```bash
git add frontend-nuxt/composables/useApi.ts \
        frontend-nuxt/composables/useAnalytics.ts \
        frontend-nuxt/tests/composables/useAnalytics.test.ts \
        frontend-nuxt/tests/setup.ts
git commit -m "feat(frontend): useAnalytics composable + useApi 追加 8 个进阶分析方法"
```

---

## Batch 2-4 在独立 plan 中（后端 API 就绪后出）

Batch 2: 考后总览 + 参数配置页（PowerFilter + StatCard + ScoreDistChart + ClassRankTable + QuestionAnalysis + AiDiagnosisCard + ErrorCausePanel + config.vue + exam.vue）

Batch 3: 学生追踪 + 班级对比页（StudentRankTable + TrendLine + RadarChart + CriticalStudents + KnowledgeHeatmap + students.vue + contrast.vue）

Batch 4: 等级赋分 + 收尾（level-score.vue + usePowerOptions 搬入 + CLAUDE.md 更新 + 全量测试）

---

## Contract Pack

### invariants
- INV-001: 所有新端点通过 `get_current_user` 认证，数据按 `visible_class_ids` / `visible_subject_codes` 过滤 | verification: existing_test pattern in test_analytics_power_options.py
- INV-002: 诊断文本通过模板拼接生成，不调用 LLM | verification: insights_service.py 中无 LLM import
- INV-003: 错因分类基于 GradingResult.ai_raw_response.details[].blanks[].reason | verification: test_question_insights_with_grading
- INV-004: 进退步 delta = prev_rank - current_rank（正数=进步） | verification: test_student_rankings_with_delta
- INV-005: 进阶 Tab 数据懒加载（loadAdvancedData 检查已有数据跳过） | verification: useAnalytics.test.ts lazy test

### counter_examples
- CE-001: 如果 loadAdvancedData 不检查已有数据就重复请求 → useAnalytics lazy test 会 FAIL | tests_that_still_pass: loadBasicData test | mitigation: questionInsights.value 检查
- CE-002: 如果 _classify_error 缺少 "概念" 关键词匹配 → test_question_insights_with_grading 的 top_cause 断言 FAIL | tests_that_still_pass: empty test | mitigation: _ERROR_PATTERNS 列表覆盖

### risk_modules
- `src/edu_cloud/modules/analytics/insights_service.py` — 新文件，错因聚合核心逻辑
- `src/edu_cloud/modules/analytics/ranking_service.py` — 新文件，进退步+临界生核心逻辑
- `src/edu_cloud/modules/analytics/router.py` — 追加 8 个端点到已有 555 行文件

### test_debt
- 知识点热力图的知识点名称目前用 knowledge_point_id 作 name（Question.knowledge_points 只存 ID 列表，无名称映射）| deadline: Batch 2-4 前端开发时评估是否需要增加知识点名称解析
