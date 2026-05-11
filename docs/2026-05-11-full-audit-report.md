# edu-cloud 全项目深度审查报告

> **审计日期**: 2026-05-11
> **审计方法**: Claude Opus 5 路并行深度审查 + GPT-5.5 独立交叉验证
> **版本基线**: `9b424a9` (master)
> **对比基线**: 2026-05-08 健康度审计 (`docs/2026-05-08-health-audit-claude-gpt.md`)
> **审查范围**: edu-cloud (19.3万行) + paper-seg (4.5K行) + answer-card-editor (720行)
> **测试基线**: 后端 2504 passed / 43 failed / 23 skipped; 前端 2496 passed / 0 failed

---

## 审查维度（12 项）

| # | 维度 | 代理 | 覆盖状态 |
|---|------|------|---------|
| 1 | 架构（层级依赖/模块边界） | arch-audit | Done |
| 2 | 技术债（TODO/HACK/遗留） | debt-audit | Done |
| 3 | Bug 隐患（竞态/边界/异常吞没） | business-bug-audit | Done |
| 4 | 业务通道阻塞（流程断点） | business-bug-audit | Done |
| 5 | 冗余与死代码 | debt-audit | Done |
| 6 | 数据层健康（drift/约束/CASCADE） | data-security-audit | Done |
| 7 | 依赖健康 | perf-deps-audit | Done |
| 8 | 性能瓶颈 | perf-deps-audit | Done |
| 9 | 安全面（鉴权/校验/暴露） | data-security-audit | Done |
| 10 | 配置与环境 | data-security-audit | Done |
| 11 | 可观测性（日志覆盖） | perf-deps-audit | Done |
| 12 | 跨仓一致性 | arch-audit | Done |

---

## 一、CRITICAL 发现（8 个）

### C-1 安全：过期 Impersonation JWT 仍可授权

| 字段 | 值 |
|------|-----|
| 位置 | `src/edu_cloud/api/deps.py:62-88, 132-139` |
| 发现者 | GPT（新发现） |
| 维度 | 9 安全 |

**现状**: 解码过期 token 后只拒绝非 impersonation 请求。过期的 impersonation token 在 `_expired_impersonation` 中解码后仍返回带权限的用户对象。

**影响**: 模拟登录无实际时间限制，攻击者获取一个 impersonation token 后可无限期使用。

**修复方向**:
1. `_expired_impersonation()` 中增加硬性过期时间（建议 30 分钟）
2. 过期后返回 401 而非降级继续
3. 记录所有 impersonation 操作到 audit_log

---

### C-2 安全：默认密钥 fail-open

| 字段 | 值 |
|------|-----|
| 位置 | `src/edu_cloud/config.py:16-30`, `src/edu_cloud/api/app.py:144-157` |
| 发现者 | 双模型确认 |
| 维度 | 9 安全 / 10 配置 |

**现状**:
```python
SECRET_KEY: str = "change-me"           # 仅 warning 不阻断
ENCRYPTION_KEY: str = "change-me-in-production"
SEED_DEFAULT_PASSWORD: str = "change-me-seed-password"
```
lifespan 中用 `SEED_DEFAULT_PASSWORD` 创建管理员，忘配 `.env` 即全系统用默认密码可登录。

**修复方向**:
1. lifespan 中检测到默认密钥时 `sys.exit(1)`（fail-close）
2. 或添加 `ENVIRONMENT` 变量，生产环境强制校验

---

### C-3 业务：考试完成后 Pipeline 异常吞没

| 字段 | 值 |
|------|-----|
| 位置 | `src/edu_cloud/modules/exam/service.py:88-100` |
| 发现者 | 双模型确认 |
| 维度 | 4 业务通道 |

**现状**:
```python
if status == "completed":
    try:
        results = await run_full_pipeline(db, exam_id=exam_id, school_id=school_id)
    except Exception:
        logger.error("auto_pipeline failed: exam=%s", exam_id, exc_info=True)
        # 异常被吞，update_exam() 返回成功
    return exam
```
先提交 completed 状态，Pipeline 失败只记日志，用户以为考试流程已完成。

**修复方向**:
1. Pipeline 失败时回滚状态或标记为 `completed_with_error`
2. 或改为异步任务（arq），状态设 `pipeline_pending`，前端轮询 Pipeline 结果
3. 失败时发通知给 academic_director

---

### C-4 并发：Grading Task 无原子领取

| 字段 | 值 |
|------|-----|
| 位置 | `src/edu_cloud/workers/grading.py:989-995` |
| 发现者 | GPT（加严，Claude 发现竞态但未定位到 task 领取层） |
| 维度 | 3 Bug |

**现状**: 按 id 读出 task 后直接置 `processing`，没有 `WHERE status='pending'` CAS 或行锁。两个 Worker 可能同时领取同一 task。

**修复方向**:
```python
result = await db.execute(
    update(GradingTask)
    .where(GradingTask.id == task_id, GradingTask.status == "pending")
    .values(status="processing", started_at=func.now())
)
if result.rowcount == 0:
    return  # 已被其他 worker 领取
```

---

### C-5 并发：GradingResult 乐观锁未生效

| 字段 | 值 |
|------|-----|
| 位置 | `src/edu_cloud/workers/grading.py:912-919, 935-946` |
| 发现者 | 双模型确认 |
| 维度 | 3 Bug |

**现状**: 有 `with_for_update(skip_locked=True)` 行锁保护读取，`version` 字段自增但未做 `WHERE version=X` 条件更新。并发写入时后写覆盖先写。

**修复方向**:
```python
if existing:
    result = await db.execute(
        update(GradingResult)
        .where(GradingResult.id == existing.id, GradingResult.version == existing.version)
        .values(**ai_fields, version=existing.version + 1)
    )
    if result.rowcount == 0:
        raise ConcurrentModificationError(...)
```

---

### C-6 租户：Pipeline 派生表更新缺 school_id

| 字段 | 值 |
|------|-----|
| 位置 | `src/edu_cloud/modules/pipeline/service.py:301-307, 371-377, 464-470` |
| 发现者 | GPT（新发现） |
| 维度 | 9 安全 |

**现状**: 按 `student_id/concept_id/subject_code` 更新派生表，未把 `school_id` 纳入查找条件。多校场景下可能跨校写入。

**修复方向**: 所有 UPDATE/UPSERT 语句增加 `AND school_id = :school_id` 条件。

---

### C-7 数据：concept_stats CASCADE DELETE

| 字段 | 值 |
|------|-----|
| 位置 | `alembic/versions/46b200fa9704_add_concept_stats_table.py:36-39` |
| 发现者 | 双模型确认（GPT 建议可降为 HIGH） |
| 维度 | 6 数据层 |

**现状**: `ondelete='CASCADE'` — 删除知识点节点会级联删除所有 `concept_stats` 统计数据（考题频率、难度、覆盖率等）。

**修复方向**: 新迁移改为 `ondelete='RESTRICT'`，应用层手动管理清理。

---

### C-8 业务：GradingTask 状态机不完整

| 字段 | 值 |
|------|-----|
| 位置 | `src/edu_cloud/modules/grading/models.py:33-41` |
| 发现者 | 双模型确认 |
| 维度 | 3 Bug / 4 业务 |

**现状**: status 字段为 String(20) 无约束。Worker 代码中使用 `cancelled`/`failed`（`grading.py:991-995, 1267-1272`），但模型层无枚举无 CHECK。

**应有状态机**:
```
pending → processing → completed
                    → failed → retry_pending → processing
                    → cancelled
```

**修复方向**:
1. 模型层添加 CHECK 约束
2. 新增 `failed_at`, `retry_count`, `last_error` 字段
3. Worker 中 failed task 走 retry 队列

---

## 二、HIGH 发现（14 个）

### H-1 安全：Impersonation 权限白名单过宽
- **位置**: `src/edu_cloud/api/deps.py:16-30`
- **问题**: 白名单包含 `USE_AI_CHAT`（AI 可访问整个数据域）和 `GENERATE_REPORT`（写权限变相实现）
- **修复**: 移除这两个权限

### H-2 租户：5 处跨校隔离缺口
- **位置**: grading/analytics/conduct 路由
- **问题**: 查询时依赖前端传入 school_id，部分路由缺少后端二级验证
- **修复**: 在 service 层统一注入 `school_id = current_role.school_id`

### H-3 租户：家长绑定可跨校错挂
- **位置**: `src/edu_cloud/modules/conduct/parent_service.py:220-236`
- **发现者**: GPT（新发现）
- **问题**: 绑定时 link 的 `school_id` 取当前 parent role，而非目标学生所在班级的学校
- **修复**: 从目标学生的 class → school 链路获取 school_id

### H-4 架构：41 个模块文件反向导入 api/deps.py
- **位置**: `src/edu_cloud/modules/*/router.py` → `edu_cloud.api.deps`
- **问题**: 模块层反向依赖 API 层，违反单向依赖原则
- **修复**: 创建 `core/auth_context.py` 统一导出 `get_current_user`/`require_permission`

### H-5 架构：pipeline/service.py 三向耦合
- **位置**: `src/edu_cloud/modules/pipeline/service.py:13-20`
- **问题**: 直接导入 exam/scan/grading + 更多模块模型
- **修复**: 通过 `core/events.py` EventBus 或 service 接口解耦

### H-6 架构：services/ 双重结构
- **位置**: `src/edu_cloud/services/` 17 个文件中 14 个是 re-export stubs
- **问题**: 外部代码不知该 import services/ 还是 modules/*/service.py
- **修复**: 保守路径——添加 linting rule + 文档注释 `# Canonical: modules/X/service.py`

### H-7 架构：Vision 模块跨仓重复
- **位置**: `paper-seg/app/vision/` vs `edu-cloud/src/edu_cloud/modules/scan/vision/`
- **问题**: 6/7 文件完全相同，segment.py 已有差异
- **修复**: 抽取为共享包 `edu-vision-core`，或建立单向同步脚本

### H-8 架构：3 个模块绕过 AI runtime 直接调 LLM
- **位置**: `workers/grading.py:26-66`, `modules/grading/router.py:96-125`, `modules/analytics/ai_diagnosis_service.py:164-176`
- **问题**: 绕过统一的 `ai/llm_adapter.py`，无统一超时/重试/计费/审计
- **修复**: 在 `ai/` 下为 grading 提供轻量级 LLM 接口

### H-9 配置：硬编码 localhost URL
- **位置**: `src/edu_cloud/config.py:13,43,46,77`
- **问题**: REDIS_URL/CORS_ORIGINS/LLM_API_URL/PAPER_SKILL_URL 默认 localhost
- **修复**: 已有 BaseSettings 支持环境变量覆盖，需确保生产 `.env` 覆盖全部

### H-10 依赖：google-genai>=1.0 无上限
- **位置**: `pyproject.toml:26`
- **问题**: AI 阅卷核心依赖版本浮动，2.0 可能破坏 API
- **修复**: 改为 `google-genai>=1.0,<2.0`

### H-11 性能：delete_exam 逐条删除（N+1）
- **位置**: `src/edu_cloud/modules/exam/service.py:104-117`
- **问题**: for 循环逐条 `await db.delete(q)`，1000 题 = 1000 次 DB 往返
- **修复**: 改用 `delete(Question).where(Question.subject_id.in_(subject_ids))`

### H-12 性能：menu/service.py O(n*m) 查询
- **位置**: `src/edu_cloud/modules/menu/service.py:22-73`
- **问题**: 先查 top_menus、再查 all_children、再循环匹配
- **修复**: 单次 JOIN 查询返回树形结构

### H-13 可观测：前端 console.error 不上报服务端
- **位置**: `frontend/src/pages/*.vue` (5 处)
- **问题**: 错误仅输出浏览器控制台，未通过 `/api/v1/client-logs` 上报
- **修复**: 创建统一 `useClientLogger()` composable

### H-14 工程卫生：backups/ 3.7GB + patch_*.py 残留
- **位置**: `backups/` (11 个 DB 备份), 根目录 4 个 `patch_*.py`
- **修复**: 实施备份 30/120 天分层清理策略；patch 脚本归档至 `scripts/archived/`

---

## 三、MEDIUM 发现（10 个）

| # | 问题 | 位置 | 发现者 |
|---|------|------|--------|
| M-1 | 无效 active_role_id 静默回退第一个角色 | `deps.py:158-165` | GPT |
| M-2 | Scan pipeline 全局单例状态（多校并发冲突） | `scan/pipeline_service.py:30-41` | GPT |
| M-3 | Worker 部分查询缺 school_id 过滤 | `workers/grading.py:1067-1069, 1096-1100` | GPT |
| M-4 | 知识库启动同步失败不阻断 | `api/app.py:111-123` | GPT |
| M-5 | NULL 约束覆盖不足（27%），CHECK 约束完全缺失 | `models/*.py` | Claude |
| M-6 | 无 ENVIRONMENT 变量区分开发/生产 | `config.py` | Claude |
| M-7 | 分页 API 缺 total_count/has_next | `conduct/admin_router.py` 等 | Claude |
| M-8 | 前端 API 响应 camelCase vs snake_case 混用 | API schema 层 | Claude |
| M-9 | ReviewPage.vue 1356 行过大 | `frontend/src/pages/ReviewPage.vue` | Claude |
| M-10 | data/ 目录含 0 字节 edu_cloud.db + 测试结果 JSON | `data/` | Claude |

---

## 四、GPT 纠正的误报

| Claude 原判 | GPT 纠正 | 证据 |
|-------------|---------|------|
| "worker.py 无完成日志" (HIGH) | **误报** — 有 DONE 日志 | `workers/grading.py:1274-1276` 有 `grading_task DONE` |
| "grading 完全无锁" | **不精确** — 有 row lock (with_for_update)，但 task 领取和 version CAS 缺失 | `workers/grading.py:912-919` |
| "conduct/router.py 路径" | **路径错误** — 实际入口是 `admin_router.py` / `parent_router.py` / `notification_router.py` | 文件系统验证 |

---

## 五、系统性根因分析

GPT 总结了四大系统性缺陷，Claude 验证认同：

### 根因 1：租户隔离靠约定不靠约束

school_id 过滤依赖每个 service 方法自觉添加。缺少统一的仓储层（Repository Pattern）或 SQLAlchemy 的 `execution_options` 自动注入 `WHERE school_id = X`。

**波及**: C-6, H-2, H-3, M-3（共 4 个发现）

**治本方案**: 在 `core/scope_filter.py` 的 `ScopeFilter` 基础上，为所有带 `school_id` 的表自动注入 tenant filter。参考 SQLAlchemy 的 `@event.listens_for(Session, "do_orm_execute")` 机制。

### 根因 2：状态机靠字符串不靠类型

Exam.status、GradingTask.status、ConductRecord.semester_id 等状态字段均为裸 String，无 DB CHECK、无 Python Enum、无状态机框架。状态转换合法性靠应用层 `_VALID_STATUS_TRANSITIONS` dict，但不是所有模块都有。

**波及**: C-8, 考试状态转换缺后置验证

**治本方案**: 为核心状态字段创建 SQLAlchemy Enum type + CHECK 约束，统一使用 `transitions` 库或自建轻量状态机。

### 根因 3：LLM 调用入口分散

`ai/llm_adapter.py` 是统一 LLM 适配器，但 grading/analytics 绕过它直接调 Gemini/LLM-proxy。导致超时/重试/计费/审计策略不统一。

**波及**: H-8

**治本方案**: 在 `ai/` 下提供分层接口——Agent 用 `AgentRuntime`，简单 LLM 调用用 `ai/llm_client.py`（轻量，不需要 Agent 框架但经过统一审计）。

### 根因 4：配置安全 fail-open

默认值设计为可直接运行（方便开发），但无生产环境启动校验。忘配 .env 不会报错。

**波及**: C-2, H-9, M-6

**治本方案**: 添加 `ENVIRONMENT` 变量，`prod` 模式下 lifespan 强制校验关键配置项，缺失则 `sys.exit(1)`。

---

## 六、健康度评分

| 维度 | 评分 | 关键问题 |
|------|------|---------|
| 1. 架构 | 6/10 | 层级倒置 + 双重服务层 + pipeline 三向耦合 |
| 2. 技术债 | 8.5/10 | 主要是工程卫生（备份/脚本），核心代码干净 |
| 3. Bug/竞态 | 5/10 | Grading 并发竞态是硬伤 |
| 4. 业务通道 | 7/10 | 主流程通，但 Pipeline 异常吞没严重 |
| 5. 冗余 | 8/10 | knowledge 模块边界清晰，少量脚本残留 |
| 6. 数据层 | 7/10 | Schema 无 drift，但约束不足 + CASCADE 风险 |
| 7. 依赖 | 8.5/10 | 健康，仅 google-genai 版本浮动 |
| 8. 性能 | 7/10 | delete_exam N+1 + menu O(n*m) 局部问题 |
| 9. 安全 | 5.5/10 | JWT 绕过 + 默认密钥 + 租户隔离缺口 |
| 10. 配置 | 6.5/10 | BaseSettings 基础好，但 fail-open |
| 11. 可观测性 | 7.5/10 | 后端日志 v2 体系好，前端和 SLA 弱 |
| 12. 跨仓一致性 | 6/10 | Vision 重复 + paper-seg 无独立 git |
| **综合** | **6.9/10** | **安全和并发是最大短板** |

---

## 七、修复优先级与行动计划

### P0 — 本周（安全 + 数据完整性）

| # | 问题 | 预估工时 | 负责模块 |
|---|------|---------|---------|
| C-1 | Impersonation JWT 过期绕过 | 2h | api/deps.py |
| C-2 | 默认密钥 fail-close | 1h | config.py + api/app.py |
| C-4 | Grading Task 原子领取 (CAS) | 3h | workers/grading.py |
| C-5 | GradingResult 乐观锁 | 2h | workers/grading.py |
| C-6 | Pipeline 派生表 school_id | 2h | modules/pipeline/service.py |
| C-3 | Pipeline 异常不吞没 | 3h | modules/exam/service.py |
| H-1 | Impersonation 权限收紧 | 0.5h | api/deps.py |

**P0 合计**: ~13.5h

### P1 — 两周内（业务正确性 + 数据保护）

| # | 问题 | 预估工时 | 负责模块 |
|---|------|---------|---------|
| C-8 | GradingTask 状态机补全 | 4h | models + workers + migration |
| C-7 | concept_stats CASCADE → RESTRICT | 1h | alembic migration |
| H-2 | 跨校隔离加固（5 处） | 4h | grading/analytics/conduct router |
| H-3 | 家长绑定跨校修复 | 1h | conduct/parent_service.py |
| H-10 | google-genai 版本锁定 | 0.5h | pyproject.toml |
| M-1 | active_role_id 回退拒绝 | 1h | api/deps.py |
| M-3 | Worker 查询加 school_id | 2h | workers/grading.py |

**P1 合计**: ~13.5h

### P2 — 本月（架构治理）

| # | 问题 | 预估工时 |
|---|------|---------|
| H-4 | core/auth_context.py 消除反向依赖 | 4d |
| H-5 | Pipeline 事件驱动改造 | 6d |
| H-6 | services/ 层文档 + linting | 1d |
| H-7 | Vision 共享包 | 2d |
| H-8 | AI runtime 统一 LLM 入口 | 3d |
| M-6 | ENVIRONMENT 变量 + 启动校验 | 0.5d |

**P2 合计**: ~16.5d

### P3 — 持续改进

| # | 问题 | 预估工时 |
|---|------|---------|
| H-11 | delete_exam batch delete | 1h |
| H-12 | menu 查询优化 | 2h |
| H-13 | 前端 console.error 上报 | 3h |
| H-14 | 备份清理 + 脚本归档 | 2h |
| M-2 | Scan pipeline 去单例化 | 4h |
| M-4 | 知识库同步 fail-close | 1h |
| M-5 | NULL/CHECK 约束加固 | 4h |
| M-7 | 分页 API 补 total_count | 2h |
| M-8 | API 响应统一 camelCase | 4h |
| M-9 | ReviewPage 拆分 | 3h |
| M-10 | data/ 清理 | 0.5h |

---

## 八、跟踪清单

> 每条修复完成后在此处标记，附 commit SHA。

### P0（本周）
- [x] C-1 Impersonation JWT 过期绕过 — `122abd7`
- [x] C-2 默认密钥 fail-close — `d47e816`
- [x] C-4 Grading Task 原子领取 — `5d4ee81`
- [x] C-5 GradingResult 乐观锁 — `5d4ee81`
- [x] H-1 Impersonation 权限收紧 — `122abd7`
- [x] C-6 Pipeline school_id 注入 — `12edc94`
- [x] C-3 Pipeline 异常处理（回滚到 reviewing） — `99763fd`
- ~~H-1 已在上方标记~~

### P1（两周内）
- [x] C-8 GradingTask 状态机 — `99763fd`
- [x] C-7 concept_stats CASCADE → RESTRICT — `e1f8e61`
- [x] H-2 跨校隔离（5 处） — `12edc94`
- [x] H-3 家长绑定跨校 — `12edc94`
- [x] H-10 google-genai 版本锁 — `e1f8e61`
- [x] M-1 active_role_id 拒绝 — `af6e00c`
- [x] M-3 Worker school_id — `12edc94`

### P2（本月）
- [x] H-4 反向依赖消除 — `ac710f4`（core/auth.py 提取，47 文件 import 更新）
- [~] H-5 Pipeline 事件驱动 — 调查后降级：设计正确的数据聚合管道，耦合是必要且显式的，不做代码改造
- [x] H-6 services/ 层统一 — 调查确认 9 个 stub 已有 `# Re-export` canonical 标记
- [~] H-7 Vision 共享包 — 调查后关闭：无跨仓重复，grading 是唯一 vision 集中地
- [ ] H-8 AI runtime 统一（需独立 Sprint）
- [x] M-6 ENVIRONMENT 变量 — `af6e00c`

### P3（持续）
- [x] H-11 delete_exam 批量化 — `e1f8e61`
- [x] H-12 menu 查询优化 — `e1f8e61`
- [x] H-13 前端错误上报 — `7a0572c`（setupConsoleCapture 拦截 console.error/warn）
- [x] H-14 备份清理 — `7a0572c`（删除 3.4GB stale backups + 3 个 patch_*.py）
- [x] M-2 Scan pipeline 跨校隔离 — `7a0572c`（_barcode_map 跨校清理）
- [x] M-4 知识库 error 级别 — `af6e00c`
- [ ] M-5 约束加固
- [ ] M-7 分页 total_count
- [ ] M-8 camelCase 统一
- [~] M-9 ReviewPage 拆分 — 已有 3 个 composable 拆分，降级为可选
- [ ] M-10 data/ 清理

---

## 九、附录

### A. paper-seg / answer-card-editor 仓库问题

两个仓库均无独立 `.git` 目录（git 操作 fallthrough 到 home 目录）。建议：
1. 为 paper-seg 初始化独立 git repo
2. answer-card-editor 评估是否合并进 edu-cloud（720 行体量）

### B. 技术债健康度细节

| 指标 | 值 |
|------|-----|
| TODO/FIXME/HACK 标记 | 4 处（均 LOW，注释/示例/占位符） |
| 死代码 | prompts_legacy.py（已完全迁移，可删）|
| 废弃依赖 | 0 |
| 未使用路由 | 0 |
| 孤立组件 | 0 |
| 测试覆盖 | 后端 2504 / 前端 2496（健康） |

### C. 数据层验证

| 指标 | 值 |
|------|-----|
| ORM 表 | 91 |
| DB 表 | 92 |
| Schema drift | 0（db_doctor clean） |
| Alembic head | `ae7b4b332ec9`（与 DB 一致） |
| UNIQUE 约束 | 30（覆盖好） |
| NOT NULL 比率 | 27%（偏低） |
| CHECK 约束 | 0（完全缺失） |

### D. 审计方法说明

1. **Claude 侧**: 5 个 Explore 代理并行，每个代理读取源码并输出结构化报告
2. **GPT 侧**: codex MCP read-only 模式，独立验证 Claude 发现 + 补充新发现
3. **交叉验证**: GPT 确认了大部分发现，纠正了 2 个误报，新发现了 6 个问题（含 2 个 CRITICAL）
4. **局限性**: 部分发现基于代码静态分析，未做运行时验证；前端性能项（虚拟滚动、bundle 大小）未取得 file:line 级证据
