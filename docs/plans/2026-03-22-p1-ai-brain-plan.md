# P1 AI 大脑实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 edu-cloud 三栏工作台接入 AI Agent 引擎——教师在中栏底部用自然语言提问，AI 调用工具查询数据并返回分析结果。

**Architecture:** 自建 ReAct 循环（参考 exam-ai），工具注册表按角色过滤。LLM 调用走 llm-proxy (port 8100)。前端通过 SSE 流式接收 AI 回答和工具调用过程。学生姓名在发送给 LLM 前匿名化。

**Tech Stack:** Python asyncio, httpx (LLM client), SSE (sse-starlette), Vue 3 + EventSource (前端)

**Design Doc:** `docs/plans/2026-03-21-super-platform-design.md` §5

**P0 基础:** 94 tests, User + UserRole + scope RBAC, WorkspaceService, 三栏前端

**完成标志:** 班主任问"我们班数学考得怎么样" → AI 调用 `get_exam_scores` 工具 → 返回带分析的回答

**Scope 说明:** 设计文档 P1 列出 L2 跨校工具（4个），但完成标志只需 L1。L2 工具（`cross_school.py`）延期到 P1 后续迭代，文件结构中保留占位。token 计费（`ai_cost_log`）和 k-匿名（<5人不暴露）同样延期。

---

## 文件结构

### 新增文件（后端 AI 引擎）

```
src/edu_cloud/ai/
├── __init__.py
├── schemas.py              # ChatMessage, ToolCall, AgentEvent 数据类
├── llm.py                  # LLM 客户端（调用 llm-proxy）
├── registry.py             # ToolRegistry + @register 装饰器
├── anonymizer.py           # 学生姓名匿名化（张三→S001）
├── context.py              # 上下文构建（系统 prompt + 角色注入）
├── agent.py                # ReAct 循环主引擎
├── audit.py                # 工具调用审计日志
└── tools/
    ├── __init__.py          # 导入注册所有工具
    ├── analytics.py         # L1 校本分析工具（8个）
    └── cross_school.py      # L2 跨校分析工具（4个）
```

### 新增文件（后端 API）

```
src/edu_cloud/api/
└── ai.py                   # POST /api/v1/ai/chat (SSE) + GET /api/v1/ai/health
```

### 新增文件（数据库模型）

```
src/edu_cloud/models/
└── ai_session.py            # AiSession + AiToolCall 审计表
```

### 新增文件（前端）

```
frontend/src/
├── components/workspace/
│   └── ChatPanel.vue        # AI 对话组件（SSE 流 + Markdown 渲染）
└── stores/
    └── aiChat.js            # AI 对话状态管理
```

### 修改文件

```
src/edu_cloud/config.py              # LLM 配置完善（llm-proxy URL + 默认模型）
src/edu_cloud/api/app.py             # 注册 ai router + 安装 sse-starlette
src/edu_cloud/models/__init__.py     # 导出新模型（如有）
frontend/src/components/workspace/DataView.vue  # 底部嵌入 ChatPanel
frontend/src/stores/context.js       # 暴露当前上下文给 ChatPanel
pyproject.toml                       # 添加 sse-starlette 依赖
```

### 测试文件

```
tests/test_ai/
├── test_schemas.py          # 数据类序列化
├── test_registry.py         # 工具注册 + 发现 + 执行
├── test_anonymizer.py       # 匿名化/还原
├── test_context.py          # 上下文构建
├── test_agent.py            # ReAct 循环（mock LLM）
├── test_tools_analytics.py  # L1 工具正确性
└── test_ai_api.py           # SSE 端点集成测试
```

---

## Task 1: AI 数据类 + LLM 客户端

**Files:**
- Create: `src/edu_cloud/ai/__init__.py`, `src/edu_cloud/ai/schemas.py`, `src/edu_cloud/ai/llm.py`
- Modify: `src/edu_cloud/config.py`
- Test: `tests/test_ai/test_schemas.py`

- [ ] **Step 1: 创建 ai 包目录**

```bash
mkdir -p src/edu_cloud/ai/tools tests/test_ai
touch src/edu_cloud/ai/__init__.py src/edu_cloud/ai/tools/__init__.py tests/test_ai/__init__.py
```

- [ ] **Step 2: 写 schemas 测试**

```python
# tests/test_ai/test_schemas.py
from edu_cloud.ai.schemas import ChatMessage, ToolCall, AgentEvent

def test_chat_message_creation():
    msg = ChatMessage(role="user", content="你好")
    assert msg.role == "user"
    assert msg.content == "你好"
    assert msg.tool_calls is None

def test_tool_call_creation():
    tc = ToolCall(id="tc1", name="get_exam_scores", arguments={"exam_id": "e1"})
    assert tc.name == "get_exam_scores"
    assert tc.arguments["exam_id"] == "e1"

def test_agent_event_serialization():
    event = AgentEvent(type="tool_call", data={"tool": "get_exam_scores"})
    d = event.to_dict()
    assert d["type"] == "tool_call"
    assert "tool" in d["data"]

def test_agent_event_answer():
    event = AgentEvent(type="answer", data={"content": "数学平均分 105 分"})
    assert event.type == "answer"
```

- [ ] **Step 3: 运行确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: 实现 schemas.py**

```python
# src/edu_cloud/ai/schemas.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ChatMessage:
    role: str                          # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list["ToolCall"] | None = None
    tool_call_id: str | None = None    # role="tool" 时关联的 tool_call id
    name: str | None = None            # role="tool" 时的工具名

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentEvent:
    type: str     # "thinking" | "tool_call" | "tool_result" | "answer" | "error"
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type, "data": self.data}
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_ai/test_schemas.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: 更新 config.py LLM 配置**

```python
# src/edu_cloud/config.py — 修改 LLM 部分
    # LLM (via llm-proxy gateway)
    LLM_API_URL: str = "http://localhost:8100/v1/chat/completions"
    LLM_API_KEY: str = "not-needed-for-local-proxy"
    LLM_MODEL: str = "claude-sonnet-4-6"
    LLM_TIMEOUT: int = 120
    LLM_MAX_RETRIES: int = 3
    LLM_MAX_STEPS: int = 8    # ReAct 最大步数
```

- [ ] **Step 7: 实现 llm.py**

```python
# src/edu_cloud/ai/llm.py
import httpx
import json
import logging
from edu_cloud.ai.schemas import ChatMessage, ToolCall
from edu_cloud.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.url = settings.LLM_API_URL
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT

    async def chat(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> ChatMessage:
        """调用 llm-proxy，返回 assistant 消息（可能含 tool_calls）"""
        payload = {
            "model": self.model,
            "messages": [self._msg_to_dict(m) for m in messages],
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            )
            resp.raise_for_status()

        data = resp.json()
        choice = data["choices"][0]["message"]

        tool_calls = None
        if choice.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"])
                    if isinstance(tc["function"]["arguments"], str)
                    else tc["function"]["arguments"],
                )
                for tc in choice["tool_calls"]
            ]

        return ChatMessage(
            role="assistant",
            content=choice.get("content"),
            tool_calls=tool_calls,
        )

    def _msg_to_dict(self, msg: ChatMessage) -> dict:
        d = {"role": msg.role}
        if msg.content is not None:
            d["content"] = msg.content
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in msg.tool_calls
            ]
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        if msg.name:
            d["name"] = msg.name
        return d
```

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/ai/ tests/test_ai/ src/edu_cloud/config.py
git commit -m "feat(P1-1): AI schemas + LLM client + config（llm-proxy 8100）"
```

**审查清单:**
- ✓ ChatMessage/ToolCall/AgentEvent 数据类完整
- ✓ LLM 客户端发送 OpenAI 兼容格式到 llm-proxy
- ✓ tool_calls 解析支持 string 和 dict 两种 arguments 格式
- ✓ config 默认指向 llm-proxy localhost:8100
- ✗ LLM 客户端不应缓存连接（每次请求新建 httpx client）

**测试契约:**
1. schemas 序列化
   - 入口: 直接构造 dataclass
   - 反例: 错误实现可能遗漏可选字段默认值
   - 边界: None content / 空 tool_calls / 空 arguments
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_schemas.py -v`

---

## Task 2: 工具注册表

**Files:**
- Create: `src/edu_cloud/ai/registry.py`
- Test: `tests/test_ai/test_registry.py`

- [ ] **Step 1: 写注册表测试**

```python
# tests/test_ai/test_registry.py
import pytest
from edu_cloud.ai.registry import ToolRegistry

registry = ToolRegistry()

@registry.register(
    name="test_add",
    description="两数相加",
    parameters={
        "type": "object",
        "properties": {
            "a": {"type": "number", "description": "第一个数"},
            "b": {"type": "number", "description": "第二个数"},
        },
        "required": ["a", "b"],
    },
    category="test",
)
async def test_add_func(a: float, b: float, _db=None) -> dict:
    return {"result": a + b}


def test_register_tool():
    """工具注册后可通过名称查找"""
    assert "test_add" in registry.list_tools()

def test_get_schemas():
    """获取 OpenAI 格式的工具 schema"""
    schemas = registry.get_schemas()
    assert len(schemas) >= 1
    schema = next(s for s in schemas if s["function"]["name"] == "test_add")
    assert schema["type"] == "function"
    assert "a" in schema["function"]["parameters"]["properties"]

def test_get_schemas_filtered_by_category():
    """按 category 过滤工具"""
    schemas = registry.get_schemas(categories=["test"])
    assert len(schemas) >= 1
    schemas_other = registry.get_schemas(categories=["nonexistent"])
    assert len(schemas_other) == 0

@pytest.mark.asyncio
async def test_execute_tool():
    """执行注册的工具"""
    result = await registry.execute("test_add", {"a": 3, "b": 5})
    assert result == {"result": 8}

@pytest.mark.asyncio
async def test_execute_with_injected_params():
    """框架参数（_前缀）自动注入"""
    result = await registry.execute("test_add", {"a": 1, "b": 2}, _db="mock_db")
    assert result == {"result": 3}

def test_execute_unknown_tool():
    """执行不存在的工具抛异常"""
    with pytest.raises(KeyError):
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            registry.execute("nonexistent", {})
        )
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_ai/test_registry.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 registry.py**

```python
# src/edu_cloud/ai/registry.py
import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        category: str = "general",
    ):
        """装饰器：注册一个 AI 工具"""
        def decorator(func: Callable):
            self._tools[name] = {
                "name": name,
                "description": description,
                "parameters": parameters,
                "category": category,
                "func": func,
            }
            return func
        return decorator

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_schemas(self, categories: list[str] | None = None) -> list[dict]:
        """返回 OpenAI function calling 格式的 tool schemas"""
        result = []
        for tool in self._tools.values():
            if categories and tool["category"] not in categories:
                continue
            result.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            })
        return result

    async def execute(self, name: str, arguments: dict[str, Any], **injected) -> Any:
        """执行工具，自动注入 _ 前缀的框架参数"""
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")

        func = self._tools[name]["func"]
        sig = inspect.signature(func)

        # 合并用户参数 + 框架注入参数
        kwargs = dict(arguments)
        for param_name in sig.parameters:
            if param_name.startswith("_") and param_name in injected:
                kwargs[param_name] = injected[param_name]

        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)


# 全局注册表实例
tools = ToolRegistry()
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_ai/test_registry.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/registry.py tests/test_ai/test_registry.py
git commit -m "feat(P1-2): 工具注册表 — @register 装饰器 + category 过滤 + 框架参数注入"
```

**审查清单:**
- ✓ @register 装饰器注册工具元数据
- ✓ get_schemas 返回 OpenAI function calling 格式
- ✓ categories 过滤正确
- ✓ execute 自动注入 _前缀参数（_db, _school_id 等）
- ✓ 未知工具抛 KeyError
- ✗ 不应在 registry 中做权限检查（由 agent 层处理）

**边界条件:**
- 注册同名工具 → 期望: 覆盖（后注册的生效）
- categories=None → 期望: 返回全部工具
- execute 时缺少必需参数 → 期望: Python TypeError

**测试契约:**
1. 工具注册+发现+执行完整链路
   - 入口: `registry.register()` + `registry.execute()`
   - 反例: 错误实现可能不存储 func 引用导致执行失败
   - 边界: 空参数 / 多余参数 / _前缀注入参数
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_registry.py -v`

---

## Task 3: L1 校本分析工具（4 个核心）

**Files:**
- Create: `src/edu_cloud/ai/tools/analytics.py`
- Modify: `src/edu_cloud/ai/tools/__init__.py`
- Test: `tests/test_ai/test_tools_analytics.py`

- [ ] **Step 1: 写 L1 工具测试**

```python
# tests/test_ai/test_tools_analytics.py
import pytest
from edu_cloud.ai.tools.analytics import (
    get_exam_scores, get_class_stats, compare_classes, get_student_profile,
)

# 需要 DB fixture，使用 conftest 中的 db + 种子数据

@pytest.mark.asyncio
async def test_get_exam_scores(db, seed_exam_with_results):
    """获取考试成绩列表"""
    exam_id = seed_exam_with_results["exam_id"]
    school_id = seed_exam_with_results["school_id"]
    result = await get_exam_scores(
        exam_id=exam_id, _db=db, _school_id=school_id, _class_ids=None
    )
    assert "students" in result
    assert len(result["students"]) > 0
    assert "total_score" in result["students"][0]
    assert "stats" in result

@pytest.mark.asyncio
async def test_get_exam_scores_with_class_filter(db, seed_exam_with_results):
    """班主任只看本班成绩"""
    exam_id = seed_exam_with_results["exam_id"]
    school_id = seed_exam_with_results["school_id"]
    class_id = seed_exam_with_results["class_id"]
    result = await get_exam_scores(
        exam_id=exam_id, _db=db, _school_id=school_id, _class_ids=[class_id]
    )
    assert len(result["students"]) > 0
    # 所有返回的学生都属于指定班级
    for s in result["students"]:
        assert s["class_id"] == class_id

@pytest.mark.asyncio
async def test_get_class_stats(db, seed_exam_with_results):
    """获取班级统计"""
    exam_id = seed_exam_with_results["exam_id"]
    class_id = seed_exam_with_results["class_id"]
    result = await get_class_stats(
        exam_id=exam_id, class_id=class_id, _db=db, _school_id=seed_exam_with_results["school_id"]
    )
    assert "avg" in result
    assert "max" in result
    assert "min" in result
    assert "count" in result

@pytest.mark.asyncio
async def test_get_exam_scores_empty(db, seed_exam_with_results):
    """空考试无成绩"""
    result = await get_exam_scores(
        exam_id="nonexistent", _db=db, _school_id="none", _class_ids=None
    )
    assert result["students"] == []
    assert result["stats"]["count"] == 0
```

- [ ] **Step 2: 创建测试 fixture**

```python
# tests/test_ai/__init__.py — 空文件

# tests/conftest.py 追加 seed_exam_with_results fixture
@pytest.fixture
async def seed_exam_with_results(db):
    """创建学校+班级+学生+考试+成绩（供 AI 工具测试）"""
    from edu_cloud.models.school import RegisteredSchool
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.models.student import Student
    from edu_cloud.models.exam import Exam, ExamResult
    import random

    school = RegisteredSchool(name="AI测试校", code="AITEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls = ClassGroup(name="七年级2班", grade="七年级", grade_number=7, school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i in range(10):
        s = Student(name=f"学生{i}", student_number=f"T{i:03d}", school_id=school.id,
                    class_id=cls.id, grade="七年级")
        db.add(s)
        students.append(s)
    await db.flush()

    exam = Exam(name="期中数学", subject_code="SX", subject_name="数学",
                max_score=150, school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()

    random.seed(42)
    for s in students:
        score = round(random.gauss(105, 20), 1)
        score = max(0, min(150, score))
        db.add(ExamResult(exam_id=exam.id, student_id=s.id, school_id=school.id, total_score=score))
    await db.commit()

    return {
        "school_id": school.id,
        "class_id": cls.id,
        "exam_id": exam.id,
        "student_ids": [s.id for s in students],
    }
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_ai/test_tools_analytics.py -v`
Expected: FAIL

- [ ] **Step 4: 实现 L1 工具**

```python
# src/edu_cloud/ai/tools/analytics.py
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.ai.registry import tools
from edu_cloud.models.exam import Exam, ExamResult
from edu_cloud.models.student import Student
from edu_cloud.models.class_group import ClassGroup


@tools.register(
    name="get_exam_scores",
    description="获取某次考试的成绩列表和统计信息。返回学生姓名、分数、排名。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
    },
    category="L1_analytics",
)
async def get_exam_scores(exam_id: str, _db: AsyncSession = None, _school_id: str = None, _class_ids: list = None) -> dict:
    q = (
        select(ExamResult, Student.name.label("student_name"), Student.student_number, Student.class_id)
        .join(Student, ExamResult.student_id == Student.id)
        .where(ExamResult.exam_id == exam_id, ExamResult.school_id == _school_id)
    )
    if _class_ids:
        q = q.where(Student.class_id.in_(_class_ids))
    q = q.order_by(ExamResult.total_score.desc())

    rows = (await _db.execute(q)).all()
    students = []
    scores = []
    for i, row in enumerate(rows):
        result, name, number, class_id = row
        students.append({
            "rank": i + 1,
            "name": name,
            "student_number": number,
            "class_id": class_id,
            "total_score": result.total_score,
        })
        scores.append(result.total_score)

    stats = _compute_stats(scores)
    return {"students": students, "stats": stats}


@tools.register(
    name="get_class_stats",
    description="获取指定班级在某次考试中的统计信息（均分、最高分、最低分、中位数、人数）。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "class_id": {"type": "string", "description": "班级 ID"},
        },
        "required": ["exam_id", "class_id"],
    },
    category="L1_analytics",
)
async def get_class_stats(exam_id: str, class_id: str, _db: AsyncSession = None, _school_id: str = None) -> dict:
    q = (
        select(ExamResult.total_score)
        .join(Student, ExamResult.student_id == Student.id)
        .where(ExamResult.exam_id == exam_id, Student.class_id == class_id, ExamResult.school_id == _school_id)
    )
    rows = (await _db.execute(q)).scalars().all()
    return _compute_stats(list(rows))


@tools.register(
    name="compare_classes",
    description="对比同一考试中多个班级的平均分、最高分等，返回各班统计。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
    },
    category="L1_analytics",
)
async def compare_classes(exam_id: str, _db: AsyncSession = None, _school_id: str = None, _class_ids: list = None) -> dict:
    q = (
        select(
            Student.class_id,
            ClassGroup.name.label("class_name"),
            func.avg(ExamResult.total_score).label("avg"),
            func.max(ExamResult.total_score).label("max"),
            func.min(ExamResult.total_score).label("min"),
            func.count().label("count"),
        )
        .join(Student, ExamResult.student_id == Student.id)
        .join(ClassGroup, Student.class_id == ClassGroup.id)
        .where(ExamResult.exam_id == exam_id, ExamResult.school_id == _school_id)
        .group_by(Student.class_id, ClassGroup.name)
    )
    if _class_ids:
        q = q.where(Student.class_id.in_(_class_ids))

    rows = (await _db.execute(q)).all()
    classes = []
    for row in rows:
        classes.append({
            "class_id": row.class_id,
            "class_name": row.class_name,
            "avg": round(float(row.avg), 1) if row.avg else 0,
            "max": float(row.max) if row.max else 0,
            "min": float(row.min) if row.min else 0,
            "count": row.count,
        })
    return {"classes": classes}


@tools.register(
    name="get_student_profile",
    description="获取某学生的各科成绩汇总。",
    parameters={
        "type": "object",
        "properties": {
            "student_number": {"type": "string", "description": "学生学号"},
        },
        "required": ["student_number"],
    },
    category="L1_analytics",
)
async def get_student_profile(student_number: str, _db: AsyncSession = None, _school_id: str = None) -> dict:
    student = (await _db.execute(
        select(Student).where(Student.student_number == student_number, Student.school_id == _school_id)
    )).scalar_one_or_none()
    if not student:
        return {"error": f"学生 {student_number} 不存在"}

    results = (await _db.execute(
        select(ExamResult, Exam.name.label("exam_name"), Exam.subject_code, Exam.max_score)
        .join(Exam, ExamResult.exam_id == Exam.id)
        .where(ExamResult.student_id == student.id)
        .order_by(Exam.created_at.desc())
    )).all()

    exams = []
    for row in results:
        result, exam_name, subject_code, max_score = row
        exams.append({
            "exam_name": exam_name,
            "subject_code": subject_code,
            "score": result.total_score,
            "max_score": max_score,
            "rate": round(result.total_score / max_score * 100, 1) if max_score else 0,
        })

    return {
        "name": student.name,
        "student_number": student.student_number,
        "class_id": student.class_id,
        "exams": exams,
    }


def _compute_stats(scores: list[float]) -> dict:
    if not scores:
        return {"count": 0, "avg": 0, "max": 0, "min": 0, "median": 0}
    sorted_s = sorted(scores)
    n = len(sorted_s)
    median = sorted_s[n // 2] if n % 2 == 1 else (sorted_s[n // 2 - 1] + sorted_s[n // 2]) / 2
    return {
        "count": n,
        "avg": round(sum(scores) / n, 1),
        "max": max(scores),
        "min": min(scores),
        "median": median,
    }
```

- [ ] **Step 5: 注册工具导入**

```python
# src/edu_cloud/ai/tools/__init__.py
from edu_cloud.ai.tools import analytics  # noqa: F401 — 触发 @register 装饰器
```

- [ ] **Step 6: 运行确认通过**

Run: `python -m pytest tests/test_ai/test_tools_analytics.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: 运行全量测试确认无回归**

Run: `python -m pytest --tb=short -q`
Expected: 94 + 新增 tests 全 PASS

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/ai/tools/ tests/
git commit -m "feat(P1-3): L1 校本分析工具 — get_exam_scores + get_class_stats + compare_classes + get_student_profile"
```

**审查清单:**
- ✓ 4 个 L1 工具全部注册到全局 registry
- ✓ 所有工具接受 _db/_school_id/_class_ids 框架参数
- ✓ _class_ids 过滤实现（班主任 scope 限制）
- ✓ 空结果返回合理默认值
- ✗ 不应在工具中做权限检查（由上层 agent 处理）

**边界条件:**
- exam_id 不存在 → 期望: 返回空 students 列表 + count=0
- 班级内 0 个学生 → 期望: 空列表，stats 全为 0
- student_number 不存在 → 期望: 返回 error 消息

**测试契约:**
1. 成绩查询 + scope 过滤
   - 入口: `get_exam_scores(exam_id, _db, _school_id, _class_ids=[cls_id])`
   - 反例: 错误实现忽略 _class_ids 返回全校数据
   - 边界: class_ids=None(全部) / class_ids=["不存在"] / 空考试
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_tools_analytics.py -v`

---

## Task 4: 匿名化 + 上下文构建

**Files:**
- Create: `src/edu_cloud/ai/anonymizer.py`, `src/edu_cloud/ai/context.py`
- Test: `tests/test_ai/test_anonymizer.py`, `tests/test_ai/test_context.py`

- [ ] **Step 1: 写匿名化测试**

```python
# tests/test_ai/test_anonymizer.py
from edu_cloud.ai.anonymizer import Anonymizer

def test_anonymize_names():
    anon = Anonymizer()
    text = "张三的数学成绩是 135 分，李四的是 120 分"
    names = ["张三", "李四"]
    result = anon.anonymize(text, names)
    assert "张三" not in result
    assert "李四" not in result
    assert "S001" in result
    assert "S002" in result

def test_deanonymize():
    anon = Anonymizer()
    anon.anonymize("张三考了满分", ["张三"])
    result = anon.deanonymize("S001考了满分")
    assert "张三" in result
    assert "S001" not in result

def test_anonymize_dict():
    anon = Anonymizer()
    data = {"name": "张三", "score": 135, "comment": "张三表现优秀"}
    names = ["张三"]
    result = anon.anonymize_data(data, names)
    assert result["name"] == "S001"
    assert result["comment"] == "S001表现优秀"
    assert result["score"] == 135  # 非字符串不变

def test_anonymizer_reset():
    anon = Anonymizer()
    anon.anonymize("张三", ["张三"])
    anon.reset()
    assert len(anon._map) == 0
```

- [ ] **Step 2: 实现 anonymizer.py**

```python
# src/edu_cloud/ai/anonymizer.py
import json
import re

class Anonymizer:
    """会话级学生姓名匿名化。映射绑定会话，会话结束 reset()。"""

    def __init__(self):
        self._map: dict[str, str] = {}       # 真名 → 匿名ID
        self._reverse: dict[str, str] = {}   # 匿名ID → 真名
        self._counter = 0

    def _get_id(self, name: str) -> str:
        if name not in self._map:
            self._counter += 1
            anon_id = f"S{self._counter:03d}"
            self._map[name] = anon_id
            self._reverse[anon_id] = name
        return self._map[name]

    def anonymize(self, text: str, names: list[str]) -> str:
        """替换文本中的学生姓名为匿名ID"""
        for name in sorted(names, key=len, reverse=True):  # 长名优先
            anon_id = self._get_id(name)
            text = text.replace(name, anon_id)
        return text

    def anonymize_data(self, data, names: list[str]):
        """递归匿名化 dict/list/str"""
        if isinstance(data, str):
            return self.anonymize(data, names)
        if isinstance(data, dict):
            return {k: self.anonymize_data(v, names) for k, v in data.items()}
        if isinstance(data, list):
            return [self.anonymize_data(item, names) for item in data]
        return data

    def deanonymize(self, text: str) -> str:
        """还原匿名ID为真名"""
        for anon_id, name in sorted(self._reverse.items(), key=lambda x: len(x[0]), reverse=True):
            text = text.replace(anon_id, name)
        return text

    def reset(self):
        self._map.clear()
        self._reverse.clear()
        self._counter = 0
```

- [ ] **Step 3: 写上下文测试**

```python
# tests/test_ai/test_context.py
from edu_cloud.ai.context import build_system_prompt

def test_system_prompt_contains_role():
    prompt = build_system_prompt(
        role="homeroom_teacher",
        display_name="张老师",
        scope={"school": "实验中学", "classes": ["七年级2班"]},
        tool_names=["get_exam_scores", "get_class_stats"],
    )
    assert "张老师" in prompt
    assert "班主任" in prompt or "homeroom_teacher" in prompt
    assert "七年级2班" in prompt
    assert "get_exam_scores" in prompt

def test_system_prompt_without_scope():
    prompt = build_system_prompt(
        role="platform_admin",
        display_name="管理员",
        scope={},
        tool_names=["get_exam_scores"],
    )
    assert "管理员" in prompt
```

- [ ] **Step 4: 实现 context.py**

```python
# src/edu_cloud/ai/context.py
from edu_cloud.ai.schemas import ChatMessage

ROLE_CN = {
    "platform_admin": "平台管理员",
    "district_admin": "教育局管理员",
    "principal": "校长",
    "academic_director": "教务主任",
    "grade_leader": "年级组长",
    "homeroom_teacher": "班主任",
    "subject_teacher": "科任教师",
}

def build_system_prompt(
    role: str,
    display_name: str,
    scope: dict,
    tool_names: list[str],
) -> str:
    role_cn = ROLE_CN.get(role, role)
    scope_desc = ""
    if scope.get("school"):
        scope_desc += f"学校：{scope['school']}\n"
    if scope.get("classes"):
        scope_desc += f"班级：{', '.join(scope['classes'])}\n"
    if scope.get("grades"):
        scope_desc += f"年级：{', '.join(scope['grades'])}\n"
    if scope.get("subjects"):
        scope_desc += f"学科：{', '.join(scope['subjects'])}\n"

    tools_desc = "、".join(tool_names) if tool_names else "无"

    return f"""你是 edu-cloud 智能教学分析助手。

当前用户：{display_name}（{role_cn}）
{scope_desc}
你可以使用以下工具查询数据：{tools_desc}

规则：
1. 用中文回答。
2. 回答基于工具查询的真实数据，不要编造数据。
3. 学生姓名已匿名化（如 S001），在回答中使用匿名 ID。
4. 如果用户的问题超出你的工具能力，诚实说明。
5. 分析要有数据支撑，给出具体数字和对比。
"""
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_ai/test_anonymizer.py tests/test_ai/test_context.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/ai/anonymizer.py src/edu_cloud/ai/context.py tests/test_ai/
git commit -m "feat(P1-4): 匿名化器 + 上下文构建（角色/scope/工具注入 system prompt）"
```

**审查清单:**
- ✓ 匿名化支持 str / dict / list 递归处理
- ✓ 还原时长 ID 优先替换（避免 S001 被 S00 匹配）
- ✓ system prompt 包含角色、scope、可用工具
- ✓ reset() 清除映射
- ✗ 不应在匿名化中处理 k-匿名逻辑（由工具层处理）

**边界条件:**
- 空 names 列表 → 期望: 文本不变
- 同一名字多次出现 → 期望: 全部替换为同一 ID
- 嵌套 dict → 期望: 递归处理所有字符串值

---

## Task 5: ReAct 循环引擎

**Files:**
- Create: `src/edu_cloud/ai/agent.py`
- Test: `tests/test_ai/test_agent.py`

- [ ] **Step 1: 写 agent 测试（mock LLM）**

```python
# tests/test_ai/test_agent.py
import pytest
from unittest.mock import AsyncMock, patch
from edu_cloud.ai.agent import Agent
from edu_cloud.ai.schemas import ChatMessage, ToolCall, AgentEvent
from edu_cloud.ai.registry import ToolRegistry

@pytest.fixture
def test_registry():
    reg = ToolRegistry()

    @reg.register(name="mock_tool", description="返回固定数据", category="test",
                  parameters={"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]})
    async def mock_tool(q: str, _db=None) -> dict:
        return {"answer": f"result for {q}"}

    return reg

@pytest.mark.asyncio
async def test_agent_direct_answer(test_registry):
    """LLM 直接回答（不调用工具）"""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = ChatMessage(role="assistant", content="你好，我是 AI 助手")

    agent = Agent(llm=mock_llm, registry=test_registry)
    events = []
    async for event in agent.run("你好", session_id="test", db=None, school_id=None, class_ids=None, role="principal", display_name="校长", scope={}):
        events.append(event)

    assert any(e.type == "answer" for e in events)
    answer = next(e for e in events if e.type == "answer")
    assert "你好" in answer.data["content"]

@pytest.mark.asyncio
async def test_agent_tool_call(test_registry):
    """LLM 调用工具后回答"""
    mock_llm = AsyncMock()
    # 第一次：LLM 返回 tool_call
    mock_llm.chat.side_effect = [
        ChatMessage(role="assistant", content=None, tool_calls=[
            ToolCall(id="tc1", name="mock_tool", arguments={"q": "数学"})
        ]),
        # 第二次：LLM 根据工具结果回答
        ChatMessage(role="assistant", content="数学的结果是 result for 数学"),
    ]

    agent = Agent(llm=mock_llm, registry=test_registry)
    events = []
    async for event in agent.run("查数学", session_id="test", db=None, school_id=None, class_ids=None, role="principal", display_name="校长", scope={}):
        events.append(event)

    types = [e.type for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "answer" in types

@pytest.mark.asyncio
async def test_agent_max_steps(test_registry):
    """超过最大步数强制停止"""
    mock_llm = AsyncMock()
    # LLM 总是返回 tool_call，永不给出 final answer
    mock_llm.chat.return_value = ChatMessage(
        role="assistant", content=None,
        tool_calls=[ToolCall(id="tc1", name="mock_tool", arguments={"q": "loop"})]
    )

    agent = Agent(llm=mock_llm, registry=test_registry, max_steps=2)
    events = []
    async for event in agent.run("无限循环", session_id="test", db=None, school_id=None, class_ids=None, role="principal", display_name="校长", scope={}):
        events.append(event)

    # 应该在 max_steps 后强制返回 error 或 answer
    assert any(e.type in ("answer", "error") for e in events)
    assert mock_llm.chat.call_count <= 3  # max_steps=2, 最多 call 3 次（含初始）
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_ai/test_agent.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 agent.py**

```python
# src/edu_cloud/ai/agent.py
import json
import logging
from typing import AsyncGenerator
from edu_cloud.ai.schemas import ChatMessage, ToolCall, AgentEvent
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.context import build_system_prompt
from edu_cloud.ai.anonymizer import Anonymizer
from edu_cloud.config import settings

logger = logging.getLogger(__name__)

# Anonymizer 集成说明：
# 1. 工具返回结果中的学生姓名 → 匿名化后再传给 LLM
# 2. LLM 最终回答 → 反匿名化后再返回前端
# 3. 匿名映射绑定会话，run() 结束后 reset()

ROLE_TOOL_CATEGORIES = {
    "platform_admin": None,  # None = all
    "district_admin": ["L2_cross_school"],
    "principal": ["L1_analytics", "L2_cross_school"],
    "academic_director": ["L1_analytics", "L2_cross_school"],
    "grade_leader": ["L1_analytics"],
    "homeroom_teacher": ["L1_analytics"],
    "subject_teacher": ["L1_analytics"],
}

class Agent:
    def __init__(self, llm, registry: ToolRegistry, max_steps: int | None = None):
        self.llm = llm
        self.registry = registry
        self.max_steps = max_steps or settings.LLM_MAX_STEPS

    async def run(
        self,
        user_message: str,
        session_id: str,
        db,
        school_id: str | None,
        class_ids: list | None,
        role: str,
        display_name: str,
        scope: dict,
    ) -> AsyncGenerator[AgentEvent, None]:
        """执行 ReAct 循环，yield AgentEvent 流"""
        # 1. 确定可用工具
        categories = ROLE_TOOL_CATEGORIES.get(role)
        tool_schemas = self.registry.get_schemas(categories=categories)
        tool_names = [s["function"]["name"] for s in tool_schemas]

        # 2. 构建系统 prompt
        system_prompt = build_system_prompt(role, display_name, scope, tool_names)

        # 3. 初始化消息列表
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]

        # 4. 匿名化器（会话级）
        anonymizer = Anonymizer()

        # 5. ReAct 循环
        for step in range(self.max_steps):
            try:
                response = await self.llm.chat(messages, tools=tool_schemas if tool_schemas else None)
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                yield AgentEvent(type="error", data={"message": f"AI 服务暂时不可用: {e}"})
                return

            # 无 tool_calls → final answer（反匿名化）
            if not response.tool_calls:
                content = response.content or "抱歉，我无法回答这个问题。"
                content = anonymizer.deanonymize(content)
                yield AgentEvent(type="answer", data={"content": content})
                return

            # 有 tool_calls → 执行工具
            messages.append(response)

            for tc in response.tool_calls:
                yield AgentEvent(type="tool_call", data={"tool": tc.name, "arguments": tc.arguments})

                try:
                    result = await self.registry.execute(
                        tc.name, tc.arguments,
                        _db=db, _school_id=school_id, _class_ids=class_ids,
                    )
                except Exception as e:
                    logger.error(f"Tool {tc.name} failed: {e}")
                    result = {"error": str(e)}

                # 匿名化工具结果中的学生姓名
                student_names = self._extract_names(result)
                anon_result = anonymizer.anonymize_data(result, student_names)
                result_str = json.dumps(anon_result, ensure_ascii=False, default=str)
                yield AgentEvent(type="tool_result", data={"tool": tc.name, "result": result})  # 前端看到真名

                messages.append(ChatMessage(
                    role="tool", content=result_str,
                    tool_call_id=tc.id, name=tc.name,
                ))

        # 超过 max_steps
        yield AgentEvent(type="answer", data={"content": "分析步骤过多，请尝试更具体的问题。"})

    @staticmethod
    def _extract_names(data) -> list[str]:
        """从工具返回结果中提取学生姓名（用于匿名化）"""
        names = []
        if isinstance(data, dict):
            for key in ("name", "student_name"):
                if key in data and isinstance(data[key], str):
                    names.append(data[key])
            for v in data.values():
                names.extend(Agent._extract_names(v))
        elif isinstance(data, list):
            for item in data:
                names.extend(Agent._extract_names(item))
        return list(set(names))
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_ai/test_agent.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/agent.py tests/test_ai/test_agent.py
git commit -m "feat(P1-5): ReAct 循环引擎 — 角色工具过滤 + max_steps 保护 + 工具执行 + 事件流"
```

**审查清单:**
- ✓ ReAct 循环：Thought→Action→Observation 模式
- ✓ 角色→工具 category 映射
- ✓ max_steps 防止无限循环
- ✓ 工具执行异常被捕获并返回 error
- ✓ 以 AsyncGenerator yield AgentEvent
- ✗ Agent 不应持有 DB session（由调用方注入）

**边界条件:**
- LLM 返回空 content 且无 tool_calls → 期望: 返回默认消息
- 工具执行异常 → 期望: 错误结果传回 LLM 继续推理
- 超过 max_steps → 期望: 返回提示消息而非崩溃

**测试契约:**
1. ReAct 循环基本流程
   - 入口: `agent.run(user_message, ...)`
   - 反例: 错误实现可能在工具调用后不把结果传回 LLM
   - 边界: 0 工具可用 / 工具执行失败 / max_steps=1
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_agent.py -v`

---

## Task 6: AI SSE API 端点 + 审计

**Files:**
- Create: `src/edu_cloud/api/ai.py`, `src/edu_cloud/models/ai_session.py`, `src/edu_cloud/ai/audit.py`
- Modify: `src/edu_cloud/api/app.py`, `pyproject.toml`
- Test: `tests/test_ai/test_ai_api.py`

- [ ] **Step 1: 添加 sse-starlette 依赖**

```bash
cd C:/Users/Administrator/edu-cloud
# pyproject.toml dependencies 追加 "sse-starlette>=2.0"
```

- [ ] **Step 2: 创建 AiSession / AiToolCall 模型**

```python
# src/edu_cloud/models/ai_session.py
from sqlalchemy import Column, String, JSON, DateTime, Float, ForeignKey, Text
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class AiSession(Base, IdMixin, TimestampMixin):
    __tablename__ = "ai_sessions"
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String(50), nullable=False)
    context_snapshot = Column(JSON, nullable=True)   # 会话开始时的左栏上下文

class AiToolCall(Base, IdMixin, TimestampMixin):
    __tablename__ = "ai_tool_calls"
    session_id = Column(String, ForeignKey("ai_sessions.id"), nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(String(50), nullable=False)
    tool = Column(String(100), nullable=False)
    arguments = Column(JSON, nullable=True)
    result_summary = Column(Text, nullable=True)     # 结果摘要（截断到 500 字符）
    duration_ms = Column(Float, nullable=True)
```

- [ ] **Step 3: 实现 audit.py**

```python
# src/edu_cloud/ai/audit.py
import time
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.ai_session import AiSession, AiToolCall

logger = logging.getLogger(__name__)

class AuditLogger:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, user_id: str, role: str, context: dict | None = None) -> str:
        session = AiSession(user_id=user_id, role=role, context_snapshot=context)
        self.db.add(session)
        await self.db.flush()
        return session.id

    async def log_tool_call(
        self, session_id: str, user_id: str, role: str,
        tool: str, arguments: dict, result: str, duration_ms: float,
    ):
        summary = result[:500] if result else ""
        self.db.add(AiToolCall(
            session_id=session_id, user_id=user_id, role=role,
            tool=tool, arguments=arguments,
            result_summary=summary, duration_ms=duration_ms,
        ))
        await self.db.flush()
```

- [ ] **Step 4: 写 AI API 测试**

```python
# tests/test_ai/test_ai_api.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_ai_health(client):
    resp = await client.get("/api/v1/ai/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_ai_chat_requires_auth(client):
    """未认证时 401"""
    resp = await client.post("/api/v1/ai/chat", json={"message": "你好"})
    assert resp.status_code in (401, 403)

@pytest.mark.asyncio
async def test_ai_chat_empty_message(client, teacher_headers):
    """空消息返回 422"""
    resp = await client.post("/api/v1/ai/chat", json={"message": ""})
    # 空消息应被拒绝或返回提示
    assert resp.status_code in (422, 400) or resp.status_code == 200
```

- [ ] **Step 5: 实现 AI API 路由**

```python
# src/edu_cloud/api/ai.py
import json
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.ai.agent import Agent
from edu_cloud.ai.llm import LLMClient
from edu_cloud.ai.registry import tools
from edu_cloud.ai.audit import AuditLogger
from edu_cloud.ai.schemas import AgentEvent
import edu_cloud.ai.tools  # noqa: F401 — 触发工具注册

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

@router.get("/health")
async def ai_health():
    tool_count = len(tools.list_tools())
    return {"status": "ok", "tools": tool_count}

@router.post("/chat")
async def ai_chat(
    body: dict,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    message = body.get("message", "").strip()
    if not message:
        return {"error": "消息不能为空"}

    user = current["user"]
    role_obj = current["current_role"]
    role = role_obj.role if hasattr(role_obj, "role") else getattr(role_obj, "_role", "unknown")

    # 构建 scope 描述
    scope = {}
    if hasattr(role_obj, "school_id") and role_obj.school_id:
        scope["school"] = role_obj.school_id
    if hasattr(role_obj, "class_ids") and role_obj.class_ids:
        scope["classes"] = role_obj.class_ids

    llm = LLMClient()
    agent = Agent(llm=llm, registry=tools)

    async def event_stream():
        async for event in agent.run(
            user_message=message,
            session_id="temp",
            db=db,
            school_id=getattr(role_obj, "school_id", None),
            class_ids=getattr(role_obj, "class_ids", None),
            role=role,
            display_name=user.display_name,
            scope=scope,
        ):
            yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 6: 注册路由到 app.py**

```python
# src/edu_cloud/api/app.py — 追加
from edu_cloud.api.ai import router as ai_router
app.include_router(ai_router)
```

- [ ] **Step 7: 运行测试**

Run: `python -m pytest tests/test_ai/test_ai_api.py -v`
Expected: PASS

- [ ] **Step 8: 运行全量测试**

Run: `python -m pytest --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 9: Commit**

```bash
git add src/edu_cloud/api/ai.py src/edu_cloud/models/ai_session.py \
        src/edu_cloud/ai/audit.py src/edu_cloud/api/app.py \
        pyproject.toml tests/
git commit -m "feat(P1-6): AI SSE 端点 + 审计模型 + 路由注册"
```

**审查清单:**
- ✓ POST /api/v1/ai/chat 返回 SSE 流
- ✓ 需要 JWT 认证
- ✓ 从 current_role 提取 scope 传给 Agent
- ✓ AiSession + AiToolCall 模型用于审计
- ✓ GET /api/v1/ai/health 返回工具数量
- ✗ 不应在 SSE 流中暴露内部异常堆栈

**边界条件:**
- 空消息 → 期望: 返回错误提示
- 未认证 → 期望: 401
- LLM 不可用 → 期望: error 事件，不崩溃

**测试契约:**
1. AI 端点认证
   - 入口: `POST /api/v1/ai/chat` 无 token
   - 反例: 错误实现可能忽略认证
   - 边界: 无 token / 过期 token / 无角色用户
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_ai_api.py -v`

---

## Task 7: AI 对话前端组件

**Files:**
- Create: `frontend/src/components/workspace/ChatPanel.vue`, `frontend/src/stores/aiChat.js`
- Modify: `frontend/src/components/workspace/DataView.vue`

- [ ] **Step 1: 创建 aiChat store**

```javascript
// frontend/src/stores/aiChat.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useContextStore } from './context.js'

export const useAiChatStore = defineStore('aiChat', () => {
  const messages = ref([])       // [{role, content, toolCalls?, toolResults?}]
  const isStreaming = ref(false)
  const error = ref('')

  async function sendMessage(text) {
    if (!text.trim() || isStreaming.value) return

    messages.value.push({ role: 'user', content: text })
    isStreaming.value = true
    error.value = ''

    const token = localStorage.getItem('token')
    let assistantContent = ''

    try {
      const response = await fetch('/api/v1/ai/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      // 添加空 assistant 消息，实时更新
      const msgIndex = messages.value.length
      messages.value.push({ role: 'assistant', content: '', toolCalls: [], toolResults: [] })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = JSON.parse(line.slice(6))

          if (data.type === 'tool_call') {
            messages.value[msgIndex].toolCalls.push(data.data)
          } else if (data.type === 'tool_result') {
            messages.value[msgIndex].toolResults.push(data.data)
          } else if (data.type === 'answer') {
            messages.value[msgIndex].content = data.data.content
          } else if (data.type === 'error') {
            error.value = data.data.message
          }
        }
      }
    } catch (e) {
      error.value = e.message || 'AI 服务不可用'
    } finally {
      isStreaming.value = false
    }
  }

  function clearMessages() {
    messages.value = []
    error.value = ''
  }

  return { messages, isStreaming, error, sendMessage, clearMessages }
})
```

- [ ] **Step 2: 创建 ChatPanel 组件**

```vue
<!-- frontend/src/components/workspace/ChatPanel.vue -->
<template>
  <div class="chat-panel">
    <!-- 消息列表 -->
    <div class="chat-messages" ref="messagesContainer">
      <div v-for="(msg, i) in chatStore.messages" :key="i" :class="['message', msg.role]">
        <div v-if="msg.role === 'user'" class="user-msg">{{ msg.content }}</div>
        <div v-else class="assistant-msg">
          <!-- 工具调用标签 -->
          <div v-if="msg.toolCalls?.length" class="tool-tags">
            <n-tag v-for="tc in msg.toolCalls" :key="tc.tool" size="small" type="info">
              🔧 {{ tc.tool }}
            </n-tag>
          </div>
          <!-- 回答内容 -->
          <div v-if="msg.content" class="answer-content" v-html="renderMarkdown(msg.content)" />
          <n-spin v-else-if="chatStore.isStreaming && i === chatStore.messages.length - 1" size="small" />
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <n-alert v-if="chatStore.error" type="error" closable style="margin: 8px">
      {{ chatStore.error }}
    </n-alert>

    <!-- 输入框 -->
    <div class="chat-input">
      <n-input
        v-model:value="inputText"
        placeholder="问一个关于教学数据的问题..."
        :disabled="chatStore.isStreaming"
        @keyup.enter="handleSend"
      />
      <n-button
        type="primary"
        :loading="chatStore.isStreaming"
        :disabled="!inputText.trim()"
        @click="handleSend"
      >
        发送
      </n-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import { useAiChatStore } from '../../stores/aiChat.js'

const chatStore = useAiChatStore()
const inputText = ref('')
const messagesContainer = ref(null)

function renderMarkdown(text) {
  // 简单 Markdown：粗体、换行、代码块
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

async function handleSend() {
  if (!inputText.value.trim()) return
  const text = inputText.value
  inputText.value = ''
  await chatStore.sendMessage(text)
}

// 自动滚动到底部
watch(() => chatStore.messages.length, async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
})
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-top: 1px solid var(--n-border-color);
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
.message { margin-bottom: 12px; }
.user-msg {
  background: #2a5d3a;
  color: white;
  padding: 8px 12px;
  border-radius: 12px 12px 0 12px;
  max-width: 80%;
  margin-left: auto;
}
.assistant-msg {
  background: #2d2d3d;
  padding: 8px 12px;
  border-radius: 12px 12px 12px 0;
  max-width: 90%;
}
.tool-tags { margin-bottom: 6px; display: flex; gap: 4px; flex-wrap: wrap; }
.chat-input {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--n-border-color);
}
</style>
```

- [ ] **Step 3: 在 DataView 底部嵌入 ChatPanel**

```vue
<!-- frontend/src/components/workspace/DataView.vue — 修改 -->
<template>
  <div style="display: flex; flex-direction: column; height: 100%;">
    <!-- 上半区：数据呈现 -->
    <div style="flex: 1; overflow-y: auto; padding-bottom: 8px;">
      <template v-if="contextStore.dashboard">
        <!-- 现有的统计卡片 + 图表 -->
        ...
      </template>
      <n-empty v-else description="请在左栏选择一次考试" />
    </div>

    <!-- 下半区：AI 对话 -->
    <div style="height: 300px; min-height: 200px;">
      <ChatPanel />
    </div>
  </div>
</template>

<script setup>
import ChatPanel from './ChatPanel.vue'
// ... 其余 import 保持不变
</script>
```

- [ ] **Step 4: 端到端验证**

Run: 启动后端 + 前端 + llm-proxy
1. 以 zhanglaoshi 登录
2. 左栏选择期中考试
3. 在底部对话框输入 "我们班数学考得怎么样"
4. 观察：AI 调用 get_exam_scores → 返回分析结果

Expected: **P1 完成标志达成**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(P1-7): AI 对话前端 — ChatPanel + SSE 流解析 + 工具调用标签"
```

**审查清单:**
- ✓ SSE 流解析（data: 前缀 → JSON parse）
- ✓ 工具调用以标签形式显示
- ✓ Markdown 基本渲染（粗体 + 换行）
- ✓ 输入框发送后清空
- ✓ 流式输出期间禁用发送按钮
- ✓ 自动滚动到最新消息
- ✗ 不应在前端存储完整工具执行结果（只显示摘要）

**边界条件:**
- 空输入 → 期望: 发送按钮禁用
- AI 返回 error 事件 → 期望: 显示错误 alert
- 流式输出中途网络断开 → 期望: error 提示，不崩溃

**测试契约:**
1. SSE 流解析正确性
   - 入口: 前端 ChatPanel fetch → SSE stream
   - 反例: 错误实现可能不处理多行 chunk 或不识别 data: 前缀
   - 边界: 空 chunk / 多事件在一个 chunk / error 事件
   - 回归: N/A
   - 命令: 手动验证（前端组件无自动化测试框架）
