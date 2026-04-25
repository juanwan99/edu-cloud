---
baseline_command: "cd ~/projects/edu-cloud && uv run python -m pytest --collect-only -q"
baseline_verified_at: "2026-04-25 00:55"
baseline_count: 2187
---

# T3-03 MANAGE_GRADING 权限回收 design

<!-- key-start -->
## 0. 任务卡

| 项 | 值 |
|---|---|
| Topic | manage-grading-revoke |
| 父任务 | edu-deep-scan §11.1 D-02（codex 共识 D-02 > D-01 优先） |
| 触发 | 用户裁定 2026-04-25 接受 codex 排序；D-03 alembic spike 后跟进（schema 稳后改权限 safer） |
| 范围 | edu-cloud `core/permissions.py` + 前端 sidebar/permission-aware 渲染 + 测试矩阵 |
| 形态 | brainstorming 产物（design 草稿）；等 approve 后 writing-plans → 独立会话 executing |
| 自治边界 | 本会话仅 design；不动代码、不写 plan |
| 前置 | T3-02 alembic drift spike 完成（schema 稳） |
<!-- key-end -->

### 0.1 现状证据（已 verify @ 2026-04-25）

`/home/ops/projects/edu-cloud/src/edu_cloud/core/permissions.py`：
- `:61` `MANAGE_GRADING = "manage_grading"  # 阅卷分配/调度 → 教务`
- `:82-89` `_TEACHER_BASE = { ..., Permission.MANAGE_GRADING, ... }` ← **基类含此权限**
- `:126`、`:159`、`:188` 角色定义中包含 MANAGE_GRADING
- `:241-243` `lesson_prep_leader = _TEACHER_BASE - {VIEW_CONDUCT,MANAGE_CONDUCT} | {MANAGE_GRADING, ...}`
- `:248` `homeroom_teacher = _TEACHER_BASE | {...}`
- `:258` `subject_teacher = _TEACHER_BASE.copy()` ← **普通任课教师继承全部**

**问题**：subject_teacher / homeroom_teacher / lesson_prep_leader 全部继承 MANAGE_GRADING，超出 MEMORY 明示设计意图（"应仅教务+备课组长"）。

### 0.2 MEMORY 锚点

`~/.claude/projects/-home-ops/memory/project_grading_permission_temp.md`：
> _TEACHER_BASE 临时含 MANAGE_GRADING；上线前须收回到教务+备课组长。

---

## 1. 设计目标

**核心**：把 MANAGE_GRADING 从 `_TEACHER_BASE` 拿掉；仅以下角色显式声明：
- `lesson_prep_leader`（备课组长，已显式）
- `homeroom_teacher`（班主任）
- `教务` 角色（grade_master / academic_admin，待对照）

**非目标**：
- ❌ 重写整个 RBAC 体系
- ❌ 改 audit_logs 写入逻辑（D-20 是独立 T3）
- ❌ 改 school_id 多租户 scope（不在 D-02 范围）

---

## 2. 设计

### 2.1 后端改动

```python
# src/edu_cloud/core/permissions.py
# 改前
_TEACHER_BASE: set[Permission] = {
    ...,
    Permission.MANAGE_GRADING,  # 临时扩大，应收回
    ...,
}

# 改后
_TEACHER_BASE: set[Permission] = {
    ...,
    # MANAGE_GRADING 已收回 @ 2026-04-25 T3-03，仅备课组长/班主任/教务显式声明
    ...,
}

# 角色定义中显式加回
lesson_prep_leader = _TEACHER_BASE | {Permission.MANAGE_GRADING, ...}  # 已含
homeroom_teacher = _TEACHER_BASE | {Permission.MANAGE_GRADING, ...}    # 新增
academic_admin = _ACADEMIC_BASE | {Permission.MANAGE_GRADING, ...}     # 新增（如已存在则 idempotent）
```

### 2.2 前端改动

`frontend/src/config/permissions.js` + `frontend/src/config/sidebarConfig.js`：
- 已基于 permissions 动态渲染 sidebar（最近 commit 7df3185 "T3 sidebar 按 permissions 派生"）
- subject_teacher 失去 MANAGE_GRADING → "阅卷分配" 菜单不再渲染
- 测试需更新：`AppSidebar.subject_teacher.test.js` 断言不含此菜单项

`frontend-nuxt/` 同步（如已有 sidebar 实现）。

### 2.3 测试矩阵

| 角色 | MANAGE_GRADING 应有？ | 测试用例 |
|---|---|---|
| platform_admin | ✅ | `test_permission_platform_admin_has_manage_grading` |
| school_admin | ✅ | 同 |
| academic_admin / 教务 | ✅ | `test_permission_academic_admin_has_manage_grading` |
| lesson_prep_leader | ✅ | `test_permission_lesson_prep_leader_has_manage_grading` |
| homeroom_teacher | ✅ | `test_permission_homeroom_teacher_has_manage_grading` |
| **subject_teacher** | ❌ | `test_permission_subject_teacher_no_manage_grading`（**新增，断言不含**） |
| guardian | ❌ | 同 |
| student | ❌ | 同 |

### 2.4 数据迁移评估

`user_roles` 表 337 行（已 verify P4）。无 schema 改动，仅 permissions.py 代码改。但需评估：
- 已部署的生产 user_roles 中是否有"subject_teacher 用户"在跑 MANAGE_GRADING 操作？
- `audit_logs` 查最近 N 天 manage_grading 端点调用方角色分布

---

## 3. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 已存在用户依赖 subject_teacher 的 MANAGE_GRADING | 业务中断 | 上线前查 audit_logs 评估实际使用；需要时给该用户加 lesson_prep_leader 角色 |
| 前端 sidebar 渲染依赖：测试覆盖不足 | UI 报错 / 死链 | 测试矩阵加 subject_teacher 渲染断言 |
| schema 不稳（T3-02 未完成） | drift 与权限改动交互 | T3-03 必须在 T3-02 后启动 |

---

## 4. 实施步骤（写 plan 用）

| 阶段 | 动作 |
|---|---|
| **S1** 现状审计 | 查 audit_logs，列 subject_teacher 用户调用 MANAGE_GRADING 端点的次数（防直接破坏生产）|
| **S2** 测试 first（TDD） | 写 8 个权限矩阵测试（含 subject_teacher 断言不含）|
| **S3** 后端改 | permissions.py 调整 _TEACHER_BASE + homeroom_teacher / academic_admin 显式加回 |
| **S4** 前端测试 | sidebar 渲染测试加 subject_teacher 不含"阅卷分配"|
| **S5** 前端改 | 如有硬编码角色判断（非 permissions 驱动）调整 |
| **S6** 集成测试 | 全量 pytest + vitest |
| **S7** Audit 上线评估 | 是否需先给个别用户加 lesson_prep_leader 角色 |
| **S8** 部署 | edu-cloud 重启 + nginx flush（无 schema 改动，无需 alembic）|

---

## 5. 验收标准

- [ ] permissions.py `_TEACHER_BASE` 不含 MANAGE_GRADING
- [ ] 8 个权限矩阵测试 pass
- [ ] subject_teacher 角色用户无法访问 `/api/grading/assignments/*` 等端点（403）
- [ ] 前端 sidebar 测试通过
- [ ] 全量 pytest ≥ 2187 passed
- [ ] audit_logs 验：上线后 24h 内 subject_teacher 调用 MANAGE_GRADING 端点 = 0

---

## 6. 与其他 T3 的关系

- **T3-02** alembic drift spike → 必须先完成（前置）
- **D-20** MANAGE_GRADING audit coverage → 独立 T3，与本任务并行
- **D-01 / T3-12** 前端战略 → frontend-nuxt sidebar 同步实现影响范围（如已有 sidebar 实现，本任务覆盖；否则推到 T3-12）

---

**T3-03 design 草稿 v0 完 @ 2026-04-25**
**等 approve 进 writing-plans；执行必须独立新会话**
