# edu-cloud ORM 模型归属规范

> 生效日期：2026-04-17
> 状态：规范文档 + 现状审计清单

## 1. 目的

edu-cloud 的 SQLAlchemy ORM 模型当前散落在 **5 种位置**，缺少成文约定，历史上已有一轮 `Task 22` backward-compat stub 迁移（遗留 re-export 文件）。本文档：

1. **固化归属规则**："跨模块共享→上浮；单模块专用→下沉"
2. **全量审计现状** —— 哪些合规、哪些偏差
3. **偏差处置建议** —— 哪些要 Phase 3 搬迁、哪些容忍共存

## 2. 归属规则（Q2 决策 = C 规则化）

### 2.1 上浮 vs 下沉判定

| 条件 | 归属 | 典型 |
|------|------|------|
| 被 **≥ 2 个模块** 以 FK 或直接 import 方式依赖 | 上浮到 `src/edu_cloud/models/` | User, School, AuditLog, ScoreSegmentConfig |
| 仅被 **1 个模块** 的 service/router 使用 | 下沉到 `modules/<name>/models.py` | HomeworkTask, BankQuestion, Rubric |
| **AI Agent 基础设施**（跨 Agent 共享） | 上浮到 `src/edu_cloud/models/` | AgentProfile, AgentFinding, WorkflowRun |
| **平台配置**（学校/权限/角色级） | 上浮到 `src/edu_cloud/models/` | SchoolSetting, Capability, TeacherAssignment |

### 2.2 命名约定

- **平台层文件**：按业务名词命名（`school.py`, `capability.py`, `notification.py`）
- **模块层文件**：统一叫 `models.py`，放在 `modules/<name>/` 下
- **特殊命名**：分析类专用 ORM 可用 `analysis_models.py`（仅 `modules/analytics/` 用这种）—— **Phase 3 标准化**，统一为 `models.py`

### 2.3 禁止的位置

- ❌ `src/edu_cloud/core/models/` —— 已有 1 处偏差（`llm_slot.py`），Phase 3 上浮到 `src/edu_cloud/models/llm_slot.py`
- ❌ `src/edu_cloud/ai/models.py` —— 已有 2 个表（AiSession/AiToolCall），Phase 3 上浮到 `src/edu_cloud/models/ai_session.py`（已有同名文件需合并）
- ❌ 同一张表在两处定义 —— 必有一处是 re-export stub

## 3. 现状审计（全量 ORM 盘点）

### 3.1 平台层 `src/edu_cloud/models/` 27 个文件

**权威定义（符合规范）**：
| 文件 | 表/类 | 符合 | 说明 |
|------|------|------|------|
| base.py | Base, IdMixin, TenantMixin, TimestampMixin | ✓ | 混入基础 |
| user.py | User | ✓ | 核心身份 |
| user_role.py | UserRole | ✓ | 多角色（被所有鉴权引用） |
| school.py | School | ✓ | 多校核心 |
| guardian.py | GuardianStudentLink | ✓ | 家长-学生绑定 |
| scope_version.py | ScopeVersion | ✓ | 权限版本 |
| capability.py | Capability | ✓ | 角色能力矩阵 |
| audit_log.py | AuditLog | ✓ | 跨模块审计 |
| school_settings.py | SchoolSetting, SchoolModule | ✓ | 学校 KV + 模块开关 |
| subject_selection.py | SubjectSelection | ✓ | 选考配置 |
| teacher_assignment.py | TeacherAssignment | ✓ | 排课 |
| score_segment.py | ScoreSegmentConfig | ✓ | 分数段（跨 analytics + exam） |
| notification.py | Notification | ✓ | 通知（跨 calendar + studio） |
| document.py | Document, DocumentVersion | ✓ | Studio 文档（跨多模块报告） |
| approval.py | ApprovalFlow, ApprovalStep | ✓ | 审批流（跨 studio + conduct） |
| calendar.py | CalendarEvent, NotificationRule | ✓ | 校历（被 notification/homework 引用） |
| agent_profile.py | AgentProfile, AgentRun | ✓ | AI Agent 身份 |
| agent_finding.py | AgentFinding, AgentTask | ✓ | Agent 巡检产出 |
| agent_memory.py | AgentMemory | ✓ | Agent 记忆 |
| agent_snapshot.py | ExamAnalysisSnapshot, ClassExamReport | ✓ | 考试快照（跨 analytics + exam） |
| ai_session.py | AiSession | ✓ | AI 会话 |
| memory.py | EntityMemory, ProjectState | ✓ | 跨会话持久化 |
| workflow.py | WorkflowRun, WorkflowStep | ✓ | 工作流 |

**Re-export stubs（Task 22 遗留兼容层）**：
| 文件 | 实际定义处 | 处置 |
|------|-----------|------|
| student.py | modules/student/models.py（Student, Class） | ⚠️ **容忍保留** —— 有大量 `from edu_cloud.models.student import ...` 调用方，改名成本高 |
| exam.py | modules/exam/models.py（Exam, ExamResult, Subject, Question） | ⚠️ 同 |
| joint_exam.py | modules/exam/models.py（JointExam, JointExamParticipant, JointExamStudentResult） | ⚠️ 同 |
| class_group.py | modules/student/models.py（Class as ClassGroup） | ⚠️ 同 |

**处置原则**：Task 22 stub 全部保留，但**不允许新增 stub**。新代码直接 import `from edu_cloud.modules.X.models`。

### 3.2 模块层 `src/edu_cloud/modules/*/models.py` 16 个

| 模块 | 定义的表 | 是否跨模块被引用 | 归属判定 |
|------|----------|----------------|---------|
| adaptive | AnswerLog, StudentDaMastery, DaBktParams, DaKnowledgePointMap, QuestionDaOverride, AdaptiveCard, DaCatalogSnapshot | 仅 AI tools | ✓ 下沉合规 |
| bank | BankQuestion, StudentErrorBook | 仅 bank | ✓ |
| card | Template, CardSkeleton | 被 scan/pipeline 引用 Template FK | ⚠️ **边缘 case**（见 §4） |
| conduct | StudentProfile, ConductClassConfig, ConductRule*, ConductRecord, ConductGroup*, ConductSemester | 仅 conduct | ✓ |
| exam | Exam, Subject, Question, ExamResult, JointExam, JointExamParticipant, JointExamStudentResult | **被 grading/scan/analytics/marking/bank/profile FK** | ⚠️ **应上浮**（见 §4） |
| grading | Rubric, GradingTask, GradingResult, GradingAssignment, GradingQualityCheck | 仅 grading | ✓ |
| homework | HomeworkTask, HomeworkSubmission | 仅 homework | ✓ |
| knowledge | KnowledgePoint, QuestionKnowledgePoint | 被 adaptive/knowledge_tree 引用 | ⚠️ 边缘 case |
| knowledge_tree | ConceptGraphNode, ConceptBigConceptMap, ConceptGraphEdge, EditSyncFailure, ConceptStats | 被 adaptive（DaKnowledgePointMap FK→ConceptGraphNode） | ⚠️ 边缘 case |
| marking | (仅本模块) | 仅 marking | ✓ |
| menu | MenuConfig | 仅 menu | ✓ |
| profile | StudentExamSnapshot, StudentKnowledgeMastery, StudentErrorPattern | 仅 profile | ✓ |
| scan | ScanTask, StudentAnswer | 被 grading FK | ⚠️ 边缘 case |
| student | Student, Class | **核心实体，被全平台 FK** | ⚠️ **应上浮**（同 exam） |
| studio | (仅本模块) | 仅 studio | ✓ |

### 3.3 偏差位置（违反 §2.3）

| 位置 | 表 | 处置建议 |
|------|-----|---------|
| `src/edu_cloud/core/models/llm_slot.py` | LLMSlot | Phase 3 搬到 `models/llm_slot.py`，删除 `core/models/` 目录 |
| `src/edu_cloud/ai/models.py` | AiSession, AiToolCall | Phase 3 合并到 `models/ai_session.py`（后者已存 AiSession，需确认是否重复定义） |
| `src/edu_cloud/modules/analytics/analysis_models.py` | ClassAnalysis, StudentAnalysis, StudentKnpMastery | Phase 3 改名为 `modules/analytics/models.py`（统一命名） |

## 4. 边缘 case 讨论

### 4.1 Exam/Student 核心实体是否该上浮？

**现状**：`modules/exam/models.py` 定义 7 个表 + `modules/student/models.py` 定义 2 个表（Student, Class），这些被**全平台 FK 引用**。

**严格按 §2.1 规则**：应上浮到 `models/exam.py` + `models/student.py`（目前这两位置是 re-export stub）。

**现实约束**：
- 真实迁移要改 7+2=9 个类定义位置
- Alembic 迁移需要写 rename 模式（或 reflect → rewrite）
- 现有 200+ 处 import 路径（跨 tests/src）需批量更新
- **收益**：结构更清晰；**成本**：4-8 小时工作 + 迁移风险

**决策**：**容忍现状**，理由：
- Task 22 已建立 `models/student.py` / `models/exam.py` / `models/joint_exam.py` 作为 re-export 入口
- 外部代码可以用 `from edu_cloud.models.exam import Exam`（看起来像上浮），也可以用 `from edu_cloud.modules.exam.models import Exam`（实际定义处）
- 只要 **统一约定"外部代码使用 `models/` 入口"**，就可以让事实上的分散变成可管理的表面一致

**Phase 3 补救**：
- 在 `models/` 下给 **grading/scan/bank/profile/marking/analytics/conduct/homework** 也建 re-export stub
- CLAUDE.md 补一条"外部代码 import ORM 用 `edu_cloud.models.*`，不用 `edu_cloud.modules.*.models`"
- 写 lint 规则或 pre-commit hook 校验

### 4.2 Card.Template 被 Scan 引用

Scan 的 StudentAnswer 通过 `template_id` 关联 Card.Template。这是 **工具链的顺序依赖**（card→scan），不是业务实体共享。**归属判定为 card/**（单模块拥有，scan 通过 FK 消费）。

### 4.3 KnowledgeTree.ConceptGraphNode 被 Adaptive 引用

Adaptive.DaKnowledgePointMap 通过 `concept_node_id` FK 关联 knowledge_tree。这是 **知识图谱映射**（knowledge_tree 是权威，adaptive 消费）。**归属判定为 knowledge_tree/**。

## 5. Import 路径约定

### 5.1 推荐（外部代码）

```python
# ✓ 平台级入口（含 re-export 兼容）
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.models.student import Student, Class
from edu_cloud.models.user import User

# ✓ 模块内代码直接 import 本模块
# modules/exam/service.py:
from edu_cloud.modules.exam.models import Exam  # 本模块内允许
```

### 5.2 避免（新代码）

```python
# ✗ 新代码不应直接 import 其他模块的 models
# modules/grading/service.py:
from edu_cloud.modules.exam.models import Exam  # 外部模块应走平台层入口
# 正确写法：
from edu_cloud.models.exam import Exam
```

### 5.3 严格禁止

```python
# ✗ 同一个 class 从两个 import 路径引入
from edu_cloud.models.exam import Exam
from edu_cloud.modules.exam.models import Exam  # 双重引入
```

## 6. 新增 ORM 模型操作清单

### Step 1：判断归属
按 §2.1 表判断 —— 跨模块 FK or AI Agent or 平台配置 → 平台层；否则模块层。

### Step 2：文件位置
- 平台层：`src/edu_cloud/models/<noun>.py`（按业务名词）
- 模块层：`src/edu_cloud/modules/<name>/models.py`（固定文件名）

### Step 3：类定义
```python
from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin


class MyEntity(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "my_entities"  # 复数，snake_case
    # ... 字段
```

### Step 4：Alembic 迁移
```bash
alembic revision --autogenerate -m "add my_entity table"
```
检查生成的 migration：
- Upgrade / downgrade 都要写
- SQLite + PostgreSQL 双方言兼容（特别是 UniqueConstraint / alter_column / drop_constraint 用 `batch_alter_table` 包装）

### Step 5：测试 smoke
```python
# tests/test_alembic_migration.py 会覆盖基础
# 额外写 tests/test_modules/test_<name>/test_models.py 验证 ORM 约束
```

### Step 6：更新 CLAUDE.md
- "数据模型概要" 表：加入表名 + 字段 + 说明
- "实现状态"：Models 行表计数 +N

## 7. 反模式

| 反模式 | 为什么 | 正确做法 |
|--------|-------|---------|
| 模块专用表上浮到 `models/` | 污染平台层命名空间 | 下沉到 `modules/<name>/models.py` |
| 跨模块共享表下沉到某模块 | 隐式依赖，其他模块要绕路 import | 上浮到 `models/` |
| 同一张表两处定义（非 re-export） | 可能冲突，Alembic 会 autogenerate 重复 DROP/CREATE | 选一处定义，另一处 re-export |
| 在 `core/` / `ai/` 目录定义新 ORM | 违反 §2.3 | 只允许 `models/` 和 `modules/*/models.py` |
| 模块内 ORM 文件起非 `models.py` 的名字 | 不一致（analytics/analysis_models.py 是偏差） | 统一 `models.py` |

## 8. Phase 3 搬迁清单（不在本文档执行）

| 搬迁项 | 当前位置 | 目标位置 | 风险 |
|--------|---------|---------|------|
| LLMSlot | core/models/llm_slot.py | models/llm_slot.py | 低（单类迁移） |
| AiSession+AiToolCall | ai/models.py | models/ai_session.py（合并） | 中（可能与现有 AiSession 定义冲突，需确认） |
| ClassAnalysis+StudentAnalysis+StudentKnpMastery | modules/analytics/analysis_models.py | modules/analytics/models.py | 低（同目录重命名） |
| 建立所有模块的 models/ re-export 入口 | N/A | models/grading.py 等新建 | 低（纯新增） |
| 补 CLAUDE.md import 约定 | N/A | CLAUDE.md | 无 |

## 9. 修订历史

| 日期 | 变更 |
|------|------|
| 2026-04-17 | 初版（Phase 2 Task 2）— 规则化 + 全量审计 + Phase 3 搬迁清单 |
