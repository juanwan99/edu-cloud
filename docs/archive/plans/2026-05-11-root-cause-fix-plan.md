# edu-cloud 根因修复计划

> **基于**: `docs/2026-05-11-full-audit-report.md` 32 条发现 + 4 大根因调研
> **策略**: P0 止血 + 根因纵切（Claude + GPT 双模型共识）
> **基线**: `9b424a9` (master), pytest 2504/43/23, vitest 2496/0

## 总览

| Phase | 内容 | 工时 | 解决发现 | 前置依赖 |
|-------|------|------|---------|---------|
| P0 | 配置 fail-closed | 0.5-1d | C-2 | 无 |
| P1 | Grading CAS + 幂等 | 0.5-1d | C-4, C-5 | 无 |
| P1.5 | Impersonation 安全专项 | 0.5d | C-1, H-1 | 无 |
| P2 | 租户隔离自动化 | 2-4d | C-6, H-2, H-3, M-3 | P1 完成 |
| P3 | 状态机注册表 | 3-5d | C-8, C-3 | P1 完成 |
| P4 | LLM 入口统一 | 2-3d | H-8 | P3 完成 |
| P5 | 架构治理 Sprint | 3-5d | H-4, H-5, H-6 | P2/P3 完成 |
| P6 | 前端可观测 + 清理 | 1-2d | H-13, M-8, M-9 | P1 完成 |

## Phase 0: 配置 fail-closed

### 目标
生产环境启动时强制校验关键密钥，默认值无法通过。

### 变更清单

**新建** `src/edu_cloud/startup_checks.py`:
- `check_critical_secrets(settings)` — SECRET_KEY/ENCRYPTION_KEY/SEED_DEFAULT_PASSWORD 非默认值
- `check_database(settings)` — SELECT 1 验证连接
- `check_redis(settings)` — PING 验证连接
- `run_all_checks(settings)` — 聚合入口
- 开关: `SKIP_STARTUP_CHECKS=1` 允许 dev/test 跳过

**修改** `src/edu_cloud/api/app.py` lifespan:
- 在种子数据前调用 `run_all_checks(settings)`
- 失败 → `raise RuntimeError` 阻断启动

**修改** `src/edu_cloud/config.py`:
- SECRET_KEY warning 保留（向后兼容），fail-closed 由 startup_checks 负责

### 验证
- pytest 全量通过（conftest 已设 SKIP_STARTUP_CHECKS=1）
- 手动测试：不设 .env 启动应 crash

## Phase 1: Grading CAS + 幂等

### 目标
消除阅卷 Worker 并发竞态，确保同一答卷不会被重复评分或覆盖。

### 变更清单

**修改** `src/edu_cloud/workers/grading.py`:
1. Task 领取改 CAS: `UPDATE grading_tasks SET status='processing' WHERE id=:id AND status='pending'`，rowcount=0 则跳过
2. Result upsert 改乐观锁: `UPDATE ... WHERE version=:loaded_version`，版本冲突则重读
3. confirmed 状态硬保护: WHERE 条件排除 `status='confirmed'`

**新增测试** `tests/test_workers/test_grading_concurrency.py`:
- test_concurrent_task_claim_only_one_wins
- test_confirmed_result_not_overwritten
- test_version_conflict_retries

### 前置
- 审计现有 DB 是否有重复 GradingResult（school_id + answer_id 组合）
- 修复脏数据后再加约束

### 验证
- 新增测试全通过
- 全量 pytest 不退步

## Phase 1.5: Impersonation 安全专项

### 变更清单
- `deps.py`: 过期 impersonation token 返回 401（硬过期 30 分钟）
- `deps.py`: 移除 USE_AI_CHAT / GENERATE_REPORT from allowlist

## Phase 2: 租户隔离自动化

### 方案（双模型共识）
1. 建立 TenantMixin 注册表（哪些 Model 有 school_id）
2. `@event.listens_for(Session, "do_orm_execute")` 自动注入 WHERE
3. Worker/system job 显式设 `execution_options(tenant_bypass=True, reason="...")`
4. **先 audit mode**（只 log 不拦截）→ 全量回归 → **再 enforce**
5. 显式旁路审计记录到 audit_log

### 风险
- event listener 可能误捕 FK 校验查询 → audit mode 先行
- raw SQL / Core bulk update 不受拦截 → CI 静态扫描兜底
- Worker 无 request context → 必须显式设 system tenant context

## Phase 3: 状态机注册表

### 方案
自建轻量 `core/state_machine.py`，不引入 transitions 库。
- STATE_MACHINES dict 集中声明所有实体的状态转换规则
- `validate_transition(entity_type, old, new)` 统一校验
- 先覆盖 GradingTask（补 failed/cancelled），再合并 Exam/Document
- C-3 Pipeline 异常：Exam 状态转为 `pipeline_pending`，Pipeline 失败设 `pipeline_failed`

## Phase 4-6: 见审查报告对应章节
