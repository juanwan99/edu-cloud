<!-- legacy-format -->
---
type: design
topic: shared-ai-grading
created: 2026-04-18 13:35:00
status: draft (Planner 骨架，待用户拍板关键设计点后扩写)
T-level: T3
related_design: docs/plans/2026-04-12-grading-dispatch-design.md（云端 grading worker 已实现）
related_endpoint: src/edu_cloud/api/compat_router.py（学校→云端 8 端点已实现，可扩展）
parent_initiative: V4 §3.3 Sprint 2 设计 plan B-1（CLAUDE.md 项目定位"算力不足学校上传切图到云端阅卷"承诺补完）
---

# 共享 AI 阅卷设计 · B-1 · 骨架版

> Planner 自写设计 plan 骨架（V3 §1 + V4 §3.3 资源分配："设计 plan 写作不消耗 worktree slot"）。
> 本骨架完成 §0-§5 关键设计点 + Phase/Task 估算 + §7 待用户拍板。
> 详细 spec（API schema / 数据模型 / 测试矩阵 / Risk Pack）留 Sprint 2 后续 session 完善。

---

## §0. 一句话定位

CLAUDE.md 项目定位段第 4 行"算力不足的学校可上传切图到云端阅卷"承诺补完——学校端无 GPU/无 LLM 配额时，将扫描切图上传到 edu-cloud，复用 grading worker 阅卷，结果回传学校端。

---

## §1. 业务背景 + Goal + Non-Goals

### 1.1 业务痛点

CLAUDE.md "实现状态" 表 API 行明写"共享 AI 阅卷"为"未实现"。当前学校端（exam-ai）必须本地部署 LLM slot 才能跑 AI 阅卷。算力不足的小学校（无 GPU）卡在阅卷环节。

### 1.2 Goal

提供 edu-cloud 侧的"代阅卷"能力：学校上传切图 → 云端 worker 阅卷 → 学校拉取/接收结果。

### 1.3 Non-Goals

- ❌ 不替换学校端本地阅卷能力（学校仍可用本地 LLM slot，共享是兜底而非默认）
- ❌ 不引入计费体系（v1 按"参与校"白名单授权，无量化计费）
- ❌ 不支持跨学校学生数据混阅（每个 grading job 仍隔离学校 scope）
- ❌ 不动 grading worker 内部算法（复用现有 `process_grading_task`）

---

## §2. 现状盘点（实证 grep 2026-04-18 13:34）

### 2.1 grading 模块（14 端点已实现）

```
src/edu_cloud/modules/grading/
├── router.py             — 11 端点（rubrics CRUD / tasks CRUD / results / review / dispatch/status）
├── assignment_router.py  — 3 端点（assignments + progress）
├── quality_router.py     — 1 端点（quality-report）
├── models.py             — Rubric / GradingTask / GradingResult / GradingAssignment
├── prompts.py            — LLM 阅卷 prompt 模板
├── llm_client.py         — LLMClient 适配器
└── MODULE.md             — 模块治理文档
```

### 2.2 grading worker（已实现 arq 调度）

`src/edu_cloud/workers/grading.py`：
- `process_grading_task(task_id)`：从 Redis 取 task → 微批次并发 → LLM 评分 → 写 GradingResult
- 配置：`GRADING_BATCH_SIZE=20` / `LLM_TIMEOUT=180s` / `LLM_MAX_RETRIES`
- 输入：`StudentAnswer.image_path`（学校已上传切图）
- 输出：GradingResult（score + feedback + raw_llm_response）

### 2.3 compat_router 8 端点（学校→云端已开通）

`src/edu_cloud/api/compat_router.py`：
- `/api/auth/login` 学校 API Key 认证
- `/api/scan/upload`（POST，已有）：学校上传切图（multipart）→ 写 StudentAnswer
- `/api/scan/upload-objective`：学校上传选择题结果（自动判分）
- 其他 5 端点（exams / subjects / templates / scan/tasks）

### 2.4 关键基础设施可复用清单

| 基础设施 | 来源 | 复用方式 |
|---|---|---|
| LLM 调用 | `grading/llm_client.py` | 直接复用（学校共享云端 LLM slot）|
| 切图存储 | `/storage/scan/` + StudentAnswer.image_path | 学校上传走 compat_router `/api/scan/upload` |
| 阅卷调度 | arq worker `process_grading_task` | 创建 GradingTask → enqueue 即可 |
| 学校鉴权 | API Key（schools.api_key_hash） | compat_router 已用，shared-grading 沿用 |
| Rubric 评分规则 | grading/models.Rubric | 学校上传 rubric（POST /rubrics 已有），共享场景同样需要 |

---

## §3. 架构概要（待用户拍板细节）

### 3.1 高层流程

```
[学校端 exam-ai]                              [edu-cloud 云端]
  1. 扫描完成，本地无 LLM
        ↓
  2. POST /api/scan/upload (现有 compat) ─→  StudentAnswer 持久化
        ↓                                       ↓
  3. POST /api/grading/shared-request      ─→ 创建 GradingTask
        ↓ (返回 task_id)                       ↓ enqueue arq
                                               ↓
                                          [grading worker]
                                          process_grading_task()
                                               ↓ LLM 评分
                                          GradingResult 写入
                                               ↓
  4. GET /api/grading/shared-result/{task_id}  ←─ 学校轮询
     OR webhook 回调（如学校配 callback_url） ←─
        ↓
  5. 学校端导入 GradingResult → 本地考试结果
```

### 3.2 核心新增 API（v1 草案）

| 方法 | 路径 | 用途 | 鉴权 |
|---|---|---|---|
| POST | `/api/grading/shared-request` | 学校发起共享阅卷请求 | API Key (学校) |
| GET | `/api/grading/shared-result/{task_id}` | 学校轮询阅卷结果 | API Key + task 归属校 |
| POST | `/api/grading/shared-cancel/{task_id}` | 学校取消进行中任务 | API Key + task 归属校 |
| GET | `/api/grading/shared-quota` | 查学校配额（v2 ready）| API Key |

### 3.3 数据模型（待 §7 拍板再细化）

候选新表 `shared_grading_request`：
- school_id (FK), exam_id (引用学校端 exam_id), task_id (FK→GradingTask)
- callback_url (Optional, webhook), status (pending/processing/completed/failed/cancelled)
- created_at, completed_at, latency_ms
- 唯一约束：school_id + exam_id + 学校端 task_idempotency_key

---

## §4. 关键设计点（待 §7 拍板）

| ID | 设计问题 | 候选方案 |
|---|---|---|
| **D-1** | 端点路径前缀 | A. 扩展 compat_router (`/api/grading/shared-*`) ／ B. 新建 `/api/v1/shared-grading/*` |
| **D-2** | 结果回传机制 | A. 仅轮询 ／ B. 仅 webhook ／ C. 双模式（学校配 callback_url 走 webhook，否则轮询）|
| **D-3** | 鉴权层 | A. 沿用 API Key ／ B. 加 grading-specific token |
| **D-4** | 并发限流 | A. 全局 GRADING_BATCH_SIZE 共享 ／ B. 按校配额 ／ C. 按 LLM slot tier 区分 |
| **D-5** | Rubric 来源 | A. 学校随请求上传 ／ B. 学校预先 POST /rubrics 后引用 rubric_id ／ C. 双模式 |
| **D-6** | 配额/计费 | v1 白名单授权（schools.shared_grading_enabled flag），v2 计量 |
| **D-7** | 失败重试 | A. 学校自行重发 ／ B. 云端自动重试（max_retries=3）|

---

## §5. Phase / Task 估算（T3，~10-15 task / 2-3 batch）

### Batch 1: API 端点 + 数据模型（4-5 task，~2-3h）

- Task 1：`shared_grading_request` 表 + Alembic migration
- Task 2：`/api/grading/shared-request` 端点 + 校归属校验 + GradingTask 创建
- Task 3：`/api/grading/shared-result/{task_id}` 端点 + 鉴权
- Task 4：`/api/grading/shared-cancel` 端点
- Task 5：单元测试 + 端到端测试（学校 mock）

### Batch 2: Worker 集成 + Webhook（3-4 task，~2h）

- Task 6：worker 完成时触发 webhook（如配 callback_url）
- Task 7：Webhook 重试 + 签名校验
- Task 8：异步任务监控 + 失败上报
- Task 9：集成测试

### Batch 3: 配额管理 + 文档（3-4 task，~2h）

- Task 10：`schools.shared_grading_enabled` flag + 配额检查
- Task 11：`/api/grading/shared-quota` 端点 + 用量统计
- Task 12：MODULE.md 补全 + CLAUDE.md "未实现端点"段移除
- Task 13：端到端测试 + 学校端 SDK 草案（exam-ai 侧文档）

**总估时**：6-7h（T3，3 batch × 2-2.5h）

---

## §6. 测试策略 + 风险（骨架占位）

### 6.1 测试策略
- 单元：API 端点参数 + 鉴权 + 状态机
- 集成：完整流程（mock 学校 client → upload → request → poll/webhook）
- 入口级：学校 API Key 越权 + task_id 归属校检查

### 6.2 主要风险
- **R-1 LLM 配额竞争**：共享阅卷与本校阅卷共用 LLM slot，需限流
- **R-2 切图存储成本**：学校大量上传切图，需 quota 或 TTL
- **R-3 鉴权扩散**：API Key 既能查考试又能阅卷，需细化 scope
- **R-4 学校端 SDK 缺失**：exam-ai 侧需配套客户端（本设计 Out of Scope，需独立 plan）

---

## §7. 待用户拍板项（设计完成前必决）

> Planner 推荐方案标 ✅，理由附在每项下。

| ID | 推荐 | 待用户 ACK |
|---|---|---|
| **D-1 端点前缀** | ✅ A. 扩展 compat_router（学校客户端已习惯 `/api` 前缀，零改造对接）| A / B |
| **D-2 结果回传** | ✅ C. 双模式（webhook 优先 + 轮询兜底，覆盖 NAT/firewall 学校）| A / B / C |
| **D-3 鉴权** | ✅ A. 沿用 API Key（最小变更，已 verified）| A / B |
| **D-4 并发限流** | ✅ B. 按校配额（v1 简化为 max_concurrent=N，v2 加 daily_quota）| A / B / C |
| **D-5 Rubric 来源** | ✅ C. 双模式（小考随请求上传，正式考用 rubric_id）| A / B / C |
| **D-6 配额** | v1 白名单（无量化）| 接受 / 改 |
| **D-7 重试** | ✅ B. 云端自动重试（max_retries=3，超过通知学校）| A / B |
| **D-8 优先级** | 与 B-7 haofenshu Batch 3 / B-2 统一题库 / B-3 跨校分析谁先？| 给序 |

---

## §8. 后续完善清单（待 Sprint 2 后续 Planner session）

1. ⏳ 用户 §7 拍板后扩写 §3.3 数据模型完整 schema
2. ⏳ §5 各 Task 拆 testable slice + 入口级测试矩阵
3. ⏳ §6 风险 R-1/R-2 缓解方案（quota / TTL）
4. ⏳ Contract Pack（invariants / counter_examples / risk_modules / test_debt）
5. ⏳ Gate 1 codex-review plan（Plan Review）
6. ⏳ exam-ai 侧 SDK 草案（独立 plan，不在本设计范围）

---

## §9. 关联设计（参考）

- `docs/plans/2026-04-12-grading-dispatch-design.md` — 云端 grading worker 已实现的全流程改造（10T/1B）
- `src/edu_cloud/modules/grading/MODULE.md` — grading 模块治理文档
- CLAUDE.md "项目定位" + "实现状态" + "未实现端点（规划中）" 三段
