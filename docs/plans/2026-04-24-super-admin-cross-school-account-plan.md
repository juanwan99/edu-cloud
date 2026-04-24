---
baseline_command: "cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=no -q"
baseline_verified_at: "2026-04-24T23:16+08:00"
baseline_count: "backend: 2161 passed / 23 skipped / 3 failed (pre-existing: test_alembic_s1a_bank::test_upgrade_then_downgrade_is_clean + test_services/test_new_permissions::test_subject_teacher_has_view_grading + test_services/test_permissions_grading::test_subject_teacher_no_manage_grading — 后两条对应 MEMORY project_grading_permission_temp，非本 plan 引入); frontend: 249 passed / 1 failed (pre-existing: frontend/src/__tests__/config.test.js::sidebar config parent has minimal items)"
topic: "2026-04-24-super-admin-cross-school-account"
tier: "T3"
risk_modules:
  - "src/edu_cloud/modules/student/teacher_router.py"
  - "frontend/src/pages/TeachersPage.vue"
  - "frontend/src/api/schools.js"
design_source: "docs/plans/2026-04-24-super-admin-cross-school-account-design.md"
revision_history:
  - round: "R1 revision"
    date: "2026-04-24T23:50+08:00"
    trigger: "GPT Codex Plan Review R1 FAIL (3 HIGH + 4 MED)"
    raw_log: "docs/plans/.codex-raw-plan-review-super-admin-r1-20260424_234500.log"
    review_report: "docs/plans/2026-04-24-super-admin-cross-school-account-plan-review.md"
    fixes_applied:
      - "F001: 新增后端测试 test_platform_admin_creates_subject_teacher_cross_school 回放 ORC-004 后端契约"
      - "F002: academic_director 测试加 UserRole.school_id 断言；Step 1.2 红灯分布准确描述（7 测试：6 FAIL + 1 PASS）"
      - "F003: openCreate 在超管跨校场景重置 form.roles=['principal']"
      - "F004: roleOptions 拆 createRoleOptions + importRoleOptions"
      - "F005: 测试补 DOM 级断言 data-testid=school-select"
      - "F006: Task 3 token 键改 'token'；场景 A/D 末尾追加 cleanup"
      - "F007: 每 Task 补审查清单 + 边界条件（≥3）段"
---

# 超管跨校创建学校管理账号 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `platform_admin` 在 `https://mcu.asia/teachers` 能为任一既有学校创建 `principal` / `academic_director` 管理账号，同时保留其他角色"只能在本校内建账号"的既有契约。

**Architecture:**
- 后端：`TeacherCreate` schema 加 `school_id` 字段；`POST /teachers` 删除 `hasattr` 死代码并引入 `is_cross_school` 判断——跨校分支手动校验 `Permission.MANAGE_SCHOOLS`（router 体内检查，不走 `Depends(require_permission(...))` 工厂）。
- 前端：`TeachersPage.vue` 在超管登录时从 `GET /schools` 拉全部学校到下拉；创建表单角色下拉在超管跨校模式下仅保留 `principal + academic_director`；提交时超管带 `school_id`。
- 测试：后端 `tests/test_api_exam/test_teachers_cross_school.py`（6 场景），前端 `frontend/src/pages/__tests__/TeachersPage.cross-school.test.js`（4 场景），无需新增 API 客户端函数。

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 async（后端）；Vue 3.5 + Naive UI + Vitest + @vue/test-utils + happy-dom（前端）。

**Design source:** `docs/plans/2026-04-24-super-admin-cross-school-account-design.md`

---

## Scope Check

本 plan 覆盖**单一子系统**：超管跨校创建学校管理账号。涉及 1 个后端 router + 1 个前端页面 + 两侧各 1 个测试文件 = 4 个主改动文件（+ 可能补 1 行 `api/schools.js` 的 listSchools 导出）。**不拆子 plan**。

**非目标**（与 design §6 一致）：
- 不改 `POST /students` 的 permission guard（followup T3-D）
- 不扩"超管跨校建科任/班主任"
- 不加 `MANAGE_SCHOOL_ADMIN_ACCOUNTS` permission（YAGNI）
- 后端不做 role 白名单强校验（保留 `ALL_SCHOOL_ROLES` 契约，由前端 UI 裁剪）

---

## File Structure

| 文件 | 动作 | 责任 |
|---|---|---|
| `src/edu_cloud/modules/student/teacher_router.py` | **Modify** L39-56 + L147-188 | `TeacherCreate` 加 `school_id` 字段；`create_teacher()` 删 `hasattr` 死代码 + 跨校判断 + 权限检查 |
| `tests/test_api_exam/test_teachers_cross_school.py` | **Create** | 后端 7 个跨校场景契约锁（含 R1-F001 超管跨校 subject_teacher 201 回归锁） |
| `frontend/src/pages/TeachersPage.vue` | **Modify** | 超管学校下拉源改 `GET /schools`；`createRoleOptions` / `importRoleOptions` 拆分（R1-F004）；`openCreate` 重置 `form.roles`（R1-F003）；提交 payload 带 `school_id`；`n-select` 加 `data-testid`（R1-F005） |
| `frontend/src/pages/__tests__/TeachersPage.cross-school.test.js` | **Create** | 前端 5 个跨校场景契约锁（含 R1-F003/F005 DOM 级 + form.roles 重置） |
| `frontend/src/api/schools.js` | **Verify / conditional Modify** | 若未 export `listSchools` 则补一行（Step 2.3 查） |

**非影响面**（调研确认）：
- `frontend/src/api/teachers.js` 零动：`listTeachers(params)` 已透传 query params，`createTeacher(data)` 已透传 body（`frontend/src/api/teachers.js:3-4` verified via Read 2026-04-24）
- `core/permissions.py` 零动：复用既有 `MANAGE_SCHOOLS`
- `api/deps.py`、`api/app.py` 零动：`PermissionDeniedError` → 403 / `ValidationError` → 422 已接线（`api/app.py:198-204` verified）
- `sidebarConfig.js:49` 零动：`platform_admin` 已挂 `/teachers`
- `tests/conftest.py` 零动：新建测试直接复用 `client` / `db` / `db_engine` fixture

---

## 关键澄清（design → plan 修正）

**design.md §3.3 描述不准确**：`require_permission` 不是 async helper，而是 FastAPI 依赖注入工厂，签名 `require_permission(perm: Permission) -> async checker(current=Depends(get_current_user))`（`src/edu_cloud/api/deps.py:71-79` verified via Read）。

**router 体内动态检查跨校权限的正确姿势**（因为 `create_teacher` 在运行时才知道是不是跨校，不能在函数签名上 `Depends(require_permission(...))`）：

```python
from edu_cloud.core.permissions import Permission
from edu_cloud.services.exceptions import PermissionDeniedError

if is_cross_school:
    if Permission.MANAGE_SCHOOLS not in current["permissions"]:
        raise PermissionDeniedError(
            f"Role '{current['current_role'].role}' lacks permission 'manage_schools' for cross-school create"
        )
    target_school_id = req.school_id
```

`PermissionDeniedError` 由 `api/app.py:198` 全局 handler 映射为 HTTP 403。

---

## semantic_regression（L017 不变量）

本 plan 完成后，以下 4 条设计不变量必须保持为真；codex-review code gate 将基于这些断言检查实现：

**ORC-001**: `POST /teachers` 必须有 school_id 来源（`current_role.school_id` **或** `req.school_id`），否则返回 422（`ValidationError("缺少 school_id")`）。

**ORC-002**: 跨校创建——即 `req.school_id` 提供且不等于 `current_role.school_id`（或 `current_role.school_id is None`）——必须检查调用者拥有 `Permission.MANAGE_SCHOOLS`，否则返回 403（`PermissionDeniedError`）。

**ORC-003**: `TeachersPage.vue` 的"学校"下拉源在 `isPlatformAdmin === true` 时为 `GET /schools` 返回的全部学校；其他角色维持既有来源（`auth.roles[].context`）。组件 DOM 中下拉渲染条件至少覆盖 `isPlatformAdmin || schoolOptions.length > 1`。

**ORC-004**: 后端**不做**角色白名单收窄，`POST /teachers` 保持 `ALL_SCHOOL_ROLES` 契约（包括超管跨校传 `role=subject_teacher` 也返回 201）；前端 UI 在 `isPlatformAdmin && selectedSchool` 时 `createRoleOptions` 仅暴露 `principal + academic_director`，且 `openCreate` 同步把 `form.roles` 重置为 `['principal']`（R1-F003 防默认角色泄漏）。`principal` 在本校建 `subject_teacher` 路径不受影响（既有契约保留）。

---

## Evidence 摘要（完整见 design.md §7）

| 判断 | 证据 |
|---|---|
| `TeacherCreate` 无 `school_id` | `teacher_router.py:39-56` Read verified |
| `hasattr(req, 'school_id')` 死代码 | `teacher_router.py:153-155`；Pydantic 未声明字段恒 False |
| `GET /teachers` 已支持 `school_id` query | `teacher_router.py:104-107` Read verified |
| `MANAGE_SCHOOLS` 归 `platform_admin` | `core/permissions.py:103` + `permissions.py:19` Read verified |
| `ALL_SCHOOL_ROLES` 含 principal+academic_director | `teacher_router.py:22-28` Read verified |
| `sidebarConfig.js` 超管已挂 `/teachers` | `frontend/src/config/sidebarConfig.js:49` Read verified |
| `api/teachers.js` 已支持传 params+body | `frontend/src/api/teachers.js:3-4` Read verified |
| `PermissionDeniedError` → 403 handler | `api/app.py:198-200` Read verified |
| `ValidationError` → 422 handler | `api/app.py:202-204` Read verified |
| 前端既存测试目录存在 | `frontend/src/pages/__tests__/SchoolsPage.create.test.js` 文件已存在 |
| 后端既存测试目录存在 | `tests/test_api_exam/__init__.py` 存在 |
| "景炎" 未硬编码 | `grep -rn "景炎" src/ scripts/ frontend/` 零命中 |
| 前端 auth token 键名是 `'token'` | `frontend/src/stores/auth.js:32/67/117` grep verified (R1-F006) |
| `roleOptions` 双入口耦合 | `frontend/src/pages/TeachersPage.vue:78`（创建表单）+ `:102`（Excel 导入 importRole）Read verified (R1-F004) |
| `form.roles` 默认值 `['subject_teacher']` | `frontend/src/pages/TeachersPage.vue:168-174` defaultForm Read verified (R1-F003) |
| Pydantic v2 未声明字段默认 extra='ignore' | 本地 REPL 验证：`class M(BaseModel): pass` + `M(x=1).model_dump()` 返回 `{}`（R1-F002 测试红灯分布依据） |

---

## Task 1: 后端 — `TeacherCreate.school_id` + 跨校判断

**Files:**
- Modify: `src/edu_cloud/modules/student/teacher_router.py:39-56`（`TeacherCreate` 新增字段）
- Modify: `src/edu_cloud/modules/student/teacher_router.py:147-188`（`create_teacher` 重写 school_id 决策 + 权限守卫）
- Create: `tests/test_api_exam/test_teachers_cross_school.py`（新建测试文件，7 场景）

**测试契约（5 字段）:**
- 入口: `POST /api/v1/teachers` 带 JWT + JSON body（走 get_current_user + get_db 完整链路）
- 反例:
  - 非超管带 `req.school_id=他校` → **403**
  - 超管不传 `school_id` 且 current_role 无 school_id → **422**
  - **R1-F001 新增**：超管传 `role=subject_teacher + school_id=他校` 必须 **201** 且 `UserRole.role/school_id` 落库正确（若返回 403/422 即等于加了后端白名单，违反 ORC-004）
- 边界（≥3，R1-F007）:
  1. `req.school_id == current_role.school_id` → `is_cross_school=False`，201（principal 本校显式传 school_id）
  2. `current_role.school_id is None + req.school_id != None` → MANAGE_SCHOOLS 持有者 201，否则 403（平台/超管场景）
  3. `current_role.school_id != None + req.school_id != None + 不等` → MANAGE_SCHOOLS 持有者 201，否则 403（跨校越权场景）
  4. `current_role.school_id is None + req.school_id is None` → 422（无 school_id 来源）
- 回归: principal 在本校建 subject_teacher 场景（不传 school_id，走 current_role.school_id）保持 201 既有行为
- 命令: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_teachers_cross_school.py -v`

**审查清单（R1-F007）:**
- [ ] `TeacherCreate.school_id` 类型 `str | None = None`（Optional，不改变既有调用方契约）
- [ ] `is_cross_school` 条件覆盖 `current_role.school_id is None` 分支（超管 scope）
- [ ] `Permission.MANAGE_SCHOOLS not in current["permissions"]` 判断放在 `if is_cross_school` 内（非跨校不触发守卫）
- [ ] `target_school_id is None` 422 分支覆盖超管既不传也无 current_role.school_id 场景
- [ ] `UserRole(..., school_id=target_school_id, ...)` 使用新变量名（不与外层混淆）
- [ ] 所有"超管创建成功"测试断言 `UserRole.school_id` 落库值（防 F002 弱断言红灯不成立）
- [ ] 测试集含 R1-F001 超管跨校 subject_teacher 201 回归锁

- [ ] **Step 1.1: 新建测试文件并写 7 个测试（6 FAIL + 1 PASS 的红灯分布）**

Create `tests/test_api_exam/test_teachers_cross_school.py`:

```python
"""超管跨校创建学校管理账号 — POST /teachers 契约测试（ORC-001/ORC-002/ORC-004）。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def cross_school_setup(db):
    """两所学校 + 超管 / 景炎校长 / 景炎科任教师三种调用者。"""
    school_a = School(id="s_jy", name="景炎初级中学", code="JY001")
    school_b = School(id="s_yc", name="育才实验中学", code="YC001")
    db.add_all([school_a, school_b])
    await db.commit()

    admin = User(id="u_pa", username="pa_cross", display_name="平台超管")
    admin.set_password("p")
    principal_a = User(id="u_pri_a", username="pri_a", display_name="景炎校长")
    principal_a.set_password("p")
    teacher_a = User(id="u_t_a", username="t_a", display_name="景炎语文老师")
    teacher_a.set_password("p")
    db.add_all([admin, principal_a, teacher_a])
    await db.flush()

    db.add_all([
        UserRole(user_id="u_pa", role="platform_admin", school_id=None, is_primary=True),
        UserRole(user_id="u_pri_a", role="principal", school_id="s_jy", is_primary=True),
        UserRole(user_id="u_t_a", role="subject_teacher", school_id="s_jy",
                 is_primary=True, subject_codes=["YW"]),
    ])
    await db.commit()

    def _token(uid, role):
        return {"Authorization": f"Bearer {create_access_token({'sub': uid, 'role': role})}"}

    return {
        "school_a_id": "s_jy",
        "school_b_id": "s_yc",
        "admin": _token("u_pa", "platform_admin"),
        "principal_a": _token("u_pri_a", "principal"),
        "teacher_a": _token("u_t_a", "subject_teacher"),
    }


class TestCrossSchoolTeacherCreate:
    """ORC-001 / ORC-002 / ORC-004 契约锁。"""

    async def test_platform_admin_creates_principal_in_target_school(
        self, client: AsyncClient, cross_school_setup, db
    ):
        """超管传 school_id=景炎 + role=principal → 201，UserRole.school_id=景炎。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "new_principal_jy",
                "display_name": "景炎新校长",
                "roles": ["principal"],
                "school_id": cross_school_setup["school_a_id"],
            },
            headers=cross_school_setup["admin"],
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["roles"][0]["role"] == "principal"
        role_row = (await db.execute(
            select(UserRole).where(UserRole.user_id == body["id"])
        )).scalar_one()
        assert role_row.school_id == cross_school_setup["school_a_id"]

    async def test_platform_admin_creates_academic_director(
        self, client: AsyncClient, cross_school_setup, db
    ):
        """ORC-002：超管传 school_id + role=academic_director → 201，落库 school_id 正确。

        R1-F002 加强：断言 UserRole.school_id 而不只是 status_code，确保红灯基线成立。
        """
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "new_director_jy",
                "display_name": "景炎新教务",
                "roles": ["academic_director"],
                "school_id": cross_school_setup["school_a_id"],
            },
            headers=cross_school_setup["admin"],
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["roles"][0]["role"] == "academic_director"
        role_row = (await db.execute(
            select(UserRole).where(UserRole.user_id == body["id"])
        )).scalar_one()
        assert role_row.school_id == cross_school_setup["school_a_id"]

    async def test_platform_admin_creates_subject_teacher_cross_school(
        self, client: AsyncClient, cross_school_setup, db
    ):
        """ORC-004 后端契约锁（R1-F001）：超管跨校传 role=subject_teacher → 201。

        后端不做角色白名单收窄（保持 ALL_SCHOOL_ROLES 契约）；角色引导由前端 UI 完成。
        若此测试返回 403 或 422，说明实现误加了后端白名单，破坏既有 principal 在本校建
        subject_teacher 路径。
        """
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "cross_subject_teacher",
                "display_name": "跨校科任教师",
                "roles": ["subject_teacher"],
                "school_id": cross_school_setup["school_a_id"],
            },
            headers=cross_school_setup["admin"],
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["roles"][0]["role"] == "subject_teacher"
        role_row = (await db.execute(
            select(UserRole).where(UserRole.user_id == body["id"])
        )).scalar_one()
        assert role_row.role == "subject_teacher"
        assert role_row.school_id == cross_school_setup["school_a_id"]

    async def test_platform_admin_without_school_id_returns_422(
        self, client: AsyncClient, cross_school_setup
    ):
        """超管不传 school_id + current_role 也无 school_id → 422（ORC-001）。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "orphan_principal",
                "display_name": "孤儿校长",
                "roles": ["principal"],
            },
            headers=cross_school_setup["admin"],
        )
        assert resp.status_code == 422, resp.text

    async def test_subject_teacher_cross_school_returns_403(
        self, client: AsyncClient, cross_school_setup
    ):
        """科任教师（本校 s_jy）试图跨校向 s_yc 建账号 → 403（ORC-002）。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "evil_cross",
                "display_name": "跨校恶意",
                "roles": ["subject_teacher"],
                "school_id": cross_school_setup["school_b_id"],
            },
            headers=cross_school_setup["teacher_a"],
        )
        assert resp.status_code == 403, resp.text

    async def test_principal_same_school_passes(
        self, client: AsyncClient, cross_school_setup
    ):
        """景炎校长显式传本校 school_id → 走本校分支（is_cross_school=False），201。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "t_new_in_own_school",
                "display_name": "本校新科任",
                "roles": ["subject_teacher"],
                "school_id": cross_school_setup["school_a_id"],
            },
            headers=cross_school_setup["principal_a"],
        )
        assert resp.status_code == 201, resp.text

    async def test_principal_cross_school_returns_403(
        self, client: AsyncClient, cross_school_setup
    ):
        """景炎校长试图跨校向 s_yc 建账号 → 403（ORC-002）。"""
        resp = await client.post(
            "/api/v1/teachers",
            json={
                "username": "cross_by_principal",
                "display_name": "跨校越权",
                "roles": ["principal"],
                "school_id": cross_school_setup["school_b_id"],
            },
            headers=cross_school_setup["principal_a"],
        )
        assert resp.status_code == 403, resp.text
```

- [ ] **Step 1.2: 运行测试确认红灯分布符合预期（R1-F002 准确描述）**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_teachers_cross_school.py -v
```

**现状代码（pre-Task-1）下预期分布：6 FAIL + 1 PASS**

| 测试 | 预期（post-impl） | 现状行为 | R1 状态 |
|---|---|---|---|
| `test_platform_admin_creates_principal_in_target_school` | 201 + `UserRole.school_id=s_jy` | current_role.school_id=None + `hasattr(req, 'school_id')` False（Pydantic v2 未声明字段 extra='ignore' 丢弃）→ school_id=None 落库 → assert school_id=s_jy **FAIL** | FAIL（红灯）|
| `test_platform_admin_creates_academic_director` | 201 + `UserRole.school_id=s_jy` | 同上 → **FAIL**（F002 加强 school_id 断言后） | FAIL（红灯）|
| `test_platform_admin_creates_subject_teacher_cross_school` | 201 + `UserRole.school_id=s_jy` | 同上 → **FAIL** | FAIL（红灯，R1-F001 新增）|
| `test_platform_admin_without_school_id_returns_422` | 422 | school_id=None → `UserRole(school_id=None)` 写入成功（nullable）→ 201 ≠ 422 **FAIL** | FAIL（红灯）|
| `test_subject_teacher_cross_school_returns_403` | 403 | current_role.school_id=s_jy + `hasattr` False → 用 s_jy 落库 → 201 ≠ 403 **FAIL** | FAIL（红灯）|
| `test_principal_same_school_passes` | 201 | 同上（current_role.school_id=s_jy）→ 201 → **PASS** | PASS（回归锁，非红灯）|
| `test_principal_cross_school_returns_403` | 403 | 同上 → 201 ≠ 403 **FAIL** | FAIL（红灯）|

Expected: **6 failed, 1 passed**。这是预期的红灯基线（6 红 + 1 回归绿），符合 TDD Red 阶段。

- [ ] **Step 1.3: 修改 `TeacherCreate` schema（L39-56）**

将 `src/edu_cloud/modules/student/teacher_router.py:39-56` 的类定义**追加一行** `school_id: str | None = None`：

```python
class TeacherCreate(BaseModel):
    username: str
    display_name: str
    password: str = "123456"
    roles: list[str] = ["subject_teacher"]
    phone: str | None = None
    email: str | None = None
    employee_id: str | None = None
    gender: str | None = None
    id_card: str | None = None
    title: str | None = None
    hire_date: str | None = None
    education: str | None = None
    university: str | None = None
    office_phone: str | None = None
    notes: str | None = None
    subject_codes: list[str] | None = None
    class_ids: list[str] | None = None
    school_id: str | None = None  # 仅超管跨校时需传；非超管忽略（ORC-001/ORC-002）
```

- [ ] **Step 1.4: 重写 `create_teacher()` 的 school_id 决策逻辑（L147-188）**

替换 `create_teacher()` 函数头部（L152-155 的 `school_id = current["current_role"].school_id or (...)` 死代码块）为跨校判断 + 权限检查。把下文 `ur = UserRole(..., school_id=school_id, ...)` 的变量名改为 `target_school_id`：

```python
@router.post("/teachers", status_code=201)
async def create_teacher(
    req: TeacherCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    # ── ORC-001/ORC-002：school_id 决策 + 跨校权限守卫 ──
    current_role = current["current_role"]
    is_cross_school = (req.school_id is not None) and (
        current_role.school_id is None or current_role.school_id != req.school_id
    )
    if is_cross_school:
        from edu_cloud.core.permissions import Permission
        from edu_cloud.services.exceptions import PermissionDeniedError
        if Permission.MANAGE_SCHOOLS not in current["permissions"]:
            raise PermissionDeniedError(
                f"Role '{current_role.role}' lacks permission 'manage_schools' for cross-school create"
            )
        target_school_id = req.school_id
    else:
        target_school_id = current_role.school_id or req.school_id
    if target_school_id is None:
        raise ValidationError("缺少 school_id")

    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise ValidationError(f"用户名 {req.username} 已存在")
    for r in req.roles:
        if r not in ALL_SCHOOL_ROLES:
            raise ValidationError(f"角色 {r} 不合法")

    import datetime as _dt
    user = User(
        username=req.username, display_name=req.display_name,
        phone=req.phone, email=req.email,
        employee_id=req.employee_id, gender=req.gender, id_card=req.id_card,
        title=req.title,
        hire_date=_dt.date.fromisoformat(req.hire_date) if req.hire_date else None,
        education=req.education, university=req.university,
        office_phone=req.office_phone, notes=req.notes,
    )
    user.set_password(req.password)
    db.add(user)
    await db.flush()

    created_roles = []
    for i, role_name in enumerate(req.roles):
        ur = UserRole(
            user_id=user.id, role=role_name, school_id=target_school_id,
            subject_codes=req.subject_codes, class_ids=req.class_ids,
            is_primary=(i == 0),
        )
        db.add(ur)
        created_roles.append(ur)
    await db.commit()
    await db.refresh(user)
    return _teacher_response(user, created_roles)
```

**关键变更（区别原代码）：**
- 删除 `school_id = current["current_role"].school_id or (req.school_id if hasattr(req, 'school_id') else None)`（死代码）
- 新增 `is_cross_school` 布尔判断
- 新增 `if is_cross_school:` 分支——导入 `Permission` + `PermissionDeniedError` + 手动检查 `Permission.MANAGE_SCHOOLS`
- 变量 `school_id` 改名 `target_school_id`（作用域局部，不与 router 其他函数变量冲突）
- `UserRole(..., school_id=target_school_id, ...)` 使用新变量名

- [ ] **Step 1.5: 运行新测试确认全部 PASS（7 绿）**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/test_teachers_cross_school.py -v
```

Expected: **7 passed**。

- [ ] **Step 1.6: 跑 teachers/student 子集确认无回归**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/ -k "teacher or student" -v
```

Expected: 新增 7 PASS + 原有 teacher/student 相关测试保持本 plan frontmatter 基线（不接受既有失败项增多）。

- [ ] **Step 1.7: 跑全量 pytest 与基线对比**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q 2>&1 | tail -10
```

基线（frontmatter baseline_verified_at 2026-04-24T23:16+08:00）：**2161 passed / 23 skipped / 3 failed**（3 failed 为既有技术债）。
Expected (post Task 1): **2168 passed** / 23 skipped / **≤3 failed**（+7 为本 plan 新增，3 pre-existing 不应增多）。

- [ ] **Step 1.8: git add + commit**

```bash
cd /home/ops/projects/edu-cloud && git add \
  src/edu_cloud/modules/student/teacher_router.py \
  tests/test_api_exam/test_teachers_cross_school.py
git commit -m "$(cat <<'EOF'
feat(teachers): support cross-school principal/academic_director create

- TeacherCreate add school_id field (Optional[str])
- POST /teachers router: replace hasattr dead-code with is_cross_school judgement
- cross-school branch manually verifies Permission.MANAGE_SCHOOLS -> PermissionDeniedError on fail
- 7 contract tests cover ORC-001/ORC-002/ORC-004 (含 subject_teacher 跨校 201 契约锁)

Design: docs/plans/2026-04-24-super-admin-cross-school-account-design.md
Plan: docs/plans/2026-04-24-super-admin-cross-school-account-plan.md Task 1
EOF
)"
```

---

## Task 2: 前端 — `TeachersPage.vue` 超管学校下拉 + 角色裁剪 + 提交 payload

**Files:**
- Verify / conditional Modify: `frontend/src/api/schools.js`（Step 2.3 查 listSchools 是否已 export，否则补一行）
- Modify: `frontend/src/pages/TeachersPage.vue`（超管学校源 / `createRoleOptions` + `importRoleOptions` 拆分（R1-F004）/ `openCreate` 重置 form.roles（R1-F003）/ `handleSave` payload / `data-testid`（R1-F005）/ defineExpose）
- Create: `frontend/src/pages/__tests__/TeachersPage.cross-school.test.js`（新建测试文件，5 场景）

**测试契约（5 字段）:**
- 入口: Vitest mount `TeachersPage.vue`，stub Naive UI 组件，mock `api/teachers` + `api/schools` + `api/client`；DOM 查询使用 `wrapper.find('[data-testid="school-select"]')`（R1-F005）
- 反例:
  - 非超管（`subject_teacher`）登录 → `GET /schools` 不被调用；DOM 中 `[data-testid="school-select"]` **不渲染**
  - 超管跨校 `openCreate` 后用户**不手改角色**直接 `handleSave` → payload.roles === `['principal']`（R1-F003 默认角色泄漏防护）
- 边界（≥3，R1-F007）:
  1. 超管登录但未选校（`selectedSchool=null`）→ `createRoleOptions.length === 8`（维持全集）
  2. 超管选中某校（`isPlatformAdmin && selectedSchool`）→ `createRoleOptions.length === 2`（裁剪）
  3. Excel 导入下拉始终使用 `importRoleOptions`（全集），不受 `selectedSchool` 影响（R1-F004 回归锁）
  4. 非超管（如 principal）→ `createRoleOptions.length === 8`，`importRoleOptions.length === 8`
- 回归: 非超管场景下 `handleSave` payload 不含 `school_id` 字段
- 命令: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/__tests__/TeachersPage.cross-school.test.js`

**审查清单（R1-F007）:**
- [ ] `isPlatformAdmin` 用 `computed`，对 `auth.currentRole?.role` 做**可空**保护
- [ ] `createRoleOptions` / `importRoleOptions` 分离（R1-F004），模板 L78 `createRoleOptions` / L102 `importRoleOptions`
- [ ] `openCreate` 在 `isPlatformAdmin.value && selectedSchool.value` 场景下把 `form.roles` 显式设为 `['principal']`（R1-F003）
- [ ] `handleSave` 仅在 `isPlatformAdmin.value && selectedSchool.value` 场景注入 `payload.school_id`
- [ ] 模板学校下拉 `<n-select>` 加 `data-testid="school-select"`（R1-F005），测试有 DOM 级断言
- [ ] `initSchools` async 化后 `onMounted` 用 `await initSchools()`（依赖序）
- [ ] `defineExpose` 暴露 `form / isPlatformAdmin / createRoleOptions / importRoleOptions / schoolOptions / selectedSchool / openCreate / handleSave`
- [ ] `listSchools` import 路径正确（若 `api/schools.js` 未 export 则先补一行）

- [ ] **Step 2.1: 新建前端测试文件并写 5 个失败测试**

Create `frontend/src/pages/__tests__/TeachersPage.cross-school.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const listTeachersSpy = vi.fn().mockResolvedValue({ data: [] })
const createTeacherSpy = vi.fn().mockResolvedValue({ data: { id: 'new', roles: [] } })
const listSchoolsSpy = vi.fn().mockResolvedValue({
  data: [
    { id: 'sch_jy', name: '景炎初级中学', code: 'JY001' },
    { id: 'sch_yc', name: '育才实验中学', code: 'YC001' },
  ],
})
const clientGetSpy = vi.fn().mockResolvedValue({ data: [] })

vi.mock('../../api/teachers', () => ({
  listTeachers: (...a) => listTeachersSpy(...a),
  createTeacher: (...a) => createTeacherSpy(...a),
  updateTeacher: vi.fn(),
  deleteTeacher: vi.fn(),
  importTeachers: vi.fn(),
  exportTeachers: vi.fn(),
  downloadTemplate: vi.fn(),
}))

vi.mock('../../api/schools', () => ({
  listSchools: (...a) => listSchoolsSpy(...a),
}))

vi.mock('../../api/client', () => ({
  default: { get: (...a) => clientGetSpy(...a) },
}))

const messageStub = { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() }
vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useMessage: () => messageStub, useDialog: () => ({ warning: vi.fn() }) }
})

import { useAuthStore } from '../../stores/auth'

function seedAuth(role, schoolContext = null) {
  const auth = useAuthStore()
  auth.$patch({
    roles: schoolContext
      ? [{ id: 'r1', role, context: { type: 'school', id: schoolContext.id, name: schoolContext.name } }]
      : [{ id: 'r1', role, context: null }],
    currentRoleId: 'r1',
  })
}

const STUBS = {
  NDataTable: true, NModal: true, NForm: true, NFormItem: true,
  NInput: true, NButton: true, NSelect: true, NTag: true, NUpload: true,
  NSwitch: true, NDivider: true,
}

describe('TeachersPage — 超管跨校创建契约锁（ORC-003/ORC-004）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listTeachersSpy.mockClear()
    createTeacherSpy.mockClear()
    listSchoolsSpy.mockClear()
    clientGetSpy.mockClear()
    Object.values(messageStub).forEach((fn) => fn.mockClear())
  })

  it('platform_admin 登录 → GET /schools 调用 + DOM 渲染学校下拉（ORC-003 DOM 级 / R1-F005）', async () => {
    seedAuth('platform_admin', null)
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    // DOM 级断言：学校下拉必须渲染（R1-F005）
    expect(wrapper.find('[data-testid="school-select"]').exists()).toBe(true)
    // API 级断言
    expect(listSchoolsSpy).toHaveBeenCalled()
    // state 断言
    expect(wrapper.vm.isPlatformAdmin).toBe(true)
    expect(wrapper.vm.schoolOptions.length).toBe(2)
    expect(wrapper.vm.schoolOptions[0]).toEqual(
      expect.objectContaining({ label: '景炎初级中学', value: 'sch_jy' })
    )
  })

  it('subject_teacher 登录 → GET /schools 不调用 + DOM 无学校下拉（ORC-003 DOM 级 / R1-F005）', async () => {
    seedAuth('subject_teacher', { id: 'sch_jy', name: '景炎初级中学' })
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    expect(wrapper.find('[data-testid="school-select"]').exists()).toBe(false)
    expect(listSchoolsSpy).not.toHaveBeenCalled()
    expect(wrapper.vm.isPlatformAdmin).toBe(false)
  })

  it('超管选中学校后 → createRoleOptions 仅含 principal+academic_director，importRoleOptions 保持全集（ORC-004 / R1-F004）', async () => {
    seedAuth('platform_admin', null)
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    wrapper.vm.selectedSchool = 'sch_jy'
    await flushPromises()
    // 创建表单下拉裁剪
    expect(wrapper.vm.createRoleOptions.length).toBe(2)
    const values = wrapper.vm.createRoleOptions.map((o) => o.value).sort()
    expect(values).toEqual(['academic_director', 'principal'])
    // Excel 导入下拉不受影响（R1-F004 回归锁）
    expect(wrapper.vm.importRoleOptions.length).toBeGreaterThanOrEqual(8)
  })

  it('超管跨校 openCreate 后未手改角色 handleSave → payload.roles === ["principal"]（R1-F003 默认角色泄漏防护）', async () => {
    seedAuth('platform_admin', null)
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    wrapper.vm.selectedSchool = 'sch_jy'
    wrapper.vm.openCreate()
    wrapper.vm.form.display_name = '景炎新校长'
    wrapper.vm.form.username = 'new_pri'
    // 关键：不手改 form.roles，直接 handleSave
    await flushPromises()
    await wrapper.vm.handleSave()
    await flushPromises()
    expect(createTeacherSpy).toHaveBeenCalledTimes(1)
    const payload = createTeacherSpy.mock.calls[0][0]
    // 默认角色被重置为 principal，非 defaultForm 的 subject_teacher
    expect(payload.roles).toEqual(['principal'])
    expect(payload.school_id).toBe('sch_jy')
  })

  it('非超管场景 handleSave → payload 不含 school_id（回归锁）', async () => {
    seedAuth('principal', { id: 'sch_jy', name: '景炎初级中学' })
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    wrapper.vm.openCreate()
    wrapper.vm.form.display_name = '本校新科任'
    wrapper.vm.form.username = 't_new'
    wrapper.vm.form.roles = ['subject_teacher']
    await flushPromises()
    await wrapper.vm.handleSave()
    await flushPromises()
    expect(createTeacherSpy).toHaveBeenCalledTimes(1)
    const payload = createTeacherSpy.mock.calls[0][0]
    expect(payload).not.toHaveProperty('school_id')
  })
})
```

- [ ] **Step 2.2: 运行 vitest 确认 5 个测试 FAIL**

Run:
```bash
cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/__tests__/TeachersPage.cross-school.test.js
```

Expected: 5 个测试 FAIL（原因：`isPlatformAdmin` / `createRoleOptions` / `importRoleOptions` 当前不存在，`handleSave` 不注入 `school_id`，模板无 `data-testid`，`openCreate` 不重置 form.roles）。

- [ ] **Step 2.3: 确认 `api/schools.js` 的 `listSchools` 存在**

Run:
```bash
grep -nE "export const listSchools|export function listSchools" /home/ops/projects/edu-cloud/frontend/src/api/schools.js
```

若命中一行：跳到 Step 2.4。若零命中：追加一行：

```javascript
export const listSchools = (params) => client.get('/schools', { params })
```

加在 `frontend/src/api/schools.js` 文件末（确保该文件已 `import client from './client'`，`api/client.js` baseURL = `/api/v1`）。

- [ ] **Step 2.4: 修改 `TeachersPage.vue` — 引入 listSchools + computed**

编辑 L124 `import { h, ref, reactive, onMounted } from 'vue'`，改为：

```javascript
import { h, ref, reactive, onMounted, computed } from 'vue'
```

并在 `import client from '../api/client'` 下一行新增：

```javascript
import { listSchools } from '../api/schools'
```

- [ ] **Step 2.5: 拆分 `roleOptions` 为 `createRoleOptions` + `importRoleOptions`（R1-F004）**

定位 L160 `const roleOptions = Object.entries(roleLabels).map(([value, label]) => ({ label, value }))`。替换为：

```javascript
const isPlatformAdmin = computed(() => {
  const auth = useAuthStore()
  return auth.currentRole?.role === 'platform_admin'
})

const ROLE_OPTIONS_ALL = Object.entries(roleLabels).map(([value, label]) => ({ label, value }))
const ROLE_OPTIONS_CROSS_SCHOOL = [
  { label: '校长', value: 'principal' },
  { label: '教务主任', value: 'academic_director' },
]

// 创建表单角色下拉：超管跨校时裁剪；其他场景全集
const createRoleOptions = computed(() => {
  if (isPlatformAdmin.value && selectedSchool.value) {
    return ROLE_OPTIONS_CROSS_SCHOOL
  }
  return ROLE_OPTIONS_ALL
})

// Excel 导入默认角色下拉：始终全集（R1-F004 不受 selectedSchool 影响）
const importRoleOptions = ROLE_OPTIONS_ALL
```

**关键变更（R1-F004）**：原 `roleOptions` 同时服务创建表单（L78）和 Excel 导入（L102 `importRole`）两个入口。改全局 computed 会连带裁剪导入下拉。本 Step 拆成 `createRoleOptions`（computed 裁剪）+ `importRoleOptions`（静态全集）两源。

- [ ] **Step 2.5a: 模板绑定 — 创建表单用 `createRoleOptions`，导入用 `importRoleOptions`**

在模板中定位 L78 `<n-select v-model:value="form.roles" :options="roleOptions" multiple placeholder="可多选" />`（创建表单区）改为：

```vue
<n-select v-model:value="form.roles" :options="createRoleOptions" multiple placeholder="可多选" />
```

定位 L102 `<n-select v-model:value="importRole" :options="roleOptions" />`（Excel 导入区）改为：

```vue
<n-select v-model:value="importRole" :options="importRoleOptions" />
```

- [ ] **Step 2.6: 改写 `initSchools()` — 超管模式从 `GET /schools` 拉全部**

替换原 L406-422 `initSchools()` 同步函数：

```javascript
async function initSchools() {
  const auth = useAuthStore()
  if (isPlatformAdmin.value) {
    try {
      const { data } = await listSchools()
      schoolOptions.value = data.map((s) => ({ label: s.name, value: s.id }))
      if (schoolOptions.value.length) {
        selectedSchool.value = schoolOptions.value[0].value
      }
    } catch {
      message.error('加载学校列表失败')
    }
    return
  }
  const seen = new Map()
  for (const r of (auth.roles || [])) {
    const ctx = r.context
    if (ctx?.id && ctx?.name && !seen.has(ctx.id)) {
      seen.set(ctx.id, ctx.name)
    }
  }
  schoolOptions.value = [...seen.entries()].map(([id, name]) => ({ label: name, value: id }))
  const current = auth.currentRole
  if (current?.context?.id) {
    selectedSchool.value = current.context.id
  } else if (schoolOptions.value.length) {
    selectedSchool.value = schoolOptions.value[0].value
  }
}
```

**同步更新 `onMounted`**（位置在文件末）：

```javascript
onMounted(async () => {
  await initSchools()
  loadTeachers()
  loadClasses()
})
```

- [ ] **Step 2.6a: 改写 `openCreate()` — 超管跨校场景重置 `form.roles=['principal']`（R1-F003）**

定位 L288 `function openCreate()`。替换为：

```javascript
function openCreate() {
  editingId.value = null
  Object.assign(form, defaultForm())
  // ORC-004 / R1-F003：超管选中某校后新建时，form.roles 默认锁在 principal
  // （避免 defaultForm 的 ['subject_teacher'] 在裁剪下拉下依然被提交）
  if (isPlatformAdmin.value && selectedSchool.value) {
    form.roles = ['principal']
  }
  showForm.value = true
}
```

**关键变更（R1-F003）**：`defaultForm()` 默认 `form.roles=['subject_teacher']`（verified `TeachersPage.vue:168-174`）。超管跨校下拉只显示"校长"/"教务主任"，但 `form.roles` 仍是 `['subject_teacher']`——用户不主动改就会提交 subject_teacher 跨校账号，违反 ORC-004 的"前端 UI 引导创建管理账号"意图。本 Step 在超管跨校场景显式重置。

- [ ] **Step 2.7: 改写 `handleSave()` — 超管创建场景 payload 注入 school_id**

定位 L314-339 `handleSave` 的 create 分支（`} else {` 后的 `const payload = { ...form }`）。替换为：

```javascript
    } else {
      const payload = { ...form }
      if (!payload.subject_codes?.length) delete payload.subject_codes
      if (!payload.class_ids?.length) delete payload.class_ids
      // ORC-004: 超管跨校创建时带 school_id；非超管忽略
      if (isPlatformAdmin.value && selectedSchool.value) {
        payload.school_id = selectedSchool.value
      }
      await createTeacher(payload)
      message.success('添加成功')
    }
```

- [ ] **Step 2.8: 改下拉 v-if 覆盖超管单校场景 + 加 `data-testid`（R1-F005）**

模板 L17 当前 `<n-select v-if="schoolOptions.length > 1" v-model:value="selectedSchool" :options="schoolOptions" style="width: 200px;" @update:value="onSchoolChange" />`。改为：

```vue
<n-select
  v-if="isPlatformAdmin || schoolOptions.length > 1"
  v-model:value="selectedSchool"
  :options="schoolOptions"
  style="width: 200px;"
  data-testid="school-select"
  @update:value="onSchoolChange" />
```

**关键变更**：
1. `v-if` 覆盖超管单校场景（ORC-003 要求超管哪怕只有 1 所学校时下拉仍可见）
2. 新增 `data-testid="school-select"`（R1-F005），供 vitest DOM 级断言使用

- [ ] **Step 2.9: `defineExpose` — 向 vitest 暴露内部 state**

Vue 3.5 `<script setup>` 组件默认不对外暴露。在 `onMounted` 之前新增：

```javascript
defineExpose({
  form,
  isPlatformAdmin,
  createRoleOptions,
  importRoleOptions,
  schoolOptions,
  selectedSchool,
  openCreate,
  handleSave,
})
```

这是 vitest `wrapper.vm.xxx` 读写通道。**注意**：R1-F004 改造后需同时暴露 `createRoleOptions` 和 `importRoleOptions`（不再是单一的 `roleOptions`）。

- [ ] **Step 2.10: 运行 vitest 确认 5 个测试全 PASS**

Run:
```bash
cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/pages/__tests__/TeachersPage.cross-school.test.js
```

Expected: 5/5 PASS。

- [ ] **Step 2.11: 运行前端全量 vitest 确认无回归**

Run:
```bash
cd /home/ops/projects/edu-cloud/frontend && npx vitest run
```

基线（frontmatter baseline_verified_at 2026-04-24T23:16+08:00）：**249 passed / 1 failed / 250 total**（1 failed 为 `frontend/src/__tests__/config.test.js::sidebar config parent has minimal items` 既有技术债）。
Expected (post Task 2): **254 passed / 1 failed / 255 total**（+5 为本 plan 新增，既有 1 failed 不应增多）。

- [ ] **Step 2.12: ESLint 通过（本会话已加的 prebuild gate）**

Run:
```bash
cd /home/ops/projects/edu-cloud/frontend && npm run lint
```

Expected: 0 errors。

- [ ] **Step 2.13: 前端 build（铁律：改代码必须 build 才能在 mcu.asia 看到）**

Run:
```bash
cd /home/ops/projects/edu-cloud/frontend && npx vite build 2>&1 | tail -10
```

Expected: `✓ built in ...s`，无错误。产物写入 `frontend/dist/`。

- [ ] **Step 2.14: git add + commit**

```bash
cd /home/ops/projects/edu-cloud && git add \
  frontend/src/pages/TeachersPage.vue \
  frontend/src/pages/__tests__/TeachersPage.cross-school.test.js \
  frontend/src/api/schools.js
git commit -m "$(cat <<'EOF'
feat(teachers): add platform_admin cross-school selector on TeachersPage

- isPlatformAdmin computed from auth.currentRole.role
- initSchools() async: platform_admin -> listSchools(); others -> auth.roles[].context
- createRoleOptions computed (cross-school -> principal + academic_director)
- importRoleOptions static full set (R1-F004 Excel import path unchanged)
- openCreate resets form.roles=['principal'] when platform_admin + selectedSchool (R1-F003)
- handleSave payload injects school_id only when (isPlatformAdmin && selectedSchool)
- school-select v-if extended to (isPlatformAdmin || schoolOptions.length > 1)
- data-testid="school-select" for DOM-level test (R1-F005)
- defineExpose exposes createRoleOptions/importRoleOptions for vitest
- 5 vitest contract locks cover ORC-003/ORC-004 + R1-F003/F004/F005

Design: docs/plans/2026-04-24-super-admin-cross-school-account-design.md
Plan: docs/plans/2026-04-24-super-admin-cross-school-account-plan.md Task 2
EOF
)"
```

---

## Task 3: 端到端闭环验证（mcu.asia 手动走查 + cleanup）

**Files:** 无代码改动，仅验证 + handoff 更新。

**测试契约（5 字段）:**
- 入口: 浏览器访问 `https://mcu.asia`，admin/123456 登录
- 反例: 用 `subject_teacher` 账号登录，`/teachers` 页面 DOM 中无 `[data-testid="school-select"]`
- 边界（≥3，R1-F007）:
  1. 超管选中某校 + 点"添加教师" → 角色下拉**仅显示**"校长"+"教务主任"
  2. 超管跨校打开弹窗 + **不手改角色** + 填名字保存 → 实际创建的角色是 `principal`（R1-F003 前端守卫生效）
  3. 超管 Excel 导入入口 → 默认角色下拉显示全集 9 个角色（R1-F004 导入路径不退化）
  4. 非超管账号 → DOM 无学校下拉（ORC-003）
- 回归: admin 切换学校 → 教师列表按 `GET /teachers?school_id=<newId>` 切换
- 命令: 无单命令；以下步骤 manual 执行

**审查清单（R1-F007）:**
- [ ] 所有手动步骤的 token 键使用 `'token'`（R1-F006，不是 `edu_cloud_token`）
- [ ] 场景 A 创建的景炎试用校长账号在走查结束时有 cleanup 步骤
- [ ] 场景 D 创建的 YC 试用校长账号在走查结束时有 cleanup 步骤
- [ ] 前端 build 产物 mtime 晚于 Task 2 Step 2.14 commit 时间

- [ ] **Step 3.1: 确认前端 build 产物已被 nginx serve**

```bash
ls -la /home/ops/projects/edu-cloud/frontend/dist/index.html
```

Expected: 文件存在且 mtime 与 Task 2 Step 2.13 build 时间相符。

- [ ] **Step 3.2: 确认后端已加载新 router 代码（Task 1 改了 Python 代码）**

```bash
ps -ef | grep uvicorn | grep -v grep | head -5
```

若 uvicorn 以 `--reload` 启动会自动热加载；否则由用户决定是否重启服务（本步不自动重启，避免服务中断）。

- [ ] **Step 3.3: 浏览器手动走查 4 场景（用户执行，Claude 不自动化）**

场景 A（超管跨校创建 principal + R1-F003 前端守卫）：
1. 浏览器打开 `https://mcu.asia`，硬刷（Ctrl+Shift+R）
2. admin / 123456 登录
3. 左侧栏 → 教师管理
4. 顶部"学校"下拉可见，含至少"景炎初级中学" + "育才实验中学"
5. 选"景炎初级中学"
6. 点"添加教师"
7. 角色下拉**仅显示**"校长" / "教务主任"两项
8. 填姓名=`景炎试用校长_ABCD`、工号=`pri_try_abcd`、**不改角色下拉**（保持显示"校长"）
9. 点保存 → 预期："添加成功"
10. 校验：新账号在教师列表中 role 标签显示"校长"（即 `principal`，R1-F003 守卫生效）

场景 B（非超管 DOM 级反例 / R1-F005）：
1. 右上角退出登录
2. 用场景 A 建的景炎试用校长账号登录（密码 123456）
3. 左侧栏 → 教师管理
4. 打开 DevTools Console 执行：`document.querySelector('[data-testid="school-select"]')`
5. 预期：返回 **`null`**（DOM 无下拉，ORC-003）
6. 教师列表只显示景炎本校教师

场景 C（非超管跨校被 403 / R1-F006 token 键修正）：
1. 景炎校长账号下，DevTools Console 执行：
   ```js
   fetch('/api/v1/teachers', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('token')}` },
     body: JSON.stringify({ username: 'evil', display_name: 'x', roles: ['principal'], school_id: '<sch_yc_id>' }),
   }).then(r => console.log('status=', r.status))
   ```
   （**R1-F006 修正**：token 键用 `'token'`，不是 `edu_cloud_token`）
2. `<sch_yc_id>` 替换为育才实验中学真实 id（场景 D 先查到 UUID）
3. 预期：console 打印 `status= 403`（ORC-002）

场景 D（超管切校回归 + YC 试用校长）：
1. 退出再 admin 登录
2. 选"育才实验中学" → 教师列表切换（GET /teachers?school_id=<YC_id>）
3. "添加教师"，填姓名=`YC试用校长_ABCD`、工号=`yc_pri_try_abcd`、角色=校长，保存 → 201
4. 切回"景炎初级中学" → 列表切换为景炎教师

- [ ] **Step 3.4: 清理试用账号（R1-F006 cleanup 强制步骤）**

admin 登录，在 `/teachers` 页面找到并删除以下两个试用账号：
- `景炎试用校长_ABCD`（工号 `pri_try_abcd`）
- `YC试用校长_ABCD`（工号 `yc_pri_try_abcd`）

或通过 API：

```bash
# 获取试用账号 user_id
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://mcu.asia/api/v1/teachers?q=试用" | jq '.[].id'

# 删除（对两个账号分别执行）
curl -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://mcu.asia/api/v1/teachers/<user_id>"
```

Expected: 两个试用账号从教师列表消失；真实景炎/YC 校长账号由用户后续独立创建（非本 plan 产物）。

- [ ] **Step 3.5: 更新 handoff 注明 impl 闭环**

Edit `docs/plans/2026-04-24-super-admin-cross-school-account-handoff.md`，在底部追加：

```markdown

## Impl 闭环（Task 1-3）
- Task 1 commit: <后端 commit sha>
- Task 2 commit: <前端 commit sha>
- 后端全量 pytest: 2168 passed / 23 skipped / ≤3 failed（pre-existing baseline 保持）
- 前端 vitest: 254 passed / 1 failed / 255 total（pre-existing config.test.js 保持）
- mcu.asia 走查：场景 A/B/C/D 全通过 + 试用账号已清理
- 前端 build 产物 mtime: <date>
```

- [ ] **Step 3.6: commit handoff 更新**

```bash
cd /home/ops/projects/edu-cloud && git add docs/plans/2026-04-24-super-admin-cross-school-account-handoff.md
git commit -m "docs(plans): cross-school account impl closure handoff"
```

---

## Gate 触发点

| Gate | 触发时机 | 动作 |
|---|---|---|
| **Gate 1: plan_review** | Plan commit 后 | `codex-review plan`；**R1 FAIL（2026-04-24，3 HIGH + 4 MED）→ R2 修订后重审（本 plan 即 R2 候选）**；R2 仍 FAIL → 拆 topic 或 WONTFIX，禁 R3+ |
| **Gate 2-A: code_review Task 1** | Task 1 Step 1.8 commit 后 | `codex-review code`；per-batch 审，finding 分 defect_fix/test_gap/design_concern 三分（L017） |
| **Gate 2-B: code_review Task 2** | Task 2 Step 2.14 commit 后 | `codex-review code`；同上 |
| **Gate 3: integration review（可选）** | Task 3 Step 3.6 commit 后 | 仅当 Task 1+2 涉及前后端契约变更的整合验证时；本 plan **不强制** |

**Gate 1 预期 finding 类型分布**（供 plan-reviewer 预检准备）：
- 可能 test_gap：前端 `defineExpose` 是否遗漏某个 state；或反例场景（principal 显式本校 / 超管零 school_id / 多角色 primary 是 platform_admin 等）漏锁
- 可能 design_concern：`handleSave` 改动与既有 edit 分支的耦合、`initSchools` async 化对 onMounted 执行顺序的影响
- 可能 defect_fix：`listSchools` 导入路径、`computed` 引入遗漏、`v-if` 条件覆盖

**L017 提醒**：GPT reviewer 的 `design_concern` 建议**仅供设计者决策**，GPT 禁止直接给出替代设计或重构方案；Executor 不直接采纳 design_concern，必须经 Planner / 用户裁定。

---

## Self-Review 检查清单

**1. Spec 覆盖**（对照 design.md 逐段）:
- [x] design §2 架构：TeachersPage 入口 + 超管选校 + 权限判定 + 落库 → Task 2 + Task 1 覆盖
- [x] design §3.1 TeacherCreate 加 school_id → Step 1.3
- [x] design §3.2 router 逻辑重写 → Step 1.4（纠正 design §3.3 对 require_permission 的签名描述）
- [x] design §4.1-4.5 前端学校下拉 / 表格切换 / 角色限制 / payload / listTeachers → Task 2 全覆盖（`api/teachers.js` 零改动）
- [x] design §5 测试策略 → Step 1.1（后端 7 场景含 R1-F001）+ Step 2.1（前端 5 场景含 R1-F003/F005）
- [x] design §6 影响面 + 非目标 → Plan 顶部 Scope Check + File Structure 已列
- [x] design §7 Evidence Block → 本 plan Evidence 摘要段
- [x] design §8 semantic_regression ORC-001~004 → 本 plan semantic_regression 段（ORC-004 明确"后端不做白名单 + UI + openCreate 双护航"）
- [x] design §9 writing-plans 阶段必读 → Task 拆分 + 测试契约 5 字段齐全
- [x] design §10 bootstrap 路径闭环 → Task 3 Step 3.3 场景 A 覆盖（试用账号 cleanup 保证不残留）

**2. Placeholder scan:**
- [x] 无 TBD/TODO/implement later
- [x] 每个代码 step 都有完整代码块
- [x] 测试代码完整可执行
- [x] 命令行具体到绝对路径 + 期望输出

**3. Type consistency:**
- [x] `TeacherCreate.school_id` 类型 `str | None = None` 一致贯穿测试与实现
- [x] `is_cross_school` bool 判断式前后端逻辑等价
- [x] `createRoleOptions` / `importRoleOptions` 命名一致（模板 L78/L102 绑定 + defineExpose + 测试断言）
- [x] `isPlatformAdmin` computed 返回 bool，模板 `v-if` + JS `.value` 一致
- [x] `UserRole.school_id` 使用 `target_school_id` 局部变量，作用域隔离
- [x] `data-testid="school-select"` 命名一致（模板 + 前端测试 + 场景 B 浏览器 console）

**4. 测试契约 5 字段完备性**（首轮 PASS 率治理目标）:
- [x] Task 1 入口 / 反例 / 边界 / 回归 / 命令 五项齐全
- [x] Task 2 入口 / 反例 / 边界 / 回归 / 命令 五项齐全
- [x] Task 3 入口 / 反例 / 边界 / 回归 / 命令 五项齐全（手动走查场景 A/B/C/D 覆盖四维 + cleanup）
- [x] **反例字段**是首轮 PASS 率治理优先级最高项——已具体到 403 / 422 / DOM null + 调用路径

**5. L017 semantic_regression 不变量可回放**:
- [x] ORC-001 → Step 1.1 `test_platform_admin_without_school_id_returns_422`
- [x] ORC-002 → Step 1.1 `test_subject_teacher_cross_school_returns_403` + `test_principal_cross_school_returns_403`
- [x] ORC-003 → Step 2.1 测试 1（超管 DOM 渲染）+ 测试 2（非超管 DOM 不渲染）（R1-F005 DOM 级）
- [x] ORC-004 后端（R1-F001）→ Step 1.1 `test_platform_admin_creates_subject_teacher_cross_school`
- [x] ORC-004 前端（R1-F003）→ Step 2.1 `超管跨校 openCreate 未手改角色 handleSave payload.roles === ['principal']` + `createRoleOptions.length === 2`

**6. CLAUDE.md 铁律检查**:
- [x] L018 ECS 单一环境：无 legacy 环境路径 / 数字 / handoff 时序引用
- [x] L017 plan 含 semantic_regression（4 条不变量 + R1-F001/F003 强化）
- [x] L014 派生任务降级：总 LOC ≈ 350，文件数 4-5 → 维持 T3，不升 T4
- [x] L016 SQLite 禁拷贝：本 plan 不涉及 db 拷贝
- [x] T3 TDD 完整：每个 Task 红 → 绿 → commit
- [x] 决策证据纪律：关键判断均有 file:line 证据（Evidence 摘要段）
- [x] 每 Task 含"审查清单"+"边界条件 ≥3" → R1-F007 补齐
- [x] 每次手动走查 token 键使用 `'token'` → R1-F006 修正

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-04-24-super-admin-cross-school-account-plan.md`.

**执行方式（由用户在新会话决定）:**

**1. Subagent-Driven（推荐 T3）** — Planner 调度，每 Task 派独立 executor subagent，Task 间 codex-review 二阶段审查

**2. Inline Execution** — 在新会话内直接 `superpowers:executing-plans`，Task 间 checkpoint

**不可同会话执行:** session_guard 禁止本会话 `writing-plans → executing-plans`（CLAUDE.md 规则）。

**新会话启动命令参考（待 R2 PASS 后）:**
```
启动新会话：T3 执行 docs/plans/2026-04-24-super-admin-cross-school-account-plan.md。plan_review R1 FAIL → 本 plan R1 revision 修订完成，等 R2 审查结果。若 R2 PASS 直接进 Task 1；若 R2 FAIL 查 handoff 指示是否拆 topic / WONTFIX。
```
