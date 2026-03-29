# 好分数业务逻辑反哺 + Agent 深度嵌入 设计文档

> **日期**: 2026-03-29 16:09:46
> **项目**: edu-cloud（多校多角色教育管理平台）
> **参考源**: haofenshu-clone（好分数全站复刻，业务逻辑参考库）
> **设计方法**: Claude × GPT 双模型两轮深度讨论

---

## 0. 项目定位

edu-cloud 是一个架构成熟但业务逻辑不完善的教育管理平台。haofenshu.com 是真实商业产品（好分数精准教学），已被完整逆向（45 页面 / 50+ API / 69KB 业务逻辑文档）。

本设计的目标：**系统性地将 haofenshu 的真实业务逻辑反哺到 edu-cloud 中，同时以 Agent 为核心交互范式重构整个系统。**

### 架构约束

| 约束 | 说明 |
|------|------|
| edu-cloud 承担全功能 | 包括日常操作（考试/阅卷/作业/教学），exam-ai 退化为数据采集节点 |
| 当前聚焦学校级 | 教育局/集团级后期 |
| 质量优先 | 无时间压力，每层做扎实再往上 |
| UI 参考 haofenshu 页面结构 | 但用 Naive UI 重实现 |
| Agent 是核心交互范式 | 不是附加功能，是系统的主要使用方式 |
| 模块可管理 | 管理员可启用/禁用模块，影响导航/API/Agent |
| 权限硬执行 | 不依赖 LLM 判断，代码层强制 |

---

## 1. 差距全景

| 维度 | edu-cloud 现状 | haofenshu 有但缺的 |
|------|---------------|-------------------|
| 学情分析 | profile 模块仅空壳 | 知识点掌握率矩阵、错题本、成绩趋势、薄弱诊断 |
| 作业系统 | 完全没有 | 5 种作业类型、发布→提交→批改→分析全流程 |
| 考后流水线 | pipeline 是 stub | 自动生成画像快照、错题更新、知识点掌握度计算 |
| 教研/题库 | bank 模块最小化 | 智能组卷(6种模式)、考情雷达、集体备课、教学计划 |
| 分析报告 | 基础统计有 | 自定义分析、分数段配置、跨考试对比、等级赋分 |
| 阅卷细节 | AI 批改有、流程不完整 | 任务分配到题块、质量监控、多人并行阅卷、进度追踪 |
| 基础信息 | CRUD 有 | 教师排课表、选考组合、变更审计日志 |
| 学校配置 | 简单 | 50+ feature flag、产品授权、扫描 DPI |

---

## 2. 反哺策略：按依赖链分层推进

```
Phase 1: 数据基底 + 权限引擎 + Agent 基础设施
Phase 2: 核心流程（考试全链路 + 作业系统）
Phase 3: 价值输出（学情分析 + 考后流水线 + 报告）
Phase 4: 高级功能（教研题库 + 智能组卷 + 教学模块）
```

每层建完后可用、可测试。后层天然依赖前层数据。

---

## 3. Agent 深度嵌入架构（Claude × GPT 共识）

### 3.1 核心决策

| 问题 | 结论 | 理由 |
|------|------|------|
| 用 OpenClaw？ | **不用做底座，不 fork** | 单用户桌面助手，跟多租户 SaaS 数据隔离/组织授权不兼容 |
| 自研 vs SDK | **保留自研 ReAct** | 现有内核已生产级；框架迁移不解决真正问题（工具治理） |
| 单 vs 多 Agent | **单入口 + 动态工具包裁剪** | IntentResolver(mini 模型) 选 domain pack → 执行 Agent 在小集合里高精度选择 |
| 常驻 Agent | **做，定时唤醒 + 确定性检测 + LLM 归因** | 不是无限循环自治体，是可审计的巡检 run |
| 员工级 Agent | **逻辑实例(AgentProfile)，共享运行时** | 每人有持久身份/偏好/记忆/权限，不需要物理进程 |
| 权限 | **RBAC + ABAC + Capability 三层，代码硬执行** | Agent 权限是用户权限的受限委托 |
| 模型选择 | **分层路由** | IntentResolver→mini, 日常→Sonnet 4, 复杂→GPT-5.4/Opus |

### 3.2 权限铁律（数据安全最高优先级）

**三条不可违反的铁律：**

1. **权限判定在工具执行层，不在 LLM 推理层。** PolicyEngine 是纯 Python 代码，不读 system prompt，不受 LLM 输出影响。LLM 无法通过任何方式（包括 prompt injection）绕过权限检查。

2. **数据查询自带 scope 注入。** 所有 SQL 查询强制拼接 `WHERE school_id = ? AND class_id IN (?)` 等条件。不是"查完再过滤"，而是"查的时候就只查允许的范围"。即使工具代码有 bug，数据库层也不会返回越权数据。

3. **Agent 不知道自己被限制了什么。** 被拒绝的调用返回"无数据"或"无权限"，不告诉 LLM 存在其他数据。避免 LLM 尝试其他路径绕过。

### 3.3 权限决策链

每次 Agent 工具执行前，PolicyEngine 按固定顺序硬判定：

```
① 模块是否启用？ ─── school_modules 表 ──── 否 → 拒绝（"该功能未启用"）
  ↓ yes
② 用户角色有基础资格？ ── RBAC ──────────── 否 → 拒绝（"无权限"）
  ↓ yes
③ Agent 被授予该 capability？── agent_capabilities ─ 否 → 拒绝（"无数据"）
  ↓ yes
④ 资源范围命中？ ── ABAC scope ────────── 否 → 拒绝（"无数据"）
  ↓ yes
⑤ 需要审批？ ── agent_approval_policies ── 是 → 生成草稿，等审批
  ↓ no
⑥ 执行工具，SQL 查询自带 scope 注入
```

**关键原则：**
- 默认拒绝，显式授权
- deny 优先于 allow
- Agent 权限 ≤ 用户本人权限（受限委托）
- 管理员不能授出超过自身管理范围的权限

### 3.4 Capability 体系

不直接映射工具名，而是映射业务能力：

| 能力域 | 读 | 写 |
|--------|----|----|
| 成绩 | `scores.read` | `scores.write` |
| 作业 | `homework.read` | `homework.assign`, `homework.grade` |
| 学情 | `analytics.read` | `analytics.export` |
| 学生 | `student.read` | `student.write` |
| 报告 | `report.read` | `report.generate` |
| 通知 | `notification.read` | `notification.send` |
| 考试 | `exam.read` | `exam.manage` |
| 题库 | `bank.read` | `bank.write` |
| 系统 | `system.read` | `system.admin` |

权限表达示例：

```yaml
# "张老师的 Agent：查看初二生物成绩 + 布置作业，不能改学生信息"
agent_profile: agent-zhanglaoshi
capabilities:
  - capability: scores.read
    effect: allow
    scope: { grade_ids: [初二], subject_codes: [BIO] }
  - capability: homework.assign
    effect: allow
    scope: { grade_ids: [初二], subject_codes: [BIO] }
  - capability: student.write
    effect: deny
```

### 3.5 Agent 实例模型

```
┌──────────────────────────────────┐
│       Agent Control Plane         │
│  (FastAPI 内嵌：profile/policy/   │
│   run/audit 管理)                 │
└──────────────┬───────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────┐         ┌─────▼──────┐
│ 员工级  │         │  常驻巡检   │
│ Agent   │         │  Agent     │
│ Profile │ ×N      │  Profile   │ ×1/school
└───┬────┘         └─────┬──────┘
    │                     │
    ▼                     ▼
┌─────────────────────────────────┐
│     共享 Agent Runtime Worker    │
│  (arq queue, ReAct loop, LLM)   │
│  每次执行 = 一个 AgentRun        │
└─────────────────────────────────┘
```

**AgentProfile 字段**：
- `id`, `owner_user_id`, `school_id`
- `profile_type` (employee / patrol / system)
- `display_name`, `preferences` (JSON)
- `memory_summary` (长期记忆摘要)
- `policy_version` (关联的权限快照版本)
- `status` (active / suspended / archived)

**AgentRun 字段**：
- `id`, `profile_id`, `trigger` (chat / cron / event)
- `status` (running / completed / failed / timeout)
- `token_cost`, `tool_calls_count`, `duration_ms`
- `findings` (JSON: 巡检发现)
- `artifacts` (JSON: 产出的草稿/通知)

### 3.6 常驻巡检 Agent

```
arq cron（可配置频率：每小时/每天）
  → Detector（纯 SQL 规则，不用 LLM）
    ├── 考试阅卷超 3 天未完成
    ├── 作业提交率 < 50% 且距截止 < 24h
    ├── 班级均分异常波动（偏离年级均值 >2σ）
    ├── 审批积压 > 5 天
    └── （管理员可配置规则 via agent_watch_specs）
  → 有 signal？
    ├── yes → Planner（LLM 做归因摘要 + 建议）
    │         → 产出 agent_findings + agent_tasks（草稿）
    │         → 推送通知给相关角色
    └── no  → 记录 "巡检正常"，结束 run
```

**安全边界**：
- 巡检 Agent 默认只有 read 权限
- 每次 run 有 token/cost/time/tool-call 上限
- 幂等键 + 冷却时间，防重复推送
- 写操作一律生成草稿，走审批

### 3.7 ToolSpec 元数据升级

```python
@tools.register(
    name="get_homework_stats",
    description="查询作业提交统计",
    category="L2_homework",
    module_code="homework",
    requires_capabilities={"homework.read"},
    risk_level="read",         # read / write / admin
    is_mutating=False,
    parameters={...}
)
```

### 3.8 ToolAccessResolver（替代 ROLE_TOOL_CATEGORIES）

```python
class ToolAccessResolver:
    def resolve(self, agent_profile, db) -> list[ToolSpec]:
        all_tools = registry.get_all()

        # 层 1: 模块过滤
        enabled_modules = get_school_modules(db, agent_profile.school_id)
        tools = [t for t in all_tools if t.module_code in enabled_modules]

        # 层 2: 角色资格过滤
        role = get_user_role(db, agent_profile.owner_user_id)
        tools = [t for t in tools if role_has_base_access(role, t.category)]

        # 层 3: Capability 过滤
        agent_caps = get_agent_capabilities(db, agent_profile.id)
        tools = [t for t in tools
                 if t.requires_capabilities <= agent_caps.allowed_set]

        return tools
```

### 3.9 IntentResolver（动态工具包裁剪）

```
用户消息 → IntentResolver（GPT-5 mini，<100ms）
         → 识别 1-3 个 domain pack
         → 只传该 domain 的工具给执行 Agent（10-15 个）
         → Agent 在小工具集里高精度选择
```

防止 60-80 工具时 LLM 工具选择准确率下降。

### 3.10 上下文优化

| 现状 | 优化 |
|------|------|
| system prompt 枚举全部工具名 | 只写能力摘要 |
| 工具结果全量 JSON 回灌 | 大结果摘要 + 分页 token，需明细时二次取数 |
| 最旧优先裁剪历史 | LLM 摘要压缩，保留关键决策点 |
| `len(text)//3` 估算 | 按 provider 用真实 tokenizer |

### 3.11 模型分层路由

接入已有 LLMSlot 体系：

| 场景 | 模型 | 用途 |
|------|------|------|
| IntentResolver | GPT-5 mini | 意图分类 + 工具包选择 |
| 日常对话 | Claude Sonnet 4 | 教师日常查询、报告生成 |
| 复杂分析 | GPT-5.4 / Claude Opus | 跨模块综合推理、学情诊断 |
| 主动巡检 | Sonnet 4 | 后台事件驱动分析 |

---

## 4. Phase 详细设计

### Phase 1: 数据基底 + 权限引擎 + Agent 基础设施

**目标**：所有后续模块的地基。完成后，系统具备模块管理、权限引擎、Agent 实例化和巡检能力。

#### 1.1 学校配置体系

- 新增 `school_settings` 表：`school_id + key + value(JSON)`
- 配置分类：feature / exam / ai / scan / display
- API: `GET/PATCH /api/v1/schools/{id}/settings`
- 前端：学校管理页新增"配置"Tab

#### 1.2 基础信息增强

| 新增 | 数据模型 | 前端 |
|------|---------|------|
| 教师排课表 | `teacher_assignments` (teacher_id + class_id + subject_id) | 排课管理页 |
| 选考组合 | `subject_selections` (name + subjects JSON) | 选考管理页 |
| 变更审计 | `audit_logs` (entity + action + before/after + operator) | 通用审计中间件 + 日志页 |
| 年级组层级 | 增强 classes 表 grade 关联 | - |

#### 1.3 知识点关联

- `questions` 表增加 `knowledge_point_ids` (JSON array)
- 建立题目→知识点映射（学情分析前置条件）

#### 1.4 模块管理

- 新增 `school_modules` 表 (school_id + module_code + enabled + config)
- API 中间件：disabled 模块返回 403
- 前端 sidebar 动态渲染
- 初始模块：exam / grading / homework / study_analytics / report / research / teaching / calendar / studio

#### 1.5 权限引擎

- Capability 体系定义（9 域 × 读/写）
- PolicyEngine（纯 Python PDP，策略存 PostgreSQL）
- `agent_capabilities` 表 (profile_id + capability + effect + scope_json)
- `agent_policy_rules` 表 (管理员配置)
- `tool_capability_map` 表 (tool_name + required_capabilities)
- 决策链实现（6 步硬判定）
- scope 注入到所有 SQL 查询

#### 1.6 Agent 实例化

- `agent_profiles` 表
- `agent_runs` 表
- `agent_findings` / `agent_tasks` / `agent_artifacts` 表
- ToolSpec 元数据升级（module_code + requires_capabilities + risk_level）
- ToolAccessResolver 替代 ROLE_TOOL_CATEGORIES
- IntentResolver（mini 模型意图分类）
- 模型分层路由接入 LLMSlot

#### 1.7 Agent 管理 UI

- Agent 列表页（本校所有 Agent Profile）
- Agent 权限配置页（capability 读/写矩阵 + scope 绑定）
- Agent 运行历史 + 审计日志页
- 模块管理页（启用/禁用）

#### 1.8 常驻巡检 Agent

- Detector（纯 SQL 规则引擎）
- `agent_watch_specs` 表（管理员可配置巡检规则）
- Planner（LLM 归因摘要）
- arq cron 调度
- 安全边界（token 上限 / 幂等 / 冷却时间）

### Phase 2: 核心流程层

**前置条件**：Phase 1 完成。

#### 2.1 考试流程补全

- 考试状态机：`draft → scanning → grading → reviewing → published → archived`
- `grading_assignments` 表（题块级任务分配）
- `grading_quality_checks` 表（质量监控）
- 阅卷进度大屏页
- 成绩发布触发排名计算
- **Agent 工具**：get_grading_progress, get_quality_report, assign_grading_task
- **Agent 触发规则**：阅卷超时提醒、质量异常告警

#### 2.2 作业系统（全新模块）

- 3 种类型：常规 / 考前练习 / 考后补偿
- `homework_tasks` + `homework_submissions` 表
- 状态：`draft → active → expired → closed`
- 前端：列表页 / 布置页（步骤向导）/ 详情页 / 考后补偿页（AI 推荐）
- **Agent 工具**：get_homework_stats, assign_homework, get_submission_details, recommend_remedial
- **Agent 触发规则**：提交率低于阈值提醒、截止前 24h 催交

#### 2.3 examids 统一查询入参

- 用 `exam_subject_id` 作为分析查询统一入参
- 不引入 haofenshu 的字符串复合键

### Phase 3: 价值输出层

**前置条件**：Phase 2 完成。

#### 3.1 学情分析

- 激活 profile 模块：知识点掌握率矩阵（班级/年级/学生三级）
- 错题本（student_error_book 已有表，补全 service + API + UI）
- 成绩趋势（跨考试 score/rank 折线）
- 薄弱诊断（worst KPs / 未掌握人数最多 / 方差最大）
- **Agent 工具**：get_class_weakness, get_student_diagnosis, get_knowledge_trend, get_error_book
- **Agent 触发规则**：新考试成绩发布后自动生成学情摘要

#### 3.2 考后流水线

- 激活 pipeline：成绩发布 → 自动触发
  - 画像快照生成（student_exam_snapshots）
  - 错题本更新（student_error_book）
  - 知识点掌握度重算（student_knowledge_mastery）
- 流水线状态追踪 + 失败重试

#### 3.3 分析报告

- 自定义分析构建器（选科目/班级/指标组合）
- 分数段配置（per school，默认 85/70/60 四档）
- 跨考试对比（同年级不同考试的趋势）
- 报告导出（PDF via Studio）
- **Agent 工具**：generate_custom_report, compare_exams, get_score_segments

### Phase 4: 高级功能层

**前置条件**：Phase 3 完成。

#### 4.1 教研题库

- 题库管理 UI（bank 模块增强）
- 智能组卷：章节组卷 / 知识点组卷 / 细目表组卷
- 考情雷达（历史出题频率分析）
- **Agent 工具**：search_bank_questions, generate_paper, get_exam_trend

#### 4.2 教学管理

- 集体备课（协同资源共享）
- 教学计划管理
- 备课资源库
- **Agent 工具**：get_teaching_plan, search_resources

---

## 5. 每个模块的 Agent 交付物清单模板

后续 Phase 2-4 每个模块的设计文档必须包含：

```markdown
## Agent 工具清单
| 工具名 | 描述 | module_code | requires_capabilities | risk_level |
|--------|------|------------|----------------------|------------|

## Agent 典型对话示例
| 角色 | 问题 | 调用工具 | 返回摘要 |
|------|------|---------|---------|

## 主动 Agent 触发规则
| 事件 | 条件 | 输出 | 接收角色 |
|------|------|------|---------|
```

---

## 6. 新增数据模型汇总

### Agent 核心表

| 表 | 用途 |
|----|------|
| `agent_profiles` | Agent 身份（owner, school, type, preferences, memory） |
| `agent_capabilities` | Agent 能力绑定（capability + effect + scope） |
| `agent_policy_rules` | 管理员配置的策略规则 |
| `agent_scope_bindings` | Agent 数据范围绑定 |
| `agent_runs` | 执行记录（trigger, status, cost, findings） |
| `agent_findings` | 巡检发现 |
| `agent_tasks` | Agent 产出的待办/草稿 |
| `agent_artifacts` | Agent 产出的文档/报告 |
| `agent_watch_specs` | 巡检规则配置 |
| `tool_capability_map` | 工具→能力映射 |
| `module_capability_map` | 模块→能力映射 |

### 业务增强表

| 表 | Phase | 用途 |
|----|-------|------|
| `school_settings` | 1 | 学校配置 KV |
| `school_modules` | 1 | 模块开关 |
| `teacher_assignments` | 1 | 教师排课 |
| `subject_selections` | 1 | 选考组合 |
| `audit_logs` | 1 | 变更审计 |
| `grading_assignments` | 2 | 阅卷题块分配 |
| `grading_quality_checks` | 2 | 质量监控 |
| `homework_tasks` | 2 | 作业任务 |
| `homework_submissions` | 2 | 作业提交 |

---

## 7. 技术决策记录

| 决策 | 选择 | 否决项 | 理由 |
|------|------|--------|------|
| Agent 框架 | 自研 ReAct + 治理层升级 | OpenClaw fork / Agent SDK / LangGraph | 多租户 SaaS 需求与桌面 Agent 不兼容；现有内核已生产级 |
| Agent 实例 | 逻辑实例(AgentProfile) + 共享 worker | 每人一个常驻进程 | 运维复杂度可控，数据库主导的数据面 |
| 权限引擎 | 内嵌 PDP + PostgreSQL 策略存储 | Casbin / OPA | 当前阶段不需要外部引擎；Cedar 风格规则更适合未来演进 |
| 工具选择 | IntentResolver(mini) + 动态裁剪 | 多 Agent swarm | 教育场景天然跨域，多 Agent 增加延迟和上下文同步成本 |
| 常驻巡检 | 定时唤醒 + 确定性检测 + LLM 归因 | 无限循环自治体 | 可审计、可限流、可回放 |
| 模型路由 | 分层（mini/Sonnet/GPT-5.4） | 单模型 | 成本和延迟优化 |

---

## 8. 风险与缓解

| 风险 | 严重度 | 缓解 |
|------|--------|------|
| Phase 1 范围过大导致延期 | HIGH | 内部再拆分为 1a(配置+基础信息) → 1b(权限引擎) → 1c(Agent 实例化) → 1d(巡检) |
| 权限模型过度设计 | MED | 第一版只做 capability allow/deny + 简单 scope，不做条件表达式 |
| LLM 工具选择准确率随工具增长下降 | MED | IntentResolver 前置裁剪；持续监控准确率指标 |
| 常驻巡检 Agent 产生误报噪音 | MED | 冷却时间 + 管理员可调阈值 + 巡检规则审计 |
| 前端权限管理 UI 复杂度高 | MED | 预置角色模板（班主任/任课教师/年级组长），管理员在模板基础上微调 |

---

## 附录 A: OpenClaw 借鉴要素

| OpenClaw 概念 | edu-cloud 对应 |
|--------------|---------------|
| Gateway (统一控制平面) | Agent Control Plane (FastAPI 内嵌) |
| agentId (逻辑身份) | AgentProfile.id |
| per-agent memory/workspace | AgentProfile.memory_summary + preferences |
| per-agent tool allow/deny | agent_capabilities + ToolAccessResolver |
| sandbox + egress guardrail | PolicyEngine 硬判定 + SQL scope 注入 |

## 附录 B: haofenshu 业务逻辑参考索引

| 模块 | 参考文件 | 关键规则 |
|------|---------|---------|
| 认证 | business-logic.md §1 | JWT + 多角色 + unifyToken SSO |
| 考试 | business-logic.md §2 | examids 复合键、考试类型分类 |
| 阅卷 | business-logic.md §3 | 题块分配、质量监控、多模式阅卷 |
| 分析 | business-logic.md §4 | 12 种报告视图、分数段配置 |
| 学情 | business-logic.md §5 | 知识点掌握率矩阵、三级诊断维度 |
| 作业 | business-logic.md §6 | 5 种类型、完整生命周期 |
| 基础信息 | business-logic.md §7 | ID 格式、教师多角色、选考组合 |
| 教研 | business-logic.md §8 | 6 种组卷模式、考情雷达 |
| 学校配置 | business-logic.md §跨切面 | 50+ feature flag |
