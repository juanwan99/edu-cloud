# exam-ai 合并进 edu-cloud 设计文档

> snapshot: 2026-03-22
> 状态: 设计中
> T 级别: T4（跨模块/跨服务，架构重构）

## §0 背景与动机

exam-ai 和 edu-cloud 是两个独立 FastAPI 服务，通过 REST API 同步数据。exam-ai 负责单校考试管理/AI 阅卷/答题卡，edu-cloud 负责多校联考/文档生成/家校通信。

**合并原因**：exam-ai 的核心功能（试卷分发、AI 阅卷、考情分析）全部依赖网络，不存在离线场景。唯一离线组件是 paper-seg（桌面扫描端）。两套独立服务导致：重复模型（User/School/Student/Knowledge）、双套认证、同步复杂度、维护成本翻倍。

**目标**：合并为单一后端服务，paper-seg 作为纯上传客户端直连云端。

## §1 合并后架构总览

```
paper-seg（桌面端，离线扫描）
  └── 扫描 → 切图 → 上传到 edu-cloud

edu-cloud（唯一后端，port 9000）
  ├── core/           共享基础（auth/RBAC/database/config/events/logging）
  ├── ai/             统一 Agent（~28 工具）
  ├── modules/
  │   ├── school/     学校管理
  │   ├── exam/       校内考试 + 联考
  │   ├── student/    学生 + 班级
  │   ├── card/       答题卡编辑器
  │   ├── scan/       扫描上传 + 图片存储
  │   ├── grading/    AI 阅卷 + 教师审核
  │   ├── marking/    手动批改
  │   ├── analytics/  考情分析
  │   ├── bank/       题库 + 错题本
  │   ├── knowledge/  知识点（DB + 内存双源）
  │   ├── profile/    学生画像 + 掌握度
  │   ├── pipeline/   考后数据聚合
  │   ├── studio/     文档生成 + 审批
  │   ├── calendar/   日历 + 通知
  │   └── paper/      论文写作（paper-skill 客户端）
  └── workers/        arq 后台任务

frontend/（Vue 3 + Naive UI，统一 SPA）
  ├── 三栏工作台（dashboard）
  ├── 考试管理 / 答题卡编辑器 / 扫描管理
  ├── AI 阅卷 / 手动批改 / 考情分析
  ├── AI 对话 / 文档 Studio / 知识点 / 题库
  └── 日历 + 通知
```

## §2 数据模型设计

### 2.1 模型归属（35 个模型，去重后）

#### core/models/（跨模块共享）

| 模型 | 来源 | 处理 |
|------|------|------|
| **User** | edu-cloud | 保留多角色设计（UserRole 表），吸收 exam-ai 的 `subject_code`、`class_ids` 字段 |
| **UserRole** | edu-cloud | 原样保留（role + school_id + is_primary） |
| **School** | edu-cloud RegisteredSchool | 改名 School，吸收 exam-ai 的 name/address/contact 字段 |
| **LLMSlot** | exam-ai | 加 `school_id` 作用域（NULL = 平台默认） |

User.subject_code 用于科任教师绑定科目，class_ids 用于班主任/年级组长绑定班级。这两个字段原在 exam-ai 中，edu-cloud 的 User 模型缺失。

#### modules/exam/models.py

| 模型 | 来源 | 处理 |
|------|------|------|
| **Exam** | exam-ai | 加 `school_id` FK，代表校内考试（status: draft→scanning→grading→reviewing→completed） |
| **Subject** | exam-ai | 通过 Exam 间接关联 school_id |
| **Question** | exam-ai | 原样迁入 |
| **JointExam** | edu-cloud | 原样保留，代表联考 |
| **JointExamParticipant** | edu-cloud | 原样保留 |
| **JointExamStudentResult** | edu-cloud | 原样保留 |
| **ExamResult** | edu-cloud | 原样保留（校内考试成绩汇总） |

Exam（校内考试）和 JointExam（联考）是不同业务实体，不合并。Exam 有 scanning/grading 状态机（对接 paper-seg），JointExam 有 distribute/collecting 状态机（跨校编排）。

#### modules/student/models.py

| 模型 | 来源 | 处理 |
|------|------|------|
| **Student** | 合并 | exam-ai 字段（student_number/gender/enrollment_year/status）+ edu-cloud 的 grade + `school_id` FK |
| **Class** | exam-ai | 加 `school_id` FK |

#### modules/card/models.py

| 模型 | 来源 |
|------|------|
| **Template** | exam-ai，原样 |
| **CardSkeleton** | exam-ai，school_id 作用域 |

#### modules/scan/models.py

| 模型 | 来源 |
|------|------|
| **ScanTask** | exam-ai，原样 |
| **StudentAnswer** | exam-ai，原样 |

#### modules/grading/models.py

| 模型 | 来源 |
|------|------|
| **Rubric** | exam-ai，原样 |
| **GradingTask** | exam-ai，原样 |
| **AIGradingResult** | exam-ai，原样 |
| **TeacherReview** | exam-ai，原样 |

#### modules/marking/models.py

| 模型 | 来源 |
|------|------|
| **MarkingAssignment** | exam-ai，原样 |
| **MarkingScore** | exam-ai，原样 |

#### modules/bank/models.py

| 模型 | 来源 |
|------|------|
| **BankQuestion** | exam-ai，原样 |
| **StudentErrorBook** | exam-ai，原样 |

#### modules/knowledge/models.py

| 模型 | 来源 |
|------|------|
| **KnowledgePoint** | exam-ai，DB-backed，school_id 区分全局/校级 |
| **QuestionKnowledgePoint** | exam-ai，原样 |

#### modules/profile/models.py

| 模型 | 来源 |
|------|------|
| **StudentExamSnapshot** | exam-ai，原样 |
| **StudentKnowledgeMastery** | exam-ai，原样 |
| **StudentErrorPattern** | exam-ai，原样 |

#### modules/studio/models.py

| 模型 | 来源 |
|------|------|
| **Document** | edu-cloud，原样 |
| **DocumentVersion** | edu-cloud，原样 |

#### modules/calendar/models.py

| 模型 | 来源 |
|------|------|
| **CalendarEvent** | edu-cloud，原样 |
| **NotificationRule** | edu-cloud，原样 |
| **Notification** | edu-cloud，原样 |

#### ai/models.py

| 模型 | 来源 |
|------|------|
| **AiSession** | edu-cloud，原样 |
| **AiToolCall** | edu-cloud，原样 |

### 2.2 多租户改造要点

exam-ai 原为单校设计，迁入后关键改造：

1. **顶层实体加 school_id FK**：Exam, Student, Class, BankQuestion, CardSkeleton, LLMSlot
2. **子实体通过父级间接关联**：Question → Subject → Exam → school_id，无需冗余 school_id
3. **Service 层强制 school_id 过滤**：所有查询方法签名包含 `school_id: str` 参数，不允许无作用域查询
4. **Agent 工具注入 school_id**：通过 ToolRegistry 的 `_school_id` 参数自动注入，工具代码无需显式处理

### 2.3 Knowledge 双源设计

知识数据有两个来源，职责不同：

| 来源 | 存储 | 数据 | 用途 |
|------|------|------|------|
| edu-knowledge-base JSON | 内存（KnowledgeStore 单例） | 课标/教材/高考真题（只读参考） | AI 工具搜索课标、概念、真题 |
| KnowledgePoint 表 | PostgreSQL | 学校自定义知识点 + 题目关联 | 题目标注、掌握度追踪、错题归因 |

两套共存，AI 工具同时搜索两个数据源。内存源在启动时从文件加载（现有 edu-cloud 逻辑），DB 源随业务 CRUD（现有 exam-ai 逻辑）。

## §3 模块内部结构约定

每个模块遵循统一结构：

```
modules/{module_name}/
├── __init__.py      # 空或导出
├── models.py        # SQLAlchemy 模型
├── schemas.py       # Pydantic request/response schemas
├── service.py       # 业务逻辑（不依赖 FastAPI）
├── router.py        # API 端点定义
└── ...              # 模块特有文件（如 card/ 有 renderer.py, export.py 等）
```

**模块间依赖规则**：
- 模块可依赖 core/（auth, database, config）
- 模块间通过 Service 调用，不直接 import 其他模块的 models
- pipeline/ 是例外——它天然跨 bank/profile/knowledge 聚合数据
- ai/ 通过 ToolRegistry 调用各模块 Service，不直接依赖模块内部

## §4 API 端点合并

### 4.1 保留的端点（edu-cloud 原有）

| 路由前缀 | 端点数 | 说明 |
|---------|--------|------|
| `/api/v1/auth/` | 2 | login + switch-role |
| `/api/v1/schools/` | 5 | 学校 CRUD + API key |
| `/api/v1/joint-exams/` | 6 | 联考生命周期 |
| `/api/v1/joint-exams/{id}/results/` | 3 | 跨校成绩 |
| `/api/v1/studio/` | 8 | 文档 + 论文 |
| `/api/v1/calendar/` | 3 | 日历事件 |
| `/api/v1/workspace/` | 2 | 工作台数据 |
| `/api/v1/ai/` | 1 | AI 对话 |
| `/api/v1/health` | 1 | 健康检查 |

### 4.2 迁入的端点（exam-ai 来源）

| 路由前缀 | 端点数 | 说明 | 改造 |
|---------|--------|------|------|
| `/api/v1/exams/` | 4 | 校内考试 CRUD | 加 school_id 作用域 |
| `/api/v1/exams/{id}/subjects/` | 2 | 科目管理 | 原样 |
| `/api/v1/questions/` | 5 | 题目 CRUD | 原样 |
| `/api/v1/templates/` | 3 | 答案模板 | 原样 |
| `/api/v1/card/` | 12 | 答题卡全套 | 原样 |
| `/api/v1/scan/` | 4 | 扫描上传 | 原样 |
| `/api/v1/grading/` | 9 | AI 阅卷 | 原样 |
| `/api/v1/marking/` | 10 | 手动批改 | 原样 |
| `/api/v1/analytics/` | 4 | 考情分析 | 原样 |
| `/api/v1/students/` | 3 | 学生管理 | 加 school_id |
| `/api/v1/knowledge/` | 6 | 知识点 | 原样 |
| `/api/v1/llm-config/` | 3 | LLM slot 管理 | 加 school_id |
| `/api/v1/pipeline/` | 3 | 数据管线 | 原样 |

### 4.3 删除的端点

| 端点 | 原位置 | 原因 |
|------|--------|------|
| `/api/v1/sync/*` | edu-cloud | 不再需要跨服务同步 |
| `/api/v1/sync_students/` | edu-cloud | 学生直接在统一 DB |
| `/api/cloud-sync/*` | exam-ai | 不再需要 |
| `/api/auth/login` (exam-ai) | exam-ai | 统一用 edu-cloud 的 auth |

### 4.4 合并后端点总计

~95 个端点（edu-cloud 原有 31 + exam-ai 迁入 68 - 删除 ~8 + 合并去重）。

### 4.5 认证方案调整

| 客户端 | 认证方式 | 说明 |
|--------|---------|------|
| 浏览器（教师/管理员） | JWT Bearer | 统一 edu-cloud 的 login + switch-role |
| paper-seg（桌面端） | JWT Bearer | 教师登录后获取 token，school_id 从 token 中提取 |

API Key 认证（原 sync 端点）废弃。paper-seg 改用 JWT——教师在桌面端登录（和浏览器一样），后续请求携带 Bearer token。school_id 从 JWT payload 中获取，paper-seg 无需手动配置学校代码。

## §5 AI Agent 合并

### 5.1 工具集合并

合并后 ~28 个工具，按类别组织：

| 类别 | 工具 | 来源 |
|------|------|------|
| **L1_exam** | get_exam_list, get_exam_detail, get_subject_list | exam-ai |
| **L1_student** | get_student_list, get_student_by_number, get_class_list | exam-ai |
| **L2_analytics** | get_exam_scores, get_class_stats, get_score_distribution, get_question_performance | exam-ai |
| **L2_cross_school** | compare_schools, get_rankings | edu-cloud |
| **L3_knowledge** | search_curriculum, search_textbook, get_concept_info, search_gaokao | edu-cloud（内存源） |
| **L3_knowledge_db** | get_knowledge_points, get_knowledge_tree | exam-ai（DB 源） |
| **L4_action** | generate_report, generate_comment | edu-cloud |
| **L5_bank** | search_bank_questions, get_error_book | exam-ai |
| **L6_profile** | get_student_profile, get_mastery_overview, get_error_patterns | exam-ai |

### 5.2 RBAC 工具访问控制

沿用 edu-cloud 的 `ROLE_TOOL_CATEGORIES` 机制：

| 角色 | 可用工具类别 |
|------|------------|
| platform_admin | 全部 |
| district_admin | L2_cross_school, L3_knowledge |
| principal | L1, L2, L3, L4, L6 |
| academic_director | L1, L2, L3, L4 |
| grade_leader | L1, L2, L3 |
| homeroom_teacher | L1, L2, L3, L5, L6 |
| subject_teacher | L1, L2, L3, L5 |
| parent | L6（仅本人子女） |

### 5.3 Agent 上下文注入

每次对话请求，从 JWT 中提取 `user_id, school_id, role, class_ids`，注入 Agent context：
- `_school_id`：所有工具查询的作用域
- `_class_ids`：班主任/年级组长的班级范围
- `_user_id`：审计日志
- 数据匿名化：学生姓名 → 别名（现有 exam-ai anonymizer 逻辑保留）

## §6 前端合并

### 6.1 技术栈对照

| | exam-ai 前端 | edu-cloud 前端 |
|--|-------------|---------------|
| 框架 | Vue 3.5 | Vue 3.3 |
| UI 库 | Naive UI 2.44 | Naive UI 2.38 |
| 状态管理 | Pinia 3.0 | Pinia 2.1 |
| 图表 | ECharts 6.0 | ECharts 5.4 |
| 构建 | Vite 7.3 | Vite 5.0 |
| HTTP | Axios | Axios |
| 代码量 | ~6,625 LOC | ~819 LOC |

版本差异不阻塞合并——统一升级到 exam-ai 的较新版本。

### 6.2 路由合并

以 edu-cloud 的三栏工作台为 shell，加入 exam-ai 的 13 个路由：

```
/login                          → LoginPage（edu-cloud）
/                               → WorkbenchPage（三栏工作台 dashboard）
/exams                          → ExamListPage（exam-ai）
/exams/:id                      → ExamDetailPage（exam-ai，5 tab 核心页）
/card-dev/:examId               → CardEditorDevPage（exam-ai）
/grading/tasks                  → GradingTasksPage（exam-ai）
/grading/tasks/:id              → GradingResultsPage（exam-ai）
/grading/review                 → TeacherReviewPage（exam-ai）
/marking                        → MarkingSelectPage（exam-ai）
/marking/grade/:questionId      → MarkingPage（exam-ai）
/marking/assign                 → MarkingAssignPage（exam-ai）
/marking/progress               → MarkingProgressPage（exam-ai）
/analytics/:examId              → AnalyticsPage（exam-ai）
/schools                        → SchoolsPage（admin）
```

三栏工作台（`/`）是 dashboard 主页，其余路由使用 DashboardLayout（顶栏 + 侧边导航 + 内容区）。

### 6.3 组件迁移

| 组件 | 大小 | 处理 |
|------|------|------|
| ExamDetailPage | 812 LOC | 直接迁入，改 API 路径前缀 |
| MarkingPage | 462 LOC | 直接迁入 |
| CardEditor.vue | 28K | 直接迁入，含 card-editor/ JS 模块 |
| ChatPanel.vue | 合并 | exam-ai 版本更丰富（工具调用展示），以它为主 |
| 其余 12 页面 | ~1,700 LOC | 直接迁入 |
| DashboardPage | 155 LOC | 合并进 WorkbenchPage |

### 6.4 Store 合并

| Store | 处理 |
|-------|------|
| auth | edu-cloud 版本为主（多角色 + switchRole），吸收 exam-ai 的 schoolCode |
| aiChat | exam-ai 版本为主（更完整的 SSE/tool_call 处理） |
| context | edu-cloud 保留 |
| studio | edu-cloud 保留 |
| 新增 exam store | 管理考试列表/详情/科目状态 |
| 新增 marking store | 管理批改状态 |

### 6.5 API Client 统一

合并为单一 axios 实例，baseURL 统一为 `/api/v1`。exam-ai 前端的 API 模块（11 个）迁入，调整路径前缀。

## §7 paper-seg 集成变更

### 7.1 当前连接方式

```
paper-seg → localhost:8000 (exam-ai)
  认证：JWT（教师登录）
  端点：GET /api/exams, GET /api/templates/*, POST /api/scan/upload/*
```

### 7.2 合并后连接方式

```
paper-seg → edu-cloud-server:9000
  认证：JWT（同一套 auth，教师登录）
  端点：GET /api/v1/exams, GET /api/v1/templates/*, POST /api/v1/scan/upload/*
```

**paper-seg 侧改动**：
1. 服务器地址从 `localhost:8000` 改为可配置的云端 URL
2. API 路径前缀从 `/api` 改为 `/api/v1`
3. 登录接口统一为 `/api/v1/auth/login`
4. 其余逻辑不变（扫描→切图→上传）

### 7.3 图片存储

沿用 exam-ai 的层级结构，改为云端存储：

```
{STORAGE_ROOT}/
└── {school_id}/
    └── {exam_id}/
        └── {subject_id}/
            └── {question_id}/
                └── {student_id}.png
```

`STORAGE_ROOT` 配置为云端服务器的本地路径（如 `/data/storage/`）。后续如需 S3/MinIO 对象存储，只需替换 StorageService 实现，接口不变。

## §8 后台任务合并

### 8.1 统一 arq Worker

```python
class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [
        process_grading_task,   # exam-ai：AI 阅卷（on-demand）
        run_auto_draft,         # edu-cloud：通知自动拟稿（cron）
        run_post_exam_pipeline, # exam-ai：考后数据聚合（on-demand）
    ]
    cron_jobs = [
        cron(run_auto_draft, hour=22, minute=0),  # 06:00 Beijing
    ]
```

### 8.2 data_pipeline 作为后台任务

exam-ai 的 `data_pipeline.py`（905 LOC）包含 5 个考后聚合函数。合并后放入 `modules/pipeline/`，通过 arq 异步执行：

1. Exam.status → completed 时，enqueue `run_post_exam_pipeline(exam_id)`
2. Worker 依次执行：populate_bank_questions → populate_error_books → generate_exam_snapshots → update_knowledge_mastery → update_error_patterns
3. 幂等设计已有（savepoint + IntegrityError + last_exam_id 检查）

## §9 数据库迁移

### 9.1 策略

创建新的 Alembic initial migration 覆盖合并后全部 ~35 个模型。edu-cloud 和 exam-ai 的旧 migration 归档但不删除。

### 9.2 执行

1. 合并代码后，`Base.metadata` 包含所有模型
2. `alembic revision --autogenerate -m "merge_exam_ai_into_edu_cloud"`
3. 开发环境继续用 `Base.metadata.create_all()`（SQLite in-memory）
4. 生产环境用 Alembic migration

### 9.3 数据迁移

如果存在旧 exam-ai 数据需要迁移到新 schema：
- 编写一次性迁移脚本（不在 Alembic 管理范围）
- 主要是加 school_id 列并填充默认值
- 当前无生产数据，此项暂不需要

## §10 测试策略

### 10.1 迁移方式

适配迁移：改 import 路径和 fixture，保留测试逻辑。

### 10.2 需要修改的内容

| 修改类型 | 说明 |
|---------|------|
| import 路径 | `from exam_ai.models` → `from edu_cloud.modules.exam.models` 等 |
| fixture | 统一用 edu-cloud 的 conftest（AsyncSession + SQLite in-memory） |
| school_id | 所有测试 fixture 补 school_id（可用固定值 `test-school-001`） |
| auth fixture | 统一用 edu-cloud 的 JWT fixture（多角色） |

### 10.3 删除的测试

- exam-ai 的 `test_cloud_sync.py`（~20 个测试）——同步机制废弃
- edu-cloud 的 sync 相关测试——同上

### 10.4 合并后测试目标

~690 个测试（exam-ai ~426 + edu-cloud ~267 - 删除 ~20 + 去重调整）。

## §11 配置合并

### 11.1 统一 Settings

```python
class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/edu_cloud"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = "./logs"

    # Storage (scanned images)
    STORAGE_ROOT: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Uploads (templates, documents)
    UPLOAD_DIR: str = "./uploads"

    # LLM
    LLM_PROXY_URL: str = "http://localhost:8100/v1"
    LLM_API_URL: str = ""        # fallback
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_VISION_MODEL: str = "gemini-3.1-pro-preview"
    LLM_TIMEOUT: int = 60
    LLM_MAX_RETRIES: int = 3

    # AI Agent
    AI_MAX_STEPS: int = 15
    AI_SESSION_TTL: int = 7200
    AI_RATE_LIMIT_PER_MINUTE: int = 10
    AI_RATE_LIMIT_PER_DAY: int = 200

    # Knowledge
    KNOWLEDGE_ENABLED: bool = True
    KNOWLEDGE_BASE_DIR: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
```

### 11.2 删除的配置

- `CLOUD_ENABLED`、`CLOUD_URL`、`CLOUD_API_KEY`——同步机制废弃
- `PLATFORM_API_KEY_SALT`——API Key 认证废弃

## §12 中间件合并

统一为 edu-cloud 的中间件栈：

1. **CORS**（FastAPI 内置）—— `settings.CORS_ORIGINS`
2. **Request Logging**（自定义）—— X-Request-ID / X-Trace-ID 注入 + 计时 + ContextVar

两边的 request logging 中间件逻辑几乎相同，以 edu-cloud 版本为主（支持 X-Trace-ID 优先级）。

全局异常处理器合并：
- NotFoundError → 404
- PermissionDeniedError → 403
- ValidationError → 422（edu-cloud 用 422，exam-ai 用 400，统一为 422）
- ConflictError → 409
- StateError → 409

## §13 删除清单

合并后彻底删除的代码：

| 组件 | 位置 | 原因 |
|------|------|------|
| CloudSyncService | exam-ai/services/cloud_sync.py | 同步废弃 |
| cloud_sync router | exam-ai/api/cloud_sync.py | 同步废弃 |
| sync router | edu-cloud/api/sync.py | 同步废弃 |
| sync_students router | edu-cloud/api/sync_students.py | 直接 DB 访问 |
| SyncService stub | edu-cloud/services/ | 同步废弃 |
| AiGradingService stub | edu-cloud/services/ | exam-ai 的完整实现替代 |
| PlatformUser model | edu-cloud/models/ | User + UserRole 替代 |
| KnowledgeStore（部分） | edu-cloud/knowledge/store.py | 保留内存搜索，删除 DB 替代部分 |
| exam-ai 独立项目 | exam-ai/ | 合并完成后归档 |

## §14 Docker 更新

```dockerfile
FROM python:3.11-slim

# Playwright for card PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-wqy-microhei fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*
RUN pip install playwright && playwright install chromium --with-deps

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

EXPOSE 9000
CMD ["python", "-m", "uvicorn", "edu_cloud.api.app:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "9000"]
```

docker-compose.yml 增加 volumes：
```yaml
volumes:
  - ./logs:/app/logs
  - ./storage:/app/storage    # 扫描图片
  - ./uploads:/app/uploads    # 模板/文档
```

## §15 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 多租户遗漏 school_id 过滤 → 数据泄漏 | 高 | Service 基类强制 school_id 参数；测试 fixture 用不同 school_id 验证隔离 |
| 35 个模型的 Alembic migration 冲突 | 中 | 新建 initial migration，不叠加旧版本 |
| 前端 28K 答题卡编辑器迁入后样式冲突 | 中 | CardEditor 已是独立 JS 模块 + scoped CSS，冲突风险低 |
| exam-ai 446 个测试适配工作量 | 中 | import 路径替换可批量 sed；fixture 改动集中在 conftest.py |
| Playwright 增加 Docker 镜像体积 | 低 | Chromium ~200MB，可接受；或用 playwright-chromium-headless-shell 精简版 |
| paper-seg 改连云端后上传延迟 | 低 | 切割后的题目图片通常几十 KB，校园网可承受 |

## §16 不做的事（YAGNI）

1. **不做微服务拆分**——单人项目，模块化单体足够
2. **不做 S3 对象存储**——文件系统够用，后续按需替换 StorageService
3. **不做 WebSocket 实时通知**——SSE 已满足 AI 对话需求
4. **不做前端 i18n**——纯中文产品
5. **不做 exam-ai 数据迁移脚本**——无生产数据
6. **不重写测试**——适配迁移，保留覆盖范围
