# 德育板块（Conduct Module）设计文档

> 创建时间: 2026-04-12 20:38:49
> 状态: 设计完成
> 来源: class-points 系统全量吸收为 edu-cloud 德育模块

> [2026-04-13 20:24:00 实现完成] Commits: 2333f64..bf630b0 (R1+R2) + e584e6a..93f0b60 (R3) — Gate 2 R1 FAIL → R2 修复 → R2 FAIL → R3 修复（commit e584e6a F002/N001/F004/F006，commit 93f0b60 F007 排行榜断言增强）→ GPT R3 R2 PASS。F001 Alembic SQLite 仍 deferred 到 haofenshu-phase1 Migration Gate Repair。

## §0 背景与决策记录

### 目标
将独立的班级积分管理系统（class-points）接入 edu-cloud，作为德育板块（conduct module）。

### 关键决策

| 决策 | 结论 | 理由 |
|------|------|------|
| 功能边界 | 纯积分管理（加减分、班规、排行、导出） | 先稳定接入，评语/档案后续迭代 |
| 集成方式 | 全量吸收为 `modules/conduct/` | 技术栈一致、避免双数据源、AI 天然集成 |
| 家长登录 | 邀请码 + 手机号/密码注册，登录后绑定孩子 | 微信登录后续迭代 |
| 绑定验证 | 需验证身份（身份证后6位/手机号/自定义验证码） | 防止随意绑定别人孩子 |
| 家长账号定位 | 复用 edu-cloud 的 parent 角色 + guardian_student_links | 一个账号看所有（积分、成绩、作业） |
| 学生 PII | 新建 `student_profiles` 扩展表，不侵入核心 students 表 | PII 隔离、模块可选、核心表不膨胀 |
| 邀请码等配置 | 新建 `conduct_class_config` 表，不侵入核心 classes 表 | 德育特有配置自管 |
| 学校 RBAC | 合入 edu-cloud capabilities 矩阵 | 统一权限管理 |
| 小组功能 | 保留 | 用户明确要求 |
| 优先级 | 家长端优先 | 用户明确要求 |

### 不做的事

- 品德评语 / 综合素质评价（后续迭代）
- 微信登录（后续迭代）
- 行为规范档案 / 家校沟通通知推送（后续迭代）
- class-points 云端数据迁移（用户明确暂不处理）
- parent_admin 角色（取消，班主任直接管理家长）

---

## §1 数据模型

所有 conduct 表通过 Alembic 迁移创建，不侵入 edu-cloud 核心表。

### 新增表（8 张）

#### student_profiles — 学生 PII 扩展

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| student_id | UUID | FK → students.id, UNIQUE | 一对一关联 |
| avatar | VARCHAR(10) | | emoji 头像 |
| birth_date | DATE | nullable | 出生日期 |
| ethnicity | VARCHAR(20) | nullable | 民族 |
| id_card_number | TEXT | nullable | AES-256-GCM 加密 |
| blood_type | VARCHAR(5) | nullable | |
| health_notes | TEXT | nullable | 健康备注 |
| home_address | TEXT | nullable | 家庭地址 |
| emergency_contact_name | VARCHAR(50) | nullable | |
| emergency_contact_phone | VARCHAR(20) | nullable | |
| verify_code | TEXT | nullable | AES 加密，家长绑定验证码原文 |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

#### conduct_class_config — 班级德育配置

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| class_id | UUID | FK → classes.id, UNIQUE | |
| invite_code | VARCHAR(10) | UNIQUE | 家长邀请码，6 位大写字母+数字 |
| verify_code_type | VARCHAR(10) | DEFAULT 'id_card' | id_card / phone / custom |
| required_parent_fields | JSON | nullable | 注册时必填字段列表 |
| is_active | BOOLEAN | DEFAULT true | 是否启用德育 |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

#### conduct_rule_categories — 班规分类

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | VARCHAR(50) | | 分类名（如"课堂表现""纪律"） |
| class_id | UUID | FK → classes.id, nullable | 班级级规则 |
| school_id | UUID | FK → schools.id, nullable | 校级规则 |
| scope | VARCHAR(10) | | class / school |
| sort_order | INTEGER | DEFAULT 0 | |
| created_at | TIMESTAMP | | |

#### conduct_rule_items — 班规子项

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | VARCHAR(100) | | 规则名（如"+1 主动举手发言"） |
| points | INTEGER | | 正数加分，负数扣分 |
| category_id | UUID | FK → conduct_rule_categories.id | |
| sort_order | INTEGER | DEFAULT 0 | |

#### conduct_records — 积分记录

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| student_id | UUID | FK → students.id | |
| class_id | UUID | FK → classes.id | 冗余，方便按班查询 |
| points | INTEGER | | 加减分值 |
| reason | TEXT | | 原因说明 |
| date | DATE | | 记录日期 |
| operator_id | UUID | FK → users.id | 操作人 |
| source | VARCHAR(10) | DEFAULT 'manual' | manual / import / batch |
| rule_item_id | UUID | FK → conduct_rule_items.id, nullable | 关联班规 |
| semester_id | UUID | FK → conduct_semesters.id, nullable | |
| created_at | TIMESTAMP | | |

#### conduct_groups — 小组

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | VARCHAR(50) | | 小组名 |
| class_id | UUID | FK → classes.id | class_id + name UNIQUE |
| avatar | VARCHAR(10) | | emoji 头像 |
| created_at | TIMESTAMP | | |

#### conduct_group_members — 小组成员

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| student_id | UUID | FK → students.id | student_id + group_id UNIQUE |
| group_id | UUID | FK → conduct_groups.id | |
| joined_at | TIMESTAMP | | |

#### conduct_semesters — 学期

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | VARCHAR(50) | | 如"2025-2026 第二学期" |
| school_id | UUID | FK → schools.id, nullable | 校级学期 |
| class_id | UUID | FK → classes.id, nullable | 班级级学期 |
| start_date | DATE | | |
| end_date | DATE | | |
| is_current | BOOLEAN | DEFAULT false | |
| created_at | TIMESTAMP | | |

### 不新增的表

| 原 class-points 表 | 处理方式 |
|---|---|
| users | 复用 edu-cloud `users` |
| classes | 复用 edu-cloud `classes` |
| schools | 复用 edu-cloud `schools` |
| class_members | 复用 edu-cloud `user_roles` + `guardian_student_links` |
| parent_profiles | 不单独建表，parent 的 phone/display_name 用 users 表 |
| school_roles / school_members | 合入 edu-cloud capabilities 矩阵 |

---

## §2 权限与角色映射

### 新增 Permission（5 个）

| Permission | 说明 | 默认拥有的角色 |
|---|---|---|
| `VIEW_CONDUCT` | 查看积分、排行榜 | homeroom_teacher, subject_teacher, grade_leader, academic_director, principal, parent |
| `MANAGE_CONDUCT` | 加减分、批量操作、删除记录 | homeroom_teacher, subject_teacher, grade_leader, academic_director |
| `MANAGE_CONDUCT_RULES` | 管理班规分类和子项 | homeroom_teacher, academic_director |
| `MANAGE_CONDUCT_PARENTS` | 管理家长账号、审核绑定、配置邀请码 | homeroom_teacher |
| `EXPORT_CONDUCT` | 导出积分 Excel/PDF | homeroom_teacher, grade_leader, academic_director |

### 角色映射

| class-points 原角色 | edu-cloud 映射 | 权限范围 |
|---|---|---|
| Class.owner_id（班主任） | `homeroom_teacher` | 本班全部 conduct 权限 |
| ClassMember.role=teacher（科任） | `subject_teacher` | VIEW_CONDUCT + MANAGE_CONDUCT（仅加减分） |
| ClassMember.role=parent | `parent` 角色 + `guardian_student_links` | VIEW_CONDUCT（仅看自己孩子） |
| ClassMember.role=parent_admin | 取消，班主任直接管理 | — |
| SchoolRole（校级角色） | `capabilities` 矩阵 | 按学校配置 |

### 数据权限过滤

复用 edu-cloud 现有 scope filter 机制：
- **homeroom_teacher**：`class_ids` 限定本班
- **subject_teacher**：`class_ids` 限定任教班级
- **grade_leader**：`grade_ids` 限定本年级所有班
- **parent**：通过 `guardian_student_links` 限定已绑定的孩子

### 模块开关

`school_modules` 新增 code `conduct`。学校未启用时，侧栏不显示、API 返回 403。

---

## §3 家长注册与绑定流程

### 整体流程

```
班主任设置邀请码 → 家长拿到邀请码 → 注册账号 → 登录 → 绑定孩子 → 进入家长端
```

### Step 1：班主任配置

班主任在班级设置页开启德育模块后自动生成：
- `invite_code`（6 位随机码，可刷新）
- `verify_code_type`（默认 id_card，可切换为 phone / custom）

如果选 custom，班主任需为每个学生设置自定义验证码。

### Step 2：家长注册

家长访问 `/parent/register?code=XXXXXX`

1. 输入邀请码（或从 URL 自动填充）→ 后端校验有效性，返回班级名称
2. 填写注册信息：
   - 姓名（display_name，必填）
   - 手机号（phone，必填，作为登录用户名）
   - 设置密码（必填）
   - 班主任配置的额外必填字段（required_parent_fields）
3. 后端创建 `users` 记录 + `user_roles(role=parent, school_id=班级所属学校)`
4. 返回 JWT token，自动登录

手机号唯一约束：同一手机号已注册 → 提示"该手机号已注册，请直接登录"。

### Step 3：家长登录

家长访问 `/parent/login`，手机号 + 密码登录，返回 JWT。

### Step 4：绑定孩子

首次登录后进入绑定页面：

1. 显示家长关联的班级（通过注册时邀请码对应的班级）
2. 输入孩子姓名
3. 验证身份（根据 verify_code_type）：
   - `id_card`：输入孩子身份证后 6 位（**Option A 锁定契约 / N001 防退化 sentinel**：后端比对 `decrypt(id_card_number)[-6:] == verify_code`，严禁退化为整串相等——整串比对会让完整身份证号在输入流量中以明文出现，违反 Option A 授权边界）
   - `phone`：输入班主任预设的手机号（F005 Option A：phone 与 custom 共享 `profile.verify_code` 字段）
   - `custom`：输入班主任预设的验证码
4. 验证通过 → 创建 `guardian_student_links`（guardian_user_id, student_id, relationship）
5. relationship：父亲 / 母亲 / 其他（注册时选）

一个家长可绑定多个孩子（同班或不同班），每次走一次验证。

### Step 5：进入家长端

绑定完成后进入 `/parent/` 主页，看到已绑定孩子的积分概览。

---

## §4 后端 API

### 模块结构

```
src/edu_cloud/modules/conduct/
├── __init__.py
├── models.py            # 8 张表的 ORM 定义
├── router.py            # API 路由入口，挂载子路由
├── schemas.py           # Pydantic 请求/响应模型
├── service.py           # 积分、排行、小组业务逻辑
├── rules_service.py     # 班规管理
├── parent_service.py    # 家长注册、绑定、家长端查询
├── export_service.py    # Excel/PDF 导出
├── crypto.py            # AES-256-GCM 加密（从 class-points 迁移）
└── permissions.py       # conduct 权限检查辅助函数
```

### API 端点（约 35 个）

#### 家长端认证（优先实现）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/v1/conduct/parent/register` | 公开（需有效邀请码） | 家长注册 |
| POST | `/api/v1/conduct/parent/login` | 公开 | 手机号+密码登录 |
| GET | `/api/v1/conduct/parent/me` | parent | 获取当前家长信息+已绑定孩子 |
| POST | `/api/v1/conduct/parent/bind` | parent | 绑定孩子（需验证） |
| GET | `/api/v1/conduct/invite/{code}/info` | 公开 | 校验邀请码，返回班级名 |

#### 家长端查询

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/conduct/parent/children` | parent | 已绑定孩子列表+积分汇总 |
| GET | `/api/v1/conduct/parent/children/{student_id}/records` | parent | 孩子积分明细 |
| GET | `/api/v1/conduct/parent/children/{student_id}/rankings` | parent | 班级排行（孩子高亮） |
| GET | `/api/v1/conduct/parent/classes/{class_id}/rules` | parent | 查看班规 |
| PUT | `/api/v1/conduct/parent/profile` | parent | 修改个人信息 |
| PUT | `/api/v1/conduct/parent/password` | parent | 修改密码 |

#### 积分管理（管理端）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/v1/conduct/classes/{id}/records` | MANAGE_CONDUCT | 加减分 |
| POST | `/api/v1/conduct/classes/{id}/records/batch` | MANAGE_CONDUCT | 批量加减分 |
| GET | `/api/v1/conduct/classes/{id}/records` | VIEW_CONDUCT | 积分记录列表（分页+筛选） |
| DELETE | `/api/v1/conduct/classes/{id}/records/{rid}` | MANAGE_CONDUCT | 删除记录 |
| POST | `/api/v1/conduct/classes/{id}/records/import` | MANAGE_CONDUCT | Excel 导入积分 |
| GET | `/api/v1/conduct/classes/{id}/rankings/students` | VIEW_CONDUCT | 学生排行榜 |
| GET | `/api/v1/conduct/classes/{id}/rankings/groups` | VIEW_CONDUCT | 小组排行榜 |

#### 班规管理

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/conduct/classes/{id}/rules` | VIEW_CONDUCT | 班规列表 |
| POST | `/api/v1/conduct/classes/{id}/rules/categories` | MANAGE_CONDUCT_RULES | 新增分类 |
| PUT | `/api/v1/conduct/classes/{id}/rules/categories/{cid}` | MANAGE_CONDUCT_RULES | 编辑分类 |
| DELETE | `/api/v1/conduct/classes/{id}/rules/categories/{cid}` | MANAGE_CONDUCT_RULES | 删除分类 |
| POST | `/api/v1/conduct/classes/{id}/rules/categories/{cid}/items` | MANAGE_CONDUCT_RULES | 新增子项 |
| PUT | `/api/v1/conduct/classes/{id}/rules/categories/{cid}/items/{iid}` | MANAGE_CONDUCT_RULES | 编辑子项 |
| DELETE | `/api/v1/conduct/classes/{id}/rules/categories/{cid}/items/{iid}` | MANAGE_CONDUCT_RULES | 删除子项 |

#### 小组管理

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/conduct/classes/{id}/groups` | VIEW_CONDUCT | 小组列表 |
| POST | `/api/v1/conduct/classes/{id}/groups` | MANAGE_CONDUCT | 创建小组 |
| DELETE | `/api/v1/conduct/classes/{id}/groups/{gid}` | MANAGE_CONDUCT | 删除小组 |
| POST | `/api/v1/conduct/classes/{id}/groups/{gid}/members` | MANAGE_CONDUCT | 添加成员 |
| DELETE | `/api/v1/conduct/classes/{id}/groups/{gid}/members/{sid}` | MANAGE_CONDUCT | 移除成员 |

#### 班级配置 + 家长管理（班主任）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/conduct/classes/{id}/config` | MANAGE_CONDUCT_PARENTS | 获取德育配置 |
| PUT | `/api/v1/conduct/classes/{id}/config` | MANAGE_CONDUCT_PARENTS | 更新配置 |
| POST | `/api/v1/conduct/classes/{id}/config/regenerate-code` | MANAGE_CONDUCT_PARENTS | 刷新邀请码 |
| GET | `/api/v1/conduct/classes/{id}/parents` | MANAGE_CONDUCT_PARENTS | 已注册家长列表 |
| DELETE | `/api/v1/conduct/classes/{id}/parents/{uid}` | MANAGE_CONDUCT_PARENTS | 移除家长绑定 |

#### 导出

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/conduct/classes/{id}/export/records` | EXPORT_CONDUCT | 导出积分 Excel |
| GET | `/api/v1/conduct/classes/{id}/export/rankings` | EXPORT_CONDUCT | 导出排行榜 Excel |
| GET | `/api/v1/conduct/classes/{id}/export/student/{sid}/report` | EXPORT_CONDUCT | 学生积分报告 PDF |

#### 学期管理

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/conduct/classes/{id}/semesters` | VIEW_CONDUCT | 学期列表 |
| POST | `/api/v1/conduct/classes/{id}/semesters` | MANAGE_CONDUCT_RULES | 创建学期 |
| PUT | `/api/v1/conduct/classes/{id}/semesters/{sid}/activate` | MANAGE_CONDUCT_RULES | 激活学期 |

---

## §5 前端页面与路由

### 布局策略

- 管理端（教师）：挂在 `AppShell` 下，复用已有侧栏和顶栏
- 家长端：新增 `ParentLayout`，独立导航结构

### 新增文件

```
frontend/src/
├── layouts/
│   └── ParentLayout.vue         # 新增，家长端布局
├── pages/
│   ├── conduct/                  # 新增，管理端德育页面
│   │   ├── ConductDashboard.vue
│   │   ├── ConductPoints.vue
│   │   ├── ConductRules.vue
│   │   ├── ConductRankings.vue
│   │   ├── ConductRecords.vue
│   │   ├── ConductGroups.vue
│   │   ├── ConductSettings.vue
│   │   ├── ConductExport.vue
│   │   └── ConductParents.vue
│   └── parent/                   # 新增，家长端页面
│       ├── ParentLogin.vue
│       ├── ParentRegister.vue
│       ├── ParentBind.vue
│       ├── ParentOverview.vue
│       ├── ParentDetails.vue
│       ├── ParentRankings.vue
│       ├── ParentRules.vue
│       └── ParentProfile.vue
├── api/
│   └── conduct.js               # 新增，conduct API 模块
└── config/
    └── sidebarConfig.js          # 修改，追加德育导航项
```

### 路由定义

管理端（AppShell 子路由）：
- `/conduct` — 德育概览
- `/conduct/points` — 积分操作
- `/conduct/rules` — 班规管理
- `/conduct/rankings` — 排行榜
- `/conduct/records` — 积分记录
- `/conduct/groups` — 小组管理
- `/conduct/settings` — 德育设置
- `/conduct/export` — 数据导出
- `/conduct/parents` — 家长管理

家长端（ParentLayout）：
- `/parent/login` — 家长登录（无需 ParentLayout）
- `/parent/register` — 家长注册（无需 ParentLayout）
- `/parent` — 积分概览
- `/parent/bind` — 绑定孩子
- `/parent/details` — 详细信息
- `/parent/rankings` — 排行榜
- `/parent/rules` — 班规查看
- `/parent/profile` — 个人中心

### 侧栏导航

`sidebarConfig.js` 追加德育分组，`moduleCode: 'conduct'`：

**homeroom_teacher（班主任）** — 全部 9 项
**subject_teacher（科任）** — 积分操作 + 排行榜
**grade_leader / academic_director** — 概览 + 排行 + 导出

### ParentLayout 设计

- 顶栏：logo + 当前孩子切换（多孩子时下拉选择）+ 个人中心
- 底部 tab 导航（移动端优先）：概览 / 排行 / 班规 / 我的
- 无侧栏，页面简洁

---

## §6 Agent 工具

### 新增工具（6 个）

注册在 `src/edu_cloud/ai/tools/conduct.py`：

| 工具名 | 域 | risk | 说明 |
|---|---|---|---|
| `get_conduct_rankings` | L2_conduct | low | 班级/年级积分排行榜，支持学期筛选 |
| `get_student_conduct_summary` | L6_profile | low | 单个学生积分汇总：总分、分类统计、趋势 |
| `get_conduct_records` | L2_conduct | low | 积分记录查询（按学生/日期/分类筛选） |
| `add_conduct_points` | L2_conduct | medium | 给学生加减分（需指定学生、分值、原因） |
| `get_conduct_rules` | L2_conduct | low | 班规分类和子项查询 |
| `get_class_conduct_overview` | L2_conduct | low | 班级德育概览：总人数、本周统计、异常学生 |

### 权限控制

- 所有工具绑定 `module_code: "conduct"`（学校未启用则不可见）
- `add_conduct_points` 需要 `MANAGE_CONDUCT` 权限
- 查询类工具对 parent 角色开放，通过 DataScope 限定已绑定的孩子

---

## §7 实现优先级

按用户要求，家长端优先：

1. **Phase 1：数据基础 + 家长端**
   - Alembic 迁移（8 张表）
   - Permission enum 扩展 + 模块开关
   - 家长注册/登录/绑定 API
   - 家长端查询 API
   - ParentLayout + 家长端 6 页面
   - 班主任邀请码配置页

2. **Phase 2：管理端**
   - 积分加减分 + 批量操作 API
   - 班规管理 API
   - 小组管理 API
   - 管理端 9 页面
   - 侧栏导航集成

3. **Phase 3：导出 + Agent**
   - Excel/PDF 导出
   - 学期管理
   - 6 个 Agent 工具
   - 积分导入（Excel）
