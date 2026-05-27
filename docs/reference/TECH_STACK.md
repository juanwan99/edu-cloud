# 技术栈与基础设施参考（按需查阅）

> 本文件从 CLAUDE.md 移出，按需 Read。不再每次会话注入。

## 技术栈

**后端：**
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg (PostgreSQL)
- Alembic (migrations)
- PyJWT (JWT) + bcrypt
- arq + Redis (后台任务：联考下发、批量阅卷、报表生成、学生画像 W3 日任务、异常巡检 W6 时任务、Agent 调度)
- httpx (调用学校端 API)
- google-genai (Gemini 官方 SDK，AI 阅卷双模式：realtime 实时 + batch 经济半价)
- opencv-python-headless + pyzbar (扫描图视觉处理：定位点检测/裁切/条码识别)
- Docker + docker-compose (部署)

**前端（`frontend/`）：**
- Vite 7 + Vue 3.5 (Composition API)
- Naive UI 2.44（冷暖撞色设计系统：深墨 #09061B + 金黄 #F4DA4C + 冷紫 #644CF0 + 橙 #ED9A51，暗色侧栏/紫色主色调/浅灰内容区三层色差，theme.js 全局覆盖）
- Vue Router 4（AppShell 根布局 + 角色/权限守卫，login 外置 + 52 路由含 parent 系列；完整路由冻结于 _frozen/）
- Pinia 3（状态管理）
- Axios（HTTP 客户端，baseURL `/api/v1`）
- ECharts 6 + vue-echarts（图表）
- KaTeX + marked（数学公式渲染 + Markdown）
- card-editor（答题卡可视化编辑器，5 模块 + CardEditor.vue）
- Vitest 4 + @vue/test-utils + happy-dom（单元测试）

## Docker 部署

Dockerfile 包含 Playwright Chromium + 中文字体（Noto CJK），用于答题卡 PDF 生成。

docker-compose 挂载卷：`./logs:/app/logs`、`./storage:/app/storage`（扫描图片）、`./uploads:/app/uploads`（上传文件）。

```bash
docker compose up -d        # 启动
docker compose pull && docker compose up -d  # 升级
docker compose logs -f      # 查看日志
```

## 端口约定

| 服务 | 端口 | 说明 |
|------|------|------|
| edu-cloud 后端 | 9000 | FastAPI（本项目） |
| edu-cloud 前端（frontend/） | 5273 / 8080 | Vite dev server，本地默认 5273 / ECS 远程 8080（host 0.0.0.0 + allowedHosts ECS IP）|
| exam-ai | 8000 | 学校端阅卷服务 |
| paper-seg | 8001 | 扫描客户端 |
| paper-skill | 9103 | AI 论文写作服务（外部，REST 客户端通过 PaperService 调用）|

### 实现状态

| 层 | 已实现 | 未实现（规划中）|
|---|--------|--------------|
| API | 320 路由（43 router 文件，跨 21 模块 + 平台级路由） | 共享 AI 阅卷 |
| Models | 88 表（modules/ 下 18 模块 + core 平台表 + AI Agent 表 + agent evolution 8 表 + score_segment_config + knowledge_tree 3 表 + adaptive 7 表 + academic 3 表 + alembic_version） | — |
| Services | School/JointExam/Results/Paper/Studio/Calendar/Notification/HomeworkTask/HomeworkSubmission/Analytics/Profile/Bank/Pipeline/Conduct/KnowledgeTree/Scan/Adaptive + exceptions | AI grading 生产接入 |
| Core | EventBus（exam.published handler 已接入 pipeline）, RBAC 49 权限 + 10 角色映射 | — |
| AI | Pydantic AI 引擎（EduAgentRuntime）+ 68 @edu_tool（16 模块）+ PolicyToolGuardrail 4 层 RBAC + AgentBudget + ConfirmationBroker 写确认 + ArtifactManager DB 持久化 + TraceRecorder DB 双写 + budget snapshot。旧 AgentLoop/Supervisor/tools/ 已删除（2026-05-13），保留 anonymizer/data_scope/memory_*/prompts/ref_*/schemas/models/workflow | 常驻巡检 Agent |
| Knowledge | KnowledgeStore（课标/L0/L1/高考索引，关键字搜索，全局单例）+ L3 查询工具（4 tools，启动加载）+ ConceptGraphNode 统一引用（旧 knowledge_points UUID 已废弃）| — |
| Tests | 后端：2314 passed / 12 failed / 23 skipped（306 测试文件）+ 前端：2373 passed / 3 failed Vitest（ECS @ 2026-05-19） | — |
| Modules | 21 模块目录，路由已迁入。技术债拆分后：`card` 含 `router.py`(839行) + `card_template_router.py`(230行) + `card_export_router.py`(326行) + `card_utils.py`(54行) + `layout_helpers.py`(排版纯函数，从旧 ai/tools/card_layout.py 提取)；`scan` 含 `pipeline_router.py`(907行) + `cv_detect_router.py`(430行)；`grading` 含 `router.py`(520行) + `grading_review_router.py`(396行) + `prompts/` 子包 + `gemini_client.py`(官方SDK) + `image_utils.py`(图片预处理) + `detail_flatten.py`(LLM输出标准化)；`analytics` 含 `router.py`(220行) + `analytics_report_router.py`(585行) + `diagnosis_service.py` + `insights_service.py` + `pipeline_service.py`。`ReviewPage.vue` 拆分为 3 composable（`review/useImageZoom.js` + `useAnnotations.js` + `useScoring.js`）。详见 `docs/2026-04-26-tech-debt-audit.md` §修复记录 | — |
| Migrations | Alembic migration（48 个迁移文件）。**唯一合法 migration 路径：`python scripts/db_migrate [target]`**（直接 `alembic upgrade` 被 env.py guard 阻断） | — |

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

## 种子数据

启动时自动创建：
- 平台管理员 `admin/123456`（User + UserRole platform_admin）
- 育才实验中学（YCSY2026）：36 班 / 1500 学生 / 200 教师+行政（幂等，密码均 123456）

## 日志体系

日志系统 v2（设计文档：`docs/plans/2026-05-05-logging-system-redesign.md`）：
- **进程分文件**：`logs/api/edu-api-*.jsonl`（API）+ `logs/worker/edu-worker-*.jsonl`（Worker）+ `logs/business/edu-biz-*.jsonl`（业务事件归档）
- **统一 Schema**：每条含 v/ts/level/layer/event/trace_id/req_id/user_id/school_id/duration_ms/data
- **全链路追踪**：trace_id 从前端→HTTP→arq Worker→LLM 调用全程传播
- **前端日志上报**：`POST /api/v1/client-logs`（clientLogger.js 批量发送 + 错误立即发 + sendBeacon 兜底）
- **查询工具**：`scripts/edu-log`——排查问题时优先用日志，不要从代码猜原因
  - 先广后窄：`errors`/`alerts`/`slow`/`stats`/`tail` 定方向，再用 `trace`/`req`/`user`/`exam`/`task` 按 ID 精确定位
  - 按来源分：前端问题用 `frontend`，LLM 问题用 `llm`，分数/状态问题用 `business`
  - 阅卷/分数/导入类问题通常组合：`task` + `exam` + `business`；登录/权限类：`user` 或 `req`；慢接口：`slow` → `trace`
  - 完整场景示例见 `docs/ops/logging.md`，单命令用法 `scripts/edu-log <command> --help`
- **保留策略**：14 天热存 → 120 天 gzip → business 保留 365 天（`scripts/edu-log-maintain` cron）
- **业务事件**：`business_event()` 记录状态变更/分数修改/权限拒绝/登录等

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
