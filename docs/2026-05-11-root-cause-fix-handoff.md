# 根因修复交接卡 — 2026-05-11

## Goal

基于 12 维度双模型深度审查（`docs/2026-05-11-full-audit-report.md`），按"P0 止血 + 根因纵切"策略修复 edu-cloud 的安全、并发、租户隔离、状态机四大系统性根因。本会话完成了全部 8 个 CRITICAL + 8 个 HIGH + 4 个 MEDIUM = 20/32 条发现的修复，新增 100 个测试。

## Must Preserve

1. **CAS 领取逻辑** (`workers/grading.py:1020-1035`) — `UPDATE ... WHERE status='pending'` 原子领取，rowcount=0 则退出。P1 核心修复，不可回退
2. **乐观锁** (`workers/grading.py:941-980`) — `UPDATE ... WHERE version=:loaded_version`，confirmed 状态硬保护不可被 AI 覆盖
3. **startup_checks fail-closed** (`startup_checks.py`) — 生产环境 SECRET_KEY/ENCRYPTION_KEY/SEED_DEFAULT_PASSWORD 必须覆盖，否则启动阻断。测试环境用 `SKIP_STARTUP_CHECKS=1`
4. **Impersonation 过期拒绝** (`deps.py`) — 已删除过期 impersonation 的特殊处理，过期 token 统一 401。`create_impersonation_token` 已有 30 分钟过期
5. **租户隔离 audit mode** (`database.py` + `core/tenant_registry.py`) — `do_orm_execute` 事件监听已挂载，audit 模式记录缺少 school_id 的查询。尚未切换 enforce 模式
6. **状态机注册表** (`core/state_machine.py`) — 4 个实体（exam/grading_task/grading_result/document）的状态转换已集中声明，`validate_transition()` 已接入 exam/service.py 和 workers/grading.py
7. **Pipeline 回滚** (`exam/service.py:88-100`) — Pipeline 失败时回滚 exam.status 到 reviewing，不再吞没异常

## Must Not Change

- `conftest.py` 开头的 `os.environ["SKIP_STARTUP_CHECKS"] = "1"` — 删除会导致全部测试因 startup_checks 阻断而失败
- `_IMPERSONATION_ALLOWED_PERMISSIONS` 白名单 — 已收紧为仅 view_* 权限（11 项），不可加回 USE_AI_CHAT / GENERATE_REPORT
- `concept_stats` FK 的 `ondelete='RESTRICT'` — 迁移 `c7_fix_cascade_to_restrict.py` 已将 CASCADE 改为 RESTRICT，不可回退
- `pyproject.toml` 中 `google-genai>=1.0,<2.0` 的上限约束

## 版本基线

| 字段 | 值 |
|------|-----|
| HEAD | `45457a1` (master) |
| 起点 | `9b424a9` |
| 新增 commit | 11 个（含 3 个 merge commit） |
| 新增测试 | 100 个（全部通过） |
| Alembic head | `c7_fix_cascade` (down_revision: `b1a2c3d4e5f6`) |
| DB drift | 未验证（需在新会话中 `db_doctor --strict`） |

## 已完成的修复（按 Phase）

| Phase | Commit | 发现 | 新建文件 |
|-------|--------|------|---------|
| P0 | `d47e816` | C-2 默认密钥 fail-closed | `startup_checks.py`, `test_startup_checks.py` |
| P1 | `5d4ee81` | C-4 Task CAS, C-5 乐观锁 | `test_grading_concurrency.py` |
| P1.5 | `122abd7` | C-1 JWT 绕过, H-1 权限收紧 | — |
| P2a | `12edc94` | C-6 Pipeline school_id, H-2 跨校隔离, H-3 家长绑定, M-3 Worker | `test_tenant_isolation.py` |
| P2b | `d648801` | 租户隔离基础设施 (audit mode) | `core/tenant_registry.py`, `test_tenant_registry.py` |
| P3 | `99763fd` | C-3 Pipeline 异常回滚, C-8 状态机 | `core/state_machine.py`, `test_state_machine.py` |
| P4a | `e1f8e61` | C-7 CASCADE, H-10 版本锁, H-11 批量删除, H-12 菜单优化 | `c7_fix_cascade_to_restrict.py` |
| P4b | `af6e00c` | M-1 角色回退, M-4 知识库 error, M-6 ENVIRONMENT | — |

## 剩余工作（12 项）

### 架构治理 Sprint（H-4 ~ H-8，预估 13-16d）

| # | 问题 | 文件范围 | 预估 |
|---|------|---------|------|
| H-4 | 41 个模块文件反向导入 api/deps.py | 新建 `core/auth_context.py`，改 41 个 router import | 4d |
| H-5 | pipeline/service.py 三向耦合 | EventBus 改造或 service 接口解耦 | 6d |
| H-6 | services/ 双重结构（17 re-export stubs） | 标注 canonical + linting rule | 1d |
| H-7 | Vision 模块跨仓重复 | 抽取 edu-vision-core 共享包 | 2d |
| H-8 | 3 个模块绕过 AI runtime 调 LLM | GoogleGenaiAdapter 包装 GeminiClient | 3d |

**建议**: H-4 和 H-6 可同一 Sprint；H-5 等 P3 状态机稳定后再做；H-7/H-8 独立。

### 前端 + 清理（预估 3-5d）

| # | 问题 | 预估 |
|---|------|------|
| H-13 | 前端 console.error 不上报服务端 | 3h |
| H-14 | backups/ 3.7GB + patch_*.py 残留 | 2h |
| M-2 | Scan pipeline 全局单例（多校并发） | 4h |
| M-5 | NULL/CHECK 约束加固 | 4h |
| M-7 | 分页 API 缺 total_count | 2h |
| M-8 | API 响应 camelCase 混用 | 4h |
| M-9 | ReviewPage.vue 1356 行过大 | 3h |

## 新增基础设施使用指南

### startup_checks.py
```bash
# 生产环境：必须在 .env 中覆盖
SECRET_KEY=your-production-key
ENCRYPTION_KEY=your-encryption-key
SEED_DEFAULT_PASSWORD=strong-seed-password

# 开发/测试：跳过检查
SKIP_STARTUP_CHECKS=1
```

### core/tenant_registry.py
```python
# 请求中自动设置（deps.py get_current_user 已接入）
from edu_cloud.core.tenant_registry import set_tenant, get_tenant, clear_tenant

# 查询时显式旁路（platform_admin / system job）
result = await session.execute(
    select(Model).options(...),
    execution_options={"tenant_bypass": True, "tenant_bypass_reason": "cross-school analytics"}
)

# 当前状态：audit mode（只记日志不拦截）
# 切换 enforce：修改 tenant_registry.py 中 TENANT_MODE = "enforce"
# 切换前必须：全量回归 + 审查 audit 日志中的误报
```

### core/state_machine.py
```python
from edu_cloud.core.state_machine import validate_transition, get_terminal_states, STATE_MACHINES

# 验证状态转换
validate_transition("grading_task", "pending", "processing")  # OK
validate_transition("grading_task", "completed", "pending")   # raises StateError

# 新增实体：在 STATE_MACHINES dict 中添加即可
# 未注册的实体类型不报错（向后兼容）
```

## 关键决策记录

1. **租户隔离方案**: event listener + 显式旁路 + audit mode 先行（Claude+GPT 共识）
2. **状态机方案**: 自建轻量 registry，不用 transitions 库
3. **C-3 修复方案**: 回滚到 reviewing + 记录 error，不抛异常给用户
4. **并发修复层面**: DB 级幂等（CAS + 乐观锁），暂不引入 Redis 分布式锁

## 参考文档

- 审查报告: `docs/2026-05-11-full-audit-report.md`（含跟踪清单）
- 修复计划: `docs/archive/plans/2026-05-11-root-cause-fix-plan.md`
- GPT 交叉审查: codex thread `019e15e7-c7ac-79a3-89af-025d488523a8`
- GPT 策略讨论: codex thread `019e1605-d746-72b1-bece-7589805e2d5f`
