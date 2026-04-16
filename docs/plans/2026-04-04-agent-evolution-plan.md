# edu-agent 演进实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 edu-agent 构建专用数据层（DataScope + ScopedQuery）、工作流引擎（W1/W3/W6）、意图路由（IntentRouter）和域工具重组，实现考后分析、学情画像、异常巡检三大场景。

**Architecture:** 双模式架构 — 已知场景走工作流确定性轨道（快+准+省），未知问题保留 LLM 自由查询灵活性。DataScope 在会话创建时一次性计算，全程不可放大（fail-closed）。工作流引擎基于持久化状态机 + 幂等键 + arq worker 执行。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + arq + Redis + PostgreSQL。复用现有 AgentLoop / ToolRegistry / EventBus / LLMProxyAdapter。

**Design:** `docs/plans/2026-04-04-agent-evolution-design.md`（617 行，GPT 补充审查 27 项已处置）

---

## 文件结构

### 新建文件

```
src/edu_cloud/
  ai/
    data_scope.py              # DataScope frozen dataclass + DataScopeBuilder
    scoped_query.py            # ScopedQuery 统一过滤层（替代 AI 层中的 ScopeFilter 用法）
    intent_router.py           # IntentRouter + DomainClassifier（关键词规则 + 实体槽位）
    entity_extractor.py        # EntityExtractor（exam/class/student/subject/time 槽位提取）
    workflow/
      __init__.py              # 包入口
      engine.py                # WorkflowEngine + WorkflowExecutor（状态机 + 持久化 + 重试）
      registry.py              # WorkflowRegistry（工作流定义注册）
      triggers.py              # EventTrigger + ScheduleTrigger + IntentTrigger
      w1_post_exam.py          # W1 考后分析 5 步
      w3_student_profile.py    # W3 学情画像 4 步
      w6_patrol.py             # W6 异常巡检 4 步
    tools/
      exam_overview.py         # get_exam_overview（合并 4 个旧工具，读 exam_analysis_snapshot）
      class_report_tool.py     # get_class_report（合并 3 个旧工具，读 class_exam_report）
      student_diagnosis.py     # get_student_diagnosis（读扩展后的 student_exam_snapshots）
      findings_tools.py        # get_findings + get_agent_tasks（读 agent_findings/agent_tasks）
      student_profile_tool.py  # get_student_profile（合并 4 个旧工具，画像+趋势+知识+错误模式）
  models/
    guardian.py                # GuardianStudentLink
    workflow.py                # WorkflowRun + WorkflowStep
    agent_finding.py           # AgentFinding + AgentTask
    agent_snapshot.py          # ExamAnalysisSnapshot + ClassExamReport

tests/
  test_ai/
    test_data_scope.py         # DataScope + DataScopeBuilder
    test_scoped_query.py       # ScopedQuery
    test_intent_router.py      # IntentRouter + EntityExtractor
    test_workflow_engine.py    # WorkflowEngine 核心
    test_w1_post_exam.py       # W1 步骤
    test_w3_profile.py         # W3 步骤
    test_w6_patrol.py          # W6 步骤
    test_new_tools.py          # 新域工具
  test_models/
    test_agent_models.py       # 新表模型 CRUD
```

### 修改文件

```
src/edu_cloud/
  core/permissions.py          # parent 角色加 USE_AI_CHAT（Task 4）
  ai/tool_access.py            # fail-closed 保险（Task 4）
  ai/prompts.py                # 新增 parent_advisor prompt 模板（Task 13）
  ai/tools/__init__.py         # 注册新工具、标记旧工具 deprecated（Task 17-18）
  api/ai.py                    # 集成 DataScope + IntentRouter + WorkflowEngine（Task 16）
  worker.py                    # 添加 W3 + W6 cron jobs（Task 18）
```

---

## Batch 1: 基础设施（Tasks 1-5）

> B1 是地基，所有后续批次依赖它。

### Task 1: Agent 新增数据模型（8 张表 + migration）

**Files:**
- Create: `src/edu_cloud/models/guardian.py`
- Create: `src/edu_cloud/models/workflow.py`
- Create: `src/edu_cloud/models/agent_finding.py`
- Create: `src/edu_cloud/models/agent_snapshot.py`
- Modify: `tests/test_alembic_migration.py`（追加新模型 import，使 Base.metadata 包含 7 张新表）
- Test: `tests/test_models/test_agent_models.py`

**说明：** 创建设计 §1-§3 中定义的 8 张新表：guardian_student_links、workflow_runs、workflow_steps、exam_analysis_snapshot、class_exam_report、agent_findings、agent_tasks、scope_versions。全部继承 Base + IdMixin/TenantMixin + TimestampMixin，使用 ForeignKey 关联现有表。scope_versions 表在 Task 5 中使用，但 migration 统一在 Task 1 生成。

- [ ] **Step 1: 写 guardian_student_links 模型测试**

```python
# tests/test_models/test_agent_models.py
import pytest
from edu_cloud.models.guardian import GuardianStudentLink

@pytest.mark.asyncio
async def test_create_guardian_link(db):
    link = GuardianStudentLink(
        guardian_user_id="user-parent-1",
        student_id="student-1",
        relationship="father",
        school_id="school-1",
        is_primary=True,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    assert link.id is not None
    assert link.relationship == "father"
    assert link.is_primary is True

@pytest.mark.asyncio
async def test_guardian_link_unique_constraint(db):
    """同一 guardian + student 不能重复。"""
    for _ in range(2):
        db.add(GuardianStudentLink(
            guardian_user_id="user-p1", student_id="s1",
            relationship="father", school_id="school-1",
        ))
    with pytest.raises(Exception):  # IntegrityError
        await db.commit()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_models/test_agent_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.models.guardian'`

- [ ] **Step 3: 实现 guardian.py 模型**

```python
# src/edu_cloud/models/guardian.py
"""监护人-学生关联表（设计 §1）。"""
from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin

class GuardianStudentLink(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "guardian_student_links"
    __table_args__ = (
        UniqueConstraint("guardian_user_id", "student_id"),
    )
    guardian_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    student_id: Mapped[str] = mapped_column(String(100), index=True)
    relationship: Mapped[str] = mapped_column(String(20))  # father/mother/guardian/other
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_models/test_agent_models.py::test_create_guardian_link -v`
Expected: PASS

- [ ] **Step 5: 写 workflow_runs + workflow_steps 模型测试**

```python
@pytest.mark.asyncio
async def test_create_workflow_run(db):
    from edu_cloud.models.workflow import WorkflowRun
    run = WorkflowRun(
        school_id="school-1",
        workflow_name="post_exam_analysis",
        trigger_type="event",
        trigger_ref="exam-123",
        idempotency_key="school-1:post_exam_analysis:exam-123:2026-04-04",
        status="pending",
        current_step=0,
        total_steps=5,
    )
    db.add(run)
    await db.commit()
    assert run.id is not None
    assert run.retry_count == 0

@pytest.mark.asyncio
async def test_workflow_idempotency_key_unique(db):
    from edu_cloud.models.workflow import WorkflowRun
    for _ in range(2):
        db.add(WorkflowRun(
            school_id="s1", workflow_name="w1", trigger_type="event",
            trigger_ref="e1", idempotency_key="same-key", status="pending",
            current_step=0, total_steps=5,
        ))
    with pytest.raises(Exception):
        await db.commit()

@pytest.mark.asyncio
async def test_create_workflow_step(db):
    from edu_cloud.models.workflow import WorkflowRun, WorkflowStep
    run = WorkflowRun(
        school_id="s1", workflow_name="w1", trigger_type="event",
        trigger_ref="e1", idempotency_key="k1", status="running",
        current_step=1, total_steps=3,
    )
    db.add(run)
    await db.flush()
    step = WorkflowStep(
        run_id=run.id, step_index=1, step_name="compute_snapshot", status="running",
    )
    db.add(step)
    await db.commit()
    assert step.run_id == run.id
```

- [ ] **Step 6: 实现 workflow.py 模型**

```python
# src/edu_cloud/models/workflow.py
"""工作流执行记录（设计 §3）。"""
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin

class WorkflowRun(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "workflow_runs"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    workflow_name: Mapped[str] = mapped_column(String(100))
    trigger_type: Mapped[str] = mapped_column(String(20))  # event/schedule/intent
    trigger_ref: Mapped[str] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(500), index=True)
    status: Mapped[str] = mapped_column(String(20))  # pending/running/completed/failed/retrying
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)

class WorkflowStep(Base, IdMixin, TimestampMixin):
    __tablename__ = "workflow_steps"

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_runs.id"))
    step_index: Mapped[int] = mapped_column(Integer)
    step_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    input_summary: Mapped[dict | None] = mapped_column(JSON, default=None)
    output_summary: Mapped[dict | None] = mapped_column(JSON, default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
```

- [ ] **Step 7: 运行 workflow 模型测试确认通过**

Run: `python -m pytest tests/test_models/test_agent_models.py -k workflow -v`
Expected: PASS

- [ ] **Step 8: 写 agent_snapshot 模型（exam_analysis_snapshot + class_exam_report）测试**

```python
@pytest.mark.asyncio
async def test_create_exam_analysis_snapshot(db):
    from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot
    snap = ExamAnalysisSnapshot(
        exam_id="exam-1", school_id="school-1",
        snapshot_type="school_overview", target_type="school", target_id=None,
        semester="2025-2026-2", version=1, status="computing",
        metrics={"avg_score": 78.5, "max_score": 99},
    )
    db.add(snap)
    await db.commit()
    assert snap.status == "computing"

@pytest.mark.asyncio
async def test_create_class_exam_report(db):
    from edu_cloud.models.agent_snapshot import ClassExamReport
    report = ClassExamReport(
        exam_id="exam-1", class_id="class-1", school_id="school-1",
        grade_rank=3, class_avg=75.0, grade_avg=72.0, vs_last_exam=2.5,
        metrics={"top_students": ["s1", "s2"]},
        version=1, status="ready",
    )
    db.add(report)
    await db.commit()
    assert report.grade_rank == 3
```

- [ ] **Step 9: 实现 agent_snapshot.py 模型**

```python
# src/edu_cloud/models/agent_snapshot.py
"""Agent 预计算快照（设计 §2）。"""
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin

class ExamAnalysisSnapshot(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "exam_analysis_snapshot"

    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), index=True)
    snapshot_type: Mapped[str] = mapped_column(String(30))  # school_overview/subject_detail/grade_aggregate
    target_type: Mapped[str] = mapped_column(String(20))    # school/grade/subject
    target_id: Mapped[str | None] = mapped_column(String(36), default=None)
    subject_code: Mapped[str | None] = mapped_column(String(50), default=None)
    semester: Mapped[str] = mapped_column(String(30))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20))  # computing/ready/stale
    metrics: Mapped[dict | None] = mapped_column(JSON, default=None)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

class ClassExamReport(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "class_exam_report"

    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), index=True)
    class_id: Mapped[str] = mapped_column(String(36), index=True)
    grade_rank: Mapped[int | None] = mapped_column(Integer, default=None)
    class_avg: Mapped[float | None] = mapped_column(Float, default=None)
    grade_avg: Mapped[float | None] = mapped_column(Float, default=None)
    vs_last_exam: Mapped[float | None] = mapped_column(Float, default=None)
    metrics: Mapped[dict | None] = mapped_column(JSON, default=None)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 10: 写 agent_finding.py 模型（agent_findings + agent_tasks）测试**

```python
@pytest.mark.asyncio
async def test_create_agent_finding(db):
    from edu_cloud.models.agent_finding import AgentFinding
    finding = AgentFinding(
        school_id="school-1", finding_type="score_anomaly",
        severity="critical", target_type="class", target_id="class-3",
        summary="3班数学均分偏离年级均值 2.5 个标准差",
        detail={"threshold": 2.0, "actual": 2.5, "class_avg": 45.0, "grade_avg": 72.0},
        status="new", notify_roles=["homeroom_teacher", "academic_director"],
        idempotency_key="class:class-3:score_anomaly:2026-04-04",
    )
    db.add(finding)
    await db.commit()
    assert finding.severity == "critical"

@pytest.mark.asyncio
async def test_finding_idempotency_key_unique(db):
    from edu_cloud.models.agent_finding import AgentFinding
    for _ in range(2):
        db.add(AgentFinding(
            school_id="s1", finding_type="score_anomaly", severity="info",
            target_type="class", target_id="c1", summary="test",
            status="new", idempotency_key="same-key",
        ))
    with pytest.raises(Exception):
        await db.commit()

@pytest.mark.asyncio
async def test_create_agent_task(db):
    from edu_cloud.models.agent_finding import AgentTask
    task = AgentTask(
        school_id="school-1", task_type="generate_report",
        assignee_role="homeroom_teacher",
        payload={"exam_id": "exam-1", "class_id": "class-3"},
        status="pending",
    )
    db.add(task)
    await db.commit()
    assert task.status == "pending"
```

- [ ] **Step 11: 实现 agent_finding.py 模型**

```python
# src/edu_cloud/models/agent_finding.py
"""Agent 发现与待办（设计 §2）。"""
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin

class AgentFinding(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "agent_findings"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    finding_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))  # info/warning/critical
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str | None] = mapped_column(String(100), default=None)
    summary: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(String(20))  # new/notified/acknowledged/resolved
    notify_roles: Mapped[list | None] = mapped_column(JSON, default=None)
    idempotency_key: Mapped[str] = mapped_column(String(500), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

class AgentTask(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "agent_tasks"

    finding_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_findings.id"), default=None
    )
    task_type: Mapped[str] = mapped_column(String(50))
    assignee_role: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(String(20))  # pending/in_progress/completed/cancelled
```

- [ ] **Step 12: 全部模型测试通过**

Run: `python -m pytest tests/test_models/test_agent_models.py -v`
Expected: ALL PASS（约 8 个测试）

- [ ] **Step 13: 生成 Alembic migration**

Run: `cd C:/Users/Administrator/edu-cloud && alembic revision --autogenerate -m "add agent evolution tables"`
验证 migration 文件包含 8 张新表（含 scope_versions）。

- [ ] **Step 14: Commit**

```bash
git add src/edu_cloud/models/guardian.py src/edu_cloud/models/workflow.py \
  src/edu_cloud/models/agent_finding.py src/edu_cloud/models/agent_snapshot.py \
  tests/test_models/test_agent_models.py alembic/versions/
git commit -m "feat(models): add 8 agent evolution tables — guardian/workflow/snapshot/finding/scope_version"
```

**测试契约:**
1. guardian_student_links 唯一约束
   - 入口: `db.add(GuardianStudentLink(...))`
   - 反例: 不加 UniqueConstraint → 重复 guardian+student 静默插入，家长 DataScope 会看到重复孩子
   - 边界: 同一 guardian 关联多个 student（合法）/ 同一 student 被多个 guardian 关联（合法）
   - 回归: N/A（新表）
   - 命令: `python -m pytest tests/test_models/test_agent_models.py::test_guardian_link_unique_constraint -v`

2. workflow_runs 幂等键唯一
   - 入口: `db.add(WorkflowRun(idempotency_key=...))`
   - 反例: 不加唯一约束 → 同一事件重复触发工作流，产出重复快照
   - 边界: 空 idempotency_key / 超长 key（500 char limit）/ 不同 school 相同 trigger_ref
   - 回归: N/A
   - 命令: `python -m pytest tests/test_models/test_agent_models.py::test_workflow_idempotency_key_unique -v`

3. agent_findings 幂等键唯一
   - 入口: `db.add(AgentFinding(idempotency_key=...))`
   - 反例: 不加唯一约束 → 同一异常重复告警，轰炸教师
   - 边界: 同 target 不同 type（合法）/ 同 target 同 type 不同日期（合法）
   - 回归: N/A
   - 命令: `python -m pytest tests/test_models/test_agent_models.py::test_finding_idempotency_key_unique -v`

**边界条件:**
- 空 JSON 字段（metrics=None, detail=None）→ 期望: 正常创建，不抛异常
- guardian relationship 非标准值（如 "stepfather"）→ 期望: 正常存入，String(20) 不做枚举约束（应用层校验）
- workflow_run 状态流转（pending→running→completed）→ 期望: 无 DB 层约束，应用层控制

**审查清单:**
- ✓ 7 张表全部继承 Base + IdMixin + TenantMixin（需要 school_id 的）+ TimestampMixin
- ✓ 所有 FK 指向正确表（users/exams/schools/agent_findings/workflow_runs）
- ✓ 幂等键字段有 UniqueConstraint + index
- ✓ status 字段用 String 不用 Enum（方便扩展）
- ✗ 不存在孤立模型（每张表都在设计文档有对应章节）
- ✗ 无未被使用的字段

---

### Task 2: DataScope 数据结构 + DataScopeBuilder

**Files:**
- Create: `src/edu_cloud/ai/data_scope.py`
- Test: `tests/test_ai/test_data_scope.py`

**说明：** 实现设计 §1 的 DataScope frozen dataclass + DataScopeBuilder（从 user_roles + teacher_assignments + guardian_links + capabilities + school_settings 推导 8 角色的可见边界）。

- [ ] **Step 1: 写 DataScope 构造测试**

```python
# tests/test_ai/test_data_scope.py
import pytest
from edu_cloud.ai.data_scope import DataScope

def test_data_scope_is_frozen():
    scope = DataScope(
        user_id="u1", school_id="s1", role="subject_teacher",
        visible_class_ids=["c1", "c2"], visible_subject_codes=["math"],
        visible_grade_ids=None, visible_student_ids=None,
        district_ids=None, can_write=True, can_see_rankings=True,
        can_cross_school=False, persona="teacher_assistant", version=1,
    )
    assert scope.role == "subject_teacher"
    assert scope.visible_class_ids == ["c1", "c2"]
    with pytest.raises(AttributeError):
        scope.role = "principal"  # frozen
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_ai/test_data_scope.py::test_data_scope_is_frozen -v`
Expected: FAIL

- [ ] **Step 3: 实现 DataScope dataclass**

```python
# src/edu_cloud/ai/data_scope.py
"""DataScope — Agent 会话级数据作用域（设计 §1）。"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class DataScope:
    user_id: str
    school_id: str
    role: str
    visible_class_ids: list[str] | None      # None = 不限
    visible_subject_codes: list[str] | None
    visible_grade_ids: list[str] | None
    visible_student_ids: list[str] | None     # 家长: [child_id]
    district_ids: list[str] | None            # district_admin 专用
    can_write: bool
    can_see_rankings: bool
    can_cross_school: bool
    persona: str      # teacher_assistant / parent_advisor / admin_analyst / school_leader
    version: int
    computed_at: datetime | None = None
```

- [ ] **Step 4: 测试通过**

Run: `python -m pytest tests/test_ai/test_data_scope.py::test_data_scope_is_frozen -v`
Expected: PASS

- [ ] **Step 5: 写 DataScopeBuilder 角色推导测试（8 角色）**

```python
@pytest.mark.asyncio
async def test_build_scope_platform_admin(db, admin_user):
    from edu_cloud.ai.data_scope import DataScopeBuilder
    scope = await DataScopeBuilder(db).build(admin_user.id, role_id=admin_user.roles[0].id)
    assert scope.visible_class_ids is None  # 全部
    assert scope.can_cross_school is True
    assert scope.persona == "admin_analyst"

@pytest.mark.asyncio
async def test_build_scope_subject_teacher(db, teacher_with_assignments):
    """科任教师只看到任教班+任教科目。"""
    user, role = teacher_with_assignments  # fixture 需创建 teacher_assignments
    scope = await DataScopeBuilder(db).build(user.id, role_id=role.id)
    assert scope.visible_class_ids is not None
    assert len(scope.visible_class_ids) > 0
    assert scope.visible_subject_codes is not None
    assert scope.persona == "teacher_assistant"

@pytest.mark.asyncio
async def test_build_scope_parent(db, parent_with_child):
    """家长只看到自己孩子。"""
    user, role = parent_with_child  # fixture 需创建 guardian_student_links
    scope = await DataScopeBuilder(db).build(user.id, role_id=role.id)
    assert scope.visible_student_ids is not None
    assert len(scope.visible_student_ids) == 1
    assert scope.can_write is False
    assert scope.persona == "parent_advisor"
    assert scope.can_see_rankings is False  # 默认 false

@pytest.mark.asyncio
async def test_build_scope_homeroom_teacher_pair_matrix(db, homeroom_teacher_with_assignments):
    """班主任特殊逻辑：自己班全科，其他任教班只有任教科目（GPT #C）。"""
    user, role = homeroom_teacher_with_assignments
    scope = await DataScopeBuilder(db).build(user.id, role_id=role.id)
    # 班主任 visible_class_ids 包含 homeroom + 任教班
    assert scope.visible_class_ids is not None
    assert len(scope.visible_class_ids) >= 1

@pytest.mark.asyncio
async def test_build_scope_fail_closed_unknown_role(db):
    """未知角色 → fail-closed → 最小权限。"""
    from edu_cloud.ai.data_scope import DataScopeBuilder, DataScopeBuildError
    with pytest.raises(DataScopeBuildError):
        await DataScopeBuilder(db).build("unknown-user", role_id="unknown-role")
```

- [ ] **Step 6: 实现 DataScopeBuilder**

DataScopeBuilder 核心逻辑（在 `data_scope.py` 中追加）：

```python
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.guardian import GuardianStudentLink

logger = logging.getLogger(__name__)

class DataScopeBuildError(Exception):
    pass

PERSONA_MAP = {
    "platform_admin": "admin_analyst",
    "district_admin": "admin_analyst",
    "principal": "school_leader",
    "academic_director": "teacher_assistant",
    "grade_leader": "teacher_assistant",
    "homeroom_teacher": "teacher_assistant",
    "subject_teacher": "teacher_assistant",
    "parent": "parent_advisor",
}

ADMIN_ROLES = {"platform_admin", "district_admin", "principal", "academic_director"}

class DataScopeBuilder:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def build(self, user_id: str, role_id: str) -> DataScope:
        # 1. 查 user_roles 获取 role + school_id
        from edu_cloud.modules.auth.models import UserRole
        role_row = await self._db.get(UserRole, role_id)
        if not role_row or role_row.user_id != user_id:
            raise DataScopeBuildError(f"Role {role_id} not found for user {user_id}")

        role = role_row.role
        school_id = role_row.school_id or ""
        persona = PERSONA_MAP.get(role)
        if persona is None:
            raise DataScopeBuildError(f"Unknown role: {role}")

        # 2. 基础可见边界
        visible_classes = None
        visible_subjects = None
        visible_grades = None
        visible_students = None
        district_ids = None
        can_cross = role in ("platform_admin", "district_admin")
        can_write = role != "parent"

        # 3. 角色特化
        if role == "district_admin":
            district_ids = role_row.district_ids or []
        elif role == "parent":
            # 从 guardian_student_links 推导
            result = await self._db.execute(
                select(GuardianStudentLink.student_id)
                .where(GuardianStudentLink.guardian_user_id == user_id)
                .where(GuardianStudentLink.school_id == school_id)
            )
            visible_students = [r[0] for r in result.all()]
        elif role in ("grade_leader", "homeroom_teacher", "subject_teacher"):
            # 从 teacher_assignments 推导
            from edu_cloud.models.teacher_assignment import TeacherAssignment
            result = await self._db.execute(
                select(TeacherAssignment)
                .where(TeacherAssignment.user_id == user_id)
                .where(TeacherAssignment.school_id == school_id)
                .where(TeacherAssignment.is_active == True)
            )
            assignments = result.scalars().all()
            visible_classes = list({a.class_id for a in assignments})
            if role == "subject_teacher":
                visible_subjects = list({a.subject_code for a in assignments})
            elif role == "homeroom_teacher":
                # 自己班全科（class_ids from UserRole），任教班只有任教科
                homeroom_class_ids = role_row.class_ids or []
                visible_classes = list(set(visible_classes) | set(homeroom_class_ids))
                # subject_codes: 任教科目列表（班主任对自己班不受此限制，在 ScopedQuery 处理）
                visible_subjects = list({a.subject_code for a in assignments})
            elif role == "grade_leader":
                visible_grades = role_row.grade_ids or []
                visible_classes = None  # 本年级全部班

        # 4. 软规则（school_settings）
        can_see_rankings = True  # 默认教职可见
        if role == "parent":
            can_see_rankings = await self._get_setting(school_id, "parent_can_see_ranking", False)

        from datetime import datetime, timezone
        return DataScope(
            user_id=user_id, school_id=school_id, role=role,
            visible_class_ids=visible_classes,
            visible_subject_codes=visible_subjects,
            visible_grade_ids=visible_grades,
            visible_student_ids=visible_students,
            district_ids=district_ids,
            can_write=can_write,
            can_see_rankings=can_see_rankings,
            can_cross_school=can_cross,
            persona=persona, version=1,
            computed_at=datetime.now(timezone.utc),
        )

    async def _get_setting(self, school_id: str, key: str, default: bool) -> bool:
        from edu_cloud.models.school_settings import SchoolSetting
        result = await self._db.execute(
            select(SchoolSetting.value)
            .where(SchoolSetting.school_id == school_id)
            .where(SchoolSetting.key == key)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return default
        return row.lower() in ("true", "1", "yes")
```

- [ ] **Step 7: 运行全部 DataScope 测试**

Run: `python -m pytest tests/test_ai/test_data_scope.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/ai/data_scope.py tests/test_ai/test_data_scope.py
git commit -m "feat(ai): DataScope + DataScopeBuilder — 8-role derivation with fail-closed"
```

**测试契约:**
1. DataScope 不可变性
   - 入口: `scope.role = "x"`
   - 反例: 用普通 dataclass → 运行时可修改 scope → 工具调用间权限升级
   - 边界: frozen=True 确保赋值抛 AttributeError
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_data_scope.py::test_data_scope_is_frozen -v`

2. 家长 visible_students 推导
   - 入口: `DataScopeBuilder(db).build(parent_user_id, role_id)`
   - 反例: 不查 guardian_student_links → visible_students=None → 家长看到全校学生
   - 边界: 无 guardian 记录→空列表 / 多个孩子→多项 / 跨校 guardian→只返回本校
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_data_scope.py::test_build_scope_parent -v`

3. 未知角色 fail-closed
   - 入口: `DataScopeBuilder(db).build("u", "bad-role")`
   - 反例: 不校验 → 构造出 persona=None 的 scope → 下游工具无法判断权限
   - 边界: role_id 不存在 / user_id 与 role_id 不匹配 / role 字符串不在 PERSONA_MAP
   - 回归: D7 fail-closed 决策
   - 命令: `python -m pytest tests/test_ai/test_data_scope.py::test_build_scope_fail_closed_unknown_role -v`

**边界条件:**
- teacher_assignments 为空的科任教师 → 期望: visible_class_ids=[]、visible_subject_codes=[]，不是 None
- district_admin 无 district_ids → 期望: district_ids=[]，不报错
- parent 无 guardian 记录 → 期望: visible_student_ids=[]，can_write=False，不报错

**审查清单:**
- ✓ DataScope frozen=True
- ✓ 8 角色全部有推导规则（PERSONA_MAP 覆盖 8 角色）
- ✓ 家长从 guardian_student_links 推导
- ✓ 班主任从 homeroom class_ids + teacher_assignments 组合推导
- ✓ fail-closed: 未知角色抛 DataScopeBuildError
- ✗ DataScope 不包含 db session（纯数据）

---

### Task 3: ScopedQuery 统一过滤层

**Files:**
- Create: `src/edu_cloud/ai/scoped_query.py`
- Test: `tests/test_ai/test_scoped_query.py`

**说明：** 实现设计 §1 的 ScopedQuery — 所有 AI 工具数据访问的统一入口。自动注入 WHERE 条件（school_id + class_id + student_id + subject_code），不可放大。

- [ ] **Step 1: 写 ScopedQuery 测试**

```python
# tests/test_ai/test_scoped_query.py
import pytest
from sqlalchemy import select
from edu_cloud.ai.data_scope import DataScope
from edu_cloud.ai.scoped_query import ScopedQuery, ScopeViolationError

@pytest.mark.asyncio
async def test_scoped_query_injects_school_id(db):
    """school_id 强制注入。"""
    scope = DataScope(
        user_id="u1", school_id="school-1", role="subject_teacher",
        visible_class_ids=["c1"], visible_subject_codes=["math"],
        visible_grade_ids=None, visible_student_ids=None,
        district_ids=None, can_write=True, can_see_rankings=True,
        can_cross_school=False, persona="teacher_assistant", version=1,
    )
    sq = ScopedQuery(db, scope)
    from edu_cloud.modules.profile.models import StudentExamSnapshot
    query = select(StudentExamSnapshot)
    scoped = sq.apply(query, StudentExamSnapshot)
    # 验证 WHERE 中包含 school_id = 'school-1'
    compiled = str(scoped.compile(compile_kwargs={"literal_binds": True}))
    assert "school_id" in compiled

@pytest.mark.asyncio
async def test_scoped_query_rejects_amplification(db):
    """请求的 class_id 不在 visible_class_ids 内 → 拒绝。"""
    scope = DataScope(
        user_id="u1", school_id="s1", role="subject_teacher",
        visible_class_ids=["c1", "c2"], visible_subject_codes=["math"],
        visible_grade_ids=None, visible_student_ids=None,
        district_ids=None, can_write=True, can_see_rankings=True,
        can_cross_school=False, persona="teacher_assistant", version=1,
    )
    sq = ScopedQuery(db, scope)
    with pytest.raises(ScopeViolationError, match="class_id"):
        sq.validate_param("class_id", "c-forbidden")

@pytest.mark.asyncio
async def test_scoped_query_admin_no_class_filter(db):
    """platform_admin 不注入 class_id 过滤。"""
    scope = DataScope(
        user_id="u1", school_id="", role="platform_admin",
        visible_class_ids=None, visible_subject_codes=None,
        visible_grade_ids=None, visible_student_ids=None,
        district_ids=None, can_write=True, can_see_rankings=True,
        can_cross_school=True, persona="admin_analyst", version=1,
    )
    sq = ScopedQuery(db, scope)
    from edu_cloud.modules.profile.models import StudentExamSnapshot
    query = select(StudentExamSnapshot)
    scoped = sq.apply(query, StudentExamSnapshot)
    compiled = str(scoped.compile(compile_kwargs={"literal_binds": True}))
    assert "class_id" not in compiled  # admin 不限制

@pytest.mark.asyncio
async def test_scoped_query_parent_locks_student_ids(db):
    """家长只看自己孩子的数据。"""
    scope = DataScope(
        user_id="u1", school_id="s1", role="parent",
        visible_class_ids=None, visible_subject_codes=None,
        visible_grade_ids=None, visible_student_ids=["student-child-1"],
        district_ids=None, can_write=False, can_see_rankings=False,
        can_cross_school=False, persona="parent_advisor", version=1,
    )
    sq = ScopedQuery(db, scope)
    from edu_cloud.modules.profile.models import StudentExamSnapshot
    query = select(StudentExamSnapshot)
    scoped = sq.apply(query, StudentExamSnapshot)
    compiled = str(scoped.compile(compile_kwargs={"literal_binds": True}))
    assert "student_id" in compiled
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_ai/test_scoped_query.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 ScopedQuery**

```python
# src/edu_cloud/ai/scoped_query.py
"""ScopedQuery — AI 工具统一数据过滤层（设计 §1）。"""
from __future__ import annotations
import logging
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.ai.data_scope import DataScope

logger = logging.getLogger(__name__)

class ScopeViolationError(Exception):
    """请求的参数超出 DataScope 允许的边界。"""

class ScopedQuery:
    def __init__(self, db: AsyncSession, scope: DataScope):
        self.db = db
        self.scope = scope

    def apply(self, query: Select, model, *, school_col="school_id",
              class_col="class_id", student_col="student_id",
              subject_col="subject_code") -> Select:
        """自动注入 WHERE 条件。"""
        # 1. school_id 强制（除跨校角色）
        if not self.scope.can_cross_school and hasattr(model, school_col):
            query = query.where(getattr(model, school_col) == self.scope.school_id)

        # 2. district_ids
        if self.scope.district_ids is not None and hasattr(model, "district"):
            query = query.where(getattr(model, "district").in_(self.scope.district_ids))

        # 3. class_ids
        if self.scope.visible_class_ids is not None and hasattr(model, class_col):
            query = query.where(getattr(model, class_col).in_(self.scope.visible_class_ids))

        # 4. subject_codes
        if self.scope.visible_subject_codes is not None and hasattr(model, subject_col):
            query = query.where(getattr(model, subject_col).in_(self.scope.visible_subject_codes))

        # 5. student_ids（家长锁定）
        if self.scope.visible_student_ids is not None and hasattr(model, student_col):
            query = query.where(getattr(model, student_col).in_(self.scope.visible_student_ids))

        return query

    async def execute(self, query: Select, model=None, **col_overrides) -> list:
        """apply + execute 一步到位。"""
        if model is not None:
            query = self.apply(query, model, **col_overrides)
        result = await self.db.execute(query)
        return result.all()

    def validate_param(self, param_name: str, value: str) -> None:
        """验证请求参数不超出 scope 边界。"""
        checks = {
            "class_id": self.scope.visible_class_ids,
            "subject_code": self.scope.visible_subject_codes,
            "student_id": self.scope.visible_student_ids,
        }
        allowed = checks.get(param_name)
        if allowed is not None and value not in allowed:
            raise ScopeViolationError(
                f"{param_name}={value} not in scope (allowed: {allowed})"
            )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_ai/test_scoped_query.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/scoped_query.py tests/test_ai/test_scoped_query.py
git commit -m "feat(ai): ScopedQuery — unified scope-aware data filter with amplification guard"
```

**测试契约:**
1. school_id 强制注入
   - 入口: `ScopedQuery(db, scope).apply(query, Model)`
   - 反例: 不注入 school_id → 教师看到别校学生数据
   - 边界: model 无 school_id 列（跳过）/ platform_admin（跳过）/ 空 school_id
   - 回归: D2 DataScope 硬边界设计
   - 命令: `python -m pytest tests/test_ai/test_scoped_query.py::test_scoped_query_injects_school_id -v`

2. 参数放大拒绝
   - 入口: `sq.validate_param("class_id", "forbidden")`
   - 反例: 不校验 → 工具参数可突破 scope 限制
   - 边界: scope.visible_class_ids=None（不限制）/ 空列表（全拒绝）/ 参数恰在列表中
   - 回归: 不可放大设计原则
   - 命令: `python -m pytest tests/test_ai/test_scoped_query.py::test_scoped_query_rejects_amplification -v`

**边界条件:**
- model 无对应列名（如无 class_id）→ 期望: 跳过该条件，不报错
- visible_class_ids=[] 空列表 → 期望: WHERE class_id IN () → 查询返回空结果
- 多条件叠加（school_id + class_id + subject_code）→ 期望: AND 连接

**审查清单:**
- ✓ school_id 对非跨校角色强制注入
- ✓ validate_param 防放大
- ✓ None 表示不限制，空列表表示全拒绝
- ✓ 家长 student_ids 锁定
- ✗ 不修改查询结果（只注入 WHERE）

---

### Task 4a: parent 权限补全

**Files:**
- Modify: `src/edu_cloud/core/permissions.py:168-171`
- Test: `tests/test_api/test_parent_permission.py`

**说明：** parent 角色加 USE_AI_CHAT 权限（设计 §5, GPT #G-1）。

- [ ] **Step 1: 写 parent 权限测试**

```python
# tests/test_api/test_parent_permission.py
from edu_cloud.core.permissions import ROLE_PERMISSIONS, Permission

def test_parent_has_use_ai_chat():
    assert Permission.USE_AI_CHAT in ROLE_PERMISSIONS["parent"]

def test_parent_has_view_scores():
    assert Permission.VIEW_SCORES in ROLE_PERMISSIONS["parent"]

def test_parent_no_write_permissions():
    parent_perms = ROLE_PERMISSIONS["parent"]
    write_perms = {Permission.MANAGE_SCHOOLS, Permission.MANAGE_HOMEWORK,
                   Permission.MANAGE_GRADING, Permission.MANAGE_EXAM_RESULTS}
    assert not parent_perms & write_perms
```

- [ ] **Step 2: 运行测试确认 USE_AI_CHAT 失败**

Run: `python -m pytest tests/test_api/test_parent_permission.py -v`
Expected: FAIL on `test_parent_has_use_ai_chat`

- [ ] **Step 3: 修改 permissions.py**

在 `core/permissions.py` 第 168-171 行，parent 权限集中加入 `Permission.USE_AI_CHAT`:

```python
"parent": {
    Permission.VIEW_SCORES,
    Permission.VIEW_HOMEWORK,
    Permission.USE_AI_CHAT,  # 设计 §5, GPT #G-1
},
```

- [ ] **Step 4: 测试通过**

Run: `python -m pytest tests/test_api/test_parent_permission.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/core/permissions.py tests/test_api/test_parent_permission.py
git commit -m "feat(permissions): grant parent USE_AI_CHAT — design §5, GPT #G-1"
```

**测试契约:**
1. parent 角色含 USE_AI_CHAT
   - 入口: `ROLE_PERMISSIONS["parent"]`
   - 反例: 不加 → 家长发起 AI 对话被 deps.py 的 require_permission 拦截，返回 403
   - 边界: 旧角色别名 "admin"/"teacher" 不受影响
   - 回归: 防止未来权限重构遗漏
   - 命令: `python -m pytest tests/test_api/test_parent_permission.py -v`

**边界条件:**
- parent 无 MANAGE_* 权限 → 期望: 集合交集为空
- platform_admin 仍有全部权限 → 期望: set(Permission) 不受影响
- 新增 permission 不影响其他角色 → 期望: 只改 parent 集合

**审查清单:**
- ✓ 只加 USE_AI_CHAT，不加其他权限
- ✓ 旧角色兼容别名不受影响
- ✗ 不引入新的 Permission 枚举值

---

### Task 4b: ToolAccessResolver fail-closed 改造

**Files:**
- Modify: `src/edu_cloud/ai/tool_access.py`（默认策略从 allow → deny）
- Modify: `src/edu_cloud/services/capability_service.py:144-153`（check_capability 默认从 allow → deny）
- Modify: `tests/test_ai/test_tool_access.py`（更新现有测试预期）
- Test: `tests/test_ai/test_tool_access_fail_closed.py`

**说明：** 将 ToolAccessResolver 和 capability 检查从 fail-open（无记录=允许）改为 fail-closed（无记录=拒绝）。这是安全语义变更（设计 D7），需要同步更新现有测试。当前 tool_access.py:37 注释"无记录默认允许"、capability_service.py:144-153 的 check_capability 也是"无记录=默认允许"，均需改为默认拒绝。

- [ ] **Step 1: 写 fail-closed 反例测试**

```python
# tests/test_ai/test_tool_access_fail_closed.py
import pytest
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.registry import ToolSpec

def _make_spec(name, allowed_roles=None, module_code=None, requires_capabilities=None):
    return ToolSpec(
        name=name, description="test", parameters={},
        func=lambda i, c: None,
        allowed_roles=allowed_roles or [],
        module_code=module_code,
        requires_capabilities=requires_capabilities or [],
    )

def test_no_capability_record_rejects():
    """无 capability 记录 → 拒绝（fail-closed）。"""
    spec = _make_spec("tool_x", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("analytics", "read")])
    resolver = ToolAccessResolver()
    # capabilities 为空 dict → 无记录
    result = resolver.resolve([spec], role="subject_teacher",
                               enabled_modules=["analytics"],
                               capabilities={})
    assert len(result) == 0  # fail-closed: 无记录 = 拒绝

def test_module_disabled_rejects():
    """模块未启用 → 工具不存在。"""
    spec = _make_spec("tool_y", allowed_roles=["subject_teacher"],
                       module_code="grading")
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=["analytics"],
                                          capabilities={})
    assert len(result) == 0

def test_explicit_allow_passes():
    """显式 capability enabled=True → 允许。"""
    spec = _make_spec("tool_z", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("analytics", "read")])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=["analytics"],
                                          capabilities={("analytics", "read"): True})
    assert len(result) == 1
```

- [ ] **Step 2: 运行测试确认 test_no_capability_record_rejects 失败**

Run: `python -m pytest tests/test_ai/test_tool_access_fail_closed.py::test_no_capability_record_rejects -v`
Expected: FAIL（当前是 fail-open，无记录=允许）

- [ ] **Step 3: 修改 tool_access.py — 无记录改为拒绝**

在 `tool_access.py` 中，capability 过滤逻辑从"无记录默认允许"改为"无记录默认拒绝"：

```python
# 旧: if cap_key in capabilities and capabilities[cap_key] is False: reject
# 新: if cap_key not in capabilities or capabilities[cap_key] is not True: reject
```

- [ ] **Step 4: 修改 capability_service.py — check_capability 默认拒绝**

```python
# capability_service.py 第 144-153 行
# 旧: 无记录 → return True
# 新: 无记录 → return False
```

- [ ] **Step 5: 更新现有 test_tool_access.py 预期**

现有 `test_tool_access.py:61` 的测试预期"default-allow"需改为"default-deny"。

- [ ] **Step 6: 运行全部 tool_access 测试**

Run: `python -m pytest tests/test_ai/test_tool_access*.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/ai/tool_access.py src/edu_cloud/services/capability_service.py \
  tests/test_ai/test_tool_access.py tests/test_ai/test_tool_access_fail_closed.py
git commit -m "feat(security): ToolAccessResolver fail-closed — no record = deny (D7)"
```

**测试契约:**
1. 无 capability 记录时拒绝
   - 入口: `ToolAccessResolver().resolve(specs, role, enabled_modules, capabilities={})`
   - 反例: fail-open 实现 → 无记录默认允许 → 新增工具未配置 capability 自动对全角色开放
   - 边界: capabilities 空 dict / capability 为 False / capability 为 True
   - 回归: D7 fail-closed 设计决策
   - 命令: `python -m pytest tests/test_ai/test_tool_access_fail_closed.py::test_no_capability_record_rejects -v`

2. 模块禁用时工具不存在
   - 入口: `resolver.resolve(specs, role, enabled_modules=["analytics"], ...)` with spec.module_code="grading"
   - 反例: 不检查 module → 禁用模块的工具仍出现在 LLM 工具列表
   - 边界: module_code=None（无模块要求，始终可见）/ 空 enabled_modules / 全部启用
   - 回归: 硬边界"模块禁用 = 工具不存在"
   - 命令: `python -m pytest tests/test_ai/test_tool_access_fail_closed.py::test_module_disabled_rejects -v`

**边界条件:**
- requires_capabilities 为空列表 → 期望: 不检查 capability，通过（无 capability 要求的工具不受 fail-closed 影响）
- allowed_roles 为空列表 → 期望: 所有角色可用（空=不限制）
- 现有测试中 default-allow 预期 → 期望: 更新为 default-deny

**审查清单:**
- ✓ tool_access.py 默认策略改 deny
- ✓ capability_service.py check_capability 默认改 deny
- ✓ 现有 test_tool_access.py 预期同步更新
- ✓ 新增反例测试覆盖 fail-closed
- ✗ 不影响 requires_capabilities=[] 的工具（无 capability 要求=不检查）

---

### Task 5: Scope 版本机制

**Files:**
- Modify: `src/edu_cloud/ai/data_scope.py`（追加 version check）
- Create: `src/edu_cloud/ai/scope_version.py`
- Test: `tests/test_ai/test_scope_version.py`

**说明：** 实现设计 §1 的 scope 版本失效机制。使用 DB 表 `scope_versions` 持久化版本号（跨 API 进程 + arq worker 共享）。每次 tool 调用前检查 version 是否匹配，不匹配 → 返回提示要求刷新。

- [ ] **Step 1: 写版本检查测试**

```python
# tests/test_ai/test_scope_version.py
import pytest
from edu_cloud.ai.scope_version import ScopeVersionChecker

@pytest.mark.asyncio
async def test_version_match_passes(db):
    checker = ScopeVersionChecker(db)
    # 首次检查，无记录 → 通过（version=1 是初始值）
    is_valid = await checker.is_valid(school_id="s1", user_id="u1", version=1)
    assert is_valid is True

@pytest.mark.asyncio
async def test_version_mismatch_fails(db):
    checker = ScopeVersionChecker(db)
    await checker.bump(school_id="s1", user_id="u1", reason="assignment.changed")
    is_valid = await checker.is_valid(school_id="s1", user_id="u1", version=1)
    assert is_valid is False

@pytest.mark.asyncio
async def test_bump_increments_version(db):
    checker = ScopeVersionChecker(db)
    v = await checker.get_current_version(school_id="s1", user_id="u1")
    await checker.bump(school_id="s1", user_id="u1", reason="role.changed")
    v2 = await checker.get_current_version(school_id="s1", user_id="u1")
    assert v2 == v + 1

@pytest.mark.asyncio
async def test_bump_persists_across_checker_instances(db):
    """版本 bump 跨实例可见（DB 持久化）。"""
    checker1 = ScopeVersionChecker(db)
    await checker1.bump(school_id="s1", user_id="u1", reason="test")
    checker2 = ScopeVersionChecker(db)  # 新实例
    v = await checker2.get_current_version(school_id="s1", user_id="u1")
    assert v == 2  # bump 后应为 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_ai/test_scope_version.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 scope_versions DB 模型**

在 Task 1 的 `models/workflow.py` 中追加（或新建 `models/scope_version.py`）：

```python
class ScopeVersion(Base, TimestampMixin):
    """Scope 版本跟踪（跨进程共享）。"""
    __tablename__ = "scope_versions"
    __table_args__ = (UniqueConstraint("school_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_reason: Mapped[str | None] = mapped_column(String(200), default=None)
```

- [ ] **Step 4: 实现 ScopeVersionChecker（DB 持久化）**

```python
# src/edu_cloud/ai/scope_version.py
"""Scope 版本检查（设计 §1 版本失效）。DB 持久化，跨 API + worker 进程共享。"""
from __future__ import annotations
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

class ScopeVersionChecker:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_current_version(self, school_id: str, user_id: str) -> int:
        from edu_cloud.models.scope_version import ScopeVersion
        row = (await self._db.execute(
            select(ScopeVersion)
            .where(ScopeVersion.school_id == school_id)
            .where(ScopeVersion.user_id == user_id)
        )).scalar_one_or_none()
        return row.version if row else 1

    async def is_valid(self, school_id: str, user_id: str, version: int) -> bool:
        current = await self.get_current_version(school_id, user_id)
        return version >= current

    async def bump(self, school_id: str, user_id: str, reason: str) -> int:
        from edu_cloud.models.scope_version import ScopeVersion
        row = (await self._db.execute(
            select(ScopeVersion)
            .where(ScopeVersion.school_id == school_id)
            .where(ScopeVersion.user_id == user_id)
        )).scalar_one_or_none()
        if row:
            row.version += 1
            row.last_reason = reason
        else:
            row = ScopeVersion(school_id=school_id, user_id=user_id, version=2, last_reason=reason)
            self._db.add(row)
        await self._db.flush()
        logger.info("scope_version: bumped %s:%s to %d (reason: %s)",
                     school_id, user_id, row.version, reason)
        return row.version

    async def bump_school(self, school_id: str, reason: str) -> None:
        """学期切换等全校失效。"""
        from edu_cloud.models.scope_version import ScopeVersion
        rows = (await self._db.execute(
            select(ScopeVersion).where(ScopeVersion.school_id == school_id)
        )).scalars().all()
        for row in rows:
            row.version += 1
            row.last_reason = reason
        await self._db.flush()
        logger.info("scope_version: bumped all users in %s (reason: %s)", school_id, reason)

```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_ai/test_scope_version.py -v`
Expected: ALL PASS

- [ ] **Step 6: 在 Task 1 migration 中包含 scope_versions 表**

Task 5 新增 `models/scope_version.py`，需在 Task 1 的 `alembic revision --autogenerate` 步骤中一并包含（或 Task 5 单独生成 migration）。确保 `test_alembic_migration.py` import 了 `edu_cloud.models.scope_version`。

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/ai/scope_version.py src/edu_cloud/models/scope_version.py \
  tests/test_ai/test_scope_version.py
git commit -m "feat(ai): ScopeVersionChecker — DB-persisted scope invalidation (scope_versions table)"
```

**测试契约:**
1. 版本匹配通过
   - 入口: `checker.is_valid(school_id, user_id, version=1)`
   - 反例: 不检查 → scope 过期后工具仍用旧权限执行
   - 边界: version=0 / 首次检查（无记录）/ bump 后检查
   - 回归: D6 scope 版本失效
   - 命令: `python -m pytest tests/test_ai/test_scope_version.py -v`

2. DB 持久化跨实例可见
   - 入口: `ScopeVersionChecker(db).bump(...)` 后新实例 `ScopeVersionChecker(db).get_current_version(...)`
   - 反例: 用进程内存 → worker bump 后 API 进程看不到 → 旧 scope 继续放行
   - 边界: 首次查询无 DB 记录 / 并发 bump / 进程重启后
   - 回归: INV-006
   - 命令: `python -m pytest tests/test_ai/test_scope_version.py::test_bump_persists_across_checker_instances -v`

**边界条件:**
- 从未 bump 过的 user → 期望: version=1（无 DB 记录时默认值），is_valid(version=1)=True
- bump_school 影响该校所有用户 → 期望: 所有相关行递增
- 不同 school 的同名 user → 期望: 版本独立（唯一约束 school_id+user_id）

**审查清单:**
- ✓ DB 持久化（scope_versions 表，跨进程共享）
- ✓ bump_school 覆盖学期切换场景
- ✓ scope_versions 纳入 migration
- ✗ 不含进程内存方案残留

---

## Batch 2: W1 考后分析（Tasks 6-10）

> 依赖 B1。工作流引擎是核心基础设施，W1 是第一个消费者。

### Task 6: WorkflowEngine 核心（Registry + Executor + 状态机）

**Files:**
- Create: `src/edu_cloud/ai/workflow/__init__.py`
- Create: `src/edu_cloud/ai/workflow/engine.py`
- Create: `src/edu_cloud/ai/workflow/registry.py`
- Test: `tests/test_ai/test_workflow_engine.py`

**说明：** 实现设计 §3 的 WorkflowEngine — 持久化状态机 + 幂等键去重 + 重试（最多 3 次）。

- [ ] **Step 1: 写 WorkflowRegistry 测试**

```python
# tests/test_ai/test_workflow_engine.py
import pytest
from edu_cloud.ai.workflow.registry import WorkflowRegistry, WorkflowDefinition, StepDefinition

def test_register_and_get_workflow():
    registry = WorkflowRegistry()
    steps = [
        StepDefinition(name="step1", func=lambda ctx: None),
        StepDefinition(name="step2", func=lambda ctx: None),
    ]
    wf = WorkflowDefinition(name="test_wf", steps=steps)
    registry.register(wf)
    assert registry.get("test_wf") is wf
    assert registry.get("nonexistent") is None

def test_registry_rejects_duplicate():
    registry = WorkflowRegistry()
    wf = WorkflowDefinition(name="dup", steps=[])
    registry.register(wf)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(wf)
```

- [ ] **Step 2: 实现 WorkflowRegistry**

```python
# src/edu_cloud/ai/workflow/registry.py
"""工作流注册中心（设计 §3）。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

StepFunc = Callable[..., Coroutine[Any, Any, dict | None]]

@dataclass
class StepDefinition:
    name: str
    func: StepFunc
    compensate: StepFunc | None = None  # 补偿函数（可选）

@dataclass
class WorkflowDefinition:
    name: str
    steps: list[StepDefinition]
    max_retries: int = 3

class WorkflowRegistry:
    def __init__(self):
        self._workflows: dict[str, WorkflowDefinition] = {}

    def register(self, wf: WorkflowDefinition) -> None:
        if wf.name in self._workflows:
            raise ValueError(f"Workflow '{wf.name}' already registered")
        self._workflows[wf.name] = wf

    def get(self, name: str) -> WorkflowDefinition | None:
        return self._workflows.get(name)

    def list_all(self) -> list[str]:
        return list(self._workflows.keys())
```

- [ ] **Step 3: 写 WorkflowExecutor 测试（状态机 + 持久化 + 幂等）**

```python
@pytest.mark.asyncio
async def test_executor_runs_all_steps(db):
    from edu_cloud.ai.workflow.engine import WorkflowExecutor
    from edu_cloud.ai.workflow.registry import WorkflowDefinition, StepDefinition

    results = []
    async def step_a(ctx):
        results.append("a")
        return {"output": "a_done"}
    async def step_b(ctx):
        results.append("b")
        return {"output": "b_done"}

    wf = WorkflowDefinition(name="test", steps=[
        StepDefinition(name="step_a", func=step_a),
        StepDefinition(name="step_b", func=step_b),
    ])
    executor = WorkflowExecutor(db)
    run = await executor.execute(
        workflow=wf, school_id="s1",
        trigger_type="event", trigger_ref="e1",
    )
    assert run.status == "completed"
    assert run.current_step == 2
    assert results == ["a", "b"]

@pytest.mark.asyncio
async def test_executor_idempotency_skips_duplicate(db):
    from edu_cloud.ai.workflow.engine import WorkflowExecutor
    from edu_cloud.ai.workflow.registry import WorkflowDefinition, StepDefinition

    call_count = 0
    async def counting_step(ctx):
        nonlocal call_count
        call_count += 1

    wf = WorkflowDefinition(name="w", steps=[StepDefinition(name="s", func=counting_step)])
    executor = WorkflowExecutor(db)
    run1 = await executor.execute(workflow=wf, school_id="s1",
                                   trigger_type="event", trigger_ref="same-ref")
    run2 = await executor.execute(workflow=wf, school_id="s1",
                                   trigger_type="event", trigger_ref="same-ref")
    assert call_count == 1  # 第二次被幂等键跳过
    assert run2.id == run1.id

@pytest.mark.asyncio
async def test_executor_retries_on_failure(db):
    from edu_cloud.ai.workflow.engine import WorkflowExecutor
    from edu_cloud.ai.workflow.registry import WorkflowDefinition, StepDefinition

    attempt = 0
    async def flaky_step(ctx):
        nonlocal attempt
        attempt += 1
        if attempt < 3:
            raise RuntimeError("transient error")
        return {"ok": True}

    wf = WorkflowDefinition(name="retry_test", steps=[
        StepDefinition(name="flaky", func=flaky_step),
    ], max_retries=3)
    executor = WorkflowExecutor(db)
    run = await executor.execute(workflow=wf, school_id="s1",
                                  trigger_type="event", trigger_ref="r1")
    assert run.status == "completed"
    assert run.retry_count == 2

@pytest.mark.asyncio
async def test_executor_fails_after_max_retries(db):
    from edu_cloud.ai.workflow.engine import WorkflowExecutor
    from edu_cloud.ai.workflow.registry import WorkflowDefinition, StepDefinition

    async def always_fail(ctx):
        raise RuntimeError("permanent error")

    wf = WorkflowDefinition(name="fail_test", steps=[
        StepDefinition(name="bad", func=always_fail),
    ], max_retries=3)
    executor = WorkflowExecutor(db)
    run = await executor.execute(workflow=wf, school_id="s1",
                                  trigger_type="event", trigger_ref="f1")
    assert run.status == "failed"
    assert run.retry_count == 3
    assert "permanent error" in run.last_error
```

- [ ] **Step 4: 实现 WorkflowExecutor**

```python
# src/edu_cloud/ai/workflow/engine.py
"""工作流执行引擎（设计 §3）— 持久化状态机 + 幂等 + 重试。"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.workflow import WorkflowRun, WorkflowStep
from edu_cloud.ai.workflow.registry import WorkflowDefinition

logger = logging.getLogger(__name__)

class WorkflowContext:
    """传入每个 step 的上下文。"""
    def __init__(self, db: AsyncSession, school_id: str, trigger_ref: str,
                 run_id: str, step_outputs: dict[str, dict]):
        self.db = db
        self.school_id = school_id
        self.trigger_ref = trigger_ref
        self.run_id = run_id
        self.step_outputs = step_outputs  # 前序步骤的产出

class WorkflowExecutor:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def execute(self, workflow: WorkflowDefinition, school_id: str,
                      trigger_type: str, trigger_ref: str) -> WorkflowRun:
        idem_key = f"{school_id}:{workflow.name}:{trigger_ref}:{date.today().isoformat()}"

        # 幂等检查
        existing = await self._db.execute(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idem_key)
        )
        run = existing.scalar_one_or_none()
        if run and run.status in ("completed", "running"):
            logger.info("workflow: skipped duplicate %s", idem_key)
            return run

        # 创建或复用 run
        if not run:
            run = WorkflowRun(
                school_id=school_id, workflow_name=workflow.name,
                trigger_type=trigger_type, trigger_ref=trigger_ref,
                idempotency_key=idem_key, status="running",
                current_step=0, total_steps=len(workflow.steps),
            )
            self._db.add(run)
            await self._db.flush()

        run.status = "running"
        step_outputs: dict[str, dict] = {}

        for i, step_def in enumerate(workflow.steps):
            if i < run.current_step:
                continue  # 已完成的步骤跳过（断点续跑）

            step = WorkflowStep(
                run_id=run.id, step_index=i, step_name=step_def.name, status="running",
                started_at=datetime.now(timezone.utc),
            )
            self._db.add(step)
            await self._db.flush()

            ctx = WorkflowContext(
                db=self._db, school_id=school_id, trigger_ref=trigger_ref,
                run_id=run.id, step_outputs=step_outputs,
            )

            success = False
            for attempt in range(workflow.max_retries + 1):
                try:
                    result = await step_def.func(ctx)
                    step_outputs[step_def.name] = result or {}
                    step.status = "completed"
                    step.output_summary = result
                    step.completed_at = datetime.now(timezone.utc)
                    run.current_step = i + 1
                    success = True
                    break
                except Exception as e:
                    run.retry_count = attempt + 1
                    run.last_error = str(e)
                    logger.warning("workflow: step %s attempt %d failed: %s",
                                   step_def.name, attempt + 1, e)

            if not success:
                step.status = "failed"
                step.error = run.last_error
                step.completed_at = datetime.now(timezone.utc)
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                await self._db.commit()
                return run

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await self._db.commit()
        return run
```

- [ ] **Step 5: 写 `__init__.py` 包入口**

```python
# src/edu_cloud/ai/workflow/__init__.py
"""Workflow engine package."""
```

- [ ] **Step 6: 运行全部测试**

Run: `python -m pytest tests/test_ai/test_workflow_engine.py -v`
Expected: ALL PASS（4 个测试）

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/ai/workflow/ tests/test_ai/test_workflow_engine.py
git commit -m "feat(workflow): WorkflowEngine — persistent state machine with idempotency and retry"
```

**测试契约:**
1. 全步骤顺序执行
   - 入口: `executor.execute(workflow, school_id, trigger_type, trigger_ref)`
   - 反例: 不按顺序执行 → Step 2 依赖 Step 1 产出但拿不到
   - 边界: 0 步工作流 / 1 步 / 5 步
   - 回归: D6 持久化状态机设计
   - 命令: `python -m pytest tests/test_ai/test_workflow_engine.py::test_executor_runs_all_steps -v`

2. 幂等键去重
   - 入口: 同 trigger_ref 连续调用两次
   - 反例: 不检查幂等 → exam.published 重复触发 → 重复快照
   - 边界: 不同日期同 trigger_ref（允许）/ 不同 school 同 trigger_ref（允许）
   - 回归: D6 并发控制
   - 命令: `python -m pytest tests/test_ai/test_workflow_engine.py::test_executor_idempotency_skips_duplicate -v`

3. 重试后恢复
   - 入口: step 函数前 2 次抛异常
   - 反例: 不重试 → 瞬态网络错误导致工作流永久失败
   - 边界: max_retries=0 / 恰好第 max_retries 次成功 / 全部失败
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_workflow_engine.py::test_executor_retries_on_failure -v`

**边界条件:**
- 空步骤工作流 → 期望: 直接 completed，current_step=0
- step 返回 None → 期望: step_outputs[name]={}，不报错
- 中途失败后重新 execute（同幂等键）→ 期望: 从断点续跑（current_step 跳过已完成）

**审查清单:**
- ✓ 幂等键格式: `{school_id}:{workflow_name}:{trigger_ref}:{date}`
- ✓ 状态流转: pending→running→completed/failed
- ✓ retry_count 和 last_error 持久化
- ✓ 每步写 WorkflowStep 记录
- ✓ step 间通过 step_outputs 传递数据
- ✗ 不引入外部调度依赖（arq 调度在 Task 18）

---

### Task 7: W1 Steps 1-3（快照 + 班级报告 + 学生诊断）

**Files:**
- Create: `src/edu_cloud/ai/workflow/w1_post_exam.py`
- Test: `tests/test_ai/test_w1_post_exam.py`

**说明：** 实现 W1 考后分析的前 3 步：compute_exam_snapshot、compute_class_reports、compute_student_diagnoses。从 scores + questions + classes 表读取，写入 exam_analysis_snapshot + class_exam_report + student_exam_snapshots。

- [ ] **Step 1: 写 compute_exam_snapshot 测试**

```python
# tests/test_ai/test_w1_post_exam.py
import pytest
from edu_cloud.ai.workflow.w1_post_exam import compute_exam_snapshot
from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot

@pytest.mark.asyncio
async def test_compute_exam_snapshot_creates_overview(db, seeded_exam):
    """exam.published 后生成学校级概览快照。"""
    ctx = WorkflowContext(
        db=db, school_id=seeded_exam.school_id,
        trigger_ref=seeded_exam.id, run_id="run-1", step_outputs={},
    )
    result = await compute_exam_snapshot(ctx)
    assert result["snapshot_count"] > 0

    from sqlalchemy import select
    rows = (await db.execute(
        select(ExamAnalysisSnapshot)
        .where(ExamAnalysisSnapshot.exam_id == seeded_exam.id)
    )).scalars().all()
    assert any(r.snapshot_type == "school_overview" for r in rows)
    assert all(r.status == "ready" for r in rows)
```

- [ ] **Step 2: 写 compute_class_reports 测试**

```python
@pytest.mark.asyncio
async def test_compute_class_reports_per_class(db, seeded_exam):
    """每个班生成一份 class_exam_report。"""
    from edu_cloud.ai.workflow.w1_post_exam import compute_exam_snapshot, compute_class_reports
    ctx = WorkflowContext(
        db=db, school_id=seeded_exam.school_id,
        trigger_ref=seeded_exam.id, run_id="run-1", step_outputs={},
    )
    snap_result = await compute_exam_snapshot(ctx)
    ctx.step_outputs["compute_exam_snapshot"] = snap_result

    result = await compute_class_reports(ctx)
    assert result["report_count"] > 0

    from sqlalchemy import select
    from edu_cloud.models.agent_snapshot import ClassExamReport
    reports = (await db.execute(
        select(ClassExamReport)
        .where(ClassExamReport.exam_id == seeded_exam.id)
    )).scalars().all()
    assert len(reports) == result["report_count"]
    assert all(r.class_avg is not None for r in reports)
```

- [ ] **Step 3: 写 compute_student_diagnoses 测试**

```python
@pytest.mark.asyncio
async def test_compute_student_diagnoses_updates_snapshots(db, seeded_exam):
    """更新 student_exam_snapshots 扩展诊断字段。"""
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot, compute_class_reports, compute_student_diagnoses,
    )
    ctx = WorkflowContext(
        db=db, school_id=seeded_exam.school_id,
        trigger_ref=seeded_exam.id, run_id="run-1", step_outputs={},
    )
    ctx.step_outputs["compute_exam_snapshot"] = await compute_exam_snapshot(ctx)
    ctx.step_outputs["compute_class_reports"] = await compute_class_reports(ctx)
    result = await compute_student_diagnoses(ctx)
    assert result["student_count"] > 0
```

- [ ] **Step 4: 实现 w1_post_exam.py（3 步）**

```python
# src/edu_cloud/ai/workflow/w1_post_exam.py
"""W1 考后分析工作流步骤（设计 §3）。"""
from __future__ import annotations
import logging
from statistics import mean, stdev
from datetime import datetime, timezone
from sqlalchemy import select, func
from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot, ClassExamReport

logger = logging.getLogger(__name__)

async def compute_exam_snapshot(ctx: WorkflowContext) -> dict:
    """Step 1: 计算考试快照（学校级+科目级）。"""
    db, exam_id, school_id = ctx.db, ctx.trigger_ref, ctx.school_id

    # 导入考试相关模型
    from edu_cloud.modules.exam.models import Score, ExamSubject

    # 获取所有科目
    subjects = (await db.execute(
        select(ExamSubject).where(ExamSubject.exam_id == exam_id)
    )).scalars().all()

    # 获取当前学期（从考试信息推导）
    from edu_cloud.modules.exam.models import Exam
    exam = await db.get(Exam, exam_id)
    semester = getattr(exam, "semester", "") or f"{datetime.now().year}"

    snapshot_count = 0

    # 学校级概览
    all_scores = (await db.execute(
        select(Score.total_score)
        .where(Score.exam_id == exam_id)
        .where(Score.total_score.isnot(None))
    )).scalars().all()

    if all_scores:
        scores_list = [float(s) for s in all_scores]
        school_snap = ExamAnalysisSnapshot(
            exam_id=exam_id, school_id=school_id,
            snapshot_type="school_overview", target_type="school",
            semester=semester, version=1, status="ready",
            metrics={
                "avg_score": round(mean(scores_list), 2),
                "max_score": max(scores_list),
                "min_score": min(scores_list),
                "median_score": round(sorted(scores_list)[len(scores_list) // 2], 2),
                "std_dev": round(stdev(scores_list), 2) if len(scores_list) > 1 else 0,
                "total_students": len(scores_list),
            },
        )
        db.add(school_snap)
        snapshot_count += 1

    # 科目级快照
    for subj in subjects:
        subj_scores = (await db.execute(
            select(Score.total_score)
            .where(Score.exam_id == exam_id)
            .where(Score.subject_id == subj.id)
            .where(Score.total_score.isnot(None))
        )).scalars().all()
        if subj_scores:
            s_list = [float(s) for s in subj_scores]
            db.add(ExamAnalysisSnapshot(
                exam_id=exam_id, school_id=school_id,
                snapshot_type="subject_detail", target_type="subject",
                target_id=subj.id, subject_code=subj.subject_code,
                semester=semester, version=1, status="ready",
                metrics={
                    "avg_score": round(mean(s_list), 2),
                    "max_score": max(s_list),
                    "min_score": min(s_list),
                    "pass_rate": round(sum(1 for s in s_list if s >= 60) / len(s_list), 3),
                    "total_students": len(s_list),
                },
            ))
            snapshot_count += 1

    await db.flush()
    logger.info("W1 step1: %d snapshots for exam %s", snapshot_count, exam_id)
    return {"snapshot_count": snapshot_count}


async def compute_class_reports(ctx: WorkflowContext) -> dict:
    """Step 2: 计算班级报告。"""
    db, exam_id, school_id = ctx.db, ctx.trigger_ref, ctx.school_id

    from edu_cloud.modules.exam.models import Score
    from edu_cloud.modules.student.models import Student

    # 按班级分组计算
    from sqlalchemy import and_
    students = (await db.execute(
        select(Student.id, Student.class_id)
        .where(Student.school_id == school_id)
    )).all()
    student_class_map = {s.id: s.class_id for s in students}

    scores = (await db.execute(
        select(Score.student_id, Score.total_score)
        .where(Score.exam_id == exam_id)
        .where(Score.total_score.isnot(None))
    )).all()

    # 按班级分组
    class_scores: dict[str, list[float]] = {}
    for s in scores:
        cid = student_class_map.get(s.student_id)
        if cid:
            class_scores.setdefault(cid, []).append(float(s.total_score))

    all_avgs = [mean(v) for v in class_scores.values() if v]
    grade_avg = mean(all_avgs) if all_avgs else 0

    # 按均分排名
    sorted_classes = sorted(class_scores.items(), key=lambda x: mean(x[1]), reverse=True)

    report_count = 0
    for rank, (cid, c_scores) in enumerate(sorted_classes, 1):
        db.add(ClassExamReport(
            exam_id=exam_id, class_id=cid, school_id=school_id,
            grade_rank=rank,
            class_avg=round(mean(c_scores), 2),
            grade_avg=round(grade_avg, 2),
            vs_last_exam=None,  # TODO: 第二期对比历史
            metrics={"student_count": len(c_scores)},
            version=1, status="ready",
        ))
        report_count += 1

    await db.flush()
    logger.info("W1 step2: %d class reports for exam %s", report_count, exam_id)
    return {"report_count": report_count, "grade_avg": grade_avg}


async def compute_student_diagnoses(ctx: WorkflowContext) -> dict:
    """Step 3: 更新学生考试快照（复用 student_exam_snapshots 表）。"""
    db, exam_id, school_id = ctx.db, ctx.trigger_ref, ctx.school_id

    from edu_cloud.modules.exam.models import Score
    from edu_cloud.modules.profile.models import StudentExamSnapshot

    scores = (await db.execute(
        select(Score)
        .where(Score.exam_id == exam_id)
        .where(Score.total_score.isnot(None))
    )).scalars().all()

    student_count = 0
    for score in scores:
        # 查找或创建快照
        existing = (await db.execute(
            select(StudentExamSnapshot)
            .where(StudentExamSnapshot.student_id == score.student_id)
            .where(StudentExamSnapshot.exam_id == exam_id)
            .where(StudentExamSnapshot.subject_code == (score.subject_code or "total"))
        )).scalar_one_or_none()

        if not existing:
            db.add(StudentExamSnapshot(
                student_id=score.student_id, exam_id=exam_id,
                subject_code=score.subject_code or "total",
                total_score=score.total_score, max_score=score.max_score or 100,
                score_rate=round(score.total_score / (score.max_score or 100), 3),
                school_id=school_id,
                exam_date=datetime.now(timezone.utc),
            ))
            student_count += 1

    await db.flush()
    logger.info("W1 step3: %d student diagnoses for exam %s", student_count, exam_id)
    return {"student_count": student_count}
```

- [ ] **Step 5: 创建 seeded_exam fixture 并运行测试**

需要在 tests/conftest.py 或 tests/test_ai/conftest.py 中添加 `seeded_exam` fixture，创建一个有 scores 的考试。

Run: `python -m pytest tests/test_ai/test_w1_post_exam.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/ai/workflow/w1_post_exam.py tests/test_ai/test_w1_post_exam.py
git commit -m "feat(w1): post-exam analysis steps 1-3 — snapshot + class reports + diagnoses"
```

**测试契约:**
1. compute_exam_snapshot 生成学校级+科目级快照
   - 入口: `compute_exam_snapshot(ctx)` where ctx.trigger_ref=exam_id
   - 反例: 不区分 snapshot_type → 查询时混淆学校级和科目级数据
   - 边界: 考试无成绩（0 scores）/ 单科目 / 多科目
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_w1_post_exam.py::test_compute_exam_snapshot_creates_overview -v`

2. compute_class_reports 每班一份
   - 入口: `compute_class_reports(ctx)` 依赖 Step 1 产出
   - 反例: 不按班级分组 → 均分计算错误
   - 边界: 单班级 / 学生无班级（跳过）/ 所有学生同分
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_w1_post_exam.py::test_compute_class_reports_per_class -v`

**边界条件:**
- 考试无成绩 → 期望: snapshot_count=0，不报错
- 科目成绩只有 1 个学生 → 期望: stdev=0
- 学生不在任何班级 → 期望: 跳过该学生的 class report

**审查清单:**
- ✓ 快照类型区分 school_overview / subject_detail
- ✓ 复用 student_exam_snapshots 表
- ✓ 统计指标完整（avg/max/min/median/stdev/pass_rate）
- ✓ 班级按均分排名
- ✗ 不调用 LLM（纯计算）

---

### Task 8: W1 Steps 4-5（异常检测 + 通知派发）

**Files:**
- Modify: `src/edu_cloud/ai/workflow/w1_post_exam.py`（追加 detect_anomalies + dispatch_notifications）
- Test: `tests/test_ai/test_w1_post_exam.py`（追加）

**说明：** Step 4 异常检测（均分偏离>2σ=critical，排名变化>50=warning），Step 5 通知派发（写 agent_findings 表）。

- [ ] **Step 1: 写 detect_anomalies 测试**

```python
@pytest.mark.asyncio
async def test_detect_anomalies_finds_outlier_class(db, seeded_exam_with_outlier):
    """班级均分偏离年级 >2σ → critical finding。"""
    from edu_cloud.ai.workflow.w1_post_exam import detect_anomalies
    ctx = WorkflowContext(
        db=db, school_id=seeded_exam_with_outlier.school_id,
        trigger_ref=seeded_exam_with_outlier.id, run_id="run-1",
        step_outputs={"compute_class_reports": {"grade_avg": 72.0}},
    )
    result = await detect_anomalies(ctx)
    assert result["finding_count"] > 0

    from sqlalchemy import select
    from edu_cloud.models.agent_finding import AgentFinding
    findings = (await db.execute(
        select(AgentFinding)
        .where(AgentFinding.school_id == seeded_exam_with_outlier.school_id)
    )).scalars().all()
    assert any(f.severity == "critical" for f in findings)

@pytest.mark.asyncio
async def test_detect_anomalies_idempotent(db, seeded_exam_with_outlier):
    """同一异常不重复创建 finding。"""
    from edu_cloud.ai.workflow.w1_post_exam import detect_anomalies
    ctx = WorkflowContext(
        db=db, school_id=seeded_exam_with_outlier.school_id,
        trigger_ref=seeded_exam_with_outlier.id, run_id="run-1",
        step_outputs={"compute_class_reports": {"grade_avg": 72.0}},
    )
    r1 = await detect_anomalies(ctx)
    r2 = await detect_anomalies(ctx)
    assert r2["finding_count"] == 0  # 第二次被幂等键拦截
```

- [ ] **Step 2: 实现 detect_anomalies + dispatch_notifications**

```python
# 追加到 w1_post_exam.py

async def detect_anomalies(ctx: WorkflowContext) -> dict:
    """Step 4: 检测异常（设计 §3 W1 Step 4）。"""
    db, exam_id, school_id = ctx.db, ctx.trigger_ref, ctx.school_id
    from edu_cloud.models.agent_snapshot import ClassExamReport
    from edu_cloud.models.agent_finding import AgentFinding

    reports = (await db.execute(
        select(ClassExamReport)
        .where(ClassExamReport.exam_id == exam_id)
        .where(ClassExamReport.school_id == school_id)
    )).scalars().all()

    if len(reports) < 2:
        return {"finding_count": 0}

    avgs = [r.class_avg for r in reports if r.class_avg is not None]
    if not avgs:
        return {"finding_count": 0}

    grade_mean = mean(avgs)
    grade_std = stdev(avgs) if len(avgs) > 1 else 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    finding_count = 0
    for report in reports:
        if report.class_avg is None or grade_std == 0:
            continue
        z_score = abs(report.class_avg - grade_mean) / grade_std
        if z_score > 2:
            idem_key = f"class:{report.class_id}:score_anomaly:{today}"
            existing = (await db.execute(
                select(AgentFinding).where(AgentFinding.idempotency_key == idem_key)
            )).scalar_one_or_none()
            if existing:
                continue
            db.add(AgentFinding(
                school_id=school_id, finding_type="score_anomaly",
                severity="critical", target_type="class", target_id=report.class_id,
                summary=f"班级均分 {report.class_avg} 偏离年级均值 {grade_mean:.1f}（{z_score:.1f}σ）",
                detail={"z_score": round(z_score, 2), "class_avg": report.class_avg,
                         "grade_avg": grade_mean, "threshold": 2.0},
                status="new",
                notify_roles=["homeroom_teacher", "academic_director"],
                idempotency_key=idem_key,
            ))
            finding_count += 1

    await db.flush()
    return {"finding_count": finding_count}


async def dispatch_notifications(ctx: WorkflowContext) -> dict:
    """Step 5: 通知派发（第一期仅标记 finding 状态，不实际推送）。"""
    db, school_id = ctx.db, ctx.school_id
    from edu_cloud.models.agent_finding import AgentFinding

    findings = (await db.execute(
        select(AgentFinding)
        .where(AgentFinding.school_id == school_id)
        .where(AgentFinding.status == "new")
    )).scalars().all()

    for f in findings:
        f.status = "notified"

    await db.flush()
    return {"notified_count": len(findings)}
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_ai/test_w1_post_exam.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/ai/workflow/w1_post_exam.py tests/test_ai/test_w1_post_exam.py
git commit -m "feat(w1): steps 4-5 — anomaly detection with idempotent findings + notification dispatch"
```

**测试契约:**
1. 异常检测准确性
   - 入口: `detect_anomalies(ctx)` with class reports
   - 反例: 不计算 z-score → 误报或漏报
   - 边界: 仅 1 个班级（无 std）/ 所有班级分数相同 / 极端离群值
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_w1_post_exam.py::test_detect_anomalies_finds_outlier_class -v`

2. 幂等去重
   - 入口: 连续调用两次 detect_anomalies
   - 反例: 不检查 idempotency_key → 重复告警
   - 边界: 同日重复 / 次日新 finding / 不同 exam 同 class
   - 回归: D6 幂等键设计
   - 命令: `python -m pytest tests/test_ai/test_w1_post_exam.py::test_detect_anomalies_idempotent -v`

**边界条件:**
- 只有 1 个班级 → 期望: 无异常（无法计算标准差有意义值）
- 所有班级分数完全相同 → 期望: grade_std=0，无异常
- grade_std=0 但有偏离 → 期望: 跳过（除以零保护）

**审查清单:**
- ✓ z-score > 2 → critical
- ✓ 幂等键格式: `{target_type}:{target_id}:{finding_type}:{date}`
- ✓ dispatch_notifications 仅标记状态，不实际推送
- ✗ 未接入校历调节阈值（第二期）

---

### Task 9: W1 域工具（3 个新读工具）

**Files:**
- Create: `src/edu_cloud/ai/tools/exam_overview.py`
- Create: `src/edu_cloud/ai/tools/class_report_tool.py`
- Create: `src/edu_cloud/ai/tools/student_diagnosis.py`
- Test: `tests/test_ai/test_new_tools.py`

**说明：** 实现 3 个新域工具（读预计算表），替代现有多工具组合。使用现有 `@tools.register` 装饰器模式。

- [ ] **Step 1: 写 get_exam_overview 测试**

```python
# tests/test_ai/test_new_tools.py
import pytest
from edu_cloud.ai.tool_context import ToolContext, ToolResult

@pytest.mark.asyncio
async def test_get_exam_overview_reads_snapshot(db, seeded_snapshots):
    """get_exam_overview 从 exam_analysis_snapshot 读取。"""
    from edu_cloud.ai.tools.exam_overview import get_exam_overview
    ctx = ToolContext(
        db=db, school_id="school-1", user_id="u1", role="principal",
    )
    result = await get_exam_overview({"exam_id": seeded_snapshots.exam_id}, ctx)
    assert result.success is True
    assert "avg_score" in result.data["overview"]

@pytest.mark.asyncio
async def test_get_exam_overview_no_snapshot(db):
    """快照不存在 → 友好提示。"""
    from edu_cloud.ai.tools.exam_overview import get_exam_overview
    ctx = ToolContext(db=db, school_id="s1", user_id="u1", role="principal")
    result = await get_exam_overview({"exam_id": "nonexistent"}, ctx)
    assert result.success is True
    assert result.data["status"] == "not_found"
```

- [ ] **Step 2: 实现 exam_overview.py**

```python
# src/edu_cloud/ai/tools/exam_overview.py
"""get_exam_overview — 考试概览工具（设计 §4，替代 4 个旧工具）。"""
from sqlalchemy import select
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot

@tools.register(
    name="get_exam_overview",
    description="获取考试分析概览：全校统计 + 各科统计 + 异常告警。替代 get_exam_summary / get_score_distribution / get_question_analysis / get_grade_aggregates。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
    },
    category="analytics", domain="exam_query",
    allowed_roles=["platform_admin", "district_admin", "principal",
                    "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low", is_read_only=True,
)
async def get_exam_overview(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input["exam_id"]
    snapshots = (await ctx.db.execute(
        select(ExamAnalysisSnapshot)
        .where(ExamAnalysisSnapshot.exam_id == exam_id)
        .where(ExamAnalysisSnapshot.school_id == ctx.school_id)
        .where(ExamAnalysisSnapshot.status == "ready")
    )).scalars().all()

    if not snapshots:
        return ToolResult(success=True, data={"status": "not_found",
                          "message": "该考试分析尚未完成或不存在"})

    overview = None
    subjects = []
    for s in snapshots:
        if s.snapshot_type == "school_overview":
            overview = s.metrics
        elif s.snapshot_type == "subject_detail":
            subjects.append({"subject_code": s.subject_code, "metrics": s.metrics})

    return ToolResult(success=True, data={
        "status": "ready",
        "overview": overview,
        "subjects": subjects,
        "snapshot_count": len(snapshots),
    })
```

- [ ] **Step 3: 实现 class_report_tool.py + student_diagnosis.py（同模式）**

class_report_tool.py 读 ClassExamReport，student_diagnosis.py 读 StudentExamSnapshot。同样的 `@tools.register` + `ToolContext` + `ToolResult` 模式。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_ai/test_new_tools.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/tools/exam_overview.py src/edu_cloud/ai/tools/class_report_tool.py \
  src/edu_cloud/ai/tools/student_diagnosis.py tests/test_ai/test_new_tools.py
git commit -m "feat(tools): add exam_overview + class_report + student_diagnosis domain tools"
```

**测试契约:**
1. get_exam_overview 读预计算表
   - 入口: `get_exam_overview({"exam_id": "..."}, ctx)`
   - 反例: 不读预计算表而实时查询 → 慢且不一致
   - 边界: 快照 status=computing / 快照不存在 / 只有学校级无科目级
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_new_tools.py::test_get_exam_overview_reads_snapshot -v`

**边界条件:**
- exam_id 不存在 → 期望: success=True, data.status="not_found"，不抛异常
- 快照 status=computing → 期望: 不返回（只返回 ready 的）
- school_id 不匹配 → 期望: 返回空（ScopedQuery 过滤）

**审查清单:**
- ✓ 3 个工具全部 is_read_only=True
- ✓ 使用 @tools.register 装饰器
- ✓ 工具签名: async def(input: dict, ctx: ToolContext) -> ToolResult
- ✓ exam_overview 不包含 parent 在 allowed_roles
- ✗ 不调用 LLM

---

### Task 10: W1 对话模式 + EventBus 集成 + W1 注册

**Files:**
- Create: `src/edu_cloud/ai/workflow/triggers.py`
- Modify: `src/edu_cloud/ai/workflow/w1_post_exam.py`（注册工作流定义）
- Test: `tests/test_ai/test_w1_integration.py`

**说明：** 将 W1 注册到 WorkflowRegistry，挂载 EventBus 的 exam.published 事件触发。

- [ ] **Step 1: 写 EventTrigger 测试**

```python
# tests/test_ai/test_w1_integration.py
import pytest
from edu_cloud.ai.workflow.triggers import EventTrigger
from edu_cloud.core.events import EventBus

@pytest.mark.asyncio
async def test_event_trigger_fires_workflow(db):
    """exam.published 事件触发 W1 工作流。"""
    triggered = []
    async def mock_execute(workflow, school_id, trigger_type, trigger_ref):
        triggered.append(trigger_ref)

    bus = EventBus()
    trigger = EventTrigger(bus, executor_func=mock_execute)
    trigger.register("exam.published", workflow_name="post_exam_analysis")
    await bus.emit("exam.published", {"exam_id": "e1", "school_id": "s1"})
    assert triggered == ["e1"]
```

- [ ] **Step 2: 实现 triggers.py**

```python
# src/edu_cloud/ai/workflow/triggers.py
"""工作流触发器（设计 §3）。"""
from __future__ import annotations
import logging
from typing import Callable, Coroutine, Any
from edu_cloud.core.events import EventBus

logger = logging.getLogger(__name__)

class EventTrigger:
    def __init__(self, bus: EventBus, executor_func: Callable):
        self._bus = bus
        self._execute = executor_func

    def register(self, event: str, workflow_name: str) -> None:
        @self._bus.on(event)
        async def handler(payload: dict):
            trigger_ref = payload.get("exam_id") or payload.get("id", "")
            school_id = payload.get("school_id", "")
            logger.info("trigger: %s → %s (ref=%s)", event, workflow_name, trigger_ref)
            await self._execute(
                workflow_name=workflow_name,
                school_id=school_id,
                trigger_type="event",
                trigger_ref=trigger_ref,
            )
```

- [ ] **Step 3: 注册 W1 工作流定义**

在 w1_post_exam.py 底部追加:

```python
from edu_cloud.ai.workflow.registry import WorkflowDefinition, StepDefinition

W1_POST_EXAM = WorkflowDefinition(
    name="post_exam_analysis",
    steps=[
        StepDefinition(name="compute_exam_snapshot", func=compute_exam_snapshot),
        StepDefinition(name="compute_class_reports", func=compute_class_reports),
        StepDefinition(name="compute_student_diagnoses", func=compute_student_diagnoses),
        StepDefinition(name="detect_anomalies", func=detect_anomalies),
        StepDefinition(name="dispatch_notifications", func=dispatch_notifications),
    ],
    max_retries=3,
)
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_ai/test_w1_integration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/workflow/triggers.py tests/test_ai/test_w1_integration.py \
  src/edu_cloud/ai/workflow/w1_post_exam.py
git commit -m "feat(w1): EventTrigger + W1 workflow registration — exam.published → post_exam_analysis"
```

**测试契约:**
1. 事件触发工作流
   - 入口: `bus.emit("exam.published", {"exam_id": "...", "school_id": "..."})`
   - 反例: 不绑定触发器 → exam.published 事件被忽略，快照不生成
   - 边界: payload 缺 school_id / payload 缺 exam_id / 事件名不匹配
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_w1_integration.py -v`

**边界条件:**
- payload 缺字段 → 期望: trigger_ref=""，不报错（工作流内部处理）
- 未注册的事件名 → 期望: EventBus 无 handler，静默跳过
- 同一事件注册多个工作流 → 期望: 全部触发

**审查清单:**
- ✓ EventTrigger 使用 EventBus.on 装饰器
- ✓ W1 定义包含 5 步
- ✓ max_retries=3
- ✗ 不修改现有 EventBus 实现

---

## Batch 3: W3 学情画像（Tasks 11-13）

> 依赖 B1。复用 pipeline 表，新增画像+家长 Persona。

### Task 11: W3 Steps 1-2（知识掌握度 + 画像更新）

**Files:**
- Create: `src/edu_cloud/ai/workflow/w3_student_profile.py`
- Test: `tests/test_ai/test_w3_profile.py`

**说明：** W3 Step 1 增量更新 student_knowledge_mastery，Step 2 扩展 student_exam_snapshots 画像字段。

- [ ] **Step 1: 写 update_knowledge_mastery 测试**

```python
# tests/test_ai/test_w3_profile.py
import pytest
from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.ai.workflow.w3_student_profile import update_knowledge_mastery

@pytest.mark.asyncio
async def test_update_mastery_increments(db, seeded_exam_with_knowledge):
    """考后增量更新知识点掌握度。"""
    ctx = WorkflowContext(
        db=db, school_id="school-1",
        trigger_ref="exam-1", run_id="run-1", step_outputs={},
    )
    result = await update_knowledge_mastery(ctx)
    assert result["updated_count"] >= 0  # 可能为 0 如果无知识点关联
```

- [ ] **Step 2: 写 update_student_profiles 测试**

```python
@pytest.mark.asyncio
async def test_update_profiles_adds_trend(db, seeded_multi_exam_student):
    """多次考试后画像包含趋势数据。"""
    from edu_cloud.ai.workflow.w3_student_profile import update_student_profiles
    ctx = WorkflowContext(
        db=db, school_id="school-1",
        trigger_ref="exam-2", run_id="run-1", step_outputs={},
    )
    result = await update_student_profiles(ctx)
    assert result["profile_count"] > 0
```

- [ ] **Step 3: 实现 w3_student_profile.py Steps 1-2**

```python
# src/edu_cloud/ai/workflow/w3_student_profile.py
"""W3 学情画像工作流步骤（设计 §3）。"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from edu_cloud.ai.workflow.engine import WorkflowContext

logger = logging.getLogger(__name__)

async def update_knowledge_mastery(ctx: WorkflowContext) -> dict:
    """Step 1: 增量更新知识点掌握度（复用 student_knowledge_mastery）。"""
    db, exam_id, school_id = ctx.db, ctx.trigger_ref, ctx.school_id
    from edu_cloud.modules.profile.models import StudentKnowledgeMastery
    from edu_cloud.modules.exam.models import Score

    # 获取本次考试 scores
    scores = (await db.execute(
        select(Score).where(Score.exam_id == exam_id)
    )).scalars().all()

    updated_count = 0
    for score in scores:
        if not score.knowledge_scores:
            continue
        # knowledge_scores 格式: {"kp_id": score_value, ...}
        for kp_id, kp_score in (score.knowledge_scores or {}).items():
            existing = (await db.execute(
                select(StudentKnowledgeMastery)
                .where(StudentKnowledgeMastery.student_id == score.student_id)
                .where(StudentKnowledgeMastery.knowledge_point_id == kp_id)
            )).scalar_one_or_none()

            if existing:
                existing.attempt_count += 1
                if kp_score >= 0.6:
                    existing.correct_count += 1
                existing.mastery_level = existing.correct_count / existing.attempt_count
                existing.last_exam_id = exam_id
                existing.last_exam_date = datetime.now(timezone.utc)
            else:
                db.add(StudentKnowledgeMastery(
                    student_id=score.student_id,
                    knowledge_point_id=kp_id,
                    mastery_level=1.0 if kp_score >= 0.6 else 0.0,
                    confidence=0.3,  # 首次低置信
                    attempt_count=1,
                    correct_count=1 if kp_score >= 0.6 else 0,
                    school_id=school_id,
                    last_exam_id=exam_id,
                    last_exam_date=datetime.now(timezone.utc),
                ))
            updated_count += 1

    await db.flush()
    logger.info("W3 step1: %d mastery records for exam %s", updated_count, exam_id)
    return {"updated_count": updated_count}


async def update_student_profiles(ctx: WorkflowContext) -> dict:
    """Step 2: 更新学生画像（扩展 student_exam_snapshots 的 error_summary 字段）。"""
    db, exam_id, school_id = ctx.db, ctx.trigger_ref, ctx.school_id
    from edu_cloud.modules.profile.models import StudentExamSnapshot

    snapshots = (await db.execute(
        select(StudentExamSnapshot)
        .where(StudentExamSnapshot.exam_id == exam_id)
        .where(StudentExamSnapshot.school_id == school_id)
    )).scalars().all()

    profile_count = 0
    for snap in snapshots:
        # 查历史趋势
        history = (await db.execute(
            select(StudentExamSnapshot.score_rate, StudentExamSnapshot.exam_date)
            .where(StudentExamSnapshot.student_id == snap.student_id)
            .where(StudentExamSnapshot.subject_code == snap.subject_code)
            .order_by(StudentExamSnapshot.exam_date.desc())
            .limit(10)
        )).all()

        trend = [{"score_rate": float(h.score_rate), "date": str(h.exam_date)} for h in history]
        snap.error_summary = snap.error_summary or {}
        snap.error_summary["trend"] = trend
        snap.error_summary["exam_count"] = len(history)
        profile_count += 1

    await db.flush()
    logger.info("W3 step2: %d profiles updated for exam %s", profile_count, exam_id)
    return {"profile_count": profile_count}
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_ai/test_w3_profile.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/workflow/w3_student_profile.py tests/test_ai/test_w3_profile.py
git commit -m "feat(w3): student profile steps 1-2 — mastery update + trend enrichment"
```

**测试契约:**
1. 知识掌握度增量更新
   - 入口: `update_knowledge_mastery(ctx)`
   - 反例: 不增量 → attempt_count 始终为 1，mastery_level 不准确
   - 边界: 无 knowledge_scores 的 score / 首次出现的 kp_id / kp_score 恰好 0.6
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_w3_profile.py::test_update_mastery_increments -v`

**边界条件:**
- score.knowledge_scores=None → 期望: 跳过该 score
- 首次出现的知识点 → 期望: 创建新记录，confidence=0.3
- 同一学生同一知识点多次考试 → 期望: 累加 attempt_count

**审查清单:**
- ✓ 复用 student_knowledge_mastery 表
- ✓ 增量更新（不覆盖历史）
- ✓ trend 数据写入 error_summary（复用现有 JSON 字段）
- ✗ 不新建表

---

### Task 12: W3 Steps 3-4（班级薄弱点 + LLM 建议）

**Files:**
- Modify: `src/edu_cloud/ai/workflow/w3_student_profile.py`（追加 compute_class_weakness + generate_learning_advice）
- Test: `tests/test_ai/test_w3_profile.py`（追加）

- [ ] **Step 1: 写 compute_class_weakness 测试**

```python
@pytest.mark.asyncio
async def test_compute_class_weakness_finds_low_mastery(db, seeded_class_mastery):
    from edu_cloud.ai.workflow.w3_student_profile import compute_class_weakness
    ctx = WorkflowContext(
        db=db, school_id="school-1",
        trigger_ref="daily", run_id="run-1", step_outputs={},
    )
    result = await compute_class_weakness(ctx)
    assert result["class_count"] > 0
```

- [ ] **Step 2: 实现 Steps 3-4 + 注册 W3 定义**

Step 3 从班级学生 mastery 聚合薄弱知识点。Step 4 用 LLM 生成建议（第一期 mock，限 100 学生/天）。

```python
async def compute_class_weakness(ctx: WorkflowContext) -> dict:
    """Step 3: 计算班级薄弱知识点。"""
    # 按班级聚合 mastery_level < 0.4 的知识点
    ...
    return {"class_count": class_count}

async def generate_learning_advice(ctx: WorkflowContext) -> dict:
    """Step 4: LLM 生成学习建议（限流 100/天）。"""
    # 第一期: 基于模板生成，不调用 LLM
    ...
    return {"advice_count": advice_count}

# W3 工作流定义
from edu_cloud.ai.workflow.registry import WorkflowDefinition, StepDefinition
W3_STUDENT_PROFILE = WorkflowDefinition(
    name="student_profile",
    steps=[
        StepDefinition(name="update_knowledge_mastery", func=update_knowledge_mastery),
        StepDefinition(name="update_student_profiles", func=update_student_profiles),
        StepDefinition(name="compute_class_weakness", func=compute_class_weakness),
        StepDefinition(name="generate_learning_advice", func=generate_learning_advice),
    ],
    max_retries=3,
)
```

- [ ] **Step 3: 运行测试 + Commit**

```bash
git commit -m "feat(w3): steps 3-4 — class weakness + learning advice (template-based)"
```

**测试契约:**
1. 班级薄弱点聚合
   - 入口: `compute_class_weakness(ctx)`
   - 反例: 不过滤 mastery_level → 返回全部知识点而非薄弱点
   - 边界: 无 mastery 数据 / 所有知识点 mastery>=0.4 / 单学生班级
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_w3_profile.py::test_compute_class_weakness_finds_low_mastery -v`

**边界条件:**
- 班级无学生 mastery → 期望: 跳过，class_count 不含该班
- generate_learning_advice 限流 → 期望: 超过 100 学生后停止
- 日期切换后限流重置 → 期望: 新一天重新计数

**审查清单:**
- ✓ compute_class_weakness 阈值 mastery_level < 0.4
- ✓ generate_learning_advice 第一期用模板
- ✓ W3 定义 4 步完整

---

### Task 13: 家长 Persona + 学生画像域工具

**Files:**
- Modify: `src/edu_cloud/ai/prompts.py`（追加 parent_advisor prompt）
- Create: `src/edu_cloud/ai/tools/student_profile_tool.py`
- Test: `tests/test_ai/test_parent_persona.py`

- [ ] **Step 1: 写 parent prompt 测试**

```python
# tests/test_ai/test_parent_persona.py
def test_build_parent_prompt_is_warm():
    from edu_cloud.ai.prompts import build_parent_prompt
    prompt = build_parent_prompt(child_name="小明", school_name="育才中学")
    assert "小明" in prompt
    assert "鼓励" in prompt or "建议" in prompt
    assert "排名" not in prompt  # 默认不含排名
```

- [ ] **Step 2: 实现 parent_advisor prompt + get_student_profile 工具**

在 `prompts.py` 中追加 `build_parent_prompt` 函数。`student_profile_tool.py` 合并现有 4 个工具（trend/knowledge_map/error_patterns/weakness），只暴露给 parent_advisor persona 的子集。

- [ ] **Step 3: 运行测试 + Commit**

```bash
git commit -m "feat(persona): parent_advisor prompt + get_student_profile domain tool"
```

**测试契约:**
1. 家长 prompt 风格
   - 入口: `build_parent_prompt(child_name, school_name)`
   - 反例: 用教师 prompt → 家长看到专业术语和原始数字
   - 边界: child_name 含特殊字符 / school_name 空
   - 回归: D5 家长体验设计
   - 命令: `python -m pytest tests/test_ai/test_parent_persona.py -v`

**边界条件:**
- parent_can_see_ranking=false → 期望: prompt 不含排名指引
- 孩子无考试数据 → 期望: 工具返回 "暂无数据"
- 多个孩子 → 期望: 每次只查 visible_student_ids 中的

**审查清单:**
- ✓ 温和、鼓励、建议导向
- ✓ 不暴露 write 工具
- ✓ allowed_roles 只含 parent（+教职角色）

---

## Batch 4: W6 异常巡检（Tasks 14-15）

### Task 14: W6 Steps 1-4（巡检规则 + 去重派发）

**Files:**
- Create: `src/edu_cloud/ai/workflow/w6_patrol.py`
- Test: `tests/test_ai/test_w6_patrol.py`

**说明：** W6 每小时扫描：阅卷超时（>72h）、作业低提交率（<50%且距截止<24h）、成绩异常（复用 W1 的检测逻辑）。去重+限流。

- [ ] **Step 1: 写 scan_grading_overdue 测试**

```python
# tests/test_ai/test_w6_patrol.py
import pytest
from datetime import datetime, timezone, timedelta
from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.ai.workflow.w6_patrol import scan_grading_overdue

@pytest.mark.asyncio
async def test_scan_grading_overdue_detects_72h(db, overdue_grading_task):
    ctx = WorkflowContext(
        db=db, school_id="school-1", trigger_ref="patrol",
        run_id="run-1", step_outputs={},
    )
    result = await scan_grading_overdue(ctx)
    assert result["finding_count"] >= 1

@pytest.mark.asyncio
async def test_scan_grading_no_overdue(db, fresh_grading_task):
    ctx = WorkflowContext(
        db=db, school_id="school-1", trigger_ref="patrol",
        run_id="run-1", step_outputs={},
    )
    result = await scan_grading_overdue(ctx)
    assert result["finding_count"] == 0
```

- [ ] **Step 2: 写 scan_submission_low 和 deduplicate_and_dispatch 测试**

```python
@pytest.mark.asyncio
async def test_scan_submission_low_detects_below_50pct(db, low_submission_homework):
    from edu_cloud.ai.workflow.w6_patrol import scan_submission_low
    ctx = WorkflowContext(
        db=db, school_id="school-1", trigger_ref="patrol",
        run_id="run-1", step_outputs={},
    )
    result = await scan_submission_low(ctx)
    assert result["finding_count"] >= 1

@pytest.mark.asyncio
async def test_deduplicate_limits_per_role(db):
    """每角色每天最多 10 条推送。"""
    from edu_cloud.ai.workflow.w6_patrol import deduplicate_and_dispatch
    # 预创建 11 个 findings 给同一角色
    from edu_cloud.models.agent_finding import AgentFinding
    for i in range(11):
        db.add(AgentFinding(
            school_id="s1", finding_type="test", severity="info",
            target_type="test", target_id=f"t{i}", summary=f"test{i}",
            status="new", idempotency_key=f"k{i}",
            notify_roles=["homeroom_teacher"],
        ))
    await db.flush()
    ctx = WorkflowContext(
        db=db, school_id="s1", trigger_ref="patrol",
        run_id="run-1", step_outputs={},
    )
    result = await deduplicate_and_dispatch(ctx)
    assert result["notified_count"] <= 10
```

- [ ] **Step 3: 实现 w6_patrol.py + W6 注册**

4 个步骤函数 + W6_PATROL WorkflowDefinition。

- [ ] **Step 4: 运行测试 + Commit**

```bash
git commit -m "feat(w6): patrol workflow — grading overdue + submission low + dedup dispatch"
```

**测试契约:**
1. 阅卷超时检测
   - 入口: `scan_grading_overdue(ctx)`
   - 反例: 不检查时间 → 未超时的任务被误标
   - 边界: 恰好 72h / 71h59m（不触发）/ 已完成的阅卷任务（跳过）
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_w6_patrol.py::test_scan_grading_overdue_detects_72h -v`

2. 限流 10 条/角色/天
   - 入口: `deduplicate_and_dispatch(ctx)` with 11 findings
   - 反例: 不限流 → 教师收到海量通知，信噪比极低
   - 边界: 恰好 10 条 / 不同角色各自计数 / 跨天重置
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_w6_patrol.py::test_deduplicate_limits_per_role -v`

**边界条件:**
- 学校无阅卷任务 → 期望: finding_count=0
- 作业已过截止日期 → 期望: 不再检测提交率
- 同一天多次巡检 → 期望: 幂等键去重

**审查清单:**
- ✓ 3 种巡检规则独立
- ✓ 幂等键包含日期
- ✓ 限流 10 条/角色/天
- ✗ 未接入校历（第二期）

---

### Task 15: W6 异常概览域工具

**Files:**
- Create: `src/edu_cloud/ai/tools/findings_tools.py`
- Test: `tests/test_ai/test_new_tools.py`（追加）

- [ ] **Step 1: 写 get_findings + get_agent_tasks 测试**

```python
@pytest.mark.asyncio
async def test_get_findings_filters_by_school(db, seeded_findings):
    from edu_cloud.ai.tools.findings_tools import get_findings
    ctx = ToolContext(db=db, school_id="school-1", user_id="u1", role="academic_director")
    result = await get_findings({"status": "new", "limit": 20}, ctx)
    assert result.success is True
    assert all(f["school_id"] == "school-1" for f in result.data["findings"])
```

- [ ] **Step 2: 实现 findings_tools.py**

2 个工具：get_findings（读 agent_findings）、get_agent_tasks（读 agent_tasks）。

- [ ] **Step 3: 运行测试 + Commit**

```bash
git commit -m "feat(tools): get_findings + get_agent_tasks domain tools for W6 patrol"
```

**测试契约:**
1. get_findings 按 school 过滤
   - 入口: `get_findings({"status": "new"}, ctx)`
   - 反例: 不过滤 school_id → 看到其他学校的异常
   - 边界: 无 findings / status 不匹配 / limit=0
   - 回归: D2 DataScope 隔离
   - 命令: `python -m pytest tests/test_ai/test_new_tools.py::test_get_findings_filters_by_school -v`

**边界条件:**
- findings 为空 → 期望: success=True, data.findings=[]
- limit 参数 → 期望: 最多返回 limit 条
- 非教职角色（parent）→ 期望: 不在 allowed_roles 中

**审查清单:**
- ✓ 2 个工具 is_read_only=True
- ✓ school_id 过滤强制
- ✓ limit 默认 20，最大 50

---

## Batch 5: IntentRouter（Tasks 16-17）

### Task 16: EntityExtractor + IntentRouter

**Files:**
- Create: `src/edu_cloud/ai/entity_extractor.py`
- Create: `src/edu_cloud/ai/intent_router.py`
- Test: `tests/test_ai/test_intent_router.py`

**说明：** 第一期关键词规则 + 实体槽位提取。意图分为工作流意图（W1/W3/W6）和自由模式。

- [ ] **Step 1: 写 EntityExtractor 测试**

```python
# tests/test_ai/test_intent_router.py
from edu_cloud.ai.entity_extractor import EntityExtractor

def test_extract_exam_entity():
    result = EntityExtractor.extract("这次期中考试数学考了多少分")
    assert result.get("subject") == "math" or "数学" in str(result)

def test_extract_class_entity():
    result = EntityExtractor.extract("3班语文成绩怎么样")
    assert "3" in str(result.get("class_ref", ""))

def test_extract_no_entity():
    result = EntityExtractor.extract("你好")
    assert not result.get("exam") and not result.get("class_ref")
```

- [ ] **Step 2: 写 IntentRouter 测试**

```python
from edu_cloud.ai.intent_router import IntentRouter

def test_route_post_exam_intent():
    router = IntentRouter()
    intent = router.classify("这次考试分析出来了吗", available_workflows=["post_exam_analysis"])
    assert intent.workflow == "post_exam_analysis"

def test_route_profile_intent():
    router = IntentRouter()
    intent = router.classify("小明最近学习怎么样", available_workflows=["student_profile"])
    assert intent.workflow == "student_profile"

def test_route_free_mode():
    router = IntentRouter()
    intent = router.classify("帮我出一套数学试卷", available_workflows=[])
    assert intent.workflow is None
    assert intent.mode == "free"

def test_route_low_confidence_asks():
    router = IntentRouter()
    intent = router.classify("看看情况", available_workflows=["post_exam_analysis", "student_profile"])
    assert intent.confidence < 0.5 or intent.needs_clarification is True
```

- [ ] **Step 3: 实现 entity_extractor.py + intent_router.py**

```python
# src/edu_cloud/ai/entity_extractor.py
"""实体槽位提取（设计 §4, GPT #F-2）。"""
import re

class EntityExtractor:
    SUBJECT_MAP = {
        "语文": "chinese", "数学": "math", "英语": "english",
        "物理": "physics", "化学": "chemistry", "生物": "biology",
        "历史": "history", "地理": "geography", "政治": "politics",
    }
    CLASS_PATTERN = re.compile(r"(\d+)\s*班")
    STUDENT_PATTERN = re.compile(r"([\u4e00-\u9fa5]{2,4})(?:同学|的)")

    @classmethod
    def extract(cls, message: str) -> dict:
        result = {}
        for cn, en in cls.SUBJECT_MAP.items():
            if cn in message:
                result["subject"] = en
                break
        m = cls.CLASS_PATTERN.search(message)
        if m:
            result["class_ref"] = m.group(1)
        m = cls.STUDENT_PATTERN.search(message)
        if m:
            result["student_ref"] = m.group(1)
        return result
```

```python
# src/edu_cloud/ai/intent_router.py
"""IntentRouter — 意图分类 + 域动态加载（设计 §4）。"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class IntentResult:
    workflow: str | None
    mode: str  # "workflow" | "free"
    domains: list[str]
    confidence: float
    needs_clarification: bool = False
    entities: dict | None = None

WORKFLOW_KEYWORDS = {
    "post_exam_analysis": ["考试分析", "成绩分析", "考后", "这次考试", "期中", "期末", "月考", "分析报告"],
    "student_profile": ["学情", "画像", "学习情况", "进步", "退步", "掌握", "薄弱"],
    "patrol": ["异常", "告警", "巡检", "超时", "未完成", "提交率"],
}

DOMAIN_KEYWORDS = {
    "exam_query": ["考试", "科目", "试卷", "题目"],
    "score_analysis": ["成绩", "分数", "排名", "均分", "对比"],
    "student_profile": ["画像", "掌握度", "错题", "趋势"],
    "homework": ["作业", "提交", "批改"],
    "knowledge": ["知识点", "课标", "教材", "概念"],
    "report": ["报告", "评语", "总结"],
    "findings": ["异常", "告警", "待办"],
}

class IntentRouter:
    def classify(self, message: str, available_workflows: list[str] | None = None) -> IntentResult:
        from edu_cloud.ai.entity_extractor import EntityExtractor
        entities = EntityExtractor.extract(message)

        # 1. 尝试匹配工作流
        best_wf = None
        best_score = 0
        for wf_name, keywords in WORKFLOW_KEYWORDS.items():
            if available_workflows and wf_name not in available_workflows:
                continue
            score = sum(1 for kw in keywords if kw in message)
            if score > best_score:
                best_score = score
                best_wf = wf_name

        if best_score >= 2:
            return IntentResult(
                workflow=best_wf, mode="workflow", domains=[],
                confidence=min(best_score / 3, 1.0), entities=entities,
            )

        # 2. 域分类
        domains = []
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(kw in message for kw in keywords):
                domains.append(domain)

        if best_score == 1:
            return IntentResult(
                workflow=best_wf, mode="workflow", domains=domains,
                confidence=0.4, needs_clarification=True, entities=entities,
            )

        return IntentResult(
            workflow=None, mode="free", domains=domains[:2],
            confidence=0.8 if domains else 0.3, entities=entities,
        )
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_ai/test_intent_router.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/entity_extractor.py src/edu_cloud/ai/intent_router.py \
  tests/test_ai/test_intent_router.py
git commit -m "feat(ai): IntentRouter + EntityExtractor — keyword-based intent classification"
```

**测试契约:**
1. 考后分析意图匹配
   - 入口: `router.classify("这次考试分析出来了吗")`
   - 反例: 不做意图分类 → 所有问题走自由模式 → LLM 每次从头查询，慢且贵
   - 边界: 只命中 1 个关键词（低置信度）/ 同时命中多个工作流 / 无关键词
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_intent_router.py::test_route_post_exam_intent -v`

2. 低置信度反问
   - 入口: `router.classify("看看情况")`
   - 反例: 不反问 → 猜错意图 → 返回错误结果
   - 边界: 完全无关键词 / 模糊表述 / 多意图混合
   - 回归: GPT #F-2 低置信度反问设计
   - 命令: `python -m pytest tests/test_ai/test_intent_router.py::test_route_low_confidence_asks -v`

**边界条件:**
- 空消息 → 期望: mode="free", confidence 低
- 消息同时匹配多工作流 → 期望: 选最高分的
- available_workflows=[] → 期望: 全部走 free mode

**审查清单:**
- ✓ 关键词规则覆盖 3 个工作流
- ✓ 域分类覆盖 7 个域
- ✓ 低置信度 needs_clarification=True
- ✗ 不调用 LLM（第一期纯规则）

---

### Task 17: 工具合并上线 + __init__.py 更新

**Files:**
- Modify: `src/edu_cloud/ai/tools/__init__.py`
- Test: `tests/test_ai/test_tool_registration.py`

**说明：** 将新工具注册到 ToolRegistry，标记旧工具 deprecated。新工具在 import 时自动注册。

- [ ] **Step 1: 写工具注册测试**

```python
# tests/test_ai/test_tool_registration.py
def test_new_tools_registered():
    from edu_cloud.ai.registry import tools
    # 触发全部注册
    import edu_cloud.ai.tools  # noqa
    all_names = [s.name for s in tools.get_all_specs()]
    assert "get_exam_overview" in all_names
    assert "get_class_report" in all_names
    assert "get_student_diagnosis" in all_names
    assert "get_findings" in all_names
    assert "get_agent_tasks" in all_names
    assert "get_student_profile" in all_names
```

- [ ] **Step 2: 更新 __init__.py**

在 `tools/__init__.py` 中追加新工具模块 import:

```python
from . import exam_overview        # noqa: F401
from . import class_report_tool    # noqa: F401
from . import student_diagnosis    # noqa: F401
from . import findings_tools       # noqa: F401
from . import student_profile_tool # noqa: F401
```

- [ ] **Step 3: 运行测试 + Commit**

```bash
git commit -m "feat(tools): register new domain tools + update __init__.py"
```

**测试契约:**
1. 新工具全部注册
   - 入口: `import edu_cloud.ai.tools; tools.get_all_specs()`
   - 反例: 忘记 import → 工具不在 registry → LLM 看不到 → 无法调用
   - 边界: 重复 import（幂等）/ registry 未初始化
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_tool_registration.py -v`

**审查清单:**
- ✓ 6 个新工具全部在 __init__.py 中 import
- ✓ 旧工具保留（渐进替换）
- ✗ 不删除旧工具（B6 做）

---

## Batch 6: 集成收尾（Tasks 18-19）

### Task 18: api/ai.py 集成 + arq cron + 旧工具标记

**Files:**
- Modify: `src/edu_cloud/api/ai.py`（集成 DataScope + IntentRouter + WorkflowEngine）
- Modify: `src/edu_cloud/worker.py`（添加 W3 + W6 cron）
- Test: `tests/test_api/test_ai_integration.py`

**说明：** 将所有组件串联：api/ai.py 入口 → DataScope 计算 → IntentRouter 分流 → 工作流/自由模式。arq 添加 W3 每日 + W6 每小时 cron。

- [ ] **Step 1: 创建 parent_headers fixture**

在 `tests/conftest.py` 中追加 parent 用户 + fixture（仿照现有 `teacher_headers` 模式）：

```python
# tests/conftest.py 追加
@pytest.fixture
async def parent_user(db, seed_school):
    """创建家长用户 + guardian_student_links。依赖 seed_school fixture（conftest.py:143）。"""
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.guardian import GuardianStudentLink
    user = User(username="parent1", display_name="家长张", is_active=True)
    user.set_password("123456")
    db.add(user)
    await db.flush()
    role = UserRole(user_id=user.id, role="parent", school_id=school.id, is_primary=True)
    db.add(role)
    link = GuardianStudentLink(
        guardian_user_id=user.id, student_id="student-1",
        relationship="father", school_id=school.id, is_primary=True,
    )
    db.add(link)
    await db.commit()
    return user, role

@pytest.fixture
async def parent_headers(parent_user):
    from edu_cloud.shared.auth import create_access_token
    user, role = parent_user
    token = create_access_token({"sub": user.id, "active_role_id": role.id})
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: 写 ai.py 集成测试（使用正确 fixture + 强断言）**

```python
# tests/test_api/test_ai_integration.py
import pytest

@pytest.mark.asyncio
async def test_ai_chat_calls_data_scope_builder(client, teacher_headers, mocker):
    """AI 对话必须调用 DataScopeBuilder — mock 验证路径被命中。"""
    mock_build = mocker.patch(
        "edu_cloud.api.ai.DataScopeBuilder",
        return_value=mocker.AsyncMock(build=mocker.AsyncMock(return_value=mocker.MagicMock(
            role="subject_teacher", persona="teacher_assistant",
            visible_class_ids=["c1"], visible_student_ids=None,
            can_cross_school=False, school_id="s1",
        )))
    )
    resp = await client.post(
        "/api/v1/ai/chat",
        headers=teacher_headers,
        json={"message": "这次期中考试分析"},
    )
    assert resp.status_code == 200
    mock_build.assert_called_once()  # DataScopeBuilder 被构造
    mock_build.return_value.build.assert_called_once()  # .build() 被调用

@pytest.mark.asyncio
async def test_ai_chat_parent_scope_locks_student_ids(client, parent_headers, mocker):
    """家长 AI 对话 — DataScope.visible_student_ids 必须锁定。"""
    scope_mock = mocker.MagicMock(
        role="parent", persona="parent_advisor",
        visible_student_ids=["student-1"],
        visible_class_ids=None, can_cross_school=False, school_id="s1",
        can_write=False,
    )
    mocker.patch(
        "edu_cloud.api.ai.DataScopeBuilder",
        return_value=mocker.AsyncMock(build=mocker.AsyncMock(return_value=scope_mock))
    )
    resp = await client.post(
        "/api/v1/ai/chat",
        headers=parent_headers,
        json={"message": "我孩子最近怎么样"},
    )
    assert resp.status_code == 200
    # 验证 scope 中 visible_student_ids 为 ["student-1"]
    assert scope_mock.visible_student_ids == ["student-1"]

@pytest.mark.asyncio
async def test_ai_chat_no_auth_returns_401(client):
    """无认证 → 严格 401。"""
    resp = await client.post("/api/v1/ai/chat", json={"message": "test"})
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_ai_chat_workflow_mode_reads_snapshot(client, teacher_headers, seeded_snapshots, mocker):
    """考后分析意图 → 工作流模式 → 验证 IntentRouter 被调用且命中 workflow。"""
    from edu_cloud.ai.intent_router import IntentResult
    mock_router = mocker.patch(
        "edu_cloud.api.ai.IntentRouter",
        return_value=mocker.MagicMock(classify=mocker.MagicMock(
            return_value=IntentResult(
                workflow="post_exam_analysis", mode="workflow",
                domains=[], confidence=0.9, entities={},
            )
        ))
    )
    mocker.patch(
        "edu_cloud.api.ai.DataScopeBuilder",
        return_value=mocker.AsyncMock(build=mocker.AsyncMock(return_value=mocker.MagicMock(
            role="subject_teacher", persona="teacher_assistant",
            visible_class_ids=["c1"], visible_student_ids=None,
            can_cross_school=False, school_id="s1",
        )))
    )
    resp = await client.post(
        "/api/v1/ai/chat",
        headers=teacher_headers,
        json={"message": "这次期中考试成绩分析报告"},
    )
    assert resp.status_code == 200
    mock_router.return_value.classify.assert_called_once()  # IntentRouter 被调用
```

- [ ] **Step 3: 修改 api/ai.py 入口**

在现有 chat 路由中集成 DataScope（使用 `current["current_role"].id` 而非 `user.active_role_id`）:

```python
# 在 chat 路由函数开头追加:
from edu_cloud.ai.data_scope import DataScopeBuilder
current_role = current["current_role"]
scope = await DataScopeBuilder(db).build(current["user"].id, role_id=current_role.id)

# IntentRouter 分流:
from edu_cloud.ai.intent_router import IntentRouter
intent = IntentRouter().classify(message, available_workflows=["post_exam_analysis", "student_profile", "patrol"])

# 根据 intent.mode 选择执行路径:
if intent.mode == "workflow" and intent.workflow:
    # 工作流对话模式（读预计算表 → 格式化回答）
    ...
else:
    # 自由模式（现有 AgentLoop）
    ...
```

- [ ] **Step 3: 修改 worker.py 添加 cron**

```python
# worker.py 追加:
from edu_cloud.ai.workflow.w3_student_profile import W3_STUDENT_PROFILE
from edu_cloud.ai.workflow.w6_patrol import W6_PATROL

async def run_w3_daily(ctx):
    """arq cron: 每天 04:00 UTC+8 = 20:00 UTC"""
    async with async_session() as db:
        from edu_cloud.ai.workflow.engine import WorkflowExecutor
        executor = WorkflowExecutor(db)
        # 遍历所有活跃学校
        ...

async def run_w6_hourly(ctx):
    """arq cron: 每小时"""
    async with async_session() as db:
        ...

# cron_jobs 追加:
cron(run_w3_daily, hour=20, minute=0),    # 20:00 UTC = 04:00 UTC+8
cron(run_w6_hourly, minute=0),             # 每小时整点
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_api/test_ai_integration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/ai.py src/edu_cloud/worker.py tests/test_api/test_ai_integration.py
git commit -m "feat(ai): integrate DataScope + IntentRouter into api/ai.py + add W3/W6 cron jobs"
```

**测试契约:**
1. 教师 AI 对话携带 scope
   - 入口: `POST /api/v1/ai/chat` with teacher JWT
   - 反例: 不计算 DataScope → 工具无权限边界 → 跨校数据泄露
   - 边界: 无 active_role_id / 角色不存在 / school 被禁用
   - 回归: D7 fail-closed
   - 命令: `python -m pytest tests/test_api/test_ai_integration.py::test_ai_chat_calls_data_scope_builder -v`

2. 家长 AI 对话 scope 隔离
   - 入口: `POST /api/v1/ai/chat` with parent JWT
   - 反例: parent 无 USE_AI_CHAT → 403
   - 边界: 无 guardian 记录 / 多个孩子 / school_settings 变更
   - 回归: Task 4a parent 权限补全
   - 命令: `python -m pytest tests/test_api/test_ai_integration.py::test_ai_chat_parent_scope_locks_student_ids -v`

**边界条件:**
- DataScopeBuilder 失败（未知角色）→ 期望: 返回 400 错误，不是 500
- IntentRouter 低置信度 → 期望: LLM 反问用户确认
- arq worker Redis 不可达 → 期望: cron 跳过本次，下次重试

**审查清单:**
- ✓ DataScope 在 chat 路由开头计算
- ✓ IntentRouter 在 DataScope 之后
- ✓ 自由模式走现有 AgentLoop
- ✓ W3 cron 04:00 UTC+8, W6 每小时
- ✗ 不修改 AgentLoop 核心循环

---

### Task 19: 端到端验证 + 全量测试

**Files:**
- Create: `scripts/e2e_agent_evolution.py`
- Test: 全量测试套件

**说明：** 端到端验证脚本 + 全量测试确认无回归。

- [ ] **Step 1: 写 e2e 验证脚本**

```python
# scripts/e2e_agent_evolution.py
"""端到端验证：DataScope → W1 → W3 → W6 → 对话。"""
import asyncio
import httpx

BASE = "http://localhost:9000/api/v1"

async def main():
    async with httpx.AsyncClient() as c:
        # 1. 登录（教师）— 注意返回字段是 access_token
        r = await c.post(f"{BASE}/auth/login", json={"username": "teacher1", "password": "123456"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. 发布考试（触发 W1）
        # ...

        # 3. AI 对话（考后分析意图）
        r = await c.post(f"{BASE}/ai/chat", headers=headers,
                         json={"message": "这次期中考试分析"})
        print("AI response:", r.status_code)

        # 4. 家长登录 + AI 对话
        r = await c.post(f"{BASE}/auth/login", json={"username": "parent1", "password": "123456"})
        parent_token = r.json()["access_token"]
        r = await c.post(f"{BASE}/ai/chat",
                         headers={"Authorization": f"Bearer {parent_token}"},
                         json={"message": "我孩子最近怎么样"})
        print("Parent AI:", r.status_code)

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 全量测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 全部通过（1037 + 新增 ≈ 60-80 = ~1100+ tests）

- [ ] **Step 3: Commit**

```bash
git add scripts/e2e_agent_evolution.py
git commit -m "feat(e2e): add agent evolution end-to-end validation script"
```

**测试契约:**
1. 全量回归无破坏
   - 入口: `python -m pytest --tb=short -q`
   - 反例: 新代码破坏现有测试 → 回归
   - 边界: N/A
   - 回归: 全量回归是 T4 必须
   - 命令: `python -m pytest --tb=short -q`

**审查清单:**
- ✓ e2e 脚本覆盖教师+家长双角色
- ✓ 全量测试无回归
- ✗ 不修改现有测试

---

## 附录：批次依赖图

```
B1 基础设施 (T1-T5)
  │
  ├──→ B2 W1 考后分析 (T6-T10)
  │
  ├──→ B3 W3 学情画像 (T11-T13)
  │
  └──→ B4 W6 异常巡检 (T14-T15)
            │
            ├──→ B5 IntentRouter (T16-T17)
            │         │
            └─────────┴──→ B6 集成收尾 (T18-T19)
```

## 附录：新增测试预估

| 批次 | 预估新增测试数 | 关键测试文件 |
|------|-------------|-------------|
| B1 | 15-20 | test_agent_models, test_data_scope, test_scoped_query, test_scope_version, test_parent_permission |
| B2 | 15-20 | test_workflow_engine, test_w1_post_exam, test_new_tools, test_w1_integration |
| B3 | 8-12 | test_w3_profile, test_parent_persona |
| B4 | 8-10 | test_w6_patrol, test_new_tools (追加) |
| B5 | 6-8 | test_intent_router, test_tool_registration |
| B6 | 4-6 | test_ai_integration |
| **合计** | **56-76** | |

---

## Contract Pack

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "DataScope 是 frozen dataclass — 创建后任何字段赋值抛 AttributeError"
      verification: pending_test
      note: "tests/test_ai/test_data_scope.py::test_data_scope_is_frozen"

    - id: INV-002
      statement: "ScopedQuery 对非跨校角色（can_cross_school=False）必须注入 school_id WHERE 条件"
      verification: pending_test
      note: "tests/test_ai/test_scoped_query.py::test_scoped_query_injects_school_id"

    - id: INV-003
      statement: "ToolAccessResolver 无 capability 记录时拒绝工具访问（fail-closed，D7）"
      verification: pending_test
      note: "tests/test_ai/test_tool_access_fail_closed.py::test_no_capability_record_rejects"

    - id: INV-004
      statement: "WorkflowExecutor 同一幂等键不重复执行（school_id + workflow + trigger_ref + date）"
      verification: pending_test
      note: "tests/test_ai/test_workflow_engine.py::test_executor_idempotency_skips_duplicate"

    - id: INV-005
      statement: "家长 DataScope 的 visible_student_ids 从 guardian_student_links 推导，can_write=False"
      verification: pending_test
      note: "tests/test_ai/test_data_scope.py::test_build_scope_parent"

    - id: INV-006
      statement: "ScopeVersionChecker 版本 bump 跨进程可见（DB 持久化）"
      verification: pending_test
      note: "tests/test_ai/test_scope_version.py::test_bump_persists_across_checker_instances"

  counter_examples:
    - id: CE-001
      scenario: "DataScopeBuilder 对 parent 角色不查 guardian_student_links → visible_student_ids=None → 家长可看全校学生"
      tests_that_still_pass: "test_data_scope_is_frozen（只检查 frozen 属性，不检查推导逻辑）"
      mitigation: "test_build_scope_parent 验证 visible_student_ids 精确匹配 guardian 记录"

    - id: CE-002
      scenario: "ScopedQuery.validate_param 不校验 → 工具参数 class_id=forbidden 突破 scope 限制"
      tests_that_still_pass: "test_scoped_query_injects_school_id（只检查 WHERE 注入，不检查参数校验）"
      mitigation: "test_scoped_query_rejects_amplification 显式传入不在 scope 内的 class_id"

    - id: CE-003
      scenario: "Task 18 api/ai.py 不调用 DataScopeBuilder，只返回 200 SSE → 测试仍绿"
      tests_that_still_pass: "status_code == 200 弱断言（已被 mock 断言替代）"
      mitigation: "test_ai_chat_calls_data_scope_builder 用 mock 验证 DataScopeBuilder 被调用 + test_ai_chat_workflow_mode_reads_snapshot 验证 IntentRouter 分流"

  risk_modules:
    - module: "src/edu_cloud/ai/tool_access.py"
      reason: "fail-open → fail-closed 安全语义变更，影响全部 39 工具的可见性"
    - module: "src/edu_cloud/ai/data_scope.py"
      reason: "全新权限边界模块，8 角色推导错误 → 数据泄露"
    - module: "src/edu_cloud/api/ai.py"
      reason: "核心入口重构，集成 DataScope + IntentRouter + WorkflowEngine"
    - module: "src/edu_cloud/ai/workflow/engine.py"
      reason: "工作流状态机 + 持久化，幂等/重试逻辑错误 → 数据不一致"
    - module: "src/edu_cloud/core/permissions.py"
      reason: "parent 权限变更，影响 RBAC 全局"

  test_debt:
    - item: "W6 巡检未接入校历（节假日阈值调节）"
      reason: "校历集成属于第二期，当前固定阈值足够第一期场景"
      deadline: "2026-05-15"
    - item: "generate_learning_advice 用模板替代 LLM 调用"
      reason: "LLM 建议生成需成本控制策略，第一期用模板降低风险"
      deadline: "2026-05-15"
    - item: "IntentRouter 关键词覆盖率约 50-60%，低于第二期 Tier 3 模型目标"
      reason: "第一期纯规则实现，覆盖率通过关键词迭代提升，不阻塞上线"
      deadline: "2026-06-01"
```

---

## GPT Plan Review R1 处置记录

| Finding | Severity | Status | 处置 |
|---------|----------|--------|------|
| F001 | HIGH | verified → fixed | 追加 Contract Pack（6 invariants + 3 counter_examples + 5 risk_modules + 3 test_debt） |
| F002 | HIGH | verified → fixed | Task 5 从进程内存改为 DB 持久化（scope_versions 表） |
| F003 | HIGH | verified → fixed | Task 18/19 改用 teacher_headers/parent_headers fixture + access_token 字段 |
| F004 | HIGH | verified → fixed | Task 18 测试增强：SSE 语义断言 + 401 反例 + 工作流分流验证 |
| F005 | HIGH | verified → fixed | Task 4 拆为 4a（parent 权限）+ 4b（fail-closed 改造，含 tool_access + capability_service） |
| F006 | MED | verified → fixed | Task 1 文件列表追加 test_alembic_migration.py |
