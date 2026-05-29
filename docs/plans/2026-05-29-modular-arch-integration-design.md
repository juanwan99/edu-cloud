# 模块化架构「渐进接入」设计（承接 P0–P6 诊断）

> **定位**：本文是「是否 + 如何把 P0–P6 模块化架构接入生产」的 **design spec**（brainstorming 产物）。
> **前序**：诊断报告 `2026-05-29-modular-arch-diagnosis.md`（codex-review plan FAIL 的逐条验证）；接入 handoff `2026-05-29-modular-arch-integration-handoff.md`。
> **下一步**：本 spec 批准后转 writing-plans 产出分阶段 implementation plan（每阶段独立 plan + codex-review）。
> **作者**：Claude（brainstorming）。**决策者**：用户（体系设计者）。

---

## 1. 决策结论（已与设计者对齐）

| 决策点 | 结论 | 依据 |
|--------|------|------|
| 要不要接入 | **接入**（非搁置、非回退） | 设计者确认 edu-cloud 后续仍会**频繁加新功能模块**，"零改动接入"架构收益高 |
| 四痛点取舍 | **四个全保留**（路由中央集权 / 权限分散 / 模块耦合 / CRUD 重复） | 设计者确认四个痛点均真实困扰，无可 YAGNI 砍除项 |
| 接入方式 | **方向 A：渐进分层接入**（按风险从低到高排队，逐阶段独立审查/部署/回滚） | 整套一次性通电 = 把 6 个 HIGH 摊在动核心的一刀上，与"不破坏已有"和 L015 教训冲突 |
| 租户隔离策略 | **fail-closed**：漏传 `school_id` 默认拒绝 / 返回空，绝不返回跨租户数据 | 设计者拍板；教育 SaaS 多租户场景的稳健默认 |

**核心立场**：架构的设计意图（解决四个结构性痛点）成立；翻车的是**实现质量与"追认式 plan 把设计意图当既成事实"**（[[L013]]/[[L015]]）。因此接入的是**意图**，落地要用"小改 + 验证 + 可回滚"的纪律重新把每一层稳稳通电，而非照搬未验证的整套半成品。

---

## 2. 背景与现状（证据）

### 2.1 四个结构性痛点（原 plan「背景与动机」量化）
1. **路由中央集权** — 新模块必须手工编辑 `router_registry.py`/`app.py` 的元组列表，是并发禁区、易冲突。
2. **权限分散** — 权限声明散落各路由装饰器，无单一真源，覆盖率不可测、易遗漏无保护端点。
3. **模块强耦合** — 模块间直接 import 实现代码，产生 `exam↔pipeline↔analytics` 循环依赖。
4. **CRUD 重复** — 前端管理页 ~55% 是 CRUD 样板，后端 service 重复 list/get/create/update/delete。

### 2.2 当前真实状态（codex-review 工具验证）
- **新架构未接入生产**：`app.py:351` 启动仍只调用旧 `register_all`（旧静态路由表）；全文无 `discover_manifests()`/`SecureRouter.validate()` 调用。**现有全站功能因此未被破坏**。
- **代码存放位置**：架构 WIP（P0–P6 约 31 文件 + events 重构）已 `git stash -u` 到 **`stash@{0}`**（分支 `codex/role-permission-phase2`）。工作树 clean。**接入第一步必须 `git stash pop` 恢复。**
- **当前 backend**：`b763888`，`source_dirty:false`（本机 systemd `edu-cloud.service`，uvicorn 127.0.0.1:9000，无 --reload；部署 = `sudo systemctl restart edu-cloud edu-cloud-worker`）。
- **遗留隐患**（诊断报告 6 HIGH + 1 MED）：F-001/F-003 未接入、F-002 边界 139 违规、F-004 事件无事务 hook、F-005 BaseService 非 fail-closed（且测试把漏洞当预期）、F-006 EventBus 注解漂移、F-007 plan 元数据。

---

## 3. 设计目标与非目标

### 目标
- 让**新功能模块零改动主干即可接入**（路由/菜单/权限/事件声明式自注册）。
- 权限有**单一真源**且覆盖率可测，消除"漏配无保护端点"风险。
- 模块边界**可守护**（新增跨界违规即失败），存量违规冻结后逐步消除。
- 每一层接入**独立可验证、可回滚**，过渡期不破坏任何现有功能。

### 非目标（YAGNI / scope 边界）
- **不**一次性重写或推倒现有 31 文件（复用 stash 骨架）。
- **不**在本轮消除全部 139 存量边界违规（只冻结 baseline，存量另排期）。
- **不**长期维护新旧双轨——每层迁移完成后**必须删除旧路径**（[[single-version-discipline]]）。
- **不**在未影子比对验证等价前切换运行时鉴权。

---

## 4. 总体策略：渐进分层接入

**原则**：新模块从阶段 1 起就走新路径；老模块按阶段逐层迁移；旧路径保留到该层彻底切换，然后删除。每阶段 = 一个独立任务（独立 plan / codex-review / 部署验证 / 回滚点）。

### 前置清理（P-clean，🟢 零风险，先于一切阶段）
独立小 commit，不动生产路径：
- **修 F-005 误导测试断言**：`test_base_service.py:147` 的 `assert page_all.total == 8`（把"漏传 school_id 返回跨租户全部"当正确）必须改为断言 fail-closed 行为。**这是最高优先**——不改会带歪后续开发者。
- 修 F-006：`triggers.py` 的 `EventBus` 注解改 `LegacyEventBus`（或统一接口）。
- 修 F-007：plan 元数据笔误（文件数 / HEAD）。

### 阶段 0：恢复 WIP（P0-restore）
- `git stash pop` 恢复 `stash@{0}` 至**独立 git worktree**隔离作业（子代理闭环模式：worktree + manifest + diff_hash 绑定）。
- 基线测试快照：恢复后先跑全量测试，记录"恢复态基线"（区分新架构引入的失败 vs 真实回归）。

### 阶段 1：模块自注册（🟢 低风险，收益最快）
- **改动**：`app.py` 启动在旧 `register_all` 之外，**并行**调用 `load_all_manifests()`/`include_manifest_routers()`，让声明了 manifest 的模块自动挂载路由。
- **旧路径**：旧静态路由表**完整保留**，新旧并存；旧模块暂不迁移。
- **验收**：① 旧 320 路由全部仍可达（路由清单 diff = 0 丢失）；② 新样例模块（calendar）路由经 manifest 挂载可达；③ 全量后端测试不低于恢复态基线；④ `curl 127.0.0.1:9000/api/v1/version` 确认部署生效。
- **Tier**：T3（碰 `app.py` 启动路径，结构性中心文件，主会话独占）。
- **回滚**：移除 app.py 新增的 manifest 加载调用即恢复旧行为。

### 阶段 2：权限单源（🔴 最高风险，三道闸隔离慢切）
- **2a 观察模式**：`roles.yaml` 成为权限单一真源，`PermissionCatalog`/`compile_permissions()` 上线；`audit_permissions.py` + `SecureRouter.validate()` 仅**报告**漏配/未声明权限的路由，**不阻断启动**。auth 运行时仍走旧 `Permission`/`ROLE_PERMISSIONS`。
- **2b 影子比对**：对每个角色×每个权限码，比对"新编译结果"与"旧 ROLE_PERMISSIONS"，输出差异报告；**目标是差异收敛到可解释的 0**（任何不等价都要逐条定性：是 bug 还是有意收紧）。
- **2c 切换**：影子比对全绿后，用 **feature flag** 把 auth 运行时切到编译器，flag 可秒级回滚。切换稳定运行确认后，删除旧 `Permission`/`ROLE_PERMISSIONS`。
- **旧路径**：保留到 2c 切换稳定。
- **Tier**：T3（碰 `auth.py` 全站鉴权，最高风险）。
- **回滚**：feature flag 翻回旧鉴权。

### 阶段 3：CRUD 基类（🟡 中）
- **前置硬门槛**：先把 `BaseService`（`base.py:135`）改为 **fail-closed**——未显式传 `school_id` 时默认拒绝 / 返回空，绝不返回跨租户数据；配套测试断言 fail-closed 行为（替换 F-005 误导断言后的正确语义）。
- **改动**：新管理页 / 新 service 继承 `BaseService`；**老页面/老 service 不动**，按需逐步迁移。
- **验收**：fail-closed 单元测试 + 至少一个真实新模块跑通 CRUD + 现有功能无回归。
- **Tier**：T2~T3（视迁移范围）。

### 阶段 4：模块边界 gate（🟡 中）
- **改动**：`audit_boundaries.py` 从 `exit(0)` 仅报告，改为 **baseline gate**——冻结当前 139 违规为基线，**新增违规即失败**（CI/pre-commit 接）。
- **存量**：139 违规 + `grading→exam→grading`/`exam→pipeline→exam` 循环依赖**另行排期逐步消除**，不阻塞本轮接入。
- **事件事务（F-004）**：在迁移到涉及事务副作用的模块（如 `publish_service.py:55` 的 ranking/error_book 触发）时，接 `buffer_event/flush_events` outbox，确保外层事务回滚时副作用不发生；不单独立阶段。
- **Tier**：T2。

---

## 5. 跨阶段铁律

- **每阶段独立闭环**：独立 plan → `codex-review plan` → 实现 → `codex-review code` → 部署验证（`curl version` 看 git_hash + source_dirty + 测试证据，[[L015]]）→ 独立回滚点。
- **新旧并存仅限过渡期**：该层迁移完成立即删旧路径，禁止长期双轨（[[single-version-discipline]]）。
- **鉴权切换三道闸**：观察 → 影子 → flag 切换，任一闸不绿不进下一步。
- **隔离作业**：worktree 隔离 + manifest（agent_id/base_sha/head_sha/diff_hash/review_gate_id）绑定。
- **证据优先**：所有"完成"声明附 git log / test output / curl version；不变量逐条工具验证，不重蹈"设计意图当既成事实"。

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 阶段 2 切鉴权切崩全站 | 三道闸 + 影子比对差异归零 + feature flag 秒回滚；旧鉴权保留到切换稳定 |
| 新旧路由并存期出现"幽灵副本"（单入口原则） | 阶段 1 验收强制路由清单 diff = 0；新模块路由与旧表无重叠校验 |
| BaseService 租户漏洞被生产触发 | 阶段 3 前置硬门槛：fail-closed 改造 + 测试先行，未改完不让任何生产子类继承 |
| 存量 139 违规拖累进度 | 只冻结 baseline 不要求清零；存量另排期 |
| stash 丢失 | 阶段 0 恢复后立即在 worktree commit，不再依赖 stash |

---

## 7. 成功标准（整体）

- 新模块新增**零改动** `app.py`/`router_registry.py`/菜单/权限中央文件即可上线（阶段 1+2 达成）。
- 权限有单一真源 `roles.yaml`，审计可输出覆盖率，无未声明权限的非 public 路由（阶段 2 达成）。
- 模块边界有 gate 守护，新增跨界违规被拦截（阶段 4 达成）。
- 全程现有功能零回归（每阶段验收 + 部署验证证据）。
- 旧路径在对应层迁移完成后已删除，无长期双轨。

---

## 8. 待 writing-plans 细化的项

- 每阶段的具体 `semantic_regression` / ORC 不变量（逐条可工具验证，不写"设计意图"）。
- 阶段 1 路由清单 diff 的具体比对脚本 / 命令。
- 阶段 2 影子比对的实现方式与差异判定标准。
- 阶段顺序是否串行（建议串行：阶段 2 鉴权稳定后再大规模 CRUD 迁移）。
