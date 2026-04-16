# Agent 韧性与验证增强设计

> [2026-04-06 22:13:06 实现完成] Commits: a664d04..10c8cdb (Gate 1+2 PASS, GPT 2 轮审查)

> 2026-04-06 19:01:21 | Claude×GPT 共识版
> 对标: DeerFlow (ByteDance, 58k star) 深度对比后的结构性增强

## §0 背景与动机

edu-cloud Agent 系统（42 工具、8 角色 RBAC、3 层记忆、1359 tests）在与 DeerFlow 的量化对比中，权限安全(7.5 vs 2.5)和测试覆盖(7 vs 3)领先，但在错误恢复(两者都弱)和输出验证(4.5 vs 1)方面存在结构性缺陷。

代码审计发现：OutputValidator 因接线错误从未真正工作；并发工具批次 >10 个会静默丢弃；error_count 语义混乱。这些不是"增强"，是必须修的 bug。

## §1 范围

方案 B（韧性+验证增强）：P0 bug fix + P1 韧性 + P2 验证 + P3 配置外提。
不含管道化重构（方案 C），理由：当前 Agent 功能稳定，无频繁加步骤需求。

**涉及文件：**
- `src/edu_cloud/ai/runtime.py` — P0-1
- `src/edu_cloud/ai/tool_executor.py` — P0-2, P1-2
- `src/edu_cloud/ai/memory_store.py` — P0-3
- `src/edu_cloud/ai/agent_loop.py` — P0-4, P2-3
- `src/edu_cloud/ai/llm_adapter.py` — P1-1
- `src/edu_cloud/ai/grounded.py` — P2-1, P2-2
- `src/edu_cloud/ai/capability_probe.py` — P3-1
- `src/edu_cloud/ai/model_router.py` — P3-2
- `src/edu_cloud/config.py` — P3-1, P3-2
- `src/edu_cloud/ai/registry.py` — P1-2（读 is_read_only）

## §2 P0：真实 Bug（4 处）

### P0-1 OutputValidator 接线修复

**根因：** `runtime.py:173` 查找 `"data" in event.data`，但 `agent_loop.py:186` 发送的 tool_result 载荷是 `{"tool": tc.name, "result": legacy_result}`。key 不匹配导致 `collected_tool_results` 始终为空，OutputValidator 空转。

**修复：** 改 runtime 侧（不改 agent_loop，保护 INV-3 SSE 契约）。

```python
# runtime.py — 兼容读取 + 过滤 error payload
if event.type == "tool_result" and isinstance(event.data, dict):
    payload = event.data.get("result", event.data.get("data"))
    if payload is not None and not (isinstance(payload, dict) and "error" in payload):
        collected_tool_results.append(
            ToolResult(success=True, data=payload)
        )
```

**设计决策（Claude×GPT 共识）：**
- 改 runtime 消费侧而非 agent_loop 生产侧，因为 `{"tool", "result"}` 格式是 SSE 前端契约
- 兼容 fallback（先 "result" 再 "data"）降低未来事件载荷演化风险
- 过滤 error payload 防止 `{"error": "xxx 404"}` 中的数字被误当事实数据

### P0-2 并发批次截断修复

**根因：** `tool_executor.py:101` 只处理 `batch.calls[:MAX_TOOL_CONCURRENCY]`（MAX=10），无后续循环。超过 10 个并发工具调用静默丢弃。

**修复：** 分片循环处理全部调用。

```python
# tool_executor.py — 分片并发
for i in range(0, len(batch.calls), MAX_TOOL_CONCURRENCY):
    chunk = batch.calls[i:i + MAX_TOOL_CONCURRENCY]
    chunk_results = await asyncio.gather(
        *[self._executor.run_one(call, ctx) for call in chunk]
    )
    results.extend(chunk_results)
```

### P0-3 深层 merge

**根因：** `memory_store.py:39,185` 使用 `{**existing, **new}` 浅层合并，嵌套 dict 整体覆盖导致字段丢失。

**修复：** 引入 `_deep_merge()` 工具函数。

```python
def _deep_merge(base: dict, update: dict) -> dict:
    """递归合并字典。dict 递归，list/scalar/None 直接替换。返回新 dict。"""
    result = {**base}
    for k, v in update.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
```

**设计约束（GPT 建议）：**
- 必须返回新 dict，不原地修改（SQLAlchemy JSON 字段追踪对原地修改不稳定）
- 当前 facts 无 schema，全部 key 深合并；未来若有需整体替换的子树再加白名单

### P0-4 error_count 语义重构

**根因：** 当前 `error_count` 只统计 LLM 调用异常（agent_loop.py:136），不统计工具失败。reset 只在工具分支后（:190），直接回答成功路径不 reset。语义不清。

**修复：** 拆为两个独立计数器，按 turn 计。

| 计数器 | 递增条件 | reset 条件 | 熔断阈值 |
|--------|---------|-----------|---------|
| `llm_error_streak` | LLM 调用异常（try/except） | 任意成功 LLM 响应（含直接回答） | ≥ 3 |
| `tool_fail_streak` | 某轮工具执行**全部失败** | 某轮有任一工具成功 | ≥ 3 |

**设计决策（Claude×GPT 共识）：**
- 按 turn 计（非按单个工具），避免单 turn 多工具失败直接打满阈值
- "全部失败"才 +1，部分失败不计入（LLM 可能一次发多个探索性调用）
- 两个计数器独立，任一熔断即停止循环

## §3 P1：韧性增强（2 处）

### P1-1 LLM 分级重试

**位置：** `llm_adapter.py` 新增 `_request_with_retry()` 内部方法。

**策略：**

| 异常类型 | 重试次数 | 退避策略 | 说明 |
|---------|---------|---------|------|
| httpx.HTTPStatusError (429) | ≤ 3 | Retry-After header 或 指数退避 1s/2s/4s | 限流暂时 |
| httpx.HTTPStatusError (500-503) | ≤ 1 | 固定 1s | 服务端瞬时故障 |
| httpx.TimeoutException | ≤ 1 | 无退避 | 网络超时 |
| httpx.HTTPStatusError (4xx 非 429) | 0 | — | 请求本身有误 |
| httpx.RequestError (连接失败等) | ≤ 1 | 固定 1s | 网络层 |

**约束：**
- 复用 `config.py` 已有的 `LLM_MAX_RETRIES` / `LLM_TIMEOUT`，不新增硬编码常量
- 先实现 `chat()` 路径，`chat_stream()` 后续补齐（当前无实际调用点）
- 尊重 `Retry-After` header

### P1-2 工具执行超时

**位置：** `tool_executor.py` 的 `ToolExecutor.run_one()` 外层。

**策略：**

```python
timeout = 30 if spec.is_read_only else 60
try:
    result = await asyncio.wait_for(self._executor.run_one(call, ctx), timeout=timeout)
except asyncio.TimeoutError:
    result = ToolResult(success=False, error=f"工具执行超时({timeout}s)")
except asyncio.CancelledError:
    result = ToolResult(success=False, error="工具执行被取消")
```

**约束：**
- 使用 `ToolSpec.is_read_only` 字段（已存在于 registry.py:15）区分超时值
- CancelledError 是 BaseException，需单独捕获

## §4 P2：验证增强（3 处，依赖 P0-1）

### P2-1 验证结构化

**位置：** `grounded.py` 重构 `_extract_numbers()` 和 `_collect_numbers()`。

**设计：** 引入 `NumberToken` 数据类。

```python
@dataclass
class NumberToken:
    value: float
    unit: str       # "分"/"名"/"人"/"%"/""
    key_path: str   # "avg_score" / "pass_rate" / ""（响应文本中无 key）
```

**容差表（按 unit 分类）：**

| unit | 类型 | 容差 | 理由 |
|------|------|------|------|
| 分 | score | 0.5%（85 分允许 ±0.4） | 教育场景分数敏感 |
| 名/人/个/次/所/班/科/题/道 | count | 0（必须精确） | 整数不允许误差 |
| % | percentage | 2% | 允许四舍五入 |
| （无单位） | unknown | 5% | 宽松兜底 |

### P2-2 百分数转换条件化

**位置：** `grounded.py` 的 `_collect_numbers()` 递归。

**修复：** 递归时携带 `key_path` 参数，只在 key 包含 `rate`/`ratio`/`percent`/`及格`/`优秀`/`pass` 时做 `×100` 转换。

### P2-3 循环检测

**位置：** `agent_loop.py` 循环内部新增状态追踪。

**检测条件（四要素全部满足）：**
1. 相同工具名
2. 参数 canonicalize 后相同（sorted keys JSON serialize）
3. 连续出现
4. 上一次结果是失败且错误文本相同

**参数归一化：**
```python
def _canonicalize(value):
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(v) for v in value]
    return value

fingerprint = json.dumps(_canonicalize(tc.arguments), ensure_ascii=False, sort_keys=True)
```

**跳过时处理：**
- 复用现有 tool_result 事件形状：`{"tool": tc.name, "result": {"error": "skipped: duplicate tool call"}}`
- 不新增事件类型（守 INV-3）
- 必须追加 `role="tool"` 消息到上下文（GPT 指出：否则 LLM 上下文协议不完整）

**阈值：** 连续 3 次相同调用触发跳过。

## §5 P3：配置外提（2 处）

### P3-1 Tier 阈值

```python
# config.py
TIER_CONTEXT_THRESHOLDS: list[int] = [100_000, 30_000]  # [T1 下限, T2 下限]
```

`CapabilityProbe.__init__()` 接受 thresholds 参数注入，默认从 Settings 读取。

### P3-2 Router 关键词

```python
# config.py
MODEL_ROUTER_ADVANCED_KEYWORDS: list[str] | None = None  # None = 使用代码默认值
```

`ModelRouter` 优先使用 Settings 值，None 时 fallback 到代码内常量。启动时 log 当前生效关键词数。

## §6 不变量

| ID | 约束 | 验证方式 |
|----|------|---------|
| INV-1 | DataScope fail-closed 行为不变 | 现有 data_scope tests |
| INV-2 | 42 个工具签名和行为不变 | 现有 tool tests |
| INV-3 | SSE 事件格式不变 | P0-1 改 runtime 消费侧；P2-3 复用现有形状 |
| INV-4 | 1359 tests 全量通过 | 每批次完成后 `pytest --tb=short -q` |

## §7 实现顺序

```
P0-1 → P0-2 → P0-3 → P0-4 → P1-1 → P1-2 → P2-1 → P2-2 → P2-3 → P3-1 → P3-2
```

GPT 建议先修 P0 全部，再做 P1。P2 验证增强依赖 P0-1（接线修复后验证才生效）。

## §8 移除项

| 原编号 | 原内容 | 移除原因 |
|--------|--------|---------|
| 1.3 | SSE finally 无异常保护 | ai.py:220-233 已有 try/except（GPT 验证） |

## §9 审查来源

- Claude: 代码审计（agent_loop/runtime/tool_executor/grounded/memory_store/llm_adapter/ai.py）
- GPT 5.4: codex-review consult（2 轮，thread 019d6266），独立读取代码验证
- 两轮讨论达成共识，GPT 发现 2 个新 bug + 纠正 3 个设计错误
