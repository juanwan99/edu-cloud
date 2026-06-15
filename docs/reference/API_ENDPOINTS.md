# API 端点参考（按需查阅）

> 本文件从 CLAUDE.md 移出，按需 Read。不再每次会话注入。

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
| GET | `/api/v1/schools/{id}/modules` | MANAGE_SCHOOL_SETTINGS | 获取全部模块状态（9 个） |
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
| GET/PATCH/DELETE | `/api/v1/exams/{id}` | 详情/更新/删除考试（DELETE 仅 draft，MANAGE_EXAMS） |
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
| GET | `/api/v1/scan/pipeline/verify-template` | 校对模板区域 vs 题目配置一致性（VIEW_GRADING，返回逐题对比+不一致项） |
| * | `/api/v1/grading/*` | AI 阅卷/评分规则/教师审核 |
| GET | `/api/v1/grading/dispatch/status` | 科目阅卷状态聚合（exam_id 查询参数，返回各科目 subject_code/stage/统计+questions 逐题明细；stage: idle→pending_detect→pending_cut→cutting→ready→ai_grading→reviewing→done） |
| POST | `/api/v1/grading/rubrics` | 创建/更新评分细则（MANAGE_GRADING，criteria 校验：blankNo/score/answer 必填+总分守恒） |
| GET | `/api/v1/grading/rubrics/{question_id}` | 获取题目评分细则 |
| POST | `/api/v1/grading/rubrics/generate` | AI 生成评分细则（MANAGE_GRADING，题干+答案+图片→LLM→criteria，upsert Rubric） |
| POST | `/api/v1/grading/grade-single` | 同步单答卷 AI 评分（MANAGE_GRADING，用于质量抽检，复用 OCR→评分 pipeline） |
| POST | `/api/v1/grading/tasks` | 创建 AI 阅卷任务（支持 question_id 题目级 + mode=realtime/batch 双模式；前置校验：归属/主观题/Rubric/Answer；重跑清理 ai_pending/ai_done、保护 confirmed）|
| GET | `/api/v1/grading/tasks` | 列出本校 AI 阅卷任务 |
| GET | `/api/v1/grading/tasks/{task_id}` | 阅卷任务详情 |
| POST | `/api/v1/grading/assignments` | 创建阅卷分配（MANAGE_GRADING） |
| GET | `/api/v1/grading/assignments` | 列出阅卷分配（VIEW_GRADING，需 exam_id） |
| GET | `/api/v1/grading/progress/{exam_id}` | 阅卷进度汇总（VIEW_GRADING） |
| GET | `/api/v1/grading/quality-report/{exam_id}` | 质量检查报告（VIEW_GRADING） |
| PATCH | `/api/v1/grading/results/{id}/annotations` | 保存教师逐空标注（VIEW_GRADING，school_id 隔离） |
| GET | `/api/v1/grading/annotations/summary` | 按 blankNo 聚合标注汇总（VIEW_GRADING，需 question_id） |
| POST | `/api/v1/exams/{id}/publish` | 发布成绩（MANAGE_EXAM_RESULTS，前置条件检查） |
| POST | `/api/v1/exams/{id}/archive` | 归档考试（MANAGE_EXAM_RESULTS） |
| * | `/api/v1/marking/*` | 人工阅卷/分配（一题多人+answer_count 配额+DELETE /assignments/{id}）/导出；GET /next 支持 mode=ai_review 浏览 AI 已阅答卷 |
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
| GET | `/api/v1/analytics/exam/{id}/basic-report` | 已登录 | 综合分析报告（总览/科目/班级/学生排名+进退步/分布/scope，AnalyticsReportPage 数据源） |
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

### 前端日志端点

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| POST | `/api/v1/client-logs` | 已登录（可选） | 前端日志批量上报（client_session_id + events[]，限流 100/min/session） |

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
| GET | `/api/v1/knowledge-tree/stats/overview` | VIEW_KNOWLEDGE_TREE | 图谱统计概览（total_concepts/total_edges + exam_freq_distribution{high>=500/mid>=50/low>=1/zero} + module_stats{avg_freq/exam_coverage}，module 参数过滤；response_model=StatsOverviewResponse） |
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

### AI Agent 端点（JWT 认证，AgentProvider / Coze-first）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/ai/health` | 无 | 工具数量 + provider/readiness 状态（`provider.active`、`provider.fallback`、Coze `chat_ready`、`required_action_submit_ready`、`tool_modes.coze_required_action`、`tool_modes.http_tool_gateway`） |
| POST | `/api/v1/ai/chat` | USE_AI_CHAT | SSE 流式对话（Coze-first AgentProvider，edu 后端统一执行 DataScope/RBAC/capability/工具壳；current_pydantic fallback） |
| POST | `/api/v1/ai/runs/{run_id}/confirmations/{confirmation_id}` | USE_AI_CHAT | 写操作确认回传（approve/reject，SSE 返回执行结果） |
| GET | `/api/v1/ai/sessions` | 已登录 | 列出当前用户的活跃会话（owner 隔离） |
| DELETE | `/api/v1/ai/sessions/{session_id}` | 已登录 | 删除会话（仅 owner，他人 403） |

### AI Internal Tool Gateway（服务间调用）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/internal/ai-tools?context_token=...` | X-AI-Tool-Token | 列出当前 edu 上下文允许的工具目录和参数 schema |
| POST | `/internal/ai-tools/{tool_name}` | X-AI-Tool-Token | 供 Coze/外部 Agent 回调执行 edu 工具；写工具先返回 confirmation_required |

> 注：`/internal/ai-tools` 已注册不代表 Coze HTTP 插件模式可用。该网关**默认 fail-closed**：当 `AI_TOOL_GATEWAY_HTTP_ENABLED=false`（默认值）时，无论 `X-AI-Tool-Token` 是否正确，两个端点都直接返回 `403`（detail: `AI tool HTTP gateway is disabled`）。route gate `AI_TOOL_GATEWAY_HTTP_ENABLED=true` 后请求才进入 token 校验：service token gate `AI_TOOL_GATEWAY_TOKEN` 未配置返回 `403`（`token is required`），token 缺失/错误仍 `403`，正确 token 才进入 context/tool 校验。`AI_TOOL_GATEWAY_PUBLIC_BASE` 不是进入 token 校验的必要条件，它只影响 provider readiness 与外部 callback/prompt URL 构造。`/api/v1/ai/health` 中 `tool_modes.http_tool_gateway` 是更严格的 readiness 聚合：需 coze 就绪、网关启用、`AI_TOOL_GATEWAY_TOKEN` 与 `AI_TOOL_GATEWAY_PUBLIC_BASE` 均齐全才为 true。当前 Coze CE 运行态未验证可用的 agent `required_action` submit/resume 路径，`tool_modes.coze_required_action=false` 是预期状态；Coze 工具调用下一步应作为 HTTP plugin callback 独立产品化。

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
