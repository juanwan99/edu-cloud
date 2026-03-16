# AI Agent 层设计文档

> snapshot: 2026-03-16
> 状态: 设计中
> 适用范围: exam-ai（Phase 1-2 嵌入）→ 独立服务（Phase 3+）

## §0 决策摘要

| 决策 | 选项 | 理由 |
|------|------|------|
| Agent 架构 | 自研 ReAct Loop | 教育查询 3-8 步，不需要 DAG；零依赖；与现有 httpx+FastAPI 无缝衔接 |
| 框架选型 | 不用 LangChain/LangGraph | 减少依赖面，教育查询模式规律性强 |
| 部署形态 | Phase 1-2 嵌入 exam-ai，Phase 3 拆为独立服务 | 1-2 所学校时零额外运维 |
| 权限模型 | JWT 转发 + API 层 RBAC 强制 | AI 权限 = 提问者权限，由后端 API 执行而非 prompt 约束 |
| 读写策略 | V1 只读；写操作走"意图+人工确认" | 成绩数据神圣性极高，AI 幻觉导致改分是灾难 |
| LLM 选型 | V1 强制国内模型，架构支持切换 | 避免数据出境合规负担 |
| 数据脱敏 | Anonymizer 层（张三→S001）| 学生数据不进入 LLM 上下文 |
| 审计 | 全链路 append-only 审计 + JSONL 双写 | 可重现 AI 推理过程 |

## §1 系统定位

**AI Agent 不是"附加功能"，是平台的核心交互范式。**

用户（教师/校长/教育局）通过自然语言与 AI 对话，AI 自主规划分析路径、调用工具查询数据、多步推理后输出深度分析报告和决策建议。

```
用户（自然语言提问）
    ↓
AI Agent（ReAct Loop）
    ├── 理解意图
    ├── 检查权限（继承用户 RBAC）
    ├── 规划分析路径
    ├── 调用工具链（并行/串行）
    ├── 多步推理 + 交叉验证
    └── 输出：结构化分析 + 决策建议 + 数据引用
```

类比：Claude Code 能自主读文件、搜索、执行命令——本系统的 AI 能自主查成绩、对比班级、分析趋势、输出报告。

## §2 Agent 内部架构

### 2.1 ReAct Loop

```python
class AgentLoop:
    """Reasoning + Acting 交替执行"""

    async def run(self, user_message, user, session_id) -> AsyncIterator[AgentEvent]:
        self.ctx.add_user_message(user_message, session_id)

        for step in range(MAX_STEPS):  # 硬性上限 15 步
            messages = self.ctx.build_messages(session_id)
            tools_schema = self.tools.get_schemas_for_user(user)

            response = await self.llm.chat(messages, tools=tools_schema)

            if response.is_final_answer:
                yield AgentEvent(type="answer", content=response.text)
                return

            # 支持并行：LLM 一次返回多个 tool_call
            tool_results = await asyncio.gather(*[
                self._execute_tool(tc, user) for tc in response.tool_calls
            ])

            for tc, result in zip(response.tool_calls, tool_results):
                yield AgentEvent(type="tool_result", tool=tc.name, data=result)
                self.ctx.add_tool_result(tc, result, session_id)
```

为什么 ReAct 而非 Plan-then-Execute：教育分析中用户问题模糊（"三班数学怎么样"），需要边探索数据边调整方向。ReAct 的"思考-行动-观察"循环天然适配。

### 2.2 上下文管理

三层上下文：

| 层 | 内容 | 生命周期 | 存储 |
|---|------|---------|------|
| System | 角色定义 + 教育领域知识 + 学校元数据 + 输出要求 | 不变 | 代码 |
| Session | 本次对话消息历史 + 工具调用结果 | 会话级（TTL 2h） | Redis |
| Working | 中间计算结果缓存 | 步骤级 | 内存 |

Token 预算：总 token < 模型上下文的 70%（留 30% 给输出）。超出时先砍最早的工具结果（保留摘要），再砍早期对话轮次。

### 2.3 System Prompt 结构

```
[角色定义]
你是{school_name}的教学分析助手。

[权限边界——动态注入]
当前用户：{display_name}，角色：{role}
可见科目：{visible_subjects or "全部"}
可见班级：{visible_classes or "全部"}

[学校上下文——动态注入]
{class_count} 个班级，{student_count} 名学生
最近考试：{recent_exams_summary}

[教育统计知识]
得分率 > 0.7: 较容易；0.4-0.7: 适中；< 0.4: 较难
区分度 > 0.3: 良好；0.2-0.3: 一般；< 0.2: 差
班级均分差异 > 10%: 显著
标准差/均分 > 0.3: 分化严重

[因果分析框架]
成绩出现显著变化时按以下维度排查：
1. 命题因素：本次难度/区分度与历次对比
2. 题目因素：哪些题得分率异常低
3. 班级因素：个别班级还是全年级
4. 学生因素：整体下滑还是个别拖后腿
注意：只提供数据层面分析，教学方法等信息提示用户结合实际判断。

[输出要求]
- 中文回答
- 数据结论必须附具体数字
- 对比分析先结论后展开
- 不确定时明确标注 [UNCERTAIN]
- 不编造数据
```

## §3 工具体系

### 3.1 三层架构

```
Layer 3: 高阶分析工具（预制分析流程，AI 可选用）
Layer 2: 业务查询工具（中粒度，AI 的主力工具集）
Layer 1: 数据原语（工具内部用，不暴露给 LLM）
```

Layer 2 是核心——每个工具名就是业务语义（LLM 看到 `get_score_distribution` 就知道用途），参数少（2-4 个），返回结构化数据。

### 3.2 工具清单（Phase 1: 15 个）

**成绩与分析域（8 个）**

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_exam_summary` | exam_id | 各科平均/最高/最低/得分率 |
| `get_score_distribution` | exam_id, ?subject_id, ?class_id | 分数段分布 |
| `get_question_analysis` | subject_id | 每题得分率/区分度 |
| `get_student_scores` | exam_id, student_id | 该生各科各题详细分数 |
| `get_class_scores` | exam_id, class_id, ?subject_id | 该班学生成绩列表 |
| `compare_classes` | exam_id, class_ids[], ?subject_id | 多班对比 |
| `rank_students` | exam_id, ?subject_id, ?class_id, top_n | 排名表 |
| `get_grade_aggregates` | exam_id, ?subject_id | 年级聚合统计（不含个体，供班级定位） |

**学生与班级域（4 个）**

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_class_list` | ?grade | 班级列表 |
| `get_class_roster` | class_id | 学生名单 |
| `search_students` | query_string | 模糊搜索 |
| `get_student_profile` | student_id | 学生信息 + 历次概要 |

**考试域（3 个）**

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_exam_list` | ?status | 考试列表 |
| `get_exam_detail` | exam_id | 考试详情 |
| `get_subject_questions` | subject_id | 题目列表 |

Phase 2 追加：`compare_exams`、`get_score_change`、`render_chart`、`generate_pdf_report`、`create_data_table`（+10 个）。

### 3.3 工具注册机制

```python
@ToolRegistry.register(
    name="get_score_distribution",
    description="获取某次考试的成绩分布。可按科目和班级过滤。",
    category="analytics",
)
async def get_score_distribution(
    exam_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    _school_id: str = "",              # 框架注入，不暴露给 LLM
    _visible_classes: list | None = None,  # 框架注入
) -> dict:
    ...
```

新模块只需在 `tools.py` 中用装饰器注册，启动时自动扫描。

### 3.4 权限在工具层的执行

每次工具调用，Agent 框架自动注入用户权限上下文：

```python
async def _execute_tool(self, tool_call, user):
    tool = self.tools.get(tool_call.name)
    return await tool.execute(
        **tool_call.arguments,
        _school_id=user.school_id,
        _visible_classes=get_visible_class_ids(user),
        _visible_subjects=get_visible_subject_codes(user),
    )
```

工具内部用这些参数过滤数据。AI 永远只能拿到用户有权看到的数据。

## §4 权限与安全架构

### 4.1 权限继承链

```
用户 JWT（含 role, school_id, class_ids, subject_code）
    ↓
AI Agent 验证 JWT，提取用户身份
    ↓
每次工具调用注入用户权限
    ↓
工具内部用 school_id + visible_classes + visible_subjects 过滤数据
    ↓
AI 只能拿到该用户有权看到的数据
```

Phase 1（嵌入 exam-ai）：直接复用 `get_current_user` + `permissions.py`，无需额外 token 机制。

Phase 3（独立服务）：引入 Scoped Delegation Token：
- AI Agent 生成短 TTL（5min）的代理 token
- 携带原始用户身份 + `scope: read-only` + `iss: ai-agent`
- exam-ai 识别代理 token 并强制只读

### 4.2 聚合降级

教师问"我班在年级的位置"时，AI 不能拉全年级数据再自己聚合（数据已泄露到 LLM 上下文）。

**方案：exam-ai 新增 `get_grade_aggregates` 端点**，返回年级聚合统计（均分/中位/百分位）+ 本班排名，不含其他班个体数据。

**k-匿名性约束**：聚合组最小 5 人，低于阈值不返回该组统计（防反推个体）。

### 4.3 数据脱敏（Anonymizer）

```
exam-ai API 返回数据（含真实姓名）
    ↓
Anonymizer: "张三" → "S001"，映射表存在内存中
    ↓
发给 LLM（prompt 中只有 S001）
    ↓
LLM 返回引用 S001
    ↓
Deanonymizer: "S001" → "张三"
    ↓
返回给前端用户
```

- 映射表与会话绑定，会话结束即销毁
- 不持久化，不落盘
- 学号永远不发送给 LLM

### 4.4 行为约束

| 约束 | 实现 |
|------|------|
| V1 只读 | 工具全部是查询类；如果未来加写操作，走"意图+确认"模式 |
| 幻觉防护 | 数据来源标注（citation）+ 数值交叉校验 + [UNCERTAIN] 标注 |
| 速率限制 | 10 次/分钟/用户，200 次/天/用户，单次会话最多 20 次 API 调用 |
| 成本控制 | Token 配额：学校 200 万/月，用户 5 万/天；超额降级到轻量模型 |

### 4.5 审计追踪

每次 AI 交互记录完整调用链：

```json
{
    "conversation_id": "conv-123",
    "steps": [
        {"type": "user_query", "content": "我班数学在年级什么水平？"},
        {"type": "tool_call", "tool": "get_class_scores", "params": {...}},
        {"type": "tool_call", "tool": "get_grade_aggregates", "params": {...}},
        {"type": "llm_call", "model": "qwen-max", "tokens": 2500},
        {"type": "response", "preview": "你班数学均分 78.5，年级排第 3..."}
    ]
}
```

存储：PostgreSQL append-only 表 + JSONL 文件双写。保留 3 年。

## §5 LLM 配置

```python
class AISettings(BaseSettings):
    AI_PROVIDER: str = "domestic_api"     # domestic_api | local | foreign_api
    AI_DOMESTIC_URL: str = ""             # 通义千问/文心/智谱
    AI_DOMESTIC_KEY: str = ""
    AI_DOMESTIC_MODEL: str = "qwen-max"
    AI_LOCAL_URL: str = ""                # Ollama/vLLM
    AI_LOCAL_MODEL: str = ""
    AI_ALLOW_FOREIGN: bool = False        # 安全开关，默认关
    AI_MAX_STEPS: int = 15               # Agent 最大步数
    AI_SESSION_TTL: int = 7200           # 会话超时（秒）
```

降级链：主力模型 → 轻量模型 → 规则引擎（不依赖 LLM，覆盖 60% 简单查询）。

## §6 输出能力

| 输出类型 | 实现 | Phase |
|---------|------|-------|
| 结构化文本 | Markdown | 1 |
| 数据表格 | JSON → 前端 DataTable | 1 |
| 统计图表 | ECharts option JSON → 前端 vue-echarts | 2 |
| PDF 报告 | Playwright HTML→PDF（复用答题卡路径） | 2 |
| 站内通知 | Notification 模型 + 前端轮询 | 2 |
| 系统配置变更 | "意图+人工确认"模式 | 3 |

人工确认分级：
- L0 自动：只读查询、文本/图表输出
- L1 通知：自动生成报告，推送通知
- L2 确认：批量操作（弹窗确认）
- L3 审批：配置变更（管理员审批）

## §7 主动性设计（Phase 2）

事件驱动：考试完成等事件触发 AI 自动分析。

| 触发事件 | 主动行为 | 输出 | 需确认? |
|---------|---------|------|---------|
| exam_finalized | 成绩异常检测 | 通知科目负责人 | 否 |
| exam_finalized | 自动分析报告 | PDF 报告 | 否 |
| grading_completed | 阅卷置信度预警 | 通知阅卷教师 | 否 |
| exam_finalized | 薄弱知识点发现 | 推送给科目教师 | 否 |

**边界原则：主动行为只允许"只读+通知"，不允许自动修改数据。**

## §8 前端集成

Phase 1：exam-ai-frontend 新增侧边栏聊天面板。

- 新增 `ChatPanel.vue` 组件 + `useAIChat` pinia store
- SSE 流式响应（`/api/ai/chat` 端点）
- 支持 Markdown 渲染 + 数据表格
- AI 不可用时自动灰色（先 health check）

技术栈复用：Vue 3 + NaiveUI + vue-echarts + pinia（已有）。

## §9 合规要点

| 要求 | 实现 |
|------|------|
| V1 强制国内 LLM | `AI_ALLOW_FOREIGN = False` |
| 学生数据脱敏 | Anonymizer 层，真实姓名不进 LLM 上下文 |
| 知情同意 | `School.ai_consent_confirmed_at` 字段，未确认则 AI 不可用 |
| 被遗忘权 | 用户可删除全部 AI 对话记录 |
| 数据最小化 | 每个工具返回最小必要数据集（聚合端点而非原始数据） |
| k-匿名性 | 聚合组 < 5 人时不返回该组统计 |

## §10 演进路线

### Phase 1: 对话式查询助手（嵌入 exam-ai）

- ReAct Agent Loop
- 15 个只读查询工具
- JWT 权限继承 + API 层 RBAC
- Anonymizer 脱敏
- 全链路审计
- 前端聊天面板
- **前置**：exam-ai 修复 analytics class_ids 过滤 + 端到端流程跑通 + 至少 1 次完整考试数据

### Phase 2: 主动分析 + 可视化

- EventBus（Redis Pub/Sub）
- 事件驱动主动分析
- ECharts 图表 + PDF 报告
- Token 配额管理
- +10 个工具（对比域 + 输出域）
- **前置**：Phase 1 上线 + 至少 2 次考试数据

### Phase 3: 知识图谱 + 独立服务

- AI Agent 拆为独立服务（port 8002）
- Scoped Delegation Token
- 知识点标签 + RAG
- 学生学习画像
- 本地 LLM 部署支持
- **前置**：知识点标注数据

### Phase 4: 自适应 + 跨校

- 接入 edu-cloud 跨校数据
- 联考对比分析
- 阅卷参数自动调优
- 教学建议生成
- **前置**：edu-cloud 上线 + 一学期数据积累

## §11 API 设计（Phase 1）

```
POST /api/ai/chat              # 对话（SSE 流式）
GET  /api/ai/sessions          # 会话列表
GET  /api/ai/sessions/{id}     # 会话详情
DELETE /api/ai/sessions/{id}   # 删除会话（被遗忘权）
GET  /api/ai/health            # AI 服务健康检查
```

## §12 文件结构（Phase 1，嵌入 exam-ai）

```
src/exam_ai/agent/
    __init__.py
    loop.py              # ReAct Agent Loop
    context.py           # 三层上下文管理
    anonymizer.py        # 数据脱敏/反脱敏
    llm.py               # 通用 LLM chat 客户端（区别于 grading 用的）
    schemas.py           # AgentEvent, ToolCallResult 等
    audit.py             # 审计日志记录
    tools/
        __init__.py      # ToolRegistry
        analytics.py     # 成绩分析工具（8 个）
        students.py      # 学生班级工具（4 个）
        exams.py         # 考试管理工具（3 个）

src/exam_ai/api/
    ai.py                # /api/ai/* 路由

前端：
    src/components/ChatPanel.vue
    src/stores/aiChat.js
```

## §13 前置修复项（Phase 1 开始前）

| 项 | 说明 | 级别 |
|----|------|------|
| analytics.py class_ids 过滤 | teacher 角色能看全校成绩，AI 会放大此漏洞 | T2 |
| exam-ai + paper-seg 端到端打通 | AI 分析需要真实考试数据 | T3（另一窗口在做） |
| 至少 1 次完整考试数据 | AI 查询助手没数据等于空壳 | 运营 |
