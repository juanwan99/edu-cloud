# edu-cloud 模块治理纲领（Module Governance）

> 创建: 2026-04-13 08:19:48
> 级别: T3
> 状态: 设计中
> 作者: Claude (Opus 4.6) + 用户 brainstorming

> [2026-04-13 21:00 实现完成] Commits (edu-cloud): ced5ea7..27e7bf4 (Task 1-7 + Round 2 修复 + R2-NEW-01 修复)。Commits (~/.claude): 5c66b45..26ca703 (hook 实现 + CHECKS 接入 + R2-NEW-01 修复)。Gate 1 Plan Review R1-R4 FAIL→R4 PASS (14 findings 落入 plan)。Gate 2 Code Review R1 FAIL (4 MED findings) → R2 PASS (全 resolved-correct)。Round 2 新增 R2-NEW-01 resolved-correct + R2-NEW-02 deferred (2026-05-15)。36/36 governance tests。

## §0 背景与目标

edu-cloud 是 AI 驱动教育平台，已聚合 20+ 业务模块（paper/scan/pipeline/grading/marking/conduct/knowledge_tree/adaptive/…），跨 exam-ai、paper-seg、德育、家长端多个子域。当前状态：

- 各模块无统一文档契约（有的有 README，有的无），找不到"对外暴露什么"
- 模块边界模糊（grading/marking/pipeline 职责重叠风险）
- 无项目级接口/数据表登记，跨模块依赖不可追溯
- 无机械校验强制力，依赖人治

**目标**：建立项目级统一治理纲领，**边开发边治理、自愈式收敛**。核心约束：

1. **绝对禁止多版本并存 / 接口混乱**（L015 级铁律）
2. 新模块入口严、存量模块触碰时升级、未触碰静默
3. 机械校验为主，不依赖人工 triage（Opus 主导调研与判定）

**非目标**（YAGNI）：
- 不做一次性大迁移（会卡死当前开发）
- 不给 services/ 和 ai/tools/ 强加 MODULE.md（仅作为依赖登记的被引用方）
- 不做前端模块纲领（前端模块化程度与后端不同，等 P2 验证后再议）

## §1 总体架构（四层治理模型）

```
┌─ Layer 1: 基线（P0）─ 一次性盘点 ─────────────────────────┐
│  Opus 主导调研 → edu-cloud-module-baseline.md（债务清单） │
└───────────────────────────────────────────────────────────┘
┌─ Layer 2: 契约（P2）─ 持续维护 ───────────────────────────┐
│  每模块 modules/<X>/MODULE.md                             │
│  · frontmatter（机读）: name / owns / exposes / depends   │
│  · 正文（人读）: 职责 / 边界 / 使用方式 / 数据流 / 变更   │
└───────────────────────────────────────────────────────────┘
┌─ Layer 3: 视图（P1）─ 自动派生 ───────────────────────────┐
│  docs/governance/modules.yaml（聚合所有 frontmatter）     │
│  docs/governance/dependency-graph.md（依赖关系 Mermaid）  │
│  由 hook 从 MODULE.md 自动生成，禁止手写                  │
└───────────────────────────────────────────────────────────┘
┌─ Layer 4: 守卫（P3）─ 机械强制 ───────────────────────────┐
│  module_governance_guard.py（PreToolUse 于 git commit）   │
│  · 新建模块缺 MODULE.md → block                           │
│  · 触碰存量模块（修改 ≥50 行）缺 MODULE.md → ask          │
│  · 跨模块调用未在 depends 登记 → ask                      │
│  · MODULE.md 声明的表/路由与代码不一致 → block            │
└───────────────────────────────────────────────────────────┘
```

**自愈式约束**：
- Layer 1 产出的债务清单不阻断任何开发，只提供"已知问题目录"
- Layer 2 只对**新建模块**和**本次修改的模块**强制，其余存量静默
- Layer 4 hook 分三档：block / ask / 静默（按修改规模与证据强度）

**单一真源**：
- 模块身份 → MODULE.md frontmatter（唯一真源）
- 全局视图 → modules.yaml（派生，可重建，禁止手写）
- 已完成设计清单 → 保留在项目 CLAUDE.md「已完成设计」段（不重复）

## §2 MODULE.md 模板

**位置**：`src/edu_cloud/modules/<X>/MODULE.md`

**完整模板**：

```markdown
---
# ── 机读字段（hook 校验 + 聚合到 modules.yaml）──
name: grading
status: active              # active | deprecated | experimental
owner: backend              # 责任方标识
layer: business             # business | infrastructure | cross-cutting

owns_tables:                # 数据库表（跨模块唯一）
  - grading_tasks
  - grading_dispatch_status
owns_routes:                # API 路由前缀（跨模块唯一）
  - /api/grading
  - /api/grading/dispatch

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

**字段校验矩阵**：

| 字段 | 必填 | Hook 校验 |
|------|------|----------|
| name | ✅ | 与目录名一致 |
| owns_tables | ✅ | 跨模块唯一；与代码中 `__tablename__` 一致 |
| owns_routes | ✅ | 跨模块唯一；与 FastAPI router 实际挂载一致 |
| exposes.services | ✅ | 声明的符号在 `__init__.py` 可 import |
| depends_on | ✅ | 跨模块调用必须在此登记（核心约束） |
| status / owner / layer | ✅ | 枚举值校验 |
| design_docs | ⚠️ 建议 | 路径存在性校验 |
| 正文 5 段 | ⚠️ 建议 | 仅校验段落标题存在 |

**最小合规门槛**（对存量模块触碰时）：
- 仅要求 frontmatter 必填字段 + 一句话"职责"
- 其余段落允许渐进补充（避免"写文档写到崩溃"）

## §3 自动派生与机械校验

### §3.1 Layer 3 聚合脚本

**位置**：`scripts/governance/aggregate_modules.py`

**输入**：遍历 `src/edu_cloud/modules/*/MODULE.md` 的 frontmatter

**输出**：
- `docs/governance/modules.yaml` — 全量模块清单（单文件，机读）
- `docs/governance/dependency-graph.md` — Mermaid 依赖图（人读）
- `docs/governance/debt-report.md` — 缺 MODULE.md 的存量模块清单

**触发时机**：git commit 时由 hook 自动执行并 stage 产物（复用 doc_sync_guard 模式）。

### §3.2 Layer 4 — module_governance_guard.py

**PreToolUse** 于 `git commit`。六条硬约束：

| # | 检查 | 档位 | 触发条件 |
|---|------|------|---------|
| 1 | 新建 `modules/<X>/` 必须含 MODULE.md | block | `git diff --cached` 含新增子目录 |
| 2 | 触碰存量模块 ≥50 行修改且缺 MODULE.md | ask | 修改规模阈值 |
| 3 | owns_tables 跨模块重复 | block | 聚合后冲突 |
| 4 | owns_routes 跨模块重复 | block | 同上 |
| 5 | 跨模块 import 未在 depends_on 登记 | ask | AST 扫描对照 frontmatter |
| 6 | MODULE.md 声明的表/路由与代码不一致 | block | 与实际 `__tablename__` / router 对比 |

**档位语义**：
- **block**：硬阻断 commit，必须修复
- **ask**：软询问（沿用 tool_preference_ask 的 Ask 范式），用户可选 proceed/fix-now/defer
- **静默**：不报，日常不打扰

**复用基础设施**：
- hook 合并调度 → 参照 `commit_guards.py`
- Ask 范式 → 参照 `tool_preference_ask.py`
- AST 扫描 → Python `ast` 标准库

**KILL_SWITCH**：`EDU_GOVERNANCE_GUARD_DISABLED=1` 环境变量可临时禁用（hook bug 时紧急出路）。

### §3.3 Layer 1 — 调研方法论

P0 调研不是脚本，是 **Opus 主导的阅读工作**（方法论来源：feedback_research_over_rules.md）。

**调研 checklist**：

1. 读每个 `modules/<X>/__init__.py` + 主 service 文件 + router 文件
2. 读 `services/` 下 12 个文件，判断与 modules/ 下同名职责的重叠
3. 读 `ai/tools/` 下的工具，判断是否有"AI 版本的同一能力"
4. 读前端 `pages/` 主页面，判断是否有绕过后端 API 的野逻辑
5. 对每个可疑点，**读调用方 + git log** 做交叉验证（L013 反向防御：有证据才下结论）

**候选缩小**（机械信号，只为缩小阅读范围，不参与判定）：
- 目录/文件名语义相似聚类
- 同一概念的 ORM 类出现在多处
- FastAPI 路由前缀重叠
- 文件名含 `_old` / `_v1` / `_deprecated` / `_backup`

**产出**：`docs/governance/edu-cloud-module-baseline-2026-04-13.md`

**清单条目格式**：
```
### 冲突 #N: {一句话摘要}
- 位置 A: src/edu_cloud/modules/grading/dispatch.py:45
- 位置 B: src/edu_cloud/modules/marking/dispatch.py:12
- 证据: {原文摘录 + git log 关键行}
- 判定: 真冲突 / 职责互补 / 历史债务
- 建议处置: {去重/重命名/保留分工/标记 deprecated}
- 用户决定: [ ] approve / [ ] reject / [ ] defer
```

**用户动作**：只对每条建议拍板 approve/reject/defer，不做 triage。

## §4 实施路线

**四阶段，每阶段独立可交付，失败可回滚**

| 阶段 | 产出 | 耗时估算 | Gate |
|------|------|---------|------|
| **P0 基线调研** | baseline.md（债务清单 + 去重建议） | Opus 3-5h，分批推进 | 用户对每条建议拍板 |
| **P1 纲领骨架** | MODULE.md 模板 + 聚合脚本 + 初版依赖图 | 1-2h | 模板在试点模块跑通 |
| **P2 试点落地** | grading + pipeline 的 MODULE.md + modules.yaml 首版 | 1h | 两试点模块通过所有 hook 校验 |
| **P3 强制上线** | module_governance_guard.py + 集成到 commit_guards.py | 2h | 新建/触碰/冲突三类场景 hook 行为符合设计 |

**顺序约束**：
- P0 先于 P1（不能用想象的冲突定模板字段）
- P1 先于 P2（模板定了才填）
- P2 先于 P3（模板在真实模块验证过再开 hook）

**P3 渐进开启**：
- 先 block 检查 1、3、4（强硬铁律）
- ask 检查 2、5 观察 1 周，根据误报率调阈值
- 检查 6 最后开（需聚合脚本成熟）

**试点范围**（P2）：`grading` + `pipeline`
- 理由：grading dispatch 刚完成（2026-04-12），设计新鲜、边界清晰
- 且是用户当前开发正在触碰的模块，符合自愈式路线天然入口

**自愈式扩展**（P3 之后）：
- 不排期"给剩余 18 个模块补 MODULE.md"
- 任何 commit 触碰 modules/X/ 且 X 缺 MODULE.md → hook ask → 本次 commit 顺手补齐
- 模板字段不够用时，修改模板 → 聚合脚本重跑 → 存量模块下次触碰按新模板补

## §5 风险与权衡

**风险 1：模板字段不够用 / 过度设计**
- 缓解：P2 试点 2 模块暴露字段缺陷；最小合规门槛让存量模块可渐进补齐
- 回滚：P2 阶段仅涉及 2 个文件，修改模板成本低

**风险 2：hook 误报卡死开发**
- 缓解：档位分级（block 只给强硬铁律）；KILL_SWITCH env 变量
- 回滚：关闭 hook 不影响已写入的 MODULE.md

**风险 3：P0 调研工作量失控**
- 缓解：分批推进，每批 5 个模块产出增量清单供用户批阅
- 用户可离线，不需要同步等待

**风险 4：services/ 和 ai/tools/ 的横切能力与 modules/ 职责重叠未治理**
- 现状：本设计仅治理 modules/，services/ 仅作为被引用方登记
- 未来：P2 试点若发现 services 层冲突严重，启动独立设计

**权衡：为什么不把 services/ 也纳入？**
- services/ 是横切能力（跨模块共享逻辑），治理规则应与 modules/ 不同
- 强行套 MODULE.md 会削弱"模块 = 业务单元"的语义
- 当前决定：services/ 作为 depends_on.services 的被引用方登记即可，不强加纲领

## §6 交付物清单

| 路径 | 内容 | 创建阶段 |
|------|------|---------|
| `docs/plans/2026-04-13-module-governance-design.md` | 本设计文档 | 当前 |
| `docs/plans/archived/2026-04/2026-04-13-module-governance-plan.md` | 实施计划（writing-plans 产出） | 紧接 brainstorming |
| `docs/governance/edu-cloud-module-baseline-2026-04-13.md` | P0 基线报告 | P0 |
| `docs/governance/MODULE-template.md` | 模板（从 §2 提取） | P1 |
| `scripts/governance/aggregate_modules.py` | 聚合脚本 | P1 |
| `docs/governance/modules.yaml` | 派生全局视图 | P2 |
| `docs/governance/dependency-graph.md` | 派生依赖图 | P2 |
| `src/edu_cloud/modules/grading/MODULE.md` | 试点 | P2 |
| `src/edu_cloud/modules/pipeline/MODULE.md` | 试点 | P2 |
| `.claude/hooks/module_governance_guard.py` | 守卫 hook | P3 |

## §7 流程定级

**T 级别：T3**

判据：
- 跨文件（新建 hook + 模板 + 试点 2 模块 + 设计文档 + 聚合脚本）
- 有接口变更（引入 MODULE.md 契约作为模块间新协议）
- 需要设计决策（字段取舍 / 档位分级 / 试点范围）

流程：design → plan → handoff → codex-review (plan) Gate 1 → 执行 → codex-review (code) Gate 2 → design 标记 `[实现完成]`
