# edu-cloud AI Agent 系统性优化设计

> 状态：设计草案（Claude + GPT 5.5 三轮辩论产出）
> 日期：2026-05-12
> 范围：AI Agent 子系统（`src/edu_cloud/ai/`）

---

## 1. 现状诊断

### 1.1 架构基线

| 维度 | 现状 | 评估 |
|------|------|------|
| 工具数量 | 63 个 / 23 模块 | 覆盖广 |
| 团队定义 | 3 个（edu_data/knowledge/homework），按数据域组织 | 与教师心智不匹配 |
| 团队启用 | **生产禁用**（`runtime.py:147` team_registry=None） | 基础设施闲置 |
| 工具覆盖 | 30/63 分配到团队，33 个孤儿工具 | 覆盖缺口大 |
| 自主循环 | Tier 1-3 分级（25/15/8 turns），plan→act→observe 骨架 | 有基础但无硬约束 |
| 安全控制 | ToolSpec 有 is_read_only/risk_level/sensitivity | **loop 和 executor 不检查** |
| 预算控制 | token 只统计不拦截，BUDGET_EXHAUSTED 枚举未接入 | **无硬限制** |
| 输出校验 | OutputValidator 存在 | **只 warn 不 block** |
| 审计 | AiToolCall 记录工具/参数/结果摘要/耗时 | **无决策理由、无确认记录** |
| 意图路由 | IntentRouter/ModelRouter 硬编码关键词 | 不可扩展 |
| 跨会话记忆 | entity_memory + project_state，DB-backed | ProjectState 几乎未使用 |
| 工作流 | W1/W3/W6 三个预定义流程，DB-backed 幂等 | 与 Agent 未融合 |
| SSE | 5 事件类型（thinking/plan/tool_call/answer/done） | 无确认通道 |

### 1.2 关键发现

1. **安全空洞**：工具元数据（risk_level/is_read_only）已定义但执行链不检查，写操作无确认闸
2. **预算缺失**：token 只累计不拦截（`agent_loop.py:157`），无请求级/用户级/学校级配额
3. **场景错位**：团队按数据域（考试/知识/作业）组织，教师按场景思考（"考完了怎么样"）
4. **Team 死代码**：3 个团队定义从未在生产激活，Supervisor 直接走单 loop
5. **审计太薄**：只记工具调用，不记路由决策、计划理由、确认动作、预算消耗
6. **工具结果泄漏**：raw tool_result 直接通过 SSE 发送前端（`agent_loop.py:236`）

---

## 2. 设计原则（七柱）

| 柱 | 原则 | 约束 |
|----|------|------|
| **P1 通用智能体** | 一个 agent 拥有全部工具，自己判断该用什么——像 Claude Code | 不做场景分类/路由分发 |
| **P2 自主循环** | plan→act→observe→re-plan 自主闭环 | 预算和安全是硬边界 |
| **P3 插件兼容** | ToolSpec v2 + Adapter 协议，外部能力可接入 | P0/P1 只做 manifest 预留，P2 接外部 |
| **P4 权限硬边界** | RBAC + DataScope + Module 三层 | fail-closed，不靠 prompt 约束 |
| **P5 动作安全** | 读自动、写确认、高风险二次确认 | executor 层硬拦截 + loop 层体验 |
| **P6 预算兜底** | 请求级硬限 + 用户/学校级配额 | 超限输出中间结果，不静默中断 |
| **P7 可观测性** | 结构化 trace，不记 chain-of-thought | PII 脱敏，热存 90 天 |

---

## 3. 核心架构：通用智能体

### 3.1 设计理念

**类比 Claude Code：** Claude Code 没有"调试场景"、"编码场景"、"搜索场景"的路由分发。它就是一个 agent，拥有所有工具（Read/Edit/Bash/Grep...），用户说什么它就做什么，自己判断该调用哪些工具、以什么顺序。

**edu-cloud Agent 应该一样：** 一个通用智能体，拥有 63+ 个教育工具。教师说"下节课力学怎么讲"，它自己去查薄弱点、查课标、查真题、生成教学建议。不需要 IntentRouter 先把请求分类到"备课场景"。

```
┌─────────────────────────────────────────────────┐
│                  通用 Agent                      │
│                                                  │
│   system prompt（角色感知 + 学校上下文）           │
│   ┌──────────────────────────────────────────┐   │
│   │  plan → act → observe → re-plan 循环     │   │
│   └──────────┬───────────────────────────────┘   │
│              │                                    │
│   ┌──────────▼───────────────────────────────┐   │
│   │          全量工具池（RBAC 过滤后）          │   │
│   │                                           │   │
│   │  备课: 课标/教材/真题/知识图谱/题库/推荐    │   │
│   │  考试: 成绩/分布/对比/排名/诊断/报告       │   │
│   │  学生: 画像/趋势/错题/知识掌握/行为         │   │
│   │  德育: 积分/排名/记录/班规/行为分析         │   │
│   │  作业: 布置/提交/批改/统计/补救             │   │
│   │  阅卷: 进度/质量/分配/评分规则              │   │
│   │  知识: 搜索/编辑/树查询/关联               │   │
│   │  答题卡: 解析/排版/布局                     │   │
│   │  报告: 生成/评语                           │   │
│   │  记忆: 跨会话实体记忆                      │   │
│   │  [P2: 外部插件工具]                        │   │
│   └───────────────────────────────────────────┘   │
│              │                                    │
│   ┌──────────▼───────────────────────────────┐   │
│   │          安全层                            │   │
│   │  RBAC + DataScope + 写确认 + 预算         │   │
│   └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### 3.2 与"场景团队"方案的区别

| 维度 | 场景团队方案（废弃） | 通用智能体方案（采用） |
|------|-------------------|-------------------|
| 路由 | IntentRouter 先分类再分发 | agent 自己判断，无前置分类 |
| 工具可见性 | 每个场景只看到分配的工具 | agent 看到全部已授权工具 |
| 灵活性 | 场景边界僵硬，跨场景需跳转 | 一次对话可自然跨域 |
| 复杂度 | 需维护场景定义+路由+映射 | 只需维护 system prompt + 工具注册 |
| 类比 | 像 IVR 电话菜单（"查成绩请按 1"） | 像 Claude Code（直接说需求） |

### 3.3 专用能力的体现方式

不通过"场景路由"，而是通过以下机制让 agent 在特定领域更强：

**1. 角色感知 System Prompt**

```python
def build_system_prompt(role, school_context, tools, memory):
    """根据角色和上下文生成 system prompt"""
    prompt = BASE_AGENT_PROMPT  # 通用能力描述
    prompt += f"\n\n## 你的身份\n你是{school_context.school_name}的 AI 教学助手。"
    prompt += f"当前用户角色：{role.display_name}。"
    prompt += f"\n\n## 你拥有的能力\n以下是你可以使用的工具：\n"
    prompt += format_tool_descriptions(tools)  # 全量已授权工具
    prompt += f"\n\n## 教学领域知识\n"
    prompt += DOMAIN_KNOWLEDGE  # 教育领域指引（备课流程、考后分析方法论等）
    if memory:
        prompt += f"\n\n## 已知信息\n{memory}"  # 跨会话记忆
    return prompt
```

**2. 领域知识注入**（代替场景路由）

在 system prompt 中注入教育领域方法论，让 agent 知道"备课应该怎么做"、"考后分析应该看什么"，而不是通过路由强制它走固定流程：

```
## 教学领域知识

### 备课教研
当教师询问备课相关问题时，通常需要：
1. 查看班级学生的薄弱知识点（get_class_knowledge_weakness）
2. 对照课标要求和教材内容（search_curriculum, search_textbook）
3. 参考高考真题和出题趋势（search_gaokao, get_question_stats）
4. 基于以上数据生成教学建议

### 考后分析
当教师询问考试结果时，通常需要：
1. 获取整体概览（get_exam_overview）
2. 查看成绩分布和题目得分率（get_score_distribution, get_question_analysis）
3. 班级对比和排名（compare_classes, rank_students）
4. 生成分析报告（generate_report）

### 学生追踪
当教师关注某个学生时，可以并行查询：
趋势/知识掌握/错题/操行/作业/诊断

（更多领域方法论...）
```

Agent 可以参考这些方法论，但不被强制。教师说"张三最近数学怎么样，顺便帮我看看下节课该讲什么"，agent 自然地同时做学生追踪和备课，不需要"场景跳转"。

**3. 前端上下文注入**

前端在用户打开 AI 面板时，自动注入当前页面上下文（exam_id/class_id/student_id），agent 不需要路由就知道用户关心什么：

```json
{
  "message": "这次考试考得怎么样",
  "refs": { "exam_id": "xxx", "page": "exam-detail" }
}
```

### 3.4 工具治理（替代团队分配）

不再把工具分配到场景团队，而是确保 63 个工具都有完整的元数据：

| 元数据字段 | 用途 | 示例 |
|-----------|------|------|
| is_read_only | 安全分级 | add_conduct_points → false |
| risk_level | 确认策略 | low/medium/high |
| sensitivity | 数据分级 | public/school/student |
| domain | 工具描述辅助 | exam/knowledge/conduct/... |
| module_code | 学校模块开关 | conduct/exam/grading/... |
| allowed_roles | RBAC 过滤 | ["teacher", "dean"] |

agent 看到全量已授权工具，自己决定用什么。安全层负责拦截越权和高风险操作。

---

## 4. 自主循环增强

### 4.1 核心架构

```
用户消息 + 上下文(refs/role/memory)
         │
         ▼
  ┌──────────────┐
  │ System Prompt │  角色 + 领域知识 + 全量工具
  └──────┬───────┘
         ▼
  ┌──────────────────────────────────────┐
  │         Agent Loop（自主循环）         │
  │                                       │
  │  while budget.can_continue():         │
  │    1. LLM 思考 → 选择工具/生成回答     │
  │    2. 如果选择工具：                   │
  │       a. 只读工具 → 直接执行           │
  │       b. 写工具 → 暂停等确认           │
  │    3. 观察结果                         │
  │    4. 如果需要 → 继续循环              │
  │    5. 如果完成 → 生成最终回答          │
  │                                       │
  │  安全检查点：                          │
  │    - 每轮预算检查                      │
  │    - 写操作确认闸                      │
  │    - 输出校验（数值合理性）            │
  │    - DataScope 强制过滤               │
  └──────────────────────────────────────┘
```

### 4.2 re-plan 触发条件

| 触发器 | 条件 | 行为 |
|--------|------|------|
| 工具失败 | 连续 2 次同类工具失败 | 切换替代工具或降级 |
| 结果异常 | OutputValidator 检测数值异常 | 交叉验证或标记不确定 |
| 预算告警 | 80% 阈值 | 压缩上下文、artifact 化、优先输出已有结果 |
| 写操作被拒 | 用户拒绝确认 | 以只读结果收尾，记录拒绝原因 |
| 数据不足 | 工具返回空结果 | 尝试放宽查询条件或告知用户 |

### 4.3 与现有代码的关系

```python
# LoopStrategy = 模型能做什么（能力上限）
# AgentBudget = 允许做什么（运行预算）
# 最终约束 = min(能力, 预算)
effective_turns = min(strategy.max_turns, budget.max_turns)
effective_tools = min(strategy.max_tool_calls, budget.max_tool_calls)
```

**删除/简化的组件：**
- ~~IntentRouter~~（不需要场景分类，agent 自己判断）
- ~~Supervisor 的 classify + run_team 分支~~（只走单 loop）
- ~~AgentTeam/TeamExecutor~~（P2 再考虑 multi-agent）
- ~~SceneRouteResult~~（无场景路由）

**保留/增强的组件：**
- AgentLoop — 核心循环，增加预算检查和写确认
- ToolExecutor — 增加安全硬门禁
- ToolRegistry — 增加 v2 manifest 字段
- ToolAccessResolver — RBAC 过滤不变
- DataScope — 数据隔离不变
- CapabilityProbe — 模型能力检测不变
- MemoryStore — 跨会话记忆不变
- OutputValidator — 从 warn 升级为可 block
- System Prompt — 从工具列表升级为角色 + 领域知识 + 工具

---

## 5. 写操作确认协议

### 5.1 双层拦截

```
AgentLoop（体验层）                    ToolExecutor（硬门禁）
    │                                       │
    ├─ 检测 is_read_only=False              ├─ 最终校验 approval_token
    ├─ 发 SSE confirmation_required         ├─ 无 token → deny + 日志
    ├─ await confirmation_future            ├─ 有 token → 校验签名
    ├─ 收到 approve → 生成 approval_token   └─ 执行
    └─ 收到 reject/timeout → 跳过工具
```

Loop 层负责**用户体验**（暂停、展示影响、等待）；Executor 层负责**安全兜底**（防绕过）。

### 5.2 SSE 事件协议

新增 3 个事件类型（旧前端忽略未知 type，向后兼容）：

```json
// 1. 请求确认
{
  "type": "confirmation_required",
  "data": {
    "confirmation_id": "conf_xxx",
    "run_id": "run_xxx",
    "tool_name": "add_conduct_points",
    "risk_level": "medium",
    "summary": "将为高一(3)班 48 名学生批量添加操行积分",
    "impact": { "students": 48, "records": 48, "write_type": "conduct_points" },
    "args_preview": { "class": "高一(3)班", "rule": "按时交作业", "points": "+2" },
    "expires_at": "2026-05-12T10:35:00+08:00"
  }
}

// 2. 确认结果
{
  "type": "confirmation_resolved",
  "data": { "confirmation_id": "conf_xxx", "decision": "approve" }
}

// 3. 超时
{
  "type": "confirmation_timeout",
  "data": { "confirmation_id": "conf_xxx" }
}
```

### 5.3 确认回传端点

```
POST /api/v1/ai/confirmations/{confirmation_id}
Body: { "decision": "approve" | "reject", "client_run_id": "run_xxx", "reason": "可选" }
```

校验：`session_id + run_id + owner_id + args_fingerprint` 必须匹配。

### 5.4 超时策略

| risk_level | 默认超时 | 说明 |
|-----------|---------|------|
| low | 120 秒 | 低风险写操作 |
| medium | 300 秒 | 常规写操作（教师可能被打断） |
| high | 300 秒 | 高风险，需二次确认或更高权限 |

超时后：loop 以"未执行写操作"的中间结果收尾。Pending 期间每 15 秒发 heartbeat 防代理断流。

### 5.5 批量操作

不逐条确认。展示集合级影响：

```
"将为高一(3)班 48 名学生批量添加操行积分 +2（按时交作业）"
```

高风险操作（如批量修改成绩）需管理员权限或二次确认。

### 5.6 服务端内存结构（P0）

```python
@dataclass
class PendingConfirmation:
    confirmation_id: str
    run_id: str
    session_id: str
    owner_id: int
    school_id: int
    tool_name: str
    call_id: str
    risk_level: str
    args_fingerprint: str
    future: asyncio.Future
    expires_at: datetime
```

P0 用进程内存（现有 session 也是内存）。P1 落库支持多 worker / 断线恢复。

---

## 6. 预算控制

### 6.1 AgentBudget 数据结构

```python
@dataclass
class AgentBudget:
    run_id: str
    school_id: int
    user_id: int
    tier: int

    # 硬限制（请求级）
    max_turns: int
    max_total_tokens: int
    max_tool_calls: int
    max_write_ops: int
    max_wall_clock_ms: int

    # 运行时计数
    used_turns: int = 0
    used_input_tokens: int = 0
    used_output_tokens: int = 0
    used_tool_calls: int = 0
    used_write_ops: int = 0
    started_at: datetime = field(default_factory=datetime.now)

    # 状态
    hard_stop_reason: str | None = None

    def can_continue(self) -> bool:
        if self.hard_stop_reason:
            return False
        if self.used_turns >= self.max_turns:
            self.hard_stop_reason = "turns_exhausted"
            return False
        if self.used_input_tokens + self.used_output_tokens >= self.max_total_tokens:
            self.hard_stop_reason = "tokens_exhausted"
            return False
        if self.used_tool_calls >= self.max_tool_calls:
            self.hard_stop_reason = "tools_exhausted"
            return False
        elapsed = (datetime.now() - self.started_at).total_seconds() * 1000
        if elapsed >= self.max_wall_clock_ms:
            self.hard_stop_reason = "timeout"
            return False
        return True
```

### 6.2 默认配额（请求级）

| Tier | max_turns | max_tokens | max_tool_calls | max_write_ops | max_wall_clock |
|------|-----------|-----------|---------------|--------------|---------------|
| 1 | 25 | 80,000 | 40 | 3 | 180s |
| 2 | 15 | 40,000 | 25 | 2 | 120s |
| 3 | 8 | 16,000 | 12 | 1 | 60s |

### 6.3 扣减点

| 时机 | 扣减项 | 位置 |
|------|--------|------|
| LLM 调用前 | turns += 1 | agent_loop.py while 循环入口 |
| LLM 返回后 | input/output tokens | agent_loop.py LLM 响应处理 |
| 工具执行前 | tool_calls += 1 | tool_executor.py run_one |
| 写操作确认后 | write_ops += 1 | 确认协议 approve 处理 |
| 每轮循环头 | wall_clock 检查 | agent_loop.py while 条件 |

### 6.4 降级路径

```
80% token → compact 上下文 + artifact 化大结果
90% token → 停止调用新工具，基于已有结果回答
tool cap → 只基于已有结果回答
write cap → 继续只读分析
wall-clock → 取消未完成工具，输出中间结果
```

### 6.5 三层配额（P1 实现）

```sql
-- 日聚合统计
CREATE TABLE ai_budget_usage_daily (
    day DATE NOT NULL,
    school_id INTEGER NOT NULL,
    user_id INTEGER,  -- NULL 表示学校整体
    input_tokens BIGINT DEFAULT 0,
    output_tokens BIGINT DEFAULT 0,
    tool_calls INTEGER DEFAULT 0,
    write_ops INTEGER DEFAULT 0,
    request_count INTEGER DEFAULT 0,
    UNIQUE(day, school_id, user_id)
);

-- 配额策略
CREATE TABLE ai_budget_policy (
    school_id INTEGER NOT NULL,
    user_id INTEGER,  -- NULL 表示学校级策略
    role VARCHAR(50),  -- NULL 表示所有角色
    tier INTEGER,
    daily_token_limit BIGINT,
    daily_tool_limit INTEGER,
    daily_write_limit INTEGER,
    enabled BOOLEAN DEFAULT TRUE
);
```

---

## 7. 可观测性（Trace）

### 7.1 数据模型

```sql
-- Agent 运行级 trace
CREATE TABLE ai_agent_trace (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(64) NOT NULL,
    school_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR(50) NOT NULL,
    scene_id VARCHAR(50),
    tier INTEGER,
    model_slot VARCHAR(30),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status VARCHAR(20),  -- running / completed / budget_stop / error
    budget_initial JSONB,
    budget_final JSONB,
    INDEX(school_id, started_at)
);

-- 决策事件（每个决策点一条）
CREATE TABLE ai_agent_trace_event (
    id SERIAL PRIMARY KEY,
    trace_id INTEGER NOT NULL REFERENCES ai_agent_trace(id),
    seq INTEGER NOT NULL,  -- 事件序号
    ts TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(30) NOT NULL,  -- route/plan/tool_select/confirm/re_plan/budget/validate/artifact
    summary TEXT NOT NULL,
    reason_codes JSONB,  -- ["keyword_match:考试", "role:academic_director"]
    input_refs JSONB,    -- {"exam_id": "xxx"}，脱敏
    output_refs JSONB,   -- {"artifact_id": "art_xxx"}
    risk_level VARCHAR(10),
    latency_ms INTEGER,
    INDEX(trace_id, seq)
);
```

### 7.2 必记决策点

| event_type | 记录内容 | 示例 |
|-----------|---------|------|
| route | 候选场景/置信度/最终选择 | scene=post_exam, confidence=0.87, reason=keyword_match |
| plan | 任务分解/依赖关系 | 3 tasks: query→analyze→report |
| tool_select | 工具名/read-write/risk/参数指纹 | tool=compare_classes, readonly=true |
| confirm | 批准/拒绝/超时/耗时 | decision=approve, wait_ms=12300 |
| re_plan | 触发原因 | trigger=tool_failure, fallback=alternative_tool |
| budget | 阈值触发/降级动作 | threshold=80%, action=compact |
| validate | warn/block/通过 | validator=numeric_check, result=pass |
| artifact | 产物创建/引用 | artifact_id=art_xxx, size=45KB |

### 7.3 PII 保护

- 学生 ID 用校级 salt 单向 hash
- 学生姓名**不入 trace**
- 成绩只记区间（如 "80-89"）或 delta 区间
- 工具参数存 fingerprint + 脱敏 preview
- trace 表不存储 raw tool_result

### 7.4 保留策略

| 类别 | 热存 | 冷存 | 备注 |
|------|------|------|------|
| 普通 trace | 90 天 | 删除 | 调试和优化用 |
| 写操作确认 | 1 年 | 归档 | 审计合规 |
| 预算聚合 | 2 年 | 归档 | 成本分析 |

---

## 8. 工具结果 Artifact 化

### 8.1 数据模型

```sql
CREATE TABLE ai_agent_artifact (
    id SERIAL PRIMARY KEY,
    artifact_id VARCHAR(64) NOT NULL UNIQUE,
    school_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    session_id VARCHAR(64),
    run_id VARCHAR(64),
    scene_id VARCHAR(50),
    source_tool VARCHAR(100),
    type VARCHAR(30),  -- table / chart_data / report / diagnosis
    title VARCHAR(200),
    storage_kind VARCHAR(10),  -- db / file
    storage_uri TEXT,
    summary JSONB NOT NULL,    -- 结构化摘要（行数/字段/聚合/异常）
    row_count INTEGER,
    byte_size INTEGER,
    pii_level VARCHAR(10),     -- none / school / student
    data_scope_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    INDEX(school_id, created_at),
    INDEX(session_id)
);
```

### 8.2 自动 Artifact 化规则

| 条件 | 处理 |
|------|------|
| 结果 ≤ 32KB 且 ≤ 50 行学生 | 直接注入模型上下文 |
| 结果 > 32KB 或 > 50 行学生 | 落 artifact，模型只拿 summary + ID |
| 含学生级明细（sensitivity=student） | 强制 artifact + 字段裁剪 |

### 8.3 ToolResult 扩展

```python
@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    summary: dict | None = None           # 结构化摘要
    artifact: ArtifactRef | None = None   # artifact 引用
    metadata: dict | None = None          # 耗时/行数等

@dataclass
class ArtifactRef:
    artifact_id: str
    title: str
    summary: dict      # 行数/字段/聚合指标/异常计数
    preview: str       # 脱敏文本预览（≤500 字）
```

### 8.4 模型引用格式

```json
{
  "artifact_id": "art_xxx",
  "title": "高一(3)班期中数学成绩明细",
  "summary": { "students": 48, "avg": 82.3, "below_60": 3, "drop_10_plus": 5 },
  "preview": "张** 91分(+3), 李** 45分(-12), ...",
  "allowed_queries": ["artifact_query", "artifact_filter", "artifact_chart"]
}
```

### 8.5 跨会话续接

加载同用户 / 同校 / 同场景最近 artifact 的 summary + ID。工具再次查询时按当前 DataScope 重新校验权限。权限变化后隐藏不可见 artifact。

---

## 9. 插件架构（P1 预留 / P2 实现）

### 9.1 信任分层

| 层级 | 权限 | 典型来源 | P0/P1 范围 |
|------|------|---------|-----------|
| core | 按 RBAC 读写 | 内置 63 工具 | 现有 |
| school_trusted | 可写但需确认 | 校本资源、定制工具 | P2 |
| vendor_readonly | 禁写、禁 PII 出域 | 第三方题库 | P2 |
| untrusted | 只读匿名 artifact | 社区 skill | P2 |

### 9.2 ToolSpec v2 Manifest 扩展（P1）

```python
@dataclass
class ToolSpec:
    # 现有字段（保留）
    name: str
    description: str
    parameters: dict
    func: Callable
    category: str = "general"
    module_code: str | None = None
    domain: str = "general"
    requires_capabilities: list[tuple[str, str]] = field(default_factory=list)
    risk_level: str = "low"
    allowed_roles: list[str] | None = None
    is_read_only: bool = True
    sensitivity: str = "school"

    # v2 新增字段（P1 预留）
    trust_tier: str = "core"                # core / school_trusted / vendor_readonly / untrusted
    source: str = "internal"                # internal / mcp / rest
    timeout_ms: int = 30000                 # 执行超时
    max_result_bytes: int = 65536           # 结果上限
    data_sends_off_campus: bool = False     # 是否向外部发送数据
    publisher: str | None = None            # 发布者
    version: str | None = None              # 版本
```

### 9.3 Adapter 接口（P2）

```python
class ToolAdapter(Protocol):
    async def load_manifest(self) -> PluginManifest: ...
    async def list_tools(self) -> list[ToolSpec]: ...
    async def execute(self, tool_name: str, arguments: dict, ctx: ToolContext) -> ToolResult: ...
    async def health(self) -> AdapterHealth: ...
```

三类实现：
- `InternalToolAdapter`：包装现有装饰器工具（零改动迁移）
- `MCPToolAdapter`：对接外部 MCP server（教研社区 skill）
- `RESTToolAdapter`：对接 REST API（第三方题库）

### 9.4 插件生命周期（P2）

```
安装（校验 manifest/签名）→ 管理员审批（权限/出域策略）→ 激活（registry 暴露工具）
→ 运行时（RBAC + trust_tier 约束）→ 停用（隐藏工具，保留审计）→ 卸载（撤销 secret）
```

---

## 10. 实施路线图

### P0：安全基线（阻塞生产使用）— 约 12-16 工作日

| 序号 | 工作项 | 依赖 | 改动文件 | 预估 |
|------|--------|------|---------|------|
| 0 | 工具安全盘点：63 个工具补齐 is_read_only / risk_level / sensitivity | 无 | tools/*.py | 0.5-1d |
| 1 | Executor 硬门禁：写操作必须 approval token，否则 deny | #0 | tool_executor.py, registry.py | 1.5-2d |
| 2 | AgentBudget 请求级：turn/token/tool/write/wall_clock 硬限制 | 无（可与 #1 并行设计） | agent_loop.py, capability_probe.py, schemas.py | 1.5-2d |
| 3 | 写确认 SSE 协议：confirmation_required 事件 + REST 确认端点 | #1, #2 | ai.py, agent_loop.py, schemas.py | 2-3d |
| 4 | 前端确认卡片：暂停态 + 影响范围展示 + 批准/拒绝 | #3 | AiSlidePanel.vue, aiChat.js, sseParser.js | 1.5-2d |
| 5 | Trace MVP：结构化决策事件记录 | #2, #3 | audit.py, models.py, 新建 trace 表 | 2d |
| 6 | Artifact MVP：大结果摘要 + ID，修复 raw result 泄漏 | #5（可选） | tool_executor.py, agent_loop.py, schemas.py | 2-3d |
| 7 | System Prompt 升级：角色感知 + 领域知识注入 + refs 上下文；简化 Supervisor 去掉 team 分支 | #5 | prompts.py, supervisor.py, runtime.py | 1.5-2d |
| 8 | 回归测试 | 全部 | tests/ | 1.5-2d |

**可并行：** #1 和 #2 设计阶段可并行；#5 和 #6 的设计可并行。代码落地建议串行（改同一条 loop/executor/SSE 链路）。

### P1：体验提升 — 约 10-14 工作日

| 工作项 | 内容 | 预估 |
|--------|------|------|
| 单 loop 自主增强 | re-plan 触发器 + 失败恢复 + 验证任务 | 3-4d |
| ToolSpec v2 manifest | 信任级别 / 来源 / 超时 / 结果上限 字段扩展 | 1-2d |
| 用户/学校级配额 | ai_budget_usage_daily + ai_budget_policy + 配额扣减 | 2-3d |
| 教师可见时间线 | trace → progress events 映射，前端任务时间线 UI | 2-3d |
| 领域知识深化 | 扩充 system prompt 中的备课/考后/学生追踪等方法论 | 1-2d |
| 确认落库 | pending confirmation DB 存储，支持断线恢复 | 1-2d |

### P2：长期竞争力 — 估算

| 工作项 | 内容 | 复杂度 |
|--------|------|--------|
| Multi-agent 团队 | TeamExecutor 升级为 DAG/条件/并行，SharedState typed + namespaced | XL |
| Workflow-Agent 融合 | workflow 生成 finding，agent 解释和草拟，写操作经确认 | L |
| 外部插件接入 | MCP / REST adapter + 安装审批 + 沙箱 + 版本管理 | XL |
| 个性化记忆 | 教师偏好 + 班级长期状态 + TTL + 用户可见可删 | M |
| 成本与质量看板 | 基于 trace 聚合：模型成本/失败率/确认率/幻觉拦截率 | M-L |
| 场景扩充 | parent_communication / paper_generation / term_summary | M |

---

## 11. 迁移策略

采用**渐进迁移**，不做大版本切换。

| 组件 | 策略 |
|------|------|
| 工具 | 保留装饰器 + ToolRegistry；新增 v2 字段默认兼容；先 shadow 记录风险判定，再开启 hard gate |
| Supervisor | 简化：去掉 classify + run_team 分支，只走单 loop；旧团队定义保留不删（dead code 不影响运行） |
| SSE | 继续 `data: {"type": ...}`；新增 confirmation_* 事件，旧前端忽略未知 type |
| 前端 | AiSlidePanel 只新增确认 UI；原 5 个事件类型不改语义 |
| 审计 | 保留现有 AiToolCall 表；新增 trace 表，不要求历史回填，用 session_id/run_id 关联 |
| Artifact | 旧 tool_result.data 保留 compact preview；新增 artifact_id/detail_available |
| 预算 | 先请求级硬限制；用户级/学校级先只统计，P1 再开启配额扣减 |

---

## 12. 风险矩阵

| 风险 | 影响 | 概率 | 缓解 |
|------|------|------|------|
| 敏感数据通过 SSE / tool_result / trace 泄漏 | 严重 | 中 | 先修 raw result 外发；敏感工具默认 artifact preview；trace 禁学生姓名原始成绩 |
| 写操作绕过确认（子 agent / workflow / 插件） | 严重 | 低 | executor 层硬门禁是最终防线；审批绑定 tool_call fingerprint；双层拦截 |
| 工具过多导致 LLM 选错工具 | 中等 | 中 | 工具描述精确化；领域知识引导；OutputValidator 交叉验证结果合理性 |
| 预算限制让回答半截中断、教师困惑 | 中等 | 中 | 超限前输出 partial answer；trace 记录 budget_stop；保留 artifact 供续接 |
| 教师不理解 agent 暂停原因 | 低 | 高 | 确认卡只写"将改什么、影响谁、能否撤销"；禁止展示内部技术理由 |

---

## 13. 验证清单

### P0 完成标准

- [ ] 63 个工具全部有准确的 is_read_only / risk_level / sensitivity 标注
- [ ] 写操作无 approval token 时 executor 层 deny（不依赖 loop 层）
- [ ] AgentBudget 在 turn / token / tool / wall_clock 任一超限时停止
- [ ] SSE 发送 confirmation_required，前端展示确认卡，POST 回传可用
- [ ] 超时 300s 后自动以中间结果收尾
- [ ] trace 记录 plan / tool_select / confirm / budget / validate 5 类事件
- [ ] 大结果自动 artifact 化，SSE 不泄漏 raw 学生数据
- [ ] System prompt 包含角色感知 + 领域知识 + refs 上下文
- [ ] Supervisor 简化后只走单 loop，不影响现有功能
- [ ] 现有前端不因新增 SSE 事件类型崩溃
- [ ] 现有 63 个工具的只读调用行为不受影响

---

## 附录 A：GPT 5.5 审查共识

以下结论经 Claude + GPT 三轮辩论 + 用户纠正达成共识：

1. **通用智能体，不做场景路由**：像 Claude Code 一样，一个 agent 拥有全部工具，自己判断该用什么。不需要 IntentRouter 分类，不需要场景团队分发。专用能力通过 system prompt 领域知识 + 工具元数据体现
2. **先安全后功能**：最危险的不是 AgentTeam 没启用，而是工具有风险元数据但执行链不检查
3. **单 loop 优先于 multi-agent**：P0/P1 增强单 loop，避免 multi-agent 放大越权和不可解释
4. **不上 WebSocket**：确认协议用 REST 端点最小改动，不引入双向连接复杂度
5. **Artifact 阈值 32KB**：8KB 太低会频繁 artifact 化削弱分析能力
6. **插件架构 P2**：P1 只做 ToolSpec v2 manifest 字段扩展，不加载外部插件
7. **确认超时 5 分钟**：教师被课堂打断是常态，120 秒太短
8. **Workflow 是 Agent 的确定性工具层**：W1/W3/W6 生成 finding，Agent 负责解释和草拟
