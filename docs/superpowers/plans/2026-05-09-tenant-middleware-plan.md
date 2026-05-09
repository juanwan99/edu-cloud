# 租户中间件实施计划（Phase 3）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入 TenantContext typed dependency 作为租户隔离的统一入口，修复剩余安全缺陷（P1-14 / H4 / P2-1/3/4），建立 pytest 静态治理防止未来遗漏。

**Architecture:** TenantContext frozen dataclass 封装 school_id + visible scopes，通过 FastAPI Depends 注入。保留 get_school_id 作为内部实现。ScopeFilter 修复空列表 fail-open。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, pytest

---

## File Structure

| 文件 | 职责 | 操作 |
|------|------|------|
| `src/edu_cloud/core/tenant.py` | TenantContext + scope helpers | **Modify** |
| `src/edu_cloud/core/scope_filter.py` | 修复空列表 fail-open | **Modify** |
| `src/edu_cloud/modules/marking/importer.py` | P1-14 school_id 修复 | **Modify** |
| `src/edu_cloud/modules/scan/pipeline_router.py` | H4 progress/stop 隔离 | **Modify** |
| `src/edu_cloud/modules/scan/pipeline_service.py` | H4 pipeline_school_id | **Modify** |
| `src/edu_cloud/api/dashboard.py` | P2-1 subject_codes 过滤 | **Modify** |
| `src/edu_cloud/modules/exam/workspace_router.py` | P2-3 subject scope | **Modify** |
| `src/edu_cloud/services/workspace_service.py` | P2-3 subject 过滤实现 | **Modify** |
| `src/edu_cloud/modules/analytics/analytics_report_router.py` | P2-4 传递 visible_subject_codes | **Modify** |
| `src/edu_cloud/modules/analytics/grade_service.py` | P2-4 接收 subject 过滤 | **Modify** |
| `tests/test_api/test_tenant_context.py` | TenantContext 单测 | **Create** |
| `tests/test_api/test_marking_import_isolation.py` | P1-14 回归测试 | **Create** |
| `tests/test_api/test_pipeline_state_isolation.py` | H4 隔离测试 | **Create** |
| `tests/test_api/test_dashboard_subject_scope.py` | P2-1 测试 | **Create** |
| `tests/governance/test_tenant_static.py` | 静态治理规则 | **Create** |

---

## semantic_regression (ORC, codex-review 自动提取):

> R2-F003 修复：ORC 不变量已纳入 contract_pack.invariants（INV-001~004）。此段保留作为 codex-review 提取锚点，引用 contract_pack 中的对应项。

ORC-P3-001: admin school_id=None 不加 WHERE → contract_pack.INV-001
ORC-P3-002: 非 admin 缺 school_id raise 403 → contract_pack.INV-001 隐含
ORC-P3-003: visible_subject_codes=() deny-all → contract_pack.INV-002
ORC-P3-004: visible_subject_codes=None 不加 WHERE → contract_pack.INV-002 隐含
ORC-P3-005: import 外校 exam_id 返回错误 → contract_pack.CE-002 mitigation
ORC-P3-006: pipeline stop 拒绝非 owner → test_pipeline_state_isolation

---

### Task 1: 热修 P1-14 — marking importer school_id 隔离

**Tier:** T2 (行为变更, 安全修复)

**Files:**
- Modify: `src/edu_cloud/modules/marking/importer.py:46,52-54,66-69`
- Test: `tests/test_api/test_marking_import_isolation.py`

**测试契约:**
- 入口: `POST /api/v1/marking/import` (HTTP 入口级)
- 反例: 如果漏加 school_id WHERE，A 校用户传 B 校 exam_id 仍返回 200 并写入跨校数据
- 边界: (1) 外校 exam_id → 400/404 (2) 本校 exam_id 空文件夹 → 200 零导入 (3) admin 用户 → 仍需 exam 归属校验
- 回归: 现有 test_marking.py 不受影响
- 命令: `.venv/bin/python -m pytest tests/test_api/test_marking_import_isolation.py -v`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_marking_import_isolation.py
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def two_schools(db):
    s1 = School(name="学校A", code="SA", district="D", api_key_hash="x")
    s2 = School(name="学校B", code="SB", district="D", api_key_hash="x")
    db.add_all([s1, s2])
    await db.flush()

    exam_b = Exam(name="B校考试", school_id=s2.id, status="draft")
    db.add(exam_b)
    await db.flush()

    user_a = User(username="importer_a", display_name="A")
    user_a.set_password("test123")
    db.add(user_a)
    await db.flush()
    db.add(UserRole(user_id=user_a.id, role="academic_director",
                    school_id=s1.id, is_primary=True))
    await db.commit()

    token_a = create_access_token({
        "sub": user_a.id, "role": "academic_director",
        "school_id": s1.id,
    })
    return {
        "school_a_id": s1.id, "school_b_id": s2.id,
        "exam_b_id": exam_b.id,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
    }


@pytest.mark.asyncio
async def test_import_rejects_other_school_exam(client, two_schools, tmp_path):
    """A校用户用 B校 exam_id 调用 import → 400/404"""
    folder = tmp_path / "subjects"
    folder.mkdir()
    resp = await client.post("/api/v1/marking/import", json={
        "exam_id": two_schools["exam_b_id"],
        "folder_path": str(folder),
    }, headers=two_schools["headers_a"])
    assert resp.status_code in (400, 404)
    assert "不存在" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_import_accepts_own_school_exam(client, two_schools, db, tmp_path):
    """A校用户用自己学校的 exam_id → 正常（可能 400 因文件夹结构，但不是权限拒绝）"""
    own_exam = Exam(name="A校考试", school_id=two_schools["school_a_id"], status="draft")
    db.add(own_exam)
    await db.commit()

    folder = tmp_path / "empty_subjects"
    folder.mkdir()
    resp = await client.post("/api/v1/marking/import", json={
        "exam_id": own_exam.id,
        "folder_path": str(folder),
    }, headers=two_schools["headers_a"])
    assert resp.status_code == 200
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_api/test_marking_import_isolation.py -v`
Expected: `test_import_rejects_other_school_exam` FAIL（当前返回 200 而非 400/404）

- [ ] **Step 3: 修复 importer.py — 3 处查询加 school_id**

```python
# importer.py:46 — Exam 查询
exam = (await db.execute(
    select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
)).scalar_one_or_none()

# importer.py:52-54 — Subject 预加载
for s in (await db.execute(
    select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
)).scalars().all():

# importer.py:66-69 — StudentAnswer 预加载
for row in (await db.execute(
    select(StudentAnswer.student_id, StudentAnswer.question_id).where(
        StudentAnswer.exam_id == exam_id, StudentAnswer.school_id == school_id,
    )
)).all():
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_marking_import_isolation.py -v`
Expected: 2 PASS

- [ ] **Step 5: 提交**

```bash
git add src/edu_cloud/modules/marking/importer.py tests/test_api/test_marking_import_isolation.py
git commit -m "fix: P1-14 marking importer add school_id isolation to Exam/Subject/Answer queries"
```

---

### Task 2: 热修 H4 — pipeline progress/stop 加 school_id 验证

**Tier:** T2 (行为变更, 安全修复)

**Files:**
- Modify: `src/edu_cloud/modules/scan/pipeline_service.py:30-53,61`
- Modify: `src/edu_cloud/modules/scan/pipeline_router.py:760-772`
- Test: `tests/test_api/test_pipeline_state_isolation.py`

**测试契约:**
- 入口: `GET /progress` + `POST /stop` (HTTP 入口级)
- 反例: 如果不记录 pipeline_school_id，B 校用户可以 stop A 校的 pipeline 且 progress 返回 A 校数据
- 边界: (1) B 校 stop A 校 pipeline → 403 (2) A 校 stop 自己 → 200 (3) B 校查 progress 时 A 校在跑 → idle (4) admin 查 progress → 返回全局
- 回归: 现有 pipeline 测试不受影响
- 命令: `.venv/bin/python -m pytest tests/test_api/test_pipeline_state_isolation.py -v`

**注意:** 大部分测试直接设置私有全局状态（_running/_pipeline_school_id），因入口级 start 需要完整扫描数据。已记入 test_debt，deadline 2026-06-15。R2-F002 修复：增加一个经 `enqueue_pipeline` 路径的测试，验证 school_id 被正确记录到 `_pipeline_school_id`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_pipeline_state_isolation.py
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def pipeline_schools(db):
    s1 = School(name="扫描校A", code="PA", district="D", api_key_hash="x")
    s2 = School(name="扫描校B", code="PB", district="D", api_key_hash="x")
    db.add_all([s1, s2])
    await db.flush()

    users = {}
    for label, school in [("a", s1), ("b", s2)]:
        u = User(username=f"pipe_{label}", display_name=label.upper())
        u.set_password("test123")
        db.add(u)
        await db.flush()
        db.add(UserRole(user_id=u.id, role="academic_director",
                        school_id=school.id, is_primary=True))
        token = create_access_token({
            "sub": u.id, "role": "academic_director", "school_id": school.id,
        })
        users[label] = {"headers": {"Authorization": f"Bearer {token}"}, "school_id": school.id}
    await db.commit()
    return users


@pytest.mark.asyncio
async def test_stop_rejects_other_school(client, pipeline_schools):
    """B校用户不能停止 A校的 pipeline。"""
    from edu_cloud.modules.scan import pipeline_service
    pipeline_service._running = True
    pipeline_service._pipeline_school_id = pipeline_schools["a"]["school_id"]
    try:
        resp = await client.post(
            "/api/v1/scan/pipeline/stop",
            headers=pipeline_schools["b"]["headers"],
        )
        assert resp.status_code == 403
    finally:
        pipeline_service._running = False
        pipeline_service._pipeline_school_id = None


@pytest.mark.asyncio
async def test_progress_returns_empty_for_other_school(client, pipeline_schools):
    """B校用户查看 progress 时，如果运行的是 A校的 pipeline，返回 idle。"""
    from edu_cloud.modules.scan import pipeline_service
    pipeline_service._running = True
    pipeline_service._pipeline_school_id = pipeline_schools["a"]["school_id"]
    try:
        resp = await client.get(
            "/api/v1/scan/pipeline/progress",
            headers=pipeline_schools["b"]["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"
    finally:
        pipeline_service._running = False
        pipeline_service._pipeline_school_id = None


@pytest.mark.asyncio
async def test_stop_allows_own_school(client, pipeline_schools):
    """A校用户可以停止自己学校的 pipeline。"""
    from edu_cloud.modules.scan import pipeline_service
    pipeline_service._running = True
    pipeline_service._pipeline_school_id = pipeline_schools["a"]["school_id"]
    try:
        resp = await client.post(
            "/api/v1/scan/pipeline/stop",
            headers=pipeline_schools["a"]["headers"],
        )
        assert resp.status_code == 200
    finally:
        pipeline_service._running = False
        pipeline_service._pipeline_school_id = None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_api/test_pipeline_state_isolation.py -v`
Expected: FAIL（_pipeline_school_id 属性不存在 + 无 school 检查）

- [ ] **Step 3: 修改 pipeline_service.py — 加 _pipeline_school_id 全局变量**

在 `pipeline_service.py:33` 后加：
```python
_pipeline_school_id: str | None = None  # 当前运行 pipeline 的学校
```

在 `enqueue_pipeline()` / `run_queue()` 中设置 `_pipeline_school_id = school_id`。
在 `request_stop()` 和队列完成后清除为 `None`。

新增两个函数：
```python
def get_pipeline_school_id() -> str | None:
    return _pipeline_school_id

def get_progress_for_school(school_id: str | None) -> dict:
    if school_id and _pipeline_school_id and _pipeline_school_id != school_id:
        return {"status": "idle", "total": 0, "processed": 0, "failed": 0,
                "current_file": "", "warnings": [], "barcode_failed": 0,
                "barcode_failed_files": [], "current_subject_id": "", "queue_remaining": 0}
    return get_progress()
```

- [ ] **Step 4: 修改 pipeline_router.py — progress/stop 加 school 检查**

```python
# pipeline_router.py:760-763
@router.get("/progress")
async def get_progress(current: dict = Depends(require_permission(Permission.MANAGE_GRADING))):
    school_id = get_school_id(current)
    return pipeline_service.get_progress_for_school(school_id)


# pipeline_router.py:766-772
@router.post("/stop")
async def stop_pipeline(current: dict = Depends(require_permission(Permission.MANAGE_GRADING))):
    school_id = get_school_id(current)
    if not pipeline_service.is_running():
        raise HTTPException(400, "流水线未在运行")
    owner = pipeline_service.get_pipeline_school_id()
    if school_id and owner and owner != school_id:
        raise HTTPException(403, "无权停止其他学校的流水线")
    pipeline_service.request_stop()
    return {"status": "stopping"}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_pipeline_state_isolation.py -v`
Expected: 4 PASS（含 1 个 enqueue 入口级测试）

注意：第 4 个测试（R3-F003 修复）验证 enqueue_pipeline 正确记录 school_id：
```python
@pytest.mark.asyncio
async def test_enqueue_records_school_id(pipeline_schools):
    """enqueue_pipeline 应将 school_id 记录到 _pipeline_school_id。"""
    from edu_cloud.modules.scan import pipeline_service
    pipeline_service._pipeline_school_id = None
    pipeline_service.enqueue_pipeline(
        school_id=pipeline_schools["a"]["school_id"],
        subject_id="test", image_dir="/tmp", side="A",
        save_answer_fn=None, save_objective_fn=None,
    )
    assert pipeline_service._pipeline_school_id == pipeline_schools["a"]["school_id"]
    pipeline_service._queue.clear()
    pipeline_service._pipeline_school_id = None
```

- [ ] **Step 6: 提交**

```bash
git add src/edu_cloud/modules/scan/pipeline_service.py src/edu_cloud/modules/scan/pipeline_router.py tests/test_api/test_pipeline_state_isolation.py
git commit -m "fix: H4 pipeline progress/stop add school_id isolation"
```

---

### Task 3: TenantContext + scope helpers + ScopeFilter 修复

**Tier:** T2 (架构增强, 安全修复)

**Files:**
- Modify: `src/edu_cloud/core/tenant.py` — TenantContext dataclass（纯数据，无 FastAPI 依赖）
- Modify: `src/edu_cloud/api/deps.py` — get_tenant_context dependency（F008 修复: 避免 core→api 反向依赖）
- Modify: `src/edu_cloud/core/scope_filter.py:19,23,25`
- Test: `tests/test_api/test_tenant_context.py`

**测试契约:**
- 入口: TenantContext 构造 + apply_* 方法单元测试 + get_tenant_context(api/deps.py) wiring 测试 + ScopeFilter 回归
- 反例: 如果 apply_subject_scope 对 () 不生成 deny-all，受限角色看到全校数据
- 边界: (1) school_id=None (admin) (2) visible_subject_codes=None (不限制) (3) visible_subject_codes=() (deny-all) (4) visible_subject_codes=("math",) (正常过滤)
- 回归: 现有 tests/test_core/test_tenant.py 5 测试不受影响
- 命令: `.venv/bin/python -m pytest tests/test_api/test_tenant_context.py tests/test_core/test_tenant.py -v`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_tenant_context.py
import pytest
from sqlalchemy import select, column
from edu_cloud.core.tenant import TenantContext


def _mock_ctx(school_id="s1", subject_codes=None, class_ids=None):
    return TenantContext(
        user_id="u1", role_id="r1", role_name="subject_teacher",
        school_id=school_id,
        visible_class_ids=class_ids,
        visible_subject_codes=subject_codes,
    )


def test_require_school_returns_id():
    ctx = _mock_ctx(school_id="school-1")
    assert ctx.require_school() == "school-1"


def test_require_school_raises_for_admin():
    ctx = _mock_ctx(school_id=None)
    with pytest.raises(Exception) as exc_info:
        ctx.require_school()
    assert exc_info.value.status_code == 403


def test_apply_subject_scope_none_no_filter():
    """None = 不限制，不添加 WHERE。"""
    ctx = _mock_ctx(subject_codes=None)
    from edu_cloud.modules.exam.models import Subject
    stmt = select(Subject)
    result = ctx.apply_subject_scope(stmt, Subject.code)
    compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
    assert "IN" not in compiled


def test_apply_subject_scope_empty_tuple_deny_all():
    """() = deny-all，添加 WHERE false()。"""
    ctx = _mock_ctx(subject_codes=())
    from edu_cloud.modules.exam.models import Subject
    stmt = select(Subject)
    result = ctx.apply_subject_scope(stmt, Subject.code)
    compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
    # 空 IN 或 false() — 不应该缺失过滤
    assert "1 != 1" in compiled or "false" in compiled.lower() or "IN (NULL)" in compiled


def test_apply_subject_scope_with_values():
    """有值 = IN 过滤。"""
    ctx = _mock_ctx(subject_codes=("math", "chinese"))
    from edu_cloud.modules.exam.models import Subject
    stmt = select(Subject)
    result = ctx.apply_subject_scope(stmt, Subject.code)
    compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
    assert "IN" in compiled


def test_get_tenant_context_admin(client, db):
    """get_tenant_context 为 platform_admin 构造 school_id=None, visible=None。"""
    from edu_cloud.api.deps import get_tenant_context
    from unittest.mock import MagicMock
    role = MagicMock()
    role.role = "platform_admin"
    role.school_id = None
    role.id = "role-1"
    role.class_ids = None
    role.subject_codes = None
    user = MagicMock()
    user.id = "admin-1"
    current = {"user": user, "current_role": role}
    import asyncio
    ctx = asyncio.get_event_loop().run_until_complete(get_tenant_context(current))
    assert ctx.school_id is None
    assert ctx.visible_class_ids is None
    assert ctx.visible_subject_codes is None


def test_get_tenant_context_teacher(client, db):
    """get_tenant_context 为 subject_teacher 构造 school_id 有值, subject_codes 是 tuple。"""
    from edu_cloud.api.deps import get_tenant_context
    from unittest.mock import MagicMock
    role = MagicMock()
    role.role = "subject_teacher"
    role.school_id = "school-1"
    role.id = "role-2"
    role.class_ids = ["c1", "c2"]
    role.subject_codes = ["math"]
    user = MagicMock()
    user.id = "teacher-1"
    current = {"user": user, "current_role": role}
    import asyncio
    ctx = asyncio.get_event_loop().run_until_complete(get_tenant_context(current))
    assert ctx.school_id == "school-1"
    assert ctx.visible_class_ids == ("c1", "c2")
    assert ctx.visible_subject_codes == ("math",)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_api/test_tenant_context.py -v`
Expected: FAIL（TenantContext 不存在）

- [ ] **Step 3: 实现 TenantContext — core/tenant.py（纯数据类，零 api 层依赖）**

在 `core/tenant.py` 文件顶部 import 区追加 `from dataclasses import dataclass` 和 `from sqlalchemy import false as sa_false`，然后在文件末尾追加（R3-F001 修复：无 from_current 类方法，无 api.permissions 导入，core 层零反向依赖；R3-F002 修复：不在追加块中写 `from __future__`）：

```python
@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: str
    role_id: str
    role_name: str
    school_id: str | None
    visible_class_ids: tuple[str, ...] | None
    visible_subject_codes: tuple[str, ...] | None

    def require_school(self) -> str:
        if self.school_id is None:
            raise HTTPException(403, "School scope required")
        return self.school_id

    def apply_school(self, stmt, model):
        if self.school_id is not None:
            stmt = stmt.where(getattr(model, "school_id") == self.school_id)
        return stmt

    def apply_subject_scope(self, stmt, column):
        if self.visible_subject_codes is None:
            return stmt
        if len(self.visible_subject_codes) == 0:
            return stmt.where(sa_false())
        return stmt.where(column.in_(self.visible_subject_codes))

    def apply_class_scope(self, stmt, column):
        if self.visible_class_ids is None:
            return stmt
        if len(self.visible_class_ids) == 0:
            return stmt.where(sa_false())
        return stmt.where(column.in_(self.visible_class_ids))
```

- [ ] **Step 3b: 实现 get_tenant_context — api/deps.py（构造入口，R3-F001 修复）**

在 `src/edu_cloud/api/deps.py` 末尾追加（api 层负责调用 permissions helpers，然后以参数传入构造纯数据 TenantContext）：

```python
from edu_cloud.core.tenant import TenantContext, get_school_id
from edu_cloud.api.permissions import get_visible_class_ids, get_visible_subject_codes


def _to_tuple(lst: list | None) -> tuple | None:
    return None if lst is None else tuple(lst)


async def get_tenant_context(
    current: dict = Depends(get_current_user),
) -> TenantContext:
    role = current["current_role"]
    return TenantContext(
        user_id=str(current["user"].id),
        role_id=str(role.id),
        role_name=role.role,
        school_id=get_school_id(current),
        visible_class_ids=_to_tuple(get_visible_class_ids(role)),
        visible_subject_codes=_to_tuple(get_visible_subject_codes(role)),
    )
```

- [ ] **Step 4: 修复 ScopeFilter 空列表 fail-open**

`scope_filter.py` 三处 `if self.X` 改为 `if self.X is not None`：

```python
# scope_filter.py:19 — 已正确（school_id 是 str，空字符串 falsy 合理）
# scope_filter.py:21 — 改为:
if self.class_ids is not None and class_col:
# scope_filter.py:23 — 改为:
if self.grade_ids is not None and grade_col:
# scope_filter.py:25 — 改为:
if self.subject_codes is not None and subject_col:
```

- [ ] **Step 5: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_tenant_context.py -v`
Expected: 7 PASS

- [ ] **Step 6: 回归测试**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: 无新增失败

- [ ] **Step 7: 提交**

```bash
git add src/edu_cloud/core/tenant.py src/edu_cloud/api/deps.py src/edu_cloud/core/scope_filter.py tests/test_api/test_tenant_context.py
git commit -m "feat: add TenantContext typed dependency + fix ScopeFilter empty-list fail-open"
```

---

### Task 4: P2-1 — Dashboard subject_codes 过滤

**Tier:** T2 (行为变更, L2 scope)

**Files:**
- Modify: `src/edu_cloud/api/dashboard.py:8,19-20,44-48,59-75`
- Test: `tests/test_api/test_dashboard_subject_scope.py`

**测试契约:**
- 入口: `GET /api/v1/dashboard/summary` (HTTP 入口级)
- 反例: 如果不加 subject JOIN，数学教师看到 pending_grading=2（含语文），而非 1
- 边界: (1) subject_teacher math → pending_grading=1 (2) academic_director → pending_grading=2 (全科) (3) subject_teacher 无任教科目 → pending_grading=0
- 回归: 现有 dashboard 测试不受影响
- 命令: `.venv/bin/python -m pytest tests/test_api/test_dashboard_subject_scope.py -v`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_dashboard_subject_scope.py
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.modules.grading.models import GradingTask
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def dashboard_scope_data(db):
    school = School(name="Dashboard测试校", code="DS", district="D", api_key_hash="x")
    db.add(school)
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id, status="published")
    db.add(exam)
    await db.flush()

    math_subj = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    chinese_subj = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add_all([math_subj, chinese_subj])
    await db.flush()

    t1 = GradingTask(school_id=school.id, subject_id=math_subj.id, status="pending")
    t2 = GradingTask(school_id=school.id, subject_id=chinese_subj.id, status="pending")
    db.add_all([t1, t2])
    await db.flush()

    math_teacher = User(username="math_t_ds", display_name="数学老师")
    math_teacher.set_password("test123")
    db.add(math_teacher)
    await db.flush()
    db.add(UserRole(user_id=math_teacher.id, role="subject_teacher",
                    school_id=school.id, is_primary=True,
                    subject_codes=["math"], class_ids=["c1"]))
    await db.commit()

    token = create_access_token({
        "sub": math_teacher.id, "role": "subject_teacher",
        "school_id": school.id,
    })
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "school_id": school.id,
        "math_subject_id": math_subj.id,
        "chinese_subject_id": chinese_subj.id,
    }


@pytest.mark.asyncio
async def test_dashboard_pending_grading_respects_subject_scope(client, dashboard_scope_data):
    """数学教师只应看到数学科目的待阅卷数=1，不包含语文的 pending。"""
    resp = await client.get("/api/v1/dashboard/summary",
                            headers=dashboard_scope_data["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_grading"] == 1, f"Expected 1 (math only), got {data['pending_grading']}"
    assert data["pending_subjects"] == 1, f"Expected 1 subject, got {data['pending_subjects']}"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_api/test_dashboard_subject_scope.py -v`
Expected: FAIL（返回 2 而非 1）

- [ ] **Step 3: 修改 dashboard.py — 加 subject_codes 过滤**

```python
# dashboard.py — 导入行追加
from edu_cloud.api.permissions import get_visible_class_ids, get_visible_subject_codes

# 在 get_summary 函数开头追加
visible_subjects = get_visible_subject_codes(role)

# 考试数查询（line 44-48）追加 — 通过 JOIN Subject 过滤
# 注：考试本身没有 subject_code，但"与我相关的考试"可通过包含我的科目判断
# Dashboard 的考试数是全校统计，subject 过滤不适用于 Exam.count
# 只需要对 pending_grading 和 pending_subjects 加 subject scope

# pending_grading 查询（line 59-66）追加
if visible_subjects is not None:
    from edu_cloud.modules.exam.models import Subject
    q = q.join(Subject, GradingTask.subject_id == Subject.id)
    if len(visible_subjects) == 0:
        q = q.where(sqlalchemy.false())
    else:
        q = q.where(Subject.code.in_(visible_subjects))

# pending_subjects 查询（line 68-75）— 同上
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_dashboard_subject_scope.py -v`
Expected: PASS

- [ ] **Step 5: 回归测试**

Run: `.venv/bin/python -m pytest tests/test_api/ --tb=short -q`
Expected: 无新增失败

- [ ] **Step 6: 提交**

```bash
git add src/edu_cloud/api/dashboard.py tests/test_api/test_dashboard_subject_scope.py
git commit -m "fix: P2-1 dashboard pending grading/subjects respect visible_subject_codes"
```

---

### Task 5: P2-3 — Workspace exam dashboard 加 subject 过滤

**Tier:** T2 (行为变更, L2 scope)

**Files:**
- Modify: `src/edu_cloud/modules/exam/workspace_router.py:14-27,30-44`
- Modify: `src/edu_cloud/services/workspace_service.py`
- Test: 在 `tests/test_api/test_dashboard_subject_scope.py` 追加

**测试契约:**
- 入口: `GET /api/v1/workspace/context` + `GET /api/v1/workspace/exams/{id}/dashboard` (HTTP 入口级)
- 反例: 如果不传 subject_codes，数学教师可在 context 中看到语文考试统计
- 边界: (1) subject_teacher math → 只含 math 科目 (2) academic_director → 全科 (3) 无 scope → 全校
- 回归: 现有 workspace 测试不受影响
- 命令: `.venv/bin/python -m pytest tests/test_api/test_dashboard_subject_scope.py -v`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 test_dashboard_subject_scope.py

@pytest.mark.asyncio
async def test_workspace_context_excludes_other_subjects(client, dashboard_scope_data):
    """数学教师的工作台上下文不应包含语文科目数据。"""
    resp = await client.get("/api/v1/workspace/context",
                            headers=dashboard_scope_data["headers"])
    assert resp.status_code == 200
    data = resp.json()
    if "exams" in data:
        for exam in data.get("exams", []):
            for subj in exam.get("subjects", []):
                assert subj.get("code") != "chinese", "数学教师不应看到语文科目"
```

- [ ] **Step 2: 修改 workspace_router.py — 传递 subject_codes**

```python
from edu_cloud.api.permissions import get_visible_subject_codes

scope = {
    "class_ids": getattr(role, "class_ids", None),
    "grade_ids": getattr(role, "grade_ids", None),
    "subject_codes": get_visible_subject_codes(role),
}
```

- [ ] **Step 3: 修改 workspace_service.py — 使用 subject_codes 过滤**

在 `get_context_tree` 和 `get_exam_dashboard` 中接收 `scope["subject_codes"]`，应用到 Subject 查询。

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_api/test_dashboard_subject_scope.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/edu_cloud/modules/exam/workspace_router.py src/edu_cloud/services/workspace_service.py tests/test_api/test_dashboard_subject_scope.py
git commit -m "fix: P2-3 workspace dashboard pass visible_subject_codes to service"
```

---

### Task 6: P2-4 — Analytics grade overview 传 visible_subject_codes

**Tier:** T2 (行为变更, L2 scope)

**Files:**
- Modify: `src/edu_cloud/modules/analytics/analytics_report_router.py:586-588`
- Modify: `src/edu_cloud/modules/analytics/grade_service.py:81-82`

**测试契约:**
- 入口: `GET /api/v1/analytics/grade/{grade_id}/overview` (HTTP 入口级)
- 反例: 如果不传 visible_subject_codes，数学教师看到全科聚合数据（含语文均分等）
- 边界: (1) subject_teacher math + 2 科考试 → subjects 只含 math (2) academic_director → subjects 含全科 (3) 空 grade → 404
- 回归: 现有 analytics 测试不受影响
- 命令: `.venv/bin/python -m pytest tests/test_api/test_dashboard_subject_scope.py -v`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_dashboard_subject_scope.py 追加

@pytest.mark.asyncio
async def test_grade_overview_excludes_other_subjects(client, dashboard_scope_data, db):
    """数学教师查看年级概览时，subjects 列表不应包含语文。"""
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.modules.exam.models import Exam, Subject

    school_id = dashboard_scope_data["school_id"]
    cls = ClassGroup(name="初一1班", school_id=school_id, grade_id="g1")
    db.add(cls)
    await db.flush()

    exam = Exam(name="月考", school_id=school_id, status="published")
    db.add(exam)
    await db.flush()
    db.add_all([
        Subject(exam_id=exam.id, name="数学", code="math", school_id=school_id),
        Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school_id),
    ])
    await db.commit()

    resp = await client.get(
        f"/api/v1/analytics/grade/g1/overview?exam_id={exam.id}",
        headers=dashboard_scope_data["headers"],
    )
    if resp.status_code == 200:
        data = resp.json()
        subject_codes = [s["subject_code"] for s in data.get("subjects", [])]
        assert "chinese" not in subject_codes, "数学教师不应看到语文科目数据"
```

- [ ] **Step 2: 修改 analytics_report_router.py:586-588**

```python
return await get_grade_overview(
    db, school_id=role.school_id, grade_id=grade_id, exam_id=exam_id,
    visible_subject_codes=get_visible_subject_codes(role),
)
```

- [ ] **Step 3: 修改 grade_service.py — 接收并应用 subject 过滤**

```python
async def get_grade_overview(
    db: AsyncSession, school_id: str, grade_id: str, exam_id: str,
    visible_subject_codes: list[str] | None = None,
) -> dict:
    ...
    subjects = await _get_subjects(db, exam_id, school_id)
    if visible_subject_codes is not None:
        subjects = [s for s in subjects if s.code in visible_subject_codes]
    ...
```

- [ ] **Step 4: 运行测试确认通过 + 回归**

Run: `.venv/bin/python -m pytest tests/test_api/test_dashboard_subject_scope.py tests/test_api/ --tb=short -q`

- [ ] **Step 5: 提交**

```bash
git add src/edu_cloud/modules/analytics/analytics_report_router.py src/edu_cloud/modules/analytics/grade_service.py tests/test_api/test_dashboard_subject_scope.py
git commit -m "fix: P2-4 grade overview pass visible_subject_codes for L2 scope filtering"
```

---

### Task 7: pytest 静态治理规则

**Tier:** T2 (治理基础设施)

**Files:**
- Create: `tests/governance/__init__.py`
- Create: `tests/governance/test_tenant_static.py`

**测试契约:**
- 入口: pytest 执行治理测试
- 反例: 如果 allowlist 包含本批触碰的文件，治理测试不会发现它们的旧模式
- 边界: (1) 新文件用 role.school_id → FAIL (2) 新文件用 get_school_id → PASS (3) allowlist 内旧文件 → 跳过
- 回归: 无（新测试）
- 命令: `.venv/bin/python -m pytest tests/governance/ -v`

- [ ] **Step 1: 创建治理测试**

```python
# tests/governance/test_tenant_static.py
"""静态治理规则：防止新代码引入租户隔离漏洞。"""
import ast
import os
from pathlib import Path

ROUTER_DIRS = [
    Path("src/edu_cloud/modules"),
    Path("src/edu_cloud/api"),
]

# F007 修复: 本批触碰的 4 个文件已从 allowlist 移除，要求迁移到 get_school_id/TenantContext
ALLOWLIST_RAW_SCHOOL_ID = {
    "src/edu_cloud/api/auth.py",
    "src/edu_cloud/api/impersonate.py",
    "src/edu_cloud/api/compat_router.py",
    "src/edu_cloud/api/ai.py",
    "src/edu_cloud/api/notifications_api.py",
    "src/edu_cloud/modules/academic/router.py",
    "src/edu_cloud/modules/analytics/router.py",
    "src/edu_cloud/modules/bank/router.py",
    "src/edu_cloud/modules/calendar/router.py",
    "src/edu_cloud/modules/card/card_export_router.py",
    "src/edu_cloud/modules/card/card_template_router.py",
    "src/edu_cloud/modules/card/router.py",
    "src/edu_cloud/modules/conduct/admin_router.py",
    "src/edu_cloud/modules/exam/llm_config_router.py",
    "src/edu_cloud/modules/exam/router.py",
    "src/edu_cloud/modules/grading/assignment_router.py",
    "src/edu_cloud/modules/grading/grading_review_router.py",
    "src/edu_cloud/modules/grading/quality_router.py",
    "src/edu_cloud/modules/grading/router.py",
    "src/edu_cloud/modules/knowledge_tree/router.py",
    "src/edu_cloud/modules/marking/router.py",
    "src/edu_cloud/modules/menu/router.py",
    "src/edu_cloud/modules/pipeline/router.py",
    "src/edu_cloud/modules/profile/router.py",
    "src/edu_cloud/modules/scan/router.py",
    "src/edu_cloud/modules/school/assignment_router.py",
    "src/edu_cloud/modules/school/audit_router.py",
    "src/edu_cloud/modules/school/capability_router.py",
    "src/edu_cloud/modules/school/selection_router.py",
    "src/edu_cloud/modules/school/settings_router.py",
    "src/edu_cloud/modules/student/router.py",
    "src/edu_cloud/modules/student/teacher_router.py",
    "src/edu_cloud/modules/studio/router.py",
    # 以下 4 个文件本批触碰，已从 allowlist 移除（F007），必须在修改时迁移:
    # "src/edu_cloud/api/dashboard.py" — Task 4 迁移
    # "src/edu_cloud/modules/exam/workspace_router.py" — Task 5 迁移
    # "src/edu_cloud/modules/analytics/analytics_report_router.py" — Task 6 迁移
    # "src/edu_cloud/modules/scan/pipeline_router.py" — Task 2 已用 get_school_id
}


def _find_router_files():
    files = []
    for d in ROUTER_DIRS:
        if d.exists():
            for f in d.rglob("*router*.py"):
                if "__pycache__" not in str(f):
                    files.append(f)
            for f in d.rglob("*.py"):
                if f.name in ("dashboard.py", "ai.py") and "__pycache__" not in str(f):
                    files.append(f)
    return sorted(set(files))


def test_no_new_raw_school_id_in_routers():
    """新增 router 文件不得直接使用 role.school_id，必须走 TenantContext。

    已有文件在 ALLOWLIST_RAW_SCHOOL_ID 中，触碰即迁移。
    """
    violations = []
    for f in _find_router_files():
        rel = str(f)
        if rel in ALLOWLIST_RAW_SCHOOL_ID:
            continue
        content = f.read_text()
        if '.school_id' in content and 'get_school_id' not in content and 'TenantContext' not in content:
            violations.append(rel)
    assert not violations, f"新增 router 使用了裸 role.school_id: {violations}"


def test_scope_filter_no_falsy_check():
    """ScopeFilter 不得用 if self.X 检查 scope 列表（空列表 fail-open）。"""
    content = Path("src/edu_cloud/core/scope_filter.py").read_text()
    lines = content.split("\n")
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for attr in ("class_ids", "grade_ids", "subject_codes"):
            if f"if self.{attr}" in stripped and "is not None" not in stripped:
                violations.append(f"scope_filter.py:{i}: {stripped}")
    assert not violations, f"ScopeFilter 使用了 falsy check: {violations}"
```

- [ ] **Step 2: 运行治理测试**

Run: `.venv/bin/python -m pytest tests/governance/ -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
mkdir -p tests/governance
touch tests/governance/__init__.py
git add tests/governance/
git commit -m "feat: add tenant static governance tests (no-new-raw-school_id + scope-filter-no-falsy)"
```

---

### Task 8: 全量回归测试

- [ ] **Step 1: 后端全量测试**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: 无新增失败（基线 44 known failures in llm_client/rubric）

- [ ] **Step 2: 确认新增测试数量**

Run: `.venv/bin/python -m pytest tests/test_api/test_marking_import_isolation.py tests/test_api/test_pipeline_state_isolation.py tests/test_api/test_tenant_context.py tests/test_api/test_dashboard_subject_scope.py tests/governance/ -v --co`
Expected: ~18-20 个新测试

- [ ] **Step 3: 提交最终状态（如有修复）**

---

## Contract Pack (F001 修复: schema-rooted)

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "platform_admin/district_admin 调用 get_school_id 返回 None，查询不加 school_id WHERE"
      verification: existing_test
      test_ref: tests/test_core/test_tenant.py::test_get_school_id_admin_returns_none

    - id: INV-002
      statement: "TenantContext.apply_subject_scope 当 visible_subject_codes=() 时生成 WHERE false()（deny-all）"
      verification: pending_test
      test_ref: tests/test_api/test_tenant_context.py::test_apply_subject_scope_empty_tuple_deny_all

    - id: INV-003
      statement: "ScopeFilter.apply 使用 is not None 检查 scope 列表，空列表 [] 生成 IN ()（deny-all），不跳过"
      verification: pending_test
      test_ref: tests/governance/test_tenant_static.py::test_scope_filter_no_falsy_check

    - id: INV-004
      statement: "新增 router 文件不得直接使用 current['current_role'].school_id，必须走 get_school_id 或 TenantContext"
      verification: pending_test
      test_ref: tests/governance/test_tenant_static.py::test_no_new_raw_school_id_in_routers

  counter_examples:
    - id: CE-001
      scenario: "ScopeFilter 空列表 [] 被 if self.subject_codes 跳过（falsy），受限角色看到全校所有科目数据"
      tests_that_still_pass: "现有测试无空 scope 场景，全部仍 PASS"
      mitigation: "改 if self.X 为 if self.X is not None + 新增 test_scope_filter_no_falsy_check 治理测试"

    - id: CE-002
      scenario: "importer.py select(Exam).where(Exam.id==exam_id) 不加 school_id，A 校用户传 B 校 exam_id 可写入跨校数据"
      tests_that_still_pass: "现有 test_marking.py 只测正常导入，无跨校场景"
      mitigation: "Exam/Subject/StudentAnswer 查询全部加 school_id WHERE + test_import_rejects_other_school_exam"

  risk_modules:
    - module: src/edu_cloud/core/tenant.py
      reason: "TenantContext 新增，所有 router 的 scope 入口契约变更"
    - module: src/edu_cloud/api/deps.py
      reason: "get_tenant_context dependency wiring，影响未来所有使用 TenantContext 的 router"
    - module: src/edu_cloud/core/scope_filter.py
      reason: "空列表语义从 fail-open 改为 deny-all，影响所有 ScopeFilter 调用方"
    - module: src/edu_cloud/modules/marking/importer.py
      reason: "Exam/Subject/StudentAnswer 查询加 school_id，影响导入全链路"
    - module: src/edu_cloud/modules/scan/pipeline_service.py
      reason: "全局状态增加 school 维度，影响 progress/stop/start 全链路"
    - module: src/edu_cloud/modules/scan/pipeline_router.py
      reason: "progress/stop 端点加 school_id 验证"
    - module: src/edu_cloud/api/dashboard.py
      reason: "Dashboard 聚合统计追加 subject scope JOIN，影响所有角色的仪表盘"
    - module: src/edu_cloud/modules/exam/workspace_router.py
      reason: "Workspace 传递 subject_codes 到 service"
    - module: src/edu_cloud/modules/analytics/analytics_report_router.py
      reason: "Grade overview 传递 visible_subject_codes"
    - module: src/edu_cloud/services/workspace_service.py
      reason: "Workspace service 接收并应用 subject_codes 过滤"
    - module: src/edu_cloud/modules/analytics/grade_service.py
      reason: "Grade service get_grade_overview 签名增加 visible_subject_codes 参数"
    - module: tests/governance/test_tenant_static.py
      reason: "治理基础设施，allowlist 错误会导致新漏洞漏检"

  test_debt:
    - item: "23 个旧 router 仍用 role.school_id，在 governance allowlist 中"
      reason: "全量迁移成本高，采用触碰即迁移策略逐步收敛"
      deadline: "2026-06-30"
    - item: "SQLAlchemy do_orm_execute audit mode 未实施"
      reason: "需要 model registry 确定 tenant-scoped 表清单，Phase 3.4 独立立项"
      deadline: "2026-07-31"
    - item: "pipeline 测试直接设置私有全局状态而非通过 start 入口"
      reason: "真实 start 需要完整的扫描图+模板数据，入口级测试成本高，标注后续补充"
      deadline: "2026-06-15"
```
