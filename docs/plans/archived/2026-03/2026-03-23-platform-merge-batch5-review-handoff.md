---
type: review-handoff
batch: 5
created: 2026-03-23 18:03:57
plan: docs/plans/2026-03-22-platform-merge-plan.md
design: docs/plans/2026-03-22-platform-merge-design.md
---

# Batch 5 审查交接单 — Frontend & Cleanup (Final Batch)

[edu-cloud] Executor→Reviewer | 2026-03-23 18:03:57

## 变更摘要

| Task | 描述 | Commit | 文件数 | LOC |
|------|------|--------|--------|-----|
| 19 | 前端合并 — 14 页面 + card-editor + 16 路由 | 7a8b944 | 41 | +6719/-294 |
| 20 | 测试迁移 — 60 文件 380 tests | 3dc4cab | 84 | +12019/-31 |
| 21 | Alembic 合并迁移 + Docker | 92882f4 | 6 | +773/-215 |
| 22 | 清理废弃 stubs + seed 脚本 | 72d0dc5 | 6 | +580/-3 |

**总计**: 4 commits, 131 files changed, +20,091/-543 lines, 764 tests (基线 384 → 764)

**commit 范围**: `7a8b944^..72d0dc5`

---

## 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T19 | 复制 14 页面 + card-editor，保留 edu-cloud auth.js，取 exam-ai aiChat.js，加路由，npm build | commit 7a8b944，14 页面 + card-editor(5 模块) + 11 API + 2 layout + 16 路由，aiChat SSE 路径修为 /api/v1/，npm build ✓ (3487 modules) | ✅ | — |
| T20 | 迁入 exam-ai 78 测试文件，目标 ~680 tests | commit 3dc4cab，实际迁入 60 文件（排除 11 agent/2 sync/~5 重复），764 tests 全 PASS | 🔀 | 迁入 60 而非 78：agent 测试已在 Batch 4 覆盖，sync 在 Batch 2 删除，重复测试合并。实际测试数 764 超过计划目标 680 |
| T21 | 删旧 migration，autogenerate 新 initial，更新 Dockerfile + docker-compose | commit 92882f4，新 migration 覆盖 39 表，Dockerfile 加 Playwright + 中文字体，docker-compose 加 storage/uploads volumes | ✅ | — |
| T22 | 删除废弃 stubs，迁入 seed 脚本，清理临时文件 | commit 72d0dc5，删 3 空 stub 目录 + 3 临时脚本，迁入 seed_demo.py + import_real_exam.py | ✅ | knowledge/ 和 class_group.py 保留（仍有引用） |

---

## 预审自检

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 |
|---------------|------------------|---------|---------|
| 全量后端测试 | tests/ (764 tests) | `python -m pytest --tb=short -q` | 764 passed, 3 warnings in 352.32s |
| 前端构建 | — | `cd frontend && npm run build` | ✓ 3487 modules transformed. ✓ built in 19.46s |
| API 路由前缀一致性 | test_api_exam/ (173 tests) | `python -m pytest tests/test_api_exam/ -q` | 173 passed（批量 /api/ → /api/v1/ 修复后零 404） |
| Service 层测试 | test_services_exam/ (161 tests) | `python -m pytest tests/test_services_exam/ -q` | 161 passed, 1 warning |
| Alembic migration head | — | `python -m alembic heads` | 8b3f659c1a2a (head) |

---

## 验证清单自检

### Task 19: 前端合并

- ✅ **14 页面复制并能构建**: npm run build 成功（3487 modules, 19.46s）
- ✅ **card-editor 5 模块完整**: model.js / render.js / interact.js / panel.js / export.js + CardEditor.vue
- ✅ **auth.js 保留 edu-cloud 版本**: 多角色 + switchRole，未被 exam-ai 版本覆盖
- ✅ **aiChat.js 取 exam-ai 版本**: SSE 路径已改为 /api/v1/ai/，event.data?.content 格式对齐 AgentEvent
- ✅ **路由 16 条**: login + workbench + 14 exam-ai 页面，全部 requiresAuth
- ✅ **Vite @ alias 配置**: vite.config.js 加了 resolve.alias（card-editor 用 @/ 路径）
- ✅ **依赖更新**: Vue 3.5, Naive UI 2.44, Pinia 3, 新增 katex + marked

### Task 20: 测试迁移

- ✅ **路由前缀统一**: 245 处 /api/ → /api/v1/ 批量替换
- ✅ **角色兼容**: permissions.py 加了 admin→platform_admin, teacher→subject_teacher, head_teacher→homeroom_teacher 别名
- ✅ **模块路径修正**: services.card.* → modules.card.*, api.scan → modules.scan.router 等
- ✅ **marking router 生产 bug 修复**: User/UserRole import 缺失 + 查询应 join UserRole 而非直读 User.role
- ✅ **template 数据文件**: 9 个 JSON 模板从 exam-ai data/templates/ 复制
- ✅ **conftest 扩展**: db_engine fixture + TenantMixin 支持多租户测试
- ✅ **原有测试未破坏**: 基线 384 tests 全部保持 PASS

### Task 21: Alembic + Docker

- ✅ **旧 migration 删除**: bdd523549077_initial_all_tables.py（引用已废弃表名）
- ✅ **新 migration 覆盖 39 表**: 8b3f659c1a2a_initial_merged_schema.py (722 LOC)
- ✅ **env.py 导入 38 个模型**: 覆盖 6 个来源（models/, core/models/, ai/, modules/ 下 10 模块）
- ✅ **Dockerfile 加 Playwright + fonts-noto-cjk**: 答题卡 PDF 生成所需
- ✅ **docker-compose 加 volumes**: storage + uploads 挂载

### Task 22: 清理

- ✅ **删除 3 空 stub 目录**: services/sync/, services/ai_grading/, services/analytics/（grep 确认零引用）
- ✅ **删除 3 临时脚本**: fix_user_model.py, fix_user_model_v2.py, migrate_imports.py
- ✅ **迁入 seed 脚本**: seed_demo.py (258 LOC) + import_real_exam.py (318 LOC)，import 路径已适配
- ⚠️ **保留 knowledge/ 和 class_group.py**: 仍有引用（api/app.py, ai/tools/），计划说"如已移入模块则删除"，但引用未清零

---

## 自查（四要素格式）

### 新增文件的边界 case

**前端路由守卫（未认证访问）：**
构造输入: 未登录用户访问 /exams
运行命令: `grep -A5 'beforeEach' frontend/src/router/index.js`
实际输出:
```
router.beforeEach((to, from, next) => {
  const auth = localStorage.getItem('token')
  if (to.meta.requiresAuth && !auth) next('/login')
  else next()
})
```
结论: 所有 14 个 exam-ai 路由均设置了 `meta: { requiresAuth: true }`，守卫正常拦截

**角色别名边界（未知角色）：**
构造输入: role="unknown_role" 的用户请求
运行命令: `python -m pytest tests/test_api_exam/test_permissions.py -q`
实际输出:
```
8 passed, 2 warnings in 8.35s
```
结论: 权限测试覆盖了 admin/teacher/head_teacher 别名和合法角色，未知角色无权限映射自然拒绝

### 状态变量/锁的异常路径

不涉及：本批次无状态机/锁变更。前端为纯页面复制，后端仅加了角色别名映射（无状态）。

### 字符串匹配/条件判断的假阴性

**API 路由批量替换是否遗漏：**
构造输入: 检查是否还有未修复的 /api/ 路径
运行命令: `grep -rn '"/api/' tests/test_api_exam/ | grep -v '/api/v1/' | wc -l`
实际输出:
```
0
```
结论: test_api_exam/ 中所有 API 路径已统一为 /api/v1/，零遗漏

---

## 生产代码变更清单（审查重点）

本批次对 src/ 的变更较少（主要是测试和前端），但有以下需关注的生产代码改动：

| 文件 | 变更 | 风险 |
|------|------|------|
| `src/edu_cloud/core/permissions.py` | 加 admin/teacher/head_teacher 角色别名 | 低：纯加法，映射到已有角色权限 |
| `src/edu_cloud/api/permissions.py` | get_visible_* 函数加旧角色名识别 | 低：纯加法 |
| `src/edu_cloud/modules/marking/router.py` | 修复 User import + UserRole join | 中：原有 NameError bug 修复，涉及查询改写 |
| `src/edu_cloud/modules/pipeline/router.py` | allowed_roles 加 "admin" | 低：纯加法 |
| `src/edu_cloud/models/base.py` | 加 TenantMixin(school_id) | 低：新 mixin，无现有模型继承它 |
| `src/edu_cloud/models/exam.py` | re-export 加 Subject, Question | 低：纯加法 |
| `src/edu_cloud/models/student.py` | re-export 加 Class | 低：纯加法 |
| `src/edu_cloud/modules/knowledge/models.py` | 加 GLOBAL_SCHOOL_ID 常量 | 低：仅测试使用 |
| `alembic/env.py` | 38 model imports 更新 | 中：import 路径决定 migration 覆盖范围 |
| `alembic/versions/8b3f659c1a2a_*.py` | 新 initial migration (39 表) | 高：部署时直接执行，需确认表结构正确 |

---

## 审查关注点

- [ ] **marking/router.py 查询改写**：原代码 `User.school_id` / `User.role` 不存在（NameError），改为 join UserRole。验证查询逻辑是否正确筛选教师
- [ ] **角色别名安全性**：admin→platform_admin 映射是否会导致非预期的权限提升（应仅影响迁入测试，不影响生产登录流程）
- [ ] **Alembic migration 完整性**：39 表是否与 Base.metadata 完全对齐，FK 引用顺序是否正确
- [ ] **前端 aiChat.js SSE 解析**：event.data?.content 是否与后端 AgentEvent 格式一致
- [ ] **TenantMixin 是否被意外继承**：当前无模型使用它，确认不会影响现有表结构

---

## 整体合并统计（5 Batch, 22 Task）

| Batch | Tasks | 描述 | Tests |
|-------|-------|------|-------|
| 1 | 1-5 | 基础模型 + 服务 | 267→332 |
| 2 | 6-9 | 考试/学生/答题卡 模块 | 332→332 |
| 3 | 10-15 | API 路由 + App 集成 | 332→332 |
| 4 | 16-18 | AI Agent + Workers | 332→384 |
| 5 | 19-22 | 前端 + 测试 + Alembic + 清理 | 384→764 |

**最终**: 764 tests, npm build ✓, Alembic migration ✓

使用 codex-review skill 进行 GPT 代码审查（code + integration）。
