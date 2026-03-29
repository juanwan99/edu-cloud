# Phase 1b: 基础信息增强 设计文档
> [2026-03-29 23:54:34 实现完成] Commits: 11c5d97..5712b6e | GPT R2→R3 PASS (F01 accepted-risk + F02 resolved)

> **日期**: 2026-03-29 21:38:16
> **项目**: edu-cloud（多校多角色教育管理平台）
> **前置**: Phase 1a 模块管理核心 [实现完成]
> **上游设计**: `docs/plans/2026-03-29-business-logic-backfill-design.md` §1.2

---

## 0. 范围与决策

**本 Phase 范围**: 排课表 + 选考组合（业务基础数据）。

**明确排除**:
- 变更审计日志 → 并入 Phase 1c（与权限引擎高度耦合）
- 年级层级增强 → Class 已有 grade + grade_number，无需改动
- 知识点关联 → QuestionKnowledgePoint junction table 已存在，无需改动
- 排课表与 UserRole scope 同步 → Phase 1b 独立共存，Phase 1c 权限引擎时再考虑派生

**关键设计决策**:

| 决策 | 选择 | 理由 |
|------|------|------|
| 审计日志归属 | Phase 1c | 与权限引擎高度耦合（谁做了什么 = 权限验证的反面） |
| 排课粒度 | 含学期，不含课时 | 教师每学期换班常见；课时排表是专业排课软件领域 |
| 选考组合范围 | 纯学校配置，不关联学生 | 学生选科是 Phase 2 学情分析的事 |
| 排课 vs 权限 | 独立共存 | 排课是业务事实，UserRole scope 是权限配置，语义不同 |

---

## 1. 排课表 (teacher_assignments)

### 1.1 数据模型

```python
class TeacherAssignment(Base, IdMixin, TimestampMixin):
    """教师排课记录：哪个教师在哪个学期教哪个班的什么科目。"""
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "class_id", "subject_code", "semester",
                         name="uq_teacher_assignment"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), index=True)
    subject_code: Mapped[str] = mapped_column(String(50))       # "math" / "english" 等
    semester: Mapped[str] = mapped_column(String(20))            # "2025-2026-2"
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 软删除/学期结束标记
```

**唯一约束**: 同一教师 + 同一班级 + 同一科目 + 同一学期 不重复。

### 1.2 API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/schools/{school_id}/assignments` | 列表（支持 semester / user_id / class_id / subject_code 过滤） |
| POST | `/api/v1/schools/{school_id}/assignments` | 创建（支持批量：一个教师 + 多 class_id） |
| DELETE | `/api/v1/schools/{school_id}/assignments/{id}` | 删除单条 |
| GET | `/api/v1/schools/{school_id}/assignments/summary` | 按教师聚合摘要（教师名 + 班级数 + 科目列表） |

**权限**: `MANAGE_SCHOOL_SETTINGS`（复用 Phase 1a，principal / academic_director / district_admin / platform_admin）

**scope guard**: 复用 `_check_school_scope` 模式，school-scoped 角色只能访问自己学校。

### 1.3 Service 层

```python
# school_id 贯穿所有函数，确保数据隔离
async def list_assignments(db, *, school_id, semester=None, user_id=None, class_id=None, subject_code=None)
async def create_assignments(db, *, school_id, user_id, class_ids: list[str], subject_code, semester)
    # 批量创建：一个教师 + 多个班级，跳过已存在的（幂等）
async def delete_assignment(db, *, school_id, assignment_id)
async def get_summary(db, *, school_id, semester=None)
    # 返回 [{user_id, display_name, class_count, subject_codes: [...]}]
```

**批量创建语义**: POST body 含 `class_ids: ["id1", "id2", ...]`，为每个 class_id 创建一条记录。已存在的跳过（不报错），返回实际创建的数量。

### 1.4 前端

**TeacherAssignmentsPage.vue** — 排课管理页：
- 顶部：学期选择器（NSelect）+ 年级筛选（NSelect，从 classes 的 grade 去重）
- 主体：NDataTable 展示排课列表（教师名 / 班级名 / 科目 / 学期）
- 操作：新增按钮 → NModal 弹窗（选教师 → 选科目 → 多选班级 → 确认批量创建）
- 行操作：删除（NPopconfirm 确认）

**sidebar 入口**: principal / academic_director 角色可见，icon: `settings`，label: "排课管理"，route: `/assignments`

---

## 2. 选考组合 (subject_selections)

### 2.1 数据模型

```python
class SubjectSelection(Base, IdMixin, TimestampMixin):
    """学校提供的选考科目组合（如"物化生"、"史地政"）。"""
    __tablename__ = "subject_selections"
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_subject_selection_name"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))                # "物化生" / "史地政"
    subject_codes: Mapped[list] = mapped_column(JSON)            # ["physics", "chemistry", "biology"]
    mode: Mapped[str] = mapped_column(String(20), default="custom")  # "3+1+2" / "3+3" / "custom"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

**校验规则**:
- `subject_codes`: 至少 1 个、最多 7 个，元素为非空字符串
- `name`: 同校唯一（UniqueConstraint）
- `mode`: 枚举 `{"3+1+2", "3+3", "custom"}`

### 2.2 API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/schools/{school_id}/selections` | 列表（支持 is_active / mode 过滤） |
| POST | `/api/v1/schools/{school_id}/selections` | 创建 |
| PATCH | `/api/v1/schools/{school_id}/selections/{id}` | 更新（名称 / 科目 / mode / 启停） |
| DELETE | `/api/v1/schools/{school_id}/selections/{id}` | 删除 |

**权限 + scope guard**: 同排课表。

### 2.3 Service 层

```python
async def list_selections(db, *, school_id, is_active=None, mode=None)
async def create_selection(db, *, school_id, name, subject_codes, mode="custom")
    # 校验 subject_codes 长度 + mode 枚举 + name 唯一
async def update_selection(db, *, school_id, selection_id, **kwargs)
async def delete_selection(db, *, school_id, selection_id)
```

### 2.4 前端

**SubjectSelectionsPage.vue** — 选考管理页：
- 主体：卡片列表（NCard），每张卡片展示组合名称 + 科目标签（NTag）+ 模式 + 启停开关（NSwitch）
- 操作：新增按钮 → NModal 弹窗（输入名称 → 选择模式 → 多选科目 → 确认）
- 行操作：编辑 / 删除

**sidebar 入口**: principal / academic_director 角色可见，icon: `exam`，label: "选考组合"，route: `/selections`

---

## 3. 文件规划

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/edu_cloud/models/teacher_assignment.py` | TeacherAssignment ORM |
| `src/edu_cloud/models/subject_selection.py` | SubjectSelection ORM |
| `src/edu_cloud/services/teacher_assignment_service.py` | 排课 CRUD + 批量创建 + 聚合摘要 |
| `src/edu_cloud/services/subject_selection_service.py` | 选考 CRUD + 校验 |
| `src/edu_cloud/modules/school/assignment_router.py` | 排课 API |
| `src/edu_cloud/modules/school/selection_router.py` | 选考 API |
| `tests/test_services/test_teacher_assignment_service.py` | 排课 service 测试 |
| `tests/test_services/test_subject_selection_service.py` | 选考 service 测试 |
| `tests/test_api/test_teacher_assignments.py` | 排课 API 测试 |
| `tests/test_api/test_subject_selections.py` | 选考 API 测试 |
| `frontend/src/api/teacherAssignments.js` | 排课 API client |
| `frontend/src/api/subjectSelections.js` | 选考 API client |
| `frontend/src/pages/TeacherAssignmentsPage.vue` | 排课管理页 |
| `frontend/src/pages/SubjectSelectionsPage.vue` | 选考管理页 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/edu_cloud/api/app.py` | 注册两个 router + lifespan 导入模型 |
| `alembic/env.py` | 导入新模型 |
| `tests/conftest.py` | 导入新模型 |
| `tests/test_alembic_migration.py` | 导入新模型 |
| `frontend/src/config/sidebarConfig.js` | principal/academic_director 加排课+选考导航项 |
| `frontend/src/router/index.js` | 加两个路由 |
| `CLAUDE.md` | 同步 API 端点 + 数据模型 |

### 不改动

- UserRole / permissions — 排课表与权限独立
- 知识点 / Question — 已有 junction table
- 年级层级 — Class 已有 grade + grade_number

---

## 4. 测试策略

**预期 ~30 个新测试**:

| 层 | 测试 | 数量 |
|----|------|------|
| Service (排课) | model CRUD / 批量幂等 / 唯一约束 / summary 聚合 | ~6 |
| Service (选考) | model CRUD / 校验规则 / 唯一约束 | ~5 |
| API (排课) | CRUD + 过滤 / 批量创建 / 权限 / scope guard / 多校隔离 | ~8 |
| API (选考) | CRUD + 过滤 / 校验拒绝 / 权限 / scope guard / 多校隔离 | ~8 |
| Migration | 已有 smoke test 覆盖（只需导入模型） | 0 (复用) |
| Frontend | vite build 验证 | 0 (手动) |
