# edu-cloud Agent 进化设计文档

> 创建时间: 2026-04-05 07:41:39
> 状态: 设计完成
> 级别: T4（跨模块架构升级，4 Phase 渐进交付）
> [2026-04-05 11:44:02 Phase 1 实现完成] Commits: bf4c545..e45bb05

## 0. 背景与目标

### 现状

edu-cloud Agent 是一个生产级单 Agent 循环系统：
- 39 个教育专用工具（8 领域 12 模块）
- 3 Tier LLM 能力自适应（capability_probe）
- 并发工具执行（读写分离，最大 10 并发）
- 双通道敏感度路由（primary/enhanced）
- 三层 fail-closed 权限（RBAC + Module + Capability）
- 3 个自动化工作流（W1 考后分析 / W3 学生画像 / W6 巡检）

### 能力瓶颈

| 瓶颈 | 表现 | 根因 |
|------|------|------|
| 单 Agent 上下文爆炸 | 长链条任务（论文/课件）后期质量下降 | 39 工具 + 中间产物填满 context |
| 无跨会话记忆 | 每次会话从零开始 | session_memory.py 提取但未持久化 |
| 工作流无智能 | W1/W3/W6 只做 SQL 统计 | 无 LLM 参与推理 |
| 子 Agent 空声明 | capability_probe 有 sub_agents=True 但无执行引擎 | 未实现 |
| 模型策略单一 | 整个会话用同一个 slot | 无任务级模型动态选择 |

### 目标

将 Agent 从"单循环工具调度器"升级为"多 Agent 编排平台"，支撑课件生成、论文写作等长周期复杂任务。同时将 paper-skill 项目合入 edu-cloud 作为论文写作子 Agent。

### 竞品参考

| 能力 | DeerFlow (字节) | edu-cloud 当前 | edu-cloud 目标 |
|------|----------------|---------------|---------------|
| 多 Agent 编排 | LangGraph DAG 并行 | 无 | Supervisor + AgentTeam |
| 模型灵活性 | 任意 LLM | 双通道固定 | 按任务动态选模型 |
| 跨会话记忆 | 内置 | 无 | 3 类记忆持久化 |
| 权限/数据安全 | 无 | 三层 fail-closed | 保持，扩展到记忆层 |
| 领域深度 | 通用 | 39 教育工具 | 39 + 9 新工具 + 6 工作流 |

---

## 1. Phase 路线图

```
Phase 1: 多 Agent 编排引擎        ← 核心能力上限突破
Phase 2: 跨会话记忆 + 项目状态持久化 ← 支撑长周期任务
Phase 3: 课件生成 + 论文写作 Team   ← 业务场景落地（含 paper-skill 合入）
Phase 4: 工作流 LLM 化 + 评估基准   ← 质量闭环
```

依赖关系：Phase 2 依赖 Phase 1，Phase 3 依赖 Phase 1+2，Phase 4 仅依赖 Phase 1。

---

## 2. Phase 1: 多 Agent 编排引擎

### 2.1 架构

```
┌─────────────────────────────────────────────────┐
│              Supervisor Agent                     │
│  (强模型 · 任务分解 · 路由 · 汇总)               │
│  输入: 用户请求 + DataScope + 可用 AgentTeam     │
│  输出: 最终响应 (SSE 流式)                        │
└──────────┬──────────────────┬────────────────────┘
           │ dispatch()       │ dispatch()
     ┌─────▼─────┐     ┌─────▼─────┐
     │ AgentTeam  │     │ AgentTeam  │    ← 按领域注册
     │ "research" │     │ "edu_data" │
     │            │     │            │
     │ SubAgent 1 │     │ SubAgent 1 │    ← 各带专属工具子集
     │ SubAgent 2 │     │ SubAgent 2 │
     │ SharedState│     │ SharedState│    ← 组内共享
     └────────────┘     └────────────┘
```

### 2.2 通信模式

混合模式：组内共享状态，组间消息传递。

- 组内共享状态：扩展现有 agent_loop State 对象，同一 AgentTeam 的子 Agent 读写同一个 SharedState
- 组间消息传递：通过现有 arq + Redis 任务队列，不同任务之间通过消息通信

### 2.3 核心组件

#### AgentSpec（子 Agent 声明）

```python
@dataclass
class AgentSpec:
    name: str                    # "research", "writing", "data_query"
    description: str             # Supervisor 路由依据
    tools: list[str]             # 该 Agent 可用的工具子集
    model_tier: int | None       # 强制 Tier，None=自动选
    max_turns: int               # 独立上下文轮次上限
```

#### AgentTeam（子 Agent 组）

```python
@dataclass
class AgentTeam:
    name: str                    # "paper_writing", "exam_analysis"
    agents: list[AgentSpec]
    state_class: type            # PaperState / ExamState
    execution: "parallel" | "sequential" | "dag"
```

#### Supervisor 路由逻辑

- 接收用户请求 → 判断需要哪个 AgentTeam
- 单工具可解 → 直接走现有 agent_loop（向后兼容）
- 多步骤 → 分派到 AgentTeam，子 Agent 在共享 State 上协作
- 汇总子 Agent 结果 → 生成最终响应

#### 模型动态选择

```python
def select_model(agent_spec: AgentSpec, task_complexity: str) -> str:
    if agent_spec.model_tier:
        return tier_to_slot[agent_spec.model_tier]
    complexity_map = {
        "reasoning": "enhanced",       # 强模型 slot
        "generation": "enhanced",
        "retrieval": "primary",        # 中等模型 slot
        "data_query": "primary",
        "formatting": "basic",         # 弱模型/模板
    }
    return complexity_map.get(task_complexity, "primary")
```

模型策略表：

| 子 Agent 类型 | 模型选择 | 理由 |
|--------------|---------|------|
| Supervisor（任务分解/路由） | 强模型 | 需要强推理判断任务拆分 |
| Research Agent（文献/知识检索） | 中等模型 + 工具为主 | 主要靠 API 调用，LLM 只做摘要 |
| Writing Agent（内容生成） | 强模型 | 写作质量直接决定输出质量 |
| Data Agent（数据查询/统计） | 弱模型/规则引擎 | SQL 查询不需要强推理 |
| Format Agent（排版/格式化） | 弱模型/模板引擎 | 确定性任务 |
| Review Agent（质检/审校） | 强模型 | 需要批判性思维 |

### 2.4 向后兼容

- 现有 `/api/ai/chat` SSE 端点不变
- Supervisor 判断简单请求 → 退化为现有单 Agent loop
- 复杂请求才触发多 Agent 编排
- 现有 39 个工具、权限模型、敏感度路由全部保留

### 2.5 初始 AgentTeam 预设

| Team | 子 Agents | 共享 State | 触发条件 |
|------|----------|------------|---------|
| edu_data | DataQuery + Analytics + Report | ExamAnalysisState | 考试/学情相关多步分析 |
| knowledge | Search + Curriculum + Concept | KnowledgeState | 知识库/教材相关复杂查询 |
| homework | TaskManager + Grading + Remedial | HomeworkState | 作业批改+补救推荐 |

### 2.6 改动范围

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `ai/supervisor.py` | 新增 | Supervisor Agent 路由 + 汇总 |
| `ai/agent_team.py` | 新增 | AgentTeam 注册 + 共享 State 管理 |
| `ai/agent_spec.py` | 新增 | AgentSpec 声明 + 模型动态选择 |
| `ai/agent_loop.py` | 修改 | 支持作为子 Agent 运行（接受工具子集 + 外部 State） |
| `ai/registry.py` | 修改 | 支持按 Agent 过滤工具子集 |
| `api/ai.py` | 修改 | SSE 端点接入 Supervisor |
| `ai/teams/__init__.py` | 新增 | Team 注册入口 |
| `ai/teams/edu_data.py` | 新增 | 教育数据 Team |
| `ai/teams/knowledge.py` | 新增 | 知识库 Team |
| `ai/teams/homework.py` | 新增 | 作业 Team |

估算：~800 LOC 新增 + ~200 LOC 修改

---

## 3. Phase 2: 跨会话记忆 + 项目状态持久化

### 3.1 三类记忆

| 类型 | 存储什么 | 生命周期 | 示例 |
|------|---------|---------|------|
| Entity Memory | 用户/学生/班级持久画像 | 长期，自动更新 | "张三数学薄弱，函数掌握率 40%" |
| Project State | 多会话任务进度+中间产物 | 项目周期 | "论文已完成文献综述，正在写方法论" |
| Episodic Memory | 历史会话关键决策摘要 | 中期，LRU 淘汰 | "上次用户拒绝了表格格式，偏好图表" |

### 3.2 架构

```
┌──────────────────────────────────────────────┐
│              Memory Layer                     │
├──────────┬──────────┬────────────────────────┤
│ Entity   │ Project  │ Episodic               │
│ Memory   │ State    │ Memory                 │
│          │          │                        │
│ 用户画像  │ 任务进度  │ 历史交互摘要            │
│ 学生轨迹  │ 中间产物  │ 成功/失败经验           │
│ 教师偏好  │ 检查点   │ 工具调用模式            │
├──────────┴──────────┴────────────────────────┤
│         PostgreSQL (JSONB) + Redis Cache      │
└──────────────────────────────────────────────┘
```

### 3.3 数据模型

```python
class EntityMemory(Base):
    __tablename__ = "entity_memory"
    id: Mapped[int]
    entity_type: Mapped[str]       # "student" | "teacher" | "class"
    entity_id: Mapped[str]
    school_id: Mapped[str]         # 数据隔离
    facts: Mapped[dict]            # JSONB，结构化事实
    updated_at: Mapped[datetime]

class ProjectState(Base):
    __tablename__ = "project_state"
    id: Mapped[int]
    project_type: Mapped[str]      # "paper" | "courseware"
    project_id: Mapped[str]
    owner_id: Mapped[str]
    school_id: Mapped[str]
    state: Mapped[dict]            # JSONB，进度+中间产物引用
    checkpoints: Mapped[list]      # 检查点快照列表
    status: Mapped[str]            # "active" | "paused" | "completed"
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

Episodic Memory 不单独建表，作为 Entity Memory 的子集存储（entity_type="session_episode"），通过 LRU 淘汰策略控制总量。

### 3.4 核心组件

#### MemoryExtractor（提取器）

扩展现有 `session_memory.py`：
- 每次会话结束时，LLM 提取：新发现的实体事实 + 项目进度变更 + 关键决策
- 写入 MemoryStore，冲突时用时间戳覆盖旧事实
- Tier 1 LLM 执行提取，Tier 2/3 跳过

#### MemoryInjector（注入器）

- 会话开始时，根据 DataScope 加载相关记忆
- 注入 Supervisor 的 system prompt
- Token 预算：记忆总量不超过 context_window 的 15%

#### 新增工具

```python
@tool_spec(name="memory_read", domain="system", sensitivity="school",
           allowed_roles=["teacher", "academic_director", "principal"])
async def memory_read(input: MemoryQuery, ctx: ToolContext) -> ToolResult:
    """Agent 主动查询历史记忆"""

@tool_spec(name="memory_write", domain="system", sensitivity="school",
           allowed_roles=["teacher", "academic_director", "principal"])
async def memory_write(input: MemoryUpdate, ctx: ToolContext) -> ToolResult:
    """Agent 主动写入记忆"""
```

### 3.5 数据隔离

- Entity Memory 继承现有 DataScope——教师只能读自己班级学生画像
- Project State 按 owner_id + school_id 隔离
- 三层权限模型自动覆盖（memory_read/write 注册时声明 capability）

### 3.6 改动范围

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `models/memory.py` | 新增 | 2 张表 + Alembic migration |
| `ai/memory_store.py` | 新增 | CRUD + 冲突合并 |
| `ai/memory_extractor.py` | 重写 | 替换现有 session_memory.py |
| `ai/memory_injector.py` | 新增 | 会话启动时加载 |
| `ai/tools/system_tools.py` | 新增 | memory_read / memory_write |
| `ai/supervisor.py` | 修改 | 注入记忆上下文 |

估算：~600 LOC 新增

---

## 4. Phase 3: 课件生成 + 论文写作 Agent 团队

### 4.1 paper-skill 合入策略

| paper-skill 组件 | 合入方式 | 目标位置 |
|-----------------|---------|---------|
| search_literature() | 工具迁入 | ai/tools/paper_tools.py |
| search_chinese_literature() | 工具迁入 | ai/tools/paper_tools.py |
| format_citation() | 工具迁入 | ai/tools/paper_tools.py |
| generate_outline() | AgentTeam 编排 | ai/teams/paper_writing.py |
| write_section() | SubAgent 逻辑 | ai/teams/paper_writing.py |
| quality_gate() | 工具迁入 | ai/tools/paper_tools.py |
| knowledge-base MCP | 保留 MCP 连接 | Agent 通过工具调用 |

原则：纯函数逻辑变工具，编排逻辑变 AgentTeam，MCP 连接保留。

### 4.2 论文写作 Team

```
┌─────────────── PaperWritingTeam ─────────────────┐
│  SharedState: PaperState                          │
│  execution: sequential (阶段间) + parallel (阶段内)│
│                                                    │
│  Stage 1: ResearchAgent (中等模型)                 │
│    tools: search_literature, search_chinese_lit,   │
│           knowledge_base_query, memory_read         │
│    输出 → PaperState.literature_review              │
│                                                    │
│  Stage 2: OutlineAgent (强模型)                    │
│    tools: memory_read                              │
│    输入 ← PaperState.literature_review              │
│    输出 → PaperState.outline                        │
│    checkpoint: 用户确认大纲后继续                    │
│                                                    │
│  Stage 3: WritingAgent x N (强模型, 可并行)         │
│    tools: search_literature, format_citation        │
│    每个实例负责一个章节                              │
│    输出 → PaperState.sections[i]                    │
│                                                    │
│  Stage 4: ReviewAgent (强模型)                     │
│    tools: quality_gate (6维度检测)                  │
│    输入 ← PaperState.sections                       │
│    输出 → PaperState.review_findings                │
│    FAIL → 回退到 Stage 3 修改对应章节               │
│                                                    │
│  Stage 5: FormatAgent (弱模型/模板)                 │
│    tools: format_citation, generate_bibliography    │
│    GB/T 7714 引用格式化 + 全文排版                   │
│    输出 → PaperState.final_document                 │
└────────────────────────────────────────────────────┘
```

#### PaperState

```python
@dataclass
class PaperState:
    topic: str
    requirements: dict              # 字数/格式/引用风格
    literature_review: list[dict]   # 文献摘要列表
    outline: dict                   # 章节结构
    sections: dict[str, str]        # chapter_id → 内容
    review_findings: list[dict]     # 质检结果
    final_document: str | None      # 最终输出
    citations: list[dict]           # 引用列表
    checkpoint: str                 # 当前阶段（跨会话恢复用）
```

### 4.3 课件生成 Team

```
┌─────────────── CoursewareTeam ───────────────────┐
│  SharedState: CoursewareState                      │
│  execution: sequential + parallel                  │
│                                                    │
│  Stage 1: CurriculumAgent (中等模型)               │
│    tools: curriculum_search, textbook_query,        │
│           knowledge_tree, gaokao_index              │
│    输入: 学科+年级+单元                              │
│    输出 → CoursewareState.knowledge_map              │
│                                                    │
│  Stage 2: DesignAgent (强模型)                     │
│    tools: memory_read (教师偏好)                    │
│    输出 → CoursewareState.slide_outline              │
│    checkpoint: 用户确认结构                          │
│                                                    │
│  Stage 3: ContentAgent x N (强模型, 并行)           │
│    每个实例生成一页/一节                             │
│    tools: knowledge_base_query, search_literature   │
│    输出 → CoursewareState.slides[i]                  │
│                                                    │
│  Stage 4: ExerciseAgent (中等模型)                  │
│    tools: question_bank_search, error_patterns      │
│    根据知识点薄弱数据生成针对性练习                    │
│    输入 ← Entity Memory (班级学情)                   │
│    输出 → CoursewareState.exercises                  │
│                                                    │
│  Stage 5: FormatAgent (模板引擎)                    │
│    Markdown / PPTX / PDF 输出                       │
│    输出 → CoursewareState.final_file                 │
└────────────────────────────────────────────────────┘
```

课件独特价值：Stage 4 ExerciseAgent 利用 edu-cloud 已有学情数据（考试分析/错题本/知识掌握度），生成针对本班学生薄弱点的课堂练习。通用课件工具无此能力。

### 4.4 Checkpoint 机制

长链条任务在关键节点暂停等用户确认：

```
用户: "帮我写一篇关于深度学习在教育中应用的论文"
Agent: [Stage 1 完成] 找到 23 篇相关文献...
Agent: [Stage 2 输出大纲] 建议结构：1.引言 2.文献综述 3.方法论 4.案例分析 5.结论
       确认这个大纲吗？可以调整。
用户: "第三章改成'技术框架'，加一章'实验结果'"
Agent: [Stage 3 并行写作 → Stage 4 质检 → Stage 5 排版]
Agent: 初稿完成。质检：引用格式 ✅ / 逻辑连贯 ✅ /
       原创度 ⚠ 第4章与文献3重复度偏高。要修改吗？
```

Checkpoint 与 Phase 2 的 ProjectState 联动——用户中断后下次会话自动恢复到 checkpoint 位置。

### 4.5 新增工具

| 工具 | 来源 | 归属 Agent |
|------|------|-----------|
| search_literature | paper-skill 迁入 | ResearchAgent |
| search_chinese_literature | paper-skill 迁入 | ResearchAgent |
| format_citation | paper-skill 迁入 | FormatAgent |
| generate_bibliography | paper-skill 迁入 | FormatAgent |
| quality_gate | paper-skill 迁入 | ReviewAgent |
| generate_slide_content | 新增 | ContentAgent |
| export_pptx | 新增 | FormatAgent |
| export_pdf | 新增 | FormatAgent |
| question_bank_search | 新增（复用已有 error_book 工具扩展） | ExerciseAgent |

### 4.6 改动范围

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `ai/teams/paper_writing.py` | 新增 | PaperWritingTeam + PaperState |
| `ai/teams/courseware.py` | 新增 | CoursewareTeam + CoursewareState |
| `ai/tools/paper_tools.py` | 新增 | 从 paper-skill 迁入 5 个工具 |
| `ai/tools/courseware_tools.py` | 新增 | 3 个新工具 |
| `ai/supervisor.py` | 修改 | 注册 2 个新 Team |
| `ai/agent_team.py` | 修改 | checkpoint 暂停/恢复逻辑 |

估算：~1200 LOC 新增

---

## 5. Phase 4: 工作流 LLM 化 + 评估基准

### 5.1 工作流 LLM 化

#### 改造目标

| 工作流 | 当前 | 升级后 | 价值 |
|--------|------|--------|------|
| W1 考后分析 | SQL 统计 → 模板 | + LLM 解读异常 + 自动归因 | "全班第15题正确率12%，可能原因：该知识点课堂讲解不足" |
| W3 学生画像 | 成绩聚合 → 掌握率 | + LLM 个性化学习建议 | "建议张三优先复习函数图像，参考教材P120例题" |
| W6 巡检 | 异常检测 → Finding | + LLM 严重程度 + 处置建议 | "发现3班数学成绩连续3次下滑，建议班主任关注" |
| W2 备考指南 | 缺失 | 新增：LLM 分析考点 + 复习策略 | 结合知识库 + 考试数据 |
| W4 错题分析 | 缺失 | 新增：LLM 归类错误模式 + 推荐练习 | 结合错题本 + 知识图谱 |
| W5 教学洞察 | 缺失 | 新增：LLM 跨班对比 + 教学建议 | 结合多班数据 + 课标 |

#### Step 类型扩展

```python
@dataclass
class StepDefinition:
    name: str
    func: StepFunc
    step_type: str             # "sql" | "llm" | "hybrid"
    model_tier: int | None     # llm/hybrid step 的模型等级
    compensate: StepFunc | None
```

- `sql` step：现有行为不变
- `llm` step：调用 SubAgent 做推理
- `hybrid` step：先 SQL 取数据，再 LLM 解读

工作流是后台批处理，不需要实时响应，统一用中等模型（成本低，延迟不敏感）。

### 5.2 评估基准

#### 三层评估

```
L1: 工具选择准确率 (Tool Selection)
    给定用户请求，Agent 选了正确的工具吗？
    指标: precision / recall / F1
    数据: 100+ 请求→工具 标注对

L2: 任务完成率 (Task Completion)
    多步骤任务，最终结果正确吗？
    指标: 完成率 / 步骤效率 / 回退次数
    数据: 50+ 场景（考试分析/论文/课件）

L3: 输出质量 (Output Quality)
    生成的报告/论文/课件质量如何？
    指标: LLM-as-Judge 5维评分
    数据: 30+ 产物 + 人工标注基线
```

#### 目录结构

```
tests/benchmark/
├── fixtures/
│   ├── tool_selection.jsonl        # {"query": "...", "expected_tools": [...]}
│   ├── task_scenarios.jsonl        # {"goal": "...", "expected_steps": [...]}
│   └── quality_baselines.jsonl     # {"input": "...", "reference_output": "..."}
├── bench_tool_selection.py         # L1
├── bench_task_completion.py        # L2
├── bench_output_quality.py         # L3
└── report.py                       # 汇总 → benchmark_report.md
```

#### 评估节奏与目标

- 每个 Phase 交付后跑一次全量 benchmark
- L1 目标：工具选择 F1 > 0.90
- L2 目标：多步任务完成率 > 0.80
- L3 目标：输出质量 LLM-Judge 平均 > 4.0/5.0

### 5.3 改动范围

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `workflow/registry.py` | 修改 | StepDefinition 增加 step_type / model_tier |
| `workflow/llm_step.py` | 新增 | LLM step 执行器 |
| `workflow/w1_post_exam.py` | 修改 | 关键 step 升级为 hybrid |
| `workflow/w3_student_profile.py` | 修改 | 建议生成升级为 llm |
| `workflow/w6_patrol.py` | 修改 | 严重程度判断升级为 llm |
| `workflow/w2_exam_prep.py` | 新增 | 备考指南工作流 |
| `workflow/w4_error_analysis.py` | 新增 | 错题分析工作流 |
| `workflow/w5_teaching_insights.py` | 新增 | 教学洞察工作流 |
| `tests/benchmark/` | 新增 | 3 层评估框架 |

估算：~1000 LOC 新增

---

## 6. 总览

| Phase | 核心交付 | 依赖 | 估算规模 |
|-------|---------|------|---------|
| 1. 多 Agent 编排 | Supervisor + AgentTeam + 动态模型选择 | 无 | ~800 LOC 新增 + ~200 LOC 修改 |
| 2. 跨会话记忆 | 3 类记忆 + 2 张表 + 提取/注入 + 2 工具 | Phase 1 | ~600 LOC 新增 |
| 3. 论文 + 课件 Team | 2 AgentTeam + paper-skill 迁入 + 9 工具 | Phase 1+2 | ~1200 LOC 新增 |
| 4. 工作流 LLM 化 + 评估 | 6 工作流升级/新增 + 3 层 benchmark | Phase 1 | ~1000 LOC 新增 |

总计：~3600 LOC 新增 + ~200 LOC 修改

### 关键设计决策

1. **向后兼容**：简单请求退化为现有单 Agent loop，零破坏性
2. **混合通信**：组内共享状态（简洁）+ 组间消息传递（解耦）
3. **动态模型选择**：按任务复杂度选模型，平衡质量和成本
4. **数据隔离延续**：记忆层继承 DataScope 三层权限，不开新口子
5. **渐进交付**：4 Phase 独立可用，每个 Phase 交付后系统即可运行
