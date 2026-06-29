# edu-cloud 模块化架构改造（P0–P6）Implementation Plan

> **For agentic workers:** 本 plan 为**追认式 plan**——P0–P6 代码已实现，但经 codex-review（GPT-5.5）独立审查**判定 FAIL**：本 plan 原先声称的多条 `semantic_regression` 不变量实际不成立（详见下方状态更新与诊断报告）。**新架构未接入生产、已搁置接入**，故本 plan 不再作为「落地收尾」依据，仅留作历史设计记录。

---

## ⚠️ 状态更新（2026-05-29，codex-review 后）

**判定：plan review FAIL（6 HIGH + 1 MED，全部工具验证属实）。方向已定：搁置接入，先清安全隐患。**

- **新架构是「写了但没通电」的半成品**：`app.py:351` 启动仍用旧静态路由表 `register_all`，模块自注册 / SecureRouter / 权限编译器**均未接入生产**（F-001/F-003）。现有全站功能因此**未被破坏**。
- **本 plan 原 `semantic_regression` 段的不变量多为「设计意图」而非「既成事实」，已被证伪**：
  - R3 模块边界 DAG「无循环」→ 实际 **139 violations + 循环依赖**（F-002），audit 脚本不 gate。
  - R4 权限编译 legacy 等价 → auth 运行时仍用旧 enum/dict，编译器未接入（F-003）。
  - R6 事件 transactional outbox → 无 commit/rollback hook，`publish_service` 仍 flush 后即 emit（F-004）。
  - R5 租户隔离 → BaseService 非 fail-closed，漏传 school_id 跨租户（F-005，已加警告 + 修测试误导断言）。
  - R1 EventBus 命名漂移 → 已修 `triggers.py` 注解（F-006）。
- **完整诊断与处置矩阵**：`docs/plans/2026-05-29-modular-arch-diagnosis.md`
- **接入 / 租户策略 / 事件事务 / 边界债** 已立为后续设计议题（见诊断报告「核心决策点」），需走 brainstorming→design，不在本流程完成。

---

**Goal:** 把 edu-cloud 从「中央集权式路由注册 + 分散权限声明 + 模块强耦合」重构为「声明式模块自注册 + 单源权限编译 + 契约化模块边界」，让新模块零改动主干即可接入。

**Architecture:** 以 `ModuleManifest` 为核心契约（声明路由/权限/模型/事件/依赖），启动时由 `discover_manifests()` 自动发现加载；权限由 `roles.yaml` 单源经 `PermissionCatalog` 编译；`SecureRouter` 在启动时 fail-closed 强制校验每个路由都声明了权限；模块间只能经 `contracts/events/schemas` 交互，由审计脚本守护边界 DAG。

**Tech Stack:** FastAPI + 异步 SQLAlchemy（后端）、Vue 3 + Naive UI + Vite（前端）、Pydantic V2（事件/分页模型）、AST 静态分析（审计脚本）。

**实现状态（F-007 已修正）:** 模块化改造代码约 31 个文件落在工作树（不含本 plan 与诊断文档），plan 已 commit 于 `a65c480`。架构测试 `112 passed`——但**仅覆盖新模块的孤立单元，未覆盖接入后的生产路径**，且其中 `test_base_service` 曾把租户漏洞当预期断言（已修，见 F-005）。已清理迁移残留 `events_legacy.py.bak`。⚠️ 新架构**未接入生产**，详见上方状态更新。

---

## 背景与动机

改造前的四个结构性痛点（P0 审计脚本量化）：

1. **路由中央集权** — 新模块必须手工编辑 `router_registry.py`/`app.py` 的 `(import_path, attr_name)` 元组列表，是并发禁区、易冲突。
2. **权限分散** — 权限声明散落在各路由装饰器，无单一真源，覆盖率不可测、易遗漏无保护端点。
3. **模块强耦合** — 模块间直接 import 实现代码，产生 `exam↔pipeline↔analytics` 循环依赖。
4. **CRUD 重复** — 前端多个管理页 ~55% 是 CRUD 样板，后端 service 重复 list/get/create/update/delete。

---

## File Structure（32 改动文件，按阶段）

### P0 审计基线（非 gate，exit(0) 仅生成报告）
- `scripts/audit_permissions.py` (183) — 路由权限覆盖率审计（AST 扫描 `require_permission`/`get_current_user`）
- `scripts/audit_boundaries.py` (187) — 跨模块导入边界审计 + DAG 循环检测（DFS）
- `scripts/audit_crud_pages.py` (197) — 前端 CRUD 页面重复度加权评分（0–100）

### P1 模块 Manifest + 自动发现
- `src/edu_cloud/core/modules/manifest.py` (38) — `ModuleManifest`/`PermissionSpec`/`RouterSpec` 数据类
- `src/edu_cloud/core/modules/registry.py` (75) — `ModuleRegistry` + `discover_manifests()` 目录扫描
- `src/edu_cloud/core/modules/loader.py` (48) — `load_all_manifests()`/`import_manifest_models()`/`include_manifest_routers()`
- `src/edu_cloud/modules/calendar/manifest.py` (17) — 样例模块声明

### P2 权限编译器（roles.yaml 单源）
- `src/edu_cloud/core/permission_compiler/catalog.py` — `PermissionCatalog`（注册/继承解析/通配符/循环检测/fail-fast 验证）
- `src/edu_cloud/core/permission_compiler/compiler.py` — `compile_permissions()` 编译管道（yaml 加载→manifest 聚合→includes 展开→resolve）
- `src/edu_cloud/core/permission_compiler/roles.yaml` — 50 权限码 + 16 角色（含 1 抽象角色）单一真源
- `src/edu_cloud/core/permission_compiler/__init__.py` — 导出接口

### P2.5 SecureRouter + 启动校验
- `src/edu_cloud/core/secure_router.py` (233) — 路由包装器，强制 `permission=`/`public=True`，`validate()` 启动 fail-closed
- `tests/test_core/test_secure_router.py` (329) — 7 测试类 29 用例

### P3 事件总线 + 领域事件
- `src/edu_cloud/core/events/types.py` (21) — `DomainEvent` 基类（frozen，含 event_id/name/tenant_id/actor_id/occurred_at）
- `src/edu_cloud/core/events/bus.py` (80) — 新 `EventBus`（subscribe/publish）+ 全局单例
- `src/edu_cloud/core/events/session.py` (33) — session 级缓冲（transactional outbox：commit 后 flush）
- `src/edu_cloud/core/events/__init__.py` (99) — 新旧并存导出（含 `LegacyEventBus` 向后兼容）

### P4 BaseService + 分页
- `src/edu_cloud/core/services/base.py` (172) — 泛型异步 CRUD 基类（租户过滤/分页/排序/钩子）
- `src/edu_cloud/core/services/pagination.py` (36) — `PageParams`/`Page`（size 上限 200）

### P5 前端 CRUD 模板
- `frontend/src/components/CrudPage.vue` (141) — CRUD UI 壳（n-data-table + 分页 + slot）
- `frontend/src/composables/useCrudResource.js` (92) — CRUD 状态/逻辑 composable

### P6 脚手架
- `scripts/new_module.py` (393) — 一键生成 8 文件模块骨架（manifest/model/service/router/API/页面/测试）

### 配套测试 + 文档
- `tests/test_base_service.py`、`tests/test_event_bus.py`、`tests/test_module_manifest.py`、`tests/test_permission_compiler.py`、`tests/test_core/test_secure_router.py`
- `CLAUDE.md`（M，补「模块化架构（2026-05-28）」段）
- 已删：`src/edu_cloud/core/events.py`（D，迁移到 `events/` 包）

---

## 各阶段关键设计决策

**P1：声明式替代命令式** — `ModuleManifest` 取代手工元组列表；`discover_manifests()` 只加载含 `manifest.py` 的目录，无 manifest 老模块静默跳过（向后兼容）；`import_manifest_models()` 独立于路由注册，保证模型元数据先于路由就绪，避免 table-not-found。

**P2：单源 + 分层编译** — `roles.yaml` 是权限-角色唯一真源，取代旧 `Permission enum + ROLE_PERMISSIONS dict`；编译分 yaml 加载→目录注册→继承解析三段，允许 manifest 在中间插入权限/role_grants；`perm_includes` 展开、通配符 fnmatch、抽象角色（`_teacher_base` 不出现在 export_matrix）、`all: true` 受 revoke 约束、继承环检测 `CircularInheritanceError`。**编译结果与 legacy 等价**（`test_permission_compiler.py::TestBackwardCompat`）。

**P2.5：fail-closed 权限强制** — 每路由必须 `permission=` 或 `public=True`，遗漏在 `validate()` 启动检查 `RuntimeError`；双模式（enum + manifest 字符串码）；权限 Depends() 自动注入。**注意：`validate()` 当前未在 `app.py` 集成调用**（见 semantic_regression 第 5 条）。

**P3：新旧事件并存** — 新 `DomainEvent`(frozen)/`publish`/`subscribe` 与 `LegacyEventBus`(.on/.emit) 并存；transactional outbox（`session.info['_domain_events']` 缓冲，commit 后 flush）；publish 顺序执行 + 单 handler 失败隔离。

**P4：模板基类** — 泛型 `BaseService[ModelT]`，子类设 `model` 即获 CRUD；`_apply_tenant_filter` 检 `school_id` 自动加 WHERE；immutable `{id, school_id}` update 跳过；仅 `flush()` 不 `commit()`（交调用层事务）。

**P5：组件/逻辑分离** — `CrudPage.vue`(UI) + `useCrudResource.js`(状态)；config 工厂模式；兼容 `{data:[...]}` 与 `{data:{items,total}}` 两种响应；save 前删 `payload.id` 防 ID 覆盖。

**P6：自动注册脚手架** — 生成 manifest 走 `discover_manifests()` 自动扫描、router 用 `SecureRouter` 强制权限、service 继承租户隔离、`--dry-run` + 防覆盖原子写入。

---

## semantic_regression（ORC 不变量 — codex-review 必须逐项验证）

> 收尾 commit 前，以下不变量必须保持；任一被破坏即为回归。

### R1 ⚠️ EventBus 命名语义漂移（HIGH — 头号风险）
- **不变量**：所有 `from edu_cloud.core.events import event_bus` 拿到的必须是带 `.on()/.emit()` 的 dict-bus（现为 `LegacyEventBus` 实例，`events/__init__.py:69`）。
- **回归点**：改造前 `core.events.EventBus` = 旧 dict-bus；改造后该名字被给了**新** domain bus（`bus.py:14`，只有 `subscribe/publish`）。`triggers.py:7` `from ...events import EventBus` + `:17 bus: EventBus` 的类型注解现在指向**错误的类**——仅因 `app.py:204 EventTrigger(event_bus, ...)` 实际传入 legacy 实例（有 `.on()`）才未在运行时暴露。
- **验证要求**：① 确认全部 4 处旧 import 点（`app.py:192`/`triggers.py:7`/`publish_service.py:57`/`pipeline/__init__.py:6`）运行时行为不变；② 决策 `triggers.py` 类型注解应改为 `LegacyEventBus`（design_concern，交设计者）；③ 全量测试覆盖这 4 条运行时路径。

### R2 权限强制声明 fail-closed（HIGH）
- **不变量**：每个 SecureRouter 路由必须声明 `permission=` 或 `public=True`，未声明启动即 `RuntimeError`；权限覆盖率 ≥95%、无保护端点为 0。
- **验证要求**：确认 `SecureRouter.validate()` 的集成状态——若尚未在 `app.py` startup 调用，则 fail-closed 保证**当前未生效**，需明确是 P2.5 待集成项还是已集成。

### R3 模块边界 DAG（MEDIUM）
- **不变量**：`edu_cloud.modules` 下模块间只能 import `contracts/events/schemas` 三类子路径；依赖图必须是 DAG（无循环）；只能依赖 `core|shared|models|services|config|database` 公共层。
- **验证要求**：`audit_boundaries.py` 报 0 violations、0 循环。

### R4 权限编译 legacy 等价（MEDIUM）
- **不变量**：`roles.yaml` 编译出的权限矩阵必须与旧 `Permission enum + ROLE_PERMISSIONS` 完全等价。
- **验证要求**：`test_permission_compiler.py::TestBackwardCompat` 全绿；继承环检测有效。

### R5 租户隔离（HIGH）
- **不变量**：`BaseService` 对含 `school_id` 的 model 自动加租户过滤；`{id, school_id}` 为 immutable，update 不可改；create 自动注入 `school_id`。
- **验证要求**：`test_base_service.py` 覆盖跨租户读写隔离。

### R6 事件 transactional outbox（MEDIUM）
- **不变量**：domain event 只在事务 commit 成功后发布（经 `session.info` 缓冲 + flush）。
- **验证要求**：`test_event_bus.py` 覆盖「commit 后才发布、rollback 不发布」。

---

## 已知次要风险（审计脚本启发式局限，非阻断，记录备查）

- **权限审计盲区**（medium）：`audit_permissions._check_auth()` 仅扫函数签名 defaults，检测不到嵌套 `Depends()` 注入的权限（`audit_permissions.py:52-70`）。
- **权限声明一致性缺失**（medium）：审计脚本与 `ModuleManifest.permissions` 独立运行，未交叉验证「声明但未使用」的权限。
- **边界审计不查 contract 内部**（medium）：`audit_boundaries.py:78-81` 仅按 `is_contract(sub_path)` 判定，不扫描 contract 文件内部是否泄露实现。
- **模块发现无有效性标记**（low）：`discover_modules()` 仅按目录名判定，不校验 `manifest.py`/`__init__.py` 存在。
- **CRUD 评分主观**（low）、**前端扫描路径固定**（low）、**import 追踪仅一级**（low）。

---

## 收尾 Tasks（真正待执行）

- [ ] **Task A：codex-review plan** — 本 plan commit 后 `codex-review plan`，过 gates.json，自动提取上方 semantic_regression。
- [ ] **Task B：codex-review code（32 文件）** — 获独立审查 receipt（满足 completion-guard mandatory_review）。findings 按 L017 三分：defect_fix（修）/ test_gap（补测试）/ design_concern（如 R1 triggers.py 注解，交设计者）。
- [ ] **Task C：处理 findings** — 修 defect、补 test_gap；design_concern 汇总报用户。避免反复改同一文件（trajectory）。
- [ ] **Task D：前端 build** — `cd frontend && npm run build`，更新 dist（CrudPage.vue/useCrudResource.js 改动，edu-cloud 硬禁令），消除 truth_gate SOURCE→BUILD 不一致。
- [ ] **Task E：clean commit + 全量测试** — commit 使工作树 clean（消除 proof_taint），在 clean tree 跑全量测试对比基线（后端 2347p/19f/23s、前端 2373p/3f），确认无新增 fail；audit_boundaries 0 violations。
- [ ] **Task F：completion 验证** — 确认 completion-guard 全绿（truth_gate/proof_taint/mandatory_review/trajectory）。

---

## Self-Review

- **Spec 覆盖**：P0–P6 八阶段逐一映射到 File Structure + 设计决策，无遗漏阶段。
- **不变量完整性**：6 条 ORC 不变量覆盖权限（R2/R4）、边界（R3）、租户（R5）、事件（R1/R6）四大维度。
- **类型一致性**：接口签名取自精读的代码原文（`ModuleManifest`/`PermissionCatalog.resolve()`/`SecureRouter`/`DomainEvent`/`BaseService`），与实现一致。
- **追认 plan 诚实性**：已明确标注「代码已实现」，收尾 task 为真实待办，未伪装成从零实现。
