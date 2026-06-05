# Phase 0.5 模块语义统一 设计 v2（2026-06-05）

> 项目：`/home/ops/projects/edu-cloud`，分支 `feat/module-governance-repair`
> 性质：纯新增设计文档，未触碰任何代码。
> 上游：`docs/plans/2026-06-05-foundation-governance-master-plan.md` §4 Phase 0.5、§3.1 契约 C3。
> 接手交接：`docs/plans/2026-06-05-foundation-phase0-handoff.md` §7。
> **v2 修订（回炉补强，回应代码审查 5 条）**：① backend fail-open 全集补全（academic/exam-imports/profile，不止 conduct）② 真源升级为逐入口期望表 ③ 守卫升级为逐路由比对 ④ 前端消费点补齐 4 方 ⑤ 架构模块真源改用 `modules.yaml`。详见 §10 修订记录。

---

## 0. 一句话

建立**逐入口**的架构模块 ↔ 学校开关码声明式真源，并加一个**逐路由比对的只读守卫**，把四方/多方消费者的现状冻结成基线、用精确可收敛的 `known_drift` 豁免已知漏洞、禁止新增漂移；**不改任何业务行为**。

---

## 1. 病灶（带证据，v2 补全）

代码库存在两套模块概念：

| 概念 | 数量 | 真源 |
|---|---|---|
| 架构模块 | 23 | `docs/governance/modules.yaml`（各模块 `MODULE.md` 聚合产物）|
| 学校开关码 `MODULE_CODES` | 9 | `src/edu_cloud/models/school_settings.py:20-30` |

`MODULE_CODES` = {exam, grading, homework, study_analytics, research, teaching, calendar, studio, conduct}
`DEFAULT_ENABLED` = {exam, grading, homework, calendar, studio, conduct}（`school_settings.py:35`）

两者之间的映射**已存在，但隐式、多重复制、零守卫**，且当前事实基线本身带 fail-open 漏洞。

### 1.1 后端 gating 真相（逐 prefix 扫描）

后端路由有**两种定义形态**：① `APIRouter(prefix="/api/v1/<module>")`（带模块名前缀）② `APIRouter(prefix="/api/v1")` + `@router.get("/grades")`（base-prefix + decorator 派生）。`module_middleware.py` 用 `path.startswith(prefix)` 匹配：不命中 `ROUTE_MODULE_MAP` 任何前缀且不在 `EXEMPT_PREFIXES` → `module_code=None` → 直接放行。**形态①逐一判定，4 个业务入口 fail-open**（有路由、语义该受控、却被放行）：

| prefix | 架构模块 | 语义应归开关 | 现状 | 证据 |
|---|---|---|---|---|
| `/api/v1/academic` | academic | teaching | **fail-open** | `academic/router.py:13`；`module_middleware.py:22` 无此前缀 |
| `/api/v1/conduct` | conduct | conduct | **fail-open** | `conduct/admin_router.py:34` 等 3 router；middleware 无 |
| `/api/v1/exam-imports` | exam_import | exam | **fail-open** | `exam_import/router.py:27`；middleware 无 |
| `/api/v1/profile` | profile | study_analytics | **fail-open** | `profile` router prefix；middleware 无 |

**形态②（v3 补，GPT review 发现）**：`student/router.py:21`、`teacher_router.py:22` 均 `prefix="/api/v1"`，decorator 派生 `/api/v1/grades`（`student/router.py:73`）、`/api/v1/teachers`（`teacher_router.py:107`），当前 pass-through。两者语义属基础信息/共享身份（同 router 的 `/students` `/classes` 已在 EXEMPT）→ 应 exempt。**纯 grep `prefix="/api/v1/<module>"` 会漏这类 → 守卫 route discovery 必须 prefix+decorator 展开（见 §4）。**

另有 `/api/v1/menus`（menu）、`/api/v1/portal`（portal）未 gating，但属导航基础设施 / 聚合层（Portal 在 `service.py` 内部已按 `enabled_module_codes` 逐项过滤），当前“放行”行为与“应 EXEMPT”一致 → 定性为“应显式登记 EXEMPT”，非业务 bug。grades/teachers 同此类（应显式 exempt）。

正确受 gating 的 16 条前缀（`ROUTE_MODULE_MAP`，全部正确）：
exams/subjects/questions/scan/card/templates/pipeline → exam；grading/marking → grading；analytics → study_analytics；knowledge/knowledge-tree/bank → research；calendar；studio；homework。

### 1.2 前端 moduleCode 消费点（v3：4 个可见性消费点 + 1 个设置写入点）

**4 个可见性/路由消费点**（守卫逐 route 比对对象）：

| 消费者 | 位置 | 形态 |
|---|---|---|
| 路由守卫 | `frontend/src/config/routeAccess.js:5` `ROUTE_ACCESS_REQUIREMENTS` | route → moduleCode |
| 侧边栏 | `frontend/src/config/sidebarConfig.js:5` `SIDEBAR_GROUPS` | item → moduleCode |
| 路由元数据 | `frontend/src/router/index.js` `meta.moduleCode` | route → moduleCode（conduct/exam/grading/study_analytics）|
| 首页硬编码 | `frontend/src/pages/DashboardPage.vue:437+` action `moduleCode` | grading/homework/study_analytics |

**1 个设置写入消费点（v3 补，GPT review 发现）**：`frontend/src/api/schoolSettings.js:15` `toggleModule(schoolId, moduleCode, enabled)` —— 这里 `moduleCode` 是**调用参数**（操作"开关模块"动作的 API），不是"按开关 gate 功能"的可见性消费。**性质不同，不纳入逐 route 比对**；但纳入"消费者源码零改" diff gate（§7），防止此处被静默改动。

排除：`frontend/src/router/_frozen/index.full.js`、`config/_frozen/sidebarConfig.full.js`（冻结快照，非活跃真源）。

### 1.3 Portal 服务目录

`src/edu_cloud/modules/portal/service.py:20` `SERVICE_CATALOG`，9 条服务，覆盖全 9 开关码（含 teaching 空壳入口 route `/academic`）。

### 1.4 三类已确证漂移（精确化）

1. **后端 fail-open ×4**（§1.1）：academic / conduct / exam-imports / profile 应受开关控制却放行。
2. **studio 前端缺入口**：后端有 gating（`module_middleware.py:34`）+ Portal 有卡片，但前端 4 方均无 studio 入口。
3. **teaching 语义错位**：teaching 开关码已声明、不在 DEFAULT_ENABLED；其后端实现是 `academic`（**非空壳**，v2 修正），但 academic 既未接 teaching gating（见漂移 1）、前端 `/academic/*` 也不挂 moduleCode；仅 Portal 给了 route `/academic` 入口。

---

## 2. 目标与范围

### 目标
- 建立**逐入口**声明式真源，覆盖 23 架构模块 + 9 开关码 + 后端 prefix / 前端 route / sidebar item / portal service 全部消费点。
- 加逐路由比对静态守卫：现状冻结、`known_drift` 精确豁免、**任何新增漂移或新增 fail-open 即 CI 红**。
- teaching 语义错位、4 处 backend fail-open、studio 前端缺口全部精确登记。

### 范围边界（行为不变契约）
- **所有消费者源码一行不改**（middleware / routeAccess / sidebar / router-meta / DashboardPage / SERVICE_CATALOG 均不动）。
- 4 处 fail-open / studio / teaching 漂移**只登记不修复**，各自另开 Phase（fail-open 属安全类，建议优先）。
- AI 工具 `module_code` 归属**不动**（属 Phase 3，由 `scripts/governance/check_ai_tool_modules.py` 管）。
- 不删除现有任一映射表。

---

## 3. 真源 `docs/governance/module-semantics.yaml`（逐入口期望表）

核心升级：真源不再是"模块码出现在哪几方"，而是**每个具体入口 → architecture_module + school_module_code 的期望表**，守卫据此逐入口比对，能抓"合法值但映射错"（如 `/analytics→exam`）。

```yaml
version: 2

# ── 第一层：9 个学校开关码（镜像 school_settings.py::MODULE_CODES）
school_module_codes: [exam, grading, homework, study_analytics, research, teaching, calendar, studio, conduct]

# ── 第二层：23 架构模块 → 开关码归属（语义 owner；键集校验自 modules.yaml）
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
  academic: teaching          # academic 是 teaching 的后端实现（v2 修正：非空壳）
  menu: null                  # 导航基础设施
  portal: null                # 聚合层，内部按子开关过滤
  school: null                # 核心/管理基础设施
  student: null               # 基础信息/共享身份

# ── 第三层：逐入口期望表（守卫比对的核心）
backend_routes:               # prefix → expect: gated:<code> | exempt
  /api/v1/exams:            { expect: "gated:exam" }
  /api/v1/subjects:         { expect: "gated:exam" }
  /api/v1/questions:        { expect: "gated:exam" }
  /api/v1/scan:             { expect: "gated:exam" }
  /api/v1/card:             { expect: "gated:exam" }
  /api/v1/templates:        { expect: "gated:exam" }
  /api/v1/pipeline:         { expect: "gated:exam" }
  /api/v1/grading:          { expect: "gated:grading" }
  /api/v1/marking:          { expect: "gated:grading" }
  /api/v1/analytics:        { expect: "gated:study_analytics" }
  /api/v1/knowledge:        { expect: "gated:research" }
  /api/v1/knowledge-tree:   { expect: "gated:research" }
  /api/v1/bank:             { expect: "gated:research" }
  /api/v1/calendar:         { expect: "gated:calendar" }
  /api/v1/studio:           { expect: "gated:studio" }
  /api/v1/homework:         { expect: "gated:homework" }
  # 应 gated 但当前 fail-open（豁免见 known_drift）
  /api/v1/academic:         { expect: "gated:teaching", drift: academic-backend-fail-open }
  /api/v1/conduct:          { expect: "gated:conduct",  drift: conduct-backend-fail-open }
  /api/v1/exam-imports:     { expect: "gated:exam",     drift: exam-import-backend-fail-open }
  /api/v1/profile:          { expect: "gated:study_analytics", drift: profile-backend-fail-open }
  # 基础设施 / 聚合，期望 exempt
  /api/v1/menus:            { expect: "exempt", drift: menus-not-in-exempt-list }
  /api/v1/portal:           { expect: "exempt", drift: portal-not-in-exempt-list }
  /api/v1/grades:           { expect: "exempt", drift: grades-not-in-exempt-list }    # base-prefix+decorator 派生
  /api/v1/teachers:         { expect: "exempt", drift: teachers-not-in-exempt-list }  # base-prefix+decorator 派生
  /api/v1/client-logs:      { expect: "exempt", drift: client-logs-not-in-exempt-list }  # base-prefix+decorator 派生（api/client_logs.py，plan-review F1）
  /api/v1/auth:             { expect: "exempt" }
  /api/v1/health:           { expect: "exempt" }
  /api/v1/version:          { expect: "exempt" }
  /api/v1/schools:          { expect: "exempt" }
  /api/v1/dashboard:        { expect: "exempt" }
  /api/v1/ai:               { expect: "exempt" }
  /api/v1/classes:          { expect: "exempt" }
  /api/v1/students:         { expect: "exempt" }
  /api/v1/joint-exams:      { expect: "exempt" }
  /api/v1/notifications:    { expect: "exempt" }
  /api/v1/llm-config:       { expect: "exempt" }
  /api/v1/workspace:        { expect: "exempt" }

frontend_route_module:        # 前端 route → 期望 moduleCode（合并 routeAccess + router-meta，二者须一致）
  /exams: exam
  /exam-import: exam
  /marking: grading
  /grading/tasks: grading
  /ai-grading: grading
  /analytics/report: study_analytics
  /analytics/ai-report: study_analytics
  /homework: homework
  /question-bank: research
  /knowledge-tree: research
  /error-book: research
  /conduct: conduct
  /conduct/settings: conduct
  /calendar: calendar
  # 无开关（基础/共享），显式声明 null 以防"漏挂"被误判
  /students: null
  /joint-exams: null
  /school-settings: null
  /academic/teaching-plans: null   # teaching 未接线，见 known_drift teaching-*
  /academic/timetable: null
  /academic/semesters: null
  /assignments: null
  /selections: null
  /teachers: null
  /schools: null
  /admin/impersonate: null

# Portal SERVICE_CATALOG 期望（service id == module_code，全部 ∈ school_module_codes）
portal_services_expect_self_module: true

# DashboardPage 硬编码 action moduleCode 期望（grading/homework/study_analytics 均为合法值）
dashboard_actions_expect_valid_only: true

# ── 第四层：已知漂移登记（精确绑定 consumer + 入口；修复后必须删除对应条目）
known_drift:
  - id: academic-backend-fail-open
    consumer: backend_middleware
    locus: /api/v1/academic
    expect: "gated:teaching"
    actual: "ungated (pass-through)"
    severity: security
    note: academic API 不受 teaching 开关控制
  - id: conduct-backend-fail-open
    consumer: backend_middleware
    locus: /api/v1/conduct
    expect: "gated:conduct"
    actual: "ungated (pass-through)"
    severity: security
  - id: exam-import-backend-fail-open
    consumer: backend_middleware
    locus: /api/v1/exam-imports
    expect: "gated:exam"
    actual: "ungated (pass-through)"
    severity: security
  - id: profile-backend-fail-open
    consumer: backend_middleware
    locus: /api/v1/profile
    expect: "gated:study_analytics"
    actual: "ungated (pass-through)"
    severity: security
  - id: menus-not-in-exempt-list
    consumer: backend_middleware
    locus: /api/v1/menus
    expect: "exempt (explicit)"
    actual: "pass-through (implicit, behavior identical)"
    severity: hygiene
  - id: portal-not-in-exempt-list
    consumer: backend_middleware
    locus: /api/v1/portal
    expect: "exempt (explicit)"
    actual: "pass-through (implicit, behavior identical)"
    severity: hygiene
  - id: grades-not-in-exempt-list
    consumer: backend_middleware
    locus: /api/v1/grades
    expect: "exempt (explicit)"
    actual: "pass-through (implicit, behavior identical)"
    severity: hygiene
    note: base-prefix+decorator 派生（student/router.py:73），grep prefix 漏列
  - id: teachers-not-in-exempt-list
    consumer: backend_middleware
    locus: /api/v1/teachers
    expect: "exempt (explicit)"
    actual: "pass-through (implicit, behavior identical)"
    severity: hygiene
    note: base-prefix+decorator 派生（teacher_router.py:107）
  - id: client-logs-not-in-exempt-list
    consumer: backend_middleware
    locus: /api/v1/client-logs
    expect: "exempt (explicit)"
    actual: "pass-through (implicit, behavior identical)"
    severity: hygiene
    note: base-prefix+decorator 派生（api/client_logs.py:14,38）；plan-review F1 补
  - id: studio-frontend-entry-missing
    consumer: frontend
    locus: routeAccess + sidebar + router-meta + dashboard
    expect: "studio entry present"
    actual: "no frontend entry"
    severity: ux
  - id: teaching-frontend-unwired
    consumer: frontend
    locus: /academic/* (routeAccess + sidebar)
    expect: "moduleCode: teaching"
    actual: "moduleCode: null (unwired)"
    severity: semantic
    note: academic 后端存在但前端入口未挂 teaching；Portal 给了 /academic 假入口
```

---

## 4. 守卫 `scripts/governance/check_module_semantics.py`（逐路由比对）

只读，**不改写任何源码**。校验五类：

1. **真源自洽**
   - `school_module_codes` == `MODULE_CODES`（import school_settings）。
   - `architecture_to_module_code` 键集 == `modules.yaml` 的 23 模块 name 集合（**不用目录 ls**）。
   - 值 ∈ `school_module_codes ∪ {null}`。

2. **后端逐入口比对**（核心，抓 fail-open + 错配）
   - **route discovery（v3 修正）**：不能只 grep `prefix="/api/v1/<module>"`——会漏 `prefix="/api/v1"` + decorator 派生的 `/grades` `/teachers`。须用 FastAPI 展开后的 `app.routes` 真实 path，或 AST 解析「router prefix + 各 `@router.<method>(path)` decorator」拼出完整 endpoint 全集。
   - 对每个 endpoint path：实际状态 = gated:<code>（startswith 命中 ROUTE_MODULE_MAP）/ exempt（命中 EXEMPT）/ pass-through（都不在）。保留 middleware 的 `startswith` 语义以与现状一致，另对 segment 边界（如 `/exams` vs `/exam-imports`）做 warning。
   - 与 `backend_routes[prefix].expect` 比对：
     - 实际 == 期望 → 绿。
     - 实际 != 期望但有 `drift` 字段，且 `known_drift` 中该 id 条目的 `(consumer, locus, expect, actual)` 四元组与当前实际**完全一致** → 绿（精确豁免）。仅按 id 放行会掩盖 drift 内容漂移（GPT P1-b），故必须匹配完整元组：actual 一旦变化（如真被修复或恶化）→ 元组失配 → 红。
     - **实际 != 期望且无登记 → 红**（新 fail-open / 错配 / 新增未声明 prefix）。

3. **前端逐 route 比对**（抓"合法值映射错"）
   - 解析 routeAccess + router-meta（+ sidebar）每个 route 的 moduleCode。
   - 与 `frontend_route_module[route]` 比对：值不一致 → 红（含 `/analytics→exam` 这类错配）；同一 route 在 routeAccess 与 router-meta 间不一致 → 红。
   - DashboardPage / sidebar 出现的每个 moduleCode ∈ `school_module_codes`（野值检查）。

4. **Portal 比对**：`SERVICE_CATALOG` 每条 `module_code` ∈ `school_module_codes` 且 == 其 `id`（`portal_services_expect_self_module`）。

5. **known_drift 收敛 + frontend drift 探测（plan-review F2）**：backend drift 每条必须被某 `backend_routes` 入口的 `drift` 字段引用（无孤儿）。frontend drift（studio/teaching）**不按 id 硬编码放行**——每个须有探测器 `_FRONTEND_DRIFT_PROBES[id](parsed)→bool` 验证实际状态：drift 仍成立→绿；实际已不成立（疑似已修复）→红（应删登记）；无探测器的 frontend drift→红（fail-closed）。backend 入口被修复后仍留 drift → 元组失配（第2类）红。

CLI：`--check`（exit≠0 即违规，供 CI）；`--update`（仅人工确认后刷新基线，与其它 governance 脚本一致）。

### 4.1 Contract Pack 补全（risk_modules / test_debt，plan-review F4）

- **risk_modules**（高风险消费者，守卫必须覆盖）：`api/module_middleware.py`（后端门禁）、`frontend/src/config/routeAccess.js` + `router/index.js`（前端可见性双源）、`sidebarConfig.js`、`pages/DashboardPage.vue`、`modules/portal/service.py::SERVICE_CATALOG`。
- **test_debt**：当前**无**守卫保证以上多方对同一映射一致 → 本 Phase 反例矩阵 + frontend drift 探测消除该债；`_FRONTEND_DRIFT_PROBES` 须随新增 frontend drift 同步扩展（无探测器即 fail-closed）。

---

## 5. 测试 `tests/governance/test_module_semantics.py`（对齐契约 C3，反例必须真红）

- **正例**：四/多方现状 + 当前真源 → 守卫绿（8 处已知 drift 精确放行）。
- **反例矩阵**（每条必须真变红）：
  1. backend：给某 fail-open 入口"假装修复"——从 `known_drift` 删 `conduct-backend-fail-open` 但 middleware 仍未 gating → 红（豁免缺失）。
  2. backend：新增一个未声明 prefix 且 pass-through → 红（新 fail-open 不被默认放行，fail-closed）。
  3. backend 错配：把 `/api/v1/analytics` 期望改 `exam`、middleware 实为 study_analytics → 红。
  4. 前端 routeAccess 某 route moduleCode 漂移 → 红。
  5. 前端 router-meta 与 routeAccess 同 route 不一致 → 红。
  6. sidebar / DashboardPage 出现野值 moduleCode（∉ 9）→ 红。
  7. Portal SERVICE_CATALOG 某 module_code 漂移 / ∉ 9 → 红。
  8. 真源第一层与 `MODULE_CODES` 不一致 → 红。
  9. `architecture_to_module_code` 漏某架构模块（键集 != modules.yaml）→ 红。
  10. 孤儿 known_drift（登记一个真源里不存在 drift 标记的 id）→ 红。
  11. **base-prefix+decorator 新 endpoint**：在 `prefix="/api/v1"` router 下新增 `@router.get("/foo")` 未声明 → 守卫经 route 展开发现 `/api/v1/foo` pass-through 且无登记 → 红（验证 route discovery 不漏 decorator 派生，对应 GPT P0-b）。
  12. **known_drift 元组漂移**：某 drift 的 `actual` 已变但 id 不变 → 红（验证按四元组匹配，非仅 id，对应 GPT P1-b）。

实现用 monkeypatch / 临时构造输入注入反例，不污染生产源码。

---

## 6. 提交策略（总纲 §9，每批 < 8 文件、< 500 行）

- **Commit 1（声明真源）**：`docs/governance/module-semantics.yaml`（+ 如需，`foundation-boundaries.md` 补一句指向真源）。纯数据，doc commit。
- **Commit 2（守卫 + 测试 + CI）**：`scripts/governance/check_module_semantics.py` + `tests/governance/test_module_semantics.py` + `.github/workflows/test.yml` 纳入。含代码 → 走 `codex-review code`。

如后续要让四方派生自真源（行为变更）→ 另开 Commit 3 / 另开 Phase（Phase 2 范围），不与本设计混。

---

## 7. 验收标准

- `module-semantics.yaml` 覆盖 23 架构模块 + 9 开关码 + 后端全 prefix + 前端全 route + portal services；teaching/4 fail-open/studio 全部精确在册。
- `check_module_semantics.py --check` 在当前代码上**绿**（8 处 drift 精确放行）。
- 十条反例测试全部真变红，尤其 #2（新 fail-open fail-closed）+ #3（映射错配）。
- 任一新增 fail-open / 错配 / 野值 / 孤儿登记 → CI 红。
- 全程消费者源码零改动（`git diff` 这些文件为空）。

---

## 8. 回滚边界

本 Phase 的 worktree + 两个独立 commit 即天然回滚单元：全部为新增文件（真源 yaml + 守卫脚本 + 测试 + CI 一行），回退 = 删除这两个 commit，不影响任何前序 Phase，无业务行为受影响（因本 Phase 不改行为）。

---

## 9. 不做（明确边界）

- 不改任一消费者源码。
- 不修复 4 处 backend fail-open / studio / teaching。
- 不动 AI 工具 `module_code` 归属。
- 不让消费者派生自真源（Phase 2）。
- 不重构依赖循环（Phase 4）。

---

## 10. v2 修订记录（回应代码审查 5 条）

| # | 审查意见 | 核实 | 修订 |
|---|---|---|---|
| 1 | teaching 判断错、backend fail-open 不止 conduct（academic/exam_import 有真实 API 未 gating）| 属实，且扫描另发现 profile 同样 fail-open | §1.1 补全 4 处 fail-open；teaching 定性改为"后端实现是 academic、非空壳"；known_drift 增至 8 条 |
| 2 | `expected_consumers` 把缺口写成"期望缺失"、合法化漂移 | 属实 | 删除 expected_consumers；改为逐入口期望表 + 精确 known_drift（绑定 consumer+locus，修复后强制删除）|
| 3 | 守卫只查 module_code 合法性、抓不住映射错配 | 属实 | §4 升级为后端逐 prefix / 前端逐 route 比对；反例 #3 专测错配 |
| 4 | 前端还有 router-meta + DashboardPage 消费点未纳入 | 属实 | §1.2 补齐 4 方；守卫纳入 router-meta 一致性 + DashboardPage 野值检查；`_frozen/*` 显式排除 |
| 5 | 架构模块真源应按 MODULE.md 不按目录 | 属实 | 真源键集校验改用 `modules.yaml`（MODULE.md 聚合），不用目录 ls |

### v3 修订（回应 codex-review consult 4 条 finding）

GPT 经 codex-gateway consult 独立读代码库验证，确认 v2 的 4 真漏 + menus/portal 定性 + 逐入口机制 + 行为不变均成立，另挖出 4 处补强项：

| # | finding | 优先级 | 核实 | 修订 |
|---|---|---|---|---|
| v3-1 | backend_routes 全集漏 `/api/v1/grades`、`/api/v1/teachers`（base-prefix+decorator 派生，pass-through）| P0 | 属实（`student/router.py:21,73`、`teacher_router.py:22,107`）| §1.1 形态②补全；§3 backend_routes + known_drift 各加 2 条（exempt 类，hygiene）|
| v3-2 | 守卫 route discovery 若只 grep `prefix="/api/v1/<module>"` 会漏 decorator 派生根 | P0 | 属实 | §4 改为 FastAPI route 展开 / AST(prefix+decorator)；§5 加负例 #11 |
| v3-3 | 前端 moduleCode 不止 4 方，`schoolSettings.js` 也消费（设置写入）| P1 | 属实（`schoolSettings.js:15` `toggleModule` 参数）| §1.2 区分"4 可见性消费点 + 1 设置写入点"，后者纳入零 diff gate 不纳入逐 route 比对 |
| v3-4 | known_drift 若只按 id 放行会掩盖 drift 内容漂移 | P1 | 属实 | §4 改为按 `(consumer,locus,expect,actual)` 四元组匹配；§5 加负例 #12 |
