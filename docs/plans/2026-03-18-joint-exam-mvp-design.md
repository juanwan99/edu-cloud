# edu-cloud P1 联考 MVP 设计文档

> snapshot: 2026-03-18
> 状态: 设计完成，待实现

## §0 决策摘要

| 决策项 | 选择 | 备选（弃用） | 理由 |
|--------|------|-------------|------|
| MVP 范围 | 纯管理（学校+联考+成绩） | 含 AI 共享阅卷 | 共享阅卷依赖云端 GPU/LLM 调度，复杂度跳级 |
| 下发模式 | 深度下发（元数据+答题卡模板） | 轻量下发（仅元数据） | 统一模板确保评分一致性 |
| 模板权威源 | 出题校 exam-ai 创建→上传云端→其他校拉取 | 云端创建 / 离线分发 | 复用 exam-ai 已有 card-editor，避免重建 |
| 同步触发 | 纯手动（按钮触发） | 定时轮询 / 混合 | MVP 简洁，手动可控 |
| 成绩粒度 | 学生逐题明细 | 科目总分 / 学校聚合 | 数据价值最大，支持逐题分析 |
| 验证规模 | 2 所模拟学校 | 3 所 | 验证数据流正确性，不验证规模 |
| 架构路径 | 双端对称开发（edu-cloud 先行） | edu-cloud 优先 / 接口契约先行 | 职责清晰 + 聚焦开发 |
| 逐题明细存储 | JSONB 列（detail_scores） | 独立关联表 | 题目数不固定，JSON 避免超宽表；排名用冗余 total_score 列 |
| Service 异常体系 | 自定义异常 + 全局处理器 | HTTPException 直抛 | 与 exam-ai 一致，Service 层不依赖 FastAPI |
| 模板文件存储 | 本地文件系统（uploads/） | 对象存储 | MVP 2 所学校，数据量极小 |

## §1 数据流全景

```
出题校 exam-ai                    edu-cloud                     参与校 exam-ai
─────────────                    ─────────                     ─────────────
1. card-editor 创建模板
2. 点击"上传联考模板" ──push──→  3. 存储模板+创建联考
                                 4. 协调员指定参与校
                                 5. 协调员点击"下发"
                                           ←──pull── 6. 点击"拉取联考"
                                                      7. 收到联考元数据+模板
                                                      8. 本地扫描→阅卷→逐题评分
                                                      9. 点击"上报成绩" ──push──→
1. 本地阅卷完成
2. 点击"上报成绩" ──push──→     10. 汇总所有校成绩
                                11. 跨校排名+对比（平台管理员查看）
```

## §2 数据模型

### 2.1 现有模型变更

**RegisteredSchool** — 确认已有字段（无需新增）：
- `name: str` — 已存在（school.py:17）
- `is_active: bool = True` — 已存在（school.py:24）
- `district: str` — 已存在
- 本次无新增字段，现有字段满足需求

**JointExam** — 新增字段：
- `creator_school_id: UUID (FK → registered_schools.id)` — 出题校
- `template_file_path: str | None` — 模板存储根路径
- `answer_detail_schema: JSON | None` — 各科目的题目结构，由 `upload_template` 写入。格式: `{"YW": [{"id": "q1", "max_score": 10, "type": "主观题"}, ...], "SX": [...]}`。`pull_joint_exams` 响应中包含此字段，参与校据此了解每科题目结构。

**JointExam 状态机改造**：

现有状态 → 新状态对应表：

| 现有 | 新 | 说明 |
|------|-----|------|
| draft | draft | 不变 |
| distributed | templates_ready, distributed | 拆分：模板上传完成 vs 协调员下发 |
| scanning | collecting | 云端不关心扫描细节，只关心成绩收集 |
| grading | （删除） | 阅卷是学校本地状态，云端不追踪 |
| completed | completed | 不变 |
| archived | archived | 不变 |

```
draft → templates_ready → distributed → collecting → completed → archived
```
- `draft`: 联考创建，等待出题校上传模板
- `templates_ready`: 所有科目模板上传完毕（自动推进，判定: `subjects` JSON 的全部 `code` 对应的 `uploads/templates/{exam_id}/{code}/skeleton.json` 均存在）
- `distributed`: 协调员手动下发给参与校
- `collecting`: 首次收到任意学校的成绩时自动推进（出题校和参与校的上报同等计入）
- `completed`: 所有参与校（含出题校）所有科目上报完毕（自动推进）或协调员手动截止
- `archived`: 归档

**JointExamParticipant** — 新增字段：
- `is_creator: bool = False` — 区分出题校和参与校

**JointExamParticipant.status 改造**：

| 现有 | 新 | 说明 |
|------|-----|------|
| pending | pending | 不变 |
| accepted | （删除） | MVP 手动添加即参与，无审批流程 |
| scanning | （删除） | 云端不追踪 |
| scores_uploaded | scores_uploaded | 保留，表示该校已上报完成 |
| completed | （删除） | 合并到 scores_uploaded |

新 status: `pending → scores_uploaded`（按科目追踪上报进度，全部科目上报后自动推进）

### 2.2 新增模型

**JointExamStudentResult** — 替代旧 JointExamScore（逐题明细粒度）：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| joint_exam_id | FK | 联考 |
| school_id | FK | 上报学校 |
| subject_code | str | 科目编码 |
| student_name | str | 学生姓名 |
| student_number | str | 学号 |
| total_score | float | 冗余总分（方便排名查询） |
| detail_scores | JSONB | `[{"question_id": "q1", "score": 5.0, "max_score": 10.0}, ...]` |
| uploaded_at | datetime | 上报时间 |

唯一约束：`(joint_exam_id, school_id, subject_code, student_number)` — 同一学生同一科目可 upsert。

索引：
- `(joint_exam_id, subject_code, total_score DESC)` — 排名查询
- `(joint_exam_id, school_id)` — 按校汇总

### 2.3 模板文件存储

```
edu-cloud/uploads/templates/{joint_exam_id}/{subject_code}/
  skeleton.json    # 答题卡骨架（JSON）
  template.pdf     # 答题卡 PDF
```

本地文件系统存储。Docker 部署时挂载 volume。

## §3 API 端点设计

### 3.1 学校管理（JWT 认证，platform_admin/district_admin）

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/v1/schools` | 注册新学校（返回一次性明文 API Key） |
| GET | `/api/v1/schools` | 学校列表（支持 district/is_active 过滤） |
| GET | `/api/v1/schools/{id}` | 学校详情 |
| PATCH | `/api/v1/schools/{id}` | 更新学校信息/停用/启用 |
| POST | `/api/v1/schools/{id}/rotate-key` | 轮换 API Key（返回新明文 key） |

### 3.2 联考管理（JWT 认证，exam_coordinator+）

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/v1/joint-exams` | 创建联考（指定出题校、科目列表） |
| GET | `/api/v1/joint-exams` | 联考列表 |
| GET | `/api/v1/joint-exams/{id}` | 联考详情（含参与校+各科模板状态+上报进度） |
| PATCH | `/api/v1/joint-exams/{id}` | 更新联考信息 |
| POST | `/api/v1/joint-exams/{id}/distribute` | 手动下发（templates_ready → distributed） |
| POST | `/api/v1/joint-exams/{id}/complete` | 手动截止（collecting → completed） |
| POST | `/api/v1/joint-exams/{id}/participants` | 添加参与校 |
| DELETE | `/api/v1/joint-exams/{id}/participants/{school_id}` | 移除参与校 |

### 3.3 成绩查看（JWT 认证，权限分级）

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/joint-exams/{id}/results` | 跨校排名（支持 subject_code 过滤） |
| GET | `/api/v1/joint-exams/{id}/results/by-school` | 按学校分组对比（平均分/最高/中位数/参考人数） |
| GET | `/api/v1/joint-exams/{id}/results/students/{student_number}` | 单个学生逐题得分+各科排名 |

### 3.4 同步端点（API Key 认证，学校端调用）

| 方法 | 路径 | 方向 | 用途 |
|------|------|------|------|
| POST | `/api/v1/sync/heartbeat` | 校→云 | 保留不变 |
| GET | `/api/v1/sync/joint-exams` | 校←云 | 改造：返回联考元数据+各科模板下载 URL（服务端生成绝对 URL） |
| POST | `/api/v1/sync/scores` | 校→云 | 改造：接收逐题明细 |
| POST | `/api/v1/sync/templates` | 校→云 | 新增：出题校上传模板（multipart: skeleton JSON + PDF） |
| GET | `/api/v1/sync/templates/{exam_id}/{subject_code}` | 校←云 | 新增：下载模板文件 |

**`GET /api/v1/sync/joint-exams` 响应示例：**

```json
{
  "joint_exams": [
    {
      "id": "uuid-xxx",
      "name": "2026年春季联考",
      "status": "distributed",
      "subjects": [
        {
          "code": "YW",
          "name": "语文",
          "template_url": "http://cloud:9000/api/v1/sync/templates/uuid-xxx/YW",
          "answer_detail_schema": [
            {"id": "q1", "max_score": 10, "type": "主观题"},
            {"id": "q2", "max_score": 5, "type": "选择题"}
          ]
        }
      ],
      "created_at": "2026-03-18T10:00:00+08:00"
    }
  ]
}
```

`template_url` 由服务端拼接（`{base_url}/api/v1/sync/templates/{exam_id}/{subject_code}`），exam-ai 直接 GET 下载。

## §4 Service 层设计（edu-cloud）

### 4.1 school_service.py

```python
class SchoolService:
    async def create_school(name, code, district) -> tuple[RegisteredSchool, str]
        # 生成 API Key（{code}:{random_secret}），bcrypt 存储
        # 返回 (model, 明文 key)——明文仅此一次

    async def list_schools(district=None, is_active=None) -> list[RegisteredSchool]
    async def get_school(school_id) -> RegisteredSchool
    async def update_school(school_id, **fields) -> RegisteredSchool
    async def rotate_api_key(school_id) -> str  # 返回新明文 key
```

### 4.2 joint_exam_service.py

```python
class JointExamService:
    async def create_exam(name, subjects, creator_school_id, created_by) -> JointExam
        # 状态 = draft，自动创建 Participant(is_creator=True)

    async def add_participant(exam_id, school_id) -> JointExamParticipant
    async def remove_participant(exam_id, school_id)

    async def upload_template(exam_id, subject_code, skeleton_data, pdf_bytes, answer_schema: list)
        # 保存文件到 uploads/templates/{exam_id}/{subject_code}/
        # 将 answer_schema 写入 JointExam.answer_detail_schema[subject_code]
        # 判定: subjects JSON 全部 code 对应的 skeleton.json 均存在 → draft → templates_ready

    async def distribute(exam_id)
        # 校验 status=templates_ready → 推进到 distributed

    async def submit_scores(exam_id, school_id, subject_code, student_results: list)
        # 批量 upsert JointExamStudentResult（student_number 去重）
        # 出题校（is_creator=True）和参与校的上报同等处理，无特殊逻辑
        # 状态推进:
        #   首次收到任意学校的成绩 → distributed → collecting
        #   所有 Participant（含出题校）所有科目均已上报 → collecting → completed
        # 上报完成判定: Participant.status 推进到 scores_uploaded 当该校所有 subjects 都有成绩记录

    async def force_complete(exam_id)
        # 协调员手动截止（collecting → completed）

    async def get_exam_detail(exam_id) -> dict
        # 联考详情 + 各校上报进度 + 各科模板状态
```

### 4.3 results_service.py

```python
class ResultsService:
    async def get_rankings(exam_id, subject_code=None) -> list[dict]
        # subject_code 指定时：该科排名
        # subject_code=None：全科总分排名（SUM(total_score) GROUP BY student_number）

    async def get_school_comparison(exam_id) -> list[dict]
        # 按学校+科目聚合：平均分、最高分、中位数、参考人数

    async def get_student_detail(exam_id, student_number) -> dict
        # 该生所有科目逐题得分 + 各科排名位次
```

### 4.4 异常体系

```python
# services/exceptions.py
class NotFoundError(Exception): ...       # → 404
class PermissionDeniedError(Exception): ... # → 403
class ValidationError(Exception): ...     # → 422
class ConflictError(Exception): ...       # → 409（重复上报）
class StateError(Exception): ...          # → 409（状态机非法转换）
```

全局异常处理器在 app.py 注册，统一映射 HTTP 状态码。与 exam-ai 模式一致。

## §5 exam-ai 侧变更

### 5.1 新增模块

```
src/exam_ai/
  services/
    cloud_sync.py       # 云端同步服务
  api/
    cloud_sync.py       # 同步触发端点
```

### 5.2 CloudSyncService

```python
class CloudSyncService:
    def __init__(self, cloud_url: str, api_key: str):
        self.client = httpx.AsyncClient(base_url=cloud_url, headers={"X-API-Key": api_key})

    async def push_template(subject_id: int) -> dict
        # 读取本地 editor_layout → 导出 skeleton JSON + PDF bytes
        # POST /api/v1/sync/templates (multipart)

    async def pull_joint_exams() -> list[dict]
        # GET /api/v1/sync/joint-exams
        # 返回联考列表（含各科模板下载 URL）

    async def pull_template(exam_id: str, subject_code: str) -> dict
        # GET /api/v1/sync/templates/{exam_id}/{subject_code}
        # 下载 skeleton + PDF → 写入本地 Template 表

    async def push_scores(local_exam_id: int, subject_code: str, joint_exam_id: str) -> dict
        # 查本地 GradingResult → 组装逐题明细
        # POST /api/v1/sync/scores

    async def heartbeat() -> dict
        # POST /api/v1/sync/heartbeat
```

### 5.3 API 端点（手动触发）

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/cloud/push-template` | 出题校：上传当前科目模板到云端 |
| POST | `/api/cloud/pull-exams` | 参与校：拉取联考列表+模板 |
| POST | `/api/cloud/push-scores` | 上报指定联考+科目的成绩明细 |
| GET | `/api/cloud/status` | 同步状态（上次心跳、待上报科目数） |

### 5.4 配置

```env
CLOUD_URL=http://localhost:9000
CLOUD_API_KEY=SCHOOL01:secret123
CLOUD_ENABLED=false
```

`CLOUD_ENABLED=false` 时：
- `/api/cloud/*` 路由不注册（app.py 中条件判断），返回 404
- `CloudSyncService` 不实例化（DI 中不注册），避免 `CLOUD_URL` 未设置时的配置错误
- `CLOUD_URL` 和 `CLOUD_API_KEY` 在 `CLOUD_ENABLED=false` 时为 Optional，不校验

### 5.5 不改动的部分

- card-editor、答案解析管线、AI Agent、阅卷流程 — 全部不动
- 现有模型和路由 — 不动
- 前端 — MVP 不加按钮，纯 API 验证

## §6 测试策略

### 6.1 edu-cloud 测试

**基础设施修复（前置）：**
- 补 alembic.ini + 首个 migration
- 修复 Dockerfile（移除 COPY alembic.ini）
- conftest.py 已有 SQLite in-memory fixture，沿用

**按模块测试：**

| 模块 | 测试范围 | 预估数量 |
|------|---------|---------|
| school_service | CRUD + API Key 生成/轮换/验证 + 停用 | 8-10 |
| joint_exam_service | 创建 + 参与校管理 + 模板上传 + 状态机推进 + 成绩提交 | 12-15 |
| results_service | 排名 + 按校对比 + 学生明细 | 6-8 |
| API 层 | 端点集成测试（AsyncClient） | 15-20 |
| sync 端点 | API Key 认证 + 模板上传/下载 + 成绩提交 | 8-10 |

总计预估：50-60 个测试。

**边界条件重点：**
- 状态机非法转换（draft 直接 distribute → StateError）
- 重复上报（同学生同科目 → upsert，不报错）
- 空成绩上报（0 条记录 → ValidationError）
- 模板未全部上传就尝试下发 → StateError
- API Key 格式错误 / 已停用学校 → 401

### 6.2 exam-ai 测试

| 模块 | 测试范围 | 预估数量 |
|------|---------|---------|
| cloud_sync service | mock httpx → 验证请求格式和错误处理 | 8-10 |
| cloud_sync API | CLOUD_ENABLED=false → 404; =true → 正常 | 4-6 |

### 6.3 端到端验证

种子数据（2 所学校）：
- `SCHOOL01`（测试一校，出题校）+ `SCHOOL02`（测试二校，参与校）
- 1 场联考，2 个科目（语文+数学），每校 5 个学生
- 完整流程：创建联考 → 上传模板 → 下发 → 拉取 → 上报成绩 → 排名查看

验证脚本（`scripts/e2e_joint_exam.py`）：用 httpx 模拟完整流程，断言每一步的状态和数据。

## §7 Alembic 迁移策略

1. 补 `alembic.ini`（从 .env 读 DATABASE_URL）
2. 修改 `alembic/env.py` 引用 `edu_cloud.models.base.Base.metadata`
3. 生成首个 migration：包含所有现有表 + JointExamStudentResult 新表 + JointExamScore 删除
4. app.py lifespan 中的 `create_all()` 保留用于开发（`if settings.debug`），生产走 Alembic

## §8 实现分期

### Phase 1: edu-cloud 基础设施 + 学校管理

- Alembic 修复 + 首个 migration
- Dockerfile 修复
- services/exceptions.py + 全局异常处理器
- SchoolService + API 端点 + 测试

### Phase 2: edu-cloud 联考核心

- JointExamService（创建/参与校/模板上传/状态机/成绩提交）
- 模板文件存储
- sync 端点改造（templates 上传/下载、scores 新粒度）
- 测试

### Phase 3: edu-cloud 成绩查看

- ResultsService（排名/按校对比/学生明细）
- 成绩查看 API 端点
- 测试

### Phase 4: exam-ai sync client

- CloudSyncService + API 端点
- CLOUD_ENABLED 开关
- mock 测试

### Phase 5: 端到端验证

- 种子数据（2 所学校）
- E2E 验证脚本
- 完整流程跑通

## §9 不做的事（明确排除）

- 前端 UI（MVP 纯 API 验证，用 curl/httpx 测试）
- AI 共享阅卷（P3）
- 统一题库（P4）
- 自动同步/轮询（后续增强）
- WebSocket 实时通知
- 文件对象存储（S3/MinIO）
- 多租户隔离（MVP 全局可见）

## §10 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| exam-ai GradingResult 结构与逐题明细不匹配 | push_scores 组装困难 | Phase 4 开始前先调研 exam-ai 的 grading 数据结构 |
| 模板 PDF 文件较大（>5MB） | 上传/下载慢 | MVP 不限制大小，后续加压缩 |
| 跨校排名中学号重复 | 排名错误 | `(school_id, student_number)` 联合唯一 |
| PostgreSQL JSONB 聚合性能 | 大数据量慢 | MVP 数据量小（2 校），后续加物化视图 |
