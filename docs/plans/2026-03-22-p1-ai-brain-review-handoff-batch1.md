[edu-cloud] Executor→Reviewer | 2026-03-22 09:39:53
## 审查交接单: Task 1-7
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-22-p1-ai-brain-plan.md

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | AI schemas + LLM client + config | commit b2d9936 | ✅ | — |
| T2 | 工具注册表 registry.py | commit bba413e | ✅ | — |
| T3 | L1 校本分析工具 (4个) | commit 9621e04 | ✅ | — |
| T4 | 匿名化器 + 上下文构建 | commit d60a3d8 | ✅ | — |
| T5 | ReAct 循环引擎 agent.py | commit 8895bef | 🔀 | 修复了 registry.py get_schemas(categories=[]) 的 bug：空列表是 falsy，需用 `is not None` 判断 |
| T6 | AI SSE API + 审计模型 | commit 37d9161 | ✅ | 未安装 sse-starlette，直接用 StreamingResponse 即可 |
| T7 | AI 对话前端 ChatPanel | commit 2a10fd3 | ✅ | — |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 |
|---------------|------------------|---------|---------|
| schemas 序列化 | test_schemas::test_chat_message_creation | `python -m pytest tests/test_ai/test_schemas.py -v` | 4 PASSED |
| 工具注册+发现+执行 | test_registry::test_execute_tool | `python -m pytest tests/test_ai/test_registry.py -v` | 6 PASSED |
| 成绩查询+scope过滤 | test_tools_analytics::test_get_exam_scores_with_class_filter | `python -m pytest tests/test_ai/test_tools_analytics.py -v` | 7 PASSED |
| 匿名化双向映射 | test_anonymizer::test_anonymize_names + test_deanonymize | `python -m pytest tests/test_ai/test_anonymizer.py -v` | 4 PASSED |
| 上下文含角色/scope/工具 | test_context::test_system_prompt_contains_role | `python -m pytest tests/test_ai/test_context.py -v` | 2 PASSED |
| ReAct直接回答 | test_agent::test_agent_direct_answer | `python -m pytest tests/test_ai/test_agent.py -v` | 7 PASSED |
| ReAct工具调用后回答 | test_agent::test_agent_tool_call | (同上) | PASSED |
| max_steps保护 | test_agent::test_agent_max_steps | (同上) | PASSED |
| AI健康检查 | test_ai_api::test_ai_health | `python -m pytest tests/test_ai/test_ai_api.py -v` | 5 PASSED |
| AI认证守卫 | test_ai_api::test_ai_chat_requires_auth | (同上) | PASSED |

### 验证清单自检

**T1 — AI schemas + LLM client**
- ✅ ChatMessage/ToolCall/AgentEvent 数据类完整
- ✅ LLM 客户端发送 OpenAI 兼容格式到 llm-proxy
- ✅ tool_calls 解析支持 string 和 dict 两种 arguments 格式
- ✅ config 默认指向 llm-proxy localhost:8100

**T2 — 工具注册表**
- ✅ @register 装饰器注册工具元数据
- ✅ get_schemas 返回 OpenAI function calling 格式
- ✅ categories 过滤正确（含空列表→空结果修复）
- ✅ execute 自动注入 _前缀参数

**T3 — L1 工具**
- ✅ 4 个工具全部注册到全局 registry
- ✅ _class_ids scope 过滤实现
- ✅ 空结果返回合理默认值
- ✅ student_number 不存在返回 error

**T4 — 匿名化 + 上下文**
- ✅ 匿名化支持 str/dict/list 递归
- ✅ 还原时长 ID 优先
- ✅ system prompt 含角色/scope/工具

**T5 — ReAct 引擎**
- ✅ 角色→工具 category 映射
- ✅ 未知角色默认空工具集
- ✅ max_steps 防止无限循环
- ✅ 工具执行异常捕获
- ✅ 匿名化集成：工具结果匿名化→LLM；最终回答反匿名化→前端

**T6 — AI SSE API**
- ✅ POST /ai/chat 返回 SSE 流
- ✅ 需要 USE_AI_CHAT 权限
- ✅ scope 从 current_role 提取
- ✅ AiSession/AiToolCall 审计模型

**T7 — AI 对话前端**
- ✅ SSE 流解析 (data: 前缀)
- ✅ 工具调用标签显示
- ✅ Markdown 基本渲染 (XSS 转义)
- ✅ 自动滚动到底部
- ✅ 流式期间禁用发送

### 自查（四要素格式）

- 工具注册表空 categories 隔离：
  构造输入: `registry.get_schemas(categories=[])`
  运行命令: `python -m pytest tests/test_ai/test_agent.py::test_agent_unknown_role_no_tools -v`
  实际输出:
  ```
  PASSED — 未知角色获得空工具集
  ```
  结论: 空列表正确返回零工具

- AI API 认证守卫：
  构造输入: 无 token 的 POST /api/v1/ai/chat
  运行命令: `python -m pytest tests/test_ai/test_ai_api.py::test_ai_chat_requires_auth -v`
  实际输出:
  ```
  PASSED — 返回 401/403
  ```
  结论: 权限检查生效

- 学生不存在时工具返回错误：
  构造输入: `get_student_profile(student_number="NONEXIST")`
  运行命令: `python -m pytest tests/test_ai/test_tools_analytics.py::test_get_student_profile_not_found -v`
  实际输出:
  ```
  PASSED — 返回 {"error": "学生 NONEXIST 不存在"}
  ```
  结论: 不存在的学生正确返回错误而非崩溃

### 统计

- **变更规模**: 26 files changed, 1453 insertions, 25 deletions
- **测试**: 94 → 129 (+35)
- **Commits**: bba413e..2a10fd3 (7 commits)

使用 codex-review skill 进行 GPT 代码审查。
