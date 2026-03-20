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
# 开发环境（WSL 内执行）
cd /mnt/c/Users/Administrator/edu-cloud
python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload
```

## 测试命令

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q
```
<!-- key-end -->

## 项目结构

```
src/edu_cloud/
  api/
    app.py              # FastAPI 应用工厂 + lifespan + 请求日志中间件 + 全局异常处理器
    deps.py             # 依赖注入（JWT 认证 get_current_user + require_permission）
    auth.py             # POST /api/v1/auth/login（平台用户 JWT 登录）
    schools.py          # 学校管理 CRUD（创建/列表/详情/更新/API Key 轮换）
    joint_exams.py      # 联考管理（创建/列表/详情/参与校/下发/截止）
    results.py          # 成绩查看（排名/按校对比/学生明细）
    sync.py             # 学校端↔云端同步（heartbeat/pull-exams/templates/scores）
  models/
    base.py             # Base + IdMixin(UUID) + TimestampMixin(UTC)
    school.py           # RegisteredSchool（学校档案 + API Key + 心跳）
    platform_user.py    # PlatformUser（4 角色 + bcrypt 密码）
    joint_exam.py       # JointExam + JointExamParticipant + JointExamStudentResult
  services/
    exceptions.py       # 5 个自定义异常（NotFound/Permission/Validation/Conflict/State）
    school_service.py   # 学校 CRUD + API Key 管理
    joint_exam_service.py # 联考生命周期（创建→模板→下发→成绩→完成）
    results_service.py  # 排名 + 按校对比 + 学生明细
    sync/               # 空 stub
    ai_grading/         # 空 stub
    analytics/          # 空 stub
  core/
    events.py           # 进程内 EventBus（已定义，handler 未接入）
    permissions.py      # 10 个 Permission 枚举 + 4 角色 RBAC 映射
  shared/
    auth.py             # JWT create/decode 工具函数
  config.py             # Settings（DB/Redis/JWT/LLM/UPLOAD_DIR 配置，BaseSettings）
  database.py           # async engine + session factory
  logging_config.py     # 双输出（Console UTC+8 + JSONL RotatingFile）
scripts/
  e2e_joint_exam.py     # 端到端联考验证脚本（2 校完整流程）
tests/
  conftest.py           # SQLite in-memory + AsyncClient + admin/school fixtures
  test_api/             # API 集成测试（health/deps/schools/joint_exams/sync_v2/results）
  test_models/          # 模型单测
  test_services/        # Service 单测（exceptions/school/joint_exam/results）
```

### 实现状态

| 层 | 已实现 | 未实现（规划中）|
|---|--------|--------------|
| API | auth/login, schools(CRUD+key), joint-exams(生命周期), results(排名/对比/明细), sync(heartbeat/exams/templates/scores), health, version | 跨校分析(高级), 题库, 共享 AI 阅卷 |
| Models | 5 表（school/user/exam/participant/student_result）| 题库模型（BankQuestion/BankCategory）|
| Services | SchoolService, JointExamService, ResultsService, exceptions | EventBus handler, AI grading |
| Core | EventBus 定义, RBAC 映射(10 权限 + require_permission) | EventBus handler 接入 |
| Tests | 58 tests（API+Service+Model 全覆盖）| — |
| Migrations | Alembic 脚手架 | 未写 migration 文件 |

## 技术栈

- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg (PostgreSQL)
- Alembic (migrations)
- python-jose (JWT) + bcrypt
- arq + Redis (后台任务：联考下发、批量阅卷、报表生成)
- httpx (调用学校端 API)
- Docker + docker-compose (部署)

## 日志体系

与 exam-ai 保持一致：双输出（Console + JSONL）、Request ID 追踪、UTC+8 时区。
日志文件：`logs/app.jsonl`，10MB 轮转，5 份备份。

<!-- key-start -->
## 端口约定

| 服务 | 端口 | 说明 |
|------|------|------|
| edu-cloud | 9000 | 云端平台（本项目） |
| exam-ai | 8000 | 学校端阅卷服务 |
| paper-seg | 8001 | 扫描客户端 |
<!-- key-end -->

## 角色体系

### 平台级角色（edu-cloud 管理）

| 角色 | 权限 | 说明 |
|------|------|------|
| platform_admin | 全部 | 平台超管 |
| district_admin | 管辖区域内学校 | 教育局管理员 |
| exam_coordinator | 联考编排+查看 | 联考协调员 |
| observer | 只读 | 数据查看 |

### 学校内角色（exam-ai 管理，云端不介入）

admin / principal / subject_leader / head_teacher / teacher

## API 端点（已实现）

### 平台端点（JWT 认证）

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/v1/auth/login` | 平台用户登录，返回 JWT |
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/version` | 版本+启动时间 |

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

### 同步端点（API Key 认证，X-API-Key header）

| 方法 | 路径 | 方向 | 用途 |
|------|------|------|------|
| POST | `/api/v1/sync/heartbeat` | 校→云 | 心跳+版本上报 |
| GET | `/api/v1/sync/joint-exams` | 校←云 | 拉取联考（含 template_url） |
| POST | `/api/v1/sync/templates` | 校→云 | 上传试卷模板（multipart） |
| GET | `/api/v1/sync/templates/{exam_id}/{subject}` | 校←云 | 下载模板（zip） |
| POST | `/api/v1/sync/scores` | 校→云 | 上报成绩（含逐题明细） |

API Key 格式：`{school_code}:{secret}`，bcrypt 验证。

### 未实现端点（规划中）

- 共享 AI 阅卷（`grading-request`/`grading-result`）
- 统一题库
- 高级跨校分析（趋势/对比图表）

## 关联项目

| 项目 | 路径 | 关系 |
|------|------|------|
| exam-ai | `C:/Users/Administrator/exam-ai` | 学校端，本项目的下游客户端 |
| paper-seg | `C:/Users/Administrator/paper-seg` | 扫描端，不直接与云端通信 |

## 数据库

```
# .env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/edu_cloud
```

云端必须使用 PostgreSQL（跨校聚合查询、高并发写入）。不支持 SQLite。

## Docker 部署

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
| registered_schools | code(唯一), api_key_hash, last_heartbeat, district | 学校档案 |
| platform_users | username(唯一), role, districts(JSON), school_ids(JSON) | 平台用户 |
| joint_exams | name, status(draft→templates_ready→distributed→collecting→completed→archived), subjects(JSON), created_by(FK), creator_school_id(FK), answer_detail_schema(JSON) | 联考 |
| joint_exam_participants | joint_exam_id(FK), school_id(FK), status, is_creator, student/score_count | 参与校 |
| joint_exam_student_results | joint_exam_id, school_id, subject_code, student_name/number, total_score, detail_scores(JSON) | 成绩明细（含逐题） |

## 种子数据

启动时自动创建：平台管理员 `admin/123456`（platform_admin 角色）。
