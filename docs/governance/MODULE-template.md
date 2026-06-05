# MODULE.md 模板（人读版）

> 本文件是 edu-cloud 模块治理纲领（`docs/plans/2026-04-13-module-governance-design.md`）§2 的人读参考。
> 每个 `src/edu_cloud/modules/<X>/` 下均应有一份 `MODULE.md`，frontmatter 为机读真源。

---

## 完整模板

```markdown
---
# ── 机读字段（aggregate_modules.py 读取 + module_governance_guard.py 校验）──
name: grading
status: active              # active | deprecated | experimental
owner: backend              # 责任方标识（可填团队/个人/"backend"）
layer: business             # business | infrastructure | cross-cutting

owns_tables:                # 数据库表（跨模块唯一）
  - grading_tasks
  - grading_dispatch_status
owns_routes:                # API 路由前缀（跨模块唯一，含完整挂载路径）
  - /api/v1/grading
  - /api/v1/grading/dispatch

exposes:
  services:                 # 可被 import 的 service 函数/类
    - start_pipeline
    - get_dispatch_status
  events:                   # 发出的领域事件
    - grading.dispatch.completed

depends_on:
  modules: [pipeline, paper, scan]
  services: [paper_service, results_service]
  ai_tools: []

created: 2026-04-12
last_reviewed: 2026-04-13
design_docs:
  - docs/plans/2026-04-12-grading-dispatch-design.md
---

# grading 模块

## 职责
（一句话，禁止"和 XX 相关的功能"这种空话）

## 边界
- **做什么**：{能力 1}、{能力 2}
- **不做什么**：{明确划给其他模块的能力}

## 使用方式
{其他模块/前端如何调用本模块，最小示例}

## 数据流
{输入 → 本模块 → 输出}

## 变更历史
{仅记录影响对外契约的变更，不记录内部重构}
```

---

## 字段说明

### 机读字段（frontmatter，aggregate_modules.py + guard 必读）

| 字段 | 必填 | 取值 | 校验规则 |
|------|------|------|---------|
| `name` | ✅ | 字符串 | 与目录名一致 |
| `status` | ✅ | `active` / `deprecated` / `experimental` | 枚举 |
| `owner` | ✅ | 字符串 | 责任方标识（团队/个人）|
| `layer` | ✅ | `business` / `infrastructure` / `cross-cutting` | 枚举 |
| `owns_tables` | ✅ | 字符串列表 | 跨模块唯一；与代码中 `__tablename__` 一致 |
| `owns_routes` | ✅ | 字符串列表 | 跨模块唯一；与 FastAPI `APIRouter(prefix=...)` 一致（若 prefix 为裸前缀如 `/api/v1`，则展开为完整挂载路径如 `/api/v1/classes`）|
| `exposes.services` | ✅ | 字符串列表 | 声明的符号需在 `__init__.py` 或本模块公开 import 处可达 |
| `exposes.events` | ⚠️ 建议 | 字符串列表（如 `grading.dispatch.completed`）| 无 hook 强制 |
| `depends_on.modules` | ✅ | 字符串列表 | 跨模块调用必须登记（核心约束 — Layer 4 检查 5）|
| `depends_on.services` | ✅ | 字符串列表 | 仅列 `from edu_cloud.services.X import ...` 中的 X |
| `depends_on.ai_tools` | ✅ | 字符串列表 | 本模块自创的 AI 工具名（一般为空）|
| `created` | ⚠️ 建议 | `YYYY-MM-DD` | 模块首次创建时间 |
| `last_reviewed` | ⚠️ 建议 | `YYYY-MM-DD` | 最近一次评审时间 |
| `design_docs` | ⚠️ 建议 | 字符串列表（路径）| 路径存在性由人工保证 |

### 正文字段（5 段）

| 段标题 | 必填 | 要求 |
|--------|------|------|
| `## 职责` | ✅ | 一句话。禁止"和 XX 相关的功能"这种空话 |
| `## 边界` | ⚠️ 建议 | 至少填"做什么"和"不做什么"各一条 |
| `## 使用方式` | ⚠️ 建议 | 最小示例，展示如何从其他模块/前端调用 |
| `## 数据流` | ⚠️ 建议 | 输入 → 本模块 → 输出 |
| `## 变更历史` | ⚠️ 建议 | 仅对外契约变更；内部重构不记 |

---

## 填写指引

### 最小合规门槛（存量模块被触碰时）

1. frontmatter 必填字段全填
2. 正文「职责」段至少一句话
3. 其余段落可渐进补充（避免"写文档写到崩溃"）

### 字段填写规范

- `owns_tables`: 只列 `__tablename__` 明确定义在本模块的表（其他模块拥有的表通过 `depends_on.modules` 隐式依赖）
- `owns_routes`: 只列 FastAPI `APIRouter(prefix=...)` 实际挂载的 prefix；若路由 prefix 为裸前缀（如 `/api/v1`），展开为该 router 实际挂载的完整路径列表
- `depends_on.modules`: 只列 `from edu_cloud.modules.X import ...` 中的 X
- `depends_on.services`: 只列 `from edu_cloud.services.X import ...` 中的 X
- `exposes.services`: 只列通过 `__init__.py` 或模块公开 import 点暴露出去的符号；内部辅助函数不列

### 禁止

- 在 `owns_*` 里列其他模块拥有的资源（跨模块重复会被 hook 拒绝 — Layer 4 检查 3/4）
- 在正文「职责」段写"和 XX 相关的功能"空话
- 预设"模块 A 应当做 X" — 必须以代码实情为准（设计 §3.3 L013 反向防御）

### 关于同名资源

若本模块与其他模块有同名 service class / function（如 `publish_service`），在 `exposes.services` 中使用完整路径 `edu_cloud.modules.X.publish_service.ClassName` 以避免 AI tool / 文档摘录的歧义。

---

## 示例（参考 P2 试点）

- `src/edu_cloud/modules/grading/MODULE.md`（Task 4 产出）
- `src/edu_cloud/modules/pipeline/MODULE.md`（Task 5 产出）

---

## 聚合与守卫

- **聚合脚本**: `scripts/governance/aggregate_modules.py` 读取所有 MODULE.md frontmatter → `docs/governance/modules.yaml` + `dependency-graph.md` + `debt-report.md`
- **守卫 hook**: `~/.claude/hooks/module_governance_guard.py` 在 git commit 时强制：
  - 新建模块必须含 MODULE.md（block）
  - owns_tables / owns_routes 跨模块重复（block）
  - 触碰存量模块 ≥50 行修改缺 MODULE.md（block）
  - 派生产物（modules.yaml 等）过期（block）
- **KILL_SWITCH**: `EDU_GOVERNANCE_GUARD_DISABLED=1`
