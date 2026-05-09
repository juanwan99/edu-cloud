# 租户中间件架构设计（Phase 3）

> **日期**: 2026-05-09
> **前序**: Permission Isolation Phase 1+2（39 项修复，5 层隔离模型系统性修复）
> **审计依据**: Claude × GPT 联合深度调查（3 轮辩论收敛）
> **设计者**: Claude Opus 4.6 + GPT 5.5

---

## 1. 问题定义

Phase 2 通过 `core/tenant.py` 集中化和条件式过滤模式修复了 39 项隔离缺陷，但根因未解决：

**开放环执行模型** — 每个端点手动调用 `get_school_id()` + 手动拼 WHERE。新端点遗漏一个 WHERE 就是一个跨校泄露。

当前 38 个 router 文件中：
- 10 个 import `get_school_id`（Phase 2 集中化）
- 28 个直接使用 `role.school_id` / `getattr(role, "school_id", ...)`（分散模式）
- 0 个使用统一的 tenant context

## 2. 现有资产盘点

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| Tenant helper | `get_school_id(current) -> str\|None` + `CROSS_SCHOOL_ROLES` | `core/tenant.py:5-21` | Phase 2 建立，10 router 使用 |
| Scope helper | `get_visible_class_ids(role)` / `get_visible_subject_codes(role)` | `api/permissions.py:18-31` | 从 UserRole 属性直接派生 |
| Query wrapper | `ScopeFilter.apply(stmt, model, ...)` | `core/scope_filter.py:6-35` | 4 维度 WHERE 注入 |
| Data snapshot | `DataScope` frozen dataclass + `DataScopeBuilder` | `ai/data_scope.py:49-173` | AI 层专用，10 角色 fail-closed |
| Scoped query | `ScopedQuery` with deny-all on empty | `ai/scoped_query.py:48-59` | AI 工具层，比 ScopeFilter 安全 |
| Module middleware | `ModuleCheckMiddleware` JWT→UserRole→school_id | `api/module_middleware.py:59-131` | 解析模式可复用 |
| Session factory | `async_session(class_=AsyncSession)` | `database.py:18-24` | 标准 AsyncSession，无自定义 |
| Auth dependency | `get_current_user()` → `{user, roles, current_role, permissions}` | `api/deps.py:54-172` | 所有 router 的认证入口 |

## 3. 增量 vs 新建论证

- **默认立场：增强已有代码**
- 选择增量：在 `core/tenant.py` 基础上新增 `TenantContext` dataclass + `get_tenant_context` dependency
- 不新建独立模块/库：复用 `get_school_id`、`get_visible_*` 等已验证的 helper
- 不走 repository 层：320 个端点全量迁移成本过高，scope helper 足够

## 4. 交付路径

- 目标目录：`src/edu_cloud/core/tenant.py`（扩展现有文件）
- 生产 serving：后端 pytest 测试套件通过
- 用户影响：纯后端安全加固，无前端变更

---

## 5. 架构方案

### 5.1 核心组件：TenantContext

```python
# core/tenant.py — 纯数据类，零 api 层依赖（R3-F001 修复）
@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: str
    role_id: str
    role_name: str
    school_id: str | None          # None = cross-school (admin)
    visible_class_ids: tuple[str, ...] | None    # None = all, () = deny-all
    visible_subject_codes: tuple[str, ...] | None  # None = all, () = deny-all

    def require_school(self) -> str: ...
    def apply_school(self, stmt, model) -> stmt: ...
    def apply_subject_scope(self, stmt, column) -> stmt: ...
    def apply_class_scope(self, stmt, column) -> stmt: ...

# api/deps.py — 构造入口，负责调用 permissions helpers
async def get_tenant_context(current = Depends(get_current_user)) -> TenantContext:
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

**关键语义契约**：
- `None` = 不限制（admin 全局视图）
- `tuple()` = 限制为空集 = **deny-all**（修复 ScopeFilter fail-open）
- `tuple(...)` = 限制为指定集合

### 5.2 Dependency 注入（api/deps.py）

```python
# api/deps.py — 构造入口，负责调用 permissions helpers
async def get_tenant_context(current = Depends(get_current_user)) -> TenantContext:
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

Router 使用：
```python
@router.get("/tasks")
async def list_tasks(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GradingTask)
    stmt = ctx.apply_school(stmt, GradingTask)
    stmt = ctx.apply_subject_scope(stmt, GradingTask.subject_code)
    ...
```

### 5.3 与 get_school_id 的关系

- `get_school_id` **保留**为 TenantContext 内部实现
- 标注 internal/compat，禁止新 router 直接 import
- 旧 router 按"触碰即迁移"原则逐步替换

### 5.4 ScopeFilter 修复

`core/scope_filter.py:25-26` 的 `if self.subject_codes` 对空列表 `[]` 是 falsy，导致 fail-open。修复为 `is not None` 语义。

### 5.5 SQLAlchemy audit mode（Phase 3.4，延后）

```python
@event.listens_for(Session, "do_orm_execute")
def tenant_audit(execute_state):
    if not execute_state.is_select:
        return
    ctx = tenant_ctx_var.get()
    # 只记录，不拦截
    if ctx is None:
        logger.warning("unscoped_query", ...)
```

不在第一阶段强制过滤。原因：
- 无法覆盖 raw SQL / Core table select / 聚合 DML
- 后台任务无 request context
- 需要 model registry 确定哪些表是 tenant-scoped

---

## 6. 剩余修复项整合

| 项 | 缺陷 | 整合策略 |
|----|------|---------|
| P1-14 marking import | `importer.py:46` Exam + `:52` Subject + `:66` StudentAnswer 缺 school_id | **热修**（不等 TenantContext） |
| H4 pipeline progress/stop | 全局状态无 school 维度 | **热修**：加 pipeline_school_id 验证 |
| P2-1 dashboard | 考试数/待阅卷缺 subject_codes | TenantContext 首批落地 |
| P2-3 workspace | exam dashboard 缺 subject 过滤 | TenantContext 首批落地 |
| P2-4 analytics grade | 年级概览不传 visible_subject_codes | TenantContext 首批落地 |

---

## 7. 治理规则（pytest 静态分析）

`tests/governance/test_tenant_static.py` 四条规则：

1. **禁止新 router 直接 `current["current_role"].school_id`** — 必须走 TenantContext
2. **禁止 scope helper 用 `if subject_codes` / `or None`** — 必须用 `is not None`
3. **禁止 tenant-scoped model 的裸 `db.get(Model, id)`** — 需后续 school 校验或 allowlist
4. **禁止新增状态端点无 school/owner scope**

---

## 8. 分期路线图

| 阶段 | 内容 | 工期 | 依赖 |
|------|------|------|------|
| **3.0** | 热修 P1-14 + H4 | 半天 | 无 |
| **3.1** | TenantContext + get_tenant_context + ScopeFilter 修复 | 1 天 | 无 |
| **3.2** | 迁移 P2-1/3/4 + dashboard/workspace/analytics 到 TenantContext | 1 天 | 3.1 |
| **3.3** | pytest 静态治理规则 | 半天 | 3.1 |
| **3.4** | SQLAlchemy do_orm_execute audit mode（只记录） | 1 天 | 3.1 |
| **3.5** | 选择性启用强制过滤（需 model registry） | 待评估 | 3.4 |

---

## 9. 风险评估

| 风险 | Tier | 概率 | 影响 | 缓解 | 证据 |
|------|------|------|------|------|------|
| TenantContext 迁移引入回归 | T2 | 中 | 中 | 旧 get_school_id 保留兼容，逐步迁移 | `grep -c get_school_id src/edu_cloud/modules/*/router*.py` → 10 文件已用 |
| deny-all 语义误杀合法查询 | T2 | 低 | 高 | 充分测试空 scope 场景 | `scope_filter.py:25` `if self.subject_codes` 是 falsy check |
| audit mode 日志量过大 | T1 | 中 | 低 | 按模块启用，限 warning 级别 | Phase 3.4 延后，不影响当前 |
| session filter 绕过 | — | 确定 | — | 不依赖 B 做安全边界，A 是主线 | `database.py:18` 标准 AsyncSession，无 ORM event |
| core→api 反向依赖 | T2 | 高 | 中 | get_tenant_context 放 api/deps.py，TenantContext 留 core | F008: `core/tenant.py` 不 import `api.deps` |

### Evidence: 架构路线选择（A+TenantContext 混合 vs B session filter）

**decision**: 方案 A（TenantContext typed dependency）为主线，B 仅 audit mode
**evidence_refs**:
  - `src/edu_cloud/core/tenant.py:5-21` — Phase 2 已验证 get_school_id 模式
  - `src/edu_cloud/core/scope_filter.py:25` — ScopeFilter `if self.subject_codes` fail-open 证据
  - `src/edu_cloud/ai/data_scope.py:256` — DataScopeBuilder `or None` 风险证据
  - `src/edu_cloud/database.py:18` — 标准 AsyncSession，无自定义 Session 基础
  - `src/edu_cloud/api/module_middleware.py:82-108` — JWT→UserRole→school_id 解析模式可复用
  - `grep -rln 'role.school_id' src/edu_cloud/ | wc -l` → 38 文件使用裸 role.school_id
**Q1**: evidence_source: code-grep | evidence_state: verified
**Q2_excluded**:
  - 方案 B（session filter 强制）: SQLAlchemy do_orm_execute 无法覆盖 raw SQL/Core select/聚合 DML/后台任务；反证: `grep -rn "text(" src/edu_cloud/modules/ | wc -l` 有 raw SQL 使用
  - 全量 repository 层: 320 端点迁移成本过高；反证: `grep -c "select(" src/edu_cloud/modules/*/router*.py | awk -F: '{s+=$2}END{print s}'` → ~200 处直接查询
**impact_scope**: cross-module（影响所有 router 的 scope 入口）
**unknowns**:
  - DataScopeBuilder `or None` 修复是否影响 AI 工具层行为 — followup: 检查 AI tools 测试覆盖
**followup_spike**: none（AI 工具层有独立测试套件，修复 ScopeFilter 后跑回归即可验证）

## 10. Claude × GPT 共识声明

本设计经 3 轮辩论收敛：
- **Claude 主张**方案 A（middleware inject）→ GPT 提升为"typed TenantContext"→ 共识
- **GPT 主张**第三条路线（scoped repository）→ Claude 反对全量迁移 → 折中为 scope helper
- **GPT 发现** ScopeFilter fail-open + DataScope `or None` 语义风险 → 纳入修复
- **共识**：A 为主线（TenantContext），B 仅 audit mode；先修后架构
