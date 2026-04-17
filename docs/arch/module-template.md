# edu-cloud 模块分层规范

> 生效日期：2026-04-17
> 状态：规范文档（描述既有实践，固化为新模块开发约束）

## 1. 目的

edu-cloud 后端在 `src/edu_cloud/modules/` 下维护 20 个业务模块。历经 exam-ai 合并 + 多次功能迭代，模块内部结构呈现 3 种稳定形态。本文档将这 3 种形态**正式化为 3 种模块模板**，作为：

- 新增模块时的选型依据
- 评审现有模块结构偏差的对照标尺
- 跨模块一致性的约束边界

本文档不修改现有模块结构（那是 Phase 3-4 的工作），仅**固化命名、分层、文件组织的约定**。

## 2. 三种模板总览

| 模板 | 特征 | 适用场景 | 现有实例（20 模块覆盖） |
|------|------|---------|----------------------|
| **A · 简单 HTTP 型** | router + service + 可选 models + 可选 schemas，单一路由入口 | 一套 CRUD/查询 API，业务逻辑适中，无多路径分叉 | bank, calendar, homework, knowledge, menu, pipeline, profile, student（8 个） |
| **B · 重功能 HTTP 型** | 多个 `*_router.py` 子路由 或 多个 service 专门化 或 大量工具文件 | 功能域大，按子域拆分路由/服务；或有专门化工具（导出/解析/算法） | analytics, card, conduct, exam, grading, knowledge_tree, marking, scan, school, studio（10 个） |
| **C · 纯服务型** | 只有 service，**无 router.py** | 仅作为内部依赖被其他模块/Agent 工具调用；不直接暴露 HTTP | adaptive, paper（2 个） |

### 2.1 选型决策树

```
新模块是否需要直接暴露 HTTP 端点？
│
├─ 否 → 模板 C（纯服务型）
│       示例：adaptive（BKT 引擎，被 Agent 工具调用）
│              paper（包装 paper-skill 外部 API，被 studio 调用）
│
└─ 是 → 是否预估 > 15 个端点 或 涉及 >= 3 个独立子功能域？
         │
         ├─ 否 → 模板 A（简单 HTTP 型）
         │       示例：homework（/homework/tasks CRUD + submissions）
         │              menu（/menus 单一查询）
         │
         └─ 是 → 模板 B（重功能 HTTP 型）
                 示例：exam（联考 + 结果 + 工作台 + LLM 配置 4 个子域）
                        card（渲染 + 导出 + 解析 + 模板 4 个子域）
```

## 3. 模板详细规范

### 3.1 模板 A · 简单 HTTP 型

**文件清单（必须）**：
```
modules/<name>/
├── __init__.py
├── router.py          # FastAPI APIRouter，所有端点在此
├── service.py         # 业务逻辑（与 DB 交互的 async 函数）
└── models.py          # 可选：ORM 表定义（若本模块专用）
```

**可选扩展**：
- `schemas.py` — 若请求/响应结构复杂，独立 Pydantic 模型
- `MODULE.md` — 若模块有特殊约束或使用说明

**路由约定**：
- `router = APIRouter(prefix="/<kebab-name>", tags=["<Module Name>"])`
- 路径用 kebab-case（如 `/homework-tasks` 不是 `/homework_tasks`）
- 所有端点必须加 `dependencies=[Depends(require_permission(...))]` 或业务层鉴权

**Service 约定**：
- 所有 DB 操作函数 `async def`，接受 `db: AsyncSession` 作为首个参数
- 抛异常用 `modules/exam/exceptions.py`（待统一到 `core/exceptions.py`，本文档暂留现状）
- 不在 service 里做 HTTP 错误处理（那是 router 的责任）

**Models 约定**：
- 继承 `models/base.py` 的 `Base + IdMixin(UUID) + TenantMixin(school_id) + TimestampMixin(UTC)` 混入
- 单模块专用表放此处；跨模块共享表上浮到 `src/edu_cloud/models/`（详见 `orm-placement.md`）

**当前合规的范例**：`modules/homework/`（3 文件：router + service + models）

---

### 3.2 模板 B · 重功能 HTTP 型

**触发条件**（任一满足即升级为 B）：
- 预估端点数 ≥ 15
- 业务按子域自然分为 ≥ 3 个独立功能块
- 需要专门化工具类（导出器、解析器、算法引擎）
- 涉及多种角色视角的权限分支（如管理端 + 家长端）

**文件清单（典型）**：
```
modules/<name>/
├── __init__.py
├── router.py              # 主路由（公共端点）
├── <subdomain>_router.py  # 子域路由（一个子域一个文件）
├── service.py             # 核心服务（公共逻辑）
├── <subdomain>_service.py # 子域服务（可选）
├── models.py              # ORM 表
├── schemas.py             # 可选：Pydantic 模型（若多处复用）
├── <tool>.py              # 专门化工具（exporter/parser/renderer...）
└── MODULE.md              # 推荐：说明子域划分、跨文件约束
```

**子域拆分规则**：
- 子域命名反映**业务名词**，不是技术分层（对：`admin_router` / `parent_router` / `joint_exam_router`；错：`get_router` / `post_router`）
- 每个 `*_router.py` 有自己的 `APIRouter` 实例，在 `api/app.py` 统一挂载
- 子域 service 跟随子域 router 配对（`<subdomain>_router.py` 调 `<subdomain>_service.py`）

**当前合规范例**：
- `modules/exam/`（4 子路由 + 3 子服务 + 1 slot_selector 工具）
- `modules/school/`（5 子路由聚合学校配置的不同维度）
- `modules/conduct/`（admin + parent 双路由 + crypto/permissions/rules/export 工具）

**需重构候选**：
- `modules/card/`（20 文件平铺，应按子域进一步下沉到子目录，Phase 4 处理）

---

### 3.3 模板 C · 纯服务型

**文件清单（必须）**：
```
modules/<name>/
├── __init__.py
├── service.py         # 公共入口，对外暴露函数
└── <支持文件>.py       # 按需：models / 算法 / 工具
```

**不得出现的文件**：
- `router.py` — 若需对外 HTTP，升级为模板 A 或 B
- `*_router.py` — 同上

**使用约定**：
- 被其他模块的 service.py 导入（`from edu_cloud.modules.adaptive.service import diagnose`）
- 或被 Agent 工具注册（`src/edu_cloud/ai/tools/adaptive.py` 调用）
- 不直接由 `api/app.py` 挂载

**当前合规范例**：
- `modules/adaptive/`（BKT 引擎 + 路径规划 + 题目选择器，被 AI tools/adaptive.py 注册）
- `modules/paper/`（仅 service.py，包装外部 paper-skill API，被 studio/router.py 调用）

**MODULE.md 推荐项**：
- 谁是调用方（下游列表）
- 外部依赖（如 paper-skill 远程服务）
- 不变量（如"所有函数必须 idempotent"）

## 4. 20 模块现状对照表

| 模块 | 模板 | 符合规范? | 备注 |
|------|------|----------|------|
| adaptive | C | ✓ | BKT + 路径规划 + 选择器 |
| analytics | B | ✓ | report/segment/exporters 专门化 |
| bank | A | ✓ | 三件套 |
| calendar | A | ✓ | 三件套 + notification_service |
| card | B | △ 平铺过大 | Phase 4 候选：按子域下沉 rendering/ export/ parser/ template/ |
| conduct | B | ✓ | admin+parent 双路由完整 |
| exam | B | ✓ | 4 子路由 + 3 子服务 |
| grading | B | ✓ | assignment + quality 子路由 + MODULE.md |
| homework | A | ✓ | 三件套 |
| knowledge | A | ✓ | 三件套 + loader/store |
| knowledge_tree | B | ✓ | 多 service 专门化（detail/exam_items/stats/sync/quality） |
| marking | B | ✓ | router + exporter/importer/scorer 工具 |
| menu | A | ✓ | 三件套 |
| paper | C | ✓ | 仅 service.py（外部 API 包装） |
| pipeline | A | ✓ | router + service + MODULE.md |
| profile | A | ✓ | 三件套 |
| scan | B | ✓ | pipeline_router + objective/tpl + vision/ 子目录 |
| school | B | ✓ | 5 子路由（assignment/audit/capability/selection/settings） |
| student | A | ✓ | 三件套 |
| studio | B | ✓ | router + approval_service 独立审批流 |

**符合率**：19/20（card 需 Phase 4 子目录化）

## 5. 新增模块操作清单

### Step 1：确定模板类型
按 §2.1 决策树选 A/B/C。

### Step 2：创建目录结构
```bash
# 模板 A
mkdir -p src/edu_cloud/modules/<name>
touch src/edu_cloud/modules/<name>/{__init__,router,service}.py

# 模板 B：多建几个子路由 stub
# 模板 C：省略 router.py
```

### Step 3：挂载路由（A/B 类型）
在 `src/edu_cloud/api/app.py` 的 `create_app()` 函数里：
```python
from edu_cloud.modules.<name>.router import router as <name>_router
app.include_router(<name>_router, prefix="/api/v1")
```

### Step 4：注册模块开关（若可被学校级启停）
在 `src/edu_cloud/models/school_settings.py` 的 `MODULE_CODES` 加入模块 code，
如默认启用则加入 `DEFAULT_ENABLED`。

### Step 5：补测试骨架
```bash
mkdir -p tests/test_modules/test_<name>
# 至少一个 test_<name>_smoke.py 验证 router 挂载 + 基础 CRUD
```

### Step 6：更新 CLAUDE.md
- 项目结构章节：加入模块路径
- 实现状态表：Modules 行模块数 +1
- API 端点章节：若新增端点 ≥ 3 个，补小节

## 6. 命名约定速查

| 对象 | 规则 | 示例 |
|------|------|------|
| 模块目录 | snake_case，业务名词 | `knowledge_tree`, `homework` |
| 路径前缀 | kebab-case | `/knowledge-tree`, `/homework` |
| 文件名 | snake_case | `admin_router.py`, `pipeline_service.py` |
| 类名 | PascalCase | `ScoreSegmentConfig`, `GradingTask` |
| 函数名 | snake_case，动词开头 | `get_visible_class_ids`, `create_exam` |
| 枚举 | UPPER_SNAKE | `MODULE_CODES`, `QUESTION_TYPE_ESSAY` |
| Permission | UPPER_SNAKE，domain_action 合成 | `MANAGE_EXAMS`, `VIEW_GRADING` |

## 7. 反模式（禁止）

| 反模式 | 为什么 | 正确做法 |
|--------|-------|---------|
| 在模板 C 模块加 `router.py` | 违反纯服务型约束 | 升级为 A/B，同时更新文档分类 |
| 多个 `*_router.py` 都用同一个 `APIRouter` 实例 | 破坏子域边界 | 每个子路由独立 `APIRouter(prefix=..., tags=...)` |
| 在 `router.py` 里写 DB 业务逻辑 | 违反分层 | 下沉到 service.py |
| 同名类在 `modules/X/models.py` 和 `models/X.py` 同时定义 | 双源冲突 | 按 `orm-placement.md` 规则选一处 |
| 工具文件平铺（参考 card/ 现状） | 可读性差 | ≥ 8 个工具文件时按子域下沉到子目录 |

## 8. 修订历史

| 日期 | 变更 |
|------|------|
| 2026-04-17 | 初版（Phase 2 Task 1）— 基于现有 20 模块提炼三类模板 |
