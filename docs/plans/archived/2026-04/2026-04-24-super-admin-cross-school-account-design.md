# 超管跨校创建学校管理账号 — Design

**版本**: v0.1
**日期**: 2026-04-24
**Scope**: T3（跨模块 + 公开 API 契约变更）
**状态**: 设计完成，待 user review → 独立新会话走 writing-plans

---

## §1 目标

`platform_admin`（超管）登录 `https://mcu.asia/teachers`，能为**任一既有学校**创建两类学校管理账号：
- `principal`（校长）
- `academic_director`（教务主任）

其他角色（`principal` / `academic_director` / `subject_teacher` 等）在 `POST /teachers` 上的行为保持不变——他们依然只能在**自己所在学校**内创建教师/管理者。

---

## §2 架构 & 职责

| 关注点 | 承担 |
|---|---|
| 入口 | `TeachersPage.vue` 顶部加"学校"下拉；**仅超管可见** |
| 选校 → 数据切换 | 选中某校后，表格切到该校教师列表（`GET /teachers?school_id=...`，后端 `teacher_router.py:107` 已支持此参数），创建表单预填 `school_id` |
| 权限判定 | `POST /teachers` 判断 `is_cross_school`；跨校场景挂 `require_permission(MANAGE_SCHOOLS)` 守卫 |
| 落库 | 组合插入 `users` 一行 + `user_roles` 一行：`role=principal/academic_director`, `school_id=选中校.id`, `is_primary=True` |

**关键判断**：

```
is_cross_school = (req.school_id is not None) and (
    current_role.school_id is None or current_role.school_id != req.school_id
)
```

---

## §3 后端契约变更

### 3.1 `TeacherCreate` schema（`src/edu_cloud/modules/student/teacher_router.py:39-56`）

新增字段：

```python
class TeacherCreate(BaseModel):
    username: str
    display_name: str
    password: str = "123456"
    roles: list[str] = ["subject_teacher"]
    school_id: str | None = None          # ← 新增，仅超管跨校时需传
    # 其他既有字段保持不变...
```

**语义**：
- 非超管角色 **忽略此字段**——始终用 `current_role.school_id`
- 超管角色可传此字段指定目标学校
- 超管不传此字段时，维持原错误路径（`school_id=None` → 业务校验失败）

### 3.2 Router 逻辑（`teacher_router.py:147-190`）

**删除死代码 fallback**：

```python
# 删除以下（hasattr 对 Pydantic 未声明字段恒 False）：
school_id = current["current_role"].school_id or (
    req.school_id if hasattr(req, 'school_id') else None
)
```

**替换为**：

```python
current_role = current["current_role"]
is_cross_school = (req.school_id is not None) and (
    current_role.school_id is None or current_role.school_id != req.school_id
)
if is_cross_school:
    require_permission(current, Permission.MANAGE_SCHOOLS)
    target_school_id = req.school_id
else:
    target_school_id = current_role.school_id or req.school_id
if target_school_id is None:
    raise ValidationError("缺少 school_id")
```

### 3.3 Permission 守卫

**`core/permissions.py` 零改动**——复用既有 `Permission.MANAGE_SCHOOLS`。

**引入来源**：`from edu_cloud.core.permissions import Permission` + `from edu_cloud.api.deps import require_permission`（注意 `require_permission` 在 edu_cloud 里是 async helper，不是 FastAPI `Depends()` 装饰器；写 impl 时确认签名）。

---

## §4 前端 UI 变更

### 4.1 `TeachersPage.vue`

顶部筛选栏：

```vue
<n-select
  v-if="isPlatformAdmin"
  v-model:value="selectedSchoolId"
  :options="schoolOptions"
  placeholder="请选择学校（超管跨校管理）"
/>
```

- `isPlatformAdmin = computed(() => auth.currentRole?.role === 'platform_admin')`
- `schoolOptions` 从 `GET /schools` 拉，格式 `[{ label: '景炎初级中学', value: '<uuid>' }, ...]`

### 4.2 表格数据源切换

- 超管模式：`GET /teachers?school_id=<selectedSchoolId>`
- 其他模式：`GET /teachers`（后端用 `current_role.school_id` 过滤）

### 4.3 创建表单角色下拉限制

```js
const roleOptions = computed(() => {
  if (isPlatformAdmin.value && selectedSchoolId.value) {
    // 超管跨校场景：只两个选项
    return [
      { label: '校长', value: 'principal' },
      { label: '教务主任', value: 'academic_director' },
    ]
  }
  // 其他场景沿用既有全部校级角色
  return EXISTING_ROLE_OPTIONS
})
```

### 4.4 提交 payload

`createTeacher({ ..., school_id: isPlatformAdmin ? selectedSchoolId : undefined })`

### 4.5 `frontend/src/api/teachers.js`

`listTeachers` 支持 `school_id` query 参数（可能需扩展既有 API 函数签名）。

---

## §5 测试策略（TDD，先红后绿）

### 5.1 后端

新增或追加 `tests/test_api_exam/test_teachers_cross_school.py`（文件名按既有测试目录惯例确定）：

| 场景 | 断言 |
|---|---|
| `platform_admin` 传 `school_id=景炎.id` + `role=principal` | 201，`user_role.school_id == 景炎.id`, `user_role.role == 'principal'` |
| `platform_admin` 不传 `school_id`（current_role 也无 school_id） | 422（ValidationError 缺少 school_id） |
| `subject_teacher` 传 `req.school_id=另一校.id` | 403（MANAGE_SCHOOLS 缺失） |
| `principal` 传 `req.school_id=本校.id`（显式本校，非跨校） | 201（兼容；`is_cross_school=False`） |
| `principal` 传 `req.school_id=另一校.id` | 403 |
| `platform_admin` 传 `role=subject_teacher`（不在允许集合） | 后端**沿用既有 `ALL_SCHOOL_ROLES` 校验**（subject_teacher 合法，返回 201）；仅前端 UI 限制超管跨校下拉只显示 principal + academic_director。避免破坏"校长在本校建科任"既有契约，详见 §6 决策 |

### 5.2 前端

新增 `frontend/src/pages/__tests__/TeachersPage.cross-school.test.js`：

| 场景 | 断言 |
|---|---|
| `platform_admin` 登录 + 进 TeachersPage | 学校下拉渲染可见 |
| `subject_teacher` 登录 + 进 TeachersPage | 学校下拉不渲染（`v-if` false） |
| 超管选中某校 + 填表单提交 | `createTeacher` 被调用时 payload 含 `school_id` |
| 超管模式下创建表单的角色下拉 | options 长度 = 2，含 `principal` 和 `academic_director` |

---

## §6 影响面 & 范围

### 影响文件
- `src/edu_cloud/modules/student/teacher_router.py` — schema 新增字段 + router 逻辑重写
- `frontend/src/pages/TeachersPage.vue` — UI + 逻辑
- `frontend/src/api/teachers.js` — `listTeachers` 支持 `school_id` query 参数
- 后端测试新增 1 个文件
- 前端测试新增 1 个文件

### 非影响
- `core/permissions.py` 零动
- `user_roles` 表结构零动（使用既有 `role` + `school_id` + `is_primary` 字段）
- `SchoolsPage.vue` 零动（入口选了 B 路径 TeachersPage）
- `sidebarConfig.js` 零动（超管 sidebar 已含 `/teachers`）

### 非目标（scope exclusion）
- 不修 `POST /students` 无 permission guard 问题（T3-D followup：学生/教师 POST 端点普遍无 permission 守卫）
- 不扩"超管跨校创建科任/班主任"（只限 principal + academic_director）
- 不加 `MANAGE_SCHOOL_ADMIN_ACCOUNTS` permission（YAGNI）
- 不做 `district_admin` 跨校建账号能力（未来若要再加）
- 后端 `POST /teachers` 不做角色白名单强校验（仅前端 UI 限制选项；后端允许 `ALL_SCHOOL_ROLES` 保持既有契约，避免破坏"校长在本校建科任教师"路径）

### 决策理由（§6 最后一条）
**为什么后端不做"只允许 principal/academic_director"白名单？**
- 跨校守卫（`MANAGE_SCHOOLS`）已经阻止非超管调用
- 超管本身是授信角色，前端 UI 限制选项已足够引导
- 后端再加角色白名单 = 改变 `POST /teachers` 既有契约，会破坏 `principal` 在本校建 `subject_teacher` 的合法路径
- **根本原因**：跨校/非跨校的判断决定是否挂 `MANAGE_SCHOOLS`，角色枚举由前端场景化裁剪即可

---

## §7 Evidence Block

**decision**: 超管跨校建管理账号 = `TeacherCreate` 加 `school_id` 字段 + router 跨校判断 + `MANAGE_SCHOOLS` 守卫 + `TeachersPage` 学校下拉（超管可见）

**evidence_refs**:
- `src/edu_cloud/modules/student/teacher_router.py:39-56` — `TeacherCreate` 当前无 `school_id` 字段（verified via Read 2026-04-24）
- `src/edu_cloud/modules/student/teacher_router.py:152-154` — `hasattr(req, 'school_id')` fallback 是死代码（Pydantic 实例 hasattr 对未声明字段恒 False，verified via code-read）
- `src/edu_cloud/modules/student/teacher_router.py:107` — `GET /teachers` 已支持 `school_id: str | None = None` 查询参数（verified via Grep）
- `src/edu_cloud/core/permissions.py:23,109,143,173` — `MANAGE_SCHOOLS` 归属 `platform_admin`（verified via Grep）
- `src/edu_cloud/modules/student/teacher_router.py:22-28` — `ALL_SCHOOL_ROLES = TEACHER_ROLES ∪ {principal, academic_director, district_admin}`（verified via Read）
- `frontend/src/config/sidebarConfig.js:49` — `platform_admin` sidebar 已挂 `/teachers` 路由入口（verified via Grep）
- `grep -rn "景炎" src/ scripts/ frontend/` → 零命中，景炎学校在代码库不存在（verified via Bash）

**Q1**: evidence_source: code-grep + code-read | evidence_state: verified

**Q2_excluded**:
- 备选 A（SchoolsPage 行操作入口）: 用户选 B（2026-04-24 对话）；反证: A 方案要新建弹窗 + 子页面，改动集中度低于 B
- 备选 B（新增 `MANAGE_SCHOOL_ADMIN_ACCOUNTS` permission）: 用户选复用 `MANAGE_SCHOOLS`（YAGNI，无第二个持有人）；反证: 若 permission 只有 `platform_admin` 一个持有者，与 `MANAGE_SCHOOLS` 无功能区分
- 备选 C（开放 `ALL_SCHOOL_ROLES` 全部角色）: 用户选仅 `principal + academic_director`；反证: 用户原意是"学校管理账号"心智，校级管理层两个角色符合语义边界
- 备选 D（新建 `school_admin` 独立角色）: 用户放弃（评估后认为 T4 成本过高，见 2026-04-24 对话）；反证: 加新角色需联动权限枚举、sidebar、RBAC、测试 fixture 全链路，改动面 >8 文件 → L014 升 T4

**impact_scope**: cross-module（frontend `TeachersPage` + backend `modules/student` + 两边测试）

**unknowns**:
- `TeachersPage.vue` 既有 vitest 覆盖度 → followup: writing-plans 阶段调研 `src/pages/__tests__/TeachersPage.*.test.js`（若存在），决定是否复用 fixture
- 既有 `listTeachers` API 函数签名是否已支持 `params` 传入 → followup: 读 `frontend/src/api/teachers.js`

**followup_spike**: none（writing-plans 阶段可直接 Read 上述两处即可解）

---

## §8 semantic_regression（L017 不变量）

**ORC-001**: `POST /teachers` 必须有 school_id 来源（`current_role.school_id` **或** `req.school_id`），否则返回 422。

**ORC-002**: 跨校创建——即 `req.school_id` 提供且不等于 `current_role.school_id`（或 `current_role` 无 school_id）——必须检查 `MANAGE_SCHOOLS` 权限，否则返回 403。

**ORC-003**: TeachersPage 的"学校"下拉仅 `auth.currentRole.role === 'platform_admin'` 时渲染；其他角色下 DOM 不应存在该 select 元素。

**ORC-004**: 超管跨校创建时前端角色下拉 options.length === 2 且仅含 `principal` + `academic_director`；后端不做角色白名单（保持既有契约，见 §6 决策理由）。

---

## §9 实施前置（writing-plans 阶段必读）

- 本 design.md 是 spec，不是 plan。writing-plans 阶段需产出：
  - Task 拆分（按 TDD slice）
  - 每 Task 的测试契约（入口/反例/边界/回归/命令）
  - Gate 触发点
- 独立会话启动 writing-plans 时，传入本 design.md 路径 + 本次对话摘要

## §10 相关历史

- 与 2026-04-24 schools 422 fix 同日衍生（前者修 `POST /schools` 的 district 契约，本 design 延伸到 `POST /teachers` 的 school_id 契约）
- 前置依赖：schools 422 fix 已部署（前端加"学区"字段），超管才能通过 UI 成功创建景炎学校
- 后续：impl 完成后可为 admin 账户挂景炎的 principal 角色，完成 bootstrap 路径闭环
