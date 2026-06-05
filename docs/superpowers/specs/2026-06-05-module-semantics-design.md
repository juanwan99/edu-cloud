# Phase 0.5 模块语义统一 设计（2026-06-05）

> 项目：`/home/ops/projects/edu-cloud`，分支 `feat/module-governance-repair`
> 性质：纯新增设计文档，未触碰任何代码。
> 上游：`docs/plans/2026-06-05-foundation-governance-master-plan.md` §4 Phase 0.5、§3.1 契约 C3。
> 接手交接：`docs/plans/2026-06-05-foundation-phase0-handoff.md` §7。

---

## 0. 一句话

建立架构模块 ↔ 学校开关码的**单一声明式真源**，并加一个**只读校验式守卫**把四方消费者的现状冻结成基线、禁止新增漂移；**不改任何业务行为**。

---

## 1. 病灶（带证据）

代码库存在两套模块概念：

| 概念 | 数量 | 真源 |
|---|---|---|
| 架构模块 | 23 | `src/edu_cloud/modules/*/`（`ls` 实测 23 个目录，含 portal 聚合层，排除 `__pycache__`）|
| 学校开关码 `MODULE_CODES` | 9 | `src/edu_cloud/models/school_settings.py:20-30` |

`MODULE_CODES` = {exam, grading, homework, study_analytics, research, teaching, calendar, studio, conduct}
`DEFAULT_ENABLED` = {exam, grading, homework, calendar, studio, conduct}（`school_settings.py:35`）

两者之间的映射**已存在，但隐式、四重复制、零守卫**。四方消费者各维护一份：

| 消费者 | 位置 | 形态 |
|---|---|---|
| 后端 API gating | `src/edu_cloud/api/module_middleware.py:22` `ROUTE_MODULE_MAP` | 路由前缀 → 开关码（16 前缀）|
| 前端路由守卫 | `frontend/src/config/routeAccess.js:5` `ROUTE_ACCESS_REQUIREMENTS` | 前端路由 → 开关码 |
| 侧边栏 | `frontend/src/config/sidebarConfig.js:5` `SIDEBAR_GROUPS` | 菜单项 → 开关码 |
| Portal 服务目录 | `src/edu_cloud/modules/portal/service.py:20` `SERVICE_CATALOG` | 9 条服务 → 开关码 |

### 1.1 四方覆盖矩阵（调查实测）

| 开关码 | 后端 middleware | 前端 routeAccess | sidebar | Portal catalog |
|---|---|---|---|---|
| exam | √ 7 前缀 | √ | √ | √ |
| grading | √ /grading,/marking | √ | √ | √ |
| homework | √ | √ | √ | √ |
| study_analytics | √ /analytics | √ | √ | √ |
| research | √ /knowledge,/knowledge-tree,/bank | √ | √ | √ |
| calendar | √ | √ | √ | √ |
| **studio** | √ /studio | **✗** | **✗** | √ |
| **conduct** | **✗（fail-open）** | √ | √ | √ |
| **teaching** | **✗ 无路由** | **✗** | **✗** | √ 空壳入口 |

仅 Portal `SERVICE_CATALOG` 覆盖全 9 个。三个确证漂移：

1. **conduct 后端 fail-open**：conduct 有路由 `/api/v1/conduct`（`conduct/admin_router.py:34` / `notification_router.py:14` / `parent_router.py:21`），但 `module_middleware.py` 中 `grep conduct = 0` —— 既不在 `ROUTE_MODULE_MAP` 也不在 `EXEMPT_PREFIXES`。关掉 conduct 开关后，前端隐藏入口但后端 API 照常返回数据。**这是当下存在的安全/一致性 bug。**
2. **studio 前端缺入口**：后端有 gating（`module_middleware.py:34`）+ Portal 有卡片（`service.py:84-92`），但前端 routeAccess/sidebar 无任何 studio 入口。
3. **teaching 空壳**：`MODULE_CODES` 有、不在 `DEFAULT_ENABLED`、后端无路由前缀、前端 `/academic/*` 不挂 moduleCode（`routeAccess.js:22-25`、`sidebarConfig.js:36-41`），仅 Portal 给了它 route `/academic` 的假入口（`service.py:66-74`）。

---

## 2. 目标与范围

### 目标
- 建立单一声明式映射真源，覆盖 23 架构模块 + 9 开关码全量。
- 加四方一致性静态守卫：四方现状冻结为基线，已知 3 漂移登记放行，**任何新增漂移即 CI 红**。
- `teaching` 空壳显式登记。

### 范围边界（行为不变契约）
- **四方源码一行不改**（middleware / routeAccess / sidebar / SERVICE_CATALOG 均不动）。
- conduct / studio / teaching 三个漂移**只登记不修复**，各自另开 Phase。
- AI 工具 `module_code` 归属**不动**（属 Phase 3，由 `scripts/governance/check_ai_tool_modules.py` 管）。
- 不删除现有任一映射表。

---

## 3. 真源 `docs/governance/module-semantics.yaml`（三层）

```yaml
version: 1

# ── 第一层：9 个学校开关码（镜像 school_settings.py::MODULE_CODES）
#    守卫校验：本层 == MODULE_CODES，防真源与 school_settings 脱节
school_module_codes:
  - exam
  - grading
  - homework
  - study_analytics
  - research
  - teaching
  - calendar
  - studio
  - conduct

# ── 第二层：23 架构模块 → 开关码归属（语义 owner，覆盖全 23）
#    作用：为 Phase 1/2/3 提供"架构模块该归哪个开关"的权威表
#    守卫校验：键覆盖全 23 模块、值 ∈ {9 开关码} ∪ {null}
#    注意：本层是语义声明，不驱动对四方/AI 工具现状的 fail（那由第三层负责）
architecture_to_module_code:
  exam: exam
  exam_import: exam
  scan: exam
  card: exam
  pipeline: exam
  paper: exam
  grading: grading
  marking: grading
  analytics: study_analytics
  profile: study_analytics
  adaptive: study_analytics
  knowledge: research
  knowledge_tree: research
  bank: research
  homework: homework
  calendar: calendar
  studio: studio
  conduct: conduct
  academic: teaching          # 语义归属；当前未接线，见 known_drift
  menu: null                  # 导航基础设施，无开关
  portal: null                # 聚合层，不拥有开关
  school: null                # 核心/管理基础设施
  student: null               # 基础信息/共享身份

# ── 第三层：四方期望覆盖 + 已知漂移登记
#    expected: 每个开关码该在哪几方有体现（守卫据此查缺失）
#    缺失项必须在 known_drift 登记，否则红
expected_consumers:
  exam:            [backend, route_access, sidebar, portal]
  grading:         [backend, route_access, sidebar, portal]
  homework:        [backend, route_access, sidebar, portal]
  study_analytics: [backend, route_access, sidebar, portal]
  research:        [backend, route_access, sidebar, portal]
  calendar:        [backend, route_access, sidebar, portal]
  studio:          [backend, portal]          # 前端缺，见 known_drift studio-*
  conduct:         [route_access, sidebar, portal]   # 后端缺，见 known_drift conduct-*
  teaching:        [portal]                    # 仅 Portal 空壳，见 known_drift teaching-*

known_drift:
  - id: conduct-backend-gating-missing
    where: src/edu_cloud/api/module_middleware.py (ROUTE_MODULE_MAP + EXEMPT_PREFIXES)
    detail: >
      conduct 有 /api/v1/conduct 路由但后端无任何 gating（fail-open）。
      关闭 conduct 开关后后端 API 仍返回数据。
    severity: security
    fix_phase: deferred-security-fix   # 安全 bug，建议独立优先修复，不在 Phase 0.5

  - id: studio-frontend-entry-missing
    where: frontend/src/config/routeAccess.js + sidebarConfig.js
    detail: studio 后端 + Portal 有，前端无路由/菜单入口。
    severity: ux
    fix_phase: deferred-frontend         # 独立前端入口补全，不在 Phase 0.5

  - id: teaching-empty-shell
    where: all-four-consumers
    detail: >
      teaching 开关码已声明且不在 DEFAULT_ENABLED；academic 架构模块未接线到它；
      仅 Portal SERVICE_CATALOG 给了 route /academic 的假入口。
    severity: semantic
    fix_phase: Phase 1+
```

---

## 4. 守卫 `scripts/governance/check_module_semantics.py`

只读校验，**不改写任何四方源码**。校验四类：

1. **真源自洽**
   - 第一层 `school_module_codes` == `MODULE_CODES`（import `school_settings`）。
   - 第二层 `architecture_to_module_code` 键集 == `src/edu_cloud/modules/*` 实际 23 模块（排除 `__pycache__`）。
   - 第二层值 ∈ `school_module_codes ∪ {null}`。
   - `expected_consumers` 键集 ⊆ `school_module_codes`。

2. **野值检查**：四方解析出的每个 `module_code` ∈ `school_module_codes`。
   - 后端：解析 `ROUTE_MODULE_MAP` values。
   - 前端 routeAccess / sidebar：正则/解析提取 `moduleCode:` 值（沿用 `check_permission_mirror.py` 解析前端文件的既有手法）。
   - Portal：import `SERVICE_CATALOG`，取 `module_code`。

3. **覆盖 + fail-closed**：对每个开关码，比对"实际出现的方" vs `expected_consumers` 声明的方。
   - 实际缺失但 `expected_consumers` 已不含该方 → 合法（如 studio 不含 frontend）。
   - 实际缺失且需被 `known_drift` 解释 → 必须有对应 `known_drift` 条目，否则红。
   - **未在真源声明的开关码出现在某方 / 某方出现真源未知的 module_code → 默认红（fail-closed，对齐总纲 C3 F-001）。**

4. **known_drift 收敛**：`known_drift` 只能 == 当前 3 条基线；新增漂移无登记即红。已修复的漂移从表中删除（基线收紧，不允许"修了还留登记"）。

CLI：`--check`（exit≠0 即违规，供 CI）、`--update`（仅在显式人工确认后刷新基线，与其它 governance 脚本一致）。

---

## 5. 测试 `tests/governance/test_module_semantics.py`（对齐契约 C3）

- **正例**：四方现状 + 当前真源 → 守卫绿。
- **反例矩阵**（每条必须真变红，浅层存在性不算通过）：
  1. middleware 改一条与真源冲突（如 `/api/v1/analytics → exam`）→ 红
  2. 前端 routeAccess 某条 moduleCode 漂移 → 红
  3. sidebar 某条 moduleCode 漂移 → 红
  4. SERVICE_CATALOG 某条 module_code 漂移 → 红
  5. **新增未登记缺口 / 出现真源未知的 module_code（未映射默认放行）→ 红**（fail-closed 反例）
  6. 真源第一层与 `MODULE_CODES` 故意不一致 → 红
  7. 第二层漏掉某个架构模块 → 红

实现用 monkeypatch / 临时构造输入注入反例，不污染生产源码。

---

## 6. 提交策略（总纲 §9，每批 < 8 文件、< 500 行）

- **Commit 1（声明真源）**：`docs/governance/module-semantics.yaml`（+ 如需，`foundation-boundaries.md` 补一句指向真源）。纯数据，doc commit。
- **Commit 2（守卫 + 测试 + CI）**：`scripts/governance/check_module_semantics.py` + `tests/governance/test_module_semantics.py` + `.github/workflows/test.yml` 纳入。含代码 → 走 `codex-review code`。

如后续要让四方派生自真源（行为变更）→ 另开 Commit 3 / 另开 Phase（Phase 2 范围），不与本设计混。

---

## 7. 验收标准

- `module-semantics.yaml` 覆盖 23 架构模块 + 9 开关码全量，teaching 空壳显式在册。
- `check_module_semantics.py --check` 在当前代码上**绿**（3 漂移已登记放行）。
- 七条反例测试全部真变红。
- 后端 `ROUTE_MODULE_MAP` / 前端 routeAccess / sidebar / Portal `SERVICE_CATALOG` 四方与真源一致性被校验；任一新增漂移 CI 红。
- 全程四方源码零改动（`git diff` 四方文件为空）。

---

## 8. 回滚边界

本 Phase 的 worktree + 两个独立 commit 即天然回滚单元：全部为新增文件（真源 yaml + 守卫脚本 + 测试 + CI 一行），回退 = 删除这两个 commit，不影响任何前序 Phase，无业务行为受影响（因本 Phase 不改行为）。

---

## 9. 不做（明确边界）

- 不改四方任一源码。
- 不修复 conduct / studio / teaching 三个漂移。
- 不动 AI 工具 `module_code` 归属。
- 不让四方派生自真源（Phase 2）。
- 不重构依赖循环（Phase 4）。
