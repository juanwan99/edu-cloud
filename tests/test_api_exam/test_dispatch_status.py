"""阅卷调度状态聚合 API 测试。"""
import pytest
from sqlalchemy import insert


@pytest.fixture
async def dispatch_fixtures(db):
    """Seed school + exam + subject + questions for dispatch status tests."""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.exam.models import Exam, Subject, Question

    school = School(name="调度测试校", code="DISP01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    user = User(username="dispatch_admin", display_name="调度管理员")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id)
    db.add(exam)
    await db.flush()

    subject = Subject(name="数学", exam_id=exam.id, school_id=school.id, code="math")
    db.add(subject)
    await db.flush()

    # 主观题
    subj_q = Question(
        subject_id=subject.id, question_type="essay",
        name="解答题1", max_score=10.0, school_id=school.id,
    )
    db.add(subj_q)
    await db.flush()

    # 选择题
    obj_q = Question(
        subject_id=subject.id, question_type="choice",
        name="选择题1", max_score=3.0, correct_answer="A", school_id=school.id,
    )
    db.add(obj_q)
    await db.flush()

    await db.commit()

    return {
        "school_id": school.id,
        "user_id": user.id,
        "exam_id": exam.id,
        "subject_id": subject.id,
        "subjective_question_id": subj_q.id,
        "objective_question_id": obj_q.id,
    }


@pytest.fixture
async def dispatch_headers(client, dispatch_fixtures):
    """JWT headers for dispatch test user."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "dispatch_admin", "password": "123456"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestDispatchStatus:
    async def test_idle_stage(self, client, dispatch_fixtures, dispatch_headers):
        """无 StudentAnswer 时 stage=idle。"""
        exam_id = dispatch_fixtures["exam_id"]
        resp = await client.get(
            f"/api/v1/grading/dispatch/status?exam_id={exam_id}",
            headers=dispatch_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for s in data:
            assert s["stage"] == "idle"
            assert "subject_name" in s
            assert "subject_id" in s

    async def test_ready_stage_after_answers(self, client, db_engine, dispatch_fixtures, dispatch_headers):
        """有主观题 StudentAnswer + Rubric 时 stage=ready。"""
        exam_id = dispatch_fixtures["exam_id"]
        subject_id = dispatch_fixtures["subject_id"]
        school_id = dispatch_fixtures["school_id"]
        subj_q_id = dispatch_fixtures["subjective_question_id"]

        from edu_cloud.modules.scan.models import StudentAnswer
        from edu_cloud.modules.grading.models import Rubric

        async with db_engine.begin() as conn:
            await conn.execute(insert(StudentAnswer).values(
                id="sa-test-1",
                exam_id=exam_id,
                subject_id=subject_id,
                student_id="stu1",
                question_id=subj_q_id,
                image_path="/tmp/test.png",
                school_id=school_id,
            ))
            await conn.execute(insert(Rubric).values(
                id="rubric-1",
                question_id=subj_q_id,
                criteria={"points": [{"desc": "正确", "score": 10}]},
                source="manual",
                school_id=school_id,
            ))

        resp = await client.get(
            f"/api/v1/grading/dispatch/status?exam_id={exam_id}",
            headers=dispatch_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        subject_status = next(s for s in data if s["subject_id"] == subject_id)
        assert subject_status["stage"] == "ready"

    async def test_objective_only_not_ready(self, client, db_engine, dispatch_fixtures, dispatch_headers):
        """F012 回归：只有选择题答案（无 image_path）时不应 ready，应为 idle。
        防护 CE-002：answer_count>0 但无主观题 → 用户点 AI 阅卷得 400。"""
        exam_id = dispatch_fixtures["exam_id"]
        subject_id = dispatch_fixtures["subject_id"]
        school_id = dispatch_fixtures["school_id"]

        from edu_cloud.modules.scan.models import StudentAnswer
        async with db_engine.begin() as conn:
            await conn.execute(insert(StudentAnswer).values(
                id="sa-obj-only",
                exam_id=exam_id, subject_id=subject_id,
                student_id="stu1",
                question_id=dispatch_fixtures["objective_question_id"],
                detected_answer="A", score=3.0,
                image_path=None,
                school_id=school_id,
            ))

        resp = await client.get(
            f"/api/v1/grading/dispatch/status?exam_id={exam_id}",
            headers=dispatch_headers,
        )
        data = resp.json()
        subject_status = next(s for s in data if s["subject_id"] == subject_id)
        assert subject_status["stage"] == "idle", f"Expected idle for objective-only, got {subject_status['stage']}"

    async def test_failed_task_shows_failed_stage(self, client, db_engine, dispatch_fixtures, dispatch_headers):
        """F012 回归：GradingTask status=failed 必须显示 failed，不能折叠成 done。"""
        exam_id = dispatch_fixtures["exam_id"]
        subject_id = dispatch_fixtures["subject_id"]
        school_id = dispatch_fixtures["school_id"]

        from edu_cloud.modules.scan.models import StudentAnswer
        from edu_cloud.modules.grading.models import GradingTask, Rubric

        async with db_engine.begin() as conn:
            await conn.execute(insert(StudentAnswer).values(
                id="sa-fail-test",
                exam_id=exam_id, subject_id=subject_id,
                student_id="stu1",
                question_id=dispatch_fixtures["subjective_question_id"],
                image_path="/tmp/test.png",
                school_id=school_id,
            ))
            await conn.execute(insert(Rubric).values(
                id="rubric-fail",
                question_id=dispatch_fixtures["subjective_question_id"],
                criteria={"points": [{"desc": "正确", "score": 10}]},
                source="manual",
                school_id=school_id,
            ))
            await conn.execute(insert(GradingTask).values(
                id="gt-failed",
                subject_id=subject_id, status="failed",
                total=10, completed=0, failed=10,
                created_by=dispatch_fixtures["user_id"],
                school_id=school_id,
            ))

        resp = await client.get(
            f"/api/v1/grading/dispatch/status?exam_id={exam_id}",
            headers=dispatch_headers,
        )
        data = resp.json()
        subject_status = next(s for s in data if s["subject_id"] == subject_id)
        assert subject_status["stage"] == "failed", f"Expected failed, got {subject_status['stage']}"

    async def test_multi_subject_mixed_stages(self, client, db_engine, dispatch_fixtures, dispatch_headers):
        """多科目混合状态：验证批量查询正确隔离每科数据。"""
        exam_id = dispatch_fixtures["exam_id"]
        school_id = dispatch_fixtures["school_id"]
        math_subject_id = dispatch_fixtures["subject_id"]

        from edu_cloud.modules.exam.models import Subject, Question
        from edu_cloud.modules.scan.models import StudentAnswer
        from edu_cloud.modules.grading.models import GradingTask, GradingResult, Rubric

        async with db_engine.begin() as conn:
            # 第二科目：英语（idle — 无任何数据，无主观题 → all_subj_q_ids 边界）
            await conn.execute(insert(Subject).values(
                id="subj-eng", name="英语", exam_id=exam_id,
                school_id=school_id, code="english",
            ))
            await conn.execute(insert(Question).values(
                id="q-eng-choice", subject_id="subj-eng", question_type="choice",
                name="听力1", max_score=2.0, correct_answer="B", school_id=school_id,
            ))

            # 第三科目：语文（reviewing — 有答卷+rubric+completed task+GradingResult）
            await conn.execute(insert(Subject).values(
                id="subj-chn", name="语文", exam_id=exam_id,
                school_id=school_id, code="chinese",
            ))
            await conn.execute(insert(Question).values(
                id="q-chn-essay", subject_id="subj-chn", question_type="essay",
                name="作文", max_score=60.0, school_id=school_id,
            ))
            await conn.execute(insert(StudentAnswer).values(
                id="sa-chn-1", exam_id=exam_id, subject_id="subj-chn",
                student_id="stu1", question_id="q-chn-essay",
                image_path="/tmp/chn.png", school_id=school_id,
            ))
            await conn.execute(insert(StudentAnswer).values(
                id="sa-chn-2", exam_id=exam_id, subject_id="subj-chn",
                student_id="stu2", question_id="q-chn-essay",
                image_path="/tmp/chn2.png", school_id=school_id,
            ))
            await conn.execute(insert(Rubric).values(
                id="rubric-chn", question_id="q-chn-essay",
                criteria={"points": [{"desc": "优秀", "score": 60}]},
                source="manual", school_id=school_id,
            ))
            await conn.execute(insert(GradingTask).values(
                id="gt-chn-done", subject_id="subj-chn", status="completed",
                total=2, completed=2, failed=0,
                created_by=dispatch_fixtures["user_id"], school_id=school_id,
            ))
            # GradingResult: 2 个 AI 评分，1 个已确认，1 个待复核
            await conn.execute(insert(GradingResult).values(
                id="gr-chn-1", answer_id="sa-chn-1", question_id="q-chn-essay",
                school_id=school_id, ai_task_id="gt-chn-done",
                ai_score=55.0, ai_confidence=0.9, status="confirmed",
                final_score=55.0, max_score=60.0, source="ai", version=1,
            ))
            await conn.execute(insert(GradingResult).values(
                id="gr-chn-2", answer_id="sa-chn-2", question_id="q-chn-essay",
                school_id=school_id, ai_task_id="gt-chn-done",
                ai_score=48.0, ai_confidence=0.85, status="ai_done",
                max_score=60.0, version=1,
            ))

            # 数学：ai_grading 状态（有答卷+rubric+processing task）
            await conn.execute(insert(StudentAnswer).values(
                id="sa-math-multi", exam_id=exam_id, subject_id=math_subject_id,
                student_id="stu1", question_id=dispatch_fixtures["subjective_question_id"],
                image_path="/tmp/math.png", school_id=school_id,
            ))
            await conn.execute(insert(Rubric).values(
                id="rubric-math-multi", question_id=dispatch_fixtures["subjective_question_id"],
                criteria={"points": [{"desc": "正确", "score": 10}]},
                source="ai_generated", school_id=school_id,
            ))
            await conn.execute(insert(GradingTask).values(
                id="gt-math-proc", subject_id=math_subject_id, status="processing",
                total=5, completed=2, failed=0,
                created_by=dispatch_fixtures["user_id"], school_id=school_id,
            ))

        resp = await client.get(
            f"/api/v1/grading/dispatch/status?exam_id={exam_id}",
            headers=dispatch_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

        by_code = {s["subject_code"]: s for s in data}

        # 英语：纯选择题科目 → idle, 无主观题 questions
        eng = by_code["english"]
        assert eng["stage"] == "idle"
        assert eng["answer_count"] == 0
        assert eng["questions"] == []
        assert eng["ai_scored_count"] == 0
        assert eng["confirmed_total"] == 0

        # 语文：reviewing（ai_scored_count=2 > confirmed_total=1）
        chn = by_code["chinese"]
        assert chn["stage"] == "reviewing"
        assert chn["answer_count"] == 2
        assert chn["subjective_total"] == 2
        assert chn["ai_scored_count"] == 2
        assert chn["confirmed_total"] == 1
        assert chn["manual_confirmed_count"] == 0
        assert len(chn["questions"]) == 1
        q_chn = chn["questions"][0]
        assert q_chn["name"] == "作文"
        assert q_chn["has_rubric"] is True
        assert q_chn["ai_scored_count"] == 2
        assert q_chn["graded_count"] == 1
        assert q_chn["answer_count"] == 2

        # 数学：ai_grading
        math = by_code["math"]
        assert math["stage"] == "ai_grading"
        assert math["answer_count"] == 1
        assert math["ai_pending_count"] == 3
        assert math["grading_task_id"] == "gt-math-proc"
        assert len(math["questions"]) == 1
        assert math["questions"][0]["has_rubric"] is True
        assert math["questions"][0]["rubric_source"] == "ai_generated"
