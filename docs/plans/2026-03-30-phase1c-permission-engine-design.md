# Phase 1c: 权限引擎 + 审计日志 设计文档
> [2026-03-30 09:37:31 实现完成] Commits: 6773fd0..a1ec97b | Gates: plan_review PASS + code_review_batch1 PASS(R3)

> **日期**: 2026-03-30 07:25:57
> **项目**: edu-cloud（多校多角色教育管理平台）
> **前置**: Phase 1a 模块管理 [实现完成] + Phase 1b 基础信息 [实现完成]
> **上游设计**: `docs/plans/2026-03-29-business-logic-backfill-design.md` §1.5 + §3.2-3.4

---

## 0. 范围与决策

**本 Phase 范围**: Capability 可配置权限 + ScopeFilter 查询工具 + 审计日志。

**明确排除**:
- 审批流（§1.5 第⑤步）→ Phase 1d（Agent 实例化时才有消费者）
- Agent Capability 检查（§1.5 第③步的 agent_capabilities）→ Phase 1d
- PolicyEngine 完整 6 步决策链 → Phase 1d（本 Phase 实现前 4 步，①②已有）
- 前端审计日志页 → Phase 1e（Agent 管理 UI 一起做）
- 全量 service scope 改造 → 各 Phase 按需接入

**关键设计决策**:

| 决策 | 选择 | 理由 |
|------|------|------|
| 权限引擎深度 | 前 4 步（模块→RBAC→Capability→scope） | ①②已有，③④新增，⑤⑥等 Agent 来了再做 |
| Capability vs Permission | 共存：Permission 硬约束 + Capability 可配置层 | 不动已有代码，渐进式叠加 |
| 审计触发机制 | Service 层 @audited 装饰器 | 精确控制范围，能拿 before/after 快照 |
| scope 注入 | ScopeFilter 工具类 + 示范接入 | 模式验证后再推广，不强制全量改造 |
| 审计初期范围 | 4 个 service（settings/assignments/selections/modules） | 关键配置变更，不审计读操作 |

**权限检查层级关系**:
```
请求 → ① ModuleCheckMiddleware（模块是否启用）     [Phase 1a 已有]
     → ② require_permission（角色有 Permission？）  [已有]
     → ③ check_capability（学校启用该 Capability？） [本 Phase 新增]
     → ④ ScopeFilter（数据范围过滤）                [本 Phase 新增]
     → ⑤ 审批检查                                   [Phase 1d]
     → ⑥ 执行                                       [已有]
```

---

## 1. Capability 可配置权限层

### 1.1 与现有 Permission 的关系

- **Permission（代码层）**: `require_permission(Permission.VIEW_EXAMS)` — 编译时确定，角色→权限映射硬编码在 `permissions.py`
- **Capability（配置层）**: school 级别可定制 — "这个学校的科任教师能不能导出成绩"
- **检查顺序**: Permission → Capability。Permission 不过 = 直接拒绝；Permission 过了但 Capability 没开 = 拒绝
- **类比**: Module 控制功能块可见性，Capability 控制功能块内的操作权限

### 1.2 数据模型

```python
class Capability(Base, IdMixin, TimestampMixin):
    """学校级角色能力配置：域×操作×角色。"""
    __tablename__ = "capabilities"
    __table_args__ = (
        UniqueConstraint("school_id", "role", "domain", "action",
                         name="uq_capability"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    role: Mapped[str] = mapped_column(String(50))        # "principal" / "subject_teacher" 等
    domain: Mapped[str] = mapped_column(String(50))      # "exam" / "grading" 等 (9 域)
    action: Mapped[str] = mapped_column(String(20))      # "read" / "write"
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

### 1.3 域定义

9 个域对齐 MODULE_CODES + system 管理域：

```python
CAPABILITY_DOMAINS = {
    "exam": "考试管理",
    "grading": "阅卷系统",
    "homework": "作业管理",
    "study_analytics": "学情分析",
    "research": "教研题库",
    "teaching": "教学管理",
    "calendar": "校历日程",
    "studio": "文档中心",
    "system": "系统管理",
}
CAPABILITY_ACTIONS = {"read", "write"}
```

### 1.4 默认模板

创建学校时按角色生成默认 capability 行。模板逻辑：

- principal: 全域 read+write
- academic_director: 全域 read+write（除 system.write）
- grade_leader: exam/grading/study_analytics read; studio/calendar read
- homeroom_teacher: exam/grading read+write; study_analytics/calendar/studio read
- subject_teacher: exam/grading read+write; study_analytics/research read
- parent: study_analytics read only

platform_admin / district_admin 不生成 capability 行（跳过检查）。

### 1.5 Service

```python
async def init_school_capabilities(db, *, school_id: str) -> None
    # 按默认模板批量创建（幂等）
async def get_capabilities(db, *, school_id: str, role: str | None = None) -> list[Capability]
async def set_capability(db, *, school_id: str, role: str, domain: str, action: str, enabled: bool) -> Capability
async def check_capability(db, *, school_id: str, role: str, domain: str, action: str) -> bool
    # 无记录 = 默认允许（宽松策略，capability 表主要用于 disable）
```

**宽松策略**: capability 行不存在时默认允许。这样未初始化的学校不会被全面封锁。只有显式 `enabled=False` 才拒绝。

### 1.6 API

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/schools/{id}/capabilities` | 获取角色能力矩阵（支持 role 过滤） |
| PATCH | `/api/v1/schools/{id}/capabilities` | 修改单个 capability（role + domain + action + enabled） |
| POST | `/api/v1/schools/{id}/capabilities/init` | 按默认模板初始化（幂等） |

权限: MANAGE_SCHOOL_SETTINGS + _check_school_scope

---

## 2. ScopeFilter 查询工具

### 2.1 工具类

```python
# src/edu_cloud/core/scope_filter.py
class ScopeFilter:
    """基于 UserRole 的 scope 自动注入 WHERE 条件。"""

    def __init__(self, role: UserRole):
        self.school_id = role.school_id
        self.grade_ids = role.grade_ids
        self.class_ids = role.class_ids
        self.subject_codes = role.subject_codes

    def apply(self, stmt, model, *, school_col="school_id",
              class_col=None, grade_col=None, subject_col=None):
        """追加过滤条件。school_id 始终追加（非 None 时）；
        grade/class/subject 有 scope 值且 model 有对应列时才追加。"""
        if self.school_id:
            stmt = stmt.where(getattr(model, school_col) == self.school_id)
        if self.class_ids and class_col:
            stmt = stmt.where(getattr(model, class_col).in_(self.class_ids))
        if self.grade_ids and grade_col:
            stmt = stmt.where(getattr(model, grade_col).in_(self.grade_ids))
        if self.subject_codes and subject_col:
            stmt = stmt.where(getattr(model, subject_col).in_(self.subject_codes))
        return stmt

    @classmethod
    def from_role(cls, role) -> "ScopeFilter | None":
        """platform_admin/district_admin 等无 school_id 的角色返回 None（不过滤）。"""
        if not role or not role.school_id:
            return None
        return cls(role)
```

### 2.2 示范接入

改造 `teacher_assignment_service.list_assignments` 加可选 `scope: ScopeFilter | None` 参数。当 scope 非空时用 `scope.apply(stmt, TeacherAssignment, subject_col="subject_code")` 追加过滤。

不改造其余 service。

---

## 3. 审计日志

### 3.1 数据模型

```python
class AuditLog(Base, IdMixin, TimestampMixin):
    """实体变更审计日志。"""
    __tablename__ = "audit_logs"

    school_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("schools.id"), index=True, default=None)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))     # "school_setting" / "school_module" / "teacher_assignment" 等
    entity_id: Mapped[str] = mapped_column(String(36))       # 被操作实体的 ID
    action: Mapped[str] = mapped_column(String(20))          # "create" / "update" / "delete"
    before_data: Mapped[dict | None] = mapped_column(JSON, default=None)   # 变更前快照
    after_data: Mapped[dict | None] = mapped_column(JSON, default=None)    # 变更后快照
    request_id: Mapped[str | None] = mapped_column(String(50), default=None)  # 关联 ContextVar request_id
```

### 3.2 @audited 装饰器

```python
def audited(entity_type: str, id_param: str = "entity_id"):
    """Service 层装饰器：自动记录 before/after 快照。

    被装饰函数需要返回被操作的 ORM 对象（create/update）或 None（delete）。
    装饰器从函数参数中提取 db session 和 school_id。
    user_id 从 ContextVar 获取（由 request_logging 中间件设置）。
    """
```

装饰器逻辑：
1. create: before=None, after=entity.__dict__
2. update: before=查询旧值, after=entity.__dict__
3. delete: before=entity.__dict__, after=None

**user_id 来源**: 新增 `current_user_var: ContextVar[str]` 在 request_logging 中间件中设置（从 JWT 提取），装饰器读取。

### 3.3 初期审计范围

| Service | 函数 | action |
|---------|------|--------|
| school_settings_service | upsert_setting | create/update |
| school_settings_service | set_module_enabled | update |
| teacher_assignment_service | create_assignments | create |
| teacher_assignment_service | delete_assignment | delete |
| subject_selection_service | create_selection | create |
| subject_selection_service | update_selection | update |
| subject_selection_service | delete_selection | delete |

### 3.4 查询 API

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/schools/{id}/audit-logs` | 查询审计日志（支持 entity_type / user_id / action / start_date / end_date 过滤，分页） |

权限: MANAGE_SCHOOL_SETTINGS + _check_school_scope。不做前端页面（Phase 1e）。

---

## 4. 文件规划

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/edu_cloud/models/capability.py` | Capability ORM |
| `src/edu_cloud/models/audit_log.py` | AuditLog ORM |
| `src/edu_cloud/services/capability_service.py` | Capability CRUD + init_school_capabilities + check_capability |
| `src/edu_cloud/services/audit_service.py` | @audited 装饰器 + AuditLog 写入 + 查询 |
| `src/edu_cloud/core/scope_filter.py` | ScopeFilter 工具类 |
| `src/edu_cloud/modules/school/capability_router.py` | Capability API |
| `src/edu_cloud/modules/school/audit_router.py` | AuditLog 查询 API |
| `tests/test_services/test_capability_service.py` | Capability service 测试 |
| `tests/test_services/test_audit_service.py` | @audited 装饰器 + 查询测试 |
| `tests/test_services/test_scope_filter.py` | ScopeFilter 单元测试 |
| `tests/test_api/test_capabilities.py` | Capability API 测试 |
| `tests/test_api/test_audit_logs.py` | AuditLog API 测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/edu_cloud/api/app.py` | 注册 capability_router + audit_router + lifespan 导入 + current_user_var 中间件 |
| `src/edu_cloud/services/school_settings_service.py` | 给 upsert_setting / set_module_enabled 加 @audited |
| `src/edu_cloud/services/teacher_assignment_service.py` | 给 create/delete 加 @audited + list_assignments 示范 ScopeFilter |
| `src/edu_cloud/services/subject_selection_service.py` | 给 create/update/delete 加 @audited |
| `alembic/env.py` | 导入新模型 |
| `tests/conftest.py` | 导入新模型 |
| `tests/test_alembic_migration.py` | 导入新模型 |
| `CLAUDE.md` | 同步 API 端点 + 数据模型 |

### 不改动

- Permission 枚举 / ROLE_PERMISSIONS — Capability 是叠加层，不替换
- 其余 service 的 scope 注入 — 示范一个，其余按需
- 前端 — 无新页面（审计页 Phase 1e）

---

## 5. 测试策略

**预期 ~35 个新测试**:

| 层 | 测试 | 数量 |
|----|------|------|
| Capability service | model / init_school / get / set / check + 宽松策略 | ~7 |
| Capability API | CRUD + scope guard + 权限 + 初始化幂等 | ~6 |
| ScopeFilter | school_id / class_ids / grade_ids / subject_codes / None 跳过 | ~5 |
| @audited 装饰器 | create/update/delete 快照 + user_id ContextVar + request_id | ~6 |
| AuditLog API | 查询 + 过滤 + 分页 + 权限 | ~5 |
| 集成 | @audited 接入后 existing service tests 仍 pass | ~3 |
| Migration | 复用 smoke test | 0 |
