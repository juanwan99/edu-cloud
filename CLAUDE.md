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
    app.py              # FastAPI 应用工厂
    deps.py             # 依赖注入（认证、DB session）
    auth.py             # 平台认证（登录、Token）
    school_mgmt.py      # 学校注册、授权、状态监控
    joint_exam.py       # 联考 CRUD、下发、汇总
    sync.py             # 学校端↔云端 数据同步端点
    analytics.py        # 跨校分析
    question_bank.py    # 统一题库
  models/
    base.py             # Base + IdMixin + TimestampMixin
    school.py           # RegisteredSchool（云端管理的学校档案）
    platform_user.py    # 平台级用户（区管理员、联考协调员）
    joint_exam.py       # JointExam, JointExamParticipant
    question_bank.py    # BankQuestion, BankCategory
  services/
    sync/               # 同步协议实现
    ai_grading/         # 共享 AI 阅卷（复用 exam-ai 的 LLM client 模式）
    analytics/          # 跨校统计聚合
  core/
    events.py           # 进程内事件总线
    permissions.py      # 平台级 RBAC
  config.py
  database.py
  logging_config.py
```

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

## 同步协议

学校端 ↔ 云端通过 REST API 同步，学校端主动推/拉：

| 端点 | 方向 | 用途 |
|------|------|------|
| `POST /api/v1/sync/heartbeat` | 校→云 | 心跳+版本上报 |
| `GET /api/v1/sync/joint-exams` | 校←云 | 拉取分配给本校的联考 |
| `POST /api/v1/sync/scores` | 校→云 | 上报联考成绩 |
| `POST /api/v1/sync/grading-request` | 校→云 | 请求云端 AI 阅卷 |
| `GET /api/v1/sync/grading-result/{id}` | 校←云 | 拉取阅卷结果 |

学校端通过 API Key 认证（注册时由平台下发），不使用用户级 JWT。

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

## 详细参考文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 同步协议设计 | `docs/sync-protocol.md` | 学校端↔云端完整同步流程 |
| 联考流程设计 | `docs/joint-exam-flow.md` | 联考从创建到出报告的完整生命周期 |
