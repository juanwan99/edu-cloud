# 模块化架构「渐进接入」设计（承接 P0–P6 诊断）

> **定位**：本文是「是否 + 如何把 P0–P6 模块化架构接入生产」的 **design spec**（brainstorming 产物）。
> **前序**：诊断报告 `2026-05-29-modular-arch-diagnosis.md`（codex-review plan FAIL 的逐条验证）；接入 handoff `2026-05-29-modular-arch-integration-handoff.md`。
> **下一步**：本 spec 批准后转 writing-plans 产出分阶段 implementation plan（每阶段独立 plan + codex-review）。
> **作者**：Claude（brainstorming）。**决策者**：用户（体系设计者）。**已吸收 GPT 跨模型设计评审，见 §9。**

---

## 1. 决策结论（已与设计者对齐）

| 决策点 | 结论 | 依据 |
|--------|------|------|
| 要不要接入 | **接入**（非搁置、非回退） | 设计者确认 edu-cloud 后续仍会**频繁加新功能模块**，"零改动接入"架构收益高 |
| 四痛点取舍 | **四个全保留**（路由中央集权 / 权限分散 / 模块耦合 / CRUD 重复） | 设计者确认四个痛点均真实困扰，无可 YAGNI 砍除项 |
| 接入方式 | **方向 A：渐进分层接入**（按风险从低到高排队，逐阶段独立审查/部署/回滚） | 整套一次性通电 = 把 6 个 HIGH 摊在动核心的一刀上，与"不破坏已有"和 L015 教训冲突 |
| 租户隔离策略 | **fail-closed（精确语义，见 §4 阶段3 + §9 F-01）**：区分「角色授权全量范围」(合法全校可见，如 platform/校级管理员，`get_visible_class_ids(role)==None` → 放行) 与「缺失租户上下文」(受限角色未解析出 scope → 拒绝/空)。**禁止 `None=>[]` 一刀切**——既不误伤合法全量角色，也绝不返回越权跨租户数据 | 设计者拍板 fail-closed 方向；GPT 评审 F-01 精确化语义（`permissions.py:25,60`） |

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
- **代码存放位置**：架构 WIP（P0–P6 约 31 文件 + events 重构，**含 P0 审计脚本 `audit_boundaries.py`/`audit_permissions.py` 等**——故工作树当前查无此文件，属正常）已 `git stash -u`，**不可变 object = `38fab1d548cc026ad81fea1aae172727398e383a`**（`stash@{0}` 仅为可变别名，GPT F-07）。工作树 clean。**接入第一步必须 `git stash apply 38fab1d`（或 `git stash pop`）恢复。** writing-plans 须锚定此不可变 object + 当时的不可变 commit SHA，不依赖会漂移的 `stash@{0}`/`HEAD`。
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

### 阶段 0：恢复 WIP + 前置边界 gate（P0-restore，GPT F-04）
- `git stash apply 38fab1d`（不可变 object）恢复架构 WIP 至**独立 git worktree**隔离作业（子代理闭环模式：worktree + manifest + diff_hash 绑定）；恢复后立即在 worktree commit，不再依赖可变 stash 别名（F-07）。
- 基线测试快照：恢复后先跑全量测试，记录"恢复态基线"（区分新架构引入的失败 vs 真实回归）。
- **边界 baseline gate 前置**（不再等到阶段4）：恢复出 `audit_boundaries.py` 后**立即**冻结当前 139 违规为 baseline 并启用 **negative-delta gate**（新增违规即失败）。理由：阶段 1–3 自身会改动 `app.py`/`auth.py` 等中央文件，若 gate 拖到最后，过渡期新引入的耦合/循环依赖将无人拦截。存量 139 的**消除**仍留到阶段4（见下），但**冻结闸门必须在动任何代码前就位**。

### 阶段 1：模块自注册（🟢 低风险，收益最快）
- **改动**：`app.py` 启动在旧 `register_all` 之外，**并行**调用 `load_all_manifests()`/`include_manifest_routers()`，让声明了 manifest 的模块自动挂载路由。
- **旧路径**：旧静态路由表**完整保留**，新旧并存；旧模块暂不迁移。
- **验收**：① 旧 320 路由全部仍可达（路由清单 diff = 0 丢失）；② 新样例模块（calendar）路由经 manifest 挂载可达；③ **路由唯一性不变量（GPT F-03，呼应单入口原则）**：全部已注册路由 `(method, path)` 无重复、每路由可追溯到唯一 owner module；`include_router` 循环须有 ownership/uniqueness 守卫，杜绝新旧并存产生的"幽灵副本"与 old-wins/new-wins 顺序依赖（"不丢路由 + calendar 可达"不足以证明无重复）；④ 全量后端测试不低于恢复态基线；⑤ `curl 127.0.0.1:9000/api/v1/version` 确认部署生效。
- **Tier**：T3（碰 `app.py` 启动路径，结构性中心文件，主会话独占）。
- **回滚**：移除 app.py 新增的 manifest 加载调用即恢复旧行为。

### 阶段 2：权限单源（🔴 最高风险，三道闸隔离慢切）
- **2a 观察模式**：`roles.yaml` 成为权限单一真源，`PermissionCatalog`/`compile_permissions()` 上线；`audit_permissions.py` + `SecureRouter.validate()` 仅**报告**漏配/未声明权限的路由，**不阻断启动**。auth 运行时仍走旧 `Permission`/`ROLE_PERMISSIONS`。
- **2b 影子比对**：对每个角色×每个权限码，比对"新编译结果"与"旧 ROLE_PERMISSIONS"，输出差异报告；**目标是差异收敛到可解释的 0**（任何不等价都要逐条定性：是 bug 还是有意收紧）。
- **2c 切换**：影子比对全绿后，用 **feature flag** 把 auth 运行时切到编译器，flag 可秒级回滚。切换稳定运行确认后，删除旧后端 `Permission`/`ROLE_PERMISSIONS`。
- **2d 前后端单源一致（GPT F-02，HIGH）**：前端 `frontend/src/config/permissions.js` 当前是后端 `ROLE_PERMISSIONS` 的**手写镜像**（`permissions.js:1` 自述"镜像后端"），驱动菜单/侧栏 gate。"单源"切换**必须同步前端**——前端权限改为从 `roles.yaml` 编译产物**派生/生成**（而非继续维护手写镜像），否则会出现"后端切新源、前端仍用旧镜像"的用户可见菜单/UI 回归。前端改动须经 `vite build` 上生产验证（见 §5 前端红线）。
- **旧路径**：后端旧权限保留到 2c 切换稳定；前端旧镜像保留到 2d 派生机制上线并经生产验证。
- **Tier**：T3（碰 `auth.py` 全站鉴权，最高风险）。
- **回滚**：feature flag 翻回旧鉴权。

### 阶段 3：CRUD 基类（🟡 中）
- **前置硬门槛（fail-closed 精确语义，GPT F-01，🔴 鉴权红旗）**：把 `BaseService` 的租户过滤改为**区分两种「空」**——① 角色被授权全量可见（`get_visible_class_ids(role)==None`，如 platform/district/school_admin/principal/academic_director，见 `permissions.py:25,60`）→ 放行全部；② 受限角色且未解析出 `school_id`/`visible_class_ids`（缺失租户上下文）→ 拒绝/返回空。**禁止 `None=>[]` 一刀切**（会误伤①类合法全量角色）。实现须引入显式的"租户范围"状态（如 `UNRESTRICTED` vs `MISSING` 哨兵），不靠裸 `None` 兼表两义。配套测试**分别**断言①②两种语义（替换 F-005 误导断言）。⚠️ 须独立修复设计 + Semantic Regression Gate。
- **改动**：新管理页 / 新 service 继承 `BaseService`；**老页面/老 service 不动**，按需逐步迁移。
- **验收**：fail-closed 精确语义单元测试（①②两态）+ 至少一个真实新模块跑通 CRUD + 现有功能无回归。
- **Tier**：T2~T3（视迁移范围）。

### 阶段 4：存量边界债消除（🟡 中；冻结 gate 已在阶段0前置）
- **改动**：baseline gate（冻结 139 + negative-delta）已于阶段0就位。本阶段做**存量消除**：逐步拆解 139 违规 + `grading→exam→grading`/`exam→pipeline→exam` 循环依赖，每消除一批就收紧 baseline。
- **不阻塞**：存量消除可在阶段1–3 其后排期，不阻塞接入主线。
- **Tier**：T2。

### 贯穿性设计约束：事件事务边界（GPT F-05，不可推迟）
GPT 指出：现有 `publish_service.py:47,55` 在 `db.flush()` 后**立即 emit**，且 `events.py:36-52` 把 handler 异常 `try/except` 吞掉——这是**设计级生命周期边界**，不是实现细节，**不能推迟到"迁移有副作用模块时再说"**。因此：
- **进入任何涉及领域事件副作用的模块迁移前**，先定义清楚事务边界契约：领域事件必须在**外层事务提交后**才 flush（transactional outbox），事务回滚则事件不发；handler 失败有显式的重试/落账策略，**禁止静默吞异常**。
- 这是鉴权之外的第二个**红旗区**：须独立修复设计 + Semantic Regression Gate，禁止把 immediate-emit + try/except 当作可接受 fallback。

---

## 5. 跨阶段铁律

- **每阶段独立闭环**：独立 plan → `codex-review plan` → 实现 → `codex-review code` → 部署验证（`curl version` 看 git_hash + source_dirty + 测试证据，[[L015]]）→ 独立回滚点。
- **新旧并存仅限过渡期**：该层迁移完成立即删旧路径，禁止长期双轨（[[single-version-discipline]]）。
- **鉴权切换三道闸**：观察 → 影子 → flag 切换，任一闸不绿不进下一步。
- **前端生产红线（GPT F-06）**：任何影响角色/权限/模块/菜单/侧栏的变更，完成证据**必须包含 `frontend/dist` 构建 + `https://mcu.asia` 生产验证**，不接受"只验后端 version/route/health"（交付合同 = `frontend/src` → `vite build` → `frontend/dist` → mcu.asia）。
- **隔离作业**：worktree 隔离 + manifest（agent_id/base_sha/head_sha/diff_hash/review_gate_id）绑定。
- **证据优先**：所有"完成"声明附 git log / test output / curl version；不变量逐条工具验证，不重蹈"设计意图当既成事实"。

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 阶段 2 切鉴权切崩全站 | 三道闸 + 影子比对差异归零 + feature flag 秒回滚；旧鉴权保留到切换稳定 |
| 新旧路由并存期出现"幽灵副本"（单入口原则） | 阶段 1 验收强制路由清单 diff = 0 + 路由唯一性不变量（method/path 无重复、有 owner） |
| BaseService 租户漏洞被生产触发 / fail-closed 误伤全量角色 | 阶段 3 前置硬门槛：fail-closed 精确语义（区分授权全量 vs 缺失上下文）+ 两态测试先行，未改完不让任何生产子类继承 |
| 权限单源后端切了前端没切 | 阶段 2d：前端权限从 roles.yaml 派生，经 vite build 生产验证 |
| 存量 139 违规拖累进度 | 只冻结 baseline 不要求清零；存量另排期 |
| 过渡期新增边界违规无人拦 | 边界冻结 gate 前置到阶段0，先于一切代码改动 |
| stash 丢失 | 阶段 0 恢复后立即在 worktree commit，不再依赖 stash |

---

## 7. 成功标准（整体）

- 新模块新增**零改动** `app.py`/`router_registry.py`/菜单/权限中央文件即可上线（阶段 1+2 达成）。
- 权限有单一真源 `roles.yaml`，审计可输出覆盖率，无未声明权限的非 public 路由；**前后端权限同源**（阶段 2 达成）。
- 模块边界有 gate 守护，新增跨界违规被拦截（阶段 0 起生效）。
- 涉及权限/菜单/模块的变更已 `vite build` 并在 `https://mcu.asia` 生产验证可见（GPT F-06，非仅后端验收）。
- 全程现有功能零回归（每阶段验收 + 部署验证证据）。
- 旧路径在对应层迁移完成后已删除，无长期双轨。

---

## 8. 待 writing-plans 细化的项

- 每阶段的具体 `semantic_regression` / ORC 不变量（逐条可工具验证，不写"设计意图"）。
- 阶段 1 路由清单 diff + 路由唯一性的具体比对脚本 / 命令。
- 阶段 2 影子比对的实现方式与差异判定标准；前端权限派生机制（从 roles.yaml 生成）。
- 阶段 3 fail-closed 的"租户范围"状态机具体实现（`UNRESTRICTED`/`MISSING` 哨兵）。
- 阶段顺序是否串行（建议串行：阶段 2 鉴权稳定后再大规模 CRUD 迁移）。

---

## 9. GPT 跨模型设计评审吸收（2026-05-29）

> codex exec（GPT-5.5）独立设计评审。**总体结论：接入方向有条件成立，无证据要求永久搁置或推倒重做。** 7 条 finding 经 Claude 工具独立核验**全部成立**，已逐条吸收进本 spec。原始日志：`docs/plans/.codex-design-review-raw.log`。

| ID | 严重性 | 议题 | 吸收位置 |
|----|--------|------|----------|
| F-01 | HIGH | fail-closed 不能 `None=>[]` 一刀切，会误伤合法全量可见角色（`permissions.py:25,60`） | §1 决策表 + §4 阶段3 前置硬门槛（精确语义 + SRG） |
| F-02 | HIGH | 前端有独立 `ROLE_PERMISSIONS` 镜像（`permissions.js:1,10`），权限单源切换必须同步前端 | §4 阶段 2d |
| F-03 | MED | `include_router` 无唯一性守卫，路由 diff=0 不足以证明无幽灵副本 | §4 阶段1 验收③ 路由唯一性不变量 |
| F-04 | MED | 边界 baseline gate 应前置（否则阶段1–3 新增违规无人拦）；`audit_boundaries.py` 在 stash 内 | §4 阶段0 前置 gate + 阶段4 retitle 存量消除 |
| F-05 | MED | 事件 `flush 后即 emit + try/except 吞异常`（`publish_service.py:55`/`events.py:36`）是设计级边界，不可推迟 | §4 贯穿性设计约束：事件事务边界 |
| F-06 | MED | 成功标准漏前端 dist/prod truthline 红线 | §5 前端生产红线 + §7 成功标准 |
| F-07 | LOW | spec 锚 `stash@{0}`/`HEAD` 是可变引用 | §2.2 固化不可变 object `38fab1d` |

**进入 writing-plans 前的设计层 blocker（GPT 列）**：F-01~F-05，均已在本 spec 定清设计方向。其中 F-01（鉴权）、F-05（事件生命周期）为红旗区，writing-plans 阶段须配 Semantic Regression Gate，不在本设计层给具体代码改法。
