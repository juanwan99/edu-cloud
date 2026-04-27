# edu-cloud — 教育云平台

> **架构边界声明（2026-04-16 takeover `00cfc3d` 后生效）**
>
> ECS 是**单一权威开发环境**，与原 Windows/WSL 环境已**完全切断**。
> 全部规格、plan、handoff、测试基线、命令路径**只以 ECS 为准**。
>
> 禁引：Windows-era 数字（如 1896/118/120/108）、`C:/Users/Administrator` 路径、
> R1-R3 handoff 时序追溯、"Windows 历史/worktree"等表述。
>
> 所有 baseline 用 ECS pytest 实测数字，不解释来源、不对比 Windows。详见 LESSON L018。
>
> T-Wipe 2026-04-18 Phase 6: pre-takeover 内容的历史 plan / design / review-report（含
> `docs/plans/2026-04-12-haofenshu-biz-replication-design.md` /
> `docs/plans/2026-04-13-migration-gate-repair-design.md` /
> `docs/plans/2026-04-14-auth-fail-closed-repair-design.md` /
> `docs/plans/2026-04-14-conduct-roadmap-design.md` 等 64 文件，W4 多 2 份 R4/R5 review report）已加
> `<!-- pre-takeover: archived for history, not active spec -->` 顶部 marker 隔离。
> 这些历史产物仅供追溯，不作活规格使用；活规格以 CLAUDE.md + 当前 plan/handoff 为准。

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
| 扫描切割 | edu-cloud + paper-seg | edu-cloud 内置 OpenCV 切割（auto_detect_cv + pipeline），paper-seg 仍支持本地模式 |

**关键关系**：exam-ai 是本项目的**下游客户端**，通过 REST API 同步数据。每所学校运行独立的 exam-ai 实例，edu-cloud 统一管理。
<!-- key-end -->

<!-- key-start -->
## 启动命令

```bash
# 后端（ECS W4 worktree）
cd /home/ops/projects/edu-cloud
.venv/bin/python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload

# 前端（Vite dev server）
cd /home/ops/projects/edu-cloud/frontend
npm run dev
# → http://0.0.0.0:8080（ECS 远程开发，allowedHosts 锁定）；代理 /api → http://localhost:9000
```

## 前端 serving 架构

用户通过 `https://mcu.asia` 访问 → nginx HTTPS 443 → **serve `frontend/dist/` 静态文件**（不是代理到 Vite dev server）。

```
浏览器 → nginx 443 (try_files $uri /index.html) → frontend/dist/ → 旧 build 产物
         nginx 80  → 301 跳 HTTPS（不走 Vite）
         Vite 8080 → 仅限 curl localhost 直连（开发调试用）
```

**铁律：改了前端代码必须 build 才能让用户看到。**

```bash
cd /home/ops/projects/edu-cloud/frontend && npx vite build
```

- `npm run dev` 只启动 dev server，用户通过 mcu.asia 看不到
- `vitest` 通过 ≠ 用户看到新代码——测试验证逻辑正确性，不验证交付
- 用户说"硬刷新没用"→ 第一反应检查是否忘了 build，不要说"浏览器缓存"

## 测试命令

```bash
# 后端 ECS pytest 实测 @ 2026-04-26：2199 passed / 21 failed（既有债）/ 23 skipped
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q

# 前端 Vitest + happy-dom（frontend/ 961 tests @ 2026-04-27）
cd /home/ops/projects/edu-cloud/frontend && npx vitest run
```
<!-- key-end -->

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
    conduct/                # 管理端操行页面（AppShell 内，权限守卫，classId 从 auth store 读取）
      ConductDashboard.vue  # 德育概览（统计卡片+本周加扣分+积分最高/最低+最近记录）
      ConductPoints.vue     # 积分操作（学生多选+班规快捷按钮+手动输入+最近记录）
      ConductRules.vue      # 班规管理（分类折叠+条目 CRUD+积分标签）
      ConductRankings.vue   # 排��榜（学生/小组 Tab+学期筛选）
      ConductRecords.vue    # 积分记录（分页表格+学生/日期过滤+删除）
      ConductGroups.vue     # 小组管理（卡片网格+成员抽屉+添加/移除）
      ConductSettings.vue   # 德育设置（邀请码+验证方式+模块开关+学期管理）
      ConductParents.vue    # 家长管理（表格+移除）
      ConductExport.vue     # 数据导出（记录/排行榜+日期/学期筛选+Excel 下载）
  components/
    shell/
      AppHeader.vue         # 68px 毛玻璃顶栏（Logo/SchoolContext/搜索/通知铃/角色切换）
      AppSidebar.vue        # 角色过滤侧栏导航（220px/64px 折叠，sidebarConfig 驱动）
      SchoolContext.vue     # 纯展示当前角色上下文名称
      RoleSwitcher.vue      # 角色切换下拉菜单（NDropdown，含头像）
      NotificationBell.vue  # 通知铃铛（NBadge + NPopover，占位）
    ai/
      AiFloatingButton.vue  # 右下角 AI 助手浮动按钮（权限 use_ai_chat 控制可见性）
      AiSlidePanel.vue      # 右侧 400px 滑出 AI 面板（路由变化自动关闭）
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
  card-editor/              # 答题卡编辑器原生 JS（5 模块：model/render/interact/panel/export）
  api/                      # API 调用层（16 模块 + client.js，baseURL /api/v1；conduct.js 含独立 parentClient 用 cp_token；students.js 学生CRUD+导入导出；teachers.js 教师CRUD+导入导出；cards.js 含 renderDocPages 文档渲染）
  config/
    roles.js                # 10 角色枚举 + 旧别名映射 + normalizeRole()
    permissions.js          # 角色→权限映射（镜像后端 core/permissions.py）+ hasPermission()
    sidebarConfig.js        # 角色→侧边栏导航项 JSON 配置（conduct 按 hasPermission 动态过滤：FULL 9 项 platform_admin+district_admin+homeroom / academic_director 8 项 / grade_leader 6 项 / subject_teacher 5 项 / principal 4 项 / parent 3 项 / teaching_research_leader+lesson_prep_leader 0 项）
    dashboardConfig.js      # 角色→仪表盘 KPI/Widget JSON 配置
  stores/
    auth.js                 # Pinia auth（多角色 + switchRole，edu-cloud 版）
    aiChat.js               # AI 对话（SSE + tool_call 展示，exam-ai 版）
    context.js / studio.js  # 云平台上下文/Studio
  router/                   # Vue Router（AppShell 41 子路由含 /ai-grading 无参入口 / 冻结完整版 44 路由在 _frozen/index.full.js；/parent/* 跳过平台 auth）
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
    dashboard.py        # GET /api/v1/dashboard/summary（角色 scope 聚合统计：students/classes/exams/staff/pending_grading/pending_subjects）
    notifications_api.py # GET /api/v1/notifications（通知列表，status/since 过滤）
    ai.py               # AI Agent 路由（AgentRuntime pipeline: DataScope → AuditLogger → AgentContext → AgentRuntime.run() → SSE）
    compat_router.py    # exam-ai 兼容路由（/api 前缀，paper-seg 零改动对接，8 端点）
    module_middleware.py # ModuleCheckMiddleware — 禁用模块 API 硬拦截（JWT active_role_id → school_id 解析）
    # 以下为 re-export stubs，canonical → modules/
    schools.py → modules/school/router.py
    joint_exams.py → modules/exam/joint_exam_router.py
    results.py → modules/exam/results_router.py
    studio.py → modules/studio/router.py
    calendar.py → modules/calendar/router.py
    workspace.py → modules/exam/workspace_router.py
  models/
    base.py             # Base + IdMixin(UUID) + TenantMixin(school_id) + TimestampMixin(UTC)
    school_settings.py  # SchoolSetting（KV 配置）+ SchoolModule（模块开关）+ MODULE_CODES/DEFAULT_ENABLED
    teacher_assignment.py # TeacherAssignment（教师排课记录：教师×班级×科目×学期）
    subject_selection.py # SubjectSelection（学校选考科目组合：物化生/史地政等）
    capability.py       # Capability（学校级角色能力配置：域×操作×角色）
    audit_log.py        # AuditLog（实体变更审计日志）
    agent_profile.py    # AgentProfile（Agent 身份）+ AgentRun（执行记录）
    school.py           # RegisteredSchool（学校档案 + API Key + 心跳）
    platform_user.py    # PlatformUser（4 角色 + bcrypt 密码）
    joint_exam.py       # JointExam + JointExamParticipant + JointExamStudentResult
    score_segment.py    # ScoreSegmentConfig（学校级分数段配置，per school + optional per subject override）
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
    permissions.py      # 34 个 Permission 枚举 + 10 角色 RBAC 映射
    scope_filter.py     # ScopeFilter 工具类（基于 UserRole 注入 WHERE 条件）
  knowledge/
    __init__.py         # 包入口
    loader.py           # 知识库 JSON 文件加载（课标/L0/L1/高考索引）
    store.py            # 内存索引 KnowledgeStore + 全局单例 knowledge_store（关键字搜索）
  ai/
    data_scope.py       # DataScope（frozen 数据可见性快照）+ DataScopeBuilder（10 角色 fail-closed 派生）
    scoped_query.py     # ScopedQuery（统一 scope WHERE 注入 + 参数越权拦截 ScopeViolationError）
    agent_loop.py       # AgentLoop 核心循环（plan→tool exec→answer 状态机，替代旧 agent.py）
    llm_adapter.py      # LLMProxyAdapter（统一 LLM 适配器，走 llm-proxy）
    capability_probe.py # CapabilityProbe（模型能力检测→tier→LoopStrategy）
    sensitivity_router.py # SensitivityRouter（双通道路由，student 工具锁定主通道）
    prompts.py          # build_teacher_prompt（角色感知 system prompt 模板）
    tool_context.py     # ToolContext + ToolResult（统一工具签名 (input, ctx) → ToolResult）
    tool_executor.py    # ToolExecutor + ToolOrchestrator（并行/串行工具执行）
    context_manager.py  # ContextManager（token 计数 + 压缩）
    task_planner.py     # TaskPlanner（多步任务规划，tier≤2 启用）
    session_memory.py   # SessionMemoryExtractor（会话记忆提取，tier=1 启用）
    memory_store.py     # MemoryStore（entity_memory/project_state CRUD + 冲突合并，跨会话持久化）
    memory_extractor.py # MemoryExtractor（会话结束后提取实体记忆并写入 MemoryStore）
    memory_injector.py  # MemoryInjector（会话启动时加载跨会话记忆，格式化注入 system prompt；角色 scope 安全策略）
    schemas.py          # ChatMessage/ToolCall/AgentEvent 数据模型
    anonymizer.py       # 会话级姓名脱敏（字段检测 + student_number 剥离）
    audit.py            # AuditLogger（DB 持久化 AiSession/AiToolCall）
    registry.py         # ToolRegistry + ToolSpec dataclass（元数据：domain/module_code/allowed_roles/risk_level）
    tool_access.py      # ToolAccessResolver（RBAC ∩ Module ∩ Capability 三重过滤）
    models.py           # AiSession/AiToolCall 表
    tools/
      __init__.py       # 触发全部 23 个工具模块注册（62 tools + exam_subject_id 统一查询）
      analytics.py      # L2_cross_school（2）: get_exam_scores/get_class_stats
      analytics_score.py # L2_analytics（5）: exam_summary/distribution/question/student/class scores
      analytics_compare.py # L2_analytics（3）: compare_classes/rank_students/grade_aggregates
      exams.py          # L1_exam（3）: exam_list/detail/subject_questions
      students.py       # L1_student（4）: class_list/roster/search/profile
      bank.py           # L5_bank（2）: error_book/question_stats
      profile.py        # L6_profile（4）: trend/knowledge_map/weakness/error_pattern
      knowledge.py      # L3_knowledge（4）: search_curriculum/textbook/concept/gaokao
      knowledge_db.py   # L3_knowledge_db（2）: knowledge_tree/question_knowledge_points
      grading_ops.py    # L1_exam（3）: grading_progress/quality_report/assign_grading
      actions.py        # L4_action（2）: generate_report/comment
      homework.py       # L2_homework（5）: task list/stats/submit/assign/remedial
      analytics_report.py # L2_analytics（3）: get_score_segments/compare_exams/generate_analysis_report
      knowledge_tree.py # L1_knowledge（1）: edit_knowledge_graph
      conduct.py    # L2_conduct（6）: conduct rankings/records/rules/points/overview/summary
      adaptive.py       # L1_knowledge（1）: diagnose_and_recommend
      card_layout.py    # L1_exam（3）: card_parse_answers, card_auto_layout, card_adjust_layout
      class_report_tool.py # L2_analytics（1）: get_class_report
      exam_overview.py  # L1_exam（1）: get_exam_overview
      findings_tools.py # L1_agent（2）: get_findings, get_agent_tasks
      memory_tools.py   # L1_agent（2）: memory_read, memory_write
      student_diagnosis.py # L6_profile（1）: get_student_diagnosis
      student_profile_tool.py # L6_profile（1）: get_student_learning_profile
  workers/
    grading.py          # process_grading_task（AI 阅卷，微批次并发 GRADING_BATCH_SIZE=20）+ run_post_exam_pipeline（考后处理，已接线 pipeline）
  shared/
    auth.py             # JWT create/decode 工具函数
    upload_validation.py # 图片上传 magic bytes 验证（替代 Python 3.13 废弃的 imghdr）
  config.py             # Settings（DB/Redis/JWT/ENCRYPTION_KEY(PII加密)/LLM(timeout=180s)/GRADING_BATCH_SIZE(20)/UPLOAD_DIR/知识库/AI Agent 配置，BaseSettings）
  database.py           # async engine + session factory（PostgreSQL 连接池 pool_size=20/max_overflow=40/pool_recycle=3600）
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
| API | 276 路由（含 academic 10 + exam schedule 2 + analytics 进阶 8） | 共享 AI 阅卷 |
| Models | 88 表（modules/ 下 18 模块 + core 平台表 + AI Agent 表 + agent evolution 8 表 + score_segment_config + knowledge_tree 3 表 + adaptive 7 表 + academic 3 表 + alembic_version） | — |
| Services | School/JointExam/Results/Paper/Studio/Calendar/Notification/HomeworkTask/HomeworkSubmission/Analytics/Profile/Bank/Pipeline + exceptions | AI grading 生产接入 |
| Core | EventBus（exam.published handler 已接入 pipeline）, RBAC 34 权限 + 10 角色映射 | — |
| AI | 62 tools（23 模块）+ IntentResolver + ModelRouter + ToolAccessResolver + AgentProfile | 常驻巡检 Agent |
| Knowledge | KnowledgeStore（课标/L0/L1/高考索引，关键字搜索，全局单例）+ L3 查询工具（4 tools，启动加载）| — |
| Tests | 2199 passed / 21 failed（既有债）后端 + 961 前端 Vitest（ECS 实测 @ 2026-04-27） | — |
| Modules | 21 模块目录，路由已迁入。技术债 H-01 拆分后：`card` 含 `router.py`(839行) + `card_template_router.py`(230行) + `card_export_router.py`(326行)；`grading` 含 `router.py`(520行) + `grading_review_router.py`(396行) + `prompts/` 子包；`analytics` 含 `router.py`(220行) + `analytics_report_router.py`(585行)。详见 `docs/2026-04-26-tech-debt-audit.md` §修复记录 | — |
| Migrations | Alembic migration（88 表，31 个迁移，含 S1-A T2 `a88094ee4ea6` bank_question +5 列） | — |

## 技术栈

**后端：**
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg (PostgreSQL)
- Alembic (migrations)
- python-jose (JWT) + bcrypt
- arq + Redis (后台任务：联考下发、批量阅卷、报表生成)
- httpx (调用学校端 API)
- opencv-python-headless + pyzbar (扫描图视觉处理：定位点检测/裁切/条码识别)
- Docker + docker-compose (部署)

**前端（`frontend/`）：**
- Vite 7 + Vue 3.5 (Composition API)
- Naive UI 2.44（暗色主题）
- Vue Router 4（AppShell 根布局 + 角色/权限守卫，login 外置 + 41 子路由；完整 44 路由冻结于 _frozen/）
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
| edu-cloud 前端（frontend/） | 5273 / 8080 | Vite dev server，本地默认 5273 / ECS 远程 8080（host 0.0.0.0 + allowedHosts ECS IP）|
| exam-ai | 8000 | 学校端阅卷服务 |
| paper-seg | 8001 | 扫描客户端 |
| paper-skill | 9103 | AI 论文写作服务（外部，REST 客户端通过 PaperService 调用）|
<!-- key-end -->

## 角色体系

### 统一角色体系（edu-cloud 管理，P0 重构后）

> 重构声明（2026-03-21）：edu-cloud 从联考后端升级为统一平台后，
> 学校内角色由 edu-cloud 直接管理，不再由 exam-ai 管理。
> exam-ai 退化为数据采集节点。详见 `docs/plans/2026-03-21-super-platform-design.md` §1。

| 角色 | 作用域 | 核心职责 | 说明 |
|------|-------|---------|------|
| platform_admin | 全局 | 全部权限 | 平台超管 |
| district_admin | 辖区 | 辖区学校管理+跨校分析 | 教育局管理员 |
| principal | 全校 | 审批/学校配置/全局查看（>= 教务查看权） | 校长 |
| academic_director | 全校 | 考试/排课/阅卷/选考运营管理 | 教务主任 |
| teaching_research_leader | 全校·单学科 | 跨年级学科教研、质量分析 | 教研组长 |
| grade_leader | 单年级·全科 | 年级行政、班级对比、年级通知 | 年级组长 |
| lesson_prep_leader | 单年级·单学科·全平行班 | 集体备课、教学进度统一 | 备课组长 |
| homeroom_teacher | 本班全科+任教班本科 | 教师基线+班级通知管理 | 班主任 |
| subject_teacher | 任教班·任教科 | 教师基线（教学/阅卷/作业/论文） | 科任教师 |
| parent | 自己孩子 | 查看成绩/作业/通知 | 家长（企微登录）|

**权限拆分（2026-04-12）**：`MANAGE_SCHOOL_SETTINGS` → `MANAGE_SCHOOL_CONFIG`（校长：KV/模块/能力矩阵）+ `MANAGE_SCHEDULING`（教务：排课/选考）。新增 `MANAGE_EXAMS`（校内考试 CRUD）。详见 `core/permissions.py`。

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
| POST | `/api/v1/auth/login` | 平台用户登录，返回 JWT + roles（含 context: type/id/name + 可选 subject_codes/class_ids） |
| POST | `/api/v1/auth/switch-role` | 切换活跃角色，返回新 JWT + active_role（含 context） |
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/version` | 版本+启动时间 |
| GET | `/api/v1/dashboard/summary` | 仪表盘聚合统计（角色 scope 过滤：students/classes/exams/staff/pending_grading/pending_subjects） |
| GET | `/api/v1/menus` | 动态菜单树（按 current_role + school enabled_modules 过滤；MenuConfig 驱动） |

### 学校管理端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| POST | `/api/v1/schools` | MANAGE_SCHOOLS | 创建学校（返回 API Key） |
| GET | `/api/v1/schools` | VIEW_SCHOOLS | 列表（支持 district/is_active 过滤） |
| GET | `/api/v1/schools/{id}` | VIEW_SCHOOLS | 学校详情 |
| PATCH | `/api/v1/schools/{id}` | MANAGE_SCHOOLS | 更新学校信息 |
| POST | `/api/v1/schools/{id}/rotate-key` | MANAGE_SCHOOLS | 轮换 API Key |

### 学校配置端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/schools/{id}/settings` | MANAGE_SCHOOL_SETTINGS | 获取学校 KV 配置（支持 category 过滤） |
| PATCH | `/api/v1/schools/{id}/settings` | MANAGE_SCHOOL_SETTINGS | 创建/更新配置项 |
| GET | `/api/v1/schools/{id}/modules` | MANAGE_SCHOOL_SETTINGS | 获取全部模块状态（8 个） |
| GET | `/api/v1/schools/{id}/modules/enabled` | 已登录（school scope） | 获取已启用模块代码列表 |
| PATCH | `/api/v1/schools/{id}/modules/{code}` | MANAGE_SCHOOL_SETTINGS | 启用/禁用模块 |

### 排课管理端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/schools/{id}/assignments` | MANAGE_SCHOOL_SETTINGS | 列表（支持 semester/user_id/class_id/subject_code 过滤） |
| POST | `/api/v1/schools/{id}/assignments` | MANAGE_SCHOOL_SETTINGS | 批量创建（一个教师+多班级，幂等） |
| DELETE | `/api/v1/schools/{id}/assignments/{aid}` | MANAGE_SCHOOL_SETTINGS | 删除单条 |
| GET | `/api/v1/schools/{id}/assignments/summary` | MANAGE_SCHOOL_SETTINGS | 按教师聚合摘要 |

### 选考组合端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/schools/{id}/selections` | MANAGE_SCHOOL_SETTINGS | 列表（支持 is_active/mode 过滤） |
| POST | `/api/v1/schools/{id}/selections` | MANAGE_SCHOOL_SETTINGS | 创建（校验科目数量+模式枚举+唯一名） |
| PATCH | `/api/v1/schools/{id}/selections/{sid}` | MANAGE_SCHOOL_SETTINGS | 更新（名称/科目/mode/启停） |
| DELETE | `/api/v1/schools/{id}/selections/{sid}` | MANAGE_SCHOOL_SETTINGS | 删除 |

### 能力配置端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/schools/{id}/capabilities` | MANAGE_SCHOOL_SETTINGS | 获取角色能力矩阵（支持 role 过滤） |
| PATCH | `/api/v1/schools/{id}/capabilities` | MANAGE_SCHOOL_SETTINGS | 修改单个 capability（role + domain + action + enabled） |
| POST | `/api/v1/schools/{id}/capabilities/init` | MANAGE_SCHOOL_SETTINGS | 按默认模板初始化（幂等） |

### 审计日志端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/schools/{id}/audit-logs` | MANAGE_SCHOOL_SETTINGS | 查询审计日志（支持 entity_type/user_id/action/date 过滤，分页） |

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
| PUT | `/api/v1/questions/{id}/content` | 更新题干/参考答案（MANAGE_EXAMS，含 content/content_images/reference_answer/reference_answer_images） |
| POST | `/api/v1/questions/{id}/content/upload-image` | Multipart 上传题目图片（MANAGE_EXAMS），返回 `{"path": "/uploads/questions/..."}` |
| GET/POST | `/api/v1/classes`, `/api/v1/students` | 班级/学生管理（含 grade/selection/subject_code 过滤 + 导入导出） |
| GET | `/api/v1/grades` | 年级列表 |
| * | `/api/v1/teachers` | 教师 CRUD + 导入导出（15 列档案 + 角色/学科/班级） |
| * | `/api/v1/card/*` | 答题卡生成/骨架/条码/编辑器布局CRUD/小微排版/文档渲染（24 端点，含 upload-answer + auto-layout + 3 Agent 工具 + render-doc-pages） |
| * | `/api/v1/templates/*` | 模板 CRUD |
| * | `/api/v1/scan/*` | 扫描上传/任务管理 |
| POST | `/api/v1/scan/pipeline/scan-dir` | 扫描目录结构，返回科目子文件夹和图片统计 |
| POST | `/api/v1/scan/pipeline/start` | 启动扫描切割流水线（subject_id + image_dir + 可选 tpl_path） |
| GET | `/api/v1/scan/pipeline/progress` | 获取流水线进度 |
| POST | `/api/v1/scan/pipeline/stop` | 停止流水线 |
| POST | `/api/v1/scan/pipeline/preview` | 预览扫描图切割标注（base64） |
| POST | `/api/v1/scan/pipeline/import-tpl` | 导入 .tpl 文件到 Template 表 |
| GET | `/api/v1/scan/pipeline/scan-image` | 提供扫描图片 HTTP 访问（模板编辑器用，限 uploads 目录） |
| POST | `/api/v1/scan/pipeline/auto-detect-cv` | OpenCV+LLM 混合检测答题卡区域（VIEW_GRADING） |
| GET | `/api/v1/scan/pipeline/cv-template` | 查询科目已有 CV 检测 Template（A/B 面，VIEW_GRADING） |
| POST | `/api/v1/scan/pipeline/save-cv-template` | 保存检测结果为 Template（VIEW_GRADING，自动创建 choice/essay Question） |
| * | `/api/v1/grading/*` | AI 阅卷/评分规则/教师审核 |
| GET | `/api/v1/grading/dispatch/status` | 科目阅卷状态聚合（exam_id 查询参数，返回各科目 subject_code/stage/统计+questions 逐题明细；stage: idle→pending_detect→pending_cut→cutting→ready→ai_grading→reviewing→done） |
| POST | `/api/v1/grading/rubrics` | 创建/更新评分细则（MANAGE_GRADING，criteria 校验：blankNo/score/answer 必填+总分守恒） |
| GET | `/api/v1/grading/rubrics/{question_id}` | 获取题目评分细则 |
| POST | `/api/v1/grading/rubrics/generate` | AI 生成评分细则（MANAGE_GRADING，题干+答案+图片→LLM→criteria，upsert Rubric） |
| POST | `/api/v1/grading/tasks` | 创建 AI 阅卷任务（支持 question_id 题目级；前置校验：归属/主观题/Rubric/Answer；重跑清理 ai_pending/ai_done、保护 confirmed）|
| GET | `/api/v1/grading/tasks` | 列出本校 AI 阅卷任务 |
| GET | `/api/v1/grading/tasks/{task_id}` | 阅卷任务详情 |
| POST | `/api/v1/grading/assignments` | 创建阅卷分配（MANAGE_GRADING） |
| GET | `/api/v1/grading/assignments` | 列出阅卷分配（VIEW_GRADING，需 exam_id） |
| GET | `/api/v1/grading/progress/{exam_id}` | 阅卷进���汇总（VIEW_GRADING） |
| GET | `/api/v1/grading/quality-report/{exam_id}` | 质量检查报告（VIEW_GRADING） |
| POST | `/api/v1/exams/{id}/publish` | 发布成绩（MANAGE_EXAM_RESULTS，前置条件检查） |
| POST | `/api/v1/exams/{id}/archive` | 归档考试（MANAGE_EXAM_RESULTS） |
| * | `/api/v1/marking/*` | 人工阅卷/分配（一题多人+answer_count 配额+DELETE /assignments/{id}）/导出 |
| * | `/api/v1/analytics/*` | 统计分析（摘要/分布/题目/年级，支持 subject_id 单参数查询） |
| GET | `/api/v1/analytics/segments/config` | MANAGE_SCHOOL_SETTINGS | 获取本校分数段配置（默认+科目覆盖） |
| PUT | `/api/v1/analytics/segments/config` | MANAGE_SCHOOL_SETTINGS | 创建/更新分数段配置（upsert） |
| DELETE | `/api/v1/analytics/segments/config/{subject_code}` | MANAGE_SCHOOL_SETTINGS | 删除科目覆盖配置 |
| POST | `/api/v1/analytics/report/query` | 已登录 | 自定义分析构建器（按角色裁剪 metrics） |
| GET | `/api/v1/analytics/report/trend/grade` | 已登录（校级+） | 年级成绩趋势 |
| GET | `/api/v1/analytics/report/trend/class` | 已登录（非家长） | 班级成绩趋势 |
| GET | `/api/v1/analytics/report/trend/student` | 已登录 | 学生成绩趋势（班级/guardian 校验） |
| POST | `/api/v1/analytics/report/export` | GENERATE_REPORT | 生成分析报告文档（走 Studio） |
| GET | `/api/v1/analytics/power-options` | 已登录 | 级联筛选树（年级→班级→科目→考试，RBAC 过滤） |
| POST | `/api/v1/analytics/level-score/convert` | MANAGE_EXAM_RESULTS | 等级赋分转换（原始分→百分位等级→线性插值赋分） |
| GET | `/api/v1/analytics/exam/{id}/question-insights` | 已登录 | 题目错因聚合 + 难度/区分度（AI 阅卷数据） |
| GET | `/api/v1/analytics/exam/{id}/diagnosis` | 已登录 | 考试诊断文本（模板拼接，ORC-007 不调 LLM） |
| GET | `/api/v1/analytics/exam/{id}/student-rankings` | 已登录 | 学生排名 + 进退步 delta |
| GET | `/api/v1/analytics/exam/{id}/critical-students` | 已登录 | 临界生筛选（差 N 分及格/优秀） |
| GET | `/api/v1/analytics/exam/{id}/class-boxplot` | 已登录 | 各班分数箱线图 |
| GET | `/api/v1/analytics/exam/{id}/class-knowledge` | 已登录 | 班级×知识点掌握率热力图 |
| GET | `/api/v1/analytics/exam/{id}/class-error-patterns` | 已登录 | 班级错误模式对比 |
| GET | `/api/v1/profile/students/{id}/ai-diagnosis` | VIEW_SCORES | 学生个体 AI 诊断（模板拼接） |
| * | `/api/v1/knowledge/*` | 知识点 CRUD/树查询/关联 |
| POST | `/api/v1/pipeline/run/{id}` | 数据流水线触发 |
| * | `/api/v1/llm-config/slots` | LLM 槽位管理 |
| PUT/GET | `/api/v1/exams/{id}/schedule` | 考试排程（时间/地点） |

### 教务管理端点（JWT 认证）

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/v1/academic/semesters` | 创建学期 |
| GET | `/api/v1/academic/semesters` | 列出学期 |
| GET | `/api/v1/academic/semesters/current` | 获取当前学期 |
| PATCH | `/api/v1/academic/semesters/{id}` | 更新学期 |
| POST | `/api/v1/academic/semesters/{id}/activate` | 激活学期 |
| PUT/GET | `/api/v1/academic/periods` | 时段管理 |
| GET | `/api/v1/academic/timetable` | 查询课表 |
| PUT | `/api/v1/academic/timetable/{class_id}` | 保存班级课表 |
| GET | `/api/v1/academic/timetable/stats` | 课表统计 |

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

### 作业管理端点（JWT 认证，Phase 2.2）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| POST | `/api/v1/homework/tasks` | MANAGE_HOMEWORK | 创建作业 |
| GET | `/api/v1/homework/tasks` | VIEW_HOMEWORK | 列出作业（支持 class_id/subject_code/status/task_type 过滤） |
| GET | `/api/v1/homework/tasks/{id}` | VIEW_HOMEWORK | 作业详情（含内嵌 stats） |
| PATCH | `/api/v1/homework/tasks/{id}` | MANAGE_HOMEWORK | 更新作业（仅 draft） |
| POST | `/api/v1/homework/tasks/{id}/publish` | MANAGE_HOMEWORK | 发布作业（自动创建提交记录） |
| POST | `/api/v1/homework/tasks/{id}/close` | MANAGE_HOMEWORK | 关闭作业 |
| DELETE | `/api/v1/homework/tasks/{id}` | MANAGE_HOMEWORK | 删除作业（仅 draft） |
| GET | `/api/v1/homework/tasks/{id}/submissions` | VIEW_HOMEWORK | 列出提交记录 |
| POST | `/api/v1/homework/tasks/{id}/submissions/{sub_id}/submit` | VIEW_HOMEWORK | 学生提交作业 |
| POST | `/api/v1/homework/tasks/{id}/submissions/{sub_id}/grade` | MANAGE_HOMEWORK | 单个批改 |
| POST | `/api/v1/homework/tasks/{id}/grade-batch` | MANAGE_HOMEWORK | 批量批改 |
| GET | `/api/v1/homework/tasks/{id}/stats` | VIEW_HOMEWORK | 提交/批改统计 |

### 知识树端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/knowledge-tree/graph` | VIEW_KNOWLEDGE_TREE | 获取知识图谱（{navigation: ModuleNav[], graph: {nodes, edges}}，module 过滤，include_draft 发布过滤，nodes 只含 L1 concept，v2: description/hard_counts/external_refs/confidence/review_status，v3 合并 concept_stats: exam_frequency/exam_coverage/avg_difficulty/importance_score/textbook_chapters/study_unit_id/estimated_minutes/prerequisite_depth/planning_weight） |
| GET | `/api/v1/knowledge-tree/graph/{node_id}/detail` | VIEW_KNOWLEDGE_TREE | 获取概念节点详情（课标/教材/DA/真题/教材证据，从 knowledge.db 聚合） |
| GET | `/api/v1/knowledge-tree/graph/{node_id}/exam-items` | VIEW_KNOWLEDGE_TREE | 概念关联高考真题分页（concept→DA→q_matrix→assessment_items，knowledge.db 缺失降级 total=0，page/page_size 参数；response_model=ExamItemsResponse；DISTINCT + IN 均按 item_id ASC 稳定排序，详情按 page_ids 顺序回写） |
| GET | `/api/v1/knowledge-tree/stats/overview` | VIEW_KNOWLEDGE_TREE | 图谱统计概览（total_concepts/total_edges + exam_freq_distribution{high≥500/mid≥50/low≥1/zero} + module_stats{avg_freq/exam_coverage}，module 参数过滤；response_model=StatsOverviewResponse） |
| GET | `/api/v1/knowledge-tree/mastery` | VIEW_KNOWLEDGE_TREE | 获取学生掌握度（聚合到概念和模块级别，排除 BigConcept，需 student_id） |
| GET | `/api/v1/knowledge-tree/search` | 已登录 | 搜索知识点（name+aliases+description，只返回 concept） |
| GET | `/api/v1/knowledge-tree/quality-check` | EDIT_KNOWLEDGE_TREE | 质量巡检（6 规则：孤立/连通分量/低置信度/跨模块/无描述/rejected 堆积，module 过滤） |
| POST | `/api/v1/knowledge-tree/edit` | EDIT_KNOWLEDGE_TREE | 编辑知识图谱（add/remove/update node/edge + set_review_status node/edge + reorder） |

### 学情画像端点（JWT 认证，Phase 3.1）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/profile/students/{id}/trend` | VIEW_SCORES | 成绩趋势（历次快照，支持 subject_code 过滤） |
| GET | `/api/v1/profile/students/{id}/knowledge` | VIEW_SCORES | 知识点掌握度列表（支持 course_code 过滤） |
| GET | `/api/v1/profile/students/{id}/error-patterns` | VIEW_SCORES | 错误模式分析（支持 subject_code 过滤） |
| GET | `/api/v1/profile/class/weakness` | VIEW_SCORES | 班级薄弱知识点 TOP N（需 class_id） |

### 题库 + 错题本端点（JWT 认证，Phase 3.1）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/bank/questions` | VIEW_QUESTION_BANK | 题库列表（支持 type/difficulty 过滤） |
| GET | `/api/v1/bank/questions/{id}` | VIEW_QUESTION_BANK | 题库题目详情 |
| GET | `/api/v1/bank/error-book/{student_id}` | VIEW_SCORES | 学生错题本（支持 mastery_status 过滤） |
| GET | `/api/v1/bank/error-book/{student_id}/stats` | VIEW_SCORES | 错题统计（按掌握状态分组） |

### AI Agent 端点（JWT 认证，Batch 4 迁入）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/ai/health` | 无 | 工具数量 + 状态 |
| POST | `/api/v1/ai/chat` | USE_AI_CHAT | SSE 流式对话（multi-turn session，llm-proxy slot=ai-chat） |
| GET | `/api/v1/ai/sessions` | 已登录 | 列出当前用户的活跃会话（owner 隔离） |
| DELETE | `/api/v1/ai/sessions/{session_id}` | 已登录 | 删除会话（仅 owner，他人 403） |

### exam-ai 兼容端点（`/api` 前缀，paper-seg 零改动对接）

> **退役计划**：8 端点已注入 `DeprecationWarning` + Response header (`Deprecation: true` / `Sunset` / `Link`)，目标退役 **2026-07-31**。详见 `docs/plans/compat-router-deprecation.md`。

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/auth/login` | 兼容登录（忽略 school_code，走 edu-cloud 用户认证） |
| GET | `/api/exams` | 列出当前学校考试 |
| GET | `/api/exams/{id}/subjects` | 列出考试科目 |
| GET | `/api/templates/{subject_id}/{side}` | 获取模板（image_size 格式兼容） |
| POST | `/api/scan/tasks` | 创建扫描任务 |
| PATCH | `/api/scan/tasks/{id}` | 更新扫描进度 |
| POST | `/api/scan/upload` | 上传切图（Multipart） |
| POST | `/api/scan/upload-objective` | 上传选择题结果（自动判分） |

### 操行管理-家长端点

| 方法 | 路径 | 认证 | 用途 |
|------|------|------|------|
| GET | `/api/v1/conduct/invite/{code}/info` | 无 | 验证邀请码，返回班级/学校信息 |
| POST | `/api/v1/conduct/parent/register` | 无 | 家长注册（手机号+邀请码） |
| POST | `/api/v1/conduct/parent/login` | 无 | 家长登录（手机号+密码） |
| GET | `/api/v1/conduct/parent/me` | JWT | 当前家长信息+已绑定孩子列表 |
| POST | `/api/v1/conduct/parent/bind` | JWT | 绑定孩子（身份验证） |
| GET | `/api/v1/conduct/parent/children` | JWT | 已绑定孩子列表+积分汇总 |
| GET | `/api/v1/conduct/parent/children/{student_id}/records` | JWT | 孩子操行记录（分页） |
| GET | `/api/v1/conduct/parent/children/{student_id}/rankings` | JWT | 孩子班级排名 |
| GET | `/api/v1/conduct/parent/classes/{class_id}/rules` | JWT | 班规查询（分类+条目嵌套） |
| PUT | `/api/v1/conduct/parent/profile` | JWT | 更新家长资料（仅 display_name） |
| PUT | `/api/v1/conduct/parent/password` | JWT | 修改密码 |

### 操行管理-管理端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/conduct/classes/{class_id}/config` | MANAGE_CONDUCT_PARENTS | 获取班级操行配置 |
| PUT | `/api/v1/conduct/classes/{class_id}/config` | MANAGE_CONDUCT_PARENTS | 更新操行配置（verify_code_type/required_parent_fields/is_active） |
| POST | `/api/v1/conduct/classes/{class_id}/config/regenerate-code` | MANAGE_CONDUCT_PARENTS | 重新生成邀请码 |
| GET | `/api/v1/conduct/classes/{class_id}/parents` | MANAGE_CONDUCT_PARENTS | 列出班级已绑定家长 |
| DELETE | `/api/v1/conduct/classes/{class_id}/parents/{user_id}` | MANAGE_CONDUCT_PARENTS | 移除家长绑定关系 |
| POST | `/api/v1/conduct/classes/{class_id}/records` | MANAGE_CONDUCT | 添加积分记录（单个/多个学生） |
| POST | `/api/v1/conduct/classes/{class_id}/records/batch` | MANAGE_CONDUCT | 批量添加积分（/records 别名） |
| GET | `/api/v1/conduct/classes/{class_id}/records` | VIEW_CONDUCT | 查询积分记录（分页+学生/日期过滤） |
| DELETE | `/api/v1/conduct/classes/{class_id}/records/{record_id}` | MANAGE_CONDUCT | 删除积分记录 |
| GET | `/api/v1/conduct/classes/{class_id}/rankings/students` | VIEW_CONDUCT | 学生积分排行榜 |
| GET | `/api/v1/conduct/classes/{class_id}/rankings/groups` | VIEW_CONDUCT | 小组积分排行榜 |
| GET | `/api/v1/conduct/classes/{class_id}/rules` | VIEW_CONDUCT | 获取班规（分类+条目嵌套） |
| POST | `/api/v1/conduct/classes/{class_id}/rules/categories` | MANAGE_CONDUCT_RULES | 创建班规分类 |
| PUT | `/api/v1/conduct/classes/{class_id}/rules/categories/{cat_id}` | MANAGE_CONDUCT_RULES | 更新班规分类 |
| DELETE | `/api/v1/conduct/classes/{class_id}/rules/categories/{cat_id}` | MANAGE_CONDUCT_RULES | 删除班规分类（级联删除条目） |
| POST | `/api/v1/conduct/classes/{class_id}/rules/categories/{cat_id}/items` | MANAGE_CONDUCT_RULES | 创建班规条目 |
| PUT | `/api/v1/conduct/classes/{class_id}/rules/categories/{cat_id}/items/{item_id}` | MANAGE_CONDUCT_RULES | 更新班规条目 |
| DELETE | `/api/v1/conduct/classes/{class_id}/rules/categories/{cat_id}/items/{item_id}` | MANAGE_CONDUCT_RULES | 删除班规条目 |
| GET | `/api/v1/conduct/classes/{class_id}/groups` | VIEW_CONDUCT | 列出小组及成员 |
| POST | `/api/v1/conduct/classes/{class_id}/groups` | MANAGE_CONDUCT | 创建小组 |
| DELETE | `/api/v1/conduct/classes/{class_id}/groups/{group_id}` | MANAGE_CONDUCT | 删除小组（级联删除成员） |
| POST | `/api/v1/conduct/classes/{class_id}/groups/{group_id}/members` | MANAGE_CONDUCT | 批量添加小组成员 |
| DELETE | `/api/v1/conduct/classes/{class_id}/groups/{group_id}/members/{student_id}` | MANAGE_CONDUCT | 移除小组成员 |
| GET | `/api/v1/conduct/classes/{class_id}/semesters` | VIEW_CONDUCT | 列出学期 |
| POST | `/api/v1/conduct/classes/{class_id}/semesters` | MANAGE_CONDUCT_RULES | 创建学期 |
| PUT | `/api/v1/conduct/classes/{class_id}/semesters/{semester_id}/activate` | MANAGE_CONDUCT_RULES | 激活学期（其他学期自动停用） |
| GET | `/api/v1/conduct/classes/{class_id}/export/records` | EXPORT_CONDUCT | 导出积分记录 Excel（支持日期过滤） |
| GET | `/api/v1/conduct/classes/{class_id}/export/rankings` | EXPORT_CONDUCT | 导出积分排行榜 Excel（支持学期过滤） |

### 未实现端点（规划中）

- 共享 AI 阅卷（`grading-request`/`grading-result`）
- 统一题库
- 高级跨校分析（趋势/对比图表）

## 关联项目

> ECS 单一环境（L018）：关联项目均为独立 repo，不在本 worktree 同目录。运行/部署位置见各自 repo 或 server-rules.md。

| 项目 | 关系 |
|------|------|
| exam-ai | 学校端，本项目的下游客户端（退化为数据采集节点）|
| paper-seg | 扫描端（本地运行），通过 `/api` 兼容层连接 edu-cloud |
| paper-skill | AI 论文写作服务（外部 REST，端口 9103），edu-cloud 通过 PaperService 调用 |

## 数据库

```
# .env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/edu_cloud
```

生产环境使用 PostgreSQL（连接池 20+40，pool_recycle=3600）。开发/测试使用 SQLite（`sqlite+aiosqlite`，无连接池）。

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
| 业务逻辑反哺设计 | `docs/plans/2026-03-29-business-logic-backfill-design.md` | Phase 1-4 分层反哺 + Agent 深度嵌入架构 |
| AI Agent 设计（旧） | `docs/plans/2026-03-16-ai-agent-design.md` | Agent Phase 1-4 架构设计（554 行，§14 含 API→Service 分层）|
| edu-agent 设计（当前） | `docs/plans/2026-04-03-edu-agent-design.md` | Claude Code 裁剪架构，30 Tasks / 7 Batches / 39 工具 / 1124 tests [实现完成] |
| edu-agent 演进设计 | `docs/plans/2026-04-04-agent-evolution-design.md` | DataScope + WorkflowEngine + W1/W3/W6 + IntentRouter，20 Tasks / 6 Batches / 1325 tests [实现完成] |
| 分析报告设计 | `docs/plans/2026-04-05-analytics-report-design.md` | 分数段配置 + 自定义分析构建器 + 跨考试三维趋势 + PDF 导出，13 Tasks / 1359 tests [实现完成] |
| Phase 2 跨会话记忆 | `docs/plans/2026-04-05-agent-evolution-design.md` §3 | EntityMemory + ProjectState + Episodic Memory，7 Tasks / 62 tests [实现完成] |
| Agent Runtime 架构升级 | `docs/plans/2026-04-05-agent-runtime-design.md` | AgentRuntime 多入口 + ModelRouter 双层模型 + OutputValidator 防幻觉，9 Tasks [实现完成] |
| Agent 韧性与验证增强 | `docs/plans/2026-04-06-agent-resilience-design.md` | P0 bug fix(4) + P1 韧性(2) + P2 验证(3) + P3 配置(2)，11 Tasks / 1543 tests [实现完成] |
| 自适应学习系统 | `docs/plans/2026-04-06-adaptive-learning-design.md` | BKT 掌握度 + 路径规划 + 选题器 + Agent 工具，10 Tasks / 1582 tests [实现完成] |
| 知识树可视化 | `docs/plans/2026-04-05-knowledge-tree-design.md` | AntV G6 力导向图 + 投影同步 + 多角色权限 + Agent 编辑工具 [实现完成] |
| 知识图谱层级重构 | `docs/plans/2026-04-09-knowledge-graph-restructure-design.md` | 4 层导航（Module→BigConcept→Concept→Evidence）+ L1-only 图谱 + search API + 审核状态机，10 Tasks / 168 tests [实现完成] |
| 知识图谱多层教学模型 Phase 1 | `docs/plans/2026-04-09-knowledge-graph-model-design.md` | edge review_status + Graph API v2 + 质量巡检 6 规则 + 发布过滤 + 审查工作台前端，9 Tasks / 124+78 tests [实现完成] |
| 知识图谱教师工作台 Phase 2 | `docs/plans/2026-04-10-teacher-workbench-design.md` | 固定分层教师工作台（ModuleOverviewPanel / ConceptMapPanel / ConceptFocusOverlay）+ layoutEngine toposort + BigConcept 分带 + 跨模块徽标 + 删除 GraphPanel，6 Tasks / 2 Batches / +43 tests [实现完成] |
| 知识图谱教师工作台 Phase 2.5 | `docs/plans/2026-04-10-teacher-workbench-phase2.5-design.md` | 清理 Phase 2 test_debt：焦点模式节点/边淡化（`setElementState` + state spec + `buildVisibleEdgeList` helper + createGraph 末尾重放）+ 跨模块徽标悬停展开 peer 列表（G6 Tooltip plugin，async getContent）；桥接/对比边统一标记 deferred→Phase 3。focusedNodeId 保持组件内部 ref。3 Tasks / 1 Batch / 182 tests (160+22)，GPT 2 轮审查通过（R1 FAIL F001-F003 test-gap → R2 PASS resolved-correct）[实现完成] |
| **F003 Question 写入责任链重设 [实现完成]** | `docs/plans/2026-04-11-f003-question-writeback-design.md` | 新建 `publish_service.py`（upsert Question/Template + publish_card_atomic 原子事务）+ 前端 publishCard 单次 POST 重写 + pipeline_router build_pipeline_save_answer_fn 工厂 + Question UniqueConstraint migration。13 Tasks / 3 Batches / 6 Gates (Plan R7 + Code ×3 R3 + Integration + Reconciliation)，29 新测试。→ `docs/plans/2026-04-11-f003-question-writeback-design.md` |
| **阅卷调度全流程改造 [实现完成]** | `docs/plans/2026-04-12-grading-dispatch-design.md` | GradingTasksPage → GradingDispatchPage：扫描→选择题自动判分→AI 阅卷→校对统一入口。pipeline_router start_pipeline 装配 save_objective_fn（Template + tpl_path 双分支，tpl_path fallback 按 Question.name 题号映射）+ GET /grading/dispatch/status 聚合科目阶段。10 Tasks / 1 Batch，Gate 1 Plan Review R1-R3 FAIL→PASS（14 findings 落入 plan），Gate 2 Code Review R1-R3 FAIL→PASS（F001/F002/F004/R2-F005 resolved-correct，F003 deferred 到 conduct 模块），5/5 wiring tests + 前端 190/190 PASS。→ `docs/plans/2026-04-12-grading-dispatch-design.md` |
| **德育模块（conduct）[实现完成]** | `docs/plans/2026-04-12-conduct-module-design.md` | class-points 全量吸收为 edu-cloud 德育板块。8 ORM 表 + 5 Permission + 6 Agent tools + 家长端（邀请码+手机号+绑定验证）+ 管理端（积分/班规/小组/学期/导出）+ AES-256-GCM PII 加密。22 Tasks / 7 Batches。**Gate 2 R1 FAIL → R2 修复 → R2 FAIL → R3 修复 → R3-R1 FAIL (F007) → R3-R2 PASS**。R2：F001 Alembic + F002 class-scope/resource-affinity 守卫 + F003 Agent 工具 DataScope + F004 get_children + F005 phone Option A + F006 导出入口级测试。**R3 (Batch 7 Task 19-22+24)**：F002 body-field 越权关闭（check_rule_item_class + check_students_class 守卫覆盖 add_points rule_item_id / group_members student_ids，+3 红测）+ N001 id_card 后 6 位契约回退（`stored[-6:] != verify_code`，Option A 锁定，design.md §3 sentinel，+2 反向红测）+ F004 前端字段契约测试（`frontend/src/pages/parent/__tests__/ParentRules.spec.js` vitest）+ F006 records 导出断言升级（openpyxl + 真实 operator）+ F007 rankings 排序+聚合断言（2 学生×4 记录，断言总分 + ORDER BY desc）。conduct tests ECS pytest 实测 68 passed @ 2026-04-18。F001 Alembic SQLite deferred 到 haofenshu-phase1 Migration Gate Repair。Round 3 commits: e584e6a..93f0b60。→ `docs/plans/2026-04-12-conduct-module-design.md` |
| **好分数业务复刻 Phase 1 [Nuxt 骨架已退役 2026-04-26；Batch 1 ✅ / Batch 2 ✅ / Batch 3 已废弃]** | `docs/plans/2026-04-12-haofenshu-biz-replication-design.md` + `docs/plans/2026-04-12-haofenshu-phase1-plan.md` | **Nuxt 骨架已退役，frontend/（Naive UI）为唯一前端。以下为历史记录。** **蓝图**：8 模块 45 页面 stub + 后端动态菜单系统 + 预聚合数据模型（ClassAnalysis/StudentAnalysis/StudentKnpMastery）+ ExamResult rank 字段。3 Batch × 12 Task，4 Gate（Gate 1 plan + Gate 2 × 3 Batch）。**Batch 1 (Task 1-3, Schema + Menu API)**：menu_configs + MenuService + GET /api/v1/menus 动态菜单（role × module 双维过滤）+ seed_menus 8 模块 42 子菜单；commit 3488b52 追认挂载 conduct_admin_router（F002 approved 扩大 Batch 1 范围，28 端点 /api/v1/conduct/classes/*）。**Gate 1 Plan R5 PASS** + **Gate 2 Code R1 FAIL (F001/F002/F003) → R2 PASS** (12/12 menu+migration tests + R2-F001 LOW design-concern 不阻塞; commits e64957a → ef8a32a)。**Batch 2 (Task 4-9, Frontend 骨架, 2026-04-13)**：[已退役] Nuxt 3.17 + Element Plus + Pinia + 品牌色 SCSS (T4) / auth+context store + global middleware + 8 vitest tests (T5) / useApi composable 27 方法 + 4 vitest tests (T6) / useMenus + TopNav + SubNav + UserDropdown (T7) / 三种 layout default/fullscreen/auth (T8) / login + home 模块卡片网格 + index 重定向 (T9)。**vitest 12/12 PASS**，后端零改动。**独立 Gate 4 步**：①Nuxt dev ✅ ②login ✅ ③④ deferred (GPT 独立验证：9000 常驻后端进程陈旧，fresh 9001 对照实例正常返回 6 模块)。commits 08d86f0..78e0764。**Gate 2 Code R1 FAIL** (2026-04-13 23:53)：**B2-F001** MED code-bug — [已退役] lockfile 不可复现（`npm ci` 失败 + `npm ls` invalid）；**B2-F002** MED code-bug — `useMenus.ts` 吞错破坏 plan Task 8 fail-closed 契约（触及 fallback strategy + lifecycle 红旗模式，已出独立修复设计 `docs/plans/2026-04-14-auth-fail-closed-repair-design.md` 以 AuthError sentinel + 职责分层 + Fix Intent Card 4 ORC + 3 反证护航）；**B2-F003** LOW design-concern — Step 3/4 归因措辞不准（不阻塞）。**R2 Executor 修复** (commits 8daa076 + 5bf5c27)：24/24 Vitest PASS，反证 3 条独立复现通过。**Gate 2 Code R2 FAIL** (2026-04-14 07:35)：**B2-F001 contested** — `npm ci` 产生 8+ 条非废弃 EBADENGINE 警告（lockfile 要求 node ≥20.19.0，仓库无 engines/.nvmrc，环境 v20.18.0）；**B2-F002 verified** ✅ (AuthError 三层传递 + 4 slices + 3 反证全通)；**B2-F003 contested** — R2 交接单 L171 残留旧表述"WSL hot-reload"未删（L174 有新表述 = 新旧混合）。**Round 3 Executor 交接卡** `docs/plans/2026-04-14-haofenshu-phase1-batch2-r3-handoff.md` 已就绪（Planner 决策方案 A + 顺手 X，用户 L017 approved behavior_change：本地 Node 升级 **≥22.12.0**（覆盖 lockfile 里所有 dep 的 runtime 要求，含 `>=20.19.0` 和 `>=22.12.0` 两档） + `package.json` engines.node + `.nvmrc` 锁定 Node 版本 + R2 交接单 L171 旧表述 WSL hot-reload 删除 + plan risk_modules 追认 `package.json`/`package-lock.json`）。R3 scope 铁律：禁改 lockfile / 禁改应用代码（B2-F002 verified，AuthError 链路不动）/ 禁降 nitropack 等核心依赖（方案 B rejected）/ 禁 --legacy-peer-deps。gates.json R2 FAIL 回执已校正 raw_output_hash 指向 authoritative FAIL log（commit f539a5f，双审查 audit trail 保留 SECONDARY PASS log 副本）。**R3 Executor 修复完成** (2026-04-14 09:05)：B2-F001 方案 A 落地——`package.json` 追加 `engines.node: ">=22.12.0"` + `.nvmrc` 新建锁 `22.12.0`（portable Node 22.22.2 at `~/bin/node-v22.22.2-win-x64/`，winget install 1603 因 node.exe 被 Claude Code 占用+MsiSystemRebootPending 失败，改用 zip 解压 + `~/.bashrc` PATH 前置，不覆盖系统 Node 20.18）；B2-F003 顺手——R2 handoff §6 改为"根因定论"精简段，删除原表述 block quote，`grep -c "hot-reload"` → 0。**7 项验证断言全通过**：node v22.22.2 / npm ci --ignore-scripts exit 0 706 packages / EBADENGINE 0 / npm ls invalid+extraneous 0 / npx nuxt prepare exit 0 / Vitest 24/24 PASS / hot-reload 0。R3 交接单 `docs/plans/2026-04-14-haofenshu-phase1-review-handoff-batch2-r3.md`。**Gate 2 Code R3 PASS** (2026-04-14 09:25, commit 6ddb19c)：GPT 独立复现 7 项断言全通 + B2-F001/F002/F003 全 verified，**Batch 2 Gate 2 闭环**（code_review_batch2.status=pass, report_path 锚定 R3 报告）。**Batch 3 Executor 交接卡** `docs/plans/2026-04-14-haofenshu-phase1-batch3-handoff.md` 已就绪（Planner 追加 3 项前置修复：R4 useMenus startsWith 分隔符 + R1 后端 E2E 启动脚本化 + plan risk_modules 追认 `package.json`/`package-lock.json`）。**Batch 3 (Task 10-12, PowerFilter + 45 页面 stub + 端到端)** 已废弃（Nuxt 骨架退役）。→ `docs/plans/2026-04-12-haofenshu-biz-replication-design.md` |
| **好分数业务复刻 Phase 2 [S1-A ✅ 闭环 (plan_review=manual_override + code_review_batch1=PASS @ 2026-04-24T19:31) / S1-B/C/D 待启动]** | `docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md` (v0.3 §4.2 基线漂移修正) + `docs/plans/2026-04-24-haofenshu-s1-l1-data-layer-plan-review.md` (9 findings: F001 alembic down_revision / F002 ORM 注册机制 / F003-6 测试契约+Contract Pack / F009 subject vs course 参数语义) | **蓝图**：4 Sprint 分层（L1 数据→L2 服务→L3 编排→L4 治理）填补好分数业务闭环（题库→组卷→作业→错题→推送）。S1 Plan R1 FAIL (commit 97601bd, 6 HIGH + 3 MED) 后按路径 A 拆 topic 串行推进：**S1-A bank_question ✅ 闭环** (8 commit e237c6c..86b4ca5: T0 baseline 修正 + T1 ORM +5 字段 + T0.5 前置 multi-base fix + T2 migration a88094ee4ea6 + T3 smoke 6 tests + T4 Gate/handoff + T5 codex-review R1 PASS；有益副作用 baseline 22→21 failed + 1→0 error) → S1-C grades+Class.grade_id+teaching_plans+PaperAccessLevel (down_revision=a88094ee4ea6) → S1-B concept.depth_level → S1-D StudentProfileView VO。每条 migration linear chain 自包含 up/down，链首 `down_revision=a8c7d2e4f135`（2026-04-24 R2 后基线漂移修正锚点，plan v0.2/R1/R2 时为 `36e25241e55d`，post-1716bfe conduct migration 后 head 上移一环，见 plan.md E-002）。**前置治理**：commit 20a6961 修 pre-existing multi-base bug (f7a3b2c1d456.down_revision None→'8b3f659c1a2a')，linear chain 归一。→ `docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md` |
| **Migration Gate 方言中立性修复 [实现完成]** | `docs/plans/2026-04-13-migration-gate-repair-design.md` | F001 R1 独立修复设计。6 个历史 Alembic migration 的 DDL 构造改为 SQLite + PG 双方言兼容：1a325e38e941（UniqueConstraint 内嵌 create_table）、b08103b3a6f5/a370e2771c6d/2a40f59215de/52af1c37bf14/c9587c787c6b（batch_alter_table 包装独立 create_unique_constraint / alter_column / drop_column / drop_constraint）。PG 上 DDL 等价（已 stamped 数据库零重放），SQLite smoke 从断裂恢复到 3/3 PASS，恢复 INV-03/INV-04。Fix Intent Card + Semantic Regression Gate 护航。→ `docs/plans/2026-04-13-migration-gate-repair-design.md` |
| **知识图谱可视化 Phase 1（kg-phase1）[Batch 3.a ✅ / Batch 3.b 待启动 / Batch 3.c 待推]** | `docs/plans/2026-04-12-knowledge-graph-optimization-design.md` + `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md` | 14 Tasks / 3 Batches × Gate 2。**进度**：T0-T10 ✅ / T11-T14 pending。**Batch 1 (T1-T6)** 后端 stats 全链路 R2 PASS (`1c3c1a2..bcb1971`)。**Batch 2 (T7-T8)** Graph API v3 + 高考题/概览 API R3 PASS (`d300263`)。**Batch 3.a (T9-T10)** 前端 heatmapUtils（log 尺度考频 + 4 态掌握度 + 3 态审核状态 + importance→size）+ ColorModeToggle 三模式 + ConceptMapPanel v3 视觉升级（buildG6Data size+fill 三分支 + watch colorMode setData/render 保留 focusedNodeId + defineExpose）R1 FAIL (F001 KnowledgeTreePage selectedStudentId 状态分裂 / F002 mount.test.js stub 吞新 prop / F003 G6 mock 缺 setData spy) → **R2 PASS** (`2ab10a2..c5bff80`)。Planner 纠正 Executor R1 对 F001 scope 误判（composable 已导出 ref 只需页面解构），scope 扩容 1 文件 mount.test.js 由用户 L017 批准。**Gate 1 Plan Review R1-R6** FAIL→PASS（R5 FAIL 4 finding：R5-T001 fixture schema 错 / R5-T002 T9-T13 测试目录 `frontend/src/components/knowledge-tree/__tests__/` 根本不存在是 R1-R4 漏审前置缺陷 / R5-P002 freshness / R5-P001 半对半错——`94cb65d7` 幽灵 hash 证据 GPT 独立验证 staging 污染而非 amendment 超范围；R6 全部 resolved-correct / resolved-false-positive，subject_hash `a963e85b`）。**关键约束**：TreeNavPanel select-node emit 必须传完整 node 对象 (F010 R4)。**Batch 3.b 待启动** (T11 NodeDetailDrawer 高考真题+学习单元 tab + T12 章节导航 buildChapterTree + TreeNavPanel 双模式)：handoff-batch3b.md commit `f9ab3a1` 已就绪。**Batch 3.c 待推** (T13 ModuleOverviewPanel + T14 P001 处置 INV-002 L1 集合相等测试落盘 + Phase 1 收尾)。Planner 交接卡: `docs/plans/2026-04-13-knowledge-graph-phase1-planner-handoff.md`。→ `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md` |
| **德育板块统筹规划路线图（conduct-roadmap）[批次 1 实现完成 ✅ (2026-04-24)；conduct 80 passed / frontend 22 passed]** | `docs/plans/2026-04-14-conduct-roadmap-design.md` + `-batch1-plan.md` + `-plan-review.md` + `-r2.md` + `-r3.md` + `-r4.md` + `-r5.md` | R3 PASS 后全景治理规划。批次 1 T1-T5：lesson_prep_leader 权限回收（R-T1）/ AddPointsRequest.date→record_date（R-T2，R2-F004 后端 API 契约修复）/ sidebar permissions 派生（subject_teacher 2→4 per F005 approved）/ conduct MODULE.md 补全 / 文档数字漂移修正。**R1 FAIL** 9 → R2 → **R2 FAIL** 6 → R3 → **R3 FAIL** 5 → R4 → **R4 FAIL** 3 → R5 → **R5 FAIL** 3 finding raw `f0582600...`: HIGH×1 + LOW×2。**R4 核心 100% resolved**；R5-F001 是测试设计根因洞察（lesson_prep_leader fixture 无 class_ids，conduct scope 守卫先 403 → INV-T1-003 假绿）→ **R6 修订（2026-04-18 W4 窗口）**：R5-F001 Task 3 Step 3.4a fixture 加 `class_ids=[cls.id]` + 新增对照组 `test_subject_teacher_with_same_scope_passes_rbac`（同 scope 下 200，证明 403 来自 RBAC 回收）；R5-F002 Task 2 Files 摘要 "1 测试" → "3 测试"；R5-F003 Step 5.5 基线从历史数字改为 "234 基线实跑 + 16 新 = 250"（post-T-Wipe 对齐 ECS 后 conduct 目标 ≥80）。Contract Pack INV-T1-003 证据链升级。基线 ECS pytest 实测 @ 2026-04-18: conduct 68 / services 15 / frontend 13；**R6 plan 预计实现后**: conduct ≥80 / services 15 / frontend ≥29（分项列示，不汇总）。批次 2/3 占位。T-Wipe Phase 4 (W4 051cc35) 已将 plan 数字对齐 ECS 68 基线。→ `docs/plans/2026-04-14-conduct-roadmap-design.md` |
| 平台交接单 | exam-ai `docs/plans/2026-03-16-platform-handoff.md` | A→B→C→D 四阶段全局规划 |

## 数据模型概要

**ORM Import 约定**（见 `docs/arch/orm-placement.md`）：
- **外部代码统一从 `edu_cloud.models.*` 入口 import**（如 `from edu_cloud.models.grading import GradingTask`）
- 模块内部代码可直接 import 本模块 models（如 `modules/exam/service.py` 可写 `from edu_cloud.modules.exam.models import Exam`）
- `edu_cloud.models/` 下每个模块都有对应文件（平台层真实定义 或 re-export stub 指向 `modules/*/models.py`），19 个入口全覆盖

**模块分层规范**：见 `docs/arch/module-template.md`（三类模板 A/B/C + 决策树 + 20 模块现状对照）

| 表 | 关键字段 | 说明 |
|---|---------|------|
| schools | code(唯一), api_key_hash(Optional), is_active, district | 学校档案（原 registered_schools） |
| users | username(唯一), display_name, hashed_password, is_active, employee_id, gender, id_card, title, hire_date, education, university, office_phone, notes | 统一用户（含教师档案 9 列扩展） |
| user_roles | user_id(FK), role, school_id(FK), class_ids, is_primary | 多角色+scope |
| llm_slots | school_id(FK,nullable), slot_number, api_url, api_key, model, is_enabled, tier(nullable) | LLM 槽位配置（学校覆盖>平台默认>.env，tier: mini/standard/advanced） |
| agent_profiles | owner_user_id(FK→users), school_id(FK→schools), profile_type, display_name, preferences(JSON), memory_summary(Text) | Agent 身份（唯一约束：user+school） |
| agent_runs | profile_id(FK→agent_profiles), session_id, tools_resolved(JSON), tools_selected(JSON), model_used, model_tier, intent_domains(JSON), token_input, token_output | Agent 执行记录 |
| joint_exams | name, status(draft→...→archived), subjects(JSON), created_by(FK→users), creator_school_id(FK) | 联考 |
| joint_exam_participants | joint_exam_id(FK), school_id(FK), status, is_creator | 参与校 |
| joint_exam_student_results | joint_exam_id, school_id, subject_code, student_name/number, total_score, detail_scores(JSON) | 成绩明细 |
| documents | type, title, status, content_json, created_by(FK→users), assigned_to(FK), school_id(FK) | Studio 文档 |
| calendar_events | type, title, event_date, school_id(FK), created_by(FK→users), semester, is_active | 校历事件 |
| notification_rules | event_id(FK), days_before, template_type, target_roles(JSON), auto_draft, triggered | 通知触发规则 |
| notifications | document_id(FK), channel, status, target_scope(JSON), school_id(FK) | 通知发送记录 |
| school_settings | school_id(FK), category, key(唯一per school), value(Text,nullable) | 学校 KV 配置 |
| school_modules | school_id(FK), module_code(唯一per school), enabled, config(Text,nullable) | 模块开关（9 codes: exam/grading/homework/study_analytics/research/teaching/calendar/studio/conduct）。`DEFAULT_ENABLED` 默认启用 6 个：exam/grading/homework/calendar/studio/**conduct**（2026-04-13 conduct 加入默认集，现存学校经 `scripts/archived/backfill_conduct_module.py` 补齐（已归档，任务完成），契约测试 `test_default_enabled_includes_conduct` 防止回退） |
| teacher_assignments | user_id(FK), class_id(FK), subject_code, semester, school_id(FK), is_active | 教师排课记录（唯一约束：user+class+subject+semester） |
| subject_selections | school_id(FK), name(唯一per school), subject_codes(JSON), mode, is_active | 学校选考科目组合（模式: 3+1+2/3+3/custom） |
| capabilities | school_id(FK), role, domain, action, enabled(default True) | 学校级角色能力配置（唯一约束：school+role+domain+action） |
| audit_logs | school_id(FK,nullable), user_id(FK,nullable), entity_type, entity_id, action, before_data(JSON), after_data(JSON), request_id | 变更审计日志 |
| homework_tasks | school_id(FK), title, task_type(regular/pre_exam/post_exam), subject_code, class_id(FK,nullable), assigned_by(FK), exam_id(FK,nullable), deadline, status(draft→active→expired→closed), content(Text), grading_mode | 作业任务 |
| homework_submissions | task_id(FK), student_id(FK), status(pending/submitted/graded), score(Float,nullable), feedback(Text), submit_time, content(Text), graded_by(FK,nullable), graded_at | 作业提交记录（唯一约束：task+student） |
| guardian_student_links | guardian_user_id(FK→users), student_id, relationship, is_primary, school_id(FK) | 家长-学生绑定（唯一约束：guardian+student） |
| workflow_runs | workflow_name, trigger_type, trigger_ref, idempotency_key(唯一), status, current_step, total_steps, retry_count, started_at, completed_at, last_error | 工作流执行实例 |
| workflow_steps | run_id(FK→workflow_runs), step_index, step_name, status, input_summary(JSON), output_summary(JSON), started_at, completed_at, error | 工作流步骤记录 |
| exam_analysis_snapshot | exam_id(FK→exams), snapshot_type, target_type, target_id, subject_code, semester, version, status, metrics(JSON), computed_at | 考试分析快照（不可变，版本递增） |
| class_exam_report | exam_id(FK→exams), class_id, grade_rank, class_avg, grade_avg, vs_last_exam, metrics(JSON), version, status, computed_at | 班级考试报告 |
| agent_findings | finding_type, severity, target_type, target_id, summary, detail(JSON), status, notify_roles(JSON), idempotency_key(唯一), resolved_at | Agent 巡检发现（幂等） |
| agent_tasks | finding_id(FK→agent_findings,nullable), task_type, assignee_role, payload(JSON), status, school_id(FK) | Agent 生成的待办任务 |
| score_segment_config | school_id(FK), subject_code(nullable), boundaries(JSON), labels(JSON), created_by(FK→users,nullable) | 学校级分数段配置（默认+科目覆盖，partial unique index） |
| scope_versions | school_id, user_id, version, last_reason（唯一约束：school+user） | Scope 版本追踪（角色变更时递增） |
| entity_memory | entity_type(String30), entity_id, school_id, facts(JSON) | 跨会话实体记忆（student/teacher/class/session_episode），复合索引 (school_id, entity_type, entity_id) |
| project_state | project_type, project_id, owner_id, school_id, state(JSON), checkpoints(JSON,default=[]), status(String20,default=active) | 跨会话项目进度（paper/courseware 等），索引 (owner_id,school_id) + (project_type,project_id) |
| concept_graph_nodes | id(PK,String64), name, knowledge_level(String10), primary_module(idx), description, synced_at, subject, node_type(concept/big_concept), display_order, review_status, reviewed_by, reviewed_at, aliases_json, evidence_ids_json, difficulty, bloom_level | 知识图谱节点（投影自 knowledge.db concepts + big_concepts） |
| concept_big_concept_map | concept_id(PK,FK→nodes), big_concept_id(PK,FK→nodes), is_primary | BigConcept→Concept 映射 |
| concept_graph_edges | id(PK,serial), source_id(FK→nodes), target_id(FK→nodes), relation_type, strength, confidence, review_status(String20,default=ai_draft), synced_at | 知识图谱边（UniqueConstraint: source+target+type） |
| edit_sync_failures | id(PK,serial), operation_json, error_message, created_at | 知识图谱编辑回写失败记录 |
| concept_stats | concept_id(PK,FK→nodes CASCADE), exam_frequency, exam_coverage, avg_difficulty, importance_score, planning_weight(JSON), textbook_chapters(JSON), study_unit_id, estimated_minutes, prerequisite_depth, computed_at | 概念统计指标（Phase 1，从 knowledge.db + MCU 投影计算）|
| answer_logs | student_id, knowledge_point_id, question_id, is_correct, response_time_ms, exam_id, answered_at | 自适应学习作答日志 |
| student_da_mastery | student_id, knowledge_point_id, p_mastery, p_transit, p_slip, p_guess, attempt_count, correct_count, last_updated | BKT 掌握度（唯一：student+kp） |
| da_bkt_params | knowledge_point_id(唯一), p_init, p_transit, p_slip, p_guess, sample_count, last_calibrated | BKT 全局先验参数 |
| da_knowledge_point_map | knowledge_point_id(唯一), concept_node_id(FK→concept_graph_nodes), subject_code, difficulty, bloom_level | 知识点→概念图映射 |
| question_da_override | question_id(唯一), difficulty_override, bloom_level_override, knowledge_point_ids(JSON), reason | 题目自适应属性覆盖 |
| adaptive_cards | student_id, card_type, payload(JSON), status, school_id, created_at | 自适应学习卡片（诊断/推荐） |
| da_catalog_snapshot | snapshot_id(PK), school_id, subject_code, snapshot_data(JSON), created_at | 知识点目录快照 |

## 种子数据

启动时自动创建：
- 平台管理员 `admin/123456`（User + UserRole platform_admin）
- 育才实验中学（YCSY2026）：36 班 / 1500 学生 / 200 教师+行政（幂等，密码均 123456）
