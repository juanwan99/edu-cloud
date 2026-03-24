# edu-cloud — 教育云平台

<!-- key-start -->
## 项目定位

edu-cloud 是**多校协同的云端平台**，是学校端（exam-ai）的上游调度中心。

```
[监管端]                      [云端平台]                      [学校端]
教育局/集团看板  ──────→  edu-cloud (port 9000)  ←──────  exam-ai × N 所学校
  - 全区成绩总览              - 联考编排与下发                 - 本校考试管理
  - 学校间对比                - 跨校数据汇总                   - 扫描+AI阅卷
  - 教学质量监控              - 共享 AI 阅卷服务               - 成绩上报到云端
                              - 学校注册与状态监控
                              - 统一题库管理
```

### 职责边界

| 职责 | 归属 | 说明 |
|------|------|------|
| 学校注册与授权 | edu-cloud | 审批学校接入、下发 API Key |
| 联考生命周期 | edu-cloud | 创建→下发→汇总→报告 |
| 跨校成绩聚合 | edu-cloud | 各校上报，云端汇总排名 |
| 共享 AI 阅卷 | edu-cloud | 算力不足的学校可上传切图到云端阅卷 |
| 统一题库 | edu-cloud | 各校贡献+云端审核+联考组卷 |
| 本校考试管理 | exam-ai | 云端不介入单校日常考试 |
| 扫描切割 | paper-seg | 始终在本地执行 |

**关键关系**：exam-ai 是本项目的**下游客户端**，通过 REST API 同步数据。每所学校运行独立的 exam-ai 实例，edu-cloud 统一管理。
<!-- key-end -->

<!-- key-start -->
## 启动命令

```bash
# 后端（WSL 内执行）
cd /mnt/c/Users/Administrator/edu-cloud
python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload

# 前端（Windows Git Bash，port_guard 须用 serve.py）
cd /c/Users/Administrator/edu-cloud/frontend
python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev
# → http://localhost:5173，代理 /api → http://localhost:9000
```

## 测试命令

```bash
# 后端（780 tests）
cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q

# 前端（Vitest + happy-dom，35 tests）
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run
```
<!-- key-end -->

## 项目结构

```
frontend/src/
  layouts/
    AppShell.vue            # 角色感知壳层（AppHeader + AppSidebar + router-view + AiFloatingButton）
    WorkbenchLayout.vue     # 三栏布局（左侧边栏 + 顶栏 + 中央内容 + 右侧边栏）
    AuthLayout.vue          # 登录页布局
  pages/
    LoginPage.vue           # 登录页（edu-cloud 多角色版）
    AnalysisPage.vue        # 分析页（原 WorkbenchPage 重命名）
    ExamListPage.vue        # 考试列表（exam-ai 迁入）
    ExamDetailPage.vue      # 考试详情（科目/题目/答题卡/扫描/阅卷）
    DashboardPage.vue       # 仪表盘
    AnalyticsPage.vue       # 成绩分析（ECharts）
    GradingTasksPage.vue    # AI 阅卷任务
    GradingResultsPage.vue  # 阅卷结果
    TeacherReviewPage.vue   # 教师复核
    MarkingSelectPage.vue   # 手动阅卷选题
    MarkingPage.vue         # 手动阅卷
    MarkingAssignPage.vue   # 分配阅卷任务
    MarkingProgressPage.vue # 阅卷进度
    SchoolsPage.vue         # 学校管理（admin）
    CardEditorDevPage.vue   # 答题卡编辑器开发页
  components/
    shell/
      AppHeader.vue         # 68px 毛玻璃顶栏（Logo/SchoolContext/搜索/通知铃/角色切换）
      AppSidebar.vue        # 角色过滤侧栏导航（220px/64px 折叠，sidebarConfig 驱动）
      SchoolContext.vue     # 纯展示当前角色上下文名称
      RoleSwitcher.vue      # 角色切换下拉菜单（NDropdown，含头像）
      NotificationBell.vue  # 通知铃铛（NBadge + NPopover，占位）
    ai/
      AiFloatingButton.vue  # 右下角 AI 助手浮动按钮（占位）
    CardEditor.vue          # 可视化答题卡编辑器（封装 card-editor/）
    ChatPanel.vue           # AI 对话面板（SSE 流式）
    context/ workspace/ studio/ calendar/  # 云平台三栏组件
  card-editor/              # 答题卡编辑器原生 JS（5 模块：model/render/interact/panel/export）
  api/                      # API 调用层（11 模块 + client.js，baseURL /api/v1）
  config/
    roles.js                # 8 角色枚举 + 旧别名映射 + normalizeRole()
    permissions.js          # 角色→权限映射（镜像后端 core/permissions.py）+ hasPermission()
    sidebarConfig.js        # 角色→侧边栏导航项 JSON 配置
    dashboardConfig.js      # 角色→仪表盘 KPI/Widget JSON 配置
  stores/
    auth.js                 # Pinia auth（多角色 + switchRole，edu-cloud 版）
    aiChat.js               # AI 对话（SSE + tool_call 展示，exam-ai 版）
    context.js / studio.js  # 云平台上下文/Studio
  router/                   # Vue Router（AppShell 根 + 角色/权限守卫 fail-closed，2 顶级 + 14 子路由）
  main.js                   # 入口（Naive UI 暗色主题 + Pinia + Router）
  App.vue                   # 根组件
```

```
src/edu_cloud/
  api/
    app.py              # FastAPI 应用工厂 + lifespan + 请求日志中间件 + 全局异常处理器
    deps.py             # 依赖注入（JWT 认证 get_current_user + require_permission）
    permissions.py      # 数据权限过滤（get_visible_class_ids/get_visible_subject_codes）
    auth.py             # POST /api/v1/auth/login（平台用户 JWT 登录）
    dashboard.py        # GET /api/v1/dashboard/summary（角色 scope 聚合统计）
    notifications_api.py # GET /api/v1/notifications（通知列表，status/since 过滤）
    ai.py               # AI Agent 路由（Batch 4 迁移）
    # 以下为 re-export stubs，canonical → modules/
    schools.py → modules/school/router.py
    joint_exams.py → modules/exam/joint_exam_router.py
    results.py → modules/exam/results_router.py
    studio.py → modules/studio/router.py
    calendar.py → modules/calendar/router.py
    workspace.py → modules/exam/workspace_router.py
  models/
    base.py             # Base + IdMixin(UUID) + TenantMixin(school_id) + TimestampMixin(UTC)
    school.py           # RegisteredSchool（学校档案 + API Key + 心跳）
    platform_user.py    # PlatformUser（4 角色 + bcrypt 密码）
    joint_exam.py       # JointExam + JointExamParticipant + JointExamStudentResult
  services/
    exceptions.py       # 5 个自定义异常（NotFound/Permission/Validation/Conflict/State）
    school_service.py   # 学校 CRUD + API Key 管理
    joint_exam_service.py # 联考生命周期（创建→模板→下发→成绩→完成）
    results_service.py  # 排名 + 按校对比 + 学生明细
  data/
    seed_demo.py          # 演示数据种子（exam-ai 迁入）
    seed_knowledge_math.py # 数学知识点种子
    import_real_exam.py   # 真实考试数据导入工具（exam-ai 迁入）
  core/
    events.py           # 进程内 EventBus（已定义，handler 未接入）
    permissions.py      # 10 个 Permission 枚举 + 4 角色 RBAC 映射
  knowledge/
    __init__.py         # 包入口
    loader.py           # 知识库 JSON 文件加载（课标/L0/L1/高考索引）
    store.py            # 内存索引 KnowledgeStore + 全局单例 knowledge_store（关键字搜索）
  ai/
    agent.py            # ReAct Agent（ROLE_TOOL_CATEGORIES 9 类别 RBAC）
    llm.py              # LLMChatClient（OpenAI + Anthropic 双协议，重试，llm-proxy slot）
    context.py          # build_system_prompt + AgentContext（session 管理/token 裁剪）
    schemas.py          # ChatMessage/ToolCall/AgentEvent 数据模型
    anonymizer.py       # 会话级姓名脱敏（字段检测 + student_number 剥离）
    audit.py            # AuditLogger（DB 持久化 AiSession/AiToolCall）
    registry.py         # ToolRegistry 全局实例 + 装饰器注册 + 依赖注入
    models.py           # AiSession/AiToolCall 表
    tools/
      __init__.py       # 触发全部 10 个工具模块注册（31 tools）
      analytics.py      # L2_cross_school（2）: get_exam_scores/get_class_stats
      analytics_score.py # L2_analytics（5）: exam_summary/distribution/question/student/class scores
      analytics_compare.py # L2_analytics（3）: compare_classes/rank_students/grade_aggregates
      exams.py          # L1_exam（3）: exam_list/detail/subject_questions
      students.py       # L1_student（4）: class_list/roster/search/profile
      bank.py           # L5_bank（2）: error_book/question_stats
      profile.py        # L6_profile（4）: trend/knowledge_map/weakness/error_pattern
      knowledge.py      # L3_knowledge（4）: search_curriculum/textbook/concept/gaokao
      knowledge_db.py   # L3_knowledge_db（2）: knowledge_tree/question_knowledge_points
      actions.py        # L4_action（2）: generate_report/comment
  workers/
    grading.py          # process_grading_task（AI 阅卷）+ run_post_exam_pipeline（考后处理 stub）
  shared/
    auth.py             # JWT create/decode 工具函数
  config.py             # Settings（DB/Redis/JWT/LLM/UPLOAD_DIR/知识库 配置，BaseSettings）
  database.py           # async engine + session factory
  logging_config.py     # 双输出（Console UTC+8 + JSONL RotatingFile）
  worker.py             # arq WorkerSettings（3 functions: auto_draft/grading/pipeline）
scripts/
  e2e_joint_exam.py     # 端到端联考验证脚本（2 校完整流程）
tests/
  conftest.py           # SQLite in-memory + AsyncClient + admin/school/db_engine fixtures
  test_api/             # 平台 API 测试（health/deps/schools/joint_exams/sync_v2/results）
  test_api_exam/        # 考试 API 测试（exam-ai 迁入，32 文件）
  test_services/        # 平台 Service 单测（exceptions/school/joint_exam/results）
  test_services_exam/   # 考试 Service 单测（exam-ai 迁入，27 文件）
  test_exam_misc/       # 考试杂项测试（answer_standardizer/template_library/integration）
  test_models/          # 模型单测
  test_knowledge/       # 知识库单测（loader/store）
  test_workers/         # Worker 单测（grading task 注册/签名验证）
  test_alembic_migration.py  # Alembic 迁移 smoke test（upgrade/downgrade/表集合对比）
```

### 实现状态

| 层 | 已实现 | 未实现（规划中）|
|---|--------|--------------|
| API | auth/login, schools(CRUD+key), joint-exams(生命周期), results(排名/对比/明细), sync(heartbeat/exams/templates/scores), health, version, studio(documents CRUD+transition+paper/create+paper/:id/status), calendar(events CRUD) | 跨校分析(高级), 题库, 共享 AI 阅卷 |
| Models | 29 表（modules/ 下 exam/student/card/scan/grading/marking/bank/profile/knowledge/pipeline + core school/user/user_role/llm_slot + studio/calendar/notification）| — |
| Services | SchoolService, JointExamService, ResultsService, PaperService(paper-skill REST 客户端), StudioService(list_documents OR assigned_to), CalendarService(create/list/delete/triggered_rules), NotificationService(dispatch stub+幂等), exceptions | EventBus handler, AI grading |
| Tasks | tasks.py: auto_draft_notifications（扫描日历→自动创建 notification 草稿，防重复 triggered 标记）| arq cron 生产接入 |
| Worker | worker.py: arq WorkerSettings（run_auto_draft cron 22:00 UTC = 06:00 UTC+8）| — |
| Core | EventBus 定义, RBAC 映射(10 权限 + require_permission) | EventBus handler 接入 |
| Knowledge | KnowledgeStore（课标/L0/L1/高考索引，关键字搜索，全局单例）+ L3 查询工具（4 tools，启动加载）| — |
| Tests | 780 tests（API+Service+Model+Knowledge+AI Tools+Paper+Calendar+Tasks+Notification+LLMSlot+Exam迁入+Alembic迁移+权限边界+Dashboard 全覆盖）+ 27 前端 Vitest | — |
| Modules | 15 模块目录（exam/student/card/scan/grading/marking/analytics/bank/profile/pipeline/knowledge/studio/calendar/paper/school），路由已迁入 | — |
| Migrations | Alembic 初始 migration（39 表，autogenerate） | — |

## 技术栈

**后端：**
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg (PostgreSQL)
- Alembic (migrations)
- python-jose (JWT) + bcrypt
- arq + Redis (后台任务：联考下发、批量阅卷、报表生成)
- httpx (调用学校端 API)
- Docker + docker-compose (部署)

**前端（`frontend/`）：**
- Vite 7 + Vue 3.5 (Composition API)
- Naive UI 2.44（暗色主题）
- Vue Router 4（AppShell 根布局 + 角色/权限守卫，login 外置 + 14 子路由）
- Pinia 3（状态管理）
- Axios（HTTP 客户端，baseURL `/api/v1`）
- ECharts 6 + vue-echarts（图表）
- KaTeX + marked（数学公式渲染 + Markdown）
- card-editor（答题卡可视化编辑器，5 模块 + CardEditor.vue）
- Vitest 4 + @vue/test-utils + happy-dom（单元测试）

## 日志体系

与 exam-ai 保持一致：双输出（Console + JSONL）、Request ID 追踪、UTC+8 时区。
日志文件：`logs/app.jsonl`，10MB 轮转，5 份备份。

<!-- key-start -->
## 端口约定

| 服务 | 端口 | 说明 |
|------|------|------|
| edu-cloud 后端 | 9000 | FastAPI（本项目） |
| edu-cloud 前端 | 5173 | Vite dev server（开发）|
| exam-ai | 8000 | 学校端阅卷服务 |
| paper-seg | 8001 | 扫描客户端 |
| paper-skill | 9103 | AI 论文写作服务（外部，REST 客户端通过 PaperService 调用）|
<!-- key-end -->

## 角色体系

### 统一角色体系（edu-cloud 管理，P0 重构后）

> 重构声明（2026-03-21）：edu-cloud 从联考后端升级为统一平台后，
> 学校内角色由 edu-cloud 直接管理，不再由 exam-ai 管理。
> exam-ai 退化为数据采集节点。详见 `docs/plans/2026-03-21-super-platform-design.md` §1。

| 角色 | 权限 | 说明 |
|------|------|------|
| platform_admin | 全部 | 平台超管 |
| district_admin | 管辖区域内学校 | 教育局管理员 |
| principal | 全校管理+分析 | 校长 |
| academic_director | 教务+联考+分析 | 教务主任 |
| grade_leader | 本年级分析 | 年级组长 |
| homeroom_teacher | 本班管理+评语+通知 | 班主任 |
| subject_teacher | 所教班+学科+论文 | 科任教师 |
| parent | 只看自己孩子 | 家长（企微登录）|

**exam-ai 旧角色兼容别名**（permissions.py + api/permissions.py）：

| 旧角色 | 映射到 | 说明 |
|--------|--------|------|
| admin | platform_admin | exam-ai 迁入测试使用 |
| teacher | subject_teacher | exam-ai 迁入测试使用 |
| head_teacher | homeroom_teacher | exam-ai 迁入测试使用 |

## API 端点（已实现）

### 平台端点（JWT 认证）

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/v1/auth/login` | 平台用户登录，返回 JWT + roles（含 context: type/id/name） |
| POST | `/api/v1/auth/switch-role` | 切换活跃角色，返回新 JWT + active_role（含 context） |
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/version` | 版本+启动时间 |
| GET | `/api/v1/dashboard/summary` | 仪表盘聚合统计（角色 scope 过滤：students/classes/exams） |

### 学校管理端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| POST | `/api/v1/schools` | MANAGE_SCHOOLS | 创建学校（返回 API Key） |
| GET | `/api/v1/schools` | VIEW_SCHOOLS | 列表（支持 district/is_active 过滤） |
| GET | `/api/v1/schools/{id}` | VIEW_SCHOOLS | 学校详情 |
| PATCH | `/api/v1/schools/{id}` | MANAGE_SCHOOLS | 更新学校信息 |
| POST | `/api/v1/schools/{id}/rotate-key` | MANAGE_SCHOOLS | 轮换 API Key |

### 联考管理端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| POST | `/api/v1/joint-exams` | CREATE_JOINT_EXAM | 创建联考 |
| GET | `/api/v1/joint-exams` | VIEW_JOINT_EXAM | 联考列表 |
| GET | `/api/v1/joint-exams/{id}` | VIEW_JOINT_EXAM | 联考详情（含参与校） |
| POST | `/api/v1/joint-exams/{id}/participants` | MANAGE_JOINT_EXAM | 添加参与校 |
| DELETE | `/api/v1/joint-exams/{id}/participants/{school_id}` | MANAGE_JOINT_EXAM | 移除参与校 |
| POST | `/api/v1/joint-exams/{id}/distribute` | MANAGE_JOINT_EXAM | 下发联考 |
| POST | `/api/v1/joint-exams/{id}/force-complete` | MANAGE_JOINT_EXAM | 强制截止 |

### 成绩查看端点（JWT 认证）

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/joint-exams/{id}/results` | 排名（支持 subject_code 过滤，无则全科总分） |
| GET | `/api/v1/joint-exams/{id}/results/by-school` | 按校对比（avg/max/median/count） |
| GET | `/api/v1/joint-exams/{id}/results/students/{number}` | 学生明细（含每科排名） |

### 考试管理端点（JWT 认证，Batch 3 迁入）

| 方法 | 路径 | 用途 |
|------|------|------|
| POST/GET | `/api/v1/exams` | 创建/列表考试 |
| GET/PATCH | `/api/v1/exams/{id}` | 详情/更新考试 |
| POST/GET | `/api/v1/exams/{id}/subjects` | 创建/列表科目 |
| POST/GET/PATCH/DELETE | `/api/v1/questions` | 题目 CRUD |
| GET/POST | `/api/v1/classes`, `/api/v1/students` | 班级/学生管理 |
| * | `/api/v1/card/*` | 答题卡生成/骨架/条码（19 端点） |
| * | `/api/v1/templates/*` | 模板 CRUD |
| * | `/api/v1/scan/*` | 扫描上传/任务管理 |
| * | `/api/v1/grading/*` | AI 阅卷/评分规则/教师审核 |
| * | `/api/v1/marking/*` | 人工阅卷/分配/导出 |
| * | `/api/v1/analytics/*` | 统计分析（摘要/分布/题目/年级） |
| * | `/api/v1/knowledge/*` | 知识点 CRUD/树查询/关联 |
| POST | `/api/v1/pipeline/run/{id}` | 数据流水线触发 |
| * | `/api/v1/llm-config/slots` | LLM 槽位管理 |

### Studio 文档端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/studio/templates` | 已登录 | 获取当前角色可用模板 |
| GET | `/api/v1/studio/documents` | GENERATE_REPORT | 列出文档（本人创建或被指派） |
| POST | `/api/v1/studio/documents` | GENERATE_REPORT | 创建文档 |
| GET | `/api/v1/studio/documents/{id}` | GENERATE_REPORT | 文档详情 |
| PATCH | `/api/v1/studio/documents/{id}` | GENERATE_REPORT | 更新文档内容 |
| POST | `/api/v1/studio/documents/{id}/transition` | GENERATE_NOTIFICATION | 状态流转（P3-4 F3: 通知文档 executed 需额外 SEND_NOTIFICATION；F4: pending 自动创建审批流；executed 触发 NotificationService.dispatch） |

### Studio 论文端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| POST | `/api/v1/studio/paper/create` | WRITE_PAPER | 创建论文任务（调用 paper-skill，创建 Studio Document 关联记录） |
| GET | `/api/v1/studio/paper/{paper_id}/status` | 已登录 | 查询论文进度（透传 paper-skill /api/paper/:id/status） |

### 日历端点（JWT 认证，P3-2）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| POST | `/api/v1/calendar/events` | GENERATE_NOTIFICATION | 创建校历事件（含通知规则） |
| GET | `/api/v1/calendar/events` | 已登录 | 列出本校校历事件（支持 start/end 日期过滤） |
| DELETE | `/api/v1/calendar/events/{id}` | GENERATE_NOTIFICATION | 软删除校历事件（is_active=False） |

### 通知端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/notifications` | 已登录 | 列出本校通知（支持 status/since 过滤） |

### AI Agent 端点（JWT 认证，Batch 4 迁入）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/ai/health` | 无 | 工具数量 + 状态 |
| POST | `/api/v1/ai/chat` | USE_AI_CHAT | SSE 流式对话（multi-turn session） |
| GET | `/api/v1/ai/sessions` | 已登录 | 列出活跃会话 |
| DELETE | `/api/v1/ai/sessions/{session_id}` | 已登录 | 删除会话 |

### 未实现端点（规划中）

- 共享 AI 阅卷（`grading-request`/`grading-result`）
- 统一题库
- 高级跨校分析（趋势/对比图表）

## 关联项目

| 项目 | 路径 | 关系 |
|------|------|------|
| exam-ai | `C:/Users/Administrator/exam-ai` | 学校端，本项目的下游客户端 |
| paper-seg | `C:/Users/Administrator/paper-seg` | 扫描端，不直接与云端通信 |
| paper-skill | `C:/Users/Administrator/paper-skill` | AI 论文写作服务，edu-cloud 通过 PaperService 调用（端口 9103）|

## 数据库

```
# .env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/edu_cloud
```

云端必须使用 PostgreSQL（跨校聚合查询、高并发写入）。不支持 SQLite。

## Docker 部署

Dockerfile 包含 Playwright Chromium + 中文字体（Noto CJK），用于答题卡 PDF 生成。

docker-compose 挂载卷：`./logs:/app/logs`、`./storage:/app/storage`（扫描图片）、`./uploads:/app/uploads`（上传文件）。

```bash
docker compose up -d        # 启动
docker compose pull && docker compose up -d  # 升级
docker compose logs -f      # 查看日志
```

## 参考文档

| 文档 | 路径 | 内容 |
|------|------|------|
| AI Agent 设计 | `docs/plans/2026-03-16-ai-agent-design.md` | Agent Phase 1-4 架构设计（554 行，§14 含 API→Service 分层）|
| 平台交接单 | exam-ai `docs/plans/2026-03-16-platform-handoff.md` | A→B→C→D 四阶段全局规划 |

## 数据模型概要

| 表 | 关键字段 | 说明 |
|---|---------|------|
| schools | code(唯一), api_key_hash(Optional), is_active, district | 学校档案（原 registered_schools） |
| users | username(唯一), display_name, hashed_password, is_active | 统一用户（原 PlatformUser 已删除） |
| user_roles | user_id(FK), role, school_id(FK), class_ids, is_primary | 多角色+scope |
| llm_slots | school_id(FK,nullable), slot_number, api_url, api_key, model, is_enabled | LLM 槽位配置（学校覆盖>平台默认>.env） |
| joint_exams | name, status(draft→...→archived), subjects(JSON), created_by(FK→users), creator_school_id(FK) | 联考 |
| joint_exam_participants | joint_exam_id(FK), school_id(FK), status, is_creator | 参与校 |
| joint_exam_student_results | joint_exam_id, school_id, subject_code, student_name/number, total_score, detail_scores(JSON) | 成绩明细 |
| documents | type, title, status, content_json, created_by(FK→users), assigned_to(FK), school_id(FK) | Studio 文档 |
| calendar_events | type, title, event_date, school_id(FK), created_by(FK→users), semester, is_active | 校历事件 |
| notification_rules | event_id(FK), days_before, template_type, target_roles(JSON), auto_draft, triggered | 通知触发规则 |
| notifications | document_id(FK), channel, status, target_scope(JSON), school_id(FK) | 通知发送记录 |

## 种子数据

启动时自动创建：平台管理员 `admin/123456`（User + UserRole platform_admin）。
