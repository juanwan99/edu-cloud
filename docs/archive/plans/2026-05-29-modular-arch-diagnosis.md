# 模块化架构 P0-P6 诊断报告（GPT 独立审查 + 验证）

> 触发：codex-review plan 判定 **FAIL（6 HIGH + 1 MED）**。本报告逐条验证 finding 并分类，供方向决策。
> 审查者：GPT-5.5（codex exec，xhigh）。验证者：Claude（工具复核每条证据属实）。
> 原始审查日志：`docs/plans/.codex-plan-review-raw.log`

## 一句话结论

这摊 P0-P6 改造的本质是 **「搭了壳子但没通电的半成品」 + 「审计脚本暴露的存量技术债」**。
**好消息**：现有全站功能**未被破坏**——新架构根本没接入生产启动路径，旧的路由表/权限系统照常运行。
**坏消息**：新架构目前是「死代码」（写了不用），且暴露/夹带了租户隔离设计缺陷、事件时机问题、139 处边界违规。

## 7 个 Finding 分类

### B 类 — 集成未完成（新架构是摆设，「要不要真接入」是设计决策）

**F-001 (HIGH)** 模块自注册 + SecureRouter 没接入 app.py
- 证据：`app.py:351-352` 启动只有 `register_all(app)`（旧静态路由表 `router_registry.py`）；全文无任何 `discover_manifests()`/`load_all_manifests()`/`SecureRouter.validate()` 调用。
- 影响：P1（模块系统）、P2.5（SecureRouter fail-closed）写了但生产启动完全没用。

**F-003 (HIGH)** 权限编译器没接入 auth
- 证据：`auth.py:18,111,155,162` 运行时全用旧 `Permission`/`ROLE_PERMISSIONS`；`secure_router.py:172-175` 注释自认 auth 集成是 TODO。
- 影响：P2（权限编译器）只是「旁路验证工具」，不是运行时权限真源。

> B 类共性：**不接入 = 没生效 = 没破坏现有，但也没产生价值**。是否完成接入是重大设计决策（要动 app.py/auth.py 核心，影响全站鉴权与路由）。

### A 类 — 真缺陷（一旦相关代码被使用即出问题）

**F-005 (HIGH 🔴 安全)** BaseService 租户隔离漏洞
- 证据：`base.py:135` `if school_id and hasattr(...)` 仅在传了 school_id 才过滤；`test_base_service.py:147` `assert page_all.total == 8` **把「漏传 school_id 返回全部跨租户数据」当成了正确断言**。
- 现状：BaseService 暂无生产子类使用（仅 test + new_module 模板），所以**漏洞尚未被生产触发**——但是定时炸弹，且测试断言会误导后续开发者以为「跨租户返回是对的」。
- 性质：design_concern（租户策略应 fail-closed 还是显式 admin bypass）+ test 必须修正。

**F-004 (HIGH 🔴 真 bug)** 事件回滚副作用
- 证据：全仓无 commit/rollback hook；`publish_service.py:55` 用 legacy `event_bus.emit` 在 `db.flush()` 后立即触发 `_calculate_rankings`/`_update_error_books`，外层事务若回滚，副作用已发生。新写的 `buffer_event/flush_events`（`session.py`）根本没被调用。
- 性质：既有 emit 时机问题 + 新 outbox 工具未接入。design_concern（需设计事务边界）。

### C 类 — 存量债暴露 / 不变量造假

**F-002 (HIGH)** 模块边界 139 violations + 循环依赖
- 证据：`audit_boundaries.py` 实跑输出 `Total boundary violations: 139`，含 `grading→exam→grading`、`exam→pipeline→exam` 循环；脚本永远 `exit 0`（不 gate）。
- 性质：plan 声称「R3 模块边界 DAG / 0 violations」**是假的**。这 139 处是 P0 审计脚本**暴露的存量技术债**（不是本次改坏的），但 plan 把目标写成了既成事实。处理：建 baseline gate（冻结现状、新增违规失败）或逐步消除。

### D 类 — 小修 / plan 自身问题

**F-006 (HIGH→实际小修)** EventBus 命名漂移
- 证据：`events/__init__.py:14` 导出新 `EventBus`（仅 subscribe/publish），`:69` 才是 legacy singleton；`triggers.py:7,17` 注解 `EventBus` 却调 `.on`。
- 现状：`app.py:204` 实际传 legacy 实例，duck-typing 能跑；但按注解传 `EventBus()` 会运行时炸。
- 处理：triggers.py 注解改 `LegacyEventBus` 或统一接口（小修）。

**F-007 (MED)** plan 元数据不准
- 证据：plan 写「32 文件 / HEAD e7e5ddf」，实际 31 文件 / HEAD 已变 a65c480（plan 已 commit）。
- 处理：Claude 修正 plan 元数据（我的笔误）。

## 根因自评（Claude）

plan 的 6 条 ORC「不变量」中，R3/R4/R6 是把精读得到的**设计意图**直接抄成了**既成事实**，未用工具验证——违背 L015（完成必须有证据）。GPT 独立审查用工具逐条戳破，这正是跨模型审查的价值。

## 处理建议矩阵（待用户决策）

| Finding | 建议处理 | 谁决策 | 紧急度 |
|---------|---------|--------|--------|
| F-005 测试误导断言 | 立即修正测试（别把漏洞当预期） | Claude 可做 | 高 |
| F-005 租户策略 | fail-closed vs admin bypass | **用户/设计者** | 高 |
| F-004 事件事务边界 | 接 outbox 还是改 emit 时机 | **用户/设计者** | 中 |
| F-001/F-003 新架构接入 | 完成集成 / 搁置 / 回退 | **用户/设计者** | 核心决策 |
| F-002 边界债 | baseline gate / 逐步消除 | **用户/设计者** | 中 |
| F-006 EventBus 注解 | 注解改 LegacyEventBus | Claude 可做 | 低 |
| F-007 plan 元数据 | Claude 修正 | Claude 可做 | 低 |

## 核心决策点

**这套新架构（模块自注册 + SecureRouter + 权限编译器 + 事件总线 + BaseService）目前是「写了但没通电」的半成品。最大的方向问题是：要不要、以及如何把它真正接入生产？** 这决定了 A/B/C 类问题是「现在修」还是「随集成一起设计」。
