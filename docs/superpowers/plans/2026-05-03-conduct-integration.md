# 德育三环整合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将德育模块从"班级孤岛"升级为"教育局→学校→家长"三层贯通的一体化系统，同时减少页面碎片、降低用户心智负担。

**Architecture:** 不新增页面，而是让现有页面 scope-adaptive（根据角色自动展示对应层级的数据）。后端新增 scope_service 统一聚合层 + rule template cascade 规则继承 + EventBus 驱动家长推送。前端 Dashboard/Rules 页面改造为多层自适应。

**Tech Stack:** FastAPI + SQLAlchemy async / Vue 3 + Naive UI / 现有 EventBus (`core/events.py`) / 现有 RBAC 体系

**设计原则：**
- 零新增页面：ConductDashboard 根据角色自动切换视图层级
- 规则继承不增加操作：学校/区级规则自动向下 cascade，班主任只需管差异
- 家长主动推送：EventBus 在记录积分时自动触发，家长无需主动刷新
- 数据上卷不增加操作：校级/区级数据从 conduct_records 实时聚合，无需"上报"按钮

---

## 现有资产盘点

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| 后端模型 | 8 表（含 scope 字段已预留） | `modules/conduct/models.py` | ConductRuleCategory.scope + school_id 已存在 |
| 后端服务 | admin_service + parent_service + rules_service + export_service | `modules/conduct/` | 4 service files |
| 前端管理 | 9 页面（Dashboard/Points/Rules/Rankings/Records/Groups/Settings/Parents/Export） | `frontend/src/pages/conduct/` | 全部就绪 |
| 前端家长 | 9 页面（Login/Register/Bind/Overview/Details/Rankings/Rules/Profile/Scores） | `frontend/src/pages/parent/` | 全部就绪 |
| 权限 | 5 个 conduct permission + 10 角色 RBAC | `core/permissions.py` | VIEW/MANAGE/RULES/PARENTS/EXPORT |
| 事件系统 | EventBus（进程内，exam.published 已接线） | `core/events.py` | 可直接注册 conduct.* 事件 |
| AI 工具 | 6 个 conduct tools + DataScope 隔离 | `ai/tools/conduct.py` | F003 class scope 已守卫 |

## 增量 vs 新建论证

- **默认立场：增量**。全部在现有模块上扩展
- ConductRuleCategory 已有 school_id + scope 字段，只需 enable 使用（当前硬编码 "class"）
- ConductDashboard.vue 已有 class_id 注入逻辑，扩展为 scope-adaptive 无需重写
- EventBus 已有注册机制，新增 `conduct.points_added` 事件零成本
- 不新建平行目录、不新建独立页面

## 交付路径

- 目标目录：`frontend/src/pages/conduct/` + `modules/conduct/`（增强现有）
- 生产 serving：nginx 443 → `frontend/dist/`（`npx vite build` 后用户可见）
- 用户访问 URL：`https://mcu.asia`（ConductDashboard 根据角色自动切换视图）

---

## File Structure

### 新建文件（3 个后端 service + 1 migration）

| 文件 | 职责 |
|------|------|
| `src/edu_cloud/modules/conduct/scope_service.py` | 多层聚合引擎：根据 user role 自动切换 class/school/district 层级查询 |
| `src/edu_cloud/modules/conduct/event_service.py` | 积分事件发射 + 家长通知生成 |
| `src/edu_cloud/modules/conduct/notification_router.py` | 家长通知拉取端点（复用 cp_token 认证） |
| `alembic/versions/d_conduct_notifications_table.py` | conduct_notifications 表 |

### 修改文件（后端 5 + 前端 3）

| 文件 | 变更 |
|------|------|
| `modules/conduct/rules_service.py` | 支持 scope="school" 创建 + cascade 查询（合并学校+班级规则） |
| `modules/conduct/admin_router.py` | 新增 scope-adaptive 聚合端点 + 学校级规则端点 |
| `modules/conduct/admin_service.py` | add_points 时触发 EventBus 事件 |
| `modules/conduct/models.py` | 新增 ConductNotification 模型 |
| `core/events.py` | 注册 conduct.points_added handler |
| `frontend/src/pages/conduct/ConductDashboard.vue` | scope-adaptive：根据角色显示 class/school/district 聚合视图 |
| `frontend/src/pages/conduct/ConductRules.vue` | 显示继承的学校级规则（只读）+ 班级覆盖 |
| `frontend/src/api/conduct.js` | 新增聚合 API + 通知 API 调用 |

---

## Task 1: Scope-Adaptive 聚合服务（后端核心）

**Files:**
- Create: `src/edu_cloud/modules/conduct/scope_service.py`
- Test: `tests/test_conduct/test_scope_service.py`

### 设计意图

一个 service 函数根据调用者的 role 自动决定聚合粒度：
- homeroom_teacher / subject_teacher → 返回单班数据
- grade_leader → 返回年级所有班对比
- principal / academic_director → 返回全校所有班对比
- district_admin → 返回辖区所有校对比

前端 Dashboard 只需调一个 endpoint，后端根据 JWT role 返回适配数据。

- [ ] **Step 1: 写 scope_service 的失败测试**

```python
# tests/test_conduct/test_scope_service.py
"""Scope-adaptive aggregation service tests."""
import pytest
from datetime import date, timedelta

from edu_cloud.modules.conduct.scope_service import get_conduct_overview


@pytest.mark.asyncio
async def test_overview_class_scope(db_session, seed_conduct_data):
    """班主任看到单班数据"""
    result = await get_conduct_overview(
        db=db_session,
        scope_type="class",
        scope_ids=[seed_conduct_data["class_id"]],
    )
    assert "summary" in result
    assert result["summary"]["total_students"] > 0
    assert result["summary"]["total_records"] > 0
    assert "rankings" in result
    assert "trend" in result
    assert len(result["trend"]) <= 4  # 最近 4 周


@pytest.mark.asyncio
async def test_overview_school_scope(db_session, seed_conduct_data):
    """校长看到全校班级对比"""
    result = await get_conduct_overview(
        db=db_session,
        scope_type="school",
        scope_ids=[seed_conduct_data["school_id"]],
    )
    assert "summary" in result
    assert "class_comparison" in result
    for cls in result["class_comparison"]:
        assert "class_name" in cls
        assert "avg_points" in cls
        assert "record_count" in cls


@pytest.mark.asyncio
async def test_overview_district_scope(db_session, seed_conduct_data):
    """教育局看到跨校对比"""
    result = await get_conduct_overview(
        db=db_session,
        scope_type="district",
        scope_ids=[seed_conduct_data["district"]],
    )
    assert "summary" in result
    assert "school_comparison" in result
    for school in result["school_comparison"]:
        assert "school_name" in school
        assert "avg_points" in school
        assert "total_students" in school
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_conduct/test_scope_service.py -v`
Expected: FAIL with "No module named 'edu_cloud.modules.conduct.scope_service'"

- [ ] **Step 3: 实现 scope_service.py**

```python
# src/edu_cloud/modules/conduct/scope_service.py
"""Scope-adaptive 德育数据聚合 — 一套查询适配所有角色层级。"""
import logging
from datetime import date, timedelta

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.conduct.models import ConductRecord, ConductSemester
from edu_cloud.modules.student.models import Student, Class
from edu_cloud.models.school import RegisteredSchool

logger = logging.getLogger(__name__)


async def get_conduct_overview(
    db: AsyncSession,
    scope_type: str,
    scope_ids: list[str],
    weeks: int = 4,
) -> dict:
    """
    统一聚合入口。scope_type 决定聚合粒度：
    - "class": scope_ids = [class_id, ...]
    - "school": scope_ids = [school_id, ...]
    - "district": scope_ids = [district_name, ...]
    """
    if scope_type == "class":
        return await _class_overview(db, scope_ids, weeks)
    elif scope_type == "school":
        return await _school_overview(db, scope_ids, weeks)
    elif scope_type == "district":
        return await _district_overview(db, scope_ids, weeks)
    raise ValueError(f"Unknown scope_type: {scope_type}")


async def _class_overview(db: AsyncSession, class_ids: list[str], weeks: int) -> dict:
    """单班/多班聚合（班主任/科任视角）"""
    since = date.today() - timedelta(weeks=weeks)

    # 汇总统计
    summary_q = (
        select(
            func.count(func.distinct(ConductRecord.student_id)).label("total_students"),
            func.count(ConductRecord.id).label("total_records"),
            func.coalesce(func.sum(case(
                (ConductRecord.points > 0, ConductRecord.points), else_=0
            )), 0).label("total_positive"),
            func.coalesce(func.sum(case(
                (ConductRecord.points < 0, ConductRecord.points), else_=0
            )), 0).label("total_negative"),
        )
        .where(ConductRecord.class_id.in_(class_ids))
    )
    row = (await db.execute(summary_q)).one()

    # TOP/BOTTOM 5 排行
    rank_q = (
        select(
            Student.id, Student.name,
            func.sum(ConductRecord.points).label("total"),
        )
        .join(ConductRecord, ConductRecord.student_id == Student.id)
        .where(ConductRecord.class_id.in_(class_ids))
        .group_by(Student.id, Student.name)
        .order_by(func.sum(ConductRecord.points).desc())
    )
    all_ranked = (await db.execute(rank_q)).all()
    top5 = [{"name": r.name, "points": r.total} for r in all_ranked[:5]]
    bottom5 = [{"name": r.name, "points": r.total} for r in all_ranked[-5:]] if len(all_ranked) > 5 else []

    # 周趋势
    trend = await _weekly_trend(db, class_ids, weeks)

    return {
        "scope_type": "class",
        "summary": {
            "total_students": row.total_students,
            "total_records": row.total_records,
            "total_positive": row.total_positive,
            "total_negative": row.total_negative,
        },
        "rankings": {"top": top5, "bottom": bottom5},
        "trend": trend,
    }


async def _school_overview(db: AsyncSession, school_ids: list[str], weeks: int) -> dict:
    """全校班级对比（校长/教务视角）"""
    # 全校汇总
    all_class_ids_q = select(Class.id).where(Class.school_id.in_(school_ids))
    all_class_ids = [r for r in (await db.execute(all_class_ids_q)).scalars().all()]

    summary_q = (
        select(
            func.count(func.distinct(ConductRecord.student_id)).label("total_students"),
            func.count(ConductRecord.id).label("total_records"),
        )
        .where(ConductRecord.class_id.in_(all_class_ids))
    )
    row = (await db.execute(summary_q)).one()

    # 班级对比
    comparison_q = (
        select(
            Class.id, Class.name.label("class_name"),
            func.count(ConductRecord.id).label("record_count"),
            func.coalesce(func.avg(ConductRecord.points), 0).label("avg_points"),
        )
        .join(ConductRecord, ConductRecord.class_id == Class.id)
        .where(Class.school_id.in_(school_ids))
        .group_by(Class.id, Class.name)
        .order_by(func.avg(ConductRecord.points).desc())
    )
    classes = (await db.execute(comparison_q)).all()

    return {
        "scope_type": "school",
        "summary": {
            "total_students": row.total_students,
            "total_records": row.total_records,
            "class_count": len(all_class_ids),
        },
        "class_comparison": [
            {"class_id": c.id, "class_name": c.class_name,
             "record_count": c.record_count, "avg_points": float(c.avg_points)}
            for c in classes
        ],
    }


async def _district_overview(db: AsyncSession, districts: list[str], weeks: int) -> dict:
    """跨校对比（教育局视角）"""
    # 获取辖区所有学校
    schools_q = select(RegisteredSchool.id, RegisteredSchool.name).where(
        RegisteredSchool.district.in_(districts),
        RegisteredSchool.is_active == True,
    )
    schools = (await db.execute(schools_q)).all()
    school_ids = [s.id for s in schools]

    if not school_ids:
        return {"scope_type": "district", "summary": {"total_schools": 0, "total_students": 0}, "school_comparison": []}

    # 按校聚合
    comparison_q = (
        select(
            Class.school_id,
            func.count(func.distinct(ConductRecord.student_id)).label("total_students"),
            func.count(ConductRecord.id).label("record_count"),
            func.coalesce(func.avg(ConductRecord.points), 0).label("avg_points"),
        )
        .join(ConductRecord, ConductRecord.class_id == Class.id)
        .where(Class.school_id.in_(school_ids))
        .group_by(Class.school_id)
    )
    rows = (await db.execute(comparison_q)).all()
    school_map = {s.id: s.name for s in schools}

    return {
        "scope_type": "district",
        "summary": {
            "total_schools": len(school_ids),
            "total_students": sum(r.total_students for r in rows),
        },
        "school_comparison": [
            {"school_id": r.school_id, "school_name": school_map.get(r.school_id, ""),
             "total_students": r.total_students, "record_count": r.record_count,
             "avg_points": float(r.avg_points)}
            for r in rows
        ],
    }


async def _weekly_trend(db: AsyncSession, class_ids: list[str], weeks: int) -> list[dict]:
    """最近 N 周的加分/扣分趋势"""
    result = []
    today = date.today()
    for i in range(weeks - 1, -1, -1):
        week_start = today - timedelta(weeks=i + 1)
        week_end = today - timedelta(weeks=i)
        q = (
            select(
                func.coalesce(func.sum(case(
                    (ConductRecord.points > 0, ConductRecord.points), else_=0
                )), 0).label("positive"),
                func.coalesce(func.sum(case(
                    (ConductRecord.points < 0, ConductRecord.points), else_=0
                )), 0).label("negative"),
            )
            .where(
                ConductRecord.class_id.in_(class_ids),
                ConductRecord.date >= week_start,
                ConductRecord.date < week_end,
            )
        )
        row = (await db.execute(q)).one()
        result.append({
            "week_start": week_start.isoformat(),
            "positive": row.positive,
            "negative": row.negative,
        })
    return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_conduct/test_scope_service.py -v`
Expected: 3 PASS

- [ ] **Step 5: 新增 scope-adaptive 路由端点**

在 `admin_router.py` 追加一个统一入口：

```python
# 追加到 admin_router.py 末尾

from edu_cloud.modules.conduct.scope_service import get_conduct_overview
from edu_cloud.api.permissions import get_visible_class_ids

@router.get("/overview")
async def conduct_overview(
    user=Depends(require_view_conduct),
    db: AsyncSession = Depends(get_db),
):
    """Scope-adaptive 德育概览 — 根据角色自动聚合对应层级数据。"""
    role = user["active_role"]
    role_name = role.role

    if role_name in ("platform_admin", "district_admin"):
        district = getattr(role, "district", None) or "default"
        return await get_conduct_overview(db, "district", [district])
    elif role_name in ("principal", "academic_director"):
        return await get_conduct_overview(db, "school", [role.school_id])
    else:
        class_ids = get_visible_class_ids(role)
        if class_ids is None:
            return await get_conduct_overview(db, "school", [role.school_id])
        return await get_conduct_overview(db, "class", class_ids)
```

- [ ] **Step 6: 端点集成测试**

```python
# tests/test_conduct/test_scope_service.py 追加

@pytest.mark.asyncio
async def test_overview_endpoint_homeroom(client_homeroom):
    """班主任调 /overview 返回 class scope"""
    resp = await client_homeroom.get("/api/v1/conduct/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_type"] == "class"


@pytest.mark.asyncio
async def test_overview_endpoint_principal(client_principal):
    """校长调 /overview 返回 school scope"""
    resp = await client_principal.get("/api/v1/conduct/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_type"] == "school"
    assert "class_comparison" in data
```

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/conduct/scope_service.py tests/test_conduct/test_scope_service.py
git add src/edu_cloud/modules/conduct/admin_router.py
git commit -m "feat(conduct): scope-adaptive overview service — 一个端点适配所有角色层级"
```

---

## Task 2: 规则模板 Cascade（学校规则自动继承到班级）

**Files:**
- Modify: `src/edu_cloud/modules/conduct/rules_service.py`
- Modify: `src/edu_cloud/modules/conduct/admin_router.py`
- Test: `tests/test_conduct/test_rules_cascade.py`

### 设计意图

启用已有的 `scope="school"` 字段。学校级规则自动出现在每个班的规则列表中（标记为"学校规则"、只读）。班主任可以新增班级规则，但不能修改学校规则。教务主任/校长可以管理学校级规则。

**不新增页面**——在现有 ConductRules.vue 中，学校规则显示在顶部（带"学校"标签），班级规则显示在下方。

- [ ] **Step 1: 写 cascade 查询的失败测试**

```python
# tests/test_conduct/test_rules_cascade.py
"""规则 cascade 测试：学校规则自动出现在班级规则列表中。"""
import pytest

from edu_cloud.modules.conduct.rules_service import get_rules, create_category


@pytest.mark.asyncio
async def test_school_rule_visible_in_class(db_session, seed_school):
    """学校级规则在班级查询时可见"""
    # 创建学校级规则
    school_cat = await create_category(
        db_session, class_id=None, school_id=seed_school["id"],
        name="校级文明规范", scope="school",
    )
    # 创建班级规则
    class_cat = await create_category(
        db_session, class_id=seed_school["class_id"],
        name="班级纪律", scope="class",
    )

    # 查询班级规则（应该包含学校规则）
    rules = await get_rules(db_session, class_id=seed_school["class_id"])
    names = [r["name"] for r in rules]
    assert "校级文明规范" in names
    assert "班级纪律" in names

    # 学校规则标记为只读
    school_rule = next(r for r in rules if r["name"] == "校级文明规范")
    assert school_rule["scope"] == "school"
    assert school_rule["readonly"] is True


@pytest.mark.asyncio
async def test_class_rule_not_visible_in_other_class(db_session, seed_school):
    """班级规则不跨班可见"""
    await create_category(
        db_session, class_id="other_class_id",
        name="其他班规则", scope="class",
    )
    rules = await get_rules(db_session, class_id=seed_school["class_id"])
    names = [r["name"] for r in rules]
    assert "其他班规则" not in names
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_conduct/test_rules_cascade.py -v`
Expected: FAIL (create_category 不接受 school_id/scope 参数)

- [ ] **Step 3: 修改 rules_service.py 支持 cascade**

```python
# rules_service.py — 修改 get_rules 和 create_category

async def get_rules(db: AsyncSession, class_id: str) -> list[dict]:
    """Get nested categories + items for a class, including inherited school rules."""
    # 查出班级所属学校
    from edu_cloud.modules.student.models import Class
    cls = (await db.execute(select(Class).where(Class.id == class_id))).scalar_one_or_none()
    school_id = cls.school_id if cls else None

    # 查询：本班规则 + 本校学校级规则
    q = (
        select(ConductRuleCategory)
        .where(
            (ConductRuleCategory.class_id == class_id) |
            ((ConductRuleCategory.school_id == school_id) & (ConductRuleCategory.scope == "school"))
        )
        .order_by(ConductRuleCategory.scope.desc(), ConductRuleCategory.sort_order, ConductRuleCategory.name)
    )
    categories = (await db.execute(q)).scalars().all()

    result = []
    for cat in categories:
        items = (
            await db.execute(
                select(ConductRuleItem)
                .where(ConductRuleItem.category_id == cat.id)
                .order_by(ConductRuleItem.sort_order, ConductRuleItem.name)
            )
        ).scalars().all()

        result.append({
            "id": cat.id,
            "name": cat.name,
            "scope": cat.scope,
            "readonly": cat.scope == "school",
            "sort_order": cat.sort_order,
            "items": [
                {"id": item.id, "name": item.name, "points": item.points, "sort_order": item.sort_order}
                for item in items
            ],
        })

    return result


async def create_category(
    db: AsyncSession,
    class_id: str | None = None,
    school_id: str | None = None,
    name: str = "",
    scope: str = "class",
    sort_order: int = 0,
) -> dict:
    """Create a rule category at class or school level."""
    cat = ConductRuleCategory(
        class_id=class_id,
        school_id=school_id,
        name=name,
        scope=scope,
        sort_order=sort_order,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "scope": cat.scope, "sort_order": cat.sort_order}
```

- [ ] **Step 4: 新增学校级规则管理端点**

```python
# admin_router.py 追加 — 学校级规则管理（教务/校长可用）

@router.get("/schools/{school_id}/rules")
async def get_school_rules(
    school_id: str,
    user=Depends(require_manage_rules),
    db: AsyncSession = Depends(get_db),
):
    """获取学校级规则（教务/校长管理入口）"""
    from edu_cloud.modules.conduct import rules_service
    cats = (await db.execute(
        select(ConductRuleCategory)
        .where(ConductRuleCategory.school_id == school_id, ConductRuleCategory.scope == "school")
        .order_by(ConductRuleCategory.sort_order)
    )).scalars().all()
    result = []
    for cat in cats:
        items = (await db.execute(
            select(ConductRuleItem).where(ConductRuleItem.category_id == cat.id)
            .order_by(ConductRuleItem.sort_order)
        )).scalars().all()
        result.append({
            "id": cat.id, "name": cat.name, "scope": "school", "sort_order": cat.sort_order,
            "items": [{"id": i.id, "name": i.name, "points": i.points, "sort_order": i.sort_order} for i in items],
        })
    return result


@router.post("/schools/{school_id}/rules/categories")
async def create_school_rule_category(
    school_id: str,
    body: RuleCategoryCreate,
    user=Depends(require_manage_rules),
    db: AsyncSession = Depends(get_db),
):
    """创建学校级规则分类"""
    from edu_cloud.modules.conduct import rules_service
    return await rules_service.create_category(
        db, class_id=None, school_id=school_id,
        name=body.name, scope="school", sort_order=body.sort_order,
    )
```

- [ ] **Step 5: 运行测试**

Run: `.venv/bin/python -m pytest tests/test_conduct/test_rules_cascade.py tests/test_conduct/test_admin_api.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/conduct/rules_service.py
git add src/edu_cloud/modules/conduct/admin_router.py
git add tests/test_conduct/test_rules_cascade.py
git commit -m "feat(conduct): rule template cascade — 学校规则自动继承到班级"
```

---

## Task 3: 积分事件 + 家长通知

**Files:**
- Create: `src/edu_cloud/modules/conduct/event_service.py`
- Create: `src/edu_cloud/modules/conduct/notification_router.py`
- Modify: `src/edu_cloud/modules/conduct/models.py`
- Modify: `src/edu_cloud/modules/conduct/admin_service.py`
- Create: `alembic/versions/d_conduct_notifications_table.py`
- Test: `tests/test_conduct/test_notifications.py`

### 设计意图

教师记录积分时，EventBus 自动触发通知写入。家长端只需拉取未读通知列表（比 WebSocket 简单可靠，移动端兼容性好）。

通知不是独立页面——嵌入 ParentOverview 顶部作为"未读消息"卡片。

- [ ] **Step 1: 新增 ConductNotification 模型**

```python
# models.py 追加

class ConductNotification(Base, IdMixin):
    """家长端通知（积分变动触发）"""
    __tablename__ = "conduct_notifications"

    parent_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False,
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), index=True, nullable=False,
    )
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conduct_records.id"), nullable=False,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
```

- [ ] **Step 2: 写 migration**

```python
# alembic/versions/d_conduct_notifications_table.py
"""conduct notifications table

Revision ID: d0ndc7n0t1fy
Revises: a8c7d2e4f135
"""
from alembic import op
import sqlalchemy as sa

revision = "d0ndc7n0t1fy"
down_revision = "a8c7d2e4f135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conduct_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False, index=True),
        sa.Column("record_id", sa.String(36), sa.ForeignKey("conduct_records.id"), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("conduct_notifications")
```

- [ ] **Step 3: 实现 event_service.py**

```python
# src/edu_cloud/modules/conduct/event_service.py
"""积分事件处理：记录积分后自动通知家长。"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.guardian import GuardianStudentLink
from edu_cloud.modules.conduct.models import ConductNotification, ConductRecord
from edu_cloud.modules.student.models import Student

logger = logging.getLogger(__name__)


async def notify_parents_on_points(db: AsyncSession, record_id: str) -> int:
    """为积分记录创建家长通知，返回通知数量。"""
    record = (await db.execute(
        select(ConductRecord).where(ConductRecord.id == record_id)
    )).scalar_one_or_none()
    if not record:
        return 0

    student = (await db.execute(
        select(Student).where(Student.id == record.student_id)
    )).scalar_one_or_none()
    if not student:
        return 0

    # 查找绑定该学生的所有家长
    links = (await db.execute(
        select(GuardianStudentLink).where(GuardianStudentLink.student_id == record.student_id)
    )).scalars().all()

    if not links:
        return 0

    point_str = f"+{record.points}" if record.points > 0 else str(record.points)
    title = f"{student.name} 德育积分变动 {point_str}"
    body = f"原因：{record.reason}（{record.date}）"

    count = 0
    for link in links:
        notif = ConductNotification(
            parent_user_id=link.guardian_user_id,
            student_id=record.student_id,
            record_id=record_id,
            title=title,
            body=body,
        )
        db.add(notif)
        count += 1

    await db.commit()
    logger.info(f"Created {count} notifications for record {record_id}")
    return count
```

- [ ] **Step 4: 在 admin_service.add_points 中触发事件**

在 `admin_service.py` 的 `add_points` 函数末尾追加：

```python
    # 触发家长通知
    from edu_cloud.modules.conduct.event_service import notify_parents_on_points
    for rec in created_records:
        await notify_parents_on_points(db, rec.id)
```

- [ ] **Step 5: 实现家长通知拉取端点**

```python
# src/edu_cloud/modules/conduct/notification_router.py
"""家长通知端点（cp_token 认证）"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.conduct.models import ConductNotification
from edu_cloud.modules.conduct.parent_router import get_current_parent, get_parent_db

router = APIRouter(prefix="/api/v1/conduct/parent", tags=["conduct-parent-notifications"])


@router.get("/notifications")
async def get_notifications(
    unread_only: bool = False,
    limit: int = 20,
    parent=Depends(get_current_parent),
    db: AsyncSession = Depends(get_parent_db),
):
    """拉取家长通知列表"""
    q = (
        select(ConductNotification)
        .where(ConductNotification.parent_user_id == parent["user_id"])
        .order_by(ConductNotification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        q = q.where(ConductNotification.is_read == False)

    notifs = (await db.execute(q)).scalars().all()
    return [
        {
            "id": n.id, "title": n.title, "body": n.body,
            "is_read": n.is_read, "created_at": n.created_at.isoformat(),
            "student_id": n.student_id,
        }
        for n in notifs
    ]


@router.post("/notifications/read-all")
async def mark_all_read(
    parent=Depends(get_current_parent),
    db: AsyncSession = Depends(get_parent_db),
):
    """标记所有通知为已读"""
    await db.execute(
        update(ConductNotification)
        .where(
            ConductNotification.parent_user_id == parent["user_id"],
            ConductNotification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 6: 注册 router 到 app.py**

在 `app.py` 的 conduct router 导入处追加：
```python
from edu_cloud.modules.conduct.notification_router import router as conduct_notification_router
app.include_router(conduct_notification_router)
```

- [ ] **Step 7: 写测试**

```python
# tests/test_conduct/test_notifications.py
"""通知系统测试"""
import pytest
from edu_cloud.modules.conduct.event_service import notify_parents_on_points


@pytest.mark.asyncio
async def test_notification_created_on_points(db_session, seed_parent_binding, seed_conduct_record):
    """积分记录触发家长通知"""
    count = await notify_parents_on_points(db_session, seed_conduct_record["id"])
    assert count == 1


@pytest.mark.asyncio
async def test_no_notification_without_binding(db_session, seed_conduct_record_no_parent):
    """无家长绑定时不创建通知"""
    count = await notify_parents_on_points(db_session, seed_conduct_record_no_parent["id"])
    assert count == 0


@pytest.mark.asyncio
async def test_notification_content(db_session, seed_parent_binding, seed_conduct_record):
    """通知内容包含学生姓名和分值"""
    from sqlalchemy import select
    from edu_cloud.modules.conduct.models import ConductNotification

    await notify_parents_on_points(db_session, seed_conduct_record["id"])
    notif = (await db_session.execute(select(ConductNotification))).scalar_one()
    assert seed_conduct_record["student_name"] in notif.title
    assert seed_conduct_record["reason"] in notif.body
```

- [ ] **Step 8: 运行测试**

Run: `.venv/bin/python -m pytest tests/test_conduct/test_notifications.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add src/edu_cloud/modules/conduct/models.py
git add src/edu_cloud/modules/conduct/event_service.py
git add src/edu_cloud/modules/conduct/notification_router.py
git add src/edu_cloud/modules/conduct/admin_service.py
git add alembic/versions/d_conduct_notifications_table.py
git add tests/test_conduct/test_notifications.py
git commit -m "feat(conduct): event-driven parent notifications — 积分变动自动通知家长"
```

---

## Task 4: 前端 Dashboard Scope-Adaptive 改造

**Files:**
- Modify: `frontend/src/pages/conduct/ConductDashboard.vue`
- Modify: `frontend/src/pages/conduct/ConductRules.vue`
- Modify: `frontend/src/api/conduct.js`
- Modify: `frontend/src/pages/parent/ParentOverview.vue`
- Test: `frontend/src/pages/conduct/__tests__/ConductDashboard.spec.js`

### 设计意图

ConductDashboard 改为调用 `/api/v1/conduct/overview` 统一端点，根据返回的 `scope_type` 渲染不同的视图：
- `class` → 现有视图（学生排行 + 最近记录）
- `school` → 班级对比卡片（每班均分/记录数/排行）
- `district` → 学校对比卡片（每校均分/学生数/活跃度）

零新增页面。同一个 ConductDashboard 适配三层角色。

- [ ] **Step 1: api/conduct.js 新增接口**

```javascript
// 追加到 conduct.js

// Scope-adaptive overview（根据角色自动返回对应层级数据）
export function getConductOverview() {
  return api.get('/conduct/overview')
}

// 学校级规则管理
export function getSchoolRules(schoolId) {
  return api.get(`/conduct/schools/${schoolId}/rules`)
}
export function createSchoolCategory(schoolId, data) {
  return api.post(`/conduct/schools/${schoolId}/rules/categories`, data)
}

// 家长通知
export function getParentNotifications(unreadOnly = false) {
  return parentClient.get('/conduct/parent/notifications', { params: { unread_only: unreadOnly } })
}
export function markNotificationsRead() {
  return parentClient.post('/conduct/parent/notifications/read-all')
}
```

- [ ] **Step 2: 改造 ConductDashboard.vue 为 scope-adaptive**

```vue
<!-- ConductDashboard.vue — 核心改造逻辑（template 条件渲染） -->
<template>
  <n-page-header title="德育概览" />

  <n-spin :show="loading">
    <!-- 通用汇总卡片（所有层级共享） -->
    <div class="stat-cards">
      <n-card v-for="stat in summaryCards" :key="stat.label">
        <n-statistic :label="stat.label" :value="stat.value" />
      </n-card>
    </div>

    <!-- CLASS 层级：学生排行 + 趋势 + 最近记录 -->
    <template v-if="data?.scope_type === 'class'">
      <n-card title="积分排行">
        <n-data-table :columns="studentRankColumns" :data="data.rankings?.top" size="small" />
      </n-card>
      <n-card title="周趋势">
        <v-chart :option="trendChartOption" autoresize style="height: 200px" />
      </n-card>
    </template>

    <!-- SCHOOL 层级：班级横向对比 -->
    <template v-else-if="data?.scope_type === 'school'">
      <n-card title="班级德育对比">
        <n-data-table :columns="classCompareColumns" :data="data.class_comparison" size="small" />
      </n-card>
    </template>

    <!-- DISTRICT 层级：学校横向对比 -->
    <template v-else-if="data?.scope_type === 'district'">
      <n-card title="学校德育对比">
        <n-data-table :columns="schoolCompareColumns" :data="data.school_comparison" size="small" />
      </n-card>
    </template>
  </n-spin>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { getConductOverview } from '@/api/conduct'

const loading = ref(false)
const data = ref(null)

const summaryCards = computed(() => {
  if (!data.value?.summary) return []
  const s = data.value.summary
  const cards = [{ label: '学生总数', value: s.total_students || s.total_schools || 0 }]
  if (s.total_records != null) cards.push({ label: '记录总数', value: s.total_records })
  if (s.total_positive != null) cards.push({ label: '加分合计', value: `+${s.total_positive}` })
  if (s.total_negative != null) cards.push({ label: '扣分合计', value: s.total_negative })
  if (s.class_count != null) cards.push({ label: '班级数', value: s.class_count })
  return cards
})

onMounted(async () => {
  loading.value = true
  try {
    const resp = await getConductOverview()
    data.value = resp.data
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 3: 改造 ConductRules.vue 显示继承规则**

在现有 ConductRules.vue 的规则列表中，学校级规则显示在顶部，带"学校"标签且不可编辑：

```vue
<!-- ConductRules.vue 修改 — 规则列表区分 scope -->
<n-collapse>
  <n-collapse-item v-for="cat in rules" :key="cat.id" :title="cat.name">
    <template #header-extra>
      <n-tag v-if="cat.scope === 'school'" type="info" size="small">学校规则</n-tag>
      <n-space v-else>
        <n-button size="tiny" @click="editCategory(cat)">编辑</n-button>
        <n-popconfirm @positive-click="deleteCategory(cat.id)">
          <template #trigger><n-button size="tiny" type="error">删除</n-button></template>
          确认删除此分类？
        </n-popconfirm>
      </n-space>
    </template>
    <!-- items 列表，学校规则 readonly -->
    <n-list>
      <n-list-item v-for="item in cat.items" :key="item.id">
        {{ item.name }}
        <template #suffix>
          <n-tag :type="item.points > 0 ? 'success' : 'error'" size="small">
            {{ item.points > 0 ? '+' : '' }}{{ item.points }}
          </n-tag>
        </template>
      </n-list-item>
    </n-list>
  </n-collapse-item>
</n-collapse>
```

- [ ] **Step 4: ParentOverview 追加通知卡片**

在 ParentOverview.vue 顶部追加未读通知区域：

```vue
<!-- ParentOverview.vue 追加 — 未读通知卡片 -->
<n-card v-if="notifications.length > 0" title="最新动态" size="small" style="margin-bottom: 16px">
  <n-list>
    <n-list-item v-for="n in notifications.slice(0, 5)" :key="n.id">
      <n-thing :title="n.title" :description="n.body" />
      <template #suffix>
        <n-text depth="3">{{ formatTime(n.created_at) }}</n-text>
      </template>
    </n-list-item>
  </n-list>
  <n-button v-if="notifications.length > 5" text @click="markAllRead">全部已读</n-button>
</n-card>
```

```javascript
// ParentOverview.vue script 追加
import { getParentNotifications, markNotificationsRead } from '@/api/conduct'

const notifications = ref([])

onMounted(async () => {
  const resp = await getParentNotifications(true)
  notifications.value = resp.data
})

async function markAllRead() {
  await markNotificationsRead()
  notifications.value = []
}
```

- [ ] **Step 5: 前端测试**

```javascript
// frontend/src/pages/conduct/__tests__/ConductDashboard.spec.js 追加

describe('Scope-adaptive rendering', () => {
  it('renders class view for homeroom teacher', async () => {
    vi.mocked(getConductOverview).mockResolvedValue({
      data: { scope_type: 'class', summary: { total_students: 45, total_records: 120 }, rankings: { top: [] }, trend: [] }
    })
    const wrapper = mount(ConductDashboard)
    await flushPromises()
    expect(wrapper.text()).toContain('积分排行')
    expect(wrapper.text()).not.toContain('班级德育对比')
  })

  it('renders school view for principal', async () => {
    vi.mocked(getConductOverview).mockResolvedValue({
      data: { scope_type: 'school', summary: { total_students: 1200, class_count: 36 }, class_comparison: [] }
    })
    const wrapper = mount(ConductDashboard)
    await flushPromises()
    expect(wrapper.text()).toContain('班级德育对比')
  })

  it('renders district view for bureau admin', async () => {
    vi.mocked(getConductOverview).mockResolvedValue({
      data: { scope_type: 'district', summary: { total_schools: 5 }, school_comparison: [] }
    })
    const wrapper = mount(ConductDashboard)
    await flushPromises()
    expect(wrapper.text()).toContain('学校德育对比')
  })
})
```

- [ ] **Step 6: 运行前端测试**

Run: `cd ~/projects/edu-cloud/frontend && npx vitest run src/pages/conduct/__tests__/ConductDashboard.spec.js`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/conduct/ConductDashboard.vue
git add frontend/src/pages/conduct/ConductRules.vue
git add frontend/src/pages/parent/ParentOverview.vue
git add frontend/src/api/conduct.js
git add frontend/src/pages/conduct/__tests__/ConductDashboard.spec.js
git commit -m "feat(conduct): scope-adaptive dashboard — 一个页面适配三层角色"
```

---

## Task 5: 集成验证 + Build

**Files:**
- No new files — integration verification

- [ ] **Step 1: 后端全量测试**

Run: `cd ~/projects/edu-cloud && .venv/bin/python -m pytest tests/test_conduct/ -v`
Expected: ALL PASS (68 existing + ~10 new = ~78)

- [ ] **Step 2: 前端全量测试**

Run: `cd ~/projects/edu-cloud/frontend && npx vitest run`
Expected: 2404+ tests, 0 failed

- [ ] **Step 3: Build 前端**

Run: `cd ~/projects/edu-cloud/frontend && npx vite build`
Expected: build 成功，dist/ 产出

- [ ] **Step 4: 验证 scope-adaptive API**

```bash
# 用 admin token 测试 district scope
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:9000/api/v1/conduct/overview | python3 -m json.tool | head -5
# Expected: {"scope_type": "district", ...}
```

- [ ] **Step 5: Commit 最终集成**

```bash
git add -A
git commit -m "feat(conduct): 三环整合完成 — 教育局/学校/家长一体化德育系统"
```

---

## 总结：三环打通的完整数据流

```
教育局 admin                 校长/教务                   班主任                      家长
     │                          │                         │                          │
     │ GET /overview            │ GET /overview            │ GET /overview             │ GET /notifications
     │ → scope=district         │ → scope=school           │ → scope=class             │ → 未读积分通知
     │ → 跨校对比表             │ → 班级对比表             │ → 学生排行+趋势           │
     │                          │                         │                          │
     │ GET /schools/{id}/rules  │ GET /schools/{id}/rules  │ GET /classes/{id}/rules   │ GET /classes/{id}/rules
     │ → 管理区级规则模板       │ → 管理学校规则           │ → 看到继承的学校规则      │ → 看到合并后的规则
     │     ↓ cascade            │     ↓ cascade            │   + 自己班规              │
     │     学校可见             │     班级可见             │                          │
     └─────────────────────────┴─────────────────────────┴──────────────────────────┘
                                                           │
                                                           │ POST /records (add_points)
                                                           │ → EventBus → notify_parents
                                                           │              → 家长自动收到通知
```

**关键整合点：**
1. **一个 `/overview` 端点**替代 N 个层级独立的 dashboard API
2. **一个 ConductDashboard.vue**根据 `scope_type` 条件渲染，无需新页面
3. **规则 cascade**让学校规则自动下沉，班主任无需手动同步
4. **EventBus 驱动**让家长零操作接收通知，无需刷新
