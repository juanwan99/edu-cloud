# exam-ai → edu-cloud 合并实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 exam-ai 全部功能合并进 edu-cloud，产出统一后端 + 统一前端。

**Architecture:** 特性模块化单体（15 modules），edu-cloud 骨架 + exam-ai 领域模型/服务/路由迁入。38 个模型，~107 端点，25 AI 工具，~680 测试。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, PostgreSQL, Redis/arq, Vue 3 + Naive UI, Playwright (card PDF)

**Design doc:** `docs/plans/2026-03-22-platform-merge-design.md`

**Migration source:** `C:/Users/Administrator/exam-ai/src/exam_ai/` (13,375 LOC, 97 files)

---

## File Structure (合并后目标)

```
src/edu_cloud/
├── core/                          # 共享基础（已有，改造）
│   ├── models/
│   │   ├── base.py                # 已有 Base + IdMixin + TimestampMixin
│   │   ├── user.py                # 已有 User（保留）
│   │   ├── user_role.py           # 已有 UserRole（保留）
│   │   ├── school.py              # 改造：RegisteredSchool → School, tablename → "schools"
│   │   └── llm_slot.py            # 迁入 exam-ai models/llm_slot.py + school_id FK
│   ├── permissions.py             # 已有（扩展 Permission 枚举 + 角色映射）
│   ├── events.py                  # 已有 EventBus
│   ├── deps.py                    # 改造：get_current_user 改用 User+UserRole
│   └── exceptions.py              # 合并两边异常类
│
├── modules/
│   ├── exam/
│   │   ├── models.py              # 迁入 Exam/Subject/Question + 保留 JointExam 系列
│   │   ├── service.py             # 迁入 exam_service.py
│   │   ├── joint_exam_service.py  # 已有（FK 改造）
│   │   ├── results_service.py     # 已有
│   │   ├── router.py              # 迁入 exam.py + question.py 路由
│   │   ├── joint_exam_router.py   # 已有
│   │   └── results_router.py      # 已有
│   │
│   ├── student/
│   │   ├── models.py              # 合并 Student + Class（吸收 ClassGroup）
│   │   ├── service.py             # 迁入 student_service.py
│   │   └── router.py              # 迁入 student.py 路由
│   │
│   ├── card/
│   │   ├── models.py              # 迁入 Template + CardSkeleton
│   │   ├── router.py              # 迁入 cards.py（1,124 LOC）+ template.py
│   │   ├── renderer.py            # 迁入（1,227 LOC）
│   │   ├── layout.py              # 迁入（572 LOC）
│   │   ├── subject_defaults.py    # 迁入（530 LOC）
│   │   ├── answer_standardizer.py # 迁入（349 LOC）
│   │   ├── defaults.py            # 迁入（294 LOC）
│   │   ├── tpl_parser.py          # 迁入（279 LOC）
│   │   ├── word_parser.py         # 迁入（269 LOC）
│   │   ├── template_library.py    # 迁入（215 LOC）
│   │   ├── barcode_gen.py         # 迁入（144 LOC）
│   │   ├── export.py              # 迁入（112 LOC）
│   │   ├── html_export.py         # 迁入（78 LOC）
│   │   └── confidence.py          # 迁入（26 LOC）
│   │
│   ├── scan/
│   │   ├── models.py              # 迁入 ScanTask + StudentAnswer
│   │   ├── service.py             # 迁入 storage.py
│   │   └── router.py              # 迁入 scan.py（422 LOC）
│   │
│   ├── grading/
│   │   ├── models.py              # 迁入 Rubric/GradingTask/AIGradingResult/TeacherReview
│   │   ├── llm_client.py          # 迁入（106 LOC）
│   │   ├── prompts.py             # 迁入（29 LOC）
│   │   └── router.py              # 迁入 grading.py（343 LOC）
│   │
│   ├── marking/
│   │   ├── models.py              # 迁入 MarkingAssignment + MarkingScore
│   │   ├── importer.py            # 迁入（149 LOC）
│   │   ├── scorer.py              # 迁入（131 LOC）
│   │   ├── exporter.py            # 迁入（95 LOC）
│   │   └── router.py              # 迁入 marking.py（367 LOC）
│   │
│   ├── analytics/
│   │   ├── service.py             # 迁入 analytics_service.py（358 LOC）
│   │   └── router.py              # 迁入 analytics.py
│   │
│   ├── bank/
│   │   ├── models.py              # 迁入 BankQuestion + StudentErrorBook
│   │   ├── service.py             # 迁入 bank_service.py
│   │   └── router.py              # 无独立路由（通过 AI Agent 访问）
│   │
│   ├── knowledge/
│   │   ├── models.py              # 迁入 KnowledgePoint + QuestionKnowledgePoint
│   │   ├── service.py             # 迁入 knowledge_service.py
│   │   ├── store.py               # 已有（内存 KnowledgeStore，保留）
│   │   ├── loader.py              # 已有（JSON 文件加载，保留）
│   │   └── router.py              # 迁入 knowledge.py 路由
│   │
│   ├── profile/
│   │   ├── models.py              # 迁入 StudentExamSnapshot/Mastery/ErrorPattern
│   │   └── service.py             # 迁入 profile_service.py
│   │
│   ├── pipeline/
│   │   └── service.py             # 迁入 data_pipeline.py（566 LOC）
│   │   └── router.py              # 迁入 pipeline.py 路由
│   │
│   ├── studio/                    # 已有（保留）
│   │   ├── models.py              # Document + DocumentVersion + ApprovalFlow + ApprovalStep
│   │   ├── service.py             # StudioService + ApprovalService
│   │   └── router.py              # studio.py
│   │
│   ├── calendar/                  # 已有（保留）
│   │   ├── models.py              # CalendarEvent + NotificationRule + Notification
│   │   ├── service.py             # CalendarService + NotificationService
│   │   └── router.py              # calendar.py
│   │
│   └── paper/                     # 已有（保留）
│       └── service.py             # PaperService
│
├── ai/                            # 合并 Agent + Tools
│   ├── agent.py                   # 合并：取 exam-ai loop.py 为主体
│   ├── registry.py                # 已有 ToolRegistry
│   ├── llm.py                     # 合并：取 exam-ai 版本（更完整）
│   ├── context.py                 # 合并：取 exam-ai 版本
│   ├── schemas.py                 # 合并
│   ├── anonymizer.py              # 迁入 exam-ai
│   ├── audit.py                   # 已有
│   └── tools/
│       ├── __init__.py            # 已有
│       ├── analytics.py           # 已有 L2_cross_school（保留）
│       ├── analytics_score.py     # 迁入 exam-ai L2_analytics
│       ├── analytics_compare.py   # 迁入 exam-ai
│       ├── actions.py             # 已有 L4_action（保留）
│       ├── knowledge.py           # 已有 L3_knowledge 内存源（保留）
│       ├── knowledge_db.py        # 迁入 exam-ai L3_knowledge_db
│       ├── exams.py               # 迁入 exam-ai L1_exam
│       ├── students.py            # 迁入 exam-ai L1_student
│       ├── bank.py                # 迁入 exam-ai L5_bank
│       └── profile.py             # 迁入 exam-ai L6_profile
│
├── workers/
│   ├── grading.py                 # 迁入 exam-ai workers/grading.py
│   └── __init__.py
│
├── data/                          # 迁入 exam-ai seed/import 脚本
│   ├── seed_demo.py
│   ├── seed_knowledge_math.py
│   └── import_real_exam.py
│
├── config.py                      # 合并两边 Settings
├── database.py                    # 已有
├── logging_config.py              # 已有
├── worker.py                      # 已有（扩展 functions 列表）
├── tasks.py                       # 已有
└── api/
    └── app.py                     # 改造：挂载全部模块路由
```

---

## Batch 划分

本计划分 5 个 Batch，每个 Batch 独立可测试，Batch 完成后走 codex-review (code)。

| Batch | 内容 | 预估 Task 数 |
|-------|------|-------------|
| 1 | Foundation — 模块骨架 + core 模型改造 + config 合并 | 5 |
| 2 | Domain Models & Services — 全部 12 模块的 models + services 迁入 | 6 |
| 3 | API Routes & App — 全部路由迁入 + app.py 改造 + middleware | 4 |
| 4 | AI Agent & Workers — Agent 合并 + 工具 + 后台任务 | 3 |
| 5 | Frontend & Cleanup — 前端合并 + 测试迁移 + Alembic + Docker | 4 |

---

## 迁移策略：Re-export Stubs 防止中间态断裂

Batch 2 会移动大量 models/ 和 services/ 文件到 modules/ 目录。如果直接删除旧文件，app.py 和 api/*.py 的 import 会立即断裂（它们在 Batch 3 才更新）。

**策略**：每次移动文件时，在旧位置留一个 re-export stub：

```python
# src/edu_cloud/models/joint_exam.py (stub after move)
# Re-export from new location for backwards compatibility
from edu_cloud.modules.exam.models import JointExam, JointExamParticipant, JointExamStudentResult  # noqa: F401
```

这些 stub 在 Task 22（清理）时统一删除。这样每个 Batch 完成后测试都能 PASS。

## ExamResult 删除的替代方案

设计文档说删除 edu-cloud 的 ExamResult，但以下代码重度依赖它：
- `ai/tools/analytics.py`（~15 处查询）
- `services/workspace_service.py`（dashboard 数据）

**决策**：**保留 ExamResult 模型**，但改为由 pipeline 模块（data_pipeline.py）从 exam-ai 的细粒度数据（StudentAnswer + AIGradingResult + MarkingScore）聚合填充。ExamResult 从"同步副本"变为"本地聚合视图"——数据来源变了，但模型和查询不变。这避免了重写 analytics 和 workspace 的大量代码。

ExamResult 移入 `modules/exam/models.py`，保留 exam_id + student_id + school_id + total_score + detail_scores 字段。

---

## Batch 1: Foundation (Task 1-5)

### Task 1: 创建模块目录结构

**Files:**
- Create: `src/edu_cloud/modules/__init__.py`
- Create: `src/edu_cloud/modules/{school,exam,student,card,scan,grading,marking,analytics,bank,knowledge,profile,pipeline,studio,calendar,paper}/__init__.py`
- Create: `src/edu_cloud/core/models/__init__.py`
- Create: `src/edu_cloud/workers/__init__.py`
- Create: `src/edu_cloud/data/__init__.py`

- [ ] **Step 1: 创建全部模块目录和 __init__.py**

```bash
cd C:/Users/Administrator/edu-cloud
for mod in school exam student card scan grading marking analytics bank knowledge profile pipeline studio calendar paper; do
  mkdir -p src/edu_cloud/modules/$mod
  touch src/edu_cloud/modules/$mod/__init__.py
done
mkdir -p src/edu_cloud/core/models
touch src/edu_cloud/core/models/__init__.py
mkdir -p src/edu_cloud/workers
touch src/edu_cloud/workers/__init__.py
mkdir -p src/edu_cloud/data
touch src/edu_cloud/data/__init__.py
touch src/edu_cloud/modules/__init__.py
```

- [ ] **Step 2: 验证目录结构**

```bash
find src/edu_cloud/modules -type f -name "*.py" | sort
```

Expected: 16 `__init__.py` files (15 modules + modules root)

- [ ] **Step 3: Commit**

```bash
git add src/edu_cloud/modules/ src/edu_cloud/core/models/ src/edu_cloud/workers/ src/edu_cloud/data/
git commit -m "chore: 创建合并所需的模块目录结构"
```

### Task 2: Core 模型改造 — School 重命名 + FK 级联

**Files:**
- Modify: `src/edu_cloud/models/school.py` — RegisteredSchool → School, tablename → "schools", 删除 sync 字段
- Modify: `src/edu_cloud/models/joint_exam.py` — FK "registered_schools.id" → "schools.id"
- Modify: `src/edu_cloud/models/student.py` — FK 更新
- Modify: `src/edu_cloud/models/class_group.py` — 暂时保留（Task 3 处理）
- Modify: `src/edu_cloud/models/document.py` — FK 更新
- Modify: `src/edu_cloud/models/calendar.py` — FK 更新
- Modify: `src/edu_cloud/models/notification.py` — FK 更新
- Modify: `src/edu_cloud/models/approval.py` — FK 更新
- Modify: `src/edu_cloud/models/ai_session.py` — FK 更新（如有）
- Modify: `src/edu_cloud/models/user_role.py` — FK 更新
- Modify: 所有引用 `RegisteredSchool` 的 service/api 文件
- Test: `tests/` — 全量回归

- [ ] **Step 1: 写迁移前的回归测试基线**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q 2>&1 | tail -5
```

记录当前测试数和全部 PASS 状态。

- [ ] **Step 2: 重命名 School 模型**

在 `models/school.py` 中：
- `class RegisteredSchool` → `class School`
- `__tablename__ = "registered_schools"` → `__tablename__ = "schools"`
- 删除字段：`api_key_hash`, `last_heartbeat`, `client_version`, `exam_ai_port`
- 保留字段：`name`, `code`, `address`, `contact`, `contact_phone`, `is_active`, `district`

- [ ] **Step 3: 全局替换 FK 引用**

在所有 models/ 文件中：
- `ForeignKey("registered_schools.id")` → `ForeignKey("schools.id")`
- `from edu_cloud.models.school import RegisteredSchool` → `from edu_cloud.models.school import School`

在所有 services/ 和 api/ 文件中：
- `RegisteredSchool` → `School`

```bash
cd C:/Users/Administrator/edu-cloud
grep -rn "RegisteredSchool\|registered_schools" src/edu_cloud/ --include="*.py"
```

逐个文件替换，确保零残留。

- [ ] **Step 4: 更新 conftest.py fixture**

测试 fixture 中引用 `RegisteredSchool` 的地方改为 `School`。

- [ ] **Step 5: 运行全量测试**

```bash
python -m pytest --tb=short -q
```

Expected: 全部 PASS（数量与 Step 1 相同）

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: RegisteredSchool → School, tablename → schools, 删除 sync 字段"
```

### Task 3: Core 模型改造 — PlatformUser 删除 + Auth 改造

**Files:**
- Delete: `src/edu_cloud/models/platform_user.py`
- Modify: `src/edu_cloud/api/auth.py` — login 改为认证 User + UserRole
- Modify: `src/edu_cloud/api/deps.py` — get_current_user 改为查 User + UserRole
- Modify: `src/edu_cloud/models/joint_exam.py` — created_by FK → "users.id"
- Modify: `src/edu_cloud/models/document.py` — created_by/approved_by FK → "users.id"
- Modify: `src/edu_cloud/models/approval.py` — approver_id FK → "users.id"
- Modify: `src/edu_cloud/api/app.py` — lifespan seed admin 改为创建 User + UserRole
- Modify: `tests/conftest.py` — admin fixture 改为 User + UserRole
- Test: 全量回归

- [ ] **Step 1: 写 auth 改造的测试**

**测试契约（Task 3 关键行为变更：PlatformUser → User+UserRole 认证）：**
- **入口**: `POST /api/v1/auth/login` body `{"username":"admin","password":"123456"}`
- **反例**: 用旧 PlatformUser 表的用户无法登录（错误实现：仍查 PlatformUser 表）
- **边界**: (1) 错误密码 → 401 (2) 不存在用户 → 401 (3) 多角色用户 JWT 包含 roles 列表 (4) switch-role 切换后 school_id 变化
- **回归**: 所有现有 API 端点的 `Depends(get_current_user)` 仍正常工作
- **命令**: `python -m pytest tests/test_api/test_auth_v2.py -v`

先更新 `tests/conftest.py`：admin fixture 改为创建 User + UserRole（platform_admin 角色），不再用 PlatformUser。

- [ ] **Step 2: 改造 auth login 端点**

`api/auth.py`：查询 `User` by username，验证密码，然后查 `UserRole` 获取角色列表，JWT payload 包含 `{"sub": user.id, "roles": [...], "active_role": primary_role, "school_id": ...}`。

- [ ] **Step 3: 改造 get_current_user 依赖**

`api/deps.py`：从 JWT 解码 user_id，查 User，查 UserRole 获取当前角色和权限。返回包含 `user, role, school_id, class_ids, subject_codes` 的上下文对象。

- [ ] **Step 4: 更新 FK 引用**

```bash
grep -rn "platform_users\|PlatformUser" src/edu_cloud/ --include="*.py"
```

- `ForeignKey("platform_users.id")` → `ForeignKey("users.id")`
- 删除 `models/platform_user.py`
- 更新 `models/__init__.py` 中的 import

- [ ] **Step 5: 更新 lifespan seed admin**

`api/app.py` lifespan：创建 User(username="admin", hashed_password=bcrypt("123456")) + UserRole(role="platform_admin", is_primary=True)。

- [ ] **Step 6: 运行全量测试**

```bash
python -m pytest --tb=short -q
```

修复任何因 auth 改造导致的测试失败。

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor: 删除 PlatformUser, auth 改为 User+UserRole 认证"
```

### Task 4: Config 合并

**Files:**
- Modify: `src/edu_cloud/config.py` — 加入 exam-ai 的配置项

- [ ] **Step 1: 合并 Settings**

在 `config.py` 的 Settings class 中加入：

```python
# Storage (scanned images from paper-seg)
STORAGE_ROOT: str = "./storage"
MAX_UPLOAD_SIZE_MB: int = 10

# LLM (exam-ai specific)
LLM_VISION_MODEL: str = ""
LLM_TIMEOUT: int = 60
LLM_MAX_RETRIES: int = 3

# AI Agent
AI_MAX_STEPS: int = 15
AI_SESSION_TTL: int = 7200
AI_RATE_LIMIT_PER_MINUTE: int = 10
AI_RATE_LIMIT_PER_DAY: int = 200
AI_MAX_CALLS_PER_SESSION: int = 20
```

- [ ] **Step 2: 运行测试确认无回归**

```bash
python -m pytest --tb=short -q
```

- [ ] **Step 3: Commit**

```bash
git add src/edu_cloud/config.py && git commit -m "feat: 合并 exam-ai 配置项到 Settings"
```

### Task 5: Core 异常类合并 + LLMSlot 模型

**Files:**
- Modify: `src/edu_cloud/services/exceptions.py` — 确保包含两边所有异常
- Create: `src/edu_cloud/core/models/llm_slot.py` — 迁入 LLMSlot
- Create: `src/edu_cloud/modules/exam/slot_selector.py` — 迁入 slot 选择逻辑（内部服务，非 HTTP 路由）

- [ ] **Step 1: 合并异常类**

确保 exceptions.py 包含：NotFoundError, PermissionDeniedError, ValidationError, ConflictError, StateError（edu-cloud 已有全部，exam-ai 的对应异常名称映射过来）。

- [ ] **Step 2: 迁入 LLMSlot 模型**

从 `exam-ai/src/exam_ai/models/llm_slot.py` 复制到 `src/edu_cloud/core/models/llm_slot.py`。
改造：`school_id` 加 `ForeignKey("schools.id")`。

- [ ] **Step 3: 迁入 llm_router.py**

从 `exam-ai/src/exam_ai/services/llm_router.py` 复制到 `src/edu_cloud/modules/exam/slot_selector.py`。
更新 import 路径。

- [ ] **Step 4: 写 LLMSlot 测试（含 slot 选择逻辑）**

**测试契约（LLMSlot + slot_selector）：**
- **入口**: `get_llm_config(db, slot=1, school_id="school-A")`
- **反例**: 学校 slot 存在时不应 fallback 到平台默认（错误实现：查询顺序反了）
- **边界**: (1) 无学校 slot + 有平台默认 → 返回平台默认 (2) 无学校 + 无平台 → fallback .env (3) slot disabled → 跳过
- **回归**: 无
- **命令**: `python -m pytest tests/test_models/test_llm_slot.py -v`

```python
# tests/test_models/test_llm_slot.py
async def test_school_slot_overrides_platform_default(db):
    """学校级 slot 优先于平台默认"""
    platform = LLMSlot(slot_number=1, api_url="http://platform", ...)
    school = LLMSlot(slot_number=1, school_id="school-A", api_url="http://school", ...)
    db.add_all([platform, school])
    await db.commit()
    url, _, _ = await get_llm_config(db, slot=1, school_id="school-A")
    assert url == "http://school"  # 不是 "http://platform"

async def test_fallback_to_platform_when_no_school_slot(db):
    """无学校 slot 时 fallback 到平台默认"""
    platform = LLMSlot(slot_number=1, api_url="http://platform", ...)
    db.add(platform)
    await db.commit()
    url, _, _ = await get_llm_config(db, slot=1, school_id="school-B")
    assert url == "http://platform"

async def test_disabled_slot_skipped(db):
    """disabled slot 不返回"""
    slot = LLMSlot(slot_number=1, is_enabled=False, ...)
    db.add(slot)
    await db.commit()
    url, _, _ = await get_llm_config(db, slot=1)
    # should fallback to .env, not return disabled slot
```

- [ ] **Step 5: 运行测试**

```bash
python -m pytest tests/test_models/test_llm_slot.py -v
python -m pytest --tb=short -q  # 全量回归
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: 迁入 LLMSlot 模型 + llm_router slot 选择逻辑"
```

---

## Batch 2: Domain Models & Services (Task 6-11)

### Task 6: Exam 模块 — 模型 + 服务

**Files:**
- Create: `src/edu_cloud/modules/exam/models.py` — Exam, Subject, Question（从 exam-ai 迁入）
- Create: `src/edu_cloud/modules/exam/service.py` — ExamService（从 exam-ai 迁入）
- Create: `src/edu_cloud/modules/exam/schemas.py` — Pydantic schemas
- Move: `src/edu_cloud/services/joint_exam_service.py` → `src/edu_cloud/modules/exam/joint_exam_service.py`
- Move: `src/edu_cloud/services/results_service.py` → `src/edu_cloud/modules/exam/results_service.py`
- Move: `src/edu_cloud/models/joint_exam.py` → 内容合入 `modules/exam/models.py`
- Modify: `src/edu_cloud/models/exam.py` → re-export stub（指向新位置）
- Test: 写 Exam/Subject/Question 基础 CRUD 测试

- [ ] **Step 1: 迁入 Exam/Subject/Question 模型**

从 exam-ai `models/exam.py` 复制 **Exam, Subject, Question** 类定义（注意：同文件还有 Template 和 CardSkeleton，这两个属于 card 模块，在 Task 8 迁入，此处不提取）。添加到 `modules/exam/models.py`。

改造：
- Exam: `school_id` 加 `ForeignKey("schools.id")`
- 将 JointExam/JointExamParticipant/JointExamStudentResult 从 `models/joint_exam.py` 合入同文件
- **保留 ExamResult**（从 edu-cloud `models/exam.py` 移入，改为由 pipeline 聚合填充），保持 ai/tools/analytics.py 和 workspace_service.py 不断裂
- 将 edu-cloud 的 `models/exam.py` 改为 re-export stub
- 将 `models/joint_exam.py` 改为 re-export stub

- [ ] **Step 2: 迁入 ExamService**

从 exam-ai `services/exam_service.py`（130 LOC）复制到 `modules/exam/service.py`。
更新所有 import 路径：`from exam_ai.models` → `from edu_cloud.modules.exam.models`。
所有查询方法加 `school_id` 参数。

- [ ] **Step 3: 移动已有 services + 留 re-export stubs**

`services/joint_exam_service.py` → `modules/exam/joint_exam_service.py`（旧位置留 re-export stub）
`services/results_service.py` → `modules/exam/results_service.py`（旧位置留 re-export stub）

- [ ] **Step 3.5: 更新 app.py lifespan 的模型 import**

将 app.py 中的 `import edu_cloud.models.exam`、`import edu_cloud.models.joint_exam` 改为 `import edu_cloud.modules.exam.models`（或通过 stub 兼容）。确保 Base.metadata.create_all() 覆盖新模型。

- [ ] **Step 4: 写基础测试**

```bash
# tests/test_modules/test_exam/test_models.py
# 测试 Exam, Subject, Question CRUD + school_id 隔离
```

- [ ] **Step 5: 运行测试**

```bash
python -m pytest tests/test_modules/test_exam/ -v
python -m pytest --tb=short -q  # 全量（修复 import 断裂）
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(exam): 迁入 Exam/Subject/Question 模型 + ExamService"
```

### Task 7: Student 模块

**Files:**
- Create: `src/edu_cloud/modules/student/models.py` — 合并 Student + Class
- Create: `src/edu_cloud/modules/student/service.py` — 迁入 student_service.py
- Modify: `src/edu_cloud/models/student.py` → re-export stub
- Modify: `src/edu_cloud/models/class_group.py` → re-export stub（ClassGroup = Class alias）
- Modify: 所有引用 ClassGroup 的文件 → Class（可通过 stub 兼容先不改）

- [ ] **Step 1: 创建合并后的 Student + Class 模型**

Student：取 exam-ai 字段（student_number/gender/enrollment_year/status）+ edu-cloud 的 grade + school_id FK。
Class：取 exam-ai 的 Class（name/grade/head_teacher_id）+ ClassGroup 的 grade_number。tablename = "classes"。

- [ ] **Step 2: 全局替换 ClassGroup → Class**

```bash
grep -rn "ClassGroup\|class_group\|class_groups" src/edu_cloud/ tests/ --include="*.py"
```

逐个替换。

- [ ] **Step 3: 迁入 student_service.py + 测试**

- [ ] **Step 4: 运行全量测试 + Commit**

```bash
python -m pytest --tb=short -q
git add -A && git commit -m "feat(student): 合并 Student+Class 模型, 替换 ClassGroup"
```

### Task 8: Card + Scan 模块

**Files:**
- Create: `src/edu_cloud/modules/card/models.py` — Template + CardSkeleton
- Copy: exam-ai `services/card/` 全部 13 文件 → `src/edu_cloud/modules/card/`
- Create: `src/edu_cloud/modules/scan/models.py` — ScanTask + StudentAnswer
- Create: `src/edu_cloud/modules/scan/service.py` — StorageService（迁入 shared/storage.py）

Card 模块是最大的迁入（4,095 LOC / 13 文件），但文件内部自包含，主要工作是更新 import 路径。

- [ ] **Step 1: 迁入 Card 模型**

Template + CardSkeleton 从 **exam-ai `models/exam.py`** 提取（与 Exam/Subject/Question 同文件，Task 6 已处理其余部分）。放入 `modules/card/models.py`。CardSkeleton 加 school_id FK。

- [ ] **Step 2: 批量复制 card services（13 文件）**

```bash
cp exam-ai/src/exam_ai/services/card/*.py edu-cloud/src/edu_cloud/modules/card/
```

逐文件更新 import：`from exam_ai.` → `from edu_cloud.modules.`

- [ ] **Step 3: 迁入 Scan 模型 + StorageService**

ScanTask + StudentAnswer → `modules/scan/models.py`。
exam-ai `shared/storage.py` → `modules/scan/service.py`。

- [ ] **Step 4: 写 Card 模型 + Scan 模型基础测试**

- [ ] **Step 5: 运行测试 + Commit**

```bash
python -m pytest --tb=short -q
git add -A && git commit -m "feat(card,scan): 迁入答题卡编辑器(13文件4095LOC) + 扫描模块"
```

### Task 9: Grading + Marking 模块

**Files:**
- Create: `src/edu_cloud/modules/grading/models.py` — Rubric/GradingTask/AIGradingResult/TeacherReview
- Create: `src/edu_cloud/modules/grading/llm_client.py` — 迁入
- Create: `src/edu_cloud/modules/grading/prompts.py` — 迁入
- Create: `src/edu_cloud/modules/marking/models.py` — MarkingAssignment/MarkingScore
- Copy: exam-ai `services/marking/` → `src/edu_cloud/modules/marking/`

- [ ] **Step 1: 迁入 Grading 全部模型和服务**

- [ ] **Step 2: 迁入 Marking 全部模型和服务（4 文件 375 LOC）**

- [ ] **Step 3: 写基础测试 + 全量回归**

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(grading,marking): 迁入 AI 阅卷 + 手动批改模块"
```

### Task 10: Analytics + Bank + Profile + Pipeline 模块

**Files:**
- Create: `src/edu_cloud/modules/analytics/service.py` — 迁入 analytics_service.py（358 LOC）
- Create: `src/edu_cloud/modules/bank/models.py` — BankQuestion + StudentErrorBook
- Create: `src/edu_cloud/modules/bank/service.py` — 迁入 bank_service.py
- Create: `src/edu_cloud/modules/profile/models.py` — 3 个画像模型
- Create: `src/edu_cloud/modules/profile/service.py` — 迁入 profile_service.py
- Create: `src/edu_cloud/modules/pipeline/service.py` — 迁入 data_pipeline.py（566 LOC）

- [ ] **Step 1: 迁入 Analytics service**

- [ ] **Step 2: 迁入 Bank 模型 + service**

- [ ] **Step 3: 迁入 Profile 模型 + service**

- [ ] **Step 4: 迁入 Pipeline service（566 LOC）**

更新 import：pipeline 跨 bank/profile/knowledge/exam 聚合数据，需要正确引用各模块模型。

- [ ] **Step 5: 写基础测试 + 全量回归**

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(analytics,bank,profile,pipeline): 迁入分析/题库/画像/管线模块"
```

### Task 11a: Knowledge 模块合并

**Files:**
- Create: `src/edu_cloud/modules/knowledge/models.py` — 迁入 KnowledgePoint + QuestionKnowledgePoint
- Create: `src/edu_cloud/modules/knowledge/service.py` — 迁入 knowledge_service.py
- Move: `src/edu_cloud/knowledge/store.py` → `src/edu_cloud/modules/knowledge/store.py`（留 re-export stub）
- Move: `src/edu_cloud/knowledge/loader.py` → `src/edu_cloud/modules/knowledge/loader.py`（留 re-export stub）

- [ ] **Step 1: 迁入 Knowledge DB 模型 + service**
- [ ] **Step 2: 移动 KnowledgeStore + loader 到 modules/knowledge/**
- [ ] **Step 3: 运行全量测试 + Commit**

```bash
python -m pytest --tb=short -q
git add -A && git commit -m "feat(knowledge): 迁入 DB 模型 + 移动 KnowledgeStore 到模块"
```

### Task 11b: Studio + Calendar 重组

**Files:**
- Move: `src/edu_cloud/services/studio_service.py` → `src/edu_cloud/modules/studio/service.py`（留 stub）
- Move: `src/edu_cloud/services/approval_service.py` → `src/edu_cloud/modules/studio/approval_service.py`（留 stub）
- Move: `src/edu_cloud/models/document.py` → 合入 `modules/studio/models.py`（留 stub）
- Move: `src/edu_cloud/models/approval.py` → 合入 `modules/studio/models.py`（留 stub）
- Move: `src/edu_cloud/services/calendar_service.py` → `src/edu_cloud/modules/calendar/service.py`（留 stub）
- Move: `src/edu_cloud/services/notification_service.py` → `src/edu_cloud/modules/calendar/notification_service.py`（留 stub）
- Move: `src/edu_cloud/models/calendar.py` + `notification.py` → 合入 `modules/calendar/models.py`（留 stub）

- [ ] **Step 1: 重组 Studio 模块** — models + services 移入，留 stubs
- [ ] **Step 2: 重组 Calendar 模块** — models + services 移入，留 stubs
- [ ] **Step 3: 运行全量测试 + Commit**

```bash
python -m pytest --tb=short -q
git add -A && git commit -m "refactor: 重组 studio/calendar 到模块结构"
```

### Task 11c: Paper/Workspace/School/AI Session 重组 + Sync 删除

**Files:**
- Move: `src/edu_cloud/services/paper_service.py` → `src/edu_cloud/modules/paper/service.py`（留 stub）
- Move: `src/edu_cloud/services/workspace_service.py` → `src/edu_cloud/modules/exam/workspace_service.py`（留 stub）
- Move: `src/edu_cloud/services/school_service.py` → `src/edu_cloud/modules/school/service.py`（留 stub）
- Move: `src/edu_cloud/models/ai_session.py` → `src/edu_cloud/ai/models.py`（留 stub）
- Move: `src/edu_cloud/services/exceptions.py` → `src/edu_cloud/core/exceptions.py`（留 stub）
- Delete: `src/edu_cloud/api/sync_students.py`（sync 废弃，依赖旧模型）

- [ ] **Step 1: 移动 Paper + Workspace + School service**（留 re-export stubs）
- [ ] **Step 2: 移动 AI Session model + exceptions**（留 re-export stubs）
- [ ] **Step 3: 删除 sync_students.py**
- [ ] **Step 4: 运行全量测试（大量 import 变更，预计需要修复 ImportError）**

```bash
python -m pytest --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: 重组 paper/workspace/school/ai-session, 删除 sync_students"
```

**→ Batch 2 完成后：codex-review (code)**

---

## Batch 3: API Routes & App (Task 12-15)

### Task 12: 迁入 exam-ai 路由 — Exam/Student/Card/Scan

**Files:**
- Create: `src/edu_cloud/modules/exam/router.py` — 迁入 exam.py + question.py 路由
- Create: `src/edu_cloud/modules/student/router.py` — 迁入 student.py 路由
- Create: `src/edu_cloud/modules/card/router.py` — 迁入 cards.py（1,124 LOC）+ template.py
- Create: `src/edu_cloud/modules/scan/router.py` — 迁入 scan.py（422 LOC）

- [ ] **Step 1: 迁入每个路由文件**

每个路由文件的改造：
1. 更新 import（models, services, deps）
2. 添加 `prefix="/api/v1/{module}"` 和 `tags`
3. 从 JWT 中提取 school_id 注入到 service 调用

- [ ] **Step 2: 挂载到 app.py**

在 `api/app.py` 的 `create_app()` 中 include 新路由。

- [ ] **Step 3: 写 API 测试（含多租户隔离验证）**

**测试契约（Task 12 关键行为变更：school_id 注入 + 多租户隔离）：**
- **入口**: `POST /api/v1/exams`（JWT 认证，school_id 从 token 提取）
- **反例**: school_A 的用户不能查看 school_B 的考试（错误实现：缺少 school_id 过滤时返回全部数据）
- **边界**: (1) 无 JWT → 401 (2) school_id 不匹配 → 空列表或 403 (3) 已删除路由 `/api/v1/sync/*` → 404
- **回归**: 原有 edu-cloud 端点（schools/joint-exams/studio/calendar）仍可正常访问
- **命令**: `python -m pytest tests/test_modules/test_exam/test_api.py -v`

每个迁入模块至少覆盖：成功路径 + 跨 school 越权 + 资源不存在。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(api): 迁入 exam/student/card/scan 路由"
```

### Task 13: 迁入 exam-ai 路由 — Grading/Marking/Analytics/Knowledge/Pipeline/LLMConfig

**Files:**
- Create: `src/edu_cloud/modules/grading/router.py` — 迁入 grading.py
- Create: `src/edu_cloud/modules/marking/router.py` — 迁入 marking.py
- Create: `src/edu_cloud/modules/analytics/router.py` — 迁入 analytics.py
- Create: `src/edu_cloud/modules/knowledge/router.py` — 迁入 knowledge.py
- Create: `src/edu_cloud/modules/pipeline/router.py` — 迁入 pipeline.py
- Create: `src/edu_cloud/modules/exam/llm_config_router.py` — 迁入 llm_config.py

- [ ] **Step 1-4: 同 Task 12 模式**

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(api): 迁入 grading/marking/analytics/knowledge/pipeline/llm-config 路由"
```

### Task 14: 重组已有路由到模块

**Files:**
- Move: `src/edu_cloud/api/joint_exams.py` → `src/edu_cloud/modules/exam/joint_exam_router.py`
- Move: `src/edu_cloud/api/results.py` → `src/edu_cloud/modules/exam/results_router.py`
- Move: `src/edu_cloud/api/schools.py` → `src/edu_cloud/modules/school/router.py`
- Move: `src/edu_cloud/api/studio.py` → `src/edu_cloud/modules/studio/router.py`
- Move: `src/edu_cloud/api/calendar.py` → `src/edu_cloud/modules/calendar/router.py`
- Move: `src/edu_cloud/api/workspace.py` → `src/edu_cloud/modules/exam/workspace_router.py`
- Keep: `src/edu_cloud/api/app.py`（入口）
- Keep: `src/edu_cloud/api/auth.py`（认证）
- Delete: `src/edu_cloud/api/sync.py`
- Delete: `src/edu_cloud/api/sync_students.py`

- [ ] **Step 1: 移动路由文件到模块**

- [ ] **Step 2: 删除 sync 路由**

- [ ] **Step 3: 更新 app.py 路由挂载**

`app.py` 只保留 auth router + health/version 端点，其余路由从 modules 导入。

- [ ] **Step 4: 运行全量测试**

```bash
python -m pytest --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(api): 重组路由到模块, 删除 sync 端点"
```

### Task 15: App factory 改造 + Middleware 统一

**Files:**
- Modify: `src/edu_cloud/api/app.py` — 更新 lifespan（加载所有模型）、挂载所有模块路由

- [ ] **Step 1: 更新 lifespan**

确保 `Base.metadata.create_all()` 覆盖全部 38 个模型。在 lifespan 中 import 所有模块的 models.py。

- [ ] **Step 2: 更新路由挂载**

确保所有模块路由都在 app.py 中注册。

- [ ] **Step 3: 全量测试**

```bash
python -m pytest --tb=short -q
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(app): 统一 app factory, 挂载全部模块路由"
```

**→ Batch 3 完成后：codex-review (code)**

---

## Batch 4: AI Agent & Workers (Task 16-18)

### Task 16: AI Agent 合并

**Files:**
- Modify: `src/edu_cloud/ai/agent.py` — 取 exam-ai loop.py 为主体（更完整的 ReAct 循环）
- Modify: `src/edu_cloud/ai/llm.py` — 取 exam-ai 版本（208 LOC vs 80 LOC）
- Modify: `src/edu_cloud/ai/context.py` — 取 exam-ai 版本（119 LOC vs 35 LOC）
- Modify: `src/edu_cloud/ai/schemas.py` — 合并两边 schemas
- Create: `src/edu_cloud/ai/anonymizer.py` — 迁入 exam-ai（65 LOC）
- Modify: `src/edu_cloud/api/ai.py` — 合并：取 exam-ai 版本（含 session CRUD，228 LOC vs 65 LOC）

- [ ] **Step 1: 替换 agent core**

用 exam-ai 的 `agent/loop.py` 内容替换 `ai/agent.py`，更新 import。
用 exam-ai 的 `agent/llm.py` 替换 `ai/llm.py`。
用 exam-ai 的 `agent/context.py` 替换 `ai/context.py`。
合并 schemas。
迁入 anonymizer.py。

- [ ] **Step 2: 合并 AI 路由**

用 exam-ai 的 `api/ai.py`（228 LOC，含 sessions 端点）替换 edu-cloud 的 `api/ai.py`（65 LOC）。更新 import。

- [ ] **Step 3: 写 Agent 基础测试**

```bash
python -m pytest tests/test_ai/ -v
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(ai): 合并 Agent 核心(loop/llm/context/anonymizer/schemas)"
```

### Task 17: AI 工具合并

**Files:**
- Keep: `src/edu_cloud/ai/tools/analytics.py` — L2_cross_school
- Keep: `src/edu_cloud/ai/tools/actions.py` — L4_action
- Keep: `src/edu_cloud/ai/tools/knowledge.py` — L3_knowledge（内存源）
- Create: `src/edu_cloud/ai/tools/analytics_score.py` — 迁入 L2_analytics
- Create: `src/edu_cloud/ai/tools/analytics_compare.py` — 迁入
- Create: `src/edu_cloud/ai/tools/exams.py` — 迁入 L1_exam
- Create: `src/edu_cloud/ai/tools/students.py` — 迁入 L1_student
- Create: `src/edu_cloud/ai/tools/bank.py` — 迁入 L5_bank
- Create: `src/edu_cloud/ai/tools/profile.py` — 迁入 L6_profile
- Create: `src/edu_cloud/ai/tools/knowledge_db.py` — 迁入 L3_knowledge_db
- Modify: `src/edu_cloud/ai/tools/__init__.py` — 注册全部 25 工具
- Modify: `src/edu_cloud/ai/agent.py` — 更新 ROLE_TOOL_CATEGORIES（注意：此常量定义在 agent.py 而非 permissions.py）

- [ ] **Step 1: 迁入 7 个工具文件**

逐个复制，更新 import。

- [ ] **Step 2: 更新工具注册**

`tools/__init__.py` 注册全部 25 工具。

- [ ] **Step 3: 更新 RBAC 映射**

`ai/agent.py` 中 `ROLE_TOOL_CATEGORIES` 更新为 9 类别，按设计文档 §5.2 映射。注意：此常量定义在 agent.py（不是 permissions.py），permissions.py 只有 `ROLE_PERMISSIONS`。

- [ ] **Step 4: 写工具注册测试**

验证每个角色可访问的工具数量正确。

- [ ] **Step 5: 运行测试 + Commit**

```bash
python -m pytest tests/test_ai/ -v
python -m pytest --tb=short -q
git add -A && git commit -m "feat(ai): 合并 25 工具 + 9 类别 RBAC 映射"
```

### Task 18: Workers 合并

**Files:**
- Create: `src/edu_cloud/workers/grading.py` — 迁入 exam-ai workers/grading.py（211 LOC）
- Modify: `src/edu_cloud/worker.py` — 注册 process_grading_task + run_post_exam_pipeline

- [ ] **Step 1: 迁入 grading worker**

复制 exam-ai `workers/grading.py` → `src/edu_cloud/workers/grading.py`。更新 import。

- [ ] **Step 2: 更新 worker.py**

```python
functions = [
    process_grading_task,
    run_auto_draft,
    run_post_exam_pipeline,
]
```

- [ ] **Step 3: 写 worker 测试（mock Redis）**

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(workers): 迁入 grading worker, 注册 pipeline 任务"
```

**→ Batch 4 完成后：codex-review (code)**

---

## Batch 5: Frontend & Cleanup (Task 19-22)

### Task 19: 前端合并

**Files:**
- Modify: `frontend/package.json` — 升级到 exam-ai 的较新版本
- Copy: exam-ai 前端页面组件 → `frontend/src/pages/`
- Copy: exam-ai 前端 API 模块 → `frontend/src/api/`
- Copy: exam-ai 前端 stores → `frontend/src/stores/`
- Copy: exam-ai card-editor 模块 → `frontend/src/card-editor/`
- Copy: exam-ai CardEditor.vue → `frontend/src/components/`
- Modify: `frontend/src/router/index.js` — 加入 13 个路由
- Modify: `frontend/src/stores/auth.js` — 保持 edu-cloud 多角色版本
- Modify: `frontend/src/stores/aiChat.js` — 取 exam-ai 版本（更完整 SSE）
- Modify: `frontend/src/api/client.js` — 统一 baseURL = `/api/v1`
- Modify: `frontend/vite.config.js` — proxy 保持 9000

- [ ] **Step 1: 升级 package.json 依赖版本**

- [ ] **Step 2: 复制页面组件（14 个 .vue 文件）**

- [ ] **Step 3: 复制 API 模块（11 个 .js 文件）**

统一 baseURL：所有 API 调用使用 `/api/v1` 前缀。

- [ ] **Step 4: 复制 card-editor 模块（5 文件 1,985 LOC）+ CardEditor.vue（28K）**

- [ ] **Step 5: 合并 stores**

- auth.js: 保持 edu-cloud 版本（多角色 + switchRole）
- aiChat.js: 取 exam-ai 版本（SSE + tool_call 展示）
- 新增 exam.js store（管理考试列表/详情）

- [ ] **Step 6: 更新 router**

加入 exam-ai 的 13 个路由。DashboardLayout 作为多数页面的 layout。

- [ ] **Step 7: 验证前端构建**

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npm install && npm run build
```

- [ ] **Step 8: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend/ && git commit -m "feat(frontend): 合并 exam-ai 前端(14页面+28K卡片编辑器)"
```

### Task 20: 测试迁移

**Files:**
- Copy: exam-ai `tests/` → `edu-cloud/tests/`（按模块重组）
- Modify: 所有测试文件的 import 路径
- Delete: `test_cloud_sync.py` 相关测试

- [ ] **Step 1: 复制 exam-ai 测试文件**

按模块重组：
- `test_api/test_exam.py` → `tests/test_modules/test_exam/test_api.py`
- `test_api/test_cards.py` → `tests/test_modules/test_card/test_api.py`
- 以此类推

- [ ] **Step 2: 批量替换 import 路径**

```bash
# 所有迁入的测试文件
find tests/ -name "*.py" -exec sed -i 's/from exam_ai\./from edu_cloud.modules./g' {} +
find tests/ -name "*.py" -exec sed -i 's/import exam_ai\./import edu_cloud.modules./g' {} +
```

注意：这只是初始替换，具体路径需要逐文件调整。

- [ ] **Step 3: 更新 conftest.py**

确保 fixture 创建所有 38 个模型的表。添加 school fixture。

- [ ] **Step 4: 删除 sync 相关测试**

- `test_api/test_cloud_sync.py`
- `test_services/test_cloud_sync.py`
- `test_api/test_sync_v2.py`
- `test_api/test_sync_students.py`

- [ ] **Step 5: 逐步修复测试**

```bash
python -m pytest --tb=short -q 2>&1 | head -50
```

逐个修复 ImportError 和 fixture 问题，直到全部 PASS。

- [ ] **Step 6: 验证测试数量**

```bash
python -m pytest --co -q | tail -3
```

Expected: ~680 tests collected

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "test: 迁移 exam-ai 测试 (~446→~420 after sync 删除)"
```

### Task 21: Alembic 迁移 + Docker 更新

**Files:**
- Create: `alembic/versions/xxxx_merge_exam_ai.py` — 新 initial migration
- Modify: `Dockerfile` — 加入 Playwright + 中文字体
- Modify: `docker-compose.yml` — 加 storage/uploads volumes

- [ ] **Step 1: 重建 Alembic migration**

**前提：当前无生产数据**，因此不需要 rename/backfill 策略。方案：
1. 删除旧 migration `alembic/versions/bdd523549077_initial_all_tables.py`
2. 更新 `alembic/env.py` 的 model imports 指向新模块路径
3. 生成新 initial migration 覆盖全部 38 个模型

```bash
cd C:/Users/Administrator/edu-cloud
rm alembic/versions/bdd523549077_initial_all_tables.py
# 更新 env.py imports 后：
python -m alembic revision --autogenerate -m "initial_merged_schema"
```

**注意**：如果未来有生产数据，需要写显式 rename migration（registered_schools→schools, platform_users→users, class_groups→classes）而非 drop+create。当前场景无此需求。

- [ ] **Step 2: 更新 Dockerfile**

加入 Playwright Chromium（用于答题卡 PDF 生成）和中文字体。

- [ ] **Step 3: 更新 docker-compose.yml**

加 volumes: `./storage:/app/storage`, `./uploads:/app/uploads`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: Alembic 合并迁移 + Docker Playwright 支持"
```

### Task 22: 清理 + 文档更新

**Files:**
- Delete: `src/edu_cloud/models/platform_user.py`（如 Task 3 未删）
- Delete: `src/edu_cloud/models/class_group.py`（如 Task 7 未删）
- Delete: `src/edu_cloud/models/exam.py`（edu-cloud 旧版）
- Delete: `src/edu_cloud/api/sync.py`
- Delete: `src/edu_cloud/api/sync_students.py`
- Delete: `src/edu_cloud/services/` 目录下已移入模块的旧文件
- Delete: `src/edu_cloud/knowledge/` 旧目录（已移入 modules/knowledge/）
- Modify: `CLAUDE.md` — 更新项目结构和端点列表
- Modify: `src/edu_cloud/models/__init__.py` — 更新 re-exports

- [ ] **Step 0: 迁入 data/ seed 脚本**

从 exam-ai 复制：
- `data/seed_demo.py`（256 LOC）
- `data/seed_knowledge_math.py`（113 LOC）
- `data/import_real_exam.py`（310 LOC）
更新 import 路径。

- [ ] **Step 1: 删除所有已废弃文件（包括 re-export stubs）**

```bash
grep -rn "from edu_cloud.services\." src/edu_cloud/ --include="*.py" | grep -v modules/
grep -rn "from edu_cloud.models\." src/edu_cloud/ --include="*.py" | grep -v core/models
```

确保无残留引用后删除旧文件。

- [ ] **Step 2: 更新 CLAUDE.md**

反映合并后的项目结构、端点列表、模块组织。

- [ ] **Step 3: 最终全量测试**

```bash
python -m pytest --tb=short -q
```

Expected: ~680 tests, all PASS

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: 清理废弃文件, 更新 CLAUDE.md 反映合并后结构"
```

**→ Batch 5 完成后：codex-review (code) + codex-review (integration)**

---

## 审查计划

| 审查点 | 类型 | 触发时机 |
|--------|------|---------|
| Batch 1 完成 | codex-review (code) | Task 5 后 |
| Batch 2 完成 | codex-review (code) | Task 11 后 |
| Batch 3 完成 | codex-review (code) | Task 15 后 |
| Batch 4 完成 | codex-review (code) | Task 18 后 |
| Batch 5 完成 | codex-review (code) + codex-review (integration) | Task 22 后 |

## 风险矩阵（per-batch 高风险区域）

| Batch | 高风险区域 | 风险类型 | 额外验证要求 |
|-------|-----------|---------|-------------|
| 1 | **Auth 改造**（Task 3）| 安全 | 多角色 JWT 测试 + 旧 PlatformUser 不可登录验证 |
| 1 | **School 表重命名 FK 级联**（Task 2）| 数据完整性 | 全量测试 + grep 零残留 |
| 2 | **多租户隔离**（所有 service school_id）| 安全 | 跨 school 越权测试 |
| 3 | **路由挂载**（~107 端点）| 集成 | 每个端点至少 1 个可达测试 |
| 4 | **AI Agent RBAC**（Task 17）| 安全 | 每角色工具可见性验证 |
| 5 | **28K 前端编辑器迁入**（Task 19）| 功能 | npm run build 无报错 |
| 5 | **Alembic migration**（Task 21）| 数据 | 无生产数据，create_all 足够 |

## 风险检查点

每个 Batch 完成后，运行全量测试确认：
1. `python -m pytest --tb=short -q` — 全部 PASS
2. `python -m pytest --co -q | tail -3` — 测试数量符合预期
3. `grep -rn "from exam_ai\." src/edu_cloud/` — 零残留旧 import
4. `grep -rn "RegisteredSchool\|PlatformUser\|ClassGroup" src/edu_cloud/` — 零残留旧类名
