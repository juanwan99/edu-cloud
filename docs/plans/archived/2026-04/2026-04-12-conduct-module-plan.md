<!-- pre-takeover: archived for history, not active spec -->
# 德育板块（Conduct Module）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 class-points 系统全量吸收为 edu-cloud 德育模块，家长端优先。

**Architecture:** 新增 `modules/conduct/` 后端模块（8 张表、35 API）+ `pages/conduct/` 管理端 + `pages/parent/` 家长端 + ParentLayout。复用 edu-cloud 用户体系、RBAC、scope filter、Agent 系统。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic + Vue 3 + Naive UI + ECharts + Pinia

**设计文档:** `docs/plans/2026-04-12-conduct-module-design.md`

---

## File Structure

### Backend — Create

| 文件 | 职责 |
|------|------|
| `src/edu_cloud/modules/conduct/__init__.py` | 包入口 |
| `src/edu_cloud/modules/conduct/models.py` | 8 张表 ORM 定义 |
| `src/edu_cloud/modules/conduct/schemas.py` | Pydantic 请求/响应模型 |
| `src/edu_cloud/modules/conduct/crypto.py` | AES-256-GCM 加密（从 class-points 迁移） |
| `src/edu_cloud/modules/conduct/permissions.py` | conduct 权限检查辅助函数 |
| `src/edu_cloud/modules/conduct/parent_router.py` | 家长端 API（注册/登录/绑定/查询） |
| `src/edu_cloud/modules/conduct/parent_service.py` | 家长端业务逻辑 |
| `src/edu_cloud/modules/conduct/admin_router.py` | 管理端 API（积分/班规/小组/配置） |
| `src/edu_cloud/modules/conduct/admin_service.py` | 管理端业务逻辑 |
| `src/edu_cloud/modules/conduct/export_service.py` | Excel/PDF 导出 |
| `src/edu_cloud/ai/tools/conduct.py` | 6 个 Agent 工具 |
| `alembic/versions/xxxx_add_conduct_tables.py` | Alembic 迁移 |
| `tests/test_conduct/__init__.py` | 测试包 |
| `tests/test_conduct/conftest.py` | conduct 测试 fixtures |
| `tests/test_conduct/test_models.py` | 模型单测 |
| `tests/test_conduct/test_parent_api.py` | 家长端 API 测试 |
| `tests/test_conduct/test_admin_api.py` | 管理端 API 测试 |
| `tests/test_conduct/test_crypto.py` | 加密模块测试 |
| `tests/test_conduct/test_permissions.py` | 权限测试 |
| `tests/test_conduct/test_agent_tools.py` | Agent 工具测试 |
| `frontend/src/layouts/ParentLayout.vue` | 家长端布局 |
| `frontend/src/pages/parent/ParentLogin.vue` | 家长登录 |
| `frontend/src/pages/parent/ParentRegister.vue` | 家长注册 |
| `frontend/src/pages/parent/ParentBind.vue` | 绑定孩子 |
| `frontend/src/pages/parent/ParentOverview.vue` | 积分概览 |
| `frontend/src/pages/parent/ParentDetails.vue` | 详细信息 |
| `frontend/src/pages/parent/ParentRankings.vue` | 排行榜 |
| `frontend/src/pages/parent/ParentRules.vue` | 班规查看 |
| `frontend/src/pages/parent/ParentProfile.vue` | 个人中心 |
| `frontend/src/pages/conduct/ConductDashboard.vue` | 德育概览 |
| `frontend/src/pages/conduct/ConductPoints.vue` | 积分操作 |
| `frontend/src/pages/conduct/ConductRules.vue` | 班规管理 |
| `frontend/src/pages/conduct/ConductRankings.vue` | 排行榜 |
| `frontend/src/pages/conduct/ConductRecords.vue` | 积分记录 |
| `frontend/src/pages/conduct/ConductGroups.vue` | 小组管理 |
| `frontend/src/pages/conduct/ConductSettings.vue` | 德育设置 |
| `frontend/src/pages/conduct/ConductExport.vue` | 数据导出 |
| `frontend/src/pages/conduct/ConductParents.vue` | 家长管理 |
| `frontend/src/api/conduct.js` | API 调用层 |

### Backend — Modify

| 文件 | 变更 |
|------|------|
| `src/edu_cloud/core/permissions.py` | 新增 5 个 Permission + ROLE_PERMISSIONS 扩展 |
| `src/edu_cloud/models/school_settings.py` | MODULE_CODES 加 `"conduct"` |
| `src/edu_cloud/api/app.py` | include_router 注册 conduct 路由 |
| `src/edu_cloud/ai/tools/__init__.py` | import conduct 工具模块 |

### Frontend — Modify

| 文件 | 变更 |
|------|------|
| `frontend/src/router/index.js` | 新增 conduct + parent 路由 |
| `frontend/src/config/permissions.js` | 新增 5 个 conduct 权限 |
| `frontend/src/config/sidebarConfig.js` | 追加德育导航分组 |

---

## Batch 1: 数据基础（Task 1-3）

### Task 1: ORM 模型 + Alembic 迁移

**Files:**
- Create: `src/edu_cloud/modules/conduct/__init__.py`
- Create: `src/edu_cloud/modules/conduct/models.py`
- Create: `alembic/versions/xxxx_add_conduct_tables.py`
- Create: `tests/test_conduct/__init__.py`
- Create: `tests/test_conduct/test_models.py`

- [ ] **Step 1: 创建 conduct 包和 models.py**

```python
# src/edu_cloud/modules/conduct/__init__.py
# Conduct module — 德育板块
```

```python
# src/edu_cloud/modules/conduct/models.py
"""德育板块 ORM 模型 — 8 张表"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, JSON,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class StudentProfile(Base, IdMixin, TimestampMixin):
    """学生 PII 扩展（一对一关联 students 表）"""
    __tablename__ = "student_profiles"

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), unique=True, nullable=False,
    )
    avatar: Mapped[str | None] = mapped_column(String(10))
    birth_date: Mapped[datetime | None] = mapped_column(Date)
    ethnicity: Mapped[str | None] = mapped_column(String(20))
    id_card_number: Mapped[str | None] = mapped_column(Text)  # AES encrypted
    blood_type: Mapped[str | None] = mapped_column(String(5))
    health_notes: Mapped[str | None] = mapped_column(Text)
    home_address: Mapped[str | None] = mapped_column(Text)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(50))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20))
    verify_code: Mapped[str | None] = mapped_column(Text)  # AES encrypted


class ConductClassConfig(Base, IdMixin, TimestampMixin):
    """班级德育配置"""
    __tablename__ = "conduct_class_config"

    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id"), unique=True, nullable=False,
    )
    invite_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    verify_code_type: Mapped[str] = mapped_column(String(10), default="id_card")
    required_parent_fields: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ConductRuleCategory(Base, IdMixin):
    """班规分类"""
    __tablename__ = "conduct_rule_categories"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    class_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("classes.id"))
    school_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("schools.id"))
    scope: Mapped[str] = mapped_column(String(10), nullable=False)  # class / school
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )


class ConductRuleItem(Base, IdMixin):
    """班规子项"""
    __tablename__ = "conduct_rule_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conduct_rule_categories.id"), nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ConductRecord(Base, IdMixin):
    """积分记录"""
    __tablename__ = "conduct_records"

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), nullable=False,
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id"), nullable=False,
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    operator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    source: Mapped[str] = mapped_column(String(10), default="manual")
    rule_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conduct_rule_items.id"),
    )
    semester_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conduct_semesters.id"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )


class ConductGroup(Base, IdMixin):
    """小组"""
    __tablename__ = "conduct_groups"
    __table_args__ = (UniqueConstraint("class_id", "name", name="uq_conduct_group_class_name"),)

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id"), nullable=False,
    )
    avatar: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )


class ConductGroupMember(Base, IdMixin):
    """小组成员"""
    __tablename__ = "conduct_group_members"
    __table_args__ = (UniqueConstraint("student_id", "group_id", name="uq_conduct_gm_student_group"),)

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), nullable=False,
    )
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conduct_groups.id"), nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )


class ConductSemester(Base, IdMixin):
    """学期"""
    __tablename__ = "conduct_semesters"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    school_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("schools.id"))
    class_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("classes.id"))
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
```

- [ ] **Step 2: 生成 Alembic 迁移**

```bash
cd C:/Users/Administrator/edu-cloud
python -m alembic revision --autogenerate -m "add conduct module tables"
```

检查生成的迁移文件，确认 8 张表（student_profiles, conduct_class_config, conduct_rule_categories, conduct_rule_items, conduct_records, conduct_groups, conduct_group_members, conduct_semesters）和所有唯一约束都正确。

- [ ] **Step 3: 写模型测试**

```python
# tests/test_conduct/__init__.py

# tests/test_conduct/test_models.py
"""Conduct 模型基础测试：确认 8 张表可正常创建和查询"""
import pytest
from sqlalchemy import select

from edu_cloud.modules.conduct.models import (
    ConductClassConfig,
    ConductGroup,
    ConductGroupMember,
    ConductRecord,
    ConductRuleCategory,
    ConductRuleItem,
    ConductSemester,
    StudentProfile,
)


@pytest.mark.asyncio
async def test_student_profile_create(db):
    """student_profiles 表可创建记录"""
    from tests.test_conduct.conftest import _make_school_class_student
    school, cls, student = await _make_school_class_student(db)

    profile = StudentProfile(student_id=student.id, avatar="🐱", ethnicity="汉族")
    db.add(profile)
    await db.commit()

    result = await db.execute(
        select(StudentProfile).where(StudentProfile.student_id == student.id)
    )
    row = result.scalar_one()
    assert row.avatar == "🐱"
    assert row.ethnicity == "汉族"


@pytest.mark.asyncio
async def test_conduct_class_config_unique_invite(db):
    """invite_code 唯一约束"""
    from tests.test_conduct.conftest import _make_school_class_student
    school, cls, _ = await _make_school_class_student(db)

    config = ConductClassConfig(class_id=cls.id, invite_code="ABC123")
    db.add(config)
    await db.commit()
    assert config.verify_code_type == "id_card"  # default


@pytest.mark.asyncio
async def test_conduct_record_create(db):
    """积分记录可正常创建"""
    from tests.test_conduct.conftest import _make_school_class_student
    school, cls, student = await _make_school_class_student(db)
    from tests.conftest import _make_user
    teacher = await _make_user(db, "teacher1", "subject_teacher", school.id)

    from datetime import date
    record = ConductRecord(
        student_id=student.id, class_id=cls.id, points=3,
        reason="课堂表现好", date=date.today(), operator_id=teacher.id,
    )
    db.add(record)
    await db.commit()
    assert record.source == "manual"


@pytest.mark.asyncio
async def test_conduct_group_unique_constraint(db):
    """同班级内小组名唯一"""
    from tests.test_conduct.conftest import _make_school_class_student
    school, cls, _ = await _make_school_class_student(db)

    g1 = ConductGroup(name="第一组", class_id=cls.id, avatar="🦁")
    db.add(g1)
    await db.commit()

    from sqlalchemy.exc import IntegrityError
    g2 = ConductGroup(name="第一组", class_id=cls.id)
    db.add(g2)
    with pytest.raises(IntegrityError):
        await db.commit()
```

- [ ] **Step 4: 创建 conduct 测试 conftest**

```python
# tests/test_conduct/conftest.py
"""Conduct 模块测试 fixtures"""
import pytest

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import RegisteredSchool
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.conduct.models import ConductClassConfig
from edu_cloud.shared.auth import create_access_token


async def _make_school_class_student(db):
    """创建学校 → 班级 → 学生三件套"""
    school = RegisteredSchool(name="测试中学", code="TEST2026", is_active=True)
    db.add(school)
    await db.flush()

    cls = Class(name="高一(1)班", grade="高一", grade_number=1,
                school_id=school.id)
    db.add(cls)
    await db.flush()

    student = Student(name="张三", student_number="2026001",
                      class_id=cls.id, school_id=school.id)
    db.add(student)
    await db.commit()
    return school, cls, student


async def _make_user(db, username, role, school_id, class_ids=None):
    """创建用户 + 角色"""
    user = User(username=username, display_name=username)
    user.set_password("test123")
    db.add(user)
    await db.flush()
    ur = UserRole(user_id=user.id, role=role, school_id=school_id,
                  is_primary=True, class_ids=class_ids)
    db.add(ur)
    await db.commit()
    return user


def _auth_headers(user, role="subject_teacher"):
    token = create_access_token({"sub": user.id, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def school_class_student(db):
    return await _make_school_class_student(db)


@pytest.fixture
async def homeroom_teacher(db, school_class_student):
    school, cls, _ = school_class_student
    user = await _make_user(db, "teacher_hr", "homeroom_teacher",
                            school.id, class_ids=[cls.id])
    return user


@pytest.fixture
async def homeroom_headers(homeroom_teacher):
    return _auth_headers(homeroom_teacher, "homeroom_teacher")


@pytest.fixture
async def conduct_config(db, school_class_student):
    """创建班级德育配置（含邀请码）"""
    _, cls, _ = school_class_student
    config = ConductClassConfig(
        class_id=cls.id, invite_code="TEST01",
        verify_code_type="custom",
    )
    db.add(config)
    await db.commit()
    return config
```

- [ ] **Step 5: 运行测试**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/test_models.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/conduct/ alembic/versions/*conduct* tests/test_conduct/
git commit -m "feat(conduct): add 8 ORM models + Alembic migration"
```

**审查清单:**
- ✓ 8 张表定义与 design.md §1 一致
- ✓ 所有 FK 引用已有表（students, classes, schools, users）
- ✓ UniqueConstraint 存在于 conduct_groups (class_id+name), conduct_group_members (student_id+group_id), conduct_class_config (class_id, invite_code)
- ✓ student_profiles.student_id 是 unique 一对一
- ✓ IdMixin + TimestampMixin 复用 edu-cloud 基类
- ✗ 没有修改任何已有表

---

### Task 2: Permission 扩展 + 模块开关

**Files:**
- Modify: `src/edu_cloud/core/permissions.py`
- Modify: `src/edu_cloud/models/school_settings.py`
- Create: `tests/test_conduct/test_permissions.py`

- [ ] **Step 1: 写权限测试**

```python
# tests/test_conduct/test_permissions.py
"""Conduct 权限测试"""
import pytest
from edu_cloud.core.permissions import Permission, has_permission


def test_conduct_permissions_exist():
    """5 个 conduct 权限存在"""
    assert Permission.VIEW_CONDUCT
    assert Permission.MANAGE_CONDUCT
    assert Permission.MANAGE_CONDUCT_RULES
    assert Permission.MANAGE_CONDUCT_PARENTS
    assert Permission.EXPORT_CONDUCT


def test_homeroom_teacher_has_all_conduct_perms():
    assert has_permission("homeroom_teacher", Permission.VIEW_CONDUCT)
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT)
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT_RULES)
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT_PARENTS)
    assert has_permission("homeroom_teacher", Permission.EXPORT_CONDUCT)


def test_subject_teacher_has_view_and_manage():
    assert has_permission("subject_teacher", Permission.VIEW_CONDUCT)
    assert has_permission("subject_teacher", Permission.MANAGE_CONDUCT)
    assert not has_permission("subject_teacher", Permission.MANAGE_CONDUCT_RULES)
    assert not has_permission("subject_teacher", Permission.MANAGE_CONDUCT_PARENTS)


def test_parent_has_view_only():
    assert has_permission("parent", Permission.VIEW_CONDUCT)
    assert not has_permission("parent", Permission.MANAGE_CONDUCT)


def test_grade_leader_has_view_manage_export():
    assert has_permission("grade_leader", Permission.VIEW_CONDUCT)
    assert has_permission("grade_leader", Permission.MANAGE_CONDUCT)
    assert has_permission("grade_leader", Permission.EXPORT_CONDUCT)
    assert not has_permission("grade_leader", Permission.MANAGE_CONDUCT_PARENTS)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_conduct/test_permissions.py -v
```

Expected: FAIL — `Permission` 没有 `VIEW_CONDUCT` 等属性

- [ ] **Step 3: 在 Permission enum 中添加 5 个权限**

在 `src/edu_cloud/core/permissions.py` 的 Permission enum 末尾追加：

```python
    # Conduct（德育）
    VIEW_CONDUCT = "view_conduct"
    MANAGE_CONDUCT = "manage_conduct"
    MANAGE_CONDUCT_RULES = "manage_conduct_rules"
    MANAGE_CONDUCT_PARENTS = "manage_conduct_parents"
    EXPORT_CONDUCT = "export_conduct"
```

在 ROLE_PERMISSIONS 中追加到各角色：

- `platform_admin`: 全部 5 个
- `principal`: VIEW_CONDUCT, EXPORT_CONDUCT
- `academic_director`: VIEW_CONDUCT, MANAGE_CONDUCT, MANAGE_CONDUCT_RULES, EXPORT_CONDUCT
- `grade_leader`: VIEW_CONDUCT, MANAGE_CONDUCT, EXPORT_CONDUCT
- `homeroom_teacher`: 全部 5 个
- `subject_teacher`: VIEW_CONDUCT, MANAGE_CONDUCT
- `parent`: VIEW_CONDUCT

- [ ] **Step 4: 在 MODULE_CODES 中添加 conduct**

在 `src/edu_cloud/models/school_settings.py` 的 MODULE_CODES dict 中追加：

```python
    "conduct": "德育管理",
```

不加入 DEFAULT_ENABLED（学校需手动启用）。

- [ ] **Step 5: 运行测试**

```bash
python -m pytest tests/test_conduct/test_permissions.py -v
```

Expected: 5 tests PASS

- [ ] **Step 6: 运行全量测试确认无回归**

```bash
python -m pytest --tb=short -q
```

Expected: 全部 PASS（1582+ tests）

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/core/permissions.py src/edu_cloud/models/school_settings.py tests/test_conduct/test_permissions.py
git commit -m "feat(conduct): add 5 permissions + conduct module code"
```

**审查清单:**
- ✓ 5 个 Permission 与 design.md §2 一致
- ✓ ROLE_PERMISSIONS 角色映射与 design.md §2 角色映射表一致
- ✓ MODULE_CODES 新增 `"conduct": "德育管理"`
- ✗ conduct 不在 DEFAULT_ENABLED 中
- ✗ 前端 permissions.js 暂未修改（Task 9 处理）

---

### Task 3: AES-256-GCM 加密模块

**Files:**
- Create: `src/edu_cloud/modules/conduct/crypto.py`
- Create: `tests/test_conduct/test_crypto.py`

- [ ] **Step 1: 写加密测试**

```python
# tests/test_conduct/test_crypto.py
"""AES-256-GCM 加密/解密测试"""
import pytest
from edu_cloud.modules.conduct.crypto import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    plaintext = "310101200001011234"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext


def test_encrypt_produces_different_ciphertext():
    """每次加密产生不同密文（随机 nonce）"""
    plaintext = "hello"
    c1 = encrypt(plaintext)
    c2 = encrypt(plaintext)
    assert c1 != c2
    assert decrypt(c1) == decrypt(c2) == plaintext


def test_decrypt_invalid_returns_none():
    assert decrypt("not-valid-ciphertext") is None
    assert decrypt("") is None


def test_encrypt_none_returns_none():
    assert encrypt(None) is None
    assert encrypt("") is None
```

- [ ] **Step 2: 实现加密模块**

```python
# src/edu_cloud/modules/conduct/crypto.py
"""AES-256-GCM 加密 — 用于学生身份证号、验证码等 PII 字段"""

import base64
import hashlib
import os
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from edu_cloud.config import settings

logger = logging.getLogger(__name__)

_KEY: bytes | None = None


def _get_key() -> bytes:
    global _KEY
    if _KEY is None:
        raw = getattr(settings, "ENCRYPTION_KEY", "") or "default-dev-key"
        _KEY = hashlib.sha256(raw.encode()).digest()
    return _KEY


def encrypt(plaintext: str | None) -> str | None:
    if not plaintext:
        return None
    key = _get_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        raw = base64.b64decode(ciphertext)
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(_get_key())
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
    except Exception:
        logger.warning("conduct.crypto: decrypt failed")
        return None
```

- [ ] **Step 3: 在 config.py 中确保 ENCRYPTION_KEY 配置项存在**

检查 `src/edu_cloud/config.py`，如果没有 `ENCRYPTION_KEY` 字段则追加：

```python
    ENCRYPTION_KEY: str = "change-me-in-production"
```

- [ ] **Step 4: 运行测试**

```bash
python -m pytest tests/test_conduct/test_crypto.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/conduct/crypto.py tests/test_conduct/test_crypto.py
git commit -m "feat(conduct): add AES-256-GCM crypto module"
```

**审查清单:**
- ✓ encrypt/decrypt 往返一致
- ✓ 随机 nonce 保证每次密文不同
- ✓ 无效输入返回 None，不抛异常
- ✗ 密钥从 settings.ENCRYPTION_KEY 读取，不硬编码

**边界条件:**
- 空字符串 / None → 返回 None
- 非法 base64 密文 → 返回 None，不抛异常
- 密钥变更后旧密文 → 解密返回 None

---

## Batch 2: 家长端后端（Task 4-6）

### Task 4: 家长注册/登录/邀请码 API

**Files:**
- Create: `src/edu_cloud/modules/conduct/schemas.py`
- Create: `src/edu_cloud/modules/conduct/parent_service.py`
- Create: `src/edu_cloud/modules/conduct/parent_router.py`
- Create: `tests/test_conduct/test_parent_api.py`
- Modify: `src/edu_cloud/api/app.py` — 注册 parent_router

- [ ] **Step 1: 写 schemas.py**

```python
# src/edu_cloud/modules/conduct/schemas.py
"""Conduct Pydantic schemas"""
from datetime import date
from pydantic import BaseModel, Field


# ── Parent Auth ──

class InviteCodeInfo(BaseModel):
    class_name: str
    school_name: str
    verify_code_type: str

class ParentRegisterRequest(BaseModel):
    invite_code: str = Field(..., min_length=4, max_length=10)
    display_name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., pattern=r"^1\d{10}$")
    password: str = Field(..., min_length=6)
    relationship: str = Field(default="other")  # 父亲/母亲/其他

class ParentLoginRequest(BaseModel):
    phone: str
    password: str

class ParentBindRequest(BaseModel):
    class_id: str
    student_name: str
    verify_code: str
    relationship: str = Field(default="other")


# ── Conduct Records ──

class AddPointsRequest(BaseModel):
    student_ids: list[str] = Field(..., min_length=1)
    points: int
    reason: str = Field(..., min_length=1)
    rule_item_id: str | None = None
    date: date | None = None

class PointsRecordResponse(BaseModel):
    id: str
    student_id: str
    student_name: str
    points: int
    reason: str
    date: date
    operator_name: str
    source: str
    rule_item_name: str | None = None
    created_at: str


# ── Rules ──

class RuleCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    sort_order: int = 0

class RuleItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    points: int

class RuleCategoryResponse(BaseModel):
    id: str
    name: str
    sort_order: int
    items: list[dict] = []


# ── Groups ──

class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    avatar: str | None = None

class GroupMemberAdd(BaseModel):
    student_ids: list[str]


# ── Config ──

class ConductConfigUpdate(BaseModel):
    verify_code_type: str | None = None
    required_parent_fields: list[str] | None = None
    is_active: bool | None = None
```

- [ ] **Step 2: 写 parent_service.py**

```python
# src/edu_cloud/modules/conduct/parent_service.py
"""家长端业务逻辑"""
import logging
import string
import random
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import RegisteredSchool
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.conduct.models import (
    ConductClassConfig, ConductRecord, ConductRuleCategory,
    ConductRuleItem, StudentProfile,
)
from edu_cloud.modules.conduct.crypto import decrypt
from edu_cloud.shared.auth import create_access_token
from edu_cloud.services.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def generate_invite_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


async def get_invite_info(db: AsyncSession, code: str) -> dict:
    """校验邀请码，返回班级和学校信息"""
    result = await db.execute(
        select(ConductClassConfig, Class, RegisteredSchool)
        .join(Class, ConductClassConfig.class_id == Class.id)
        .join(RegisteredSchool, Class.school_id == RegisteredSchool.id)
        .where(ConductClassConfig.invite_code == code)
        .where(ConductClassConfig.is_active == True)
    )
    row = result.first()
    if not row:
        raise NotFoundError("邀请码无效或已停用")
    config, cls, school = row
    return {
        "class_id": cls.id,
        "class_name": cls.name,
        "school_id": school.id,
        "school_name": school.name,
        "verify_code_type": config.verify_code_type,
    }


async def register_parent(db: AsyncSession, phone: str, display_name: str,
                          password: str, invite_code: str, relationship: str) -> dict:
    """家长注册：创建 user + user_role(parent)"""
    # 检查手机号是否已注册
    existing = await db.execute(
        select(User).where(User.phone == phone)
    )
    if existing.scalar():
        raise ValidationError("该手机号已注册，请直接登录")

    info = await get_invite_info(db, invite_code)

    user = User(
        username=phone,  # 手机号作为用户名
        display_name=display_name,
        phone=phone,
        is_active=True,
    )
    user.set_password(password)
    db.add(user)
    await db.flush()

    role = UserRole(
        user_id=user.id,
        role="parent",
        school_id=info["school_id"],
        is_primary=True,
    )
    db.add(role)
    await db.commit()

    token = create_access_token({
        "sub": user.id,
        "role": "parent",
        "active_role_id": role.id,
    })
    return {"token": token, "user_id": user.id, "class_id": info["class_id"]}


async def login_parent(db: AsyncSession, phone: str, password: str) -> dict:
    """家长登录"""
    result = await db.execute(select(User).where(User.username == phone))
    user = result.scalar()
    if not user or not user.verify_password(password):
        raise ValidationError("手机号或密码错误")

    # 找到 parent role
    role_result = await db.execute(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role == "parent")
    )
    role = role_result.scalar()
    if not role:
        raise ValidationError("该账号不是家长账号")

    token = create_access_token({
        "sub": user.id,
        "role": "parent",
        "active_role_id": role.id,
    })
    return {"token": token, "user_id": user.id}


async def bind_child(db: AsyncSession, user_id: str, class_id: str,
                     student_name: str, verify_code: str, relationship: str) -> dict:
    """绑定孩子（需验证身份）"""
    # 查班级配置
    config_result = await db.execute(
        select(ConductClassConfig).where(ConductClassConfig.class_id == class_id)
    )
    config = config_result.scalar()
    if not config:
        raise NotFoundError("该班级未开启德育模块")

    # 查学生
    student_result = await db.execute(
        select(Student).where(Student.class_id == class_id, Student.name == student_name)
    )
    student = student_result.scalar()
    if not student:
        raise NotFoundError("未找到该学生")

    # 验证身份
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.student_id == student.id)
    )
    profile = profile_result.scalar()

    vtype = config.verify_code_type
    if vtype == "id_card":
        # 从加密的身份证号取后6位比对
        if not profile or not profile.id_card_number:
            raise ValidationError("该学生未录入身份证号，请联系班主任")
        id_card = decrypt(profile.id_card_number) or ""
        if id_card[-6:] != verify_code:
            raise ValidationError("身份证后6位不正确")
    elif vtype in ("phone", "custom"):
        if not profile or not profile.verify_code:
            raise ValidationError("该学生未设置验证码，请联系班主任")
        stored = decrypt(profile.verify_code) or ""
        if stored != verify_code:
            raise ValidationError("验证码不正确")
    else:
        raise ValidationError(f"未知验证方式: {vtype}")

    # 检查是否已绑定
    from edu_cloud.models.user_role import GuardianStudentLink
    existing = await db.execute(
        select(GuardianStudentLink).where(
            GuardianStudentLink.guardian_user_id == user_id,
            GuardianStudentLink.student_id == student.id,
        )
    )
    if existing.scalar():
        raise ValidationError("已绑定该学生")

    link = GuardianStudentLink(
        guardian_user_id=user_id,
        student_id=student.id,
        relationship=relationship,
        school_id=student.school_id,
    )
    db.add(link)
    await db.commit()

    return {"student_id": student.id, "student_name": student.name}


async def get_children(db: AsyncSession, user_id: str) -> list[dict]:
    """获取已绑定孩子列表 + 积分汇总"""
    from edu_cloud.models.user_role import GuardianStudentLink
    result = await db.execute(
        select(GuardianStudentLink, Student, Class)
        .join(Student, GuardianStudentLink.student_id == Student.id)
        .join(Class, Student.class_id == Class.id)
        .where(GuardianStudentLink.guardian_user_id == user_id)
    )
    children = []
    for link, student, cls in result.all():
        # 统计积分
        points_result = await db.execute(
            select(func.coalesce(func.sum(ConductRecord.points), 0))
            .where(ConductRecord.student_id == student.id)
        )
        total_points = points_result.scalar()

        children.append({
            "student_id": student.id,
            "student_name": student.name,
            "class_id": cls.id,
            "class_name": cls.name,
            "total_points": total_points,
            "relationship": link.relationship,
        })
    return children
```

- [ ] **Step 3: 写 parent_router.py**

```python
# src/edu_cloud/modules/conduct/parent_router.py
"""家长端 API 路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.modules.conduct import parent_service as svc
from edu_cloud.modules.conduct.schemas import (
    ParentRegisterRequest, ParentLoginRequest, ParentBindRequest,
)

router = APIRouter(prefix="/api/v1/conduct", tags=["conduct-parent"])


@router.get("/invite/{code}/info")
async def get_invite_info(code: str, db: AsyncSession = Depends(get_db)):
    return await svc.get_invite_info(db, code)


@router.post("/parent/register")
async def register_parent(req: ParentRegisterRequest, db: AsyncSession = Depends(get_db)):
    return await svc.register_parent(
        db, req.phone, req.display_name, req.password,
        req.invite_code, req.relationship,
    )


@router.post("/parent/login")
async def login_parent(req: ParentLoginRequest, db: AsyncSession = Depends(get_db)):
    return await svc.login_parent(db, req.phone, req.password)


@router.get("/parent/me")
async def get_parent_me(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    children = await svc.get_children(db, user_id)
    return {"user_id": user_id, "children": children}


@router.post("/parent/bind")
async def bind_child(
    req: ParentBindRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await svc.bind_child(
        db, current_user["user_id"],
        req.class_id, req.student_name, req.verify_code, req.relationship,
    )


@router.get("/parent/children")
async def get_children(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await svc.get_children(db, current_user["user_id"])
```

- [ ] **Step 4: 在 app.py 注册路由**

在 `src/edu_cloud/api/app.py` 中 import 并注册：

```python
from edu_cloud.modules.conduct.parent_router import router as conduct_parent_router
# ... 在 include_router 区域追加：
app.include_router(conduct_parent_router)
```

- [ ] **Step 5: 写家长端 API 测试**

```python
# tests/test_conduct/test_parent_api.py
"""家长端 API 集成测试"""
import pytest
from httpx import AsyncClient

from edu_cloud.modules.conduct.models import StudentProfile, ConductClassConfig
from edu_cloud.modules.conduct.crypto import encrypt


@pytest.mark.asyncio
async def test_invite_code_info(client: AsyncClient, conduct_config, school_class_student):
    """GET /invite/{code}/info 返回班级和学校信息"""
    resp = await client.get("/api/v1/conduct/invite/TEST01/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["verify_code_type"] == "custom"
    assert "class_name" in data


@pytest.mark.asyncio
async def test_invite_code_invalid(client: AsyncClient):
    """无效邀请码返回 404"""
    resp = await client.get("/api/v1/conduct/invite/BADCODE/info")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_parent_register_and_login(client: AsyncClient, conduct_config):
    """注册 → 登录 → 获取信息"""
    # 注册
    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "TEST01",
        "display_name": "张妈妈",
        "phone": "13800000001",
        "password": "test123",
        "relationship": "母亲",
    })
    assert resp.status_code == 200
    assert "token" in resp.json()

    # 登录
    resp = await client.post("/api/v1/conduct/parent/login", json={
        "phone": "13800000001",
        "password": "test123",
    })
    assert resp.status_code == 200
    token = resp.json()["token"]

    # 获取信息
    resp = await client.get("/api/v1/conduct/parent/me",
                            headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["children"] == []  # 尚未绑定


@pytest.mark.asyncio
async def test_parent_register_duplicate_phone(client: AsyncClient, conduct_config):
    """重复手机号注册返回 400"""
    body = {"invite_code": "TEST01", "display_name": "A",
            "phone": "13800000002", "password": "test123"}
    await client.post("/api/v1/conduct/parent/register", json=body)
    resp = await client.post("/api/v1/conduct/parent/register", json=body)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_parent_bind_child(client: AsyncClient, db, conduct_config, school_class_student):
    """绑定孩子（custom 验证码）"""
    _, cls, student = school_class_student

    # 设置验证码
    profile = StudentProfile(student_id=student.id, verify_code=encrypt("mycode"))
    db.add(profile)
    await db.commit()

    # 注册家长
    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "TEST01", "display_name": "张爸爸",
        "phone": "13800000003", "password": "test123",
    })
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 绑定
    resp = await client.post("/api/v1/conduct/parent/bind", json={
        "class_id": cls.id, "student_name": student.name,
        "verify_code": "mycode", "relationship": "父亲",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["student_name"] == student.name

    # 验证绑定结果
    resp = await client.get("/api/v1/conduct/parent/children", headers=headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["student_name"] == student.name


@pytest.mark.asyncio
async def test_parent_bind_wrong_code(client: AsyncClient, db, conduct_config, school_class_student):
    """验证码错误 → 400"""
    _, cls, student = school_class_student
    profile = StudentProfile(student_id=student.id, verify_code=encrypt("correct"))
    db.add(profile)
    await db.commit()

    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": "TEST01", "display_name": "X",
        "phone": "13800000004", "password": "test123",
    })
    token = resp.json()["token"]

    resp = await client.post("/api/v1/conduct/parent/bind", json={
        "class_id": cls.id, "student_name": student.name,
        "verify_code": "wrong", "relationship": "父亲",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400
```

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/test_conduct/test_parent_api.py -v
```

Expected: 6 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/conduct/schemas.py src/edu_cloud/modules/conduct/parent_service.py src/edu_cloud/modules/conduct/parent_router.py src/edu_cloud/api/app.py tests/test_conduct/test_parent_api.py
git commit -m "feat(conduct): parent register/login/bind API"
```

**审查清单:**
- ✓ 邀请码校验返回班级+学校信息
- ✓ 手机号唯一约束（注册时检查）
- ✓ 绑定时验证身份（3 种验证类型）
- ✓ 已绑定检查（防重复绑定）
- ✓ 注册后自动返回 JWT
- ✗ 公开端点无需认证（register/login/invite-info）
- ✗ 绑定/查询端点需要认证

**边界条件:**
- 无效邀请码 → 404
- 重复手机号 → 400 "已注册"
- 学生无验证码 → 400 "请联系班主任"
- 验证码错误 → 400
- 重复绑定同一学生 → 400

**测试契约:**
1. 邀请码校验返回正确信息
   - 入口: `GET /api/v1/conduct/invite/{code}/info`
   - 反例: 错误实现可能不检查 is_active=True，导致停用的邀请码仍可访问
   - 边界: 无效码 / 停用码 / 正常码
   - 回归: N/A
   - 命令: `pytest tests/test_conduct/test_parent_api.py::test_invite_code_info -v`
2. 绑定需验证码正确
   - 入口: `POST /api/v1/conduct/parent/bind`
   - 反例: 错误实现可能跳过验证码比对，任何人都能绑定任何孩子
   - 边界: 正确验证码 / 错误验证码 / 学生无验证码
   - 回归: N/A
   - 命令: `pytest tests/test_conduct/test_parent_api.py::test_parent_bind_child -v`

---

### Task 5: 家长端查询 API（积分明细 + 排行榜 + 班规）

**Files:**
- Modify: `src/edu_cloud/modules/conduct/parent_service.py`
- Modify: `src/edu_cloud/modules/conduct/parent_router.py`
- Modify: `tests/test_conduct/test_parent_api.py`

- [ ] **Step 1: 在 parent_service.py 中添加查询函数**

添加 `get_child_records()`、`get_class_rankings()`、`get_class_rules()` 三个函数。

`get_child_records(db, user_id, student_id, page, size)` — 查 ConductRecord + 分页，JOIN operator 获取操作人名。先验证 guardian_student_links 权限。

`get_class_rankings(db, class_id, semester_id=None)` — 按学生分组 SUM(points)，降序排列。

`get_class_rules(db, class_id)` — 查 ConductRuleCategory + ConductRuleItem，按 sort_order 排序，嵌套返回。

- [ ] **Step 2: 在 parent_router.py 中添加路由**

```python
@router.get("/parent/children/{student_id}/records")
async def get_child_records(
    student_id: str,
    page: int = 1, size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await svc.get_child_records(db, current_user["user_id"], student_id, page, size)

@router.get("/parent/children/{student_id}/rankings")
async def get_child_rankings(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await svc.get_child_rankings(db, current_user["user_id"], student_id)

@router.get("/parent/classes/{class_id}/rules")
async def get_class_rules(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await svc.get_class_rules(db, class_id)
```

- [ ] **Step 3: 添加个人信息修改端点**

```python
@router.put("/parent/profile")
async def update_parent_profile(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await svc.update_parent_profile(db, current_user["user_id"], data)

@router.put("/parent/password")
async def change_parent_password(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await svc.change_parent_password(
        db, current_user["user_id"], data["old_password"], data["new_password"],
    )
```

在 parent_service.py 添加 `update_parent_profile()` 和 `change_parent_password()` 函数。

- [ ] **Step 4: 写测试**

测试家长只能查看已绑定孩子的记录（未绑定 → 403），排行榜返回班级全部学生排名，密码修改验证旧密码。

- [ ] **Step 5: 运行测试**

```bash
python -m pytest tests/test_conduct/test_parent_api.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/conduct/parent_service.py src/edu_cloud/modules/conduct/parent_router.py tests/test_conduct/test_parent_api.py
git commit -m "feat(conduct): parent query + profile API"
```

**审查清单:**
- ✓ 家长只能查已绑定孩子的数据（guardian_student_links 检查）
- ✓ 排行榜返回班级全部学生（不限自己的孩子）
- ✓ 班规按 sort_order 排序，子项嵌套在分类下
- ✓ 积分记录分页
- ✓ 修改密码需验证旧密码
- ✓ 个人信息修改只能改 display_name（手机号不可改）

---

### Task 6: 管理端配置 API（邀请码 + 学生验证码设置）

**Files:**
- Create: `src/edu_cloud/modules/conduct/permissions.py`
- Create: `src/edu_cloud/modules/conduct/admin_router.py`
- Create: `src/edu_cloud/modules/conduct/admin_service.py`
- Modify: `src/edu_cloud/api/app.py` — 注册 admin_router

- [ ] **Step 1: 写 permissions.py 权限辅助**

```python
# src/edu_cloud/modules/conduct/permissions.py
"""Conduct 权限检查辅助函数"""
from fastapi import Depends
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission


def require_view_conduct():
    return Depends(require_permission(Permission.VIEW_CONDUCT))

def require_manage_conduct():
    return Depends(require_permission(Permission.MANAGE_CONDUCT))

def require_manage_rules():
    return Depends(require_permission(Permission.MANAGE_CONDUCT_RULES))

def require_manage_parents():
    return Depends(require_permission(Permission.MANAGE_CONDUCT_PARENTS))

def require_export_conduct():
    return Depends(require_permission(Permission.EXPORT_CONDUCT))
```

- [ ] **Step 2: 写 admin_service.py — 配置管理**

包含 `get_config()`, `update_config()`, `regenerate_invite_code()`, `setup_student_verify_code()`, `list_parents()`, `remove_parent()` 函数。

`setup_student_verify_code(db, student_id, verify_code)` — 加密存储到 student_profiles.verify_code。

- [ ] **Step 3: 写 admin_router.py — 配置端点**

```python
# src/edu_cloud/modules/conduct/admin_router.py
router = APIRouter(prefix="/api/v1/conduct", tags=["conduct-admin"])
```

包含 6 个端点：GET/PUT config, POST regenerate-code, GET parents, DELETE parent。

- [ ] **Step 4: 注册路由到 app.py**

- [ ] **Step 5: 写测试**

测试班主任可以获取/更新配置、刷新邀请码、查看家长列表、移除家长绑定。

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/test_conduct/ -v
```

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/conduct/permissions.py src/edu_cloud/modules/conduct/admin_router.py src/edu_cloud/modules/conduct/admin_service.py src/edu_cloud/api/app.py tests/test_conduct/
git commit -m "feat(conduct): admin config API (invite code, parents management)"
```

**审查清单:**
- ✓ 配置端点需要 MANAGE_CONDUCT_PARENTS 权限
- ✓ 刷新邀请码生成新的唯一码
- ✓ 移除家长删除 guardian_student_links 记录
- ✓ 验证码通过 crypto.encrypt 加密存储

---

## Batch 3: 家长端前端（Task 7-9）

### Task 7: 前端路由 + 权限配置 + API 模块

**Files:**
- Create: `frontend/src/api/conduct.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/config/permissions.js`

- [ ] **Step 1: 创建 conduct API 模块**

```javascript
// frontend/src/api/conduct.js
import api from './client'

// ── Parent Auth ──
export const getInviteInfo = (code) => api.get(`/conduct/invite/${code}/info`)
export const parentRegister = (data) => api.post('/conduct/parent/register', data)
export const parentLogin = (data) => api.post('/conduct/parent/login', data)
export const getParentMe = () => api.get('/conduct/parent/me')
export const bindChild = (data) => api.post('/conduct/parent/bind', data)
export const getChildren = () => api.get('/conduct/parent/children')
export const getChildRecords = (studentId, params) =>
  api.get(`/conduct/parent/children/${studentId}/records`, { params })
export const getChildRankings = (studentId) =>
  api.get(`/conduct/parent/children/${studentId}/rankings`)
export const getClassRules = (classId) =>
  api.get(`/conduct/parent/classes/${classId}/rules`)

// ── Admin ──
export const getConductConfig = (classId) =>
  api.get(`/conduct/classes/${classId}/config`)
export const updateConductConfig = (classId, data) =>
  api.put(`/conduct/classes/${classId}/config`, data)
export const regenerateInviteCode = (classId) =>
  api.post(`/conduct/classes/${classId}/config/regenerate-code`)
export const getParentsList = (classId) =>
  api.get(`/conduct/classes/${classId}/parents`)
export const removeParent = (classId, userId) =>
  api.delete(`/conduct/classes/${classId}/parents/${userId}`)

// ── Records ──
export const addPoints = (classId, data) =>
  api.post(`/conduct/classes/${classId}/records`, data)
export const addPointsBatch = (classId, data) =>
  api.post(`/conduct/classes/${classId}/records/batch`, data)
export const getRecords = (classId, params) =>
  api.get(`/conduct/classes/${classId}/records`, { params })
export const deleteRecord = (classId, recordId) =>
  api.delete(`/conduct/classes/${classId}/records/${recordId}`)
export const getStudentRankings = (classId, params) =>
  api.get(`/conduct/classes/${classId}/rankings/students`, { params })
export const getGroupRankings = (classId, params) =>
  api.get(`/conduct/classes/${classId}/rankings/groups`, { params })

// ── Rules ──
export const getRules = (classId) =>
  api.get(`/conduct/classes/${classId}/rules`)
export const createCategory = (classId, data) =>
  api.post(`/conduct/classes/${classId}/rules/categories`, data)
export const updateCategory = (classId, catId, data) =>
  api.put(`/conduct/classes/${classId}/rules/categories/${catId}`, data)
export const deleteCategory = (classId, catId) =>
  api.delete(`/conduct/classes/${classId}/rules/categories/${catId}`)
export const createRuleItem = (classId, catId, data) =>
  api.post(`/conduct/classes/${classId}/rules/categories/${catId}/items`, data)
export const updateRuleItem = (classId, catId, itemId, data) =>
  api.put(`/conduct/classes/${classId}/rules/categories/${catId}/items/${itemId}`, data)
export const deleteRuleItem = (classId, catId, itemId) =>
  api.delete(`/conduct/classes/${classId}/rules/categories/${catId}/items/${itemId}`)

// ── Groups ──
export const getGroups = (classId) =>
  api.get(`/conduct/classes/${classId}/groups`)
export const createGroup = (classId, data) =>
  api.post(`/conduct/classes/${classId}/groups`, data)
export const deleteGroup = (classId, groupId) =>
  api.delete(`/conduct/classes/${classId}/groups/${groupId}`)
export const addGroupMembers = (classId, groupId, data) =>
  api.post(`/conduct/classes/${classId}/groups/${groupId}/members`, data)
export const removeGroupMember = (classId, groupId, studentId) =>
  api.delete(`/conduct/classes/${classId}/groups/${groupId}/members/${studentId}`)

// ── Export ──
export const exportRecords = (classId, params) =>
  api.get(`/conduct/classes/${classId}/export/records`, { params, responseType: 'blob' })
export const exportRankings = (classId, params) =>
  api.get(`/conduct/classes/${classId}/export/rankings`, { params, responseType: 'blob' })
```

- [ ] **Step 2: 在 permissions.js 追加 conduct 权限**

在 ROLE_PERMISSIONS 对应角色中追加 5 个 conduct 权限（镜像后端 Task 2 的映射）。

- [ ] **Step 3: 在 router/index.js 追加路由**

追加家长端路由（`/parent/*`）和管理端路由（`/conduct/*`）。家长端路由不在 AppShell 内，使用独立的 ParentLayout 或无布局（login/register）。管理端路由在 AppShell children 内，`meta: { permissions: ['view_conduct'], moduleCode: 'conduct' }`。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/conduct.js frontend/src/router/index.js frontend/src/config/permissions.js
git commit -m "feat(conduct): frontend routing + permissions + API module"
```

**审查清单:**
- ✓ API 模块覆盖 design.md §4 全部端点
- ✓ 权限映射与后端一致
- ✓ 管理端路由在 AppShell 内，moduleCode='conduct'
- ✓ 家长端路由独立于 AppShell

---

### Task 8: ParentLayout + 家长登录/注册/绑定页面

**Files:**
- Create: `frontend/src/layouts/ParentLayout.vue`
- Create: `frontend/src/pages/parent/ParentLogin.vue`
- Create: `frontend/src/pages/parent/ParentRegister.vue`
- Create: `frontend/src/pages/parent/ParentBind.vue`

- [ ] **Step 1: 创建 ParentLayout.vue**

移动端优先布局：顶栏（logo + 孩子切换 NSelect + 个人中心 NDropdown）+ router-view + 底部 tab 导航（NBottomNavigation 或自定义 4 tab：概览/排行/班规/我的）。从 localStorage 读 `cp_token`（家长专用 token key）。

- [ ] **Step 2: 创建 ParentLogin.vue**

NCard 表单：手机号 NInput + 密码 NInput + 登录 NButton。底部链接到注册页。调用 `parentLogin()` API，成功后存 token 到 localStorage 并跳转 `/parent`。

- [ ] **Step 3: 创建 ParentRegister.vue**

接收 URL query `?code=XXXX`。流程：输入邀请码 → 调 `getInviteInfo()` 显示班级名 → 填写姓名/手机号/密码/关系 → 调 `parentRegister()`。成功后跳转 `/parent/bind`。

- [ ] **Step 4: 创建 ParentBind.vue**

调 `getParentMe()` 获取当前状态。显示绑定表单：选择班级（从注册时的邀请码关联）→ 输入孩子姓名 → 输入验证码 → 调 `bindChild()`。绑定成功显示成功提示，跳转 `/parent`。

- [ ] **Step 5: 启动前端验证页面可访问**

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npm run dev
```

手动访问 `http://localhost:5273/parent/login` 确认页面渲染正常。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/layouts/ParentLayout.vue frontend/src/pages/parent/
git commit -m "feat(conduct): ParentLayout + login/register/bind pages"
```

**审查清单:**
- ✓ ParentLayout 底部 tab 导航（概览/排行/班规/我的）
- ✓ 登录使用手机号+密码
- ✓ 注册支持 URL 邀请码自动填充
- ✓ 绑定页面显示验证码类型提示
- ✓ token 存储在 localStorage（key 与管理端隔离）

---

### Task 9: 家长端内容页面

**Files:**
- Create: `frontend/src/pages/parent/ParentOverview.vue`
- Create: `frontend/src/pages/parent/ParentDetails.vue`
- Create: `frontend/src/pages/parent/ParentRankings.vue`
- Create: `frontend/src/pages/parent/ParentRules.vue`
- Create: `frontend/src/pages/parent/ParentProfile.vue`

- [ ] **Step 1: ParentOverview.vue**

积分卡片（NCard，显示总积分 + 本周加减分）+ 最近加减分动态列表（NList，最近 10 条 ConductRecord）。多孩子时由 ParentLayout 的孩子切换控制 student_id。

- [ ] **Step 2: ParentDetails.vue**

学生基本信息卡片 + 积分分类统计饼图（ECharts）+ 积分记录列表（NDataTable 分页）。

- [ ] **Step 3: ParentRankings.vue**

NTabs 切换学生/小组排行。排行列表（NDataTable），自己孩子行高亮（row-class-name）。

- [ ] **Step 4: ParentRules.vue**

班规分类折叠面板（NCollapse），每个分类下列出子项（名称 + 分值 tag）。正分绿色 NTag，负分红色 NTag。

- [ ] **Step 5: ParentProfile.vue**

个人信息编辑（姓名、手机号只读）+ 修改密码表单 + 已绑定孩子列表。

- [ ] **Step 6: 前端测试**

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run
```

确认无编译错误。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/parent/
git commit -m "feat(conduct): parent portal pages (overview/details/rankings/rules/profile)"
```

**审查清单:**
- ✓ 所有页面使用 Naive UI 暗色主题
- ✓ 多孩子切换由 ParentLayout 的 provide/inject 控制
- ✓ 排行榜高亮自己孩子
- ✓ 班规正分绿色负分红色
- ✓ 积分记录分页

---

## Batch 4: 管理端后端（Task 10-12）

### Task 10: 积分 CRUD API

**Files:**
- Modify: `src/edu_cloud/modules/conduct/admin_service.py`
- Modify: `src/edu_cloud/modules/conduct/admin_router.py`
- Create: `tests/test_conduct/test_admin_api.py`

- [ ] **Step 1: 在 admin_service.py 添加积分管理函数**

`add_points(db, class_id, operator_id, student_ids, points, reason, rule_item_id, date)` — 批量给多个学生加减分，每个学生创建一条 ConductRecord。

`get_records(db, class_id, page, size, student_id=None, start_date=None, end_date=None)` — 分页查询积分记录，JOIN students 和 users 获取姓名。

`delete_record(db, record_id, operator_id)` — 删除积分记录。

`get_student_rankings(db, class_id, semester_id=None)` — 学生排行榜。

`get_group_rankings(db, class_id, semester_id=None)` — 小组排行榜（按小组 SUM 积分）。

- [ ] **Step 2: 在 admin_router.py 添加端点**

7 个端点：POST records, POST records/batch, GET records, DELETE records/{rid}, GET rankings/students, GET rankings/groups。权限检查用 `require_manage_conduct()` 和 `require_view_conduct()`。

- [ ] **Step 3: 写测试**

测试加分/扣分/批量操作/分页查询/删除/排行榜。

- [ ] **Step 4: 运行测试**

```bash
python -m pytest tests/test_conduct/test_admin_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/conduct/admin_service.py src/edu_cloud/modules/conduct/admin_router.py tests/test_conduct/test_admin_api.py
git commit -m "feat(conduct): points CRUD + rankings API"
```

**审查清单:**
- ✓ 批量加分对每个学生创建独立记录
- ✓ 排行榜按总分降序
- ✓ 小组排行按组内成员积分总和
- ✓ 删除记录检查 class_id 归属

**边界条件:**
- student_ids 为空列表 → 400
- points=0 → 允许（记录备注用）
- 删除不存在的记录 → 404
- 非本班学生 → 400

---

### Task 11: 班规 CRUD API

**Files:**
- Create: `src/edu_cloud/modules/conduct/rules_service.py`
- Modify: `src/edu_cloud/modules/conduct/admin_router.py`
- Modify: `tests/test_conduct/test_admin_api.py`

- [ ] **Step 1: 写 rules_service.py**

`get_rules(db, class_id)` — 查 ConductRuleCategory + ConductRuleItem，按 sort_order 嵌套返回。

`create_category(db, class_id, name, sort_order)` — 创建分类（scope=class）。

`update_category(db, category_id, name, sort_order)` — 更新分类。

`delete_category(db, category_id)` — 级联删除分类及其子项。

`create_item(db, category_id, name, points)` — 创建子项。

`update_item(db, item_id, name, points)` — 更新子项。

`delete_item(db, item_id)` — 删除子项。

- [ ] **Step 2: 在 admin_router.py 添加 7 个端点**

- [ ] **Step 3: 写测试并运行**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(conduct): rules CRUD API (categories + items)"
```

**审查清单:**
- ✓ 分类按 sort_order 排序
- ✓ 删除分类级联删除子项
- ✓ 子项 points 允许正数和负数

---

### Task 12: 小组管理 + 学期管理 API

**Files:**
- Modify: `src/edu_cloud/modules/conduct/admin_service.py`
- Modify: `src/edu_cloud/modules/conduct/admin_router.py`
- Modify: `tests/test_conduct/test_admin_api.py`

- [ ] **Step 1: 小组管理函数**

`get_groups(db, class_id)` — 查小组列表 + 成员。
`create_group(db, class_id, name, avatar)` — 创建小组。
`delete_group(db, group_id)` — 删除小组及成员。
`add_group_members(db, group_id, student_ids)` — 批量添加成员。
`remove_group_member(db, group_id, student_id)` — 移除成员。

- [ ] **Step 2: 学期管理函数**

`get_semesters(db, class_id)` — 查学期列表。
`create_semester(db, class_id, name, start_date, end_date)` — 创建学期。
`activate_semester(db, semester_id)` — 激活学期（同时停用其他）。

- [ ] **Step 3: 添加路由端点**

- [ ] **Step 4: 写测试并运行**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(conduct): groups + semesters API"
```

**审查清单:**
- ✓ 小组名在班级内唯一
- ✓ 激活学期时停用同班级/学校的其他学期
- ✓ 学生可加入多个小组（无 unique 限制 student_id alone）

---

## Batch 5: 管理端前端（Task 13-15）

### Task 13: 管理端核心页面（Points + Rules + Rankings）

**Files:**
- Create: `frontend/src/pages/conduct/ConductPoints.vue`
- Create: `frontend/src/pages/conduct/ConductRules.vue`
- Create: `frontend/src/pages/conduct/ConductRankings.vue`
- Create: `frontend/src/pages/conduct/ConductRecords.vue`

- [ ] **Step 1: ConductPoints.vue**

积分操作页面：左侧学生列表（NCheckboxGroup 多选）+ 右侧班规快捷按钮（NGrid 按分类分组，每个子项是 NButton，点击直接加分）+ 底部手动输入区（NInputNumber + NInput reason）。操作完成后 NMessage 提示。

- [ ] **Step 2: ConductRules.vue**

班规管理：NCollapse 显示分类列表，每个分类下 NList 显示子项（名称+分值+编辑/删除）。分类和子项的添加用 NModal 弹窗表单。

- [ ] **Step 3: ConductRankings.vue**

NTabs 学生/小组切换。NDataTable 排行列表 + ECharts 柱状图。NSelect 学期筛选。

- [ ] **Step 4: ConductRecords.vue**

NDataTable 积分记录列表 + 日期范围筛选（NDatePicker range）+ 学生姓名搜索。分页。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/conduct/
git commit -m "feat(conduct): admin pages (points/rules/rankings/records)"
```

---

### Task 14: 管理端辅助页面（Dashboard + Groups + Settings + Parents + Export）

**Files:**
- Create: `frontend/src/pages/conduct/ConductDashboard.vue`
- Create: `frontend/src/pages/conduct/ConductGroups.vue`
- Create: `frontend/src/pages/conduct/ConductSettings.vue`
- Create: `frontend/src/pages/conduct/ConductParents.vue`
- Create: `frontend/src/pages/conduct/ConductExport.vue`

- [ ] **Step 1-5: 逐个创建页面**

ConductDashboard: 班级积分概览统计卡片 + 本周加减分趋势折线图 + 最近操作列表。
ConductGroups: 小组卡片列表 + 成员管理弹窗 + 创建小组弹窗。
ConductSettings: 邀请码展示/刷新 + 验证方式 NRadioGroup + 学期管理列表。
ConductParents: 已注册家长 NDataTable + 绑定关系展示 + 移除操作确认。
ConductExport: Excel/PDF 导出按钮 + 日期范围选择 + 导出类型选择。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/conduct/
git commit -m "feat(conduct): admin pages (dashboard/groups/settings/parents/export)"
```

---

### Task 15: 侧栏导航集成

**Files:**
- Modify: `frontend/src/config/sidebarConfig.js`

- [ ] **Step 1: 在 sidebarConfig.js 追加德育分组**

为 homeroom_teacher、subject_teacher、grade_leader、academic_director 追加 conduct 导航项（参考 design.md §5 侧栏导航段）。每个导航项包含 `moduleCode: 'conduct'`，学校未启用时自动隐藏。

- [ ] **Step 2: 启动前端验证侧栏显示**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/config/sidebarConfig.js
git commit -m "feat(conduct): sidebar navigation for conduct module"
```

**审查清单:**
- ✓ 班主任看到全部 9 项
- ✓ 科任只看到积分操作+排行榜
- ✓ 年级组长/教务看到概览+排行+导出
- ✓ 全部项 moduleCode='conduct'

---

## Batch 6: 导出 + Agent（Task 16-18）

### Task 16: Excel/PDF 导出 API

**Files:**
- Create: `src/edu_cloud/modules/conduct/export_service.py`
- Modify: `src/edu_cloud/modules/conduct/admin_router.py`

- [ ] **Step 1: export_service.py**

`export_records_excel(db, class_id, start_date, end_date)` — openpyxl 生成积分记录 Excel。

`export_rankings_excel(db, class_id, semester_id)` — 排行榜 Excel。

`export_student_report_html(db, class_id, student_id)` — 学生积分报告 HTML（浏览器端 Ctrl+P 保存 PDF）。

- [ ] **Step 2: 添加 3 个导出端点到 admin_router.py**

权限检查 `require_export_conduct()`。Excel 返回 `StreamingResponse(content_type="application/vnd.openxmlformats...")`。

- [ ] **Step 3: 写测试**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(conduct): Excel/PDF export API"
```

---

### Task 17: Agent 工具

**Files:**
- Create: `src/edu_cloud/ai/tools/conduct.py`
- Modify: `src/edu_cloud/ai/tools/__init__.py`
- Create: `tests/test_conduct/test_agent_tools.py`

- [ ] **Step 1: 写 conduct.py — 6 个工具**

```python
# src/edu_cloud/ai/tools/conduct.py
"""Conduct 域 Agent 工具"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="get_conduct_rankings",
    description="查询班级积分排行榜",
    parameters={
        "type": "object",
        "properties": {
            "class_id": {"type": "string", "description": "班级 ID"},
            "period": {"type": "string", "enum": ["all", "this_week", "this_month"],
                       "description": "时间范围", "default": "all"},
        },
        "required": ["class_id"],
    },
    category="conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="low",
    sensitivity="school",
)
async def get_conduct_rankings(input: dict, ctx: ToolContext) -> ToolResult:
    # 实现：查 ConductRecord，按学生分组 SUM，排序返回
    ...


@tools.register(
    name="get_student_conduct_summary",
    description="查询单个学生积分汇总：总分、分类统计",
    parameters={...},
    category="conduct",
    module_code="conduct",
    domain="L6_profile",
    risk_level="low",
    sensitivity="student",
)
async def get_student_conduct_summary(input: dict, ctx: ToolContext) -> ToolResult:
    ...


@tools.register(
    name="get_conduct_records",
    description="查询积分记录（按学生/日期/分类筛选）",
    parameters={...},
    category="conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="low",
    sensitivity="school",
)
async def get_conduct_records(input: dict, ctx: ToolContext) -> ToolResult:
    ...


@tools.register(
    name="add_conduct_points",
    description="给学生加减分",
    parameters={
        "type": "object",
        "properties": {
            "student_name": {"type": "string"},
            "class_id": {"type": "string"},
            "points": {"type": "integer"},
            "reason": {"type": "string"},
        },
        "required": ["student_name", "points", "reason"],
    },
    category="conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="medium",
    allowed_roles=["homeroom_teacher", "subject_teacher", "academic_director"],
    sensitivity="school",
)
async def add_conduct_points(input: dict, ctx: ToolContext) -> ToolResult:
    ...


@tools.register(
    name="get_conduct_rules",
    description="查询班规分类和子项",
    parameters={...},
    category="conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="low",
    sensitivity="school",
)
async def get_conduct_rules(input: dict, ctx: ToolContext) -> ToolResult:
    ...


@tools.register(
    name="get_class_conduct_overview",
    description="班级德育概览：总人数、本周统计、异常学生",
    parameters={...},
    category="conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="low",
    sensitivity="school",
)
async def get_class_conduct_overview(input: dict, ctx: ToolContext) -> ToolResult:
    ...
```

- [ ] **Step 2: 在 tools/__init__.py 注册**

```python
from edu_cloud.ai.tools import conduct  # noqa: F401
```

- [ ] **Step 3: 写工具测试**

测试工具注册成功（6 个工具在 registry 中）、权限配置正确。

- [ ] **Step 4: 运行全量测试**

```bash
python -m pytest --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/tools/conduct.py src/edu_cloud/ai/tools/__init__.py tests/test_conduct/test_agent_tools.py
git commit -m "feat(conduct): 6 Agent tools for conduct module"
```

**审查清单:**
- ✓ 6 个工具与 design.md §6 一致
- ✓ add_conduct_points risk_level=medium
- ✓ 全部工具 module_code='conduct'
- ✓ student 敏感度工具锁定主通道（get_student_conduct_summary）

---

### Task 18: 全量集成测试 + 回归验证

**Files:**
- No new files

- [ ] **Step 1: 后端全量测试**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q
```

Expected: 全部 PASS（1582 + ~30 新 conduct tests）

- [ ] **Step 2: 前端测试**

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run
```

Expected: 全部 PASS

- [ ] **Step 3: Alembic 迁移测试**

```bash
python -m pytest tests/test_alembic_migration.py -v
```

Expected: PASS（新表存在于迁移后的表集合中）

- [ ] **Step 4: Commit（如有修复）**

**审查清单:**
- ✓ 后端全量测试通过
- ✓ 前端测试通过
- ✓ Alembic 迁移可正常 upgrade/downgrade
- ✓ 无已有功能回归

---

## Round 2 遗留债务备注（2026-04-13 追加）

**grading-dispatch Batch 1 deferred F003 已单点修复** (commit f275c75)：
- 端点: `GET /api/v1/conduct/parent/classes/{class_id}/rules`
- 修复手段: `parent_service._verify_guardian_class()` helper + 入口级回归测试（家长绑定班 A，请 B 班 rules → 403）
- 遗留 refactor 任务（非 Round 2 必修，视 F002 解法决定）：
  当 Round 2 的 F002（管理端跨班越权）选定"class-scope / resource-affinity 统一守卫"方案后，
  parent_router `/parent/classes/{class_id}/rules` 应迁移到统一守卫（家长绑定维度），
  替换现有 `_verify_guardian_class`。迁移属 refactor 非行为变更，无需新回归测试。

---

## Batch 7: Round 3 修复（Task 19-22，2026-04-13 追加）

> 前置: Round 2 FAIL（R2 审查报告 `docs/plans/2026-04-12-conduct-module-review-report-batch1-r2.md`），Fix Intent Card `docs/plans/.conduct-fix-intent-F002r3-N001.md`
> 边界: F001（Alembic SQLite）deferred 到 haofenshu-phase1 Migration Gate Repair，不在本批次 scope。
> 执行纪律: F002/N001 命中架构守卫 + 行为契约红旗模式 → 必须遵循 Fix Intent Card 的 non_goals 和 allowed_change_surface。

### Task 19: F002 Round 3 — 关闭剩余 2 条越权面

**意图**: Round 2 的 `check_class_scope` + `check_resource_class` 已覆盖路径参数的嵌套资源，但遗漏 body 字段/批量写路径的外班 ID 直通。Round 3 补齐。

**Fix Intent**: 见 `.conduct-fix-intent-F002r3-N001.md § F002 Round 3`

**必修改动**:
1. `src/edu_cloud/modules/conduct/permissions.py`:
   - 新增 `async def check_rule_item_class(db, rule_item_id: str, class_id: str) -> None` — join `rule_categories` 校验 rule_item 属 class，不匹配 raise 404（保持与 check_resource_class 一致的异常约定）
   - 新增 `async def check_students_class(db, student_ids: list[str], class_id: str) -> None` — 批量校验 students 属 class，单条失败整体 raise 404
2. `src/edu_cloud/modules/conduct/admin_router.py`:
   - `add_points` (line 93-109) 与 `add_points_batch` (line 112-128)：在 `check_class_scope(...)` 之后，若 `data.rule_item_id is not None` → `await check_rule_item_class(db, data.rule_item_id, class_id)`
   - `add_group_members` (line 326-337)：在 `check_resource_class(...ConductGroup...)` 之后，`await check_students_class(db, data.student_ids, class_id)`
   - `remove_group_member` (line 340-351)：同上，`await check_students_class(db, [student_id], class_id)`
3. `tests/test_conduct/test_admin_api.py` — 补 3 条越权红测（命名见 Fix Intent § verification）

**审查清单**:
- ✓ `add_points` 用本班 rule_item_id 仍成功（不回归）
- ✓ `add_points` 用外班 rule_item_id → 404（新红测 T1）
- ✓ `add_group_members` 用外班 student_ids → 404（新红测 T2）
- ✓ `remove_group_member` 用外班 student_id → 404（新红测 T3）
- ✗ 删除 `check_rule_item_class` 调用 → T1 失败（反向验证）
- ✗ 删除 `check_students_class` 调用 → T2/T3 失败（反向验证）

**边界条件:**
- 空 `student_ids=[]`（batch 无操作）→ 应 silently return（不 raise 404，空操作非越权）
- `data.rule_item_id=None`（不关联规则）→ 跳过 check_rule_item_class
- `rule_item_id` 不存在（404 实体不存在）→ 与"外班 rule_item_id"表现一致（均 raise 404），对外行为不泄露差异

**测试契约:**
1. test_add_points_cross_class_rule_item_rejected
   - 入口: `POST /api/v1/conduct/classes/{classA.id}/records`
   - 反例: 错误实现会成功写入 conduct_records.rule_item_id=classB.rule_item_id 造成跨班污染
   - 边界: rule_item_id=None 跳过；rule_item_id=本班合法→200
   - 回归: 防 F002 R3 未覆盖面复发
   - 命令: `pytest tests/test_conduct/test_admin_api.py::test_add_points_cross_class_rule_item_rejected -v`
2. test_add_group_members_cross_class_student_rejected
   - 入口: `POST /api/v1/conduct/classes/{classA.id}/groups/{group_A.id}/members`
   - 反例: 错误实现会把 studentB 加入 classA 的 group_A
   - 边界: student_ids=[] → 200 no-op；单个本班 student → 200
   - 回归: 防跨班组员污染
   - 命令: `pytest tests/test_conduct/test_admin_api.py::test_add_group_members_cross_class_student_rejected -v`
3. test_remove_group_member_cross_class_student_rejected
   - 入口: `DELETE /api/v1/conduct/classes/{classA.id}/groups/{group_A.id}/members/{studentB.id}`
   - 反例: 错误实现返回 200 假装移除（或 silently no-op），绕过 scope
   - 边界: 本班 student 不在 group → 返回 404 or 200 (幂等行为需与现有实现一致)
   - 回归: 防跨班操作组员状态
   - 命令: `pytest tests/test_conduct/test_admin_api.py::test_remove_group_member_cross_class_student_rejected -v`

---

### Task 20: N001 — 恢复 id_card 后 6 位契约（REJECT R2 行为变更）

**意图**: Round 1 F005 用户决策 Option A 明确 `id_card` 比对"后 6 位"。Round 2 误改为"整串相等"属未授权 behavior_change，用户已 REJECT。Round 3 恢复原契约。

**Fix Intent**: 见 `.conduct-fix-intent-F002r3-N001.md § N001`

**必修改动**:
1. `src/edu_cloud/modules/conduct/parent_service.py` (line 188-191)：
   ```python
   if verify_type == "id_card":
       stored = decrypt(profile.id_card_number) if profile else None
       if not stored or stored[-6:] != verify_code:
           raise ValidationError("身份证号验证失败")
   ```
2. `tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_mode`:
   - fixture 保持（完整身份证号 `"110101200001011234"`）
   - 绑定请求改为 `verify_code="011234"`（后 6 位）
3. 追加红测：
   - `test_parent_bind_id_card_full_string_rejected` — verify_code 传完整身份证号 → ValidationError
   - `test_parent_bind_id_card_wrong_6_digits` — verify_code 传错误的 6 位 → ValidationError
4. `docs/plans/2026-04-12-conduct-module-design.md` §3：追加"id_card 模式比对后 6 位（Option A 锁定，防退化 sentinel）"

**审查清单**:
- ✓ 后 6 位正确 → 绑定成功
- ✗ 完整身份证号作 verify_code → 拒绝（防 R2 行为复活）
- ✗ 错误 6 位 → 拒绝
- ✗ 把实现改回 `stored != verify_code` → test_parent_bind_id_card_mode 立刻失败（6 字符 ≠ 18 字符）

**边界条件:**
- verify_code 长度 ≠ 6 → 由 stored[-6:] 对比自然失败（不特殊处理，保持单一路径）
- stored 不足 6 位（理论不应出现）→ stored[-6:] 返回整串，与 verify_code 对比自然失败
- verify_code 含字母（身份证末位 X）→ 字符串相等比对，支持

**测试契约:**
1. test_parent_bind_id_card_mode（修正）
   - 入口: `POST /api/v1/conduct/parent/bind` body `{verify_code: "011234"}`
   - 反例: 错误实现（整串相等）→ verify_code="011234" ≠ "110101200001011234"，绑定失败
   - 边界: 后 6 位正确 → 200
   - 回归: 防 Option A 契约退化
   - 命令: `pytest tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_mode -v`
2. test_parent_bind_id_card_full_string_rejected（新增）
   - 入口: `POST /api/v1/conduct/parent/bind` body `{verify_code: "110101200001011234"}`
   - 反例: 错误实现（整串相等）→ 绑定成功，违反 Option A
   - 边界: 完整 18 位身份证号作为 verify_code
   - 回归: 防 N001 R2 行为复活
   - 命令: `pytest tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_full_string_rejected -v`

---

### Task 21: F004 Round 3 — ParentRules 字段映射契约测试

**意图**: Round 2 前端已改 `item.points`，但无测试保护字段映射，改回 `item.default_points` 不会失败（半闭环）。

**必修改动**:
1. 前端测试：`frontend/src/pages/parent/__tests__/ParentRules.spec.js`（新建）
   - mount `ParentRules.vue`，mock API 返回 `[{..., points: 5}]` → assert 渲染 `+5` 可见
   - mount 后断言 DOM 渲染了 `item.points` 的值（5），而非空/undefined
   - 反向验证：把 template 改回 `item.default_points` → mock 数据无 default_points 字段 → 断言失败
2. 或用 e2e / snapshot：对渲染输出快照比对

**审查清单**:
- ✓ mock API 返回 `points=5` → 渲染 `+5`
- ✓ 把 template `item.points` 改回 `item.default_points` → 测试失败（因 mock 数据无 default_points）
- ✓ 与现有 frontend 测试套件集成（vitest + happy-dom）

**边界条件:**
- API 返回 `points=0` → 渲染 `+0` / `-0`（非特殊符号）
- `points` 负数 → 渲染 `-3` 而非 `+-3`
- items 数组为空 → 渲染"暂无班规"占位（不崩溃）

**测试契约:**
1. test_parent_rules_renders_item_points
   - 入口: mount `ParentRules.vue`，props.currentChild.class_id 注入
   - 反例: 错误实现 `item.default_points` → mock 数据无此字段，渲染为 undefined/空
   - 边界: points=0 / 负数 / 空数组
   - 回归: 防 F004 字段映射无感回退
   - 命令: `cd frontend && npx vitest run src/pages/parent/__tests__/ParentRules.spec.js`

---

### Task 22: F006 Round 3 — 导出断言升级

**意图**: Round 2 导出测试只验 `PK` 魔数 + `>1000` 字节，空 xlsx 工作簿 4854 字节可通过；`test_export_records_excel` 的 dummy `operator_id` 被 inner join 过滤，断言仍通过（假阳性）。

**必修改动**:
1. `tests/test_conduct/test_admin_api.py::test_export_records_excel`（修正）:
   - 插入 conduct_records 前先创建 operator user（真实 FK），避免 inner join 过滤
   - 用 `openpyxl.load_workbook(BytesIO(resp.content))` 解包 xlsx
   - 断言 sheet 有至少 N+1 行（header + N 条记录）
   - 断言每条记录的关键字段（points / student_name / rule / operator）与插入数据匹配
2. `test_export_rankings_excel`（类似）:
   - 解包读 sheet，断言排名行数 = 学生数 + header
   - 断言排名顺序（points desc）正确
3. 删除 `>1000` 字节的弱断言（改为内容断言即可隐含工作簿非空）

**审查清单**:
- ✓ 插入 2 条 records → 导出 sheet 有 3 行（header + 2）
- ✓ operator FK 合法 → inner join 不过滤记录
- ✗ 清空 service 的 SELECT 逻辑 → sheet 只剩 header → 断言失败
- ✗ 改 service 用 cross join（返回笛卡尔积）→ 行数不等 N+1 → 断言失败

**边界条件:**
- 插入 0 条记录 → sheet 仅 header → 断言行数 = 1
- 非 ASCII 字段（中文学生名）→ 正确读出（openpyxl UTF-8 支持）
- 导出日期过滤（start_date/end_date）→ 过滤范围外不含，范围内含

**测试契约:**
1. test_export_records_excel（修正）
   - 入口: `GET /api/v1/conduct/classes/{class_id}/export/records`
   - 反例: 错误实现（inner join 过滤全部记录 / 空表结果）→ sheet 仅 header，行数断言失败
   - 边界: 0 条 / N 条 / 含中文字段 / 带日期过滤
   - 回归: 防空 xlsx 通过弱断言
   - 命令: `pytest tests/test_conduct/test_admin_api.py::test_export_records_excel -v`

---

### Task 23: Round 3 收尾验证

**必修动作**:
1. 运行全量 conduct 测试: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/ -q`
   - 预期: 108 (R2 基线) + 3 (Task 19 F002 越权红测) + 2 (Task 20 N001 新增红测) = 113 passed
2. 运行前端测试: `cd frontend && npx vitest run`
   - 预期: 现有 + 1 新（Task 21 ParentRules.spec.js）
3. 跑 alembic 测试（本会话 scope 外——确认不回归）: `pytest tests/test_alembic_migration.py -v`
   - 如工作区 haofenshu-phase1 的 alembic 修复已 commit → 3 passed
   - 未 commit → 1 passed, 1 failed, 1 error（F001 仍是 deferred 状态，**不阻塞 Round 3 PASS**）
4. 生成审查交接单（按 review-templates.md 模板）
5. 调用 codex-review skill Code Review（Round 3）
6. 若 PASS → 更新 gates.json `code_review_batch1.status=pass`、`round=3`、`report_path=R3 报告`

**审查清单**:
- ✓ 108 R2 基线全绿 + 新增测试全绿
- ✓ R2 标 resolved-partial/not-resolved 的 finding 全部升级
- ✓ N001 用户 REJECT 决策已落地（不追认）
- ✓ 无新 behavior_change finding（Round 3 仅修缺陷，不新增机制）

**PASS 条件**:
- F002/F004/F006/N001 全部 resolved-correct
- F001 保持 deferred（等 haofenshu-phase1 合入）
- 无 HIGH/MED code-bug/test-gap 新 finding
