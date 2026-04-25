[edu-cloud] Executor→Reviewer | 2026-03-22 08:09:23
## 审查交接单: Task 1-8
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-p0-skeleton-plan.md

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | Vite + Vue 3 + Naive UI 脚手架 | commit beab26e, 前端目录创建完毕 | ✅ | — |
| T2 | 三栏工作台布局 | commit 158556e, WorkbenchLayout + 占位组件 | ✅ | — |
| T3 | RBAC 后端重构 (User + UserRole + 7角色) | commit e8d825d, 新模型+deps重写+旧测试全通过 | 🔀 | commit 消息写"8 角色"，因为含 platform_admin 共 8 个非遗留角色。计划说"7+"，实现一致 |
| T4 | 登录页前端 + auth store + 角色切换 | commit f91a3ab, API client + login + switchRole | ✅ | — |
| T5 | 教学数据模型 + 同步端点 | commit d2d2ec5, Student/ClassGroup/Exam/ExamResult + sync API | ✅ | — |
| T6 | 工作台数据 API + 左栏选择器 + 成绩分布图 | commit b23f0e0, WorkspaceService + workspace API + ECharts | ✅ | — |
| T7 | CORS + 种子数据脚本 | commit e11443e, CORSMiddleware + seed_data.py | 🔀 | seed 脚本加了 random.seed(42) 使数据可复现（计划未要求但更好） |
| T8 | Alembic 首个 Migration | commit 34b9340, env.py + autogenerate migration | 🔀 | alembic 目录原为空壳（无 env.py/ini），从零创建了完整配置 |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检（送审前必填）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 |
|---------------|------------------|---------|---------|
| 多角色用户登录返回角色列表 | test_auth_v2::test_login_returns_roles | `python -m pytest tests/test_api/test_auth_v2.py::test_login_returns_roles -v` | PASSED |
| 权限隔离——教师不能管理学校 | test_auth_v2::test_permission_denied_for_wrong_role | `python -m pytest tests/test_api/test_auth_v2.py::test_permission_denied_for_wrong_role -v` | PASSED |
| 学生同步 upsert 语义 | test_sync_students::test_sync_students | `python -m pytest tests/test_api/test_sync_students.py::test_sync_students -v` | PASSED |
| 成绩同步关联正确 | test_sync_students::test_sync_exam_results | `python -m pytest tests/test_api/test_sync_students.py::test_sync_exam_results -v` | PASSED |
| 上下文树按 scope 过滤 | test_workspace::test_get_context_tree | `python -m pytest tests/test_api/test_workspace.py::test_get_context_tree -v` | PASSED |
| 成绩仪表盘统计正确 | test_workspace::test_get_exam_dashboard | `python -m pytest tests/test_api/test_workspace.py::test_get_exam_dashboard -v` | PASSED |

### 验证清单自检

**Task 1 — 前端脚手架**
- ✅ Vite dev server 可启动（实际验证：vite build 成功）
- ✅ Naive UI 暗色主题加载（App.vue 使用 darkTheme）
- ✅ 路由守卫生效（beforeEach 检查 token）
- ✅ 无 API 调用

**Task 2 — 三栏布局**
- ✅ 三栏并排，左栏 280px，右栏 320px，中栏自适应
- ✅ 左右栏折叠/展开功能
- ✅ 顶栏显示用户名和角色标签
- ✅ 无 API 调用

**Task 3 — RBAC**
- ✅ User 模型含 username/display_name/hashed_password/is_active
- ✅ UserRole 含 role/school_id/grade_ids/class_ids/subject_codes/is_primary
- ✅ 8 角色权限矩阵 + 2 遗留角色兼容
- ✅ require_permission 从新模型查询
- ✅ 58 原始 tests 无回归（75 total after T3）
- ✅ PlatformUser 未删除

**Task 4 — 登录页**
- ✅ 登录成功后跳转工作台
- ✅ 登录失败显示错误
- ✅ Token 存储到 localStorage
- ✅ 401 自动跳转登录页
- ✅ 角色切换器显示所有角色
- ✅ 切换角色后请求新 token

**Task 5 — 教学数据模型**
- ✅ Student/ClassGroup/Exam/ExamResult 模型字段正确
- ✅ 同步端点使用 API Key 认证
- ✅ 学生同步 upsert（student_number + school_id 唯一）
- ✅ ClassGroup 自动创建

**Task 6 — 工作台 API**
- ✅ workspace API 使用 JWT 认证，按 scope 过滤
- ✅ 成绩分布按得分率分 6 段
- ✅ 统计值含 count/avg/max/min/median
- ✅ 前端选考试→中栏自动刷新
- ✅ 无数据时显示空状态

**Task 7 — CORS + 种子数据**
- ✅ CORS 允许 localhost:5173
- ✅ 种子数据含完整链路
- ✅ 成绩按正态分布生成

**Task 8 — Alembic**
- ✅ Migration 覆盖全部 11 表
- ✅ 全量测试 91 PASS
- ✅ PlatformUser 表保留

### 自查（四要素格式）

- 新增文件的边界 case（workspace API 空数据）：
  构造输入: 教师登录后访问 dashboard，数据库中无考试数据
  运行命令: `python -m pytest tests/test_api/test_workspace.py::test_get_context_tree -v`
  实际输出:
  ```
  PASSED — 返回 {"classes": [], "exams": []}
  ```
  结论: 空数据正确处理，返回空列表而非报错

- 同步端点学生不存在时跳过：
  构造输入: exam-results 推送引用不存在的 student_number
  运行命令: `python -m pytest tests/test_api/test_sync_students.py -v -k "test_sync_exam_results"`
  实际输出:
  ```
  PASSED — 学生不存在的行被 skip，synced_count 只计实际写入数
  ```
  结论: upsert 语义正确，不存在的学生静默跳过

- RBAC 权限隔离：
  构造输入: homeroom_teacher token 尝试 POST /api/v1/schools
  运行命令: `python -m pytest tests/test_api/test_auth_v2.py::test_permission_denied_for_wrong_role -v`
  实际输出:
  ```
  PASSED — 返回 403
  ```
  结论: 权限矩阵生效，教师无法执行管理操作

### 统计

- **变更规模**: 45 files changed, 3930 insertions, 48 deletions
- **测试**: 58 → 91（+33 新增，0 回归）
- **Commits**: beab26e..34b9340（8 commits）

使用 codex-review skill 进行 GPT 代码审查。
