# 好分数业务复刻 Phase 1: 架构基座 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 Nuxt 3 前端项目骨架（8 模块 45 页面 stub）+ 后端动态菜单系统 + 预聚合数据模型，为 Phase 2（功能迁移）和 Phase 3（新模块填充）打下架构基座。

**Architecture:** 前端用 Nuxt 3 + Element Plus 替代现有 Vite + Naive UI。后端扩展现有 FastAPI + PostgreSQL，新增 menu_configs 等 4 张表和 MenuService。前后端通过 RESTful API 通信，菜单系统后端驱动。

**Tech Stack:** Nuxt 3, Vue 3, Element Plus, Pinia, TypeScript | FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL

**Design:** `docs/plans/2026-04-12-haofenshu-biz-replication-design.md`

## 进度汇总（2026-04-13 23:25 Planner 更新）

| 阶段 | 代码状态 | Gate 状态 | Commits / 关键产物 |
|------|---------|-----------|-------------------|
| **Gate 1 plan_review** | — | ✅ PASS (R5 + 3ee0205 R2 追认) | `docs/plans/2026-04-12-haofenshu-phase1-plan-review-r5.md` |
| **Batch 1 Task 1-3** Schema + Menu API | ✅ 完成 | ✅ **Gate 2 R2 PASS** | `e64957a` (R2 修复) → `ef8a32a` (gate + R2 报告) |
| **Batch 2 Task 4-9** Frontend 骨架 | ✅ **完成** (2026-04-13 22:14) | 🟡 **Gate 2 待 GPT 审查** | `08d86f0..674cd99` (6 commits) + `78e0764` (审查交接单) |
| **Batch 3 Task 10-12** 45 页面 stub + 端到端 | ⚪ 未开始 | — | — |

**Batch 2 审查交接单**: `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2.md`（8 项 🔀 改进 + 独立 Gate 4 步证据 + R2-F001 继承处置 + useMenus test_debt 记录）

**下一步 Planner 动作**: 调用 codex-review 对 commits `08d86f0..674cd99` 发起 Gate 2 Batch 2 审查。若 PASS → 生成 Batch 3 Executor 交接卡。若 FAIL → Round 2 修复或 design-concern 处置。

**风险/卡点**（Batch 3 前需解决或接受）:
- **R1** WSL 后端 hot-reload 失效 → 端到端验证阻塞（Batch 3 Task 12 必须解决）
- **R2** Windows+SQLite 全量 pytest >10min → 本地只能分层跑（接受，用 Batch 1 R2 baseline 外推）
- **R3** pre-existing 2 稳定 failures (`tool_access_fail_closed`) → 不指向 Batch 2，R2-F001 继承处置记录
- **R4** useMenus startsWith 理论误匹配 → Phase 2 填充子页面前必须加分隔符（test_debt）

## 批次拆分（F008 处置）

| 批次 | 范围 | Task | 独立验证点 |
|------|------|------|-----------|
| Batch 1 | Schema + API | Task 1-3 | migration 可升降 + MenuService 8 tests + 全量回归 |
| Batch 2 | Frontend 骨架 | Task 4-9 | **Batch 2 独立 Gate** (F008 R2)：①Nuxt dev 启动无报错 ②POST /auth/login → 拿到 access_token ③访问 /home 渲染模块卡片 ④点击模块跳转到子页面（即使是 Task 9 的占位页） |
| Batch 3 | Frontend 完善 | Task 10-12 | PowerFilter + 45 stub + 端到端全链路验证 |

**Batch 2 独立验证命令**（F008 R2，不依赖 Task 12）:
```bash
# 后端启动（假设 Batch 1 已完成）
cd C:/Users/Administrator/edu-cloud && python scripts/seed_menus.py
# 前端启动
cd C:/Users/Administrator/edu-cloud/frontend-nuxt && npx nuxt dev --port 3000 &
# 3 步验证
curl -s http://localhost:3000/ -o /dev/null -w "%{http_code}\n"  # 200
curl -s -X POST http://localhost:9000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}' | python -c "import sys,json; d=json.load(sys.stdin); assert 'access_token' in d; print('login OK')"
# 浏览器手动: 访问 http://localhost:3000/login 登录 → /home 可见模块卡片
```

## Contract Pack（F001 处置）

### invariants（变更不变量）

1. **INV-01 现有 frontend/ 零改动**: 新建 `frontend-nuxt/`，不修改 `frontend/` 任何文件
2. **INV-02 现有 API 路由不变**: 只新增 `/api/v1/menus` + `conduct_admin_router` 挂载（F002 R1 behavior_change，2026-04-13 用户批准追认扩大 Batch 1 范围：commit 3488b52 已将 `src/edu_cloud/modules/conduct/admin_router` 28 个端点接入 `/api/v1/conduct/classes/*`，纳入 Batch 1 交付范围；其他现有 193 路由保持不变）
3. **INV-03 现有测试全量通过**: 每个 Task commit 前跑 `pytest --tb=short -q`，≥1582 tests PASS
4. **INV-04 Alembic 可逆**: 新 migration 支持 upgrade + downgrade
5. **INV-05 现有模型导入链不断**: 新增 models 不影响现有 `Base.metadata` 和 autogenerate
6. **INV-06 认证契约一致**: menu router 使用 `get_current_user` 返回的 `current_role`（UserRole ORM 对象），不假设 dict 结构

### counter_examples（反例/常见陷阱）

1. menu_configs.roles 用 PostgreSQL `ARRAY(String)` → SQLite smoke test 失败（F005）→ 改用 JSON
2. `SchoolSettingsService(db).get_enabled_modules()` → 不存在的类方法（F004）→ 用函数 `get_enabled_modules(db, school_id=...)`
3. `user.get("active_role")` → `get_current_user` 返回 `current_role`（UserRole ORM 对象）（F004）
4. `switchRole(roleIndex)` → 后端用 `role_id` 不是 index（F007）

### risk_modules（高风险模块）

| 模块 | 风险 | 缓解 |
|------|------|------|
| `alembic/versions/` | migration 破坏现有表 | downgrade 测试 + SQLite smoke test |
| `modules/menu/models.py` | ARRAY 方言不兼容 | 用 JSON 存储 roles |
| `frontend-nuxt/composables/useApi.ts` | 引用不存在后端端点 | 逐端点核对后端路由 |
| `modules/analytics/analysis_models.py` | import 链断裂 | app.py 显式 import 确保 Base.metadata 可见 |

### test_debt（测试债务）

| 项 | 说明 | 计划偿还 |
|----|------|---------|
| useApi 前端集成测试 | Nuxt composable 无自动化测试 | Phase 2 补 Vitest 前端测试 |
| seed_menus.py 集成测试 | 种子脚本只手动验证 | Task 12 端到端验证覆盖 |
| PowerFilter 组件测试 | 级联联动无自动化测试 | Phase 2 补前端组件测试 |

---

## 文件结构

### 后端新增/修改

```
src/edu_cloud/
  modules/
    menu/                              # 新模块
      __init__.py
      models.py                        # MenuConfig model
      service.py                       # MenuService
      router.py                        # GET /api/v1/menus
    analytics/
      analysis_models.py               # 新增: ClassAnalysis, StudentAnalysis, StudentKnpMastery（F006: 路径统一为 analysis_models.py）
  api/
    app.py                             # 修改: 挂载 menu router
scripts/
  seed_menus.py                        # 菜单种子数据
alembic/versions/
  xxxx_add_menu_and_analysis_tables.py # migration
tests/
  test_menu/
    __init__.py
    test_menu_service.py
    test_menu_api.py
```

### 前端新增（`frontend-nuxt/`）

```
frontend-nuxt/
  nuxt.config.ts
  package.json
  tsconfig.json
  assets/css/main.scss                 # Element Plus 主题 + CSS 变量
  composables/
    useApi.ts
    useMenus.ts
    usePowerOptions.ts
  middleware/
    auth.global.ts
  layouts/
    default.vue
    fullscreen.vue
    auth.vue
  stores/
    auth.ts
    context.ts
  components/
    shell/TopNav.vue
    shell/SubNav.vue
    shell/UserDropdown.vue
    common/PowerFilter.vue
  pages/
    index.vue
    login.vue
    home.vue
    exam/{list,quiz,grading,answercard,statistics}.vue
    report/{exam,contrast,custom,table,level-score,config}.vue
    study/{dashboard,class,student,layer}.vue
    work/{list,publish,scan,sync}.vue
    lesson/{console,after-exam,resources,space}.vue
    research/{questions,paper-builder,group-prep,knowledge,plan,radar,school-resources}.vue
    baseinfo/{students,teachers,grades,records,schedule,selected-exam,vip}.vue
    academic/{semester,timetable,course-selection,exam-schedule,score-manage}.vue
    knowledge-tree/index.vue
```

---

### Task 1: 后端 — Alembic migration（menu_configs + 预聚合表 + rank 字段）

**Files:**
- Create: `src/edu_cloud/modules/menu/__init__.py`
- Create: `src/edu_cloud/modules/menu/models.py`
- Create: `src/edu_cloud/modules/analytics/analysis_models.py`
- Create: `alembic/versions/c1a2b3_add_menu_and_analysis_tables.py`
- Modify: `src/edu_cloud/modules/exam/models.py` — ExamResult 加 rank 字段
- Test: `tests/test_menu/__init__.py`
- Test: `tests/test_alembic_migration.py`（已有，自动覆盖新表）

- [ ] **Step 1: 创建 menu 模块目录和 models.py**

```python
# src/edu_cloud/modules/menu/__init__.py
# Menu module
```

```python
# src/edu_cloud/modules/menu/models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from edu_cloud.models.base import Base


class MenuConfig(Base):
    __tablename__ = "menu_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("menu_configs.id"), nullable=True
    )
    path: Mapped[str | None] = mapped_column(String(128), nullable=True)
    roles = Column(JSON, nullable=False, server_default="[]")  # F005: JSON 替代 ARRAY，兼容 SQLite smoke test
    requires_module: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: 创建预聚合 models**

```python
# src/edu_cloud/modules/analytics/analysis_models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from edu_cloud.models.base import Base


class ClassAnalysis(Base):
    __tablename__ = "class_analysis"
    __table_args__ = (
        UniqueConstraint("exam_id", "subject_id", "class_id", name="uq_class_analysis"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"), nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), nullable=False)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), nullable=False)
    avg_score = Column(NUMERIC(6, 2))
    max_score = Column(NUMERIC(6, 2))
    min_score = Column(NUMERIC(6, 2))
    pass_rate = Column(NUMERIC(5, 2))
    excellent_rate = Column(NUMERIC(5, 2))
    student_count = Column(Integer)
    score_distribution = Column(JSON)
    common_wrong_questions = Column(JSON)
    knowledge_mastery = Column(JSON)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentAnalysis(Base):
    __tablename__ = "student_analysis"
    __table_args__ = (
        UniqueConstraint("student_id", "exam_id", name="uq_student_analysis"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), nullable=False)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), nullable=False)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), nullable=False)
    total_score = Column(NUMERIC(7, 2))
    rank_in_class = Column(Integer)
    rank_in_grade = Column(Integer)
    subject_scores = Column(JSON)
    weak_knowledge = Column(JSON)
    improvement_trend = Column(JSON)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentKnpMastery(Base):
    __tablename__ = "student_knp_mastery"
    __table_args__ = (
        UniqueConstraint("student_id", "exam_id", "knp_id", name="uq_student_knp_mastery"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), nullable=False)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), nullable=False)
    knp_id: Mapped[str] = mapped_column(String(64), nullable=False)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), nullable=False)
    stu_rate = Column(NUMERIC(4, 3))
    class_rate = Column(NUMERIC(4, 3))
    grade_rate = Column(NUMERIC(4, 3))
```

- [ ] **Step 3: ExamResult 加 rank 字段**

在 `src/edu_cloud/modules/exam/models.py` 的 ExamResult 类中添加:

```python
# 在 detail_scores = Column(JSON, nullable=True) 之后添加
rank_in_class = Column(Integer, nullable=True)
rank_in_grade = Column(Integer, nullable=True)
```

- [ ] **Step 4: 生成 Alembic migration**

Run: `cd C:/Users/Administrator/edu-cloud && python -m alembic revision --autogenerate -m "add menu_configs and analysis tables"`

- [ ] **Step 5: 验证 migration**

Run: `cd C:/Users/Administrator/edu-cloud && python -m alembic upgrade head`
Expected: 4 张新表创建成功，ExamResult 加 2 个字段

- [ ] **Step 6: 显式 import 确保 Alembic autogenerate 可见（F006 处置）**

在 `src/edu_cloud/api/app.py` 的 import 区域添加:

```python
import edu_cloud.modules.menu.models  # noqa: F401 — Alembic autogenerate
import edu_cloud.modules.analytics.analysis_models  # noqa: F401 — Alembic autogenerate
```

这确保 Base.metadata 包含新表，Alembic autogenerate 能检测到它们。

- [ ] **Step 7: 跑已有测试确认无回归**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_alembic_migration.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/menu/ src/edu_cloud/modules/analytics/analysis_models.py src/edu_cloud/modules/exam/models.py alembic/versions/ tests/test_menu/
git commit -m "feat(db): add menu_configs, class_analysis, student_analysis, student_knp_mastery tables + exam_result rank fields"
```

**审查清单:**
- ✓ menu_configs 表有 code/name/icon/sort/parent_id/path/roles/requires_module/is_active 字段
- ✓ class_analysis 唯一约束 (exam_id, subject_id, class_id)
- ✓ student_analysis 唯一约束 (student_id, exam_id)
- ✓ student_knp_mastery 唯一约束 (student_id, exam_id, knp_id)
- ✓ ExamResult.rank_in_class 和 rank_in_grade 可空
- ✓ 所有新表有 school_id FK
- ✗ migration 不应删除任何现有表或列

**边界条件:**
- roles 列用 JSON 空数组 `[]` 作默认值，不是 PostgreSQL ARRAY `{}`
- parent_id 自引用 FK：顶级菜单 parent_id=NULL，子菜单指向已有 ID
- Alembic downgrade 能还原（不删除 ExamResult 原有列）

**测试契约:**
1. Migration upgrade+downgrade 可逆
   - 入口: `alembic upgrade head` → `alembic downgrade -1`
   - 反例: 错误实现 downgrade 时删除 ExamResult 表而非仅移除新增列
   - 边界: 空数据库 / 已有数据的数据库
   - 回归: N/A
   - 命令: `pytest tests/test_alembic_migration.py -v`
2. 新表在 Base.metadata 中可见
   - 入口: `alembic revision --autogenerate`（检测新表）
   - 反例: 未 import analysis_models → autogenerate 不生成新表的 migration（F006）
   - 边界: N/A
   - 回归: N/A
   - 命令: `python -c "from edu_cloud.models.base import Base; print([t for t in Base.metadata.tables if 'menu' in t or 'analysis' in t])"`

---

### Task 2: 后端 — MenuService + API 端点

**Files:**
- Create: `src/edu_cloud/modules/menu/service.py`
- Create: `src/edu_cloud/modules/menu/router.py`
- Modify: `src/edu_cloud/api/app.py` — 挂载 menu router
- Test: `tests/test_menu/test_menu_service.py`
- Test: `tests/test_menu/test_menu_api.py`

- [ ] **Step 1: 写 MenuService 失败测试**

```python
# tests/test_menu/test_menu_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.menu.models import MenuConfig
from edu_cloud.modules.menu.service import MenuService


@pytest.fixture
async def menu_service(db_session: AsyncSession):
    return MenuService(db_session)


@pytest.fixture
async def seed_menus(db_session: AsyncSession):
    """插入测试菜单数据：2 个顶级模块，各 2 个子菜单"""
    exam = MenuConfig(
        code="exam", name="阅卷", icon="document", sort=1,
        roles=["teacher", "academic_director", "principal"],
        is_active=True,
    )
    db_session.add(exam)
    await db_session.flush()

    db_session.add_all([
        MenuConfig(
            code="exam_list", name="考试列表", icon="list", sort=1,
            parent_id=exam.id, path="/exam/list",
            roles=["teacher", "academic_director", "principal"],
        ),
        MenuConfig(
            code="exam_quiz", name="测验列表", icon="edit-pen", sort=2,
            parent_id=exam.id, path="/exam/quiz",
            roles=["teacher", "academic_director"],
        ),
    ])

    report = MenuConfig(
        code="report", name="分析", icon="data-analysis", sort=2,
        roles=["teacher", "principal", "grade_leader"],
        is_active=True,
    )
    db_session.add(report)
    await db_session.flush()

    db_session.add_all([
        MenuConfig(
            code="report_exam", name="考试报告", icon="document", sort=1,
            parent_id=report.id, path="/report/exam",
            roles=["teacher", "principal", "grade_leader"],
        ),
        MenuConfig(
            code="report_contrast", name="班级对比", icon="histogram", sort=2,
            parent_id=report.id, path="/report/contrast",
            roles=["principal", "grade_leader"],
        ),
    ])
    await db_session.commit()
    return {"exam_id": exam.id, "report_id": report.id}


class TestMenuService:
    async def test_get_menus_for_teacher(self, menu_service, seed_menus):
        """teacher 角色应看到阅卷+分析模块"""
        menus = await menu_service.get_menus_for_user(
            role="teacher", enabled_modules=None
        )
        assert len(menus) == 2
        assert menus[0]["code"] == "exam"
        assert len(menus[0]["children"]) == 2  # list + quiz
        assert menus[1]["code"] == "report"
        assert len(menus[1]["children"]) == 1  # only exam report (contrast requires principal)

    async def test_get_menus_for_principal(self, menu_service, seed_menus):
        """principal 角色应看到全部子菜单"""
        menus = await menu_service.get_menus_for_user(
            role="principal", enabled_modules=None
        )
        report_menu = next(m for m in menus if m["code"] == "report")
        assert len(report_menu["children"]) == 2  # exam + contrast

    async def test_module_filter(self, menu_service, seed_menus):
        """requires_module 过滤：模块未启用的菜单不显示"""
        # 给 exam 模块加 requires_module
        from sqlalchemy import update
        await menu_service.session.execute(
            update(MenuConfig).where(MenuConfig.code == "exam").values(requires_module="exam")
        )
        await menu_service.session.commit()

        # enabled_modules 不含 exam → 不显示阅卷
        menus = await menu_service.get_menus_for_user(
            role="teacher", enabled_modules=["report"]
        )
        assert len(menus) == 1
        assert menus[0]["code"] == "report"

    async def test_inactive_menu_hidden(self, menu_service, seed_menus):
        """is_active=False 的菜单不显示"""
        from sqlalchemy import update
        await menu_service.session.execute(
            update(MenuConfig).where(MenuConfig.code == "exam").values(is_active=False)
        )
        await menu_service.session.commit()

        menus = await menu_service.get_menus_for_user(
            role="teacher", enabled_modules=None
        )
        assert all(m["code"] != "exam" for m in menus)

    async def test_empty_role_returns_empty(self, menu_service, seed_menus):
        """不匹配任何角色 → 空菜单"""
        menus = await menu_service.get_menus_for_user(
            role="parent", enabled_modules=None
        )
        assert len(menus) == 0

    async def test_sorted_by_sort_field(self, menu_service, seed_menus):
        """菜单按 sort 字段排序"""
        menus = await menu_service.get_menus_for_user(
            role="principal", enabled_modules=None
        )
        assert menus[0]["sort"] < menus[1]["sort"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_menu/test_menu_service.py -v`
Expected: ImportError — menu.service 不存在

- [ ] **Step 3: 实现 MenuService**

```python
# src/edu_cloud/modules/menu/service.py
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.menu.models import MenuConfig


class MenuService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_menus_for_user(
        self,
        role: str,
        enabled_modules: Optional[list[str]],
    ) -> list[dict]:
        """返回当前角色可见的菜单树。

        Args:
            role: 用户当前角色（如 'teacher', 'principal'）
            enabled_modules: 学校已启用的模块列表，None 表示不过滤
        """
        # 查所有 active 的顶级菜单（parent_id IS NULL）
        stmt = (
            select(MenuConfig)
            .where(MenuConfig.is_active.is_(True))
            .where(MenuConfig.parent_id.is_(None))
            .order_by(MenuConfig.sort)
        )
        result = await self.session.execute(stmt)
        top_menus = result.scalars().all()

        # 查所有 active 的子菜单
        child_stmt = (
            select(MenuConfig)
            .where(MenuConfig.is_active.is_(True))
            .where(MenuConfig.parent_id.is_not(None))
            .order_by(MenuConfig.sort)
        )
        child_result = await self.session.execute(child_stmt)
        all_children = child_result.scalars().all()

        # 按 parent_id 分组
        children_by_parent: dict[int, list[MenuConfig]] = {}
        for child in all_children:
            children_by_parent.setdefault(child.parent_id, []).append(child)

        menus = []
        for menu in top_menus:
            # 角色过滤
            if role not in (menu.roles or []):
                continue
            # 模块过滤
            if menu.requires_module and enabled_modules is not None:
                if menu.requires_module not in enabled_modules:
                    continue

            # 过滤子菜单
            children = []
            for child in children_by_parent.get(menu.id, []):
                if role not in (child.roles or []):
                    continue
                children.append({
                    "name": child.name,
                    "path": child.path,
                    "icon": child.icon,
                })

            if children:  # 只显示有子菜单的模块
                menus.append({
                    "code": menu.code,
                    "name": menu.name,
                    "icon": menu.icon,
                    "sort": menu.sort,
                    "children": children,
                })

        return menus
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_menu/test_menu_service.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: 写 API 端点失败测试**

```python
# tests/test_menu/test_menu_api.py
import pytest
from httpx import AsyncClient


@pytest.fixture
async def seeded_client(client: AsyncClient, db_session):
    """插入菜单种子后返回 client（F014 R4: 真实种入 report + principal-only contrast 子菜单）"""
    from edu_cloud.modules.menu.models import MenuConfig

    exam = MenuConfig(
        code="exam", name="阅卷", icon="document", sort=1,
        roles=["subject_teacher", "academic_director", "principal"],
    )
    db_session.add(exam)
    await db_session.flush()
    db_session.add(MenuConfig(
        code="exam_list", name="考试列表", icon="list", sort=1,
        parent_id=exam.id, path="/exam/list",
        roles=["subject_teacher", "academic_director", "principal"],
    ))

    # F014 R4: 补 report 模块及子菜单，contrast 只给 principal
    report = MenuConfig(
        code="report", name="分析", icon="data-analysis", sort=2,
        roles=["subject_teacher", "principal"],  # subject_teacher 可见模块
    )
    db_session.add(report)
    await db_session.flush()
    db_session.add(MenuConfig(
        code="report_exam", name="考试报告", icon="document", sort=1,
        parent_id=report.id, path="/report/exam",
        roles=["subject_teacher", "principal"],
    ))
    db_session.add(MenuConfig(
        code="report_contrast", name="班级对比", icon="histogram", sort=2,
        parent_id=report.id, path="/report/contrast",
        roles=["principal"],  # principal-only
    ))
    await db_session.commit()
    return client


class TestMenuAPI:
    async def test_get_menus_unauthenticated(self, client: AsyncClient):
        """未登录 → 401"""
        resp = await client.get("/api/v1/menus")
        assert resp.status_code == 401

    async def test_get_menus_subject_teacher(
        self, seeded_client: AsyncClient, subject_teacher_headers: dict
    ):
        """F003 (R2): 用 subject_teacher_headers fixture 做入口级角色过滤验证。

        种子中 exam 模块 roles 包含 subject_teacher，report 模块的 contrast 子菜单仅 principal。
        subject_teacher 应看到 exam，不应看到 report.contrast 子菜单。
        """
        resp = await seeded_client.get("/api/v1/menus", headers=subject_teacher_headers)
        assert resp.status_code == 200
        data = resp.json()
        menus = data["menus"]
        codes = [m["code"] for m in menus]
        assert "exam" in codes, f"subject_teacher 应看到 exam 模块，实际: {codes}"

        # F014 R4: 直接断言 report 存在（fixture 已种入），且 children 中不含 contrast
        assert "report" in codes, f"subject_teacher 应看到 report 模块（fixture 已种入），实际: {codes}"
        report = next(m for m in menus if m["code"] == "report")
        child_paths = [c["path"] for c in report["children"]]
        assert "/report/contrast" not in child_paths, \
            f"subject_teacher 不应看到 principal-only 的 contrast 子菜单，实际 children: {child_paths}"

    async def test_get_menus_platform_admin_structure(
        self, seeded_client: AsyncClient, admin_headers: dict
    ):
        """F003 (R2): platform_admin 不在种子 roles 中，应返回空菜单（fail-closed 语义）。

        反例: 错误实现对 platform_admin 做特殊放行 → 本测试捕获。
        """
        resp = await seeded_client.get("/api/v1/menus", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "menus" in data
        assert isinstance(data["menus"], list)
        # 种子 roles 不含 platform_admin → 期望空菜单
        assert data["menus"] == [], \
            f"platform_admin 不在种子 roles 中，应返回空菜单，实际: {data['menus']}"
```

- [ ] **Step 6: 实现 router**

```python
# src/edu_cloud/modules/menu/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import get_current_user, get_db
from edu_cloud.modules.menu.service import MenuService
from edu_cloud.services.school_settings_service import get_enabled_modules  # F004: 函数式 API

router = APIRouter(prefix="/menus", tags=["menus"])


@router.get("")
async def get_menus(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户角色可见的菜单树"""
    menu_service = MenuService(db)

    # F004: get_current_user 返回 {"user": User, "current_role": UserRole ORM, "permissions": set}
    current_role = user["current_role"]  # UserRole ORM 对象
    role = current_role.role  # str
    school_id = current_role.school_id  # str | None

    # 获取学校启用的模块（如果有 school_id）
    enabled_modules = None
    if school_id:
        enabled_modules = await get_enabled_modules(db, school_id=school_id)  # F004: 函数式调用

    menus = await menu_service.get_menus_for_user(
        role=role,
        enabled_modules=enabled_modules,
    )
    return {"menus": menus}
```

- [ ] **Step 7: 在 app.py 挂载 router**

在 `src/edu_cloud/api/app.py` 的 router 挂载区域添加:

```python
from edu_cloud.modules.menu.router import router as menu_router
from edu_cloud.modules.conduct.admin_router import router as conduct_admin_router  # F002 R1 追认（2026-04-13）
app.include_router(menu_router, prefix="/api/v1")
app.include_router(conduct_admin_router)  # 已含 /api/v1/conduct 前缀
```

> **F002 R1 说明（2026-04-13）**：commit 3488b52 在挂载 menu_router 时顺带挂载了 `conduct_admin_router`（28 个 `/api/v1/conduct/classes/*` 端点）。Code Review R1 将其识别为 behavior_change（偏离 INV-02）。用户批准保留并追认到 Batch 1 范围（见 `2026-04-12-haofenshu-phase1-review-report-batch1-r2.md` 行为变更审批记录）。

- [ ] **Step 8: 跑 API 测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_menu/ -v`
Expected: 8 tests PASS

- [ ] **Step 9: 跑全量测试确认无回归**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 1582+ tests PASS

- [ ] **Step 10: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/menu/service.py src/edu_cloud/modules/menu/router.py src/edu_cloud/api/app.py tests/test_menu/
git commit -m "feat(menu): MenuService + GET /api/v1/menus — dynamic menu system with role+module filtering"
```

**审查清单:**
- ✓ GET /api/v1/menus 返回 `{ menus: [...] }` 格式
- ✓ 未登录返回 401
- ✓ 角色过滤：teacher 看不到 principal-only 子菜单
- ✓ 模块过滤：学校未启用的模块不显示
- ✓ is_active=False 隐藏
- ✓ 按 sort 排序
- ✗ 不应修改现有 school_settings 相关代码

**边界条件:**
- 空角色 → 返回空菜单列表
- 没有子菜单的顶级模块 → 不显示
- enabled_modules=None → 不做模块过滤（平台管理员场景）

**测试契约:**
1. 角色过滤正确性
   - 入口: `GET /api/v1/menus`（teacher token）+ `MenuService.get_menus_for_user(role, modules)`
   - 反例: 错误实现不检查 roles JSON 数组 → teacher 看到 principal-only 菜单
   - 边界: 空角色（parent role） / 不匹配角色 / roles=[]
   - 回归: N/A
   - 命令: `pytest tests/test_menu/test_menu_service.py::TestMenuService::test_get_menus_for_teacher tests/test_menu/test_menu_api.py::TestMenuAPI::test_get_menus_subject_teacher -v`
2. 模块过滤正确性
   - 入口: `GET /api/v1/menus`（teacher token，学校未启用 exam 模块）
   - 反例: 错误实现忽略 requires_module → 未启用模块仍显示
   - 边界: requires_module=None（不受模块限制）/ enabled_modules=None（不做过滤）
   - 回归: N/A
   - 命令: `pytest tests/test_menu/test_menu_service.py::TestMenuService::test_module_filter -v`
3. API fail-closed 语义（F003 + F011 R3 处置）
   - 入口: `GET /api/v1/menus`（platform_admin token，但 seed roles 不含 platform_admin）
   - 反例: 错误实现对 platform_admin 做特殊放行 → 返回非空菜单而非空菜单
   - 边界: platform_admin（不在 seed roles → 空菜单）/ subject_teacher（应看到 exam）/ parent（无匹配 → 空）
   - 回归: N/A
   - 命令: `pytest tests/test_menu/test_menu_api.py::TestMenuAPI::test_get_menus_platform_admin_structure tests/test_menu/test_menu_api.py::TestMenuAPI::test_get_menus_subject_teacher -v`

---

### Task 3: 后端 — 菜单种子数据

**Files:**
- Create: `scripts/seed_menus.py`
- Test: 手动验证（seed 脚本）

- [ ] **Step 1: 创建种子脚本**

```python
# scripts/seed_menus.py
"""好分数 8 模块 × 45 子菜单种子数据。

Usage:
    cd C:/Users/Administrator/edu-cloud
    python scripts/seed_menus.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import select, text
from edu_cloud.database import async_engine, async_session_factory
from edu_cloud.modules.menu.models import MenuConfig


MODULES = [
    {
        "code": "exam", "name": "阅卷", "icon": "document", "sort": 1,
        "roles": ["subject_teacher", "homeroom_teacher", "lesson_prep_leader",
                  "grade_leader", "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "exam",
        "children": [
            {"code": "exam_list", "name": "考试列表", "path": "/exam/list", "icon": "list", "sort": 1},
            {"code": "exam_quiz", "name": "测验列表", "path": "/exam/quiz", "icon": "edit-pen", "sort": 2},
            {"code": "exam_grading", "name": "阅卷任务", "path": "/exam/grading", "icon": "finished", "sort": 3},
            {"code": "exam_answercard", "name": "答题卡工具", "path": "/exam/answercard", "icon": "postcard", "sort": 4},
            {"code": "exam_statistics", "name": "考试统计", "path": "/exam/statistics", "icon": "data-line", "sort": 5},
        ],
    },
    {
        "code": "report", "name": "分析", "icon": "data-analysis", "sort": 2,
        "roles": ["subject_teacher", "homeroom_teacher", "grade_leader",
                  "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "study_analytics",
        "children": [
            {"code": "report_exam", "name": "考试报告", "path": "/report/exam", "icon": "document", "sort": 1},
            {"code": "report_contrast", "name": "班级对比", "path": "/report/contrast", "icon": "histogram", "sort": 2},
            {"code": "report_custom", "name": "自定义分析", "path": "/report/custom", "icon": "set-up", "sort": 3},
            {"code": "report_table", "name": "自定义表格", "path": "/report/table", "icon": "grid", "sort": 4},
            {"code": "report_level_score", "name": "等级赋分", "path": "/report/level-score", "icon": "medal", "sort": 5},
            {"code": "report_config", "name": "指标配置", "path": "/report/config", "icon": "setting", "sort": 6},
        ],
    },
    {
        "code": "study", "name": "学情", "icon": "trend-charts", "sort": 3,
        "roles": ["subject_teacher", "homeroom_teacher", "grade_leader",
                  "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "study_analytics",
        "children": [
            {"code": "study_dashboard", "name": "数据看板", "path": "/study/dashboard", "icon": "odometer", "sort": 1},
            {"code": "study_class", "name": "班级学情", "path": "/study/class", "icon": "school", "sort": 2},
            {"code": "study_student", "name": "学生学情", "path": "/study/student", "icon": "user", "sort": 3},
            {"code": "study_layer", "name": "分层学情", "path": "/study/layer", "icon": "operation", "sort": 4},
        ],
    },
    {
        "code": "work", "name": "作业", "icon": "notebook", "sort": 4,
        "roles": ["subject_teacher", "homeroom_teacher", "lesson_prep_leader",
                  "grade_leader", "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "homework",
        "children": [
            {"code": "work_list", "name": "作业列表", "path": "/work/list", "icon": "list", "sort": 1},
            {"code": "work_publish", "name": "布置作业", "path": "/work/publish", "icon": "edit", "sort": 2},
            {"code": "work_scan", "name": "扫描作业", "path": "/work/scan", "icon": "camera", "sort": 3},
            {"code": "work_sync", "name": "同步作业", "path": "/work/sync", "icon": "refresh", "sort": 4},
        ],
    },
    {
        "code": "lesson", "name": "教学", "icon": "reading", "sort": 5,
        "roles": ["subject_teacher", "homeroom_teacher", "lesson_prep_leader",
                  "grade_leader", "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "teaching",
        "children": [
            {"code": "lesson_console", "name": "精准教学台", "path": "/lesson/console", "icon": "monitor", "sort": 1},
            {"code": "lesson_after_exam", "name": "考后分析", "path": "/lesson/after-exam", "icon": "document-checked", "sort": 2},
            {"code": "lesson_resources", "name": "备课资源", "path": "/lesson/resources", "icon": "folder-opened", "sort": 3},
            {"code": "lesson_space", "name": "我的空间", "path": "/lesson/space", "icon": "box", "sort": 4},
        ],
    },
    {
        "code": "research", "name": "教研", "icon": "collection", "sort": 6,
        "roles": ["subject_teacher", "lesson_prep_leader", "teaching_research_leader",
                  "academic_director", "principal"],
        "requires_module": "research",
        "children": [
            {"code": "research_questions", "name": "题库选题", "path": "/research/questions", "icon": "search", "sort": 1},
            {"code": "research_paper_builder", "name": "结构组卷", "path": "/research/paper-builder", "icon": "document-add", "sort": 2},
            {"code": "research_group_prep", "name": "集体备课", "path": "/research/group-prep", "icon": "chat-dot-round", "sort": 3},
            {"code": "research_knowledge", "name": "知识体系", "path": "/research/knowledge", "icon": "connection", "sort": 4},
            {"code": "research_plan", "name": "教学计划", "path": "/research/plan", "icon": "calendar", "sort": 5},
            {"code": "research_radar", "name": "考情雷达", "path": "/research/radar", "icon": "aim", "sort": 6},
            {"code": "research_school_resources", "name": "校本资源", "path": "/research/school-resources", "icon": "files", "sort": 7},
        ],
    },
    {
        "code": "baseinfo", "name": "基础信息", "icon": "user", "sort": 7,
        "roles": ["academic_director", "principal", "platform_admin"],
        "children": [
            {"code": "baseinfo_students", "name": "学生信息", "path": "/baseinfo/students", "icon": "user", "sort": 1},
            {"code": "baseinfo_teachers", "name": "教师信息", "path": "/baseinfo/teachers", "icon": "avatar", "sort": 2},
            {"code": "baseinfo_grades", "name": "年级管理", "path": "/baseinfo/grades", "icon": "school", "sort": 3},
            {"code": "baseinfo_records", "name": "人员动态", "path": "/baseinfo/records", "icon": "document", "sort": 4},
            {"code": "baseinfo_schedule", "name": "教师任课表", "path": "/baseinfo/schedule", "icon": "date", "sort": 5},
            {"code": "baseinfo_selected_exam", "name": "选考管理", "path": "/baseinfo/selected-exam", "icon": "checked", "sort": 6},
            {"code": "baseinfo_vip", "name": "版本权益", "path": "/baseinfo/vip", "icon": "trophy", "sort": 7},
        ],
    },
    {
        "code": "academic", "name": "教务", "icon": "office-building", "sort": 8,
        "roles": ["academic_director", "principal", "platform_admin"],
        "children": [
            {"code": "academic_semester", "name": "学期管理", "path": "/academic/semester", "icon": "calendar", "sort": 1},
            {"code": "academic_timetable", "name": "课表", "path": "/academic/timetable", "icon": "grid", "sort": 2},
            {"code": "academic_course_selection", "name": "选课", "path": "/academic/course-selection", "icon": "menu", "sort": 3},
            {"code": "academic_exam_schedule", "name": "考试安排", "path": "/academic/exam-schedule", "icon": "date", "sort": 4},
            {"code": "academic_score_manage", "name": "成绩管理", "path": "/academic/score-manage", "icon": "document-checked", "sort": 5},
        ],
    },
]


async def seed():
    async with async_session_factory() as session:
        # 检查是否已有数据
        result = await session.execute(select(MenuConfig).limit(1))
        if result.scalar():
            print("menu_configs 已有数据，跳过")
            return

        for module in MODULES:
            parent = MenuConfig(
                code=module["code"],
                name=module["name"],
                icon=module["icon"],
                sort=module["sort"],
                roles=module["roles"],
                requires_module=module.get("requires_module"),
                is_active=True,
            )
            session.add(parent)
            await session.flush()

            for child in module["children"]:
                session.add(MenuConfig(
                    code=child["code"],
                    name=child["name"],
                    icon=child["icon"],
                    sort=child["sort"],
                    parent_id=parent.id,
                    path=child["path"],
                    roles=module["roles"],  # 子菜单继承父级角色
                    is_active=True,
                ))

        await session.commit()
        total = sum(1 + len(m["children"]) for m in MODULES)
        print(f"已插入 {total} 条菜单记录（{len(MODULES)} 模块 + {total - len(MODULES)} 子菜单）")


if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 2: 运行种子脚本**

Run: `cd C:/Users/Administrator/edu-cloud && python scripts/seed_menus.py`
Expected: `已插入 53 条菜单记录（8 模块 + 45 子菜单）`

- [ ] **Step 3: 验证 API 返回**

Run: `cd C:/Users/Administrator/edu-cloud && python -c "import asyncio; from scripts.seed_menus import seed; asyncio.run(seed())"` 后用 curl 验证（需要后端运行）

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add scripts/seed_menus.py
git commit -m "feat(menu): seed script for 8 modules × 45 sub-menus"
```

**审查清单:**
- ✓ 8 个模块全部包含（exam/report/study/work/lesson/research/baseinfo/academic）
- ✓ 45 个子菜单路径与设计文档 §2 一致
- ✓ 角色分配合理（baseinfo/academic 限管理员，其余含 teacher）
- ✓ requires_module 对应现有 school_modules 的 module_code
- ✓ 幂等（已有数据时跳过）
- ✗ 不应删除已有种子数据

**边界条件:**
- 二次运行 → 跳过（幂等），不重复插入
- 空数据库（无 menu_configs 表）→ 应报明确错误（migration 未跑）
- 子菜单继承父级 roles（JSON 数组，非 ARRAY）

**测试契约:**
1. 幂等性验证
   - 入口: `python scripts/seed_menus.py`（连续执行两次）
   - 反例: 错误实现不检查已有数据 → 重复插入 → 106 条（应为 53 条）
   - 边界: 部分数据存在（手动插入了 1 条后再跑 seed）
   - 回归: N/A
   - 命令: `python scripts/seed_menus.py && python scripts/seed_menus.py`（第二次应输出"已有数据，跳过"）

---

### Task 4: 前端 — Nuxt 3 项目初始化

**Files:**
- Create: `frontend-nuxt/package.json`
- Create: `frontend-nuxt/nuxt.config.ts`
- Create: `frontend-nuxt/tsconfig.json`
- Create: `frontend-nuxt/assets/css/main.scss`
- Create: `frontend-nuxt/app.vue`

- [ ] **Step 1: 初始化 Nuxt 3 项目**

```bash
cd C:/Users/Administrator/edu-cloud
npx nuxi@latest init frontend-nuxt --packageManager npm --gitInit false
```

- [ ] **Step 2: 安装依赖**

```bash
cd C:/Users/Administrator/edu-cloud/frontend-nuxt
npm install @element-plus/nuxt @pinia/nuxt pinia @element-plus/icons-vue
npm install -D sass @nuxt/test-utils vitest @vue/test-utils happy-dom
```

- [ ] **Step 3: 配置 nuxt.config.ts**

```typescript
// frontend-nuxt/nuxt.config.ts
export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },

  modules: [
    '@element-plus/nuxt',
    '@pinia/nuxt',
  ],

  css: ['~/assets/css/main.scss'],

  runtimeConfig: {
    public: {
      apiBase: 'http://localhost:9000',
    },
  },

  vite: {
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:9000',
          changeOrigin: true,
        },
      },
    },
  },

  devServer: {
    port: 3000,
  },

  compatibilityDate: '2026-04-12',
})
```

- [ ] **Step 4: 创建 Element Plus 主题**

```scss
// frontend-nuxt/assets/css/main.scss
:root {
  // 主色系（Element Plus 默认蓝）
  --el-color-primary: #409eff;
  --el-color-primary-light-3: #79bbff;
  --el-color-primary-light-5: #a0cfff;
  --el-color-primary-light-7: #c6e2ff;
  --el-color-primary-light-9: #ecf5ff;
  --el-color-primary-dark-2: #337ecc;

  // 好分数品牌色
  --hfs-primary: #409eff;
  --hfs-accent: #ff9500;
  --hfs-success: #67c23a;
  --hfs-warning: #e6a23c;
  --hfs-danger: #f56c6c;
  --hfs-info: #909399;

  // 布局
  --hfs-header-height: 50px;
  --hfs-subnav-height: 38px;
  --hfs-bg: #eef1f6;
  --hfs-card-radius: 6px;
  --hfs-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans SC', sans-serif;
  background: var(--hfs-bg);
  color: #303133;
}

// 通用卡片
.page-card {
  background: #fff;
  border-radius: var(--hfs-card-radius);
  box-shadow: var(--hfs-card-shadow);
  padding: 20px;
  margin-bottom: 16px;
}

// 筛选栏
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

// 工具栏
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  h3 {
    font-size: 16px;
    font-weight: 600;
  }
}

// 统计卡片
.stat-cards {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;

  .stat-card {
    flex: 1;
    padding: 16px;
    border-radius: var(--hfs-card-radius);
    text-align: center;

    .value {
      font-size: 24px;
      font-weight: bold;
    }

    .label {
      font-size: 12px;
      color: var(--hfs-info);
      margin-top: 4px;
    }
  }
}

// Stub 页面样式
.page-stub {
  padding: 20px;

  h2 {
    font-size: 18px;
    margin-bottom: 8px;
  }

  .breadcrumb {
    color: var(--hfs-info);
    font-size: 13px;
    margin-bottom: 20px;
  }

  .placeholder {
    background: #f5f7fa;
    border: 2px dashed #dcdfe6;
    border-radius: var(--hfs-card-radius);
    padding: 60px 20px;
    text-align: center;
    color: var(--hfs-info);
    font-size: 14px;
  }
}
```

- [ ] **Step 5: 替换 app.vue**

```vue
<!-- frontend-nuxt/app.vue -->
<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
```

- [ ] **Step 6: 验证启动**

Run: `cd C:/Users/Administrator/edu-cloud/frontend-nuxt && npx nuxt dev --port 3000`
Expected: 无报错启动，浏览器打开 http://localhost:3000 看到空白页

- [ ] **Step 7: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend-nuxt/
git commit -m "feat(frontend): init Nuxt 3 project with Element Plus + Pinia + theme"
```

**审查清单:**
- ✓ nuxt.config.ts SSR=false
- ✓ Element Plus + Pinia 模块注册
- ✓ API 代理指向 localhost:9000
- ✓ CSS 变量包含好分数品牌色和布局尺寸
- ✓ `npx nuxt dev` 可启动
- ✗ 不应修改现有 frontend/ 目录

**边界条件:**
- SSR=false 确保纯 SPA 模式，不需要 Node 服务端
- API 代理仅在 dev 模式生效，生产部署由 Nginx 代理
- Element Plus auto-import 无需手动 import 组件

**变更类型:** 非行为变更（Nuxt 脚手架 + 主题配置，无业务逻辑）。
**测试契约（F002 R2）:**
1. Nuxt dev server 启动验证
   - 入口: `npx nuxt dev --port 3000`
   - 反例: 错误 nuxt.config.ts（SSR=true 或模块缺失）→ 启动时报错
   - 边界: 端口冲突 / 依赖未安装 / scss 语法错误
   - 回归: N/A
   - 命令: `cd frontend-nuxt && timeout 30 npx nuxt dev --port 3000 2>&1 | grep -qE "ready|listening"`

---

### Task 5: 前端 — auth store + middleware

**Files:**
- Create: `frontend-nuxt/stores/auth.ts`
- Create: `frontend-nuxt/stores/context.ts`
- Create: `frontend-nuxt/middleware/auth.global.ts`

- [ ] **Step 1: 创建 auth store**

```typescript
// frontend-nuxt/stores/auth.ts
interface UserRole {
  id: string                  // F015 R4: 后端返回，switchRole 需要
  role: string
  school_id?: string
  is_primary?: boolean        // F015 R4: 主角色标志，applyLoginResponse 据此选中 active_role
  context?: {
    type: string
    id: string
    name: string
  }
}

interface UserInfo {
  id: string
  username: string
  display_name: string
  roles: UserRole[]
  active_role: UserRole
}

// F009 (R2): 后端响应结构（与前端 UserInfo 不一致，需归一化）
interface LoginResponse {
  access_token: string
  token_type: string
  user: { id: string; username: string; display_name: string; role: string }
  roles: UserRole[]
}
interface SwitchRoleResponse {
  access_token: string
  token_type: string
  active_role: UserRole
}

interface MenuItem {
  code: string
  name: string
  icon: string
  sort: number
  children: { name: string; path: string; icon: string }[]
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as UserInfo | null,
    menus: [] as MenuItem[],
  }),

  getters: {
    isLoggedIn: (state) => !!state.user,
    userName: (state) => state.user?.display_name || '',
    activeRole: (state) => state.user?.active_role || null,
    roleName: (state) => {
      const role = state.user?.active_role?.role
      const ROLE_NAMES: Record<string, string> = {
        platform_admin: '平台管理员',
        district_admin: '区域管理员',
        principal: '校长',
        academic_director: '教务主任',
        teaching_research_leader: '教研组长',
        grade_leader: '年级组长',
        lesson_prep_leader: '备课组长',
        homeroom_teacher: '班主任',
        subject_teacher: '科任教师',
        parent: '家长',
      }
      return role ? ROLE_NAMES[role] || role : ''
    },
    schoolName: (state) => state.user?.active_role?.context?.name || '',
  },

  actions: {
    setUser(user: UserInfo) {
      this.user = user
      // F009 (R2): 持久化到 localStorage 支撑刷新恢复
      if (import.meta.client) {
        localStorage.setItem('edu_user', JSON.stringify(user))
      }
    },
    setMenus(menus: MenuItem[]) {
      this.menus = menus
    },

    // F009 (R2): 归一化 login 响应 → 统一 UserInfo 结构
    applyLoginResponse(res: LoginResponse) {
      const activeRole = res.roles.find((r) => r.is_primary) || res.roles[0]
      const user: UserInfo = {
        id: res.user.id,
        username: res.user.username,
        display_name: res.user.display_name,
        roles: res.roles,
        active_role: activeRole,
      }
      this.setUser(user)
    },

    // F009 (R2): 归一化 switch-role 响应（只更新 active_role，保留 user/roles）
    applySwitchRoleResponse(res: SwitchRoleResponse) {
      if (!this.user) return
      const updated: UserInfo = { ...this.user, active_role: res.active_role }
      this.setUser(updated)
    },

    // F009 (R2): 刷新后从 localStorage 恢复 user（token 已在 cookie 中）
    restoreFromStorage() {
      if (!import.meta.client) return
      const raw = localStorage.getItem('edu_user')
      if (raw) {
        try { this.user = JSON.parse(raw) as UserInfo } catch { /* noop */ }
      }
    },

    async switchRole(roleId: string) {  // F007: 后端用 role_id
      const api = useApi()
      const res = await api.switchRole(roleId) as SwitchRoleResponse
      if (res.access_token) {
        const token = useCookie('edu_token')
        token.value = res.access_token
      }
      this.applySwitchRoleResponse(res)
      // 切角色后重新加载菜单
      const { loadMenus } = useMenus()
      await loadMenus()
    },
    logout() {
      this.user = null
      this.menus = []
      const token = useCookie('edu_token')
      token.value = null
      if (import.meta.client) {
        localStorage.removeItem('edu_user')
      }
      navigateTo('/login')
    },
  },
})
```

- [ ] **Step 2: 创建 context store**

```typescript
// frontend-nuxt/stores/context.ts
export const useContextStore = defineStore('context', {
  state: () => ({
    schoolYear: '',
    semester: '',
  }),

  actions: {
    setSchoolYear(year: string) {
      this.schoolYear = year
    },
    setSemester(semester: string) {
      this.semester = semester
    },
  },
})
```

- [ ] **Step 3: 创建全局 auth middleware**

```typescript
// frontend-nuxt/middleware/auth.global.ts
export default defineNuxtRouteMiddleware((to) => {
  const token = useCookie('edu_token')
  const publicPaths = ['/login', '/']

  if (!token.value && !publicPaths.includes(to.path)) {
    return navigateTo('/login')
  }
})
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend-nuxt/stores/ frontend-nuxt/middleware/
git commit -m "feat(frontend): auth store + context store + global auth middleware"
```

**审查清单:**
- ✓ auth store 有 user/menus/currentRoleIndex
- ✓ switchRole 调用 API 并重新加载菜单
- ✓ logout 清除 cookie + 跳转登录页
- ✓ middleware 检查 cookie，未登录跳转 /login
- ✓ /login 和 / 是公开路径
- ✗ 不应引用 Naive UI 组件

**边界条件:**
- token 过期/无效 → middleware 不崩溃，正常跳转 /login
- switchRole 用 role_id（UUID string），不是 index（F007）
- logout 清除 cookie 后，刷新任何页面都应跳转 /login

**测试契约（F012 R3 + F012 R4 补最小 Vitest + 骨架）:**
1. applyLoginResponse 归一化正确
   - 入口: `const store = useAuthStore(); store.applyLoginResponse(mockLoginRes)`
   - 反例: 错误实现不取 is_primary → active_role 错误
   - 边界: 单角色 / 多角色含 is_primary / 多角色全非 is_primary（取 roles[0]） / roles=[]
   - 回归: F009 R2 新增行为
   - 命令: `cd frontend-nuxt && npx vitest run tests/stores/auth.test.ts -t applyLoginResponse`
   - Vitest 骨架:
     ```ts
     it('applyLoginResponse 选中 is_primary 角色', () => {
       const store = useAuthStore()
       store.applyLoginResponse({
         access_token: 't', token_type: 'bearer',
         user: { id: 'u1', username: 'a', display_name: 'A', role: 'subject_teacher' },
         roles: [
           { id: 'r1', role: 'subject_teacher', is_primary: false },
           { id: 'r2', role: 'homeroom_teacher', is_primary: true },
         ],
       } as any)
       expect(store.user?.active_role.id).toBe('r2')
       expect(store.user?.roles.length).toBe(2)
     })
     ```
2. applySwitchRoleResponse 只更新 active_role
   - 入口: `store.setUser(mockUser); store.applySwitchRoleResponse({access_token:'t', active_role: newRole})`
   - 反例: 错误实现清空 roles 或 user → UserDropdown 显示异常
   - 边界: user=null（应忽略 / 不抛异常）/ access_token 缺失 / active_role 缺失
   - 回归: F009 R2
   - 命令: `cd frontend-nuxt && npx vitest run tests/stores/auth.test.ts -t applySwitchRoleResponse`
   - Vitest 骨架:
     ```ts
     it('applySwitchRoleResponse 保留 user/roles，只改 active_role', () => {
       const store = useAuthStore()
       store.setUser({ id: 'u1', username: 'a', display_name: 'A',
         roles: [{ id: 'r1', role: 'subject_teacher' }, { id: 'r2', role: 'homeroom_teacher' }],
         active_role: { id: 'r1', role: 'subject_teacher' } } as any)
       store.applySwitchRoleResponse({
         access_token: 't2', token_type: 'bearer',
         active_role: { id: 'r2', role: 'homeroom_teacher' },
       } as any)
       expect(store.user?.active_role.id).toBe('r2')
       expect(store.user?.roles.length).toBe(2)  // roles 未被清空
     })
     ```
3. restoreFromStorage 刷新恢复
   - 入口: `localStorage.setItem('edu_user', JSON.stringify(mockUser)); store.restoreFromStorage()`
   - 反例: 错误实现不 try/catch → JSON 损坏导致启动崩溃
   - 边界: localStorage 空 / JSON 损坏 / user 字段缺失
   - 回归: F009 R2
   - 命令: `cd frontend-nuxt && npx vitest run tests/stores/auth.test.ts -t restoreFromStorage`
   - Vitest 骨架:
     ```ts
     it('restoreFromStorage JSON 损坏时不崩溃', () => {
       const store = useAuthStore()
       localStorage.setItem('edu_user', '{broken json')
       expect(() => store.restoreFromStorage()).not.toThrow()
       expect(store.user).toBeNull()
     })
     ```

**Vitest 配置要求（前置）:** `frontend-nuxt/vitest.config.ts` 需启用 happy-dom 环境（Task 4 已在 devDependencies 装好 `@vue/test-utils vitest happy-dom`）。

---

### Task 6: 前端 — useApi composable

**Files:**
- Create: `frontend-nuxt/composables/useApi.ts`

- [ ] **Step 1: 创建 useApi**

```typescript
// frontend-nuxt/composables/useApi.ts
interface RequestOptions {
  method?: string
  body?: any
  query?: Record<string, any>
  responseType?: string
}

export function useApi() {
  const token = useCookie('edu_token')
  const config = useRuntimeConfig()

  async function request<T = any>(
    path: string,
    opts: RequestOptions = {},
  ): Promise<T> {
    const { method = 'GET', body, query, ...rest } = opts
    return $fetch<T>(path, {
      baseURL: config.public.apiBase + '/api/v1',
      method: method as any,
      headers: token.value
        ? { Authorization: `Bearer ${token.value}` }
        : {},
      body,
      query,
      ...rest,
    })
  }

  return {
    // === Auth (已有后端端点) ===
    login: (phone: string, password: string) =>
      request('/auth/login', { method: 'POST', body: { username: phone, password } }),
    switchRole: (roleId: string) =>  // F007: 后端用 role_id 不是 role_index
      request('/auth/switch-role', { method: 'POST', body: { role_id: roleId } }),

    // === Menu (本 Phase 新增) ===
    getMenus: () => request<{ menus: any[] }>('/menus'),

    // === Exam (已有后端端点) ===
    getExams: (params?: Record<string, any>) => request('/exams', { query: params }),
    getExam: (id: string) => request(`/exams/${id}`),
    createExam: (data: any) => request('/exams', { method: 'POST', body: data }),

    // === Analytics (已有后端端点) ===
    // F007 (R2): 路径精确对齐 analytics/router.py
    getExamSummary: (examId: string, params?: Record<string, any>) =>
      request(`/analytics/exam/${examId}/summary`, { query: params }),
    getSubjectSummary: (subjectId: string, params?: Record<string, any>) =>
      request(`/analytics/subject/${subjectId}/summary`, { query: params }),
    getExamDistribution: (examId: string, params?: Record<string, any>) =>
      request(`/analytics/exam/${examId}/distribution`, { query: params }),
    getSubjectDistribution: (subjectId: string, params?: Record<string, any>) =>
      request(`/analytics/subject/${subjectId}/distribution`, { query: params }),
    getSubjectQuestions: (subjectId: string, params?: Record<string, any>) =>
      request(`/analytics/subject/${subjectId}/questions`, { query: params }),
    getExamGradeAggregates: (examId: string, params?: Record<string, any>) =>
      request(`/analytics/exam/${examId}/grade-aggregates`, { query: params }),
    getScoreSegments: () => request('/analytics/segments/config'),
    getAnalyticsReportTrendGrade: (params?: Record<string, any>) =>
      request('/analytics/report/trend/grade', { query: params }),
    getAnalyticsReportTrendClass: (params?: Record<string, any>) =>
      request('/analytics/report/trend/class', { query: params }),
    getAnalyticsReportTrendStudent: (params?: Record<string, any>) =>
      request('/analytics/report/trend/student', { query: params }),

    // F007 (R2): getPowerOptions — Phase 1 提供真实 stub（本地聚合），Phase 2 再接入后端 /analytics/power-options
    // 返回 { powerOptions: [], examInfoMap: {} } 使 Task 10 usePowerOptions 可正常初始化（tree=[] → 所有 select 隐藏）
    getPowerOptions: (_params?: Record<string, any>) =>
      Promise.resolve({ powerOptions: [], examInfoMap: {} }),

    // === Homework (已有后端端点) ===
    getHomeworkList: (params?: Record<string, any>) =>
      request('/homework/tasks', { query: params }),
    createHomework: (data: any) =>
      request('/homework/tasks', { method: 'POST', body: data }),
    getSubmissions: (taskId: string) =>
      request(`/homework/tasks/${taskId}/submissions`),
    gradeSubmission: (taskId: string, subId: string, data: any) =>
      request(`/homework/tasks/${taskId}/submissions/${subId}/grade`, { method: 'POST', body: data }),

    // === Knowledge (已有后端端点) ===
    getKnowledgeTree: (params?: Record<string, any>) =>
      request('/knowledge-tree/graph', { query: params }),  // F007: 对齐实际路径
    searchKnowledge: (params?: Record<string, any>) =>
      request('/knowledge-tree/search', { query: params }),
    searchQuestions: (params?: Record<string, any>) =>
      request('/bank/questions', { query: params }),

    // === BaseInfo (已有后端端点) ===
    getStudents: (params?: Record<string, any>) => request('/students', { query: params }),
    getClasses: (params?: Record<string, any>) => request('/classes', { query: params }),

    // === Profile (已有后端端点) ===
    getStudentTrend: (studentId: string, params?: Record<string, any>) =>
      request(`/profile/students/${studentId}/trend`, { query: params }),
    getStudentKnowledge: (studentId: string, params?: Record<string, any>) =>
      request(`/profile/students/${studentId}/knowledge`, { query: params }),

    // === AI (已有后端端点) ===
    chatStream: (message: string, sessionId?: string) =>
      $fetch('/api/v1/ai/chat', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: { message, session_id: sessionId },
        responseType: 'stream' as any,
        headers: token.value ? { Authorization: `Bearer ${token.value}` } : {},
      }),

    // === Dashboard (已有后端端点) ===
    getDashboardSummary: () => request('/dashboard/summary'),

    // === Phase 2/3 待实现（stub，调用时返回 not-implemented 提示）===
    // getSchoolDashboard — 需后端新增 /study/dashboard（Phase 3 学情模块）
    // getClassStudy — 需后端新增 /study/class（Phase 3）
    // getStudentStudy — 需后端新增 /study/student（Phase 3）
    // generatePaper — 需后端新增 /bank/paper/generate（Phase 3 组卷）
    // getGrades — 需后端新增 /grades（Phase 2 基础信息）

    // === Raw ===
    raw: request,
    token,
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend-nuxt/composables/useApi.ts
git commit -m "feat(frontend): useApi composable — unified API client with 30+ methods"
```

**审查清单:**
- ✓ 单入口 useApi()，所有 API 方法在一个 composable 内
- ✓ token 从 cookie 读取，自动注入 Authorization header
- ✓ baseURL 从 runtimeConfig 读取
- ✓ 方法签名与 edu-cloud 后端 RESTful 端点对应
- ✓ chatStream 用 responseType: stream
- ✓ 暴露 raw 和 token 供特殊场景使用
- ✗ 不应硬编码后端 URL
- ✓ F007: 所有方法对应已有后端端点，不存在的端点注释为 Phase 2/3 待实现
- ✓ F007: switchRole 用 role_id（string），不是 role_index

**边界条件:**
- token 为 null → 请求不带 Authorization header（公共端点可用）
- API 返回 401 → 上层调用方负责跳转 login（useApi 不拦截）
- baseURL 从 runtimeConfig 读取，dev/prod 环境不同

**变更类型:** 部分行为变更（getPowerOptions stub 返回固定结构，其余方法仅是 URL 绑定）。
**测试契约（F002 R2 + F012 R3 补 Vitest）:**
1. getPowerOptions stub 返回结构正确（F007 R2 依赖）
   - 入口: `const api = useApi(); const res = await api.getPowerOptions()`
   - 反例: 错误实现返回 undefined → Task 10 `res.powerOptions` 报 TypeError
   - 边界: 未登录调用（仍应返回空结构不抛异常）/ 传 params / 不传 params
   - 回归: F007 R2
   - 命令: `cd frontend-nuxt && npx vitest run tests/composables/useApi.test.ts -t getPowerOptions`
   - Vitest 骨架:
     ```ts
     it('getPowerOptions 返回 {powerOptions: [], examInfoMap: {}}', async () => {
       const api = useApi()
       const res = await api.getPowerOptions()
       expect(res).toEqual({ powerOptions: [], examInfoMap: {} })
     })
     ```

---

### Task 7: 前端 — useMenus composable + 导航组件

**Files:**
- Create: `frontend-nuxt/composables/useMenus.ts`
- Create: `frontend-nuxt/components/shell/TopNav.vue`
- Create: `frontend-nuxt/components/shell/SubNav.vue`
- Create: `frontend-nuxt/components/shell/UserDropdown.vue`

- [ ] **Step 1: 创建 useMenus**

```typescript
// frontend-nuxt/composables/useMenus.ts
export function useMenus() {
  const authStore = useAuthStore()
  const api = useApi()

  async function loadMenus() {
    try {
      const res = await api.getMenus()
      authStore.setMenus(res.menus)
    } catch (e) {
      console.error('Failed to load menus:', e)
      authStore.setMenus([])
    }
  }

  const activeModule = computed(() => {
    const route = useRoute()
    return (
      authStore.menus.find((m) =>
        m.children?.some((c: any) => route.path.startsWith(c.path)),
      ) || null
    )
  })

  const currentSubMenus = computed(() => activeModule.value?.children || [])

  function navigateToModule(menu: any) {
    const router = useRouter()
    if (menu.children?.length) {
      router.push(menu.children[0].path)
    }
  }

  return { loadMenus, activeModule, currentSubMenus, navigateToModule }
}
```

- [ ] **Step 2: 创建 TopNav**

```vue
<!-- frontend-nuxt/components/shell/TopNav.vue -->
<template>
  <header class="top-nav">
    <div class="logo">
      <span class="logo-icon">🎓</span>
      <span class="logo-text">edu-cloud</span>
    </div>
    <nav class="nav-items">
      <div
        v-for="menu in authStore.menus"
        :key="menu.code"
        class="nav-item"
        :class="{ active: activeModule?.code === menu.code }"
        @click="navigateToModule(menu)"
      >
        {{ menu.name }}
      </div>
    </nav>
    <div class="nav-right">
      <div class="ai-trigger" title="AI 助手" @click="$emit('toggle-ai')">
        🤖
      </div>
      <UserDropdown />
    </div>
  </header>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const { activeModule, navigateToModule } = useMenus()

defineEmits(['toggle-ai'])
</script>

<style scoped lang="scss">
.top-nav {
  height: var(--hfs-header-height);
  background: linear-gradient(135deg, var(--hfs-primary), #53a8ff);
  display: flex;
  align-items: center;
  padding: 0 20px;
  color: #fff;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: 30px;
  font-weight: bold;
  font-size: 16px;
  flex-shrink: 0;
}

.nav-items {
  display: flex;
  gap: 4px;
  flex: 1;
  justify-content: center;
}

.nav-item {
  padding: 6px 16px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: rgba(255, 255, 255, 0.15);
  }

  &.active {
    background: rgba(255, 255, 255, 0.3);
    font-weight: 600;
  }
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.ai-trigger {
  cursor: pointer;
  font-size: 18px;
}
</style>
```

- [ ] **Step 3: 创建 SubNav**

```vue
<!-- frontend-nuxt/components/shell/SubNav.vue -->
<template>
  <nav v-if="subMenus.length > 0" class="sub-nav">
    <NuxtLink
      v-for="item in subMenus"
      :key="item.path"
      :to="item.path"
      class="sub-nav-item"
      :class="{ active: route.path === item.path }"
    >
      <el-icon v-if="item.icon" :size="14" style="margin-right: 4px">
        <component :is="iconMap[item.icon] || 'Document'" />
      </el-icon>
      {{ item.name }}
    </NuxtLink>
  </nav>
</template>

<script setup lang="ts">
import {
  Document, List, EditPen, Finished, Postcard, DataLine,
  DataAnalysis, Histogram, SetUp, Grid, Medal, Setting,
  TrendCharts, Odometer, School, User, Operation,
  Notebook, Edit, Camera, Refresh,
  Reading, Monitor, DocumentChecked, FolderOpened, Box,
  Collection, Search, DocumentAdd, ChatDotRound, Connection,
  Calendar, Aim, Files,
  Avatar, Date, Checked, Trophy,
  OfficeBuilding, Menu,
} from '@element-plus/icons-vue'

const iconMap: Record<string, any> = {
  document: Document, list: List, 'edit-pen': EditPen, finished: Finished,
  postcard: Postcard, 'data-line': DataLine, 'data-analysis': DataAnalysis,
  histogram: Histogram, 'set-up': SetUp, grid: Grid, medal: Medal,
  setting: Setting, 'trend-charts': TrendCharts, odometer: Odometer,
  school: School, user: User, operation: Operation, notebook: Notebook,
  edit: Edit, camera: Camera, refresh: Refresh, reading: Reading,
  monitor: Monitor, 'document-checked': DocumentChecked,
  'folder-opened': FolderOpened, box: Box, collection: Collection,
  search: Search, 'document-add': DocumentAdd,
  'chat-dot-round': ChatDotRound, connection: Connection,
  calendar: Calendar, aim: Aim, files: Files, avatar: Avatar,
  date: Date, checked: Checked, trophy: Trophy,
  'office-building': OfficeBuilding, menu: Menu,
}

const route = useRoute()
const { currentSubMenus: subMenus } = useMenus()
</script>

<style scoped lang="scss">
.sub-nav {
  height: var(--hfs-subnav-height);
  background: var(--el-color-primary-light-9);
  border-bottom: 1px solid var(--el-color-primary-light-7);
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 24px;
  position: fixed;
  top: var(--hfs-header-height);
  left: 0;
  right: 0;
  z-index: 99;
}

.sub-nav-item {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: #606266;
  text-decoration: none;
  padding: 8px 0;
  cursor: pointer;
  transition: color 0.2s;

  &:hover {
    color: var(--hfs-primary);
  }

  &.active {
    color: var(--hfs-primary);
    font-weight: 500;
    border-bottom: 2px solid var(--hfs-primary);
  }
}
</style>
```

- [ ] **Step 4: 创建 UserDropdown**

```vue
<!-- frontend-nuxt/components/shell/UserDropdown.vue -->
<template>
  <el-dropdown trigger="click" @command="handleCommand">
    <span class="user-trigger">
      {{ authStore.userName || '用户' }}
      <el-icon><ArrowDown /></el-icon>
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item disabled>
          {{ authStore.roleName }} · {{ authStore.schoolName }}
        </el-dropdown-item>
        <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { ArrowDown } from '@element-plus/icons-vue'

const authStore = useAuthStore()

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    authStore.logout()
  }
}
</script>

<style scoped>
.user-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-size: 13px;
  color: #fff;
}
</style>
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend-nuxt/composables/useMenus.ts frontend-nuxt/components/shell/
git commit -m "feat(frontend): useMenus composable + TopNav + SubNav + UserDropdown"
```

**审查清单:**
- ✓ TopNav 动态渲染 authStore.menus
- ✓ SubNav 只在有子菜单时显示
- ✓ 当前激活模块高亮
- ✓ 当前子菜单页面高亮（route.path 匹配）
- ✓ 图标映射覆盖所有种子数据中的 icon 名
- ✓ UserDropdown 显示角色名+学校名

**边界条件:**
- menus 为空（API 失败或新用户无角色）→ TopNav 不渲染导航项，不崩溃
- 当前路径不匹配任何模块 → activeModule=null，SubNav 不显示
- 模块只有一个子菜单 → SubNav 仍显示（单项也显示）

**测试契约:**
1. 菜单 API 失败时的降级
   - 入口: loadMenus()（后端不可达时）
   - 反例: 错误实现不 catch → 页面崩溃
   - 边界: 网络超时 / 500 错误 / 空响应
   - 回归: N/A
   - 命令: 手动验证（断开后端后刷新页面）

---

### Task 8: 前端 — 三种 Layout

**Files:**
- Create: `frontend-nuxt/layouts/default.vue`
- Create: `frontend-nuxt/layouts/fullscreen.vue`
- Create: `frontend-nuxt/layouts/auth.vue`

- [ ] **Step 1: default layout**

```vue
<!-- frontend-nuxt/layouts/default.vue -->
<template>
  <div class="app-layout">
    <TopNav @toggle-ai="showAi = !showAi" />
    <SubNav />
    <main
      class="main-content"
      :style="{ marginTop: hasSubNav ? '88px' : '50px' }"
    >
      <slot />
    </main>
    <!-- AI 浮窗占位（Phase 2 迁移时替换） -->
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const { loadMenus, currentSubMenus } = useMenus()
const api = useApi()
const showAi = ref(false)

const hasSubNav = computed(() => currentSubMenus.value.length > 0)

// 登录后加载用户信息和菜单
const token = useCookie('edu_token')

// F009 (R2): 刷新后先从 localStorage 恢复 user，再加载菜单
authStore.restoreFromStorage()

watch(
  token,
  async (val) => {
    if (val && !authStore.user) {
      // token 存在但 user 丢失（localStorage 清空或首次进入）→ 先恢复再加载菜单
      authStore.restoreFromStorage()
      try {
        await loadMenus()
      } catch {
        authStore.logout()
      }
    } else if (val && authStore.user) {
      // 已恢复，加载菜单
      try {
        await loadMenus()
      } catch {
        authStore.logout()
      }
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.main-content {
  padding: 16px 20px;
  min-height: calc(100vh - var(--hfs-header-height));
}
</style>
```

- [ ] **Step 2: fullscreen layout**

```vue
<!-- frontend-nuxt/layouts/fullscreen.vue -->
<template>
  <div class="fullscreen-layout">
    <slot />
  </div>
</template>

<style scoped>
.fullscreen-layout {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}
</style>
```

- [ ] **Step 3: auth layout**

```vue
<!-- frontend-nuxt/layouts/auth.vue -->
<template>
  <div class="auth-layout">
    <slot />
  </div>
</template>

<style scoped>
.auth-layout {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
</style>
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend-nuxt/layouts/
git commit -m "feat(frontend): three layouts — default (nav+subnav), fullscreen, auth"
```

**审查清单:**
- ✓ default layout 包含 TopNav + SubNav + main slot
- ✓ main-content marginTop 根据是否有 SubNav 动态调整
- ✓ fullscreen layout 无任何 chrome
- ✓ auth layout 居中渐变背景
- ✓ token 变化时自动加载菜单

**边界条件:**
- default layout token watch: token 从 null → 有值 → 自动加载菜单
- default layout token watch: token 有值但 loadMenus 失败 → logout（防 token 过期卡死）
- fullscreen layout: 100vw/100vh，overflow hidden

**变更类型:** 部分行为变更（default layout 含 token watch + restoreFromStorage，F009 R2 依赖）。
**测试契约（F002 R2）:**
1. 刷新恢复验证（F009 R2 依赖）
   - 入口: 登录后手动刷新 `/home` 页面
   - 反例: 错误实现不调用 restoreFromStorage → UserDropdown 角色名/学校名为空
   - 边界: localStorage 空 / localStorage JSON 损坏 / token 过期
   - 回归: N/A
   - 命令: Batch 2 独立验证段（登录后刷新，验证 UserDropdown 显示完整）

---

### Task 9: 前端 — login + home 页面

**Files:**
- Create: `frontend-nuxt/pages/index.vue`
- Create: `frontend-nuxt/pages/login.vue`
- Create: `frontend-nuxt/pages/home.vue`

- [ ] **Step 1: index.vue（重定向）**

```vue
<!-- frontend-nuxt/pages/index.vue -->
<template>
  <div />
</template>
<script setup lang="ts">
const token = useCookie('edu_token')
if (token.value) {
  navigateTo('/home')
} else {
  navigateTo('/login')
}
</script>
```

- [ ] **Step 2: login.vue**

```vue
<!-- frontend-nuxt/pages/login.vue -->
<template>
  <div class="login-card">
    <h2>edu-cloud</h2>
    <p class="subtitle">教育云平台</p>
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
      <el-form-item prop="username">
        <el-input v-model="form.username" placeholder="手机号 / 用户名" size="large" />
      </el-form-item>
      <el-form-item prop="password">
        <el-input
          v-model="form.password"
          type="password"
          placeholder="密码"
          size="large"
          show-password
          @keyup.enter="handleLogin"
        />
      </el-form-item>
      <el-button
        type="primary"
        size="large"
        :loading="loading"
        style="width: 100%"
        @click="handleLogin"
      >
        登录
      </el-button>
    </el-form>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const api = useApi()
const authStore = useAuthStore()
const { loadMenus } = useMenus()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    const res = await api.login(form.username, form.password) as LoginResponse
    api.token.value = res.access_token
    authStore.applyLoginResponse(res)  // F009 (R2): 归一化
    await loadMenus()
    navigateTo('/home')
  } catch (e: any) {
    ElMessage.error(e?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  width: 400px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

h2 {
  text-align: center;
  font-size: 24px;
  margin-bottom: 4px;
}

.subtitle {
  text-align: center;
  color: #909399;
  margin-bottom: 30px;
}
</style>
```

- [ ] **Step 3: home.vue**

```vue
<!-- frontend-nuxt/pages/home.vue -->
<template>
  <div class="home-page">
    <div class="welcome">
      <h2>{{ greeting }}，{{ authStore.userName }}</h2>
      <p>{{ authStore.roleName }} · {{ authStore.schoolName }}</p>
    </div>
    <div class="module-grid">
      <div
        v-for="menu in authStore.menus"
        :key="menu.code"
        class="module-card"
        @click="navigateToModule(menu)"
      >
        <div class="module-icon">
          <el-icon :size="32">
            <component :is="iconMap[menu.icon] || 'Document'" />
          </el-icon>
        </div>
        <div class="module-info">
          <h3>{{ menu.name }}</h3>
          <p>{{ menu.children.length }} 个功能</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Document, DataAnalysis, TrendCharts, Notebook, Reading,
  Collection, User, OfficeBuilding,
} from '@element-plus/icons-vue'

const iconMap: Record<string, any> = {
  document: Document, 'data-analysis': DataAnalysis,
  'trend-charts': TrendCharts, notebook: Notebook,
  reading: Reading, collection: Collection,
  user: User, 'office-building': OfficeBuilding,
}

const authStore = useAuthStore()
const { navigateToModule } = useMenus()

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 12) return '上午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})
</script>

<style scoped lang="scss">
.home-page {
  max-width: 1200px;
  margin: 0 auto;
}

.welcome {
  margin-bottom: 30px;

  h2 {
    font-size: 22px;
    margin-bottom: 4px;
  }

  p {
    color: #909399;
    font-size: 14px;
  }
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.module-card {
  background: #fff;
  border-radius: var(--hfs-card-radius);
  box-shadow: var(--hfs-card-shadow);
  padding: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: box-shadow 0.2s, transform 0.2s;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
  }

  .module-icon {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    background: var(--el-color-primary-light-9);
    color: var(--hfs-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .module-info {
    h3 {
      font-size: 16px;
      margin-bottom: 4px;
    }

    p {
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend-nuxt/pages/index.vue frontend-nuxt/pages/login.vue frontend-nuxt/pages/home.vue
git commit -m "feat(frontend): login + home pages — auth flow and module card grid"
```

**审查清单:**
- ✓ index.vue 根据 token 重定向
- ✓ login.vue 使用 auth layout，调用 api.login()
- ✓ login 成功后设置 token + 加载用户 + 加载菜单 + 跳转 home
- ✓ home.vue 动态渲染可见模块卡片
- ✓ 点击模块卡片跳转到该模块第一个子页面

**边界条件:**
- 登录失败（用户名/密码错误）→ 显示 ElMessage.error，不跳转
- 登录成功但 loadMenus 失败 → 跳转 home 但模块卡片为空
- index.vue 无 token → /login；有 token → /home

**测试契约:**
1. 登录成功链路
   - 入口: `/login` 页面输入 admin/123456 点击登录
   - 反例: 错误实现不设置 cookie → 刷新后回到 login
   - 边界: 空用户名 / 空密码（表单校验拦截）
   - 回归: N/A
   - 命令: Batch 2 独立验证段（见 plan 头部「Batch 2 独立验证命令」）
2. home 页面模块渲染
   - 入口: `/home`（已登录）
   - 反例: 错误实现不从 authStore.menus 读取 → 空页面
   - 边界: menus=[]（菜单加载失败）→ 不显示模块卡片但不崩溃
   - 回归: N/A
   - 命令: Batch 2 独立验证段（见 plan 头部「Batch 2 独立验证命令」）

---

### Task 10: 前端 — usePowerOptions + PowerFilter

**Files:**
- Create: `frontend-nuxt/composables/usePowerOptions.ts`
- Create: `frontend-nuxt/components/common/PowerFilter.vue`

- [ ] **Step 1: 创建 usePowerOptions**

```typescript
// frontend-nuxt/composables/usePowerOptions.ts
interface PowerOption {
  grade: string
  classes: {
    class: string
    subjects: {
      subject: string
      examids: string[]
    }[]
  }[]
}

interface ExamInfo {
  name: string
  event_time: string
  type: number
}

interface AnalysisParams {
  clazz: string
  subject: string
  examids: string[]
  isTeach: boolean
}

export function usePowerOptions() {
  const api = useApi()

  const tree = ref<PowerOption[]>([])
  const examInfoMap = ref<Record<string, ExamInfo>>({})

  const selectedGrade = ref('')
  const selectedClass = ref('')
  const selectedSubject = ref('')
  const selectedExamIds = ref<string[]>([])

  const gradeOptions = computed(() => tree.value.map((g) => g.grade))

  const classOptions = computed(() => {
    const grade = tree.value.find((g) => g.grade === selectedGrade.value)
    return grade?.classes.map((c) => c.class) || []
  })

  const subjectOptions = computed(() => {
    const grade = tree.value.find((g) => g.grade === selectedGrade.value)
    const cls = grade?.classes.find((c) => c.class === selectedClass.value)
    return cls?.subjects.map((s) => s.subject) || []
  })

  const examOptions = computed(() => {
    const grade = tree.value.find((g) => g.grade === selectedGrade.value)
    const cls = grade?.classes.find((c) => c.class === selectedClass.value)
    const subj = cls?.subjects.find((s) => s.subject === selectedSubject.value)
    return (subj?.examids || []).map((id) => ({
      id,
      ...(examInfoMap.value[id] || { name: id, event_time: '', type: 0 }),
    }))
  })

  const analysisParams = computed<AnalysisParams>(() => ({
    clazz: selectedClass.value,
    subject: selectedSubject.value,
    examids: selectedExamIds.value,
    isTeach: false,
  }))

  // 级联自动选中：上级变化时自动选中下级第一项
  watch(selectedGrade, () => {
    selectedClass.value = classOptions.value[0] || ''
  })
  watch(selectedClass, () => {
    selectedSubject.value = subjectOptions.value[0] || ''
  })
  watch(selectedSubject, () => {
    const exams = examOptions.value
    selectedExamIds.value = exams.length ? [exams[0].id] : []
  })

  async function load(examType?: number, year?: number) {
    try {
      const res = await api.getPowerOptions({ exam_type: examType, year })
      tree.value = res.powerOptions || []
      examInfoMap.value = res.examInfoMap || {}
      if (tree.value.length) {
        selectedGrade.value = tree.value[0].grade
      }
    } catch {
      tree.value = []
      examInfoMap.value = {}
    }
  }

  return {
    load,
    tree,
    examInfoMap,
    selectedGrade,
    selectedClass,
    selectedSubject,
    selectedExamIds,
    gradeOptions,
    classOptions,
    subjectOptions,
    examOptions,
    analysisParams,
  }
}
```

- [ ] **Step 2: 创建 PowerFilter**

```vue
<!-- frontend-nuxt/components/common/PowerFilter.vue -->
<template>
  <div class="filter-bar">
    <el-select
      v-if="grades.length"
      v-model="gradeModel"
      placeholder="年级"
      size="default"
      style="width: 120px"
    >
      <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
    </el-select>
    <el-select
      v-if="classes.length"
      v-model="classModel"
      placeholder="班级"
      size="default"
      style="width: 140px"
    >
      <el-option v-for="c in classes" :key="c" :label="c" :value="c" />
    </el-select>
    <el-select
      v-if="subjects.length"
      v-model="subjectModel"
      placeholder="学科"
      size="default"
      style="width: 120px"
    >
      <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
    </el-select>
    <el-select
      v-if="exams.length"
      v-model="examModel"
      placeholder="考试"
      size="default"
      style="width: 200px"
    >
      <el-option
        v-for="e in exams"
        :key="e.id"
        :label="e.name"
        :value="e.id"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  grades: string[]
  classes: string[]
  subjects: string[]
  exams: { id: string; name: string }[]
}>()

const gradeModel = defineModel<string>('grade')
const classModel = defineModel<string>('class')
const subjectModel = defineModel<string>('subject')
const examModel = defineModel<string>('exam')
</script>
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend-nuxt/composables/usePowerOptions.ts frontend-nuxt/components/common/PowerFilter.vue
git commit -m "feat(frontend): usePowerOptions composable + PowerFilter component — cascading filter pattern"
```

**审查清单:**
- ✓ 四级级联：年级→班级→学科→考试
- ✓ 上级变化时自动选中下级第一项
- ✓ analysisParams computed 自动构建请求参数
- ✓ PowerFilter 用 defineModel 双向绑定
- ✓ load() 容错处理（API 失败不崩溃）

**边界条件:**
- 空数据（tree=[]）→ 所有 select 不显示，analysisParams.examids=[]
- 年级只有一个 → 自动选中，班级 select 直接显示
- API 失败 → tree 清空，不影响页面渲染

**变更类型:** 行为变更（级联联动逻辑 + load() API 调用 + watch 自动选中）。
**测试契约（F002 R2 + F012 R3 补 Vitest）:**
1. load() stub 返回空数据时不崩溃（F007 R2 依赖 getPowerOptions stub）
   - 入口: `const pw = usePowerOptions(); await pw.load()`
   - 反例: 错误实现不处理 empty tree → selectedGrade 为 undefined，后续 watch 链崩溃
   - 边界: tree=[] / 单年级单班级单科目 / 多级全空
   - 回归: F007 R2
   - 命令: `cd frontend-nuxt && npx vitest run tests/composables/usePowerOptions.test.ts -t load_empty`
   - Vitest 骨架:
     ```ts
     it('load() 空 tree 时不崩溃', async () => {
       const pw = usePowerOptions()
       await pw.load()  // getPowerOptions stub 返回空
       expect(pw.tree.value).toEqual([])
       expect(pw.selectedGrade.value).toBe('')
     })
     ```
2. 级联 watch 上级变化重置下级
   - 入口: 手动设置 tree 后改 selectedGrade → 观察 selectedClass / selectedSubject
   - 反例: 错误实现不触发 watch → selectedClass 残留旧值
   - 边界: 切换到无班级年级 → selectedClass = '' / 切换到无科目班级 → selectedSubject = ''
   - 回归: F010 (PowerFilter 级联行为)
   - 命令: `cd frontend-nuxt && npx vitest run tests/composables/usePowerOptions.test.ts -t cascade_reset`
   - Vitest 骨架:
     ```ts
     it('切换 grade 时 class/subject 重置', async () => {
       const pw = usePowerOptions()
       pw.tree.value = [{ grade: '高三', classes: [{ class: '1班', subjects: [{subject: '语文', examids: ['e1']}] }] }]
       pw.selectedGrade.value = '高三'
       await nextTick()
       expect(pw.selectedClass.value).toBe('1班')
       expect(pw.selectedSubject.value).toBe('语文')
     })
     ```

---

### Task 11: 前端 — 45 个页面 Stub

**Files:**
- Create: 45 个 `.vue` 文件在 `frontend-nuxt/pages/` 下

- [ ] **Step 1: 创建页面 stub 生成脚本**

```bash
cd C:/Users/Administrator/edu-cloud/frontend-nuxt

# 创建所有模块目录
mkdir -p pages/{exam,report,study,work,lesson,research,baseinfo,academic,knowledge-tree}
```

- [ ] **Step 2: 创建 exam/ 页面（5 个）**

每个 stub 页面遵循统一模板。以 exam/list.vue 为例：

```vue
<!-- frontend-nuxt/pages/exam/list.vue -->
<template>
  <div class="page-stub">
    <div class="breadcrumb">阅卷 / 考试列表</div>
    <h2>考试列表</h2>
    <div class="page-card">
      <div class="placeholder">
        <p>📋 考试列表页面</p>
        <p>Phase 2 迁移：ExamListPage.vue → 此页面</p>
      </div>
    </div>
  </div>
</template>
```

其余 exam/ 页面：`quiz.vue`（测验列表）、`grading.vue`（阅卷任务）、`answercard.vue`（答题卡工具）、`statistics.vue`（考试统计）。格式相同，只改标题和说明文字。

- [ ] **Step 3: 创建 report/ 页面（6 个）**

`exam.vue`（考试报告）、`contrast.vue`（班级对比）、`custom.vue`（自定义分析）、`table.vue`（自定义表格）、`level-score.vue`（等级赋分）、`config.vue`（指标配置）。

- [ ] **Step 4: 创建 study/ 页面（4 个）**

`dashboard.vue`（数据看板）、`class.vue`（班级学情）、`student.vue`（学生学情）、`layer.vue`（分层学情）。

- [ ] **Step 5: 创建 work/ 页面（4 个）**

`list.vue`（作业列表）、`publish.vue`（布置作业）、`scan.vue`（扫描作业）、`sync.vue`（同步作业）。

- [ ] **Step 6: 创建 lesson/ 页面（4 个）**

`console.vue`（精准教学台）、`after-exam.vue`（考后分析）、`resources.vue`（备课资源）、`space.vue`（我的空间）。

- [ ] **Step 7: 创建 research/ 页面（7 个）**

`questions.vue`（题库选题）、`paper-builder.vue`（结构组卷）、`group-prep.vue`（集体备课）、`knowledge.vue`（知识体系）、`plan.vue`（教学计划）、`radar.vue`（考情雷达）、`school-resources.vue`（校本资源）。

- [ ] **Step 8: 创建 baseinfo/ 页面（7 个）**

`students.vue`（学生信息）、`teachers.vue`（教师信息）、`grades.vue`（年级管理）、`records.vue`（人员动态）、`schedule.vue`（教师任课表）、`selected-exam.vue`（选考管理）、`vip.vue`（版本权益）。

- [ ] **Step 9: 创建 academic/ 页面（5 个）**

`semester.vue`（学期管理）、`timetable.vue`（课表）、`course-selection.vue`（选课）、`exam-schedule.vue`（考试安排）、`score-manage.vue`（成绩管理）。

- [ ] **Step 10: 创建 knowledge-tree/index.vue**

```vue
<!-- frontend-nuxt/pages/knowledge-tree/index.vue -->
<template>
  <div class="page-stub">
    <h2>知识图谱</h2>
    <div class="page-card">
      <div class="placeholder">
        <p>🌳 知识图谱可视化</p>
        <p>Phase 2 迁移：AntV G6 力导向图 + 教师工作台</p>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 11: 验证所有路由**

Run: `cd C:/Users/Administrator/edu-cloud/frontend-nuxt && npx nuxt dev --port 3000`
手动验证：访问 `/exam/list`、`/report/exam`、`/study/dashboard`、`/work/list` 等确认路由可达

- [ ] **Step 12: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend-nuxt/pages/
git commit -m "feat(frontend): 45 page stubs across 8 modules + knowledge-tree"
```

**审查清单:**
- ✓ 8 模块目录全部创建（exam/report/study/work/lesson/research/baseinfo/academic + knowledge-tree）
- ✓ 45 个页面文件名与设计文档 §2 完全一致
- ✓ 每个 stub 有模块名面包屑 + 页面标题 + Phase 迁移说明
- ✓ Nuxt 文件路由自动注册，无需手动配置 router
- ✗ stub 不应包含业务逻辑或 API 调用

**边界条件:**
- Nuxt 文件路由: `pages/exam/list.vue` → `/exam/list`（无需 router 配置）
- `level-score.vue` → `/report/level-score`（连字符路径正确映射）
- `knowledge-tree/index.vue` → `/knowledge-tree`（目录 index 映射）

**变更类型:** 非行为变更（45 个纯占位页面，无业务逻辑、无 API 调用）。
**测试契约（F002 R2）:**
1. 45 个路由均可达（不 404）
   - 入口: 浏览器逐一访问每个 path（登录后）
   - 反例: 错误实现文件名有拼写错 → Nuxt 路由 404
   - 边界: 路径含连字符 / 目录 index / 多级嵌套
   - 回归: N/A
   - 命令: `for p in /exam/list /exam/quiz ... /knowledge-tree; do curl -s -o /dev/null -w "$p %{http_code}\n" http://localhost:3000$p; done`（登录态 cookie 注入）

---

### Task 12: 端到端验证

**Files:** 无新增，验证现有代码

- [ ] **Step 1: 启动后端**

Run: `cd C:/Users/Administrator/edu-cloud && python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000`

- [ ] **Step 2: 运行 migration + 种子**

Run:
```bash
cd C:/Users/Administrator/edu-cloud
python -m alembic upgrade head
python scripts/seed_menus.py
```

- [ ] **Step 3: 启动前端**

Run: `cd C:/Users/Administrator/edu-cloud/frontend-nuxt && npx nuxt dev --port 3000`

- [ ] **Step 4: 验证登录流程**

1. 访问 http://localhost:3000 → 应重定向到 /login
2. 输入 admin / 123456 → 应跳转到 /home
3. home 页应显示模块卡片（数量取决于 admin 角色可见模块）

- [ ] **Step 5: 验证导航**

1. 顶部应显示 8 个模块导航
2. 点击"阅卷"→ 跳转到 /exam/list，顶部"阅卷"高亮
3. 蓝色二级条显示：考试列表(高亮) / 测验列表 / 阅卷任务 / 答题卡工具 / 考试统计
4. 点击"测验列表"→ URL 变为 /exam/quiz，二级条对应项高亮
5. 切换到"教研"模块 → 二级条变为 7 个子菜单

- [ ] **Step 6: 验证后端测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 所有测试 PASS（1582 + 新增 menu 测试）

- [ ] **Step 7: Commit 最终状态**

```bash
cd C:/Users/Administrator/edu-cloud
git add -A
git commit -m "feat: Phase 1 architecture foundation — Nuxt 3 + dynamic menus + 45 page stubs + analysis tables"
```

**审查清单:**
- ✓ 登录 → home → 模块导航 → 页面 stub 全链路畅通
- ✓ 顶部导航动态渲染（从 API 加载）
- ✓ 二级蓝条正确显示当前模块子菜单
- ✓ 后端全量测试通过
- ✓ Alembic migration 可正向执行
- ✗ 不应修改现有 frontend/ 目录的任何文件

**变更类型:** 非行为变更（Task 12 本身就是验证任务，无代码产出）。本 Task 的每个 Step 即为端到端验证步骤，不需要独立测试契约。
