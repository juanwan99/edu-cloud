---
type: handoff
created: 2026-03-30 08:52:37
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-business-logic-backfill-design.md
---

# edu-cloud 项目总交接文档（总规划师视角）

> **角色**: 项目总规划师
> **日期**: 2026-03-30
> **项目**: edu-cloud — 多校多角色教育管理云平台
> **指标**: 238 commits / 897 后端 tests / 68 前端 tests / 18 页面 / 31 AI 工具

---

## 一、项目愿景

edu-cloud 承担教育管理**全功能平台**角色（包含日常操作），exam-ai 退化为数据采集节点。平台分两级：
- **学校级**（当前重点）：考试/阅卷/作业/教学/学情/报告
- **教育局/集团级**（后期）：跨校对比/联考/区域监控

**核心差异化**：AI Agent 是系统的主要交互范式，不是附加功能。每个角色通过 Agent 对话完成日常办公。

**业务逻辑来源**：haofenshu.com（好分数，真实商业教育平台）已被完整逆向（`C:\Users\Administrator\haofenshu-clone`，45 页面 / 69KB 业务逻辑文档），作为业务逻辑参考库反哺到 edu-cloud。

---

## 二、架构全貌

```
┌─────────────────────────────────────────────────────────────────┐
│                    edu-cloud (port 9000)                         │
│  FastAPI + PostgreSQL + Redis(arq) + Vue 3 + Naive UI           │
├─────────────┬────────────────────────┬──────────────────────────┤
│  API Layer  │    Business Modules    │      AI Agent Layer      │
│  ─────────  │    ────────────────    │      ──────────────      │
│  FastAPI    │  15 modules:           │  ReAct Agent (自研)      │
│  JWT Auth   │  exam/student/card/    │  31 tools, 9 RBAC 类别  │
│  RBAC+ABAC  │  scan/grading/marking/ │  双 LLM 协议            │
│  Module MW  │  analytics/bank/       │  SSE 流式前端            │
│             │  profile/pipeline/     │  匿名化 + 审计           │
│             │  knowledge/studio/     │                          │
│             │  calendar/school/paper  │                          │
├─────────────┴────────────────────────┴──────────────────────────┤
│                        Data Layer                                │
│  39+ 表 / Alembic 迁移 / 知识库内存索引 / 种子数据              │
└─────────────────────────────────────────────────────────────────┘
         ↕ REST API                    ↕ REST API
    exam-ai × N 学校              paper-skill (论文)
```

**技术栈**：
- 后端：FastAPI + SQLAlchemy 2.0 (async) + asyncpg + Alembic + arq + Redis
- 前端：Vue 3.5 + Vite 7 + Naive UI 2.44 + Pinia 3 + ECharts 6
- AI：自研 ReAct Agent + OpenAI/Anthropic 双协议 + 31 tools
- 测试：pytest (async) + Vitest + happy-dom

---

## 三、已完成工作（按时间线）

### 原始平台建设（03-16 ~ 03-24）

| Phase | 日期 | 内容 | Gate |
|-------|------|------|------|
| P0 骨架 | 03-21 | Auth + Dashboard + 核心模型 + RBAC(8角色10权限) | GPT PASS |
| P1 AI Brain | 03-22 | ReAct Agent + 31 tools + SSE chat + 匿名化 + 审计 | GPT PASS |
| P2 Studio | 03-22 | 文档 CRUD + 状态流转 + 审批流 | GPT PASS |
| P3 Notification | 03-22 | 校历事件 + 通知规则 + 调度(stub) | GPT PASS |
| P4 Knowledge | 03-22 | 课标树 + 教材概念 + 搜索 + L3 查询工具 | GPT PASS |
| Platform Merge | 03-22~23 | exam-ai 迁入（考试/学生/答题卡/扫描/阅卷/手动批改/分析） | GPT PASS (5 batch) |
| Frontend Redesign | 03-23~24 | 角色感知壳层 + 8 角色 sidebar + 权限守卫 | GPT PASS (4 batch) |

### 好分数反哺 Phase 1（03-29 ~ 03-30）

| Sub-phase | 日期 | 内容 | Gate | Tests |
|-----------|------|------|------|-------|
| **设计** | 03-29 | 业务逻辑反哺 + Agent 深度嵌入设计（Claude×GPT 双模型讨论） | — | — |
| **1a 模块管理** | 03-29 | school_settings KV + school_modules 开关 + 中间件硬拦截 + sidebar moduleCode + 管理页 | Plan R6 PASS + Code R2 PASS | +29 |
| **1b 基础信息** | 03-29 | TeacherAssignment 排课 + SubjectSelection 选考 + 3 前端页面 | Plan PASS + Code R3 PASS | +22 |
| **1c 权限引擎** | 03-30 | Capability model/service/API + AuditLog + @audited decorator + ScopeFilter | Plan PASS, **执行进行中** | +12 (进行中) |

---

## 四、当前状态（2026-03-30 快照）

### 分支状态

| 分支 | 状态 | 说明 |
|------|------|------|
| `master` | Phase 1b 完成 | 含 P0-P4 + Platform Merge + Frontend Redesign + Phase 1a + 1b |
| `feat/phase1c-permission-engine` | **活跃** | Phase 1c 执行中，7 commits ahead of master |

### 测试状态

| 维度 | 数量 | 状态 |
|------|------|------|
| 后端 tests collected | 897 | 896 pass, **1 fail** (alembic 迁移表对比——Phase 1c 表已有 model 无 migration) |
| 前端 tests | 68 | 全部 pass |
| 前端 test files | 6 | router / auth-store / config / AppSidebar / aiChat / cardEditor |

### Phase 1c 执行进度

Phase 1c 有 8 个 Task，当前代码显示 Task 1-7 的代码已部分落地（model + service + router + ScopeFilter + @audited），但 state.json 显示全部 pending（可能是执行器未更新 state）。

**实际代码状态**（从 git log 判断）：

| Task | 内容 | 代码状态 |
|------|------|---------|
| 1 | Capability Model | ✅ committed (6773fd0) |
| 2 | Capability Service | ✅ committed (86dae0c) |
| 3 | Capability API | ✅ committed (23758ab) |
| 4 | ScopeFilter | ✅ committed (f3c652a) |
| 5 | ScopeFilter 示范 | ✅ committed (997f9bb) |
| 6 | AuditLog + @audited | ✅ committed (559e3bd) |
| 7 | @audited 集成 | ✅ committed (1050518) |
| 8 | Migration + 文档 | **未完成** — 缺 Alembic migration（这是测试失败的原因）|

**GPT Code Review 状态**：Plan Review PASS。Code Review 尚未进行（Task 8 未完成）。

### 已知问题

| 问题 | 严重度 | 位置 | 说明 |
|------|--------|------|------|
| Alembic 迁移缺失 | HIGH | Phase 1c Task 8 | capabilities + audit_logs 表无 migration |
| test_migration 失败 | HIGH | test_alembic_migration.py | 上述原因导致 |
| F-04 audit action | MED | school_settings_service.py | upsert_setting 审计 action 始终 "create" |
| F-05 id_param | MED | audit_service.py | set_module_enabled 的 id_param="module_code" 但 db.get 期望 UUID |
| 通知调度 stub | LOW | notification_service.py | 标记已发送但实际未投递 |
| pipeline stub | LOW | workers/grading.py | run_post_exam_pipeline 是空函数 |

---

## 五、总体路线图

### 反哺策略：按依赖链分层推进

```
Phase 1: 数据基底 + 权限引擎 + Agent 基础设施  ← 65% 完成
  ├── 1a 模块管理      ✅ 完成
  ├── 1b 基础信息      ✅ 完成
  ├── 1c 权限引擎      🔄 执行中（差 Task 8 + Code Review）
  └── 1d Agent 实例化   📋 未规划

Phase 2: 核心流程层                              ← 未开始
  ├── 2.1 考试流程补全（状态机 + 阅卷任务分配 + 质量监控 + 成绩发布）
  ├── 2.2 作业系统（全新模块：常规/考前/考后补偿 3 类型）
  └── 2.3 examids 统一查询入参

Phase 3: 价值输出层                              ← 未开始
  ├── 3.1 学情分析（知识点掌握率矩阵 + 错题本 + 成绩趋势 + 薄弱诊断）
  ├── 3.2 考后流水线（成绩发布 → 画像快照 → 错题更新 → 知识点掌握度）
  └── 3.3 分析报告（自定义分析 + 分数段配置 + 跨考试对比 + 导出）

Phase 4: 高级功能层                              ← 未开始
  ├── 4.1 教研题库（智能组卷 6 模式 + 考情雷达）
  └── 4.2 教学管理（集体备课 + 教学计划 + 资源库）
```

### Agent 深度嵌入路线图

| 里程碑 | 依赖 | 内容 |
|--------|------|------|
| **Phase 1c** | 1a+1b | Capability 三层权限 + PolicyEngine + AuditLog（当前进行中）|
| **Phase 1d** | 1c | AgentProfile + AgentRun + ToolAccessResolver + IntentResolver + 模型分层路由 |
| **Phase 1e** | 1d | 常驻巡检 Agent（Detector + Planner + arq 调度）|
| **每个 Phase 2-4 模块** | 1d | 每个模块必须同时交付 Agent 工具清单 + 典型对话示例 + 主动触发规则 |

### Agent 架构决策（Claude × GPT 共识）

| 决策 | 结论 |
|------|------|
| 框架 | 保留自研 ReAct，不用 OpenClaw/Agent SDK |
| 实例 | 逻辑实例(AgentProfile)，共享 worker |
| 权限 | **代码硬执行**，三铁律：执行层判定/SQL scope 注入/Agent 不知限制 |
| 工具选择 | IntentResolver(mini) + 动态工具包裁剪 |
| 模型 | 分层路由：mini/Sonnet 4/GPT-5.4 |
| 巡检 | 定时唤醒 + 确定性检测 + LLM 归因 |

---

## 六、关键设计文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| **总设计** | `C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-business-logic-backfill-design.md` | 好分数反哺 + Agent 深度嵌入 4 Phase 设计（519行）|
| **原始平台设计** | `C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-super-platform-design.md` | P0-P4 原始架构设计 |
| **AI Agent 设计** | `C:\Users\Administrator\edu-cloud\docs\plans\2026-03-16-ai-agent-design.md` | Agent Phase 1-4 原始设计 |
| **Phase 1a plan** | `C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1a-module-management-plan.md` | 模块管理 7 Task（GPT R6 PASS）|
| **Phase 1b plan** | `C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1b-base-info-plan.md` | 基础信息 7 Task（GPT PASS）|
| **Phase 1c plan** | `C:\Users\Administrator\edu-cloud\docs\plans\2026-03-30-phase1c-permission-engine-plan.md` | 权限引擎 8 Task（GPT Plan PASS）|
| **Phase 1c design** | `C:\Users\Administrator\edu-cloud\docs\plans\2026-03-30-phase1c-permission-engine-design.md` | Capability + AuditLog 设计 |
| **haofenshu 业务逻辑** | `C:\Users\Administrator\haofenshu-clone\docs\business-logic.md` | 完整业务逻辑参考（2044行/69KB）|
| **haofenshu 交接** | `C:\Users\Administrator\haofenshu-clone\docs\HANDOFF.md` | haofenshu-clone 项目全貌 |

---

## 七、权限体系现状

### 已实现

```
层 1: RBAC（8 角色 + 11 权限枚举）
  → require_permission() 装饰器
  → 前端 permissions.js 镜像

层 2: 数据范围（UserRole.school_id/class_ids/grade_ids/subject_codes）
  → get_visible_class_ids() / get_visible_subject_codes()
  → Agent 工具 _visible_classes/_visible_subjects 注入

层 3: 模块开关（school_modules 表）
  → ModuleCheckMiddleware API 硬拦截
  → 前端 sidebar moduleCode 过滤
```

### Phase 1c 正在建设

```
层 4: Capability（domain×action×role 细粒度能力矩阵）
  → init_school_capabilities() 默认模板
  → get/set_capability() API
  → check_capability() 待集成到工具调用

层 5: 审计（AuditLog + @audited 装饰器）
  → 自动记录 entity 变更的 before/after
  → 集成到 settings/assignments/selections service
```

### Phase 1d 待建设

```
层 6: Agent 权限（AgentProfile + agent_capabilities）
  → ToolAccessResolver（角色 ∩ 模块 ∩ Capability 三重过滤）
  → PolicyEngine 6 步硬判定
  → Agent 不知道自己被限制了什么
```

---

## 八、测试体系

| 目录 | 文件数 | 覆盖 |
|------|--------|------|
| tests/test_api/ | 12+ | 平台 API (health/schools/joint-exams/results/settings/assignments/selections) |
| tests/test_api_exam/ | 32 | exam-ai 迁入 API |
| tests/test_services/ | 6+ | 平台 Service (school/joint_exam/results/settings/assignment/selection) |
| tests/test_services_exam/ | 27 | exam-ai 迁入 Service |
| tests/test_models/ | 8 | 模型单测 |
| tests/test_knowledge/ | 4 | 知识库单测 |
| tests/test_ai/ | 3 | Agent + LLM + API |
| tests/test_modules/ | 4 | calendar/notification/studio/approval |
| tests/test_workers/ | 8 | grading worker |
| tests/test_alembic_migration.py | 1 | 迁移 smoke test |
| frontend/src/__tests__/ | 6 | router/auth/config/sidebar/aiChat/cardEditor |

---

## 九、即时行动项（优先级排序）

### P0: 完成 Phase 1c（差最后一步）

Phase 1c Task 1-7 代码已 commit，只差 **Task 8: Alembic migration + 文档更新**。

```
[edu-cloud] Executor | 2026-03-30 08:52:37
项目: C:\Users\Administrator\edu-cloud
分支: feat/phase1c-permission-engine
任务: 完成 Phase 1c Task 8（Alembic migration 生成 + test_alembic_migration.py 更新 + CLAUDE.md 更新）
完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
Topic: phase1c
```

### P1: Phase 1c Code Review

Task 8 完成后，跑 GPT Code Review（Gate 2）对 Phase 1c 全部 commits。

### P2: Phase 1c merge to master

Code Review PASS 后，merge `feat/phase1c-permission-engine` 到 master。

### P3: Phase 1d 设计

Agent 实例化 + 常驻巡检设计。这是 Phase 1 的最后一块：
- AgentProfile / AgentRun 数据模型
- ToolAccessResolver（替代 ROLE_TOOL_CATEGORIES）
- IntentResolver（动态工具包裁剪）
- 模型分层路由（接入 LLMSlot）
- 常驻巡检（Detector + Planner + arq）

### P4: Phase 2 设计

Phase 1 全部完成后，进入核心流程层：
- 考试状态机（draft→scanning→grading→reviewing→published）
- 作业系统（3 类型全生命周期）
- 每个模块带 Agent 工具清单

---

## 十、约束与偏好

| 约束 | 说明 |
|------|------|
| T3 流程 | 所有 Phase 必须走 design → plan → GPT Plan Review → 新会话执行 → GPT Code Review |
| 权限硬执行 | 三铁律不可违反：执行层判定 / SQL scope 注入 / Agent 不知限制 |
| 模块交付必含 Agent | 每个新模块 = 后端 + 前端 + Agent 工具 + 测试 |
| 质量优先 | 无时间压力，每层做扎实 |
| UI 参考 haofenshu | 页面结构参考好分数，用 Naive UI 重实现 |
| WSL 后端 | 服务通过 WSL 运行 |
| 不用 OpenClaw | Agent 在 FastAPI 内自建，不依赖外部 Agent 框架 |

---

## 十一、关联项目状态

| 项目 | 路径 | 状态 | 与 edu-cloud 关系 |
|------|------|------|-------------------|
| haofenshu-clone | `C:\Users\Administrator\haofenshu-clone` | 续建完成（85 文件） | 业务逻辑参考库 |
| exam-ai | `C:\Users\Administrator\exam-ai` | 已合入 edu-cloud | 退化为数据采集节点 |
| paper-seg | `C:\Users\Administrator\paper-seg` | 日志重构进行中 | 扫描端，不直接与云端通信 |
| paper-skill | `C:\Users\Administrator\paper-skill` | 运行中 (port 9103) | AI 论文服务，edu-cloud 调用 |
| edu-knowledge-base | `C:\Users\Administrator\edu-knowledge-base` | 独立完成 | 知识底座，数据已加载到 edu-cloud |
