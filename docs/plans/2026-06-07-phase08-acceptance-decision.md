<!-- no-projectctl -->
# Phase 0.8 — 模块治理地基总体验收 + Portal 解锁裁定包

> **性质**：验收裁定记录（持久化既有结论，非新实施计划）。本文件只固化「源码地基是否达标」与「Portal 是否可解锁」的裁定证据，不引入任何业务代码/语义改动。
> **角色边界**：本文档由地基治理文档收口执行者持久化。Portal 解锁本身是**设计者决策**，执行者不自解锁——本文档维持 BLOCKED，并列出待设计者裁定项。

## 元信息（锚点）

| 字段 | 值 | 证据 |
|------|-----|------|
| Claude session | `sid:6be633a5` | 任务输入 |
| HEAD | `3688f32a429b3913ad8246f7a372817a8f3a0880`（`3688f32`） | `git rev-parse HEAD` |
| 分支 | `feat/module-governance-repair`（upstream: none） | `git branch --show-current` |
| Working tree | clean（`git status --porcelain` 空） | 见 Fresh Evidence Pack §A |
| 最新 review log | `docs/plans/.codex-review-2026-06-07_142553.log` | verdict PASS / findings [] |
| 最新 review 引擎 | OpenAI Codex gpt-5.5，reasoning effort xhigh | review log 头部 |
| 验收日期 | 2026-06-07（Asia/Shanghai） | — |

## 摘要结论（三句话）

1. **源码地基 PASS** —— 模块门控地基链（Phase 0.5 → 0.6/0.6C → 0.7A → 0.7B → 0.7D → 0.7E/0.7E-R1）全部收口，最新 codex-review 对当前 HEAD `3688f32` 判定 **PASS，零 finding**（机器真源 receipt 绑定 `reviewed_sha=3688f32`）。
2. **Portal homepage aggregation (Phase 1) 仍 BLOCKED** —— 解锁是设计者决策，执行工程师不自解锁；地基达标是解锁的**必要非充分**条件，仍需设计者裁定验收口径与残留项处置。
3. **truthline / DB 红灯是运行态阻塞，不是源码地基缺陷** —— DB doctor 红（`exam_import_sessions` 缺表 + orphan `_audit_log`）与 truthline 未对齐（live hash `d9b1c56` ≠ HEAD `3688f32`，本分支尚未部署）属部署/运维侧动作，不构成源码地基 FAIL，但构成 **Portal Phase 1 落地前必须由运行侧清账** 的前置。

---

## Fresh Evidence Pack

> 所有条目均带 `file:line` 或命令输出；无法证实的标 `unknown`。

### §A 当前工作树状态（本执行者现场自验，2026-06-07）

```
$ git rev-parse HEAD
3688f32a429b3913ad8246f7a372817a8f3a0880
$ git status --porcelain          # （空——working tree clean）
$ git diff --check                # （空——无空白/冲突标记）
```

### §B 最新 codex-review 机器真源（权威 verdict）

`.review-receipts.jsonl` 末 5 条（机器真源，verdict 以此为准，不以叙述为准）：

| ts (UTC+8) | verdict | reviewed_sha | 说明 |
|---|---|---|---|
| 11:02:21 | FINDINGS | `2f66ae2` | 0.7E 收口中间态 |
| 12:14:58 | PASS | `2f66ae2` | — |
| 14:02:42 | PASS | `28ddbf9` | 0.7E-R1 test_gap 收口 |
| 14:06:07 | FINDINGS | `28ddbf9` | — |
| **14:40:06** | **PASS** | **`3688f32`** | **= 当前 HEAD，最终判定** |

最新 review log 首行结构化结论（`docs/plans/.codex-review-2026-06-07_142553.log:1`）：

```json
{"verdict":"PASS", ... ,"findings":[]}
```

### §C 最新 review 内部验证证据（review log:1 summary 摘录）

- `git diff --check d7ca5c4~1..HEAD` → **PASS (no output)**（本执行者复跑同样 clean）
- `uv run python scripts/governance/check_module_semantics.py --check` → **`Module semantics baseline clean`**
- `uv run pytest tests/test_api/test_module_middleware.py tests/test_api/test_knowledge_isolation.py tests/test_api/test_l2_visible_scope.py tests/test_knowledge_tree/test_router.py tests/test_modules/test_routes_smoke.py -q` → **`91 passed, 5 warnings in 69.44s`**
- 需求分母覆盖（Phase -1）：
  - 非默认缺行 fail-closed **3/3** — `tests/test_api/test_module_middleware.py:157-158`
  - 全模块默认镜像 **9/9** — `:191-192`
  - 默认模块缺行 pass-through **6/6** — `:163-164`
  - HTTP dispatch 状态 **4/4** — `:258-293`
- 实现对齐：`src/edu_cloud/api/module_middleware.py:119-142,208-209` 对齐前端 `src/edu_cloud/services/school_settings_service.py:109`；工程简约性 PASS，未见多层 fallback / 过度抽象。
- 环境备注：裸 `pytest` 报 `ModuleNotFoundError: No module named 'fastapi'`（全局环境缺项目依赖），`uv run` 已完成有效验证——环境噪声，非代码缺陷。

### §D drift 与默认开关现状（只读确认，本文档不改）

- `known_drift` 仅剩 **1 条** — `docs/governance/module-semantics.yaml:120`：
  `studio-frontend-entry-missing`（consumer: frontend / locus: studio-entry / expect: present / actual: absent / **severity: ux**）
- `DEFAULT_ENABLED` — `src/edu_cloud/models/school_settings.py:35`：
  `{"exam", "grading", "homework", "calendar", "studio", "conduct"}`（teaching/research/study_analytics 不在内 → 缺行 fail-closed，0.7E 语义）

### §E 地基阶段链总览（每阶段 review 收口）

| Phase | 内容 | 收口状态 | 证据锚点 |
|------|------|---------|---------|
| 0.5 | 静态 module-semantics 守卫 | ✅ | `NOW.md:61-68`；`check_module_semantics.py` |
| 0.6 + 0.6C | 运行时 authGuard 直达 URL 门控 + 覆盖完整性（R4 F-001/F-002 FIXED，R5 confirmed） | ✅ | `NOW.md:69-117` |
| 0.7A | 前端可见性 surface 统一 fail-closed（R5/R6/R7 MED security_design），**R8 零 MED/security** | ✅ | `NOW.md:118-151` |
| 0.7B | 后端中间件门控硬化（最长前缀对齐 + conduct/exam-imports 补门控 + hygiene exempt），**known_drift 11→3** | ✅ | `NOW.md:159-177`；`phase07-drift-burndown.md` |
| 0.7D | academic 双面 fail-open 收口，**known_drift 3→1**（仅余 studio） | ✅ | `NOW.md:179-186` |
| 0.7E | absent-row fail-open **全系统**收口（`module_enabled_default` 后端 403 面 ↔ 前端可见性面单一真源） | ✅ | `NOW.md:188-202` |
| 0.7E-R1 | 补 HTTP dispatch 回归 4 测试，关闭 F-001 HIGH test_gap | ✅ | `NOW.md:203-208` |
| **总验收** | **当前 HEAD `3688f32`** | **✅ PASS / 0 finding** | §B / §C |

---

## Risk Register

| ID | 风险 | 类别 | 严重度 | 证据 | 处置 / 阻塞口径 |
|----|------|------|--------|------|----------------|
| **R-RUN-1** | DB doctor 红：ORM 声明 `exam_import_sessions` 表但 DB 无此表；DB 含 orphan 表 `_audit_log` | 运行态 | 阻塞 Portal 落地 | `NOW.md:27-28` | **运行态阻塞**，非源码地基缺陷。Portal Phase 1 落地前由运行侧（migration/db_doctor）清账。本文档不迁移 DB。 |
| **R-RUN-2** | Truthline 未对齐：live hash `d9b1c56`（`NOW.md:24`）≠ HEAD `3688f32`——`feat/module-governance-repair` 地基工作**尚未部署到 `https://mcu.asia`** | 运行态 | 阻塞 Portal 落地 | `NOW.md:24-26` vs `git rev-parse --short HEAD` | **运行态阻塞**。地基代码 PASS 但用户侧未消费；部署是独立动作。本文档不部署/不构建/不回退 dist。 |
| **R-DRIFT-1** | 残留 `studio-frontend-entry-missing`（前端 studio 入口缺失） | 源码（登记 drift） | 低（ux） | `module-semantics.yaml:120` | 已登记 drift；涉及业务 UI 新增 studio 入口，超出地基「不改业务 UI」范围。是否要求 Portal 解锁前关闭由设计者裁定。 |
| **R-SEC-1** | 未 backfill `SchoolModule(teaching)` 行的**存量学校**现 fail-closed 403 | 源码（预期行为） | 低（安全修复副作用） | `NOW.md:196-199`；`module_middleware.py:119-142` | 0.7E 安全修复的**预期行为**，非回归。`init_school_modules` 为新校建全 9 行，正常 init 学校不受影响；仅未 backfill 的存量缺行学校受影响。 |
| **R-TEST-1** | 全量后端 22 failed / 前端 3 failed | 测试基线 | 噪声 | `NOW.md:202`（后端 22 = socksio/playwright/httpx 环境失败，**0 module-gating 403s**）；`NOW.md:135-136`（前端 3 = marking/review static assertions） | 均为**预先存在**的环境/历史基线失败，与模块门控地基无关。门控相关定向测试全绿（§C）。 |

---

## Portal Unlock Decision

### 裁定

**Portal homepage aggregation (Phase 1) 维持 BLOCKED。** 本执行者不解锁。

### 依据

1. **决策权归属**：解锁是设计者决策，执行工程师不自解锁——任务契约「只剩 LOW → 规划 0.7B」（`phase07-drift-burndown.md:56-59`）。0.7B/0.7D/0.7E 链已执行完毕，但解锁动作本身仍待设计者签署。
2. **地基达标 = 必要非充分**：源码地基已 PASS（本文档 §B/§C/§E），满足解锁的代码侧前提；但仍有运行态前置（R-RUN-1/R-RUN-2）与一项待裁定 drift（R-DRIFT-1）。

### 残留项快照（解锁前的全集）

- **源码侧**：`studio-frontend-entry-missing` drift（ux，R-DRIFT-1）+ Portal 解锁动作本身（`NOW.md:210-215`）。
- **运行态侧**：DB doctor 红（R-RUN-1）、truthline 未部署（R-RUN-2）——需运行侧清账，不在源码地基验收范围内。

### 待设计者裁定项（解锁前需明确）

1. **验收口径**：是否认可「源码地基 PASS + 运行态红灯由运行侧另行清账」即可解锁 Portal Phase 1，还是要求运行态红灯先转绿？
2. **studio drift 处置**：Portal 解锁前是否要求先关闭 `studio-frontend-entry-missing`（需新增业务 UI 入口，触发「改业务 UI」边界），还是允许带此 ux drift 解锁？
3. **Portal Phase 1 范围**：homepage aggregation 的功能边界、对接的模块开关口径（与 `enabledModules` / `DEFAULT_ENABLED` 的关系）由设计者定稿后方可进入实现。

> 以上 3 项任一未裁定 → Portal 保持 BLOCKED。

---

## Next Executor Packet

> 给下一个执行者（无论是运行侧清账、还是设计者裁定后的 Portal 实现者）的最小交接。

### Goal
- 若任务为 Portal Phase 1：**必须先取得设计者对上述 3 项裁定的签署**，再进入实现；不得在 BLOCKED 状态下自行抄 Portal 功能。
- 若任务为运行态清账：处理 R-RUN-1（DB）与 R-RUN-2（部署 truthline 对齐），使运行态与 HEAD `3688f32` 一致。

### 入口锚点
- HEAD：`3688f32`，分支 `feat/module-governance-repair`。
- 状态命令（取 volatile 实时值）：
  ```bash
  scripts/truth-status.sh /home/ops/projects/edu-cloud   # live hash / truthline
  scripts/truth doctor --json                            # DB doctor
  uv run python scripts/governance/check_module_semantics.py --check   # 门控守卫
  ```

### Must Preserve（不得回退）
- Phase 0.5 / 0.6 / 0.6C / 0.7A / 0.7B / 0.7D / 0.7E / 0.7E-R1 全部成果。
- 后端 403 面 ↔ 前端可见性面「单一真源」的 fail-closed 语义（`module_enabled_default`，`module_middleware.py:119-142` 对齐 `school_settings_service.py:109`）。
- `_FRONTEND_DRIFT_PROBES` 中 teaching 回退探测器（academic 回退守护）。

### Must Not Change（地基不变量）
- **不改 `DEFAULT_ENABLED`**（`school_settings.py:35`）—— teaching/research/study_analytics 不得擅自加入。
- **不改 `module-semantics.yaml` 语义**（known_drift 四元组、期望表）——除非设计者明确裁定。
- 不削弱 authGuard / 中间件的动态路由 fail-closed。
- 不在未取得设计者解锁前进入 Portal Phase 1 实现。

---

## 明确结论（复述，供索引引用）

- ✅ **源码地基 PASS**（HEAD `3688f32`，最新 codex-review PASS / 0 finding，机器真源 receipt 绑定）。
- ⛔ **Portal Phase 1 仍 BLOCKED**，需设计者裁定（验收口径 / studio drift / Portal 范围 3 项）。
- 🟥 **truthline / DB 红灯是运行态阻塞**（live hash `d9b1c56` ≠ HEAD；DB `exam_import_sessions` 缺表 + orphan `_audit_log`），非源码地基缺陷，Portal 落地前由运行侧清账。
