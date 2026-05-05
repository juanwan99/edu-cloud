# edu-cloud 日志系统重构设计

> 创建日期: 2026-05-05
> 任务级别: T3（跨模块基础设施重构）
> 设计者: Claude × GPT 共识
> 状态: v2 终稿（GPT review 12 findings 已整合）

---

## 1. 问题陈述

### 用户核心需求
"我必须依靠详细的日志定位问题、排查问题。日志必须持久化，必须特别容易查询。前端日志是重点。"

### 当前痛点

| # | 痛点 | 根因 | 影响 |
|---|------|------|------|
| 1 | 日志 3-5 天后消失 | 10MB×5 轮转 = 50MB 总量 | 无法调查一周前报告的问题 |
| 2 | 查日志要 SSH+jq 拼命令 | 无查询工具，纯文件扫描 | Claude 排查效率低 |
| 3 | 前端错误不可见 | 零上报机制 | 用户看到报错，开发者看不到 |
| 4 | HTTP→Worker 链路断裂 | arq 不继承 request context | 无法追踪"谁触发了失败的任务" |
| 5 | LLM 重试/超时静默 | `_post_with_retry` 无日志 | AI 阅卷失败时无法定位原因 |
| 6 | 业务事件不记录 | 只有技术日志，无状态变更日志 | 分数被改了不知道谁改的 |
| 7 | 无慢操作预警 | 没有 duration 阈值检查 | 问题从"慢"恶化到"挂"才发现 |

---

## 2. 设计目标

| 维度 | 目标 | 验收标准 |
|------|------|---------|
| 持久化 | 120 天可追溯 | 90 天前的日志可通过 `edu-log` 查到 |
| 可查询 | 任意 ID 秒级定位 | `edu-log trace <id>` 3 秒内返回完整链路 |
| 前端覆盖 | 前端错误自动上报 | API 失败/JS 异常/路由错误均可在后端日志中查到 |
| 全链路 | 一个 trace_id 串联全部 | 浏览器→HTTP→Worker→LLM 一条命令拉出 |
| 自包含 | 每条日志可独立理解 | 不需要跨文件 join 就能定位问题 |
| 低开销 | 不影响业务性能 | 日志写入异步，fail-open |

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser (Vue 3)                                                     │
│  clientLogger.js → batch 5s / error 立即 → POST /api/v1/client-logs │
│  X-Trace-ID / X-Request-ID 注入每个 API 请求                         │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  FastAPI Middleware                                                   │
│  trace_id + req_id + user_id + school_id → ContextVar 全局注入       │
│  请求完成 → layer=request 日志                                       │
│  慢请求(>1s) → layer=alert 日志                                      │
└──────────────┬──────────────────────┬───────────────────────────────┘
               │                      │
┌──────────────▼────────┐  ┌──────────▼────────────────────────────────┐
│  业务模块              │  │  arq Worker                               │
│  business_event() →   │  │  继承 trace_id/user_id/school_id          │
│  layer=business       │  │  layer=worker                             │
└──────────────┬────────┘  └──────────┬────────────────────────────────┘
               │                      │
               │           ┌──────────▼────────────────────────────────┐
               │           │  LLM 调用层                                │
               │           │  每次调用/重试/完成 → layer=llm            │
               │           └───────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────────┐
│  进程分文件 + 统一 Schema（F001/F002/F006/F012 修复）                 │
│                                                                       │
│  logs/api/edu-api-YYYY-MM-DD.NNN.jsonl      ← API 进程（64MB roll）   │
│  logs/worker/edu-worker-YYYY-MM-DD.NNN.jsonl ← Worker 进程（64MB roll）│
│  logs/business/edu-biz-YYYY-MM-DD.jsonl     ← 业务事件独立归档        │
│                                                                       │
│  edu-log 统一查询时自动合并 api/ + worker/ + business/ 目录           │
│  ├─ 14 天内：原始 JSONL（热查询，jq 直接扫描）                        │
│  ├─ 14-120 天：gzip 压缩（edu-log 自动 zcat）                         │
│  ├─ api/worker: >120 天删除                                           │
│  └─ business: 保留 365 天（分数争议可追溯）                            │
│                                                                       │
│  SQLite 索引: Phase 3 可选加速（v1 用 daily file + jq）               │
└──────────────────────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────────┐
│  edu-log CLI 查询工具                                                │
│  edu-log trace / req / user / exam / frontend / llm / slow / tail    │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 统一日志 Schema

所有日志共享基础字段（必填）：

```json
{
  "v": 1,
  "ts": "2026-05-05T14:03:22.184+08:00",
  "level": "info",
  "layer": "request",
  "event": "http.request.completed",
  "msg": "POST /api/v1/grading/tasks 201 423ms",
  "service": "edu-cloud",
  "logger": "edu_cloud.api.app",
  "trace_id": "tr_a3f9e2c1d4b5",
  "req_id": "rq_7x8k2m",
  "user_id": "u_123",
  "school_id": "sch_456",
  "duration_ms": 423
}
```

Layer 扩展字段：

| Layer | 必填扩展字段 | 可选扩展字段 |
|-------|-------------|-------------|
| `request` | method, path, status_code | client_ip, bytes_out, route_name |
| `client` | client_session_id, page_route, event_type | component, stack, api_path, api_status, browser, build_id |
| `worker` | job_id, job_func | task_id, exam_id, subject_id, batch_num, completed, failed, total |
| `llm` | provider, model, attempt, max_retries | slot, input_tokens, output_tokens, finish_reason, answer_id, question_id, retry_after_ms |
| `business` | action, entity_type, entity_id | old_state, new_state, fields_changed, reason, operator_id |
| `alert` | rule, threshold, actual_value | — |
| `app` | — | module, detail |

### 3.3 Layer 定义与触发条件

| Layer | 用途 | 触发点 |
|-------|------|--------|
| `request` | HTTP 请求生命周期 | 中间件自动 |
| `client` | 前端错误/行为/性能 | 前端 clientLogger 上报 |
| `worker` | 后台任务生命周期 | Worker 函数内 |
| `llm` | LLM API 调用链 | llm_adapter / gemini_client |
| `business` | 业务状态变更 | 手动调用 `business_event()` |
| `alert` | 阈值触发的预警 | 自动（中间件/Worker/LLM） |
| `app` | 通用应用日志 | `logger.info/warning/error` |

---

## 4. 前端日志系统（重点）

### 4.1 架构

```javascript
// frontend/src/utils/clientLogger.js

class ClientLogger {
  constructor() {
    this.queue = []
    this.sessionId = crypto.randomUUID()
    this.flushInterval = setInterval(() => this.flush(), 5000)
    this._restoreQueue()  // 从 localStorage 恢复未发送的事件
  }

  // 采集类型
  apiError(err, config)     // Axios 拦截器触发
  jsError(error, info)      // window.onerror / Vue errorHandler
  routeError(error, to)     // router.onError
  slowApi(config, duration) // API 响应 >3000ms
  pageView(route)           // 路由变化
  userAction(action, data)  // 关键操作（登录/提交分数/开始阅卷）

  // 发送策略
  enqueue(event)            // 入队
  flush()                   // 批量发送（fetch）
  flushBeacon()             // 页面关闭时（sendBeacon）
  _persistQueue()           // 保存到 localStorage（保底）
  _restoreQueue()           // 加载上次未发送的
}
```

### 4.2 采集点

| 采集点 | 触发条件 | 发送策略 | 字段 |
|--------|---------|---------|------|
| API 失败 | Axios 响应 status >= 400（非 401） | 立即发送 | api_path, api_method, api_status, error_message, req_id |
| JS 异常 | window.onerror / unhandledrejection | 立即发送 | message, stack, filename, line, column |
| Vue 组件错误 | app.config.errorHandler | 立即发送 | component, message, stack |
| 路由错误 | router.onError | 立即发送 | from_route, to_route, error |
| 慢 API | 响应时间 > 3000ms | 入队批量 | api_path, duration_ms |
| 页面访问 | router.afterEach | 入队批量 | page_route, prev_route |
| 关键操作 | 手动埋点 | 入队批量 | action, context |

### 4.3 前端→后端协议

**端点**: `POST /api/v1/client-logs`

**请求体**:
```json
{
  "client_session_id": "uuid-v4",
  "build_id": "__BUILD_ID__",
  "events": [
    {
      "ts": "2026-05-05T14:03:22.184+08:00",
      "level": "error",
      "event_type": "api_error",
      "page_route": "/grading/tasks",
      "trace_id": "tr_xxx",
      "data": {
        "api_path": "/api/v1/grading/tasks",
        "api_method": "POST",
        "api_status": 500,
        "error_message": "Internal Server Error",
        "req_id": "rq_echoed_from_response"
      }
    }
  ]
}
```

**后端处理**:
- 从 JWT 解析 user_id/school_id（前端不传，防伪造）
- 每个 event 写入统一日志流，layer=client
- 限流：单 session 最多 100 events/min
- 不记录 /api/v1/client-logs 自身的请求日志（防循环）

### 4.4 Trace ID 传播

```javascript
// frontend/src/api/client.js — 请求拦截器
client.interceptors.request.use(config => {
  const traceId = getOrCreateTraceId()  // 页面级复用
  const reqId = `rq_${crypto.randomUUID().slice(0, 12)}`
  config.headers['X-Trace-ID'] = traceId
  config.headers['X-Request-ID'] = reqId
  config._meta = { traceId, reqId, startTime: Date.now() }
  return config
})

// 响应拦截器 — 记录时间 + 捕获服务端 req_id
client.interceptors.response.use(
  res => {
    const duration = Date.now() - res.config._meta.startTime
    if (duration > 3000) {
      clientLogger.slowApi(res.config, duration)
    }
    return res
  },
  err => { /* ... error reporting ... */ }
)
```

---

## 5. 全链路追踪设计

### 5.1 ID 体系

| ID | 生成位置 | 生命周期 | 格式 |
|----|---------|---------|------|
| `trace_id` | 前端（每次页面操作）或中间件（无前端时） | 一次用户操作的完整链路 | `tr_` + 12 hex |
| `req_id` | 前端或中间件 | 单个 HTTP 请求 | `rq_` + 12 hex |
| `job_id` | arq 自动生成 | 单个后台任务 | arq UUID |
| `llm_call_id` | LLM 调用层 | 单次 LLM API 调用（含重试） | `lc_` + 12 hex |

### 5.2 跨边界传播

```
浏览器操作 → trace_id=tr_abc (前端生成)
  │
  ├─ API 请求 → req_id=rq_111, trace_id=tr_abc (HTTP Header)
  │    │
  │    └─ 中间件: ContextVar 注入 trace_id + req_id + user_id + school_id
  │         │
  │         ├─ 业务逻辑日志: 自动携带 trace_id + req_id
  │         │
  │         └─ enqueue_grading_task(task_id, trace_ctx={trace_id, req_id, user_id, school_id})
  │              │
  │              └─ arq Worker: 从 trace_ctx 恢复 ContextVar
  │                   │
  │                   ├─ Worker 日志: 携带 trace_id + req_id + job_id
  │                   │
  │                   └─ LLM 调用: llm_call_id=lc_222, 携带 trace_id
  │                        │
  │                        ├─ 重试日志: trace_id + llm_call_id + attempt
  │                        └─ 完成日志: trace_id + llm_call_id + tokens + duration
  │
  ├─ API 请求 2 → req_id=rq_222, trace_id=tr_abc (同一 trace)
  │
  └─ 前端错误 → client log with trace_id=tr_abc
```

### 5.3 arq 任务 Context 传播实现

```python
# enqueue 时保存 context
async def enqueue_grading_task(task_id: str) -> None:
    trace_ctx = {
        "trace_id": trace_id_var.get(),
        "req_id": request_id_var.get(),
        "user_id": current_user_var.get(),
        "school_id": current_school_var.get(),
    }
    await redis.enqueue_job("process_grading_task", task_id, _trace_ctx=trace_ctx)

# Worker 入口恢复 context
async def process_grading_task(ctx: dict, task_id: str, *, _trace_ctx: dict = None) -> None:
    if _trace_ctx:
        trace_id_var.set(_trace_ctx.get("trace_id", "-"))
        request_id_var.set(_trace_ctx.get("req_id", "-"))
        current_user_var.set(_trace_ctx.get("user_id"))
        current_school_var.set(_trace_ctx.get("school_id"))
    # ... 后续所有日志自动携带 trace context
```

---

## 6. LLM 调用日志

### 6.1 日志点

每次 LLM 调用产生 1-4 条日志：

```
llm.call.start     → 调用开始（model, slot, timeout, answer_id/question_id）
llm.call.retry     → 重试（attempt, reason: 429/5xx/timeout, retry_after_ms）
llm.call.completed → 成功（duration_ms, input_tokens, output_tokens, finish_reason）
llm.call.failed    → 最终失败（attempts_total, last_error, elapsed_total_ms）
```

### 6.2 实现位置

| 文件 | 改动 |
|------|------|
| `ai/llm_adapter.py` `_post_with_retry()` | 每次 retry 记 WARNING，最终失败记 ERROR |
| `modules/grading/gemini_client.py` `_generate()` | 调用开始记 INFO，成功/失败记结果 |
| `modules/grading/llm_client.py` | 同上模式 |

### 6.3 示例日志

```json
{
  "v": 1, "ts": "...", "level": "warning", "layer": "llm",
  "event": "llm.call.retry",
  "msg": "LLM retry: 429 rate limited, backing off 4s",
  "trace_id": "tr_abc", "req_id": "rq_111",
  "llm_call_id": "lc_222",
  "provider": "gemini", "model": "gemini-2.5-flash",
  "slot": "grading-main", "attempt": 2, "max_retries": 3,
  "reason": "429", "retry_after_ms": 4000,
  "task_id": "task_789", "answer_id": "ans_456"
}
```

---

## 7. 业务事件日志

### 7.1 Helper API

```python
# src/edu_cloud/logging_config.py 新增

def business_event(
    action: str,
    entity_type: str,
    entity_id: str,
    *,
    old_state: str | None = None,
    new_state: str | None = None,
    fields_changed: dict | None = None,
    reason: str | None = None,
    **extra,
) -> None:
    """记录业务状态变更事件。"""
    logger = logging.getLogger("edu_cloud.business")
    logger.info(
        "%s %s %s: %s → %s",
        action, entity_type, entity_id, old_state, new_state,
        extra={
            "_layer": "business",
            "_event": f"business.{action}",
            "_data": {
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "old_state": old_state,
                "new_state": new_state,
                "fields_changed": fields_changed,
                "reason": reason,
                **extra,
            }
        }
    )
```

### 7.2 必须记录的业务事件

| 事件 | action | entity_type | 触发位置 |
|------|--------|------------|---------|
| 考试状态流转 | `state_change` | `exam` | `exam/publish_service.py` |
| 分数修改（AI→教师确认） | `score_override` | `grading_result` | `grading/grading_review_router.py` |
| 分数修改（教师批注） | `annotation_save` | `grading_result` | `grading/grading_review_router.py` |
| 阅卷任务创建 | `task_create` | `grading_task` | `grading/router.py` |
| 权限拒绝 | `permission_denied` | `user` | `api/deps.py` |
| 学生导入 | `bulk_import` | `student` | `student/router.py` |
| 教师导入 | `bulk_import` | `teacher` | `student/teacher_router.py` |
| 德育加减分 | `points_add` | `conduct_record` | `conduct/admin_router.py` |
| 学校模块开关 | `module_toggle` | `school_module` | `school/settings_router.py` |
| 用户登录 | `login` | `user` | `api/auth.py` |
| 登录失败 | `login_failed` | `user` | `api/auth.py` |

---

## 8. 慢操作 Alert

### 8.1 阈值规则

| 规则 | 阈值 | Layer | Level |
|------|------|-------|-------|
| HTTP 请求慢 | > 1000ms | alert | WARNING |
| HTTP 请求极慢 | > 5000ms | alert | ERROR |
| 前端 API 慢 | > 3000ms | client | WARNING |
| LLM 单次调用慢 | > 60000ms | alert | WARNING |
| Worker 单答卷处理慢 | > 120000ms | alert | WARNING |
| Worker 整任务超时 | > 900000ms (15min) | alert | ERROR |

### 8.2 实现

Alert 日志在正常日志之外额外产出，不替代原日志：

```json
{
  "v": 1, "ts": "...", "level": "warning", "layer": "alert",
  "event": "alert.slow_request",
  "msg": "Slow request: POST /api/v1/analytics/report/query 4523ms",
  "rule": "http_slow", "threshold": 1000, "actual_value": 4523,
  "trace_id": "tr_abc", "req_id": "rq_111",
  "method": "POST", "path": "/api/v1/analytics/report/query"
}
```

---

## 9. 存储与保留策略

### 9.1 文件命名与滚动

```
logs/
  edu-2026-05-05.000.jsonl      ← 当天第一卷（≤256MB）
  edu-2026-05-05.001.jsonl      ← 当天第二卷
  edu-2026-05-04.000.jsonl.gz   ← 昨天已压缩
  edu-2026-05-03.000.jsonl.gz
  ...
  index.db                       ← SQLite 索引
```

### 9.2 保留策略

| 时间段 | 状态 | 保留规则 |
|--------|------|---------|
| 0-14 天 | 热（原始 JSONL） | 直接 jq/grep 可查 |
| 14-120 天 | 冷（gzip 压缩） | edu-log 自动解压查询 |
| 120-365 天 | 仅 business 层 | 分数争议追溯 |
| > 365 天 | 删除 | — |

### 9.3 容量估算

| 场景 | 日产量（原始） | 日产量（gzip） | 120 天总量 |
|------|-------------|-------------|-----------|
| 平日（10 用户）| 80-150 MB | 15-30 MB | 2-4 GB |
| 阅卷高峰（50 用户 + 1000 LLM/h）| 300-650 MB | 60-130 MB | 8-16 GB |
| 估算上限 | — | — | **12 GB** |

### 9.4 磁盘保护

```
≥ 85% 日志分区占用 → 强制压缩所有 >1 天的日志
≥ 90% → 删除 >90 天的非 business 日志
≥ 95% → 删除 >30 天的 app/request 日志，保留 business/alert
≥ 98% → 停止 DEBUG/INFO 写入，仅写 WARNING+
```

日志写入 **fail-open**：写失败不阻塞业务请求。一分钟内最多输出一次 stderr 告警。

---

## 10. edu-log 查询工具

### 10.1 命令清单

```bash
# 链路追踪（最常用）
edu-log trace tr_abc123                    # 按 trace_id 拉完整链路
edu-log req rq_7x8k2m                      # 按 request_id 查单请求

# 按实体查询
edu-log user u_123 --since 7d              # 某用户 7 天操作
edu-log exam exam_456 --level error        # 某考试的错误
edu-log task task_789                      # 某阅卷任务全链路

# 按 Layer 过滤
edu-log frontend --since 24h              # 前端日志
edu-log llm --since 24h --level error     # LLM 错误
edu-log business --since 30d --action score_override  # 分数修改记录

# 性能/告警
edu-log slow --over 3000 --since 24h      # 慢操作
edu-log alerts --since 7d                 # 所有 alert

# 实时
edu-log tail                              # 实时全部
edu-log tail --layer llm --level warning  # 实时 LLM 警告

# 维护
edu-log stats                             # 日志统计（文件数/大小/索引状态）
edu-log rebuild-index                     # 重建 SQLite 索引
```

### 10.2 输出格式

**默认（compact）**:
```
14:03:22 INFO  request  POST /api/v1/grading/tasks 201 423ms  tr=tr_abc req=rq_111 user=u_123
14:03:22 INFO  worker   grading_task START task=task_789      tr=tr_abc job=job_xxx
14:03:25 WARN  llm      retry: 429 backing off 4s            tr=tr_abc lc=lc_222 attempt=2
14:03:30 INFO  llm      completed: 2.1s 850+120tok           tr=tr_abc lc=lc_222 model=gemini-flash
14:03:45 INFO  worker   grading_task DONE 35/35 elapsed=23s  tr=tr_abc job=job_xxx
```

**--jsonl（机器可解析）**:
```json
{"v":1,"ts":"...","level":"info","layer":"request","event":"http.request.completed",...}
```

**--verbose（全字段展开）**:
```yaml
---
ts: 2026-05-05T14:03:22.184+08:00
level: info
layer: request
event: http.request.completed
trace_id: tr_abc123
req_id: rq_7x8k2m
user_id: u_123
school_id: sch_456
method: POST
path: /api/v1/grading/tasks
status_code: 201
duration_ms: 423
---
```

### 10.3 SQLite 索引结构

```sql
CREATE TABLE log_index (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,          -- ISO 8601
    level TEXT NOT NULL,       -- info/warning/error
    layer TEXT NOT NULL,       -- request/client/worker/llm/business/alert/app
    event TEXT,                -- 事件类型
    trace_id TEXT,
    req_id TEXT,
    user_id TEXT,
    school_id TEXT,
    exam_id TEXT,
    task_id TEXT,
    file_path TEXT NOT NULL,   -- 日志文件路径
    byte_offset INTEGER,       -- 行在文件中的偏移（仅未压缩文件有效）
    line_no INTEGER            -- 行号
);

CREATE INDEX idx_trace ON log_index(trace_id);
CREATE INDEX idx_req ON log_index(req_id);
CREATE INDEX idx_user_ts ON log_index(user_id, ts);
CREATE INDEX idx_exam ON log_index(exam_id);
CREATE INDEX idx_task ON log_index(task_id);
CREATE INDEX idx_level_ts ON log_index(level, ts);
CREATE INDEX idx_layer_ts ON log_index(layer, ts);
```

索引器作为后台进程 tail 日志文件，每 5 秒批量写入索引。

---

## 11. 实施计划

### Phase 1: 后端核心（优先级最高）

| # | 任务 | 文件 | 复杂度 |
|---|------|------|--------|
| 1.1 | 重写 logging_config.py（日滚 + 统一 schema + ContextVar 扩展） | `src/edu_cloud/logging_config.py` | 高 |
| 1.2 | 中间件增强（trace_id 生成 + school_id 提取 + 慢请求 alert） | `src/edu_cloud/api/app.py` | 中 |
| 1.3 | 新增 ContextVar: trace_id_var, school_id_var | `src/edu_cloud/logging_config.py` | 低 |
| 1.4 | LLM 适配器加日志（重试/超时/完成） | `src/edu_cloud/ai/llm_adapter.py` | 低 |
| 1.5 | Gemini client 加日志 | `src/edu_cloud/modules/grading/gemini_client.py` | 低 |
| 1.6 | arq 任务 trace context 传播 | `worker.py` + `workers/grading.py` + `grading/router.py` | 中 |
| 1.7 | 业务事件 helper + 首批埋点（10 个事件） | 多文件 | 中 |

### Phase 2: 前端日志系统

| # | 任务 | 文件 | 复杂度 |
|---|------|------|--------|
| 2.1 | clientLogger.js（采集器 + 批量发送 + localStorage 持久） | `frontend/src/utils/clientLogger.js` | 高 |
| 2.2 | client.js 改造（trace_id/req_id 注入 + 错误上报 + 慢 API） | `frontend/src/api/client.js` | 中 |
| 2.3 | main.js 接入（Vue errorHandler + window.onerror） | `frontend/src/main.js` | 低 |
| 2.4 | router 错误捕获 | `frontend/src/router/index.js` | 低 |
| 2.5 | 后端接收端点 | `src/edu_cloud/api/client_logs.py` | 中 |

### Phase 3: 查询工具与运维

| # | 任务 | 文件 | 复杂度 |
|---|------|------|--------|
| 3.1 | edu-log CLI 核心（trace/req/user/exam 查询） | `scripts/edu-log` | 高 |
| 3.2 | SQLite 索引器（后台 tail + 批量写入） | `scripts/edu-log-indexer` | 中 |
| 3.3 | 日志维护脚本（压缩/清理/磁盘保护） | `scripts/edu-log-maintain` | 中 |
| 3.4 | cron 配置（索引器 + 维护） | 系统 crontab | 低 |
| 3.5 | 运维文档 | `docs/ops/logging.md` | 低 |

### Phase 4: 补盲区

| # | 任务 | 文件 | 复杂度 |
|---|------|------|--------|
| 4.1 | adaptive 模块加日志 | `modules/adaptive/*.py` | 低 |
| 4.2 | studio 模块加日志 | `modules/studio/*.py` | 低 |
| 4.3 | menu 模块加日志 | `modules/menu/*.py` | 低 |
| 4.4 | answer_standardizer 异常日志 | `card/parser/answer_standardizer.py` | 低 |
| 4.5 | auto_detect_cv 超时日志 | `scan/auto_detect_cv.py` | 低 |

---

## 12. 迁移策略

### 向后兼容

- 旧 `logger.info("message")` 调用全部继续工作，自动被新 Formatter 包装为统一 schema
- 旧 `logs/app.jsonl` 路径保持 7 天过渡期，新日志同时写入新路径
- 现有 `logq` 工具（远程日志查询）保持兼容，后续指向 `edu-log`

### 不变量（ORC）

- 日志写入不得阻塞业务请求（fail-open）
- 日志格式向后兼容（v 字段标识版本）
- SQLite 索引是加速层，不是必须层（无索引时 edu-log 降级为 jq 扫描）
- 前端日志上报失败不影响用户操作（静默丢弃）

---

## 13. 现有资产盘点

| 资产 | 位置 | 处理方式 |
|------|------|---------|
| logging_config.py | `src/edu_cloud/logging_config.py` | 重写（保留 ContextVar 接口） |
| request middleware | `src/edu_cloud/api/app.py:249-293` | 增强（加 trace_id + school_id + alert） |
| RotatingFileHandler 配置 | logging_config.py:77 | 替换为日滚 TimedRotatingFileHandler 变体 |
| AI audit tables | `ai/models.py` (AiSession/AiToolCall) | 保留（与 JSONL 互补，不替代） |
| Worker 日志 | `workers/grading.py` 30+ statements | 保留增强（加 trace context） |
| config.py LOG_* 设置 | `src/edu_cloud/config.py` | 扩展（加 LOG_RETENTION_DAYS, LOG_MAX_GB, LOG_PATH） |

---

## 14. Evidence Block

**decision**: 进程分文件 JSONL + 统一 schema + Python CLI（SQLite 索引 Phase 3 可选）
**evidence_refs**:
  - 当前磁盘: 118G 总/48G 可用，12GB 日志预算充裕
  - 当前日志量: 35MB/logs/，日均 ~4MB（低负载期），高峰预估 300-650MB
  - `logging_config.py:77` — 现有 RotatingFileHandler 10MB×5
  - `api/app.py:249` — 现有中间件已有 req_id + user_id + duration 基础
  - `workers/grading.py:860` — Worker 入口已有 task_id，只需注入 trace_ctx
**Q2_excluded**:
  - Elasticsearch: 单机场景过重，需 2GB+ RAM；反证: 50 并发不需要分布式搜索
  - PostgreSQL 日志表: 混合 OLTP+日志会影响主库性能；反证: 已有 AiToolCall 表无性能问题但规模不同
  - 单物理文件: 多进程 rotation 不安全（F001）；反证: stdlib RotatingFileHandler 非进程安全
  - SQLite 同步写入: 日志写入不应依赖索引成功（F006）；反证: 索引损坏不应丢日志
**impact_scope**: system（跨所有模块的基础设施变更）
**unknowns**:
  - 高峰日 LLM 日志实际产量需验证（首周观察后调整 roll size）
**followup_spike**: Phase 1 上线后观察 7 天日志量，确认 64MB roll size 和 12GB cap 是否合适

---

## 15. GPT Review Findings 与修复决策

> Review by GPT-5.2-codex, 2026-05-05. 共 12 findings.

### 已整合到设计中的修复

| Finding | 级别 | 修复 |
|---------|------|------|
| F001: 单文件多进程不安全 | HIGH | 改为进程分文件（api/ + worker/），edu-log 合并查询 |
| F002: 统一文件无法按 layer 删除 | HIGH | business 事件独立归档到 `logs/business/`，保留 365 天 |
| F003: Worker 未调用 setup_logging() | HIGH | Phase 1.6 明确：arq on_startup 调用 setup_logging(process="worker") |
| F004: business_event() extra 字段不被提取 | HIGH | 新 Formatter 必须检查 record.__dict__ 中 _layer/_event/_data 并合并到 JSON |
| F005: ContextVar 无 finally reset | HIGH | trace context 设置必须用 try/finally + token.reset() |
| F006: SQLite 索引 v1 过度 | MED | 降级为 Phase 3 可选，v1 用 daily file + jq/zcat |
| F007: 前端多 client 遗漏 | HIGH | clientLogger 需 hook parentClient (conduct.js) + 全局 fetch 拦截 |
| F008: localStorage 跨用户风险 | MED | 只持久 error 队列，绑定 user_id + 30min TTL |
| F009: 敏感数据脱敏缺失 | HIGH | 日志只记 ID/timing/token count，不记学生姓名/答案文本/prompt 原文 |
| F010: CLI 命令需要的字段不在索引 | MED | v1 阶段高级查询降级为 jq scan；Phase 3 索引扩展字段 |
| F011: 无合约测试 | HIGH | Phase 1 必须包含：formatter 测试 + middleware 测试 + context reset 测试 |
| F012: 256MB roll 过大 | MED | 改为 64MB per file |

### 新增设计约束（源自 review）

1. **脱敏规则**：JSONL 禁止记录：学生全名、身份证号、手机号、答案原文（>50 字截断+hash）、LLM prompt 全文、图片 base64。只允许：entity_id、score 数值、token count、duration、error class+message（≤200 字符）。

2. **Worker logging bootstrap**：arq WorkerSettings 添加 `on_startup` hook：
   ```python
   async def startup(ctx):
       setup_logging(process="worker")
   ```

3. **ContextVar 安全模式**：所有 trace context 设置必须：
   ```python
   tokens = []
   try:
       tokens.append(trace_id_var.set(ctx["trace_id"]))
       tokens.append(request_id_var.set(ctx["req_id"]))
       # ... business logic ...
   finally:
       for t in tokens:
           t.var.reset(t)
   ```

4. **前端 sendBeacon 认证**：unload flush 无法携带 Authorization header → 端点对 sendBeacon 请求允许匿名（用 client_session_id 关联），后续索引时通过 session→user 映射补全 user_id。

5. **合约测试清单**（Phase 1 gate）：
   - [ ] _JSONLFormatter 正确提取 _layer/_event/_data 到 JSON 顶层
   - [ ] 中间件生成 trace_id 并写入响应头
   - [ ] ContextVar 在 exception 时正确 reset
   - [ ] Worker trace context 不泄漏到下一个 job
   - [ ] client-logs 端点拒绝 >100 events/min/session
   - [ ] client-logs 自身请求不产生 request 层日志（防循环）
   - [ ] business 事件同时写入主流和 business/ 归档
   - [ ] edu-log trace 能跨 api/ 和 worker/ 目录合并结果
