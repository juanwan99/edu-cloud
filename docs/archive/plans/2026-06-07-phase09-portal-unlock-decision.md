<!-- no-projectctl -->
# Phase 0.9 — Portal Phase 1 条件解锁裁定（CONDITIONAL UNLOCK）

> **性质**：解锁裁定记录（持久化设计者裁定，非新实施计划）。本文件只固化「Portal Phase 1 是否解锁、以何条件解锁」的裁定与证据，**不引入任何业务代码 / 语义改动，不部署、不重启、不迁移 DB**。
> **上游**：`docs/plans/2026-06-07-phase08-acceptance-decision.md`（Phase 0.8 地基验收 = 源码 PASS，Portal = BLOCKED，留 3 项待设计者裁定）。
> **本文定位**：phase08 的 3 项待裁定已由设计者（sid:a4e5781a）裁决——结论 **CONDITIONAL UNLOCK**。本文持久化该裁决，并把「解锁 → 实现」之间的运行态前置写成硬条件。

## 元信息（锚点）

| 字段 | 值 | 证据 |
|------|-----|------|
| Claude session（持久化执行者） | 本会话 | 任务输入 |
| 裁定来源 session | `sid:a4e5781a` | 任务输入：Portal 解锁裁定规划 |
| HEAD | `56ccd03a0178858cdf2146079b2d445b1e14c34b`（`56ccd03`） | `git rev-parse HEAD`（本轮实测） |
| 分支 | `feat/module-governance-repair`（upstream: none） | `git branch --show-current`（本轮实测） |
| Working tree | clean（`git status --short` 空） | 本轮实测 |
| 上游裁定文档 | `docs/plans/2026-06-07-phase08-acceptance-decision.md` | 见其 §Portal Unlock Decision（结论 BLOCKED + 3 待裁定项） |
| 裁定日期 | 2026-06-07（Asia/Shanghai） | — |

## 摘要结论（三句话）

1. **Portal Phase 1 = CONDITIONAL UNLOCK** —— 不是 unconditional unlock，也不是继续 KEEP BLOCKED。源码地基已 PASS（phase08 §B/§C/§E，最新 codex-review 对 `3688f32` 判 PASS/0 finding，机器真源 receipt 绑定），满足解锁的**代码侧前提**；解锁裁定本身由设计者签署生效，但**进入实现受运行态前置硬门控**。
2. **解锁 ≠ 立即开工** —— Portal Phase 1 实现必须在三项运行态/线上条件全部转绿后方可落地：① DB doctor 红项清账 ② 部署/运行态 hash 对齐当前 HEAD ③ 线上验证 module gating / portal services 不破坏 fail-closed。任一未满足 → 解锁裁定成立但**实现仍 gated**。
3. **第一刀范围已定 + 地基语义不变量冻结** —— Portal Phase 1 第一刀 = 前端聚合首页 + 消费**现有** `/api/v1/portal/*`（5 端点已实装，见 §3 证据）+ 服务卡片按 `moduleGateFromAuth` 门控；**禁止修改 `DEFAULT_ENABLED` / module middleware / authGuard / module-semantics 语义**。

---

## 1. 裁定（与 phase08 三项待裁定的逐项映射）

phase08 §「待设计者裁定项（解锁前需明确）」留下 3 项；本文逐项给出设计者裁决：

| phase08 待裁定项 | 设计者裁决（sid:a4e5781a） |
|---|---|
| **① 验收口径**：是否认可「源码地基 PASS + 运行态红灯由运行侧另行清账」即可解锁？还是要求运行态先转绿？ | **CONDITIONAL UNLOCK**：源码 PASS 即解锁裁定成立（解锁动作签署），但**实现落地必须等运行态红灯先转绿**（条件一/二/三）。即「解锁是设计者裁定，实现是运行态门控」——两者解耦但都必经。 |
| **② studio drift 处置** | studio-frontend-entry-missing **不阻塞**条件解锁；但该 drift **只能在 Portal services 真正提供 studio 入口后再关闭**，不得为解锁提前删登记。 |
| **③ Portal Phase 1 范围** | 第一刀范围锁定：**前端聚合首页 + 消费现有 `/api/v1/portal/*` + 服务卡片按 `moduleGateFromAuth` 门控**（详见 §4）。 |

### 裁定原文

> **Portal homepage aggregation (Phase 1) = CONDITIONAL UNLOCK。**
> - **不是** unconditional unlock（不得在运行态红灯下直接开写 Portal）。
> - **不是** 继续 KEEP BLOCKED（phase08 的「等设计者裁定」状态已终结）。
> - 解锁裁定由设计者签署成立；**进入实现**受 §2 三条件硬门控。

---

## 2. 解锁条件（实现落地前必须全绿）

> 三条件是「解锁裁定成立」到「Portal Phase 1 实现可开工」之间的硬门控。任一未满足 → 不得进入实现。条件的执行属**运行侧 / 部署侧动作**，不在本文档（文档固化）范围内。

### 条件一 — 先修 DB doctor 红项

- **现状（本轮实测，2026-06-07T15:35:03+08:00）**：`scripts/truth doctor --json` → `overall: red`，`issue_count: 1`，`DB_SCHEMA_DRIFT`（severity red，`blocks_completion: true`）。
- **具体红项**（NOW.md:27-28）：ORM 声明 `exam_import_sessions` 表但 DB 无此表；DB 含 orphan 表 `_audit_log`。
- **达标判据**：`scripts/truth doctor --json` → `overall: green`（或 DB_SCHEMA_DRIFT 消除，`blocks_completion` 不再成立）。
- **执行路径**（运行侧，非本文档动作）：`/home/ops/projects/edu-cloud/.venv/bin/python scripts/db_doctor.py --strict` 定位 → `python scripts/db_migrate [target]`（唯一 migration 路径，直接 alembic 被 guard 阻断）。**本文档不迁移 DB。**

### 条件二 — 部署 / 运行态 hash 对齐当前 HEAD

- **现状（guardian.watch.v1 实时快照，`logs/guardian-state.json`，generated_at 2026-06-07T07:42:01Z = 15:42 +08:00）**：HEAD `56ccd03`，但运行 / 部署态三处均落后 HEAD——
  - **后端**：port 9000 运行 hash `b763888`（PID 1941123，boot 2026-05-29 19:42:02，service edu-cloud）≠ HEAD → `BACKEND_DRIFT` + `PARALLEL_VERSION_DRIFT`（均 blocks_completion）。
  - **前端 dist / nginx**：`dist_hash=bfdbd50`（build 2026-06-07T00:17:27）/ `nginx_hash=bfdbd50`（线上）≠ HEAD → `BUILD_DRIFT`（blocks_completion）。
  - guardian overall=red，red_count=5。
- **证据修正**：NOW.md:24 的 `Current live hash: d9b1c56` 是 2026-05-26 旧 truthline 锚点，已被实际运行态 backend `b763888` / dist `bfdbd50` 取代；无论取哪个值，结论「运行态未对齐 HEAD」一致——本分支地基工作（0.5→0.7E→0.8）尚未完整部署到 `https://mcu.asia`。
- **达标判据**：`scripts/truth-status.sh /home/ops/projects/edu-cloud` truthline 全绿——backend `/api/v1/version` / `frontend/dist/version.json` / `https://mcu.asia/version.json` 三处 hash 一致且 == HEAD；guardian `BACKEND_DRIFT` / `BUILD_DRIFT` / `PARALLEL_VERSION_DRIFT` 清零。
- **执行路径**（部署侧，非本文档动作）：frontend build + 部署 dist + restart backend（guardian actions：`scripts/codex-verify frontend` / `sudo systemctl restart edu-cloud`），使三处对齐 HEAD。**本文档不部署 / 不构建 / 不回退 dist / 不重启服务。**

### 条件三 — 线上验证 module gating / portal services 不破坏 fail-closed

- **要求**：部署对齐后，在 `https://mcu.asia` 线上验证：
  1. **module gating fail-closed 仍成立** —— 缺 `SchoolModule` 行的非默认模块（teaching/research/study_analytics）线上仍 403（0.7E absent-row 收口语义，`module_middleware.py` `module_enabled_default`）；前端可见性 surface 与后端 403 面同源（0.7A `moduleGateFromAuth`）。
  2. **portal services 不破坏 fail-closed** —— Portal 聚合页 / `/api/v1/portal/*` 的服务卡片按学校模块开关门控，**不得**让禁用模块的入口对学校用户可见或可达；Portal 作为聚合层不得绕过 module middleware / authGuard。
- **达标判据**：线上回归确认上述两点为真（无 module-gating fail-open 回归）。
- **执行路径**（线上验证，非本文档动作）。**本文档不做线上验证。**

> **三条件门控总则**：① ∧ ② ∧ ③ 全绿 → Portal Phase 1 实现可开工；任一红 → 解锁裁定成立但实现 gated，不得开写。

---

## 3. Portal 后端端点现状（条件三 / 第一刀范围的代码侧证据）

「消费**现有** `/api/v1/portal/*`」属实——portal 后端 5 端点已实装（本轮实测）：

```
src/edu_cloud/modules/portal/router.py:25  @router.get("/summary",         response_model=PortalSummary)
src/edu_cloud/modules/portal/router.py:33  @router.get("/todos",           response_model=list[TodoItem])
src/edu_cloud/modules/portal/router.py:41  @router.get("/messages",        response_model=list[MessageItem])
src/edu_cloud/modules/portal/router.py:49  @router.get("/calendar-digest", response_model=list[CalendarDigestItem])
src/edu_cloud/modules/portal/router.py:57  @router.get("/services",        response_model=list[ServiceEntry])
```

- portal 模块文件齐备：`router.py` / `service.py` / `schemas.py` / `MODULE.md` / `__init__.py`（`src/edu_cloud/modules/portal/`，本轮 ls 实测）。
- `/api/v1/portal` 在 module middleware 中为 **exempt**（聚合层在 `service.py` 内部按 `enabled_module_codes` 逐项过滤——见 module-semantics design §1.1/§1.3），符合 portal-aggregation-contract「聚合不拥有业务数据、不直查源表」。
- contract（`docs/governance/portal-aggregation-contract.md`）将这 5 端点列为 "Future Portal APIs"，但 router.py 已实装 → 第一刀「消费现有 `/api/v1/portal/*`」有真实端点支撑，**不需要新建后端聚合 API**。

---

## 4. Portal Phase 1 第一刀范围（设计者裁定，实现期约束）

> 本节为裁定记录的范围声明，供实现期（条件全绿后）执行者遵循；本文档不实现任何一项。

### 范围内（第一刀）

1. **前端聚合首页** —— Portal homepage aggregation 前端壳 + 聚合视图。
2. **消费现有 `/api/v1/portal/*`** —— summary / todos / messages / calendar-digest / services（§3 已实装），前端改为消费这 5 个聚合端点，而非逐个直调业务模块端点。
3. **服务卡片按 `moduleGateFromAuth` 门控** —— 服务卡片可见性经 `frontend/src/config/routeAccess.js` 的 `moduleGateFromAuth(auth)` 取门控上下文 `{exempt, modulesLoaded, enabledModules}`（0.7A 引入），与 authGuard 数学等价 fail-closed（allow IFF 无 school_id 豁免 OR (已加载 ∧ 启用)）。

### 不变量（禁止修改 — 地基语义冻结）

> 与 phase08 §Must Not Change、module-semantics design §9 一致。Portal Phase 1 第一刀**只在前端聚合层动作**，不得触碰以下地基：

- **不改 `DEFAULT_ENABLED`**（`src/edu_cloud/models/school_settings.py:35` = `{exam, grading, homework, calendar, studio, conduct}`）——teaching/research/study_analytics 不得擅自加入。
- **不改 module middleware**（`src/edu_cloud/api/module_middleware.py`：`resolve_module_code` / `_longest_prefix_match` / `module_enabled_default` / `ROUTE_MODULE_MAP` / `EXEMPT_PREFIXES`）——不削弱后端 403 fail-closed。
- **不改 authGuard**（`frontend/src/router/index.js` 直达 URL 二次门控）——Portal 对齐它，不弱化它。
- **不改 module-semantics 语义**（`docs/governance/module-semantics.yaml` known_drift 四元组 / 期望表 / `scripts/governance/check_module_semantics.py` 6 check）——除非设计者另行裁定。
- **不绕过门控**：Portal 聚合层不得让禁用模块入口可见/可达（条件三的前端面）。

---

## 5. studio drift 处置（裁定）

- **现状**：known_drift 仅剩 1 条 —— `studio-frontend-entry-missing`（`docs/governance/module-semantics.yaml:120`；consumer: frontend / locus: studio-entry / expect: present / actual: absent / **severity: ux**）。
- **裁定**：
  - studio drift **不阻塞** Portal Phase 1 条件解锁（severity 仅 ux，非 security）。
  - 但该 drift **只能在 Portal services 真正提供 studio 入口后再关闭**——即 Portal 第一刀（§4）通过 `/api/v1/portal/services` 的 ServiceEntry 暴露 studio 服务卡片、studio 前端入口真实存在后，方可删 `module-semantics.yaml` 该登记 + `_FRONTEND_DRIFT_PROBES` 探测器。
  - **禁止**为「解锁好看」提前删 studio drift 登记（守卫 stale-drift 检测会 fail-closed 报红：drift 不成立却保留 / 入口未present却删登记，二者皆红）。

---

## 6. 不做（明确边界 — 本文档 = 文档固化）

- 不改任何业务代码 / 前端 / 中间件 / authGuard / module-semantics。
- 不修 DB（不跑 db_migrate / 不迁移 `exam_import_sessions`）。
- 不部署 / 不 build / 不回退 dist / 不重启服务。
- 不删任何 known_drift 登记（含 studio）。
- 不进入 Portal Phase 1 实现（实现受 §2 三条件门控，属后续会话）。

---

## 7. Next Executor Packet（给条件清账者 + Portal 实现者）

### Goal

- **若任务为运行态清账**：依 §2 条件一（DB doctor）+ 条件二（部署 truthline 对齐 HEAD `56ccd03`），使运行态全绿；再做 §2 条件三线上 fail-closed 回归。
- **若任务为 Portal Phase 1 实现**：**必须先确认 §2 三条件全绿**（否则解锁裁定成立但实现仍 gated，不得开写）；严格限定 §4 第一刀范围，遵守 §4 不变量。

### 入口锚点

- HEAD：`56ccd03`，分支 `feat/module-governance-repair`。
- 状态命令（取 volatile 实时值）：
  ```bash
  scripts/truth-status.sh /home/ops/projects/edu-cloud      # live hash / truthline（条件二）
  scripts/truth doctor --json                               # DB doctor（条件一）
  uv run python scripts/governance/check_module_semantics.py --check   # 门控守卫（应绿）
  ```

### Must Preserve（不得回退）

- Phase 0.5 / 0.6 / 0.6C / 0.7A / 0.7B / 0.7D / 0.7E / 0.7E-R1 全部成果。
- 后端 403 面 ↔ 前端可见性面「单一真源」fail-closed 语义（`module_enabled_default`，`module_middleware.py` 对齐 `school_settings_service.py:109`）。
- `_FRONTEND_DRIFT_PROBES` 中 teaching 回退探测器（academic 回退守护）。

### Must Not Change（地基不变量）

- 见 §4 不变量段（`DEFAULT_ENABLED` / module middleware / authGuard / module-semantics 语义）。
- 不在 §2 三条件全绿前进入 Portal Phase 1 实现。

---

## 8. 明确结论（复述，供索引引用）

- ✅ **Portal Phase 1 = CONDITIONAL UNLOCK**（设计者 sid:a4e5781a 裁定）——非 unconditional、非 KEEP BLOCKED。
- 🔒 **实现 gated by 运行态/DB cleanup**：条件一（DB doctor 红→绿）∧ 条件二（部署 hash 对齐 HEAD `56ccd03`）∧ 条件三（线上 module gating / portal services fail-closed 不破坏），全绿方可开工。
- 🎯 **第一刀范围**：前端聚合首页 + 消费现有 `/api/v1/portal/*`（5 端点已实装，`router.py:25-57`）+ 服务卡片按 `moduleGateFromAuth` 门控。
- 🧊 **地基冻结**：禁改 `DEFAULT_ENABLED` / module middleware / authGuard / module-semantics 语义。
- 🟨 **studio drift**：不阻塞解锁；仅在 Portal services 真正提供 studio 入口后再关闭，禁止提前删登记。
