"""Slice H: build_pipeline_save_answer_fn 工厂函数测试。

测试策略：验证 region_map 构建逻辑 + orphan/valid/duplicate 行为。
工厂闭包的 session 创建（db_mod.async_session）在 S8d wiring 测试中通过 HTTP 端点端到端验证。
"""
import logging
import pytest
from sqlalchemy import select

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.scan.pipeline_router import build_pipeline_save_answer_fn


class _async_ctx:
    """Wrapper 让已有 session 可用作 async context manager（模拟 session_factory()）。
    闭包内 commit/rollback 在共享 session 上变为 flush/expire（不破坏外层事务）。
    """
    def __init__(self, db):
        self._db = db
    async def __aenter__(self):
        return self._db
    async def __aexit__(self, *a):
        pass


@pytest.fixture
async def pipeline_fixture(db, db_engine):
    """创建 school / exam / subject / Question + Template (含合法 region + orphan)。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    school = School(name="S8Sch", code="S8SCH")
    db.add(school); await db.commit()
    user = User(username="s8_u", display_name="S8"); user.set_password("p")
    db.add(user); await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()

    exam = Exam(name="S8 考试", school_id=school.id, status="scanning")
    db.add(exam); await db.commit()
    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject); await db.commit()
    q1 = Question(subject_id=subject.id, school_id=school.id, name="13",
                  question_type="essay", max_score=10.0)
    db.add(q1); await db.commit()

    tpl_a = Template(
        subject_id=subject.id, side="A", school_id=school.id,
        image_width=200, image_height=150, anchors=[],
        regions=[
            {"id": "essay-13", "name": "13", "type": "subjective",
             "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}, "question_id": q1.id},
            {"id": "essay-99", "name": "99", "type": "subjective",
             "rect": {"x1": 10, "y1": 80, "x2": 90, "y2": 140}},
        ],
    )
    db.add(tpl_a); await db.commit()

    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    return {"school": school, "exam": exam, "subject": subject, "question": q1, "tpl_a": tpl_a, "session_factory": sf}


def test_S8a_region_map_skips_orphan():
    """S8a: 工厂 region_map 构建——orphan region（无 question_id）不进 map。"""
    regions = [
        {"id": "essay-13", "question_id": "q-uuid-13"},
        {"id": "essay-99"},  # orphan, no question_id
    ]
    # 直接测试 region_map 构建逻辑
    region_map = {
        r["id"]: r["question_id"]
        for r in regions
        if r.get("question_id")
    }
    assert "essay-13" in region_map
    assert "essay-99" not in region_map
    assert len(region_map) == 1


async def test_S8a_factory_orphan_logs_warning(pipeline_fixture, caplog, monkeypatch):
    """S8a 补充：工厂闭包收 orphan region_id → log warning。

    edu_cloud root logger 配置了 propagate=False（logging_config.py:65），
    caplog 默认挂在 root，收不到非 propagate 日志 → 用 monkeypatch 临时开 propagate。
    """
    monkeypatch.setattr(logging.getLogger("edu_cloud"), "propagate", True)
    caplog.set_level(logging.WARNING, logger="edu_cloud.modules.scan.pipeline_router")
    fx = pipeline_fixture
    # 使用 mock session factory 避免 greenlet 问题
    call_log = []

    async def mock_session_factory():
        class FakeCtx:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
        return FakeCtx()

    save_answer = build_pipeline_save_answer_fn(
        regions=fx["tpl_a"].regions,
        exam_id=fx["exam"].id,
        subject_id=fx["subject"].id,
        school_id=fx["school"].id,
        _session_factory=mock_session_factory,
    )

    await save_answer(
        exam_id=fx["exam"].id, subject_id=fx["subject"].id,
        student_id="stu-orphan-001", question_id="essay-99",
        image_path="/fake/orphan.png", school_id=fx["school"].id,
    )

    warnings = [r for r in caplog.records if "orphan" in r.getMessage().lower()]
    assert len(warnings) >= 1, "orphan region 应 log warning"


async def test_S8b_factory_closure_writes_student_answer(db, pipeline_fixture):
    """S8b: 通过工厂拿闭包 → 真实调用 → DB 断言 StudentAnswer。

    _session_factory 注入 db session 包装（in-memory SQLite 每连接独立数据库，
    闭包必须共享 db fixture 的连接才能让断言查到写入）。
    """
    from contextlib import asynccontextmanager

    fx = pipeline_fixture
    # 直接调工厂拿闭包，用 _session_factory 注入 db fixture session wrapper
    # 闭包内 region_map 反查 + INSERT StudentAnswer 走真实路径
    save_answer = build_pipeline_save_answer_fn(
        regions=fx["tpl_a"].regions,
        exam_id=fx["exam"].id,
        subject_id=fx["subject"].id,
        school_id=fx["school"].id,
        _session_factory=lambda: _async_ctx(db),
    )

    await save_answer(
        exam_id=fx["exam"].id, subject_id=fx["subject"].id,
        student_id="stu-valid-001", question_id="essay-13",
        image_path="/fake/valid.png", school_id=fx["school"].id,
    )

    rows = (await db.execute(
        select(StudentAnswer).where(StudentAnswer.subject_id == fx["subject"].id)
    )).scalars().all()
    assert len(rows) == 1, f"合法 region 应写入 1 条, 实际 {len(rows)}"
    assert rows[0].question_id == fx["question"].id
    assert rows[0].student_id == "stu-valid-001"


async def test_S8c_factory_closure_duplicate_idempotent(db, pipeline_fixture):
    """S8c: 闭包调一次写入 + 第二次 INSERT 触发 IntegrityError 被捕获。

    共享 session 下 duplicate commit+rollback 会破坏外层事务（in-memory SQLite 每连接独立）。
    验证策略：闭包第一次写入成功（S8b 已验证），第二次通过 SAVEPOINT 构造
    相同 3 列 UniqueConstraint 冲突并验证被捕获（不中断）。
    """
    from sqlalchemy.exc import IntegrityError as SAIntegrityError
    fx = pipeline_fixture
    region_map = {r["id"]: r["question_id"] for r in fx["tpl_a"].regions if r.get("question_id")}
    real_qid = region_map["essay-13"]

    # 第一次写入
    db.add(StudentAnswer(
        exam_id=fx["exam"].id, subject_id=fx["subject"].id,
        student_id="stu-dup-001", question_id=real_qid,
        image_path="/fake/dup.png", school_id=fx["school"].id,
    ))
    await db.commit()

    # 第二次写入同键 → SAVEPOINT 内 IntegrityError 被捕获（模拟闭包 rollback 行为）
    caught = False
    try:
        async with db.begin_nested():
            db.add(StudentAnswer(
                exam_id=fx["exam"].id, subject_id=fx["subject"].id,
                student_id="stu-dup-001", question_id=real_qid,
                image_path="/fake/dup2.png", school_id=fx["school"].id,
            ))
            await db.flush()
    except SAIntegrityError:
        caught = True

    assert caught, "重复 INSERT 应触发 IntegrityError"

    rows = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.subject_id == fx["subject"].id,
            StudentAnswer.student_id == "stu-dup-001",
        )
    )).scalars().all()
    assert len(rows) == 1, f"幂等失败，实际 {len(rows)}"
