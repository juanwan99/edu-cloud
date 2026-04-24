---
baseline_command: "cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=no -q; cd frontend-nuxt && npx vitest run"
baseline_verified_at: "2026-04-24T08:44:45+08:00"
baseline_count: "backend 2028 passed / 23 skipped; frontend-nuxt 51 passed"
---

# 教务时间轴基础设施设计

> **目标**：补齐 edu-cloud 教务三大缺口——平台级学期管理、课表排布、考试安排——建立统一的教务时间轴基础设施。
>
> **参考**：好分数（haofenshu-clone）教务模块业务逻辑，经实践验证的 K12 教育 SaaS 模式。

## §1 背景与现状

### 好分数的教务设计思想

好分数用**学年+学期**贯穿全平台时间轴：考试按 `school_year + semester + exam_type` 分类，教师任课按学期管理，学情分析按学期追踪趋势。教务模块 5 个页面覆盖：学期设置、课表、选课、考试安排、成绩管理。

### edu-cloud 三个缺口

| 缺口 | 现状 | 问题 |
|------|------|------|
| 学期管理 | `Exam.semester`/`TeacherAssignment.semester`/`CalendarEvent.semester` 为裸字符串；`ConductSemester` 限定 conduct 模块（class 级） | 无平台级学期实体，各模块各用各的字符串 |
| 课表排布 | `TeacherAssignment` 记录教师×班级×科目×学期 | 只知道"谁教谁"，不知道"什么时候教"（无节次×星期网格） |
| 考试安排 | `Exam` 有 `exam_date` 单个日期字段 | 无科目级时间段、无考场、无监考教师 |

### 决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| ConductSemester 处理 | 替换（平台级 Semester，conduct 双写过渡） | 学期定义是学校统一的，不应按班级分裂 |
| 节次配置粒度 | 全校统一 | V1 简单直接，年级差异通过"不排课"处理 |
| 考试安排方式 | 混合（Subject 加字段 + 监考 JSON） | 最小改动覆盖 80% 场景 |
| 现有 semester 字符串 | 保持不动 | 牵扯面太大，新功能用 semester_id FK |
| 范围 | 后端 + 前端一起 | 好分数页面代码是现成参考，API 不配前端等于白搭 |
| 模块组织 | 新建 `modules/academic/` | 教务逻辑集中，对齐前端 `pages/academic/` |

## §2 数据模型

### 新建 `modules/academic/models.py`

#### Semester（学期）

```python
class Semester(Base, IdMixin, TimestampMixin):
    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint("school_id", "school_year", "term",
                         name="uq_semester"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))            # "2025-2026学年第一学期"
    school_year: Mapped[str] = mapped_column(String(20))     # "2025-2026"
    term: Mapped[int] = mapped_column(Integer)               # 1 或 2
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
```

#### TimePeriod（节次定义）

```python
class TimePeriod(Base, IdMixin):
    __tablename__ = "time_periods"
    __table_args__ = (
        UniqueConstraint("school_id", "semester_id", "period_number",
                         name="uq_time_period"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    semester_id: Mapped[str] = mapped_column(String(36), ForeignKey("semesters.id"))
    period_number: Mapped[int] = mapped_column(Integer)      # 1-10
    name: Mapped[str] = mapped_column(String(20))            # "第一节" / "晚自习一"
    start_time: Mapped[time] = mapped_column(Time)           # 08:00
    end_time: Mapped[time] = mapped_column(Time)             # 08:45
    period_type: Mapped[str] = mapped_column(String(20))     # class / break / activity / self_study
```

#### TimetableSlot（课表格子）

```python
class TimetableSlot(Base, IdMixin):
    __tablename__ = "timetable_slots"
    __table_args__ = (
        UniqueConstraint("class_id", "semester_id", "weekday", "period_id",
                         name="uq_timetable_slot"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    semester_id: Mapped[str] = mapped_column(String(36), ForeignKey("semesters.id"))
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)            # 1-5
    period_id: Mapped[str] = mapped_column(String(36), ForeignKey("time_periods.id"))
    subject_code: Mapped[str] = mapped_column(String(50))
    teacher_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    room: Mapped[str | None] = mapped_column(String(50), default=None)
```

### 扩展 `modules/exam/models.py` Subject 表

```python
# 新增 4 个字段（全部 nullable，不影响现有数据）
exam_start: Mapped[datetime | None] = mapped_column(DateTime, default=None)
exam_end: Mapped[datetime | None] = mapped_column(DateTime, default=None)
exam_room: Mapped[str | None] = mapped_column(String(100), default=None)
proctor_ids: Mapped[list | None] = mapped_column(JSON, default=None)
```

### Alembic Migration

1 个 migration 文件：
- 新建 `semesters`、`time_periods`、`timetable_slots` 三张表
- 给 `subjects` 表加 `exam_start`/`exam_end`/`exam_room`/`proctor_ids` 四个字段
- 全部 nullable，down migration 为 drop table / drop column

## §3 后端 API

### 新建 `modules/academic/router.py`

#### 学期管理

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/api/v1/academic/semesters` | MANAGE_SCHEDULING | 创建学期（校验 UniqueConstraint） |
| GET | `/api/v1/academic/semesters` | 已登录 | 列出本校学期（支持 school_year 过滤） |
| GET | `/api/v1/academic/semesters/current` | 已登录 | 获取当前学期（is_current=True） |
| PATCH | `/api/v1/academic/semesters/{id}` | MANAGE_SCHEDULING | 更新学期（日期/名称） |
| POST | `/api/v1/academic/semesters/{id}/activate` | MANAGE_SCHEDULING | 设为当前学期（同校其他学期自动取消） |

#### 节次配置

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| PUT | `/api/v1/academic/periods` | MANAGE_SCHEDULING | 批量设置节次（整组替换，传完整列表） |
| GET | `/api/v1/academic/periods` | 已登录 | 获取当前学期节次列表（需 semester_id 参数） |

#### 课表管理

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/v1/academic/timetable` | 已登录 | 查询课表（必传 class_id 或 teacher_id + semester_id） |
| PUT | `/api/v1/academic/timetable/{class_id}` | MANAGE_SCHEDULING | 批量保存班级课表（整组替换，传完整格子列表） |
| GET | `/api/v1/academic/timetable/stats` | 已登录 | 课时统计（按科目/教师聚合，需 class_id + semester_id） |

#### 考试安排（扩展 exam router）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| PUT | `/api/v1/exams/{id}/schedule` | MANAGE_EXAMS | 批量设置考试科目时间安排 |
| GET | `/api/v1/exams/{id}/schedule` | 已登录 | 获取考试安排（含科目时间/考场/监考） |

### 业务规则（service 层实现）

1. **学期激活互斥**：`activate` 时，同 school_id 其他学期 `is_current` 置 False
2. **课表冲突检测**：保存课表时校验同一教师同一 semester + weekday + period 不能出现在两个班（返回冲突列表）
3. **考试时间重叠检测**：同一考试的科目时间段不能重叠
4. **课表-排课软关联**：TimetableSlot 的 teacher_id + subject_code + class_id 应在 TeacherAssignment 中存在，不存在时 warning 不阻塞
5. **节次类型过滤**：课表格子仅允许 period_type="class" 或 "self_study" 的节次
6. **教师视图查询**：按 teacher_id 查课表时，返回该教师在所有班级的格子（横向聚合）
7. **权限**：MANAGE_SCHEDULING 角色可写，其他已登录角色只读；教师角色查课表时 RBAC 限定可见班级

## §4 前端页面

### 新增文件

```
frontend-nuxt/
  composables/useAcademic.ts        # 学期/节次/课表/考试安排 API + 状态
  pages/academic/
    semester.vue                     # 填充（替换 stub）
    timetable.vue                    # 填充（替换 stub）
    exam-schedule.vue                # 填充（替换 stub）
```

`useApi.ts` 新增 12 个方法：
- 学期：`createSemester`, `getSemesters`, `getCurrentSemester`, `updateSemester`, `activateSemester`
- 节次：`setPeriods`, `getPeriods`
- 课表：`getTimetable`, `saveTimetable`, `getTimetableStats`
- 考试安排：`setExamSchedule`, `getExamSchedule`

### semester.vue

- **当前学期卡片**：学期名、起止日期、ElProgress 进度条（`已过 X%，第 Y 周`）
- **历史学期 ElTable**：学期名 / 学年 / 起止日期 / 状态标签（active=success、ended=info、upcoming=primary）/ 操作（编辑、激活、删除）
- **作息时间表**：ElCard 展示节次列表（序号/名称/时间段/类型 ElTag），"编辑作息"按钮 → ElDialog 表单
- **新建学期**：ElDialog 表单——学期名、学年、上/下学期 ElRadioGroup、起止日期 ElDatePicker

### timetable.vue

- **筛选栏**：年级 ElSelect → 班级 ElSelect（级联）+ 视图切换 ElRadioGroup（按班级/按教师）
- **课表网格**：ElTable
  - 列：节次时间 | 周一 | 周二 | 周三 | 周四 | 周五
  - 行按段分隔：上午（1-4）/ 下午（5-7）/ 晚自习（8-9）
  - 格子内容：科目名（彩色背景按科目映射）+ 教师 + 教室
  - 今日列高亮 #e6f4ff
- **课时统计**：右侧 ElCard，按科目聚合课时数，ElTag 列表降序
- **编辑模式**：MANAGE_SCHEDULING 角色可见"编辑课表"按钮，点格子 → ElPopover 选科目+教师+教室，保存时 PUT 整张表

### exam-schedule.vue

- **筛选栏**：学期 ElSelect + 考试类型 ElSelect（全部/月考/期中/期末/测验）
- **时间轴**：ElTimeline 纵向
  - 每个考试节点：考试名 + 状态 ElTag（upcoming=primary/ongoing=success/completed=info）
  - 详情：年级 + 科目数 + 天数；科目列表每科一行 `科目 | 时间段 | 考场 | 监考`
  - ongoing 的考试左边框 3px var(--el-color-primary) 高亮
  - completed 的考试 opacity 0.8
- **编辑安排**：ElDialog，ElTable 编辑每科 exam_start/exam_end（DateTimePicker）、exam_room（Input）、proctor_ids（ElSelect multiple，选项从 TeacherAssignment 按科目过滤）
- **状态判定**：所有科目 exam_end < now → completed；任一 exam_start ≤ now ≤ exam_end → ongoing；否则 upcoming

## §5 ConductSemester 迁移

### 阶段 1（本次实现）

- 新建 `semesters` 表
- conduct 学期 API（`/conduct/classes/{id}/semesters`）改为双写：
  - 创建：先写 `semesters` 表（school 级），再写 `conduct_semesters` 表（保持 FK 不断）
  - 查询：从 `semesters` 表读取（过滤 school_id）
  - 激活：同步更新两张表的 `is_current`
- conduct 前端无感知变化
- `conduct_semesters` 表保留，不做 drop

### 阶段 2（后续独立任务，不在本次 scope）

- `conduct_records.semester_id` FK 改为指向 `semesters` 表
- 废弃 `conduct_semesters` 表

## §6 种子数据

在 `seed_demo.py` 追加：
- 2 个学期：2025-2026 第一学期（2025-09-01 ~ 2026-01-15，is_current=True）+ 第二学期（2026-02-17 ~ 2026-07-10）
- 9 个节次：上午 08:00-08:45 / 08:55-09:40 / 10:00-10:45 / 10:55-11:40 + 下午 14:00-14:45 / 14:55-15:40 / 16:00-16:45 + 晚自习 19:00-19:45 / 19:55-20:40
- 2 个班的完整课表（初一 1 班 + 初一 2 班，45 格/班）
- 1 场期中考试安排（语数英 3 科，含时间段/考场/监考）

## §7 测试策略

### 后端测试

| 文件 | 覆盖 | 用例数 |
|------|------|--------|
| `tests/test_api/test_academic_semester.py` | 创建 / 列表+过滤 / 激活互斥 / 重复创建拒绝 / 权限 | 5 |
| `tests/test_api/test_academic_period.py` | 批量设置 / 查询 / 类型校验 | 3 |
| `tests/test_api/test_academic_timetable.py` | 保存 / 冲突检测 / 按教师查询 / 按班级查询 / 权限 | 5 |
| `tests/test_api/test_exam_schedule.py` | 保存 / 时间重叠检测 / 查询 | 3 |
| `tests/test_services/test_conduct_semester_migration.py` | 双写一致性 / activate 同步 / 查询来源 | 3 |

### 前端测试

| 文件 | 覆盖 | 用例数 |
|------|------|--------|
| `frontend-nuxt/tests/composables/useAcademic.test.ts` | API 调用 / 状态管理 / 进度计算 / 错误处理 | 4 |

## §8 批次划分

| 批次 | 内容 | 依赖 |
|------|------|------|
| B1 | Semester + TimePeriod 模型 + Migration + 学期/节次 CRUD API + 种子数据 + 8 测试 | 无 |
| B2 | TimetableSlot 模型 + 课表 API（含冲突检测）+ 5 测试 | B1 |
| B3 | Subject 扩展字段 + 考试安排 API + conduct 双写 + 6 测试 | B1 |
| B4 | useAcademic composable + useApi 12 方法 + 前端 3 页面 + 4 前端测试 | B1-B3 |

## §9 不变量

- **INV-001**：同一学校同一 school_year+term 不能有两个学期（UniqueConstraint 保证）
- **INV-002**：同一学校同时只有一个 is_current=True 的学期（activate service 保证）
- **INV-003**：同一班级同一学期同一 weekday+period 只能有一个课表格子（UniqueConstraint 保证）
- **INV-004**：同一教师同一学期同一 weekday+period 不能在两个班上课（service 冲突检测保证）
- **INV-005**：同一考试的科目时间段不能重叠（service 校验保证）
- **INV-006**：现有 Exam/TeacherAssignment/CalendarEvent 的 semester 字符串字段不做改动
- **INV-007**：conduct_semesters 表保留不删，双写过渡保持 conduct_records FK 不断
