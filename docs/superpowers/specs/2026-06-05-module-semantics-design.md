---
phase: design
---

# Phase 0.5 模块语义统一 设计 v4（2026-06-05）

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

`ROUTE_MODULE_MAP` 列了受 gating 映射，其中 `/api/v1/subjects` 是 **dead mapping**——`app.routes` 实测顶层 36 个 `/api/v1/<seg>` 入口中**无 subjects**（subjects 仅以嵌套形态存在：`/api/v1/exams/{exam_id}/subjects`、`/api/v1/marking/subjects`、`/api/v1/analytics/grade/{grade_id}/subjects`，三者 `startswith "/api/v1/subjects"` 均不成立，故该 map 条目永不命中）。**真源 `backend_routes` 按 `app.routes` 实测入口建立，不含 subjects 顶层条目**（实测 36 顶层 segment == backend_routes 36 条，入口级双向闭环；方向 A）。其余受 gating 映射均正确：exams/questions/scan/card/templates/pipeline → exam；grading/marking → grading；analytics → study_analytics；knowledge/knowledge-tree/bank → research；calendar；studio；homework。

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
- **所有消费者源码一行不改**（middleware / routeAccess / sidebar / router-meta / DashboardPage / SERVICE_CATALOG / schoolSettings.js 均不动）。
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
  # 动态/detail 路由（router-meta 专有，R5 F-001 纳入同一基线分母）
  /exams/:id: exam
  /card-dev/:examId: exam
  /grading/tasks/:id: grading
  /marking/grade/:questionId: grading
  /exams/:examId/ai-grading/:subjectId: grading
  /analytics/:examId: study_analytics
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

# DashboardPage action：带 route 字段，纳入 frontend_route_module 的 route 级比对（必修③，与 sidebar 同等 fail-closed+一致性）
# 此标志保留为野值兜底语义；dashboard 的 5 个 action route 均已在 frontend_route_module 声明
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

只读，**不改写任何源码**。校验六项（与 `check_module_semantics.py` 的 6 个 check 函数一一对应：`check_self_consistency` / `check_backend` / `check_frontend` / `check_frontend_drift` / `check_portal` / `check_known_drift`）：

1. **真源自洽**
   - `school_module_codes` == `MODULE_CODES`（import school_settings）。
   - `architecture_to_module_code` 键集 == `modules.yaml` 的 23 模块 name 集合（**不用目录 ls**）。
   - 值 ∈ `school_module_codes ∪ {null}`。

2. **后端逐入口比对**（核心，抓 fail-open + 错配）
   - **route discovery（v3 修正）**：不能只 grep `prefix="/api/v1/<module>"`——会漏 `prefix="/api/v1"` + decorator 派生的 `/grades` `/teachers`。须用 FastAPI 展开后的 `app.routes` 真实 path，或 AST 解析「router prefix + 各 `@router.<method>(path)` decorator」拼出完整 endpoint 全集。
   - 对每个 endpoint path：实际状态 = gated:<code>（startswith 命中 ROUTE_MODULE_MAP）/ exempt（命中 EXEMPT）/ pass-through（都不在）。保留 middleware 的 `startswith` 语义以与现状一致，另对 segment 边界（如 `/exams` vs `/exam-imports`）做 warning。
   - 与 `backend_routes[prefix].expect` 比对：
     - 实际 == 期望：若该入口仍挂 `drift` 字段 → 红（已修复，stale drift 应删，plan-review R4 F-001）；无 drift → 绿。
     - 实际 != 期望但有 `drift` 字段，且 `known_drift` 中该 id 条目的 `(consumer, locus, expect, actual)` 四元组与当前实际**完全一致** → 绿（精确豁免）。仅按 id 放行会掩盖 drift 内容漂移（GPT P1-b），故必须匹配完整元组：actual 一旦变化（如真被修复或恶化）→ 元组失配 → 红。
     - **实际 != 期望且无登记 → 红**（新 fail-open / 错配 / 新增未声明 prefix）。
   - **反向覆盖（plan-review R2 F2）**：真源 `backend_routes` 声明的每个 prefix 必须被 route discovery 发现，否则 → 红（stale 真源条目，强制删除），使 36/36 分母在入口级双向闭环（实测 `app.routes` 顶层 36 segment == backend_routes 36 条）。

3. **前端逐 route 比对**（抓"合法值映射错" + fail-closed + null 检查，plan-review R2 F1 + 必修③ + R5 F-001/F-002）— `check_frontend`
   - 解析 routeAccess + router-meta + sidebar + dashboard 的 (route, moduleCode) 对。
   - **四面统一 fail-closed + 一致性 + null 检查**：每个 route 必须 ∈ `frontend_route_module`，否则 → 红（fail-closed，防"未声明前端入口用合法值"）；真源为 **null（不受门控）却出现 moduleCode → 红**（R5 F-002：不受控入口不应被悄悄 gating）；真源非 null 且值不一致 → 红（含 `/analytics→exam` 错配、sidebar/dashboard 错配、动态路由漂移）。dashboard action 带 `route` 字段（实测 `DashboardPage.vue:435,444,455,465,474`），与 sidebar 同等 route 级比对（必修③）。
   - **router-meta 含动态参数路由**（`/exams/:id` 等 6 条）**纳入同一基线分母**（R5 F-001：6 动态路由进 `frontend_route_module`，与静态同等 fail-closed，不再"不强制声明"）；另与 routeAccess 同 route 交叉一致性 → 不一致红。
   - 各面出现的每个 moduleCode ∈ `school_module_codes`（野值检查，兜底）。

4. **前端 drift 探测 + 四元组校验**（plan-review F2 + R5 F-003，实现为独立 check）— `check_frontend_drift`：frontend drift（studio/teaching）**不按 id 硬编码放行**——每个须有探测器 `_FRONTEND_DRIFT_PROBES[id] = {expect, actual, still_holds(parsed)→bool}`。①**四元组校验**：known_drift 条目的 expect/actual 必须与 probe 契约一致（consumer=frontend 固定、locus 在条目），否则 → 红（R5 F-003，消除"声称四元组豁免但实仅 probe"的不自洽，与 backend 对称）；②**实际状态**：`still_holds` 仍成立→绿，实际已不成立（疑似已修复）→红（应删登记）；无探测器的 frontend drift→红（fail-closed，由第6类收敛兜底）。

5. **Portal 比对** — `check_portal`：`SERVICE_CATALOG` 每条 `module_code` ∈ `school_module_codes` 且 == 其 `id`（`portal_services_expect_self_module`）。

6. **known_drift 收敛** — `check_known_drift`：backend drift 每条必须被某 `backend_routes` 入口的 `drift` 字段引用（无孤儿）；frontend drift 每条必须在 `_FRONTEND_DRIFT_PROBES` 有探测器（无则 fail-closed 红）。backend 入口被修复后仍留 drift → 元组失配（第2类）红。

CLI：`--check`（exit≠0 即违规，供 CI）；`--update`（仅人工确认后刷新基线，与其它 governance 脚本一致）。

### 4.1 Contract Pack 补全（risk_modules / test_debt，plan-review F4）

- **risk_modules**（高风险消费者，守卫必须覆盖）：`api/module_middleware.py`（后端门禁）、`frontend/src/config/routeAccess.js` + `router/index.js`（前端可见性双源）、`sidebarConfig.js`、`pages/DashboardPage.vue`、`modules/portal/service.py::SERVICE_CATALOG`、`frontend/src/api/schoolSettings.js`（设置写入消费点：纳入"消费者源码零改"diff gate，**不**纳入逐 route 比对，性质是"操作开关"的 API 调用参数而非"按开关 gate 可见性"，必修⑥）。
- **test_debt**：当前**无**守卫保证以上多方对同一映射一致 → 本 Phase 反例矩阵 + frontend drift 探测消除该债；`_FRONTEND_DRIFT_PROBES` 须随新增 frontend drift 同步扩展（无探测器即 fail-closed）。

---

## 5. 测试 `tests/governance/test_module_semantics.py`（对齐契约 C3，反例必须真红）

- **正例**：四/多方现状 + 当前真源 → 守卫绿（11 处已知 drift 精确放行：9 backend + 2 frontend）。
- **反例矩阵**（21 编号 / 23 反例测试，每条必须真变红）：
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
  13. **frontend drift 探测**（拆 2 测试）：(13a) known_drift 加一条 consumer=frontend 但 `_FRONTEND_DRIFT_PROBES` 无对应 id → 红（fail-closed）；(13b) studio 实际已 present，探测器返回"drift 不成立" → 红（应删登记）。
  14. **stale 真源 prefix**：`backend_routes` 声明某 prefix 但 route discovery 未发现 → 红（反向覆盖，plan-review R2 F2）。
  15. **未声明前端 route**：routeAccess 出现不在 `frontend_route_module` 的 route → 红（fail-closed，plan-review R2 F1）。
  16. **sidebar 错配到另一合法值**：sidebar 某 route moduleCode 为合法值但与真源不符 → 红。
  17. **dashboard route 漂移**（必修③）：dashboard action 某 route moduleCode 为合法值但与真源不符 → 红（验证 dashboard 已纳入 route 级比对，非仅野值检查）。
  18. **后端入口已修复但 drift 保留**（plan-review R4 F-001）：某 fail-open 入口实际已修复（actual == expect），但 backend_routes 仍挂 `drift` 字段 → 红（stale drift 强制删除；与 #12"truth 谎称已修复但实际未改"互为反方向，闭合双向元组契约）。
  19. **null route 被加合法 moduleCode**（R5 F-002）：真源声明 null（不受门控）的 route（/students 等）出现合法 moduleCode → 红（防不受控入口被悄悄纳入门控）。
  20. **frontend drift 四元组失配**（R5 F-003）：某 frontend drift 的 expect/actual 被篡改、与 probe 契约不符 → 红。
  21. **router-meta 动态路由漂移**（R5 F-001）：动态路由（/exams/:id 等 6 条）纳入分母后，其 moduleCode 与真源不符 → 红（验证动态路由已进基线）。

> #7 拆"模块码漂移 + 野值"2 测试、#13 拆 a/b 2 测试，故 21 编号 = 23 反例测试；加 4 个正例（self/backend/frontend/portal 各 `*_passes_on_real`）= 端到端 27 测试（详见 plan Task 各 Step 的 passed 计数）。

实现用 monkeypatch / 临时构造输入注入反例，不污染生产源码。

---

## 6. 提交策略（总纲 §9，每批 < 8 文件、< 500 行）

- **Commit 1（声明真源）**：`docs/governance/module-semantics.yaml`（+ 如需，`foundation-boundaries.md` 补一句指向真源）。纯数据，doc commit。
- **Commit 2（守卫 + 测试 + CI）**：`scripts/governance/check_module_semantics.py` + `tests/governance/test_module_semantics.py` + `.github/workflows/test.yml` 纳入。含代码 → 走 `codex-review code`。

如后续要让四方派生自真源（行为变更）→ 另开 Commit 3 / 另开 Phase（Phase 2 范围），不与本设计混。

---

## 7. 验收标准

- `module-semantics.yaml` 覆盖 23 架构模块 + 9 开关码 + 后端 36 顶层 prefix（== `app.routes` 实测）+ 前端全 route + portal services；teaching/4 fail-open/studio 全部精确在册。
- `check_module_semantics.py --check` 在当前代码上**绿**（11 处 drift 精确放行：9 backend + 2 frontend）。
- 23 条反例测试（21 编号）全部真变红，尤其 #2（新 fail-open fail-closed）+ #3（映射错配）+ #18（已修复但 drift 保留）+ #19（null route gating）+ #21（动态路由漂移）。
- 任一新增 fail-open / 错配 / 野值 / 孤儿登记 / stale 真源条目 → CI 红。
- 全程消费者源码零改动（`git diff` 为空，含 7 个 risk_modules 文件 + `schoolSettings.js`）。

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

### v4 修订（方向 A+B：`app.routes` 实测为唯一真源 + spec/plan 全量对齐，处置 plan-review 不收敛根因 6 项）

根因（plan-review R1=4→R2=3→R3=4 不收敛）：①事实基线照搬非实测（subjects 错）②逐条打补丁引入新局部不一致。本轮以 `create_app().routes` 实测为唯一真源、spec 与 plan 全量对齐同口径修复，根除照搬与碎补丁。

| # | 必修项 | 核实（实测证据） | 修订 |
|---|---|---|---|
| ① | `/api/v1/subjects` 非顶层 segment | `create_app().routes` 实测顶层仅 **36** 个 `/api/v1/<seg>`，subjects 仅嵌套（`/exams/{id}/subjects`、`/marking/subjects`、`/analytics/.../subjects`）| 删 §3 backend_routes subjects 条目（37→36）；§1.1 注明 dead mapping；实测 36 == backend_routes 36 双向闭环 |
| ② | CI 不自洽（governance job 跑不了 import create_app）| `test.yml`：governance job 仅 `pip install pytest pyyaml`；backend job 才 `pip install -e ".[dev]"` | 守卫 `--check` + test 接入 **backend job**（重依赖），用 `python` 非 `.venv/bin/python`；保留 `app.routes` 实测（Must Preserve）|
| ③ | dashboard 只野值检查，抓不住 route 映射错 | `DashboardPage.vue:435,444,455,465,474` 各 action 带 `route` 字段（实测 5 对全命中真源）| §4 第3类 + parse_frontend/_compare_frontend：dashboard 升级为 route 级 fail-closed+一致性；加反例 #17 |
| ④ | stale 计数 | 实际 known_drift **11**、反例 **19 测试 / 17 编号**、正例 **4** | drift 8→11；反例十/十二→19；正例 1→4；expected 37→36；§3 注释 10→11 |
| ⑤ | CHECKS 数 5 vs 实际 6 | `CHECKS` 含 `check_frontend_drift` = 6 | §4 五类→六项（frontend drift 探测独立成第4类）；plan File Structure + self-review 5→6 |
| ⑥ | risk_modules 漏 schoolSettings.js | `schoolSettings.js:15` `toggleModule` 设置写入消费点 | §4.1 risk_modules 补 `schoolSettings.js`（纳入零 diff gate，不纳入逐 route 比对）|

> **R4 追加处置 F-001**（plan-review FINDINGS=1，已从 R3=4 收敛至 R4=1）：`_compare_backend` 在 `actual == expect` 时直接 `continue`，漏检"入口已修复但 drift 登记仍保留"方向（与契约"修复后强制删除登记"不自洽）。修：达期望但仍挂 drift 即报红；加反例 #18（与 #12 互为反方向）。反例 19→20 测试 / 17→18 编号。

> **R5 追加处置 F-001/F-002/F-003**（plan-review FINDINGS=3，R4=1→R5=3 反弹、最终轮、R6 禁止；用户裁定"修 3 项 + manual_override 进实施"）。共同根因：前端契约边界不如 backend 严格闭合。**F-002(HIGH)**：`_compare_frontend` 对 null route 仅在非 null 时查一致性 → null route 被加合法 moduleCode 不报红 → 修为 null route 出现 code 即红（反例 #19）。**F-001(MED)**：router-meta 6 动态路由(/exams/:id 等)未进 truth 分母 → 纳入 `frontend_route_module` + router_meta 改 fail-closed（反例 #21）。**F-003(MED)**：frontend drift 仅 probe、未验 expect/actual → probe 元数据化(expect/actual) + 四元组比对，与 backend 对称（反例 #20）。反例 20→23 测试 / 18→21 编号。三修已模拟验证：正例 0 错 + 三反例红。
