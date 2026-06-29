# edu-cloud 运行时安全与数据一致性深度调查报告

> 调查日期：2026-06-04  
> 调查对象：ECS `/home/ops/projects/edu-cloud`  
> 调查方式：远程只读审查、关键路径代码追踪、运行时配置核验、定向测试与最小复现  
> 调查结论版本：v1.0  
> 调查边界：本报告未修改业务代码，未输出或记录任何密钥明文，未对生产数据执行破坏性写入

---

## 1. 执行摘要

本次调查确认 edu-cloud 项目整体可运行，核心服务部署在 ECS 上，由 systemd 启动 FastAPI 后端，nginx 对外代理，Redis/Postgres 容器当前绑定在本机回环地址。前端静态检查通过，定向后端测试通过。

但调查也确认了两个需要优先处理的高风险问题：

1. 客观题上传接口存在题目归属链校验缺失，已通过最小 ASGI 用例复现：调用方可传入“科目 A”，同时提交“科目 B 的 question_id”，接口返回 200 并成功落库为 `subject_id=A, question_id=B`。这会污染分数、统计、阅卷和后续学情分析。
2. 旧阅卷导入接口只要求登录态，不要求阅卷管理权限，并接受服务器任意目录路径作为导入源。导入器会把匹配图片路径直接写入 `StudentAnswer.image_path`，后续图片读取接口再按该路径直接 stream 文件。该问题构成服务器文件路径读取面和数据污染面，建议立即收紧权限和路径 containment。

此外，线上进程实际仍以 `ENVIRONMENT=development` 运行，并使用 SQLite 主库；仓库中的 `docker-compose.yml` 与真实部署存在明显漂移，包含公开端口和默认 Postgres 密码配置。AI 工具的 `module_code` 与学校模块枚举也存在不一致，可能导致部分工具被模块开关静默禁用。

---

## 2. 调查范围与方法

### 2.1 范围

本次调查覆盖以下层面：

- ECS 连接和运行进程核验
- Git 工作区状态与项目结构
- 后端 FastAPI 入口、认证鉴权、关键业务路由
- 扫描上传、客观题评分、阅卷导入、答题图片读取
- 配置、部署、数据库、Redis/Postgres 容器暴露面
- AI 工具注册与学校模块治理
- 前端基本安全面，包括动态 HTML 使用与 lint
- 定向测试、静态检查和最小漏洞复现

### 2.2 方法

采用以下方法交叉验证：

- 远程执行只读命令检查项目路径、进程、端口、数据库状态
- 使用 `rg`/`sed`/`nl` 追踪后端关键路由和服务实现
- 运行定向 pytest，覆盖已存在的安全相关测试
- 运行前端 lint
- 运行 ruff 的基础静态检查
- 用内存数据库和 ASGI 客户端构造最小请求，复现客观题归属链缺陷

### 2.3 限制

- 本次未执行破坏性生产 PoC。
- 对“阅卷导入任意目录”问题只做代码路径验证，未在生产库写入测试数据。
- 本次未执行全量 pytest；仅执行了与扫描、阅卷、兼容路由、登录模拟相关的定向测试。
- 本次未进行完整黑盒渗透测试、密码强度审计或云安全组审计。

---

## 3. 运行时与部署快照

### 3.1 服务器与服务

ECS 连接成功，目标主机：

- hostname：`iZf8z2piigunrk8ixto7hnZ`
- 当前用户：`ops`
- 项目路径：`/home/ops/projects/edu-cloud`
- API 进程：`uvicorn edu_cloud.api.app:create_app --factory --host 127.0.0.1 --port 9000`
- 对外入口：nginx 监听 80/443
- Redis 容器：`127.0.0.1:6379->6379/tcp`
- Postgres 容器：`127.0.0.1:5432->5432/tcp`

### 3.2 Git 状态

审查时工作区状态：

```text
## master...origin/master
?? docs/2026-06-04-project-deep-investigation.md
?? docs/archive/plans/2026-06-04-module-governance-repair-plan.md
```

本报告创建前，远端已有两份未跟踪文档。本次未覆盖这些文件。

### 3.3 实际配置

运行时读取到的关键配置：

```text
ENVIRONMENT=development
LOG_LEVEL=DEBUG
DATABASE_URL_PREFIX=sqlite+aiosqlite
KNOWLEDGE_DRAFT_VISIBLE=True
CORS_ORIGINS=['http://localhost:5173']
```

数据库状态：

- Alembic 当前使用 `SQLiteImpl`
- 当前迁移版本：`a1b2_chat_msgs`
- 主库文件：`/home/ops/projects/edu-cloud/edu_cloud.db`
- 主库大小：约 538 MB
- `/home/ops/projects/edu-cloud/data/edu_cloud.db` 为 0 字节

判断：当前真实生产数据路径是仓库根目录下 SQLite 文件，而不是 compose 中声明的 Postgres。Postgres 容器虽然存在，但应用实际未使用。

---

## 4. 高风险发现

## Finding P1-01：客观题上传缺少完整归属链校验，导致跨科目错写成绩

### 风险等级

P1，高优先级数据完整性问题。

### 影响范围

受影响接口：

- `POST /api/v1/scan/upload-objective`
- 兼容接口中的客观题上传逻辑
- 可能相关的普通扫描上传和批量上传归属校验

影响对象：

- `StudentAnswer`
- 客观题分数
- 科目总分
- 阅卷结果
- 学情统计
- AI 分析和后续报告

### 代码证据

主路由：

- `/home/ops/projects/edu-cloud/src/edu_cloud/modules/scan/router.py:315-331`

接口先正确校验了考试和科目关系：

```text
Exam.id == req.exam_id
Subject.id == req.subject_id
Subject.exam_id == req.exam_id
Subject.school_id == current school
```

但在逐题处理时：

- `/home/ops/projects/edu-cloud/src/edu_cloud/modules/scan/router.py:373-399`

只校验：

```text
Question.id == ans.question_id
Question.school_id == current school
```

没有校验：

```text
Question.subject_id == req.subject_id
```

因此调用方可以提交 `subject_id=A`，但 `answers[].question_id` 指向同校其他科目的题目 B。接口随后会写入：

```text
StudentAnswer(
  exam_id=req.exam_id,
  subject_id=req.subject_id,
  question_id=ans.question_id
)
```

从而形成 `subject_id` 与 `question_id` 不一致的脏数据。

兼容接口存在同类问题：

- `/home/ops/projects/edu-cloud/src/edu_cloud/api/compat_router.py:392-409`

辅助校验函数也存在关系链不完整：

- `/home/ops/projects/edu-cloud/src/edu_cloud/modules/scan/router.py:24-41`

`_verify_ownership` 分别校验 Exam、Subject、Question 属于同一学校，但未校验：

```text
Subject.exam_id == exam_id
Question.subject_id == subject_id
```

这意味着普通图片上传路径也存在相同类型的数据一致性风险。

### 已复现证据

使用内存数据库和 ASGI 客户端构造最小用例：

1. 创建同一学校下的 exam。
2. 创建 subject A 和 subject B。
3. 在 subject B 下创建 question B。
4. 调用 `POST /api/v1/scan/upload-objective`，请求体使用 `subject_id=subject A`，但 `answers[0].question_id=question B`。
5. 接口返回 `200`。
6. 数据库中出现 `StudentAnswer(subject_id=A, question_id=B)`。

复现输出摘要：

```text
status 200
answers 1 [('subjectA-id', 'questionB-id', 1.0)]
```

### 安全与业务影响

该问题不需要突破租户边界，只要同校内存在多个科目和题目即可触发。它的核心风险是数据污染：

- 学生某科成绩可被写入其他科目的题目得分
- 科目总分、正确率、知识点分析可能失真
- 阅卷工作流可能读取到不属于当前科目的答案
- 后续补丁如果只修显示层，历史脏数据仍会残留

### 建议修复

1. 在 `upload_objective` 中逐题查询改为：

```python
select(Question).where(
    Question.id == ans.question_id,
    Question.subject_id == req.subject_id,
    Question.school_id == current["current_role"].school_id,
)
```

2. 将 `_verify_ownership` 改为完整链路校验：

```text
Exam.id == exam_id AND Exam.school_id == school_id
Subject.id == subject_id AND Subject.exam_id == exam_id AND Subject.school_id == school_id
Question.id == question_id AND Question.subject_id == subject_id AND Question.school_id == school_id
```

3. 兼容接口同步修复，避免旧客户端绕过新逻辑。
4. 增加回归测试：

- `upload_objective_rejects_question_from_other_subject`
- `upload_single_rejects_subject_exam_mismatch`
- `upload_single_rejects_question_subject_mismatch`
- compat route 对应测试

5. 增加数据体检脚本，扫描历史脏数据：

```sql
SELECT sa.id, sa.exam_id, sa.subject_id, sa.question_id
FROM student_answers sa
JOIN questions q ON q.id = sa.question_id
WHERE sa.subject_id <> q.subject_id;
```

---

## Finding P1-02：阅卷导入接口权限过宽，并接受服务器任意目录

### 风险等级

P1，高优先级授权与服务器路径访问问题。

### 影响范围

受影响接口：

- `POST /api/v1/marking/import`
- `GET /api/v1/marking/answer/{answer_id}/image`

影响对象：

- 服务器本地文件路径
- `StudentAnswer.image_path`
- 阅卷数据
- 图片读取接口

### 代码证据

导入路由：

- `/home/ops/projects/edu-cloud/src/edu_cloud/modules/marking/router.py:243-253`

该接口依赖：

```text
current: dict = Depends(get_current_user)
```

没有使用：

```text
require_permission(Permission.MANAGE_GRADING)
```

也没有限制必须为学校管理员或阅卷管理员。

导入器路径处理：

- `/home/ops/projects/edu-cloud/src/edu_cloud/modules/marking/importer.py:15-27`
- `/home/ops/projects/edu-cloud/src/edu_cloud/modules/marking/importer.py:42-44`

`folder_path` 经 `_normalize_path` 后只判断是否为目录：

```text
root = _normalize_path(folder_path)
if not root.is_dir():
    raise ValueError(...)
```

没有校验路径必须位于 `UPLOAD_DIR`、`STORAGE_ROOT` 或学校专属目录下。

导入器扫描与落库：

- `/home/ops/projects/edu-cloud/src/edu_cloud/modules/marking/importer.py:80-135`

它会扫描如下结构：

```text
{folder_path}/{subject}/{question}/{student}.png
{folder_path}/{subject}/{question}/{student}.jpg
{folder_path}/{subject}/{question}/{student}.jpeg
{folder_path}/{subject}/{question}/{student}.tif
{folder_path}/{subject}/{question}/{student}.tiff
```

并把文件路径直接保存为：

```text
image_path = str(img_file)
```

图片读取接口：

- `/home/ops/projects/edu-cloud/src/edu_cloud/modules/marking/router.py:332-363`

该接口只校验：

```text
StudentAnswer.id == answer_id
StudentAnswer.school_id == current school
os.path.isfile(answer.image_path)
```

随后直接打开并 stream：

```text
open(answer.image_path, "rb")
```

没有 containment 校验。

### 风险描述

任何拥有登录态且能命中该接口的同校用户，都可能触发服务器从指定目录导入文件。虽然导入器只接受特定图片扩展名，并要求目录形态符合 `{subject}/{question}/{student}.ext`，但这仍然构成危险面：

- 可扫描并导入非预期业务目录下的图片文件
- 可污染科目、题目、学生答卷数据
- 可将服务器本地路径持久化到数据库
- 后续图片接口会把该路径文件作为答题图片返回

该风险尤其来自“旧导入接口”和新扫描 pipeline 的安全标准不一致。新 pipeline 已经有路径 containment 思路，而该 legacy marking import 没有同步收紧。

### 建议修复

1. 给 `/api/v1/marking/import` 增加强权限：

```python
current: dict = Depends(require_permission(Permission.MANAGE_GRADING))
```

2. 对 `folder_path` 做规范化和 containment：

```text
resolved_root = root.resolve()
allowed_root = Path(settings.UPLOAD_DIR).resolve()
resolved_root.is_relative_to(allowed_root)
```

如果需要支持多个业务根目录，则显式列白名单：

```text
UPLOAD_DIR
STORAGE_ROOT
paper segmentation output root
```

3. 图片读取接口同样做 containment，不能只信任数据库中的 `image_path`。
4. 对导入创建 Subject/Question 的行为增加产品级确认或拆分权限，避免普通阅卷流自动扩展考试结构。
5. 增加回归测试：

- 非 `MANAGE_GRADING` 用户调用 import 返回 403
- `folder_path=/tmp` 或 `/etc` 返回 400
- `image_path` 指向 allowed root 外时图片接口返回 403/404
- Windows 路径转换后仍必须落在白名单根目录内

---

## 5. 中风险发现

## Finding P2-01：线上运行在 development，文档接口和调试配置未按生产收敛

### 风险等级

P2，中优先级配置风险。

### 代码证据

默认配置：

- `/home/ops/projects/edu-cloud/src/edu_cloud/config.py:12-23`
- `/home/ops/projects/edu-cloud/src/edu_cloud/config.py:47-52`
- `/home/ops/projects/edu-cloud/src/edu_cloud/config.py:79-83`

FastAPI 文档开关：

- `/home/ops/projects/edu-cloud/src/edu_cloud/api/app.py:219-226`

代码逻辑为：

```text
_is_prod = settings.ENVIRONMENT == "production"
docs_url = None if _is_prod else "/docs"
redoc_url = None if _is_prod else "/redoc"
openapi_url = None if _is_prod else "/openapi.json"
```

实际配置为：

```text
ENVIRONMENT=development
LOG_LEVEL=DEBUG
KNOWLEDGE_DRAFT_VISIBLE=True
```

### 风险描述

由于线上进程仍是 development：

- `/docs`、`/redoc`、`/openapi.json` 理论上会启用
- 日志级别为 DEBUG
- draft 知识内容默认可见

这不一定等于即时漏洞，但属于生产环境暴露面偏大。若 nginx 没有拦截文档路径，则接口结构和模型信息会暴露给外部访问者。

### 建议修复

1. 将线上 `.env` 改为：

```text
ENVIRONMENT=production
LOG_LEVEL=INFO
KNOWLEDGE_DRAFT_VISIBLE=false
```

2. nginx 层同步限制 `/docs`、`/redoc`、`/openapi.json`。
3. 保留 startup checks，避免 production 使用默认密钥启动。
4. 对 draft 可见策略增加角色约束，而不是全局开关长期为 true。

---

## Finding P2-02：仓库 compose 配置与真实部署漂移，且包含危险默认值

### 风险等级

P2，中优先级部署风险。

### 代码证据

- `/home/ops/projects/edu-cloud/docker-compose.yml:4-5`
- `/home/ops/projects/edu-cloud/docker-compose.yml:15-22`
- `/home/ops/projects/edu-cloud/docker-compose.yml:26-29`

配置包含：

```text
9000:9000
5432:5432
6379:6379
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

### 真实状态

实际运行中：

- API 由 systemd 运行在 `127.0.0.1:9000`
- nginx 对外
- Redis/Postgres 容器实际绑定在 `127.0.0.1`
- 应用当前使用 SQLite，不使用 compose 中的 Postgres

### 风险描述

该 compose 文件如果被后来维护者误用于生产，会导致：

- API、Postgres、Redis 直接公开到宿主网络
- Postgres 使用默认弱密码
- 运维误以为系统使用 Postgres，而真实数据仍在 SQLite

这属于“部署文档即风险”的问题：代码库中的运行入口会影响未来维护者行为。

### 建议修复

1. 将 compose 改成开发专用并明确文件名，如 `docker-compose.dev.yml`。
2. 所有端口默认绑定 `127.0.0.1`。
3. 移除默认数据库密码，改为必须从环境变量读取。
4. 在 README 或 deployment 文档中明确当前生产运行方式。
5. 若计划迁移 Postgres，单独制定 SQLite -> Postgres 迁移与回滚方案。

---

## Finding P2-03：AI 工具 module_code 与学校模块枚举不一致

### 风险等级

P2，中优先级功能治理问题。

### 代码证据

学校模块枚举：

- `/home/ops/projects/edu-cloud/src/edu_cloud/models/school_settings.py:20-30`

当前模块包括：

```text
exam
grading
homework
study_analytics
research
teaching
calendar
studio
conduct
```

但 AI 工具使用了枚举中不存在的模块码：

- `/home/ops/projects/edu-cloud/src/edu_cloud/ai/engine/tools/card_layout.py:21-63`
  - `module_code="card"`
- `/home/ops/projects/edu-cloud/src/edu_cloud/ai/engine/tools/misc.py:136-155`
  - `module_code="knowledge"`

### 风险描述

如果 AI 工具启用逻辑依赖学校模块开关，则这些工具可能出现：

- 永远不可用
- 在不同学校行为不一致
- 被错误归类到其他模块
- 后续权限审计无法准确覆盖

该问题不是直接安全漏洞，但会造成“功能已注册、治理不可见”的漂移。

### 建议修复

1. 明确 `card` 和 `knowledge` 是否应成为正式学校模块。
2. 如果不应独立成模块，将工具改为现有模块码：

```text
card -> exam
knowledge -> research 或 study_analytics
```

3. 增加工具注册一致性测试：所有 `edu_tool(module_code=...)` 必须存在于 `MODULE_CODES`。
4. 在模块治理文档中声明 AI 工具 module_code 的规范。

---

## 6. 质量与测试结果

### 6.1 后端定向测试

执行范围：

- `tests/test_api/test_scan_path_containment.py`
- `tests/test_api/test_scan_browse_dir_security.py`
- `tests/test_api/test_marking_import_isolation.py`
- `tests/test_api/test_compat.py`
- `tests/test_api/test_impersonate.py`

结果：

```text
63 passed, 33 warnings
```

说明：

- 现有扫描路径 containment 测试通过。
- 现有 marking import isolation 只覆盖跨校 exam 拒绝，不覆盖权限和任意路径限制。
- compat 和 impersonate 定向测试通过。

### 6.2 前端检查

执行：

```text
npm run lint -- --quiet
```

结果：通过。

补充观察：

- 未发现明显裸 `v-html` 大面积风险。
- 已扫描到的动态 HTML 使用 DOMPurify。
- JWT 存在 localStorage 中，属于可进一步加固项，但本次未列为高风险。

### 6.3 Python 静态检查

执行：

```text
.venv/bin/python -m ruff check src tests --select F,E9
```

结果：失败，约 250 个问题。

主要类别：

- 未使用 import
- 未使用变量
- f-string 无插值
- 重复定义
- 少量真实风险项

值得优先处理：

- `/home/ops/projects/edu-cloud/src/edu_cloud/modules/adaptive/sync.py`
  - 存在 `F821 Undefined name AsyncSession`

判断：当前静态质量门未收敛，不建议把 ruff 全量作为立即阻塞项；建议先按 `F821/F811/E9` 分阶段收敛，再扩展到 unused imports。

---

## 7. 其他观察

### 7.1 数据库形态

当前项目同时存在 SQLite 主库和 Postgres 容器，但应用实际连接 SQLite。SQLite 文件已达到约 538 MB，并且权限显示为可执行/全权限形态：

```text
-rwxrwxrwx 1 ops ops 538M /home/ops/projects/edu-cloud/edu_cloud.db
```

建议：

- 收紧 SQLite 文件权限。
- 明确是否继续使用 SQLite。
- 如果迁移 Postgres，先建立完整迁移演练、校验脚本和回滚方案。

### 7.2 启动 seed 行为

`create_app` lifespan 中仍包含若干 seed/demo/knowledge sync 行为：

- `/home/ops/projects/edu-cloud/src/edu_cloud/api/app.py:136-185`

这类启动期写入如果在 production 中继续执行，需要确认幂等性和失败策略。当前代码多处写着 idempotent/non-fatal，但建议生产环境显式区分：

- 开发 seed
- 演示 seed
- 生产迁移
- 启动同步

避免“启动服务”同时承担“修改生产数据结构或内容”的责任。

### 7.3 父母端/角色边界

父母端部分接口通过 `GuardianStudentLink` 做学生绑定校验，这是正确方向。观察到部分接口使用通用 `get_current_user`，并不总是显式限制当前角色必须是 parent。由于绑定链路本身仍有限制，本次未列为高风险，但建议后续做角色边界专项检查。

---

## 8. 修复优先级建议

### 8.1 立即修复，建议当天完成

1. 修复 `scan/upload-objective` 题目归属链。
2. 修复 compat 客观题上传归属链。
3. 修复 `_verify_ownership` 的 exam/subject/question 链式校验。
4. 给 `/marking/import` 增加 `MANAGE_GRADING` 权限。
5. 给 marking import 和 answer image 增加路径 containment。

### 8.2 一周内完成

1. 增加历史脏数据扫描脚本。
2. 为上述 P1 问题补全回归测试。
3. 将生产 `.env` 切换到 production 语义。
4. nginx 层屏蔽文档接口。
5. 收紧 SQLite 文件权限。

### 8.3 两周内完成

1. 整理 compose 与真实部署方式。
2. 明确 SQLite/Postgres 路线。
3. 修复 AI 工具 module_code 与学校模块枚举不一致。
4. 分阶段收敛 ruff 的 `F821/F811/E9`。

---

## 9. 建议补丁设计

### 9.1 归属链校验统一函数

建议新增统一函数，避免多个路由各自写半套校验：

```python
async def verify_exam_subject_question_chain(
    db: AsyncSession,
    *,
    school_id: str,
    exam_id: str,
    subject_id: str,
    question_id: str | None = None,
) -> tuple[Exam, Subject, Question | None]:
    ...
```

要求：

- exam 必须属于 school
- subject 必须属于 exam + school
- question 如传入，必须属于 subject + school
- 返回实体，避免重复查询

使用位置：

- `/scan/upload`
- `/scan/upload-batch`
- `/scan/upload-objective`
- compat 客观题上传
- 任何直接写入 `StudentAnswer` 的入口

### 9.2 路径 containment 工具函数

建议新增：

```python
def resolve_allowed_child(path: str | Path, allowed_roots: list[Path]) -> Path:
    resolved = Path(path).resolve()
    for root in allowed_roots:
        root_resolved = root.resolve()
        if resolved == root_resolved or resolved.is_relative_to(root_resolved):
            return resolved
    raise HTTPException(400, "Path outside allowed roots")
```

使用位置：

- marking import
- marking answer image
- 其他读取本地文件并返回给用户的接口

注意：

- Windows 路径转换后仍需再做 containment。
- 不应信任数据库中已存在的 `image_path`。
- 历史数据可能已有绝对路径，修复时要兼容或迁移。

---

## 10. 回归测试清单

建议新增或补强以下测试：

```text
test_upload_objective_rejects_question_from_other_subject
test_upload_objective_rejects_question_from_other_exam
test_upload_single_rejects_subject_from_other_exam
test_upload_single_rejects_question_from_other_subject
test_upload_batch_rejects_mismatched_question_chain
test_compat_upload_objective_rejects_question_from_other_subject
test_marking_import_requires_manage_grading
test_marking_import_rejects_path_outside_allowed_root
test_marking_answer_image_rejects_path_outside_allowed_root
test_ai_tool_module_codes_exist_in_module_codes
```

历史数据体检测试或脚本：

```sql
-- StudentAnswer subject/question mismatch
SELECT COUNT(*)
FROM student_answers sa
JOIN questions q ON q.id = sa.question_id
WHERE sa.subject_id <> q.subject_id;

-- Subject/exam mismatch through StudentAnswer
SELECT COUNT(*)
FROM student_answers sa
JOIN subjects s ON s.id = sa.subject_id
WHERE sa.exam_id <> s.exam_id;
```

---

## 11. 风险排序表

| 编号 | 等级 | 问题 | 影响 | 建议时限 |
|------|------|------|------|----------|
| P1-01 | 高 | 客观题上传缺少题目归属链校验 | 成绩与学情数据污染 | 当天 |
| P1-02 | 高 | 阅卷导入权限过宽且接受任意服务器目录 | 服务器路径读取面、数据污染 | 当天 |
| P2-01 | 中 | 线上仍为 development 配置 | 文档接口/DEBUG/draft 暴露面偏大 | 一周内 |
| P2-02 | 中 | compose 与真实部署漂移且含默认密码 | 误部署风险 | 一周内 |
| P2-03 | 中 | AI 工具 module_code 与模块枚举不一致 | 工具静默不可用或治理失真 | 两周内 |
| P3-01 | 低 | ruff 基线未收敛 | 维护成本和潜在隐藏错误 | 分阶段 |

---

## 12. 结论

edu-cloud 当前不是“整体不可控”的状态：服务可运行，定向安全测试通过，前端 lint 通过，现有鉴权体系已经有不少收敛痕迹。但本次调查确认两个 P1 问题会直接影响生产安全边界和核心数据可信度。

最优先的修复路径是先收紧所有写入 `StudentAnswer` 的归属链校验，再收紧旧阅卷导入接口的权限和路径范围。完成这两项后，应立即运行历史数据体检，判断是否已有 `subject_id/question_id` 错配数据，并决定是否需要修复脚本。

部署层面建议尽快把 production 语义落地，尤其是 `ENVIRONMENT=production`、文档接口关闭、SQLite/Postgres 策略明确化。否则后续维护者会继续在“代码声明的部署方式”和“真实运行方式”之间迷路。

---

## 附录 A：关键文件索引

```text
/home/ops/projects/edu-cloud/src/edu_cloud/modules/scan/router.py
/home/ops/projects/edu-cloud/src/edu_cloud/api/compat_router.py
/home/ops/projects/edu-cloud/src/edu_cloud/modules/marking/router.py
/home/ops/projects/edu-cloud/src/edu_cloud/modules/marking/importer.py
/home/ops/projects/edu-cloud/src/edu_cloud/config.py
/home/ops/projects/edu-cloud/src/edu_cloud/api/app.py
/home/ops/projects/edu-cloud/docker-compose.yml
/home/ops/projects/edu-cloud/src/edu_cloud/models/school_settings.py
/home/ops/projects/edu-cloud/src/edu_cloud/ai/engine/tools/card_layout.py
/home/ops/projects/edu-cloud/src/edu_cloud/ai/engine/tools/misc.py
```

## 附录 B：已执行验证摘要

```text
SSH ECS connectivity: passed
FastAPI process check: passed
Docker Redis/Postgres binding check: inspected
Alembic current: a1b2_chat_msgs, SQLiteImpl
Targeted pytest: 63 passed, 33 warnings
Frontend lint: passed
Ruff F/E9 scan: failed, ~250 findings
Objective upload mismatch PoC: reproduced
```

