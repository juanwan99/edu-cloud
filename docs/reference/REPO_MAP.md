# 项目结构参考（按需查阅）

> 本文件从 CLAUDE.md 移出，按需 Read。不再每次会话注入。

## 项目结构

```
frontend/src/
  layouts/
    AppShell.vue            # 角色感知壳层（AppHeader + AppSidebar + router-view + AiFloatingButton）
    WorkbenchLayout.vue     # 三栏布局（左侧边栏 + 顶栏 + 中央内容 + 右侧边栏）
    AuthLayout.vue          # 登录页布局
    ParentLayout.vue        # 家长端移动优先布局（顶栏+内容+底部4标签，cp_token 独立认证，子女切换）
  pages/
    LoginPage.vue           # 登录页（edu-cloud 多角色版）
    AnalysisPage.vue        # 分析页（原 WorkbenchPage 重命名）
    ExamListPage.vue        # 考试列表（exam-ai 迁入）
    ExamDetailPage.vue      # 考试详情 Tab 壳（263行，共享 exam/subjects 状态）
    exam-detail/            # ExamDetailPage 子组件（技术债 H-02 拆分，见 docs/2026-04-26-tech-debt-audit.md）
      SubjectsTab.vue       # 科目管理 Tab
      CardMakerTab.vue      # 答题卡制作 Tab
      VisualEditorTab.vue   # 可视化编辑 Tab
      AnswersTab.vue        # 标准答案 Tab
      QuestionsTab.vue      # 题目管理 Tab
    DashboardPage.vue       # 仪表盘
    AnalyticsPage.vue       # 成绩分析（ECharts）
    AnalyticsReportPage.vue # 分析报告（多考试+多指标查询，ECharts 分段柱图）
    AnalyticsTrendPage.vue  # 成绩趋势（年级/班级/学生维度折线图）
    GradeAnalyticsPage.vue  # 年级分析（班级对比+考情趋势+科目雷达+箱线图+KP热力图）
    GradingDispatchPage.vue # 扫描调度中心壳（758行，科目列表+dispatch 轮询）
    grading-dispatch/       # GradingDispatchPage 子组件（技术债 H-02 拆分）
      SubjectStatusCard.vue # 科目状态卡片
      ScanSection.vue       # 扫描阶段面板
      BatchOperationsBar.vue # 批量操作栏
    AiGradingPage.vue       # AI 阅卷壳（732行，左右分栏布局）
    ai-grading/             # AiGradingPage 子组件（技术债 H-02 拆分）
      ExamSubjectSelector.vue # 考试/科目选择器
      QuestionList.vue      # 题目列表
      GradingPanel.vue      # 阅卷操作面板
    GradingResultsPage.vue  # 阅卷结果（含返回按钮）
    TeacherReviewPage.vue   # 教师复核
    MarkingSelectPage.vue   # 手动阅卷选题
    MarkingPage.vue         # 手动阅卷
    MarkingAssignPage.vue   # 分配阅卷任务（一题多人+数量配额，per-question 卡片布局，含返回按钮）
    MarkingProgressPage.vue # 阅卷进度（含返回按钮）
    SchoolsPage.vue         # 学校管理（admin）
    SchoolSettingsPage.vue  # 学校配置（模块开关 + KV 设置 + 分数段，principal/academic_director）
    SubjectSelectionsPage.vue # 选考科目组合管理
    TeacherAssignmentsPage.vue # 教师排课管理
    StudentsPage.vue        # 学生管理（列表/搜索/导入导出/选科分配）
    TeachersPage.vue        # 教师管理（列表/创建/导入导出/15列档案）
    CardEditorDevPage.vue   # 答题卡编辑器开发页（含返回按钮）
    KnowledgeTreePage.vue  # 知识图谱可视化（AntV G6 + 三级树导航 + 掌握度着色 + 搜索过滤 + Phase 2 教师工作台：ModuleOverviewPanel/ConceptMapPanel 互斥路由 + BigConcept 分带 + ConceptFocusOverlay 焦点模式 + ESC/canvas 退出；Phase 2.5：buildVisibleEdgeList helper + relatedNodeIds/relatedEdgeIds computed + G6 node.state.faded/edge.state.dimmed·emphasized + updateElementStates + createGraph 末尾焦点重放 + G6 Tooltip plugin 徽标悬停（hover + enable 谓词 + async getContent + HTML escape）；Phase 1 T9-T10：ColorModeToggle 三模式切换 + heatmapUtils（log 尺度考频热力色 + 4 态掌握度 + 3 态审核状态 + importance→size [20,60]）；ConceptMapPanel buildG6Data 每节点 style.size/fill 按 colorMode 三分支 + watch colorMode setData/render 保留 focusedNodeId + defineExpose buildG6Data；KnowledgeTreePage selectedStudentId 从 useKnowledgeTree 解构（单一真源，R2 F001 修复 state 分裂）；GraphPanel.vue 已删除；Phase 1 T11-T14：NodeDetailDrawer exam_items + study_unit tab + ExamItemsTab/StudyUnitTab + TreeNavPanel 双模式 + ModuleOverviewPanel 统计增强）
    parent/                 # 家长端页面（独立于 AppShell，cp_token 认证）
      ParentLogin.vue       # 家长登录（手机号+密码）
      ParentRegister.vue    # 家长注册（邀请码验证→填写资料，支持 URL ?code= 预填）
      ParentBind.vue        # 绑定孩子（学生姓名+身份验证码+关系）
      ParentOverview.vue    # 概览（积分统计卡+最近记录列表）
      ParentDetails.vue     # 详细记录（分页 DataTable）
      ParentRankings.vue    # 班级排行榜（当前孩子高亮）
      ParentRules.vue       # 班规查看（分类折叠面板+正负分标签，F004 字段修正 item.points）
      ParentProfile.vue     # 个人中心（编辑姓名/改密码/已绑定孩子/退出）
    conduct/                # 管理端操行页面（AppShell 内，权限守卫，侧边栏 3 入口：工作台+设置+学生档案）
      ConductWorkbench.vue  # 德育工作台壳（NTabs: 概览/记积分/记录/排行，角色 scope 标签，query.tab 同步）
      ConductSettingsHub.vue # 德育设置壳（NTabs: 班规/小组/家长绑定/预警学期，query.tab 同步）
      ConductDashboard.vue  # 概览 Tab（scope-adaptive: class 走势图+排名/school 班级对比/district 学校对比）
      ConductPoints.vue     # 记积分 Tab（学生多选+班规快捷按钮+手动输入+最近记录）
      ConductRecords.vue    # 记录 Tab（分页表格+学生/日期过滤+删除+导出按钮）
      ConductRankings.vue   # 排行 Tab（学生/小组 Tab+学期筛选+导出按钮）
      ConductRules.vue      # 班规 Tab（分类折叠+条目 CRUD+积分标签+学校规则继承）
      ConductGroups.vue     # 小组 Tab（卡片网格+成员抽屉+添加/移除）
      ConductParents.vue    # 家长 Tab（表格+邀请码+移除）
      ConductSettings.vue   # 预警学期 Tab（邀请码+验证方式+预警阈值+学期管理）
      ConductExport.vue     # 完整导出（记录/排行榜+日期/学期筛选+Excel，旧路径重定向到记录 Tab）
  components/
    shell/
      AppHeader.vue         # 68px 毛玻璃顶栏（Logo/SchoolContext/搜索/通知铃/角色切换）
      AppSidebar.vue        # 板块分组侧栏导航（5 组折叠/展开，220px/64px 折叠，getSidebarGroups 驱动）
      SchoolContext.vue     # 纯展示当前角色上下文名称
      RoleSwitcher.vue      # 角色切换下拉菜单（NDropdown，含头像）
      NotificationBell.vue  # 通知铃铛（NBadge + NPopover，占位）
    ai/
      AiFloatingButton.vue  # 右下角 AI 助手浮动按钮（权限 use_ai_chat 控制可见性）
      AiSlidePanel.vue      # 右侧 420px 滑出 AI 聊天面板（SSE 流式 + tool_call 展示 + thinking/plan 显示）
    CardEditor.vue          # 可视化答题卡编辑器（封装 card-editor/）
    TemplatePreviewEditor.vue # 扫描模板区域编辑器（检测结果叠加+拖拽/缩放/分割，A/B双面）
    RubricEditor.vue        # 评分细则展示/编辑（v-model criteria 数组，分值合计校验）
    QuestionContentModal.vue # 题干/答案编辑弹窗（textarea + 多图上传 + Ctrl+V 粘贴图片）
    DocCropPanel.vue        # 文档裁剪面板（PDF/Word→页面渲染→框选裁剪→按题号+序号保存）
    analytics/
      ScoreSegmentSettings.vue # 分数段配置（学校默认+科目覆盖，嵌入 SchoolSettingsPage）
      StatCard.vue            # 统计卡片（数值+标签+趋势箭头+环比）
      ClassRankTable.vue      # 班级排名表（排名/均分/及格率/优秀率/进退步）
      AiDiagnosisCard.vue     # AI 诊断摘要卡片（诊断文字+建议列表+时间戳）
      ErrorCausePanel.vue     # 错因分析面板（题目→学生错因列表，支持筛选）
      StudentRankTable.vue    # 学生排名表（总分/班名次/年名次/进退步+搜索+展开行）
      TrendLine.vue           # 通用趋势折线图（vue-echarts，多系列+虚线+反转轴）
      CriticalStudents.vue    # 临界生名单（差N分及格/优秀，Tab切换+丢分题目）
      RadarChart.vue          # 通用雷达图（知识掌握/科目得分，vue-echarts）
      KnowledgeHeatmap.vue    # 知识点掌握热力图（班级×知识点，vue-echarts）
    context/ workspace/ studio/ calendar/  # 云平台三栏组件
  assets/styles/
    variables.css           # CSS 设计 token（颜色/语义色/圆角/阴影/字体/间距 scale/动效/z-index 4 层级；品牌色 primary #644CF0/accent #F4DA4C，文字色 #09061B/#5a5a68/#A0A0A8）
    global.css              # 全局样式 + 工具类（page-title 30px/w800, stat-card 36px/w800, tag-*/chart-height-*/tabular-nums/prefers-reduced-motion）
  card-editor/              # 答题卡编辑器原生 JS（5 模块：model/render/interact/panel/export）
  api/                      # API 调用层（26 文件含 client.js，baseURL /api/v1；conduct.js 含独立 parentClient 用 cp_token；students.js 学生CRUD+导入导出；teachers.js 教师CRUD+导入导出；cards.js 含 renderDocPages 文档渲染）
  config/
    roles.js                # 10 角色枚举 + 旧别名映射 + normalizeRole()
    permissions.js          # 角色→权限映射（镜像后端 core/permissions.py）+ hasPermission()
    sidebarConfig.js        # 5 板块分组（考试阅卷/教研教学/教务管理/学生管理/学校管理）+ SIDEBAR_GROUPS + getSidebarGroups(role, enabledModules) 权限动态过滤 + getSidebarItems(role) 兼容扁平接口
    dashboardConfig.js      # 角色→仪表盘 KPI/Widget JSON 配置
    chartTheme.js           # ECharts 全局色板常量（CHART_PALETTE/TEXT_COLOR/SPLIT_COLOR）
  stores/
    auth.js                 # Pinia auth（多角色 + switchRole，edu-cloud 版）
    aiChat.js               # AI 对话（SSE + tool_call 展示，exam-ai 版）
    context.js / studio.js  # 云平台上下文/Studio
  router/                   # Vue Router（52 路由：AppShell 39 子路由+7 conduct 重定向 + parent 9 路由 + login + catch-all；含 /ai-grading 无参入口 + /knowledge-tree；冻结备份在 _frozen/；/parent/* 跳过平台 auth）
  main.js                   # 入口（Pinia + Router，Naive UI 按需导入 via unplugin-vue-components）
  App.vue                   # 根组件
```

```
src/edu_cloud/
  api/
    app.py              # FastAPI 应用工厂 + lifespan + 请求日志中间件 + 全局异常处理器（路由注册委托给 router_registry.py）
    router_registry.py  # 有序路由注册表（PLATFORM_ROUTERS + MODULE_ROUTERS），替代手工 include_router；新增模块在此注册
    deps.py             # 依赖注入（JWT 认证 get_current_user + require_permission）
    permissions.py      # 数据权限过滤（get_visible_class_ids/get_visible_subject_codes）
    auth.py             # POST /api/v1/auth/login（平台用户 JWT 登录）
    dashboard.py        # GET /api/v1/dashboard/summary（角色 scope 聚合统计：students/classes/exams/staff/pending_grading/pending_subjects）
    notifications_api.py # GET /api/v1/notifications（通知列表，status/since 过滤）
    ai.py               # AI Agent 路由（EduAgentRuntime + Pydantic AI：POST /chat SSE + POST /runs/{id}/confirmations/{id} 写确认）
    compat_router.py    # exam-ai 兼容路由（/api 前缀，paper-seg 零改动对接，8 端点）
    module_middleware.py # ModuleCheckMiddleware — 禁用模块 API 硬拦截（JWT active_role_id → school_id 解析）
    # 以下为 re-export stubs，canonical → modules/
    schools.py → modules/school/router.py
    joint_exams.py → modules/exam/joint_exam_router.py
    results.py → modules/exam/results_router.py
    studio.py → modules/studio/router.py
    calendar.py → modules/calendar/router.py
    workspace.py → modules/exam/workspace_router.py
  models/               # 44 个 ORM 模型文件，按域分组：
    base.py             # Base + IdMixin(UUID) + TenantMixin(school_id) + TimestampMixin(UTC)
    # —— 平台级 ——
    school.py           # RegisteredSchool（学校档案 + API Key + 心跳）
    user.py / user_role.py # PlatformUser + UserRole（多角色）
    school_settings.py  # SchoolSetting（KV）+ SchoolModule（模块开关）
    teacher_assignment.py / subject_selection.py / capability.py  # 排课/选考/能力矩阵
    audit_log.py / notification.py / menu.py  # 审计/通知/菜单
    # —— 考试与阅卷 ——
    exam.py / student.py / class_group.py / grade.py  # 考试/学生/班级/年级
    grading.py / scan.py / card.py  # 阅卷任务/扫描/答题卡
    score_segment.py    # 分数段配置（学校+科目覆盖）
    # —— 分析与画像 ——
    analytics.py / profile.py / bank.py  # 统计/画像/题库
    knowledge.py / knowledge_tree.py / adaptive.py  # 知识库/图谱/自适应（BKT）
    # —— 业务扩展 ——
    conduct.py / guardian.py  # 德育（8 表）+ 家长绑定
    homework.py / academic.py / calendar.py  # 作业/教务/校历
    joint_exam.py       # 联考 + 参与校 + 跨校成绩
    # —— AI Agent ——
    ai_engine.py / ai_session.py  # LLM 槽位/会话
    agent_profile.py / agent_finding.py / agent_memory.py / agent_snapshot.py  # Agent 身份/发现/记忆/快照
    # —— 工作流 ——
    document.py / workflow.py / approval.py  # Studio 文档/工作流/审批
    scope_version.py / teaching_plan.py / llm_slot.py / memory.py  # 其他
  services/
    exceptions.py       # 5 个自定义异常（NotFound/Permission/Validation/Conflict/State）
    school_service.py   # 学校 CRUD + API Key 管理
    joint_exam_service.py # 联考生命周期（创建→模板→下发→成绩→完成）
    results_service.py  # 排名 + 按校对比 + 学生明细
    school_settings_service.py # Settings/Modules CRUD + init_school_modules + get_enabled_modules
    teacher_assignment_service.py # 排课 CRUD + 批量创建（幂等）+ FK 归属校验 + 聚合摘要
    subject_selection_service.py # 选考 CRUD + 校验（mode 枚举 / 科目数量）+ 唯一约束冲突处理
    capability_service.py # Capability init/get/set/check + DEFAULT_CAPABILITIES 模板
    audit_service.py    # @audited 装饰器 + write_audit_log + list_audit_logs
    agent_profile_service.py # AgentProfileService（get_or_create + record_run）
  data/
    seed_demo.py          # 演示数据种子（exam-ai 迁入）
    seed_knowledge_math.py # 数学知识点种子
    import_real_exam.py   # 真实考试数据导入工具（exam-ai 迁入）
  core/
    events.py           # 进程内 EventBus（exam.published handler 已接入 pipeline）
    permissions.py      # 49 个 Permission 枚举 + 10 角色 RBAC 映射
    scope_filter.py     # ScopeFilter 工具类（基于 UserRole 注入 WHERE 条件）
  knowledge/
    __init__.py         # 包入口
    loader.py           # 知识库 JSON 文件加载（课标/L0/L1/高考索引）
    store.py            # 内存索引 KnowledgeStore + 全局单例 knowledge_store（关键字搜索）
  ai/                    # AI Agent 子系统
    engine/              # **Pydantic AI 引擎层（活跃，api/ai.py 的唯一后端）**
      agent_deps.py     # AgentDeps — RunContext 依赖容器（替代 ToolContext，per-tool 独立 DB session）
      edu_runtime.py    # EduAgentRuntime — 顶层编排（构建 Agent → asyncio.Queue SSE → 确认恢复）
      policy_guardrail.py # PolicyToolGuardrail — 4 层硬检查（role/module/capability/scope）
      budget.py         # AgentBudget — token/tool/write/wall-clock 硬限
      confirmation_broker.py # ConfirmationBroker — 写操作暂停→SSE→前端确认卡→POST 恢复
      artifact_manager.py # ArtifactManager — >32KB/50行 自动脱敏摘要
      trace_recorder.py # TraceRecorder — JSONL + DB 双写（user_id SHA256）
      tool_meta.py      # EduToolMeta — frozen 工具元数据
      tool_wrapper.py   # @edu_tool 装饰器 + TOOL_META_REGISTRY 全局注册
      tools/            # 68 个 @edu_tool 原生工具（16 模块文件）
    # 以下为旧引擎组件（生产路径已不引用，保留供旧测试参照）
    data_scope.py       # DataScope（frozen 数据可见性快照）+ DataScopeBuilder — 被 engine 引用
    prompts.py          # build_teacher_prompt + SCHEDULED_PROMPTS — 被 engine/worker 引用
    memory_store.py     # MemoryStore — 被 engine 引用
    memory_injector.py  # MemoryInjector — 被 api/ai.py 引用
    anonymizer.py       # Anonymizer — 被 engine 引用
    schemas.py          # AgentEvent/ToolCall/Message — 被 engine 引用
    tools/              # 旧 @registry.register 工具（23 模块，63 tools）— 生产路径不再调用
  workers/
    grading.py          # process_grading_task（AI 阅卷，微批次并发 GRADING_BATCH_SIZE=20，支持 realtime/batch 双模式）+ run_post_exam_pipeline（考后处理，已接线 pipeline）
  shared/
    auth.py             # JWT create/decode 工具函数
    upload_validation.py # 图片上传 magic bytes 验证（替代 Python 3.13 废弃的 imghdr）
  config.py             # Settings（按域分组注释：Database/Security/Storage/Logging/CORS/LLM/Gemini/VertexAI/Grading/Agent/Knowledge/Paper，BaseSettings 平铺）
  database.py           # async engine + session factory（PostgreSQL 连接池 pool_size=20/max_overflow=40/pool_recycle=3600）
  logging_config.py     # 日志系统 v2（进程分文件日滚 JSONL + 全链路 trace_id + business_event() + log_event()）
  worker.py             # arq WorkerSettings（6 functions: auto_draft/grading/pipeline/w3_daily/w6_hourly/agent_scheduled）
scripts/               # 60+ 脚本，按职责分类：
  # —— 数据库 ——
  db_migrate            # 安全 migration wrapper（flock→backup→dry-run→doctor→upgrade）；唯一合法 migration 路径
  db_doctor.py          # ORM vs DB schema drift 检测（--startup/--strict/--json）
  db_branch             # branch DB 隔离工具（init/refresh/prune/list/status）
  # —— 日志 ——
  edu-log               # 日志查询 CLI（trace/req/user/exam/frontend/llm/slow/tail/stats，13 命令）
  edu-log-maintain      # 日志维护（14d 压缩/120d 删除/365d business/12GB 上限，cron 每日 03:00）
  # —— 模块与种子 ——
  new-module            # 模块脚手架（scripts/new-module <name> [--pattern standard|multi-router|service-only]）
  seed_data.py / seed_menus.py  # 演示数据/菜单种子
  # —— AI 阅卷校准 ——
  essay_v*.py           # 8+ 版本迭代阅卷测试脚本
  calibrate_scan.py / calibrate_universal.py  # 阅卷校准（bio_geo 旧脚本已归档）
  bench_llm_concurrency.py  # LLM 并发基准测试
  # —— 验证与治理 ——
  pytest_delta.py       # no-new-failures 回归门禁（对比 .quality/known-pytest-failures.txt 基线）
  e2e_joint_exam.py     # 端到端联考验证脚本（2 校完整流程）
  codex-check / codex-verify / meta-check  # 代码/元治理检查
  truth / truth-doctor.sh / truth-status.sh  # 真源状态检查
  guardian_runtime.py / guardian-watch  # Guardian 守护运行时
  # —— 部署与知识 ——
  setup_ecs_dev.sh / subagent-worktree-bootstrap  # 环境初始化
  run-arq-worker        # arq Worker 启动
  sync_concept_graph.py / migrate_knowledge_hierarchy.py  # 知识图谱同步/迁移
  import_mcu_planning_weights.py  # 知识点规划权重导入
tests/                 # 306 个测试文件，17 个子目录：
  conftest.py           # SQLite in-memory + AsyncClient + admin/school/db_engine fixtures
  test_api/             # 平台 API 测试（health/deps/schools/joint_exams/sync_v2/results/tenant_isolation）
  test_api_exam/        # 考试 API 测试（exam-ai 迁入，32 文件）
  test_services/        # 平台 Service 单测（exceptions/school/joint_exam/results）
  test_services_exam/   # 考试 Service 单测（exam-ai 迁入，27 文件）
  test_exam_misc/       # 考试杂项测试（answer_standardizer/template_library/integration）
  test_models/          # 模型单测
  test_modules/         # 模块级集成测试
  test_knowledge/       # 知识库单测（loader/store）
  test_knowledge_tree/  # 知识图谱测试
  test_workers/         # Worker 单测（grading task 注册/签名验证）
  test_conduct/         # 德育模块测试
  test_adaptive/        # 自适应学习测试（BKT/路径规划）
  test_ai/              # AI Agent 测试
  test_core/            # 核心层测试（权限/scope）
  test_logging/         # 日志系统测试
  test_menu/            # 菜单测试
  governance/           # 治理规则测试
  test_alembic_migration.py  # Alembic 迁移 smoke test（upgrade/downgrade/表集合对比）
```
