# edu-cloud 地基治理 + 数据写入收敛 统一总纲（2026-06-05）

> 性质：合并总纲。把「地基治理计划」与「StudentAnswer 写入收敛」两条线收束到一份全局治理纲领。
> 范围：`/home/ops/projects/edu-cloud`，分支 `feat/module-governance-repair`。
> 状态：**草案，待未提交 governance 工作收口 + `codex-review plan` gate**。本文档为纯新增文档，未触碰任何在途代码。
> 来源对账：本总纲合并并修订以下四份文档，详见 §0。

---

## 0. 文档定位与四文档对账

本总纲不是新计划，而是把已有的四份文档对齐成一条主线，并修订其中的事实偏差。

| 源文档 | 角色 | 在本总纲中的去向 |
|---|---|---|
| `docs/plans/2026-06-05-foundation-governance-plan.md` | 地基治理主干（Phase 0–5） | 作为骨架保留，插入 Phase 0.5、修订 Phase 3 表述 |
| `docs/superpowers/specs/2026-06-04-student-answer-write-repository-design.md`（commit `83d04fd`） | StudentAnswer 写入收敛设计 | 编为 **Phase 4 前置横切项** |
| `docs/plans/2026-06-04-structural-security-repair-v2.md`（已 R3 PASS） | 归属链 / 路径安全修复 | 列入 §2 已完成项对账 |
| `docs/reviews/2026-06-05-foundation-plan-global-review.md` | 地基计划全局审查 | 结论吸收入本总纲；其 §2 一处错误推断在 §4.0.5 订正 |

**审查报告 §2 的订正（必须在此明确）**：原报告称架构模块"没有开关可关 / Phase 1 验收落空"——**该推断错误**。经核验，存在路由前缀→开关码的桥接层（见 §4.0.5 证据），架构模块**能**被学校开关控制。真实病灶不是"没有映射"，而是"映射**隐式、三重复制、零守卫**"。本总纲以订正后的判断为准。

---

## 1. 双根目标

本总纲服务两个不可妥协的根目标，二者同源（都靠静态守卫焊死不变量）：

1. **防回归（数据正确性硬目标）**：跨科目 / 归属链这类数据写入漏洞**结构上不可能再次出现**。手段是 StudentAnswer 写入收敛——11 处散写收敛到唯一写入门 + 零裸写静态守卫。这是"以后不能再出现"的机制化兑现，不是一次性修数据。
2. **地基收敛（门户吸收前提）**：在吸收成熟门户首页/服务中心/待办中心之前，先把 Portal 聚合合同、模块边界、依赖循环、AI 工具归属、权限/模块开关、入口目录收束到稳定合同。否则门户越抄越大，旧首页散调会扩大成系统级耦合。

两个目标共享同一治理范式（§3）：用 CI 静态守卫把不变量焊死，从"靠人记得"升级为"违反即红"。

---

## 2. 已完成项对账（防重复劳动）

地基计划写于 06-05，却未纳入 06-04 已落地的成果，存在重复劳动 / 冲突风险。此处显式登记：

| 已完成项 | 状态 | 证据 | 对本总纲的影响 |
|---|---|---|---|
| 归属链校验集中化 + compat fail-open 修复 | ✅ 已提交 | `f72ae58` `core/ownership.py` | StudentAnswer 收敛的底座已就位 |
| 路径安全函数 + 文件读取 containment | ✅ 已提交 | `fb68d18` `shared/path_safety.py` | 路径越权类漏洞已焊 |
| GPT R2 审查吸收（前缀绕过 + pipeline 归属链补漏） | ✅ R3 PASS | `13df3c9` | 安全修复线已收敛 |
| AI 工具 `module_code` 对齐 `card→exam` / `knowledge→research` | ✅ 已提交 | `1dee254` | **Phase 3 已起步**，应记为"首批已完成" |
| StudentAnswer 统一写入入口设计 | ✅ 设计已提交，待评审 | `83d04fd` | 即本总纲 Phase 4 前置横切项 |

**结论**：Phase 3「AI 工具归属重分类」第一批（`knowledge→research`）已经做了，计划应从"待启动"改为"已起步、继续推进"。

---

## 3. 统一治理范式：静态守卫焊不变量

本总纲把两条线统一到同一种工程范式——**不变量用 CI 静态守卫强制，而非靠 code review 或人记忆**。

| 不变量 | 守卫形式 | 服务的根目标 |
|---|---|---|
| StudentAnswer 写入必须经唯一门（零裸写） | 静态扫描测试：禁止 `core/` 外直接 `StudentAnswer(...)` / `session.add(StudentAnswer)` | 防回归 |
| 归属链 school→exam→subject→question 一致 | 写入门内强制 `core/ownership.py` 校验 | 防回归 |
| 架构模块 ↔ 开关码映射唯一 | 静态一致性测试：四方消费者派生自同一真源 | 地基收敛 |
| 无未声明跨模块依赖边 | `check_module_dependencies.py --check` | 地基收敛 |
| AI 工具 `module_code` 归属正确 | `check_ai_tool_modules.py` + 模块开关可见性测试 | 地基收敛 |

范式的价值：上述任一不变量被破坏，CI 即红，不依赖任何人"记得检查"。这是"以后不能再出现"唯一可信的兑现方式。

---

## 3.1 Contract Pack：不变量 → 反例 → 风险模块 → 测试债（回应 GPT F-001/F-002）

§3 的不变量是 prose 级目标。本节把每条下沉为**可执行契约**：入口 + fixture + 动作 + 预期失败 + 反例矩阵 + 风险模块 + 测试债。验收门槛——浅层存在性检查（"函数存在""文件存在"）不算通过，必须有"错误实现 → 测试红"的反例证明。

### 契约 C1：StudentAnswer 零裸写

- **入口**：`tests/governance/test_student_answer_write_guard.py`（静态扫描 `src/edu_cloud/**.py`）。
- **fixture**：在 allowlist 外任一文件插入 ① `StudentAnswer(` 直接构造 ② `session.add(StudentAnswer(...))` ③ 别名构造（`from ... import StudentAnswer as SA; SA(...)`）。
- **动作**：扫描三种形态——字面 `StudentAnswer(`、`session.add(` 内的 StudentAnswer 实例、`import ... as` 别名后的构造；+ allowlist 比对（allowlist = `core/student_answer_repository.py` / `modules/scan/models.py` / `data/seed_demo.py`）。
- **预期失败**：allowlist 外出现 ≥1 处任一形态裸写 → `assert matches == []` 红。
- **反例矩阵**：正例（仅 allowlist 内构造）绿；反例（`modules/foo/x.py` 加 `StudentAnswer(...)` / `session.add(StudentAnswer(...))` / 别名构造 各一）红。
- **风险模块**：scan / compat / pipeline / marking / exam_import（11 写入点所在域）。
- **测试债**：当前**无**静态守卫 → B6 启用 `test_student_answer_write_guard`；启用前任何新裸写不被拦截。

### 契约 C2：归属链一致（school→exam→subject→question）

- **入口**：`core/student_answer_repository.create_answer_checked` / `create_answers_for_subject`；回归测试 `test_student_answer_ownership_chain.py`。
- **fixture**：question_id 属于 subject_B，但请求 subject_A 写入。
- **动作**：`create_answer_checked` 内部 `verify_exam_subject_question_chain`（查库，覆盖 school→exam→subject→question 全链）；`create_answers_for_subject` 入口先 `verify_exam_subject_chain(exam_id, subject_id, school_id)`（1 次查库，校验 school→exam→subject 自洽）再逐行内存断言 `row.question.subject_id == subject_id`——两步合起来覆盖完整归属链。
- **预期失败**：外部输入跨 subject → `HTTPException(404)`；内部断言违反 → `ValueError`。
- **反例矩阵**：正例（同 subject）通过；反例（跨 subject / 跨 exam / 跨 school / **主观题 region 跨 subject** 各一）全被拒。最后一项对应写入点 8 hazard，**必须新增**。
- **风险模块**：`core/ownership` 调用方 + 5 写入点域；尤其批量入口 `create_answers_for_subject`（FG-P1-002 扩展点）。
- **测试债**：`test_student_answer_ownership_chain.py` 已存在，需扩 cross-exam / cross-school / 主观题 region 三类反例。

### 契约 C3：架构↔开关码映射唯一

- **入口**：Phase 0.5 新增一致性测试（拟 `tests/governance/test_module_semantics.py`）。
- **fixture**：把 `ROUTE_MODULE_MAP` 某条改成与映射真源不一致（如 `/api/v1/analytics → exam`）。
- **动作**：四方消费者（module_middleware / routeAccess / SERVICE_CATALOG / sidebarConfig）派生值逐条比对映射真源。
- **预期失败**：任一消费者与真源漂移 → 测试红。
- **反例矩阵**：正例（四方一致）绿；反例（中间件 / 前端 / Portal / 侧边栏漂移各一 + **未映射 prefix 默认放行** 一项）红。
- **fail-closed（采纳 R5 F-001）**：未知 route / 未映射 prefix / 缺失 switch code → **默认 deny，不得放行**；映射遗漏须被默认拒绝兜住，而非"四方一致即通过"。
- **风险模块**：module_middleware / routeAccess / SERVICE_CATALOG / sidebarConfig（四方消费者）。
- **测试债**：当前**无**四方一致性测试 → Phase 0.5 新增 `test_module_semantics`。

### 契约 C4：无未声明跨模块依赖边

- **入口**：`scripts/governance/check_module_dependencies.py --check`（CI）。
- **fixture**：模块 A 新增 `import` 模块 B 内部，制造未在 `module-dependencies.yaml` 声明的边。
- **动作**：扫描 import 图 vs 声明基线。
- **预期失败**：出现未声明边 → exit≠0。
- **反例矩阵**：正例（仅声明边）exit 0；反例（新增未声明边）exit 1。
- **风险模块**：全 23 架构模块（当前 55 边 / 30 循环）。
- **测试债**：`check_module_dependencies.py` 已存在（"禁止新增债"）→ Phase 4 升级为"要求债务下降 / 归零"。

### 契约 C5：AI 工具 module_code 归属正确

- **入口**：`scripts/governance/check_ai_tool_modules.py` + 每批可见性测试。
- **fixture**：关闭学校的 `study_analytics` 开关。
- **动作**：analytics 域工具 module_code → 经映射真源解析为开关码 → 校验该开关关闭时工具不可见。
- **预期失败**：关 `study_analytics` 后 analytics 工具仍可见 → 测试红。
- **反例矩阵**：正例（开→可见 / 关→不可见）；反例（关 study_analytics 仍可见 / 关 research 题库工具仍可见各一）红。
- **风险模块**：46 个挂 `exam` 的 AI 工具（analytics / profile / bank / knowledge 域错挂）。
- **测试债**：`check_ai_tool_modules.py` 已存在，需每批补模块开关可见性测试。

> **契约分层落地**：C1/C2 的完整 fixture 与反例代码已内联在 §4 Phase 4 前置（StudentAnswer 收敛设计）；C3–C5 的反例夹具随对应 Phase（0.5 / 4 / 3）writing-plans 一并提交。总纲在此固化"反例矩阵必须存在 + 必须变红"的契约口径，plan gate 在 **Phase 级**验证实例化——总纲不代各 Phase 写测试代码，但每条契约的入口/fixture/预期失败已确定，错误实现无法在浅层检查下蒙混。

---

## 4. 修订版 Phase 序列

保留地基计划的 Phase 0/1/2/3/4/5 骨架，做三处实质修订：**新增 Phase 0.5**、**Phase 3 语义校准**、**Phase 4 前置插入 StudentAnswer 收敛**。

### Phase -1（前置）：收口未提交 governance 工作

> 独立成阶段，消除与 Phase 0 的职责重叠（订正 GPT F-003：原 Phase 0 既把"整理 47 变更"列为交付内容，又在执行前置里要求"先收口"，逻辑打架）。

#### 现状

工作区约 50 个未提交变更（module governance 工作，停笔于 06:49），非本会话所写，是早间遗留。

#### 受影响范围（denominator，回应 GPT F-003）

未提交变更横跨 **14 个模块目录** + 7 类非模块资产（covered/total = 21/21），逐项处置防漏归类：

**模块目录（14）**：

| 模块 | 改动 | 处置归类 |
|---|---|---|
| academic / adaptive / calendar / conduct / grading / knowledge / knowledge_tree / menu / pipeline / profile / scan / studio（12） | `MODULE.md`（治理文档） | 主题：模块治理文档（批量 doc commit）|
| exam_import | `router.py`(M) + `MODULE.md`(新增) | 主题：模块治理 + **代码改动须走 code-review** |
| portal | 全新模块目录 | 主题：Portal 聚合（Phase 1 地基），独立 commit |

**非模块资产（7 类）**：

| 类别 | 文件 | 是否含代码 |
|---|---|---|
| governance 文档 | modules.yaml / dependency-graph.md / debt-report.md / MODULE-template.md / foundation-boundaries.md / module-dependencies.yaml / ai-tool-module-codes.yaml / portal-aggregation-contract.md | 否（doc）|
| governance 脚本 | aggregate_modules.py(M) + check_ai_tool_modules / check_module_dependencies / check_permission_mirror / module_governance_guard（新增） | **是 → code-review** |
| 测试 | test_aggregate_modules / test_codex_scripts / test_module_governance_guard / test_exam_import(M) + test_ai_tool_modules / test_module_dependencies / test_permission_mirror / test_portal_contract / test_portal（新增）| **是 → code-review** |
| 前端 | permissions.js（权限镜像）| **是 → code-review** |
| CI | `.github/workflows/test.yml` | **是 → code-review** |
| API | `router_registry.py` | **是 → code-review** |
| 调查/计划文档 | 2026-06-04 两份调查报告 + `docs/plans/*` + `docs/reviews/*` | 否（doc）|

#### 要做

- 按上表逐模块/逐类拆主题 commit；**所有"含代码"项走 `codex-review code`**，纯文档批量 doc commit。
- 与来源会话（疑似 `98958610`）确认归属，避免覆盖。

#### 验收

- 工作区 clean（`git status` 无未提交代码）。
- **14 个模块 + 7 类资产逐项有归属，covered/total = 21/21**（denominator 全覆盖，无漏归类）。
- 每个含代码的主题 commit 有对应 code-review receipt。

#### 不做

- 不在本阶段新增功能或重构。

---

### Phase 0：冻结治理基线

> 前提：Phase -1 已完成、工作区 clean。Phase 0 只做"把已收口的地基固定为可审查基线 + 设门槛"，**不再包含整理/提交变更**（该职责已移到 Phase -1）。

#### 要做

- 固定治理基线文件：`foundation-boundaries.md` / `module-dependencies.yaml` / `ai-tool-module-codes.yaml` / `portal-aggregation-contract.md`。
- 确认四个治理脚本通过：`aggregate_modules` / `check_module_dependencies` / `check_ai_tool_modules` / `check_permission_mirror`。
- 设定后续所有 Phase 的共同前置门槛：不能新增未声明模块、未审核依赖边、未归属 AI 工具。

#### 验收

- 四个治理脚本全部通过。
- 任何新增模块/依赖边/AI 工具/权限漂移都能被检查发现。

---

### Phase 0.5（新增）：模块语义统一 —— Phase 2/3 的硬前置

#### 4.0.5 病灶证据（订正审查报告 §2）

代码库存在两套模块概念：

| | 数量 | 真源 |
|---|---|---|
| 架构模块 | 23 | `modules/*/MODULE.md` |
| 学校开关模块 `MODULE_CODES` | 9 | `models/school_settings.py:20` |

`MODULE_CODES` = {exam, grading, homework, study_analytics, research, teaching, calendar, studio, conduct}

**两者之间的映射已经存在，但是隐式 + 三重复制 + 零守卫**（核验证据）：

| 消费者 | 文件:行 | 映射形态 | 示例 |
|---|---|---|---|
| 后端 API gating | `api/module_middleware.py:22` `ROUTE_MODULE_MAP` | 路由前缀→开关码 | `/api/v1/analytics→study_analytics`、`/bank→research`、`/marking→grading` |
| 前端路由守卫 | `frontend/src/config/routeAccess.js:5` `ROUTE_ACCESS_REQUIREMENTS` | 前端路由→开关码 | `/analytics/report→study_analytics`、`/question-bank→research` |
| Portal 服务目录 | `modules/portal/service.py:20` `SERVICE_CATALOG` | id/module_code | 全部取自 MODULE_CODES |
| 侧边栏 | `sidebarConfig.js`（计划 §49 已点名） | 第四份分散目录 | 同样按模块语义组织 |

**真实问题**（不是"没有开关"，是这三/四份表各管一份、无共享真源、无一致性测试）：
- **隐式**：映射编码在路由前缀里，读代码者得自己反推架构模块↔开关码关系。
- **三重复制**：中间件 / routeAccess / SERVICE_CATALOG / sidebarConfig 各维护一份。
- **零守卫**：没有任何测试保证四方对同一映射达成一致 → 漂移温床。
- `teaching` 是空壳开关码：中间件无 `/api/v1/teaching` 前缀，无架构模块、无工具、不在 `DEFAULT_ENABLED`。

#### 要做

- 建立**单一声明式映射真源**：`architecture_module → school_module_code` 一张声明表（建议落 `docs/governance/module-semantics.yaml` 或后端常量），覆盖 23↔9 全量，含 `teaching` 空壳的显式标注。
- 增加**四方一致性静态守卫测试**：`ROUTE_MODULE_MAP` / `routeAccess` / `SERVICE_CATALOG` / `sidebarConfig` 全部派生自或被校验对齐同一真源，任一漂移即 CI 红。

#### 不做

- 不在本 Phase 改业务行为，只抽取/声明映射 + 加守卫。
- 不删除现有任一映射表（行为不变契约），只让它们对齐真源。

#### 验收

- 存在单一映射真源，四方消费者派生/校验自它。
- 一致性测试覆盖全量 9 开关码，故意制造漂移时测试转红。
- `teaching` 空壳状态被显式登记。

---

### Phase 1：Portal 首页聚合合同落地

沿用原计划。验收项「关闭学校模块后 Portal 项消失」依赖 Phase 0.5 的映射真源（确认 `analytics`/`marking` 经 `study_analytics`/`grading` 可关）。

---

### Phase 2：统一入口目录、权限和模块开关

沿用原计划，但**显式依赖 Phase 0.5**：入口目录单一源头 = Phase 0.5 的映射真源。验收「所有入口 moduleCode ∈ MODULE_CODES」在 Phase 0.5 完成后才成立。

---

### Phase 3：AI 工具归属重分类（语义校准）

#### 校准（必读）

工具上的 `module_code` 含义是**「学校功能开关归属」**，不是「代码架构模块 owner」。原计划「不做」里写"不把工具归属和工具实际读写的数据源分离"——这与"把 analytics 工具迁到 study_analytics"看似矛盾，校准后不矛盾：

- 迁移目标 `study_analytics`/`research` 是**开关码**（学校能否看到该工具）。
- 工具实际读写的 `analytics`/`profile`/`bank`/`knowledge` 是**架构模块**（代码 owner）。
- 二者经 Phase 0.5 映射真源连接：`analytics(架构) → study_analytics(开关)`。迁移是"修正开关归属"，不是"切断工具与数据源"。

#### 进度修正

- 第一批 `knowledge→research`、`card→exam` **已完成**（`1dee254`），记为已起步。
- 剩余 46 个 `exam` 工具按原计划分批迁移，每批先加可见性测试再移动。

验收沿用原计划。

---

### Phase 4 前置横切：StudentAnswer 写入收敛（设计内联，证据链在计划包内闭合）

> 定位：**不是独立任务，是 Phase 4 去循环的前置横切基础**。理由：①数据正确性比模块美学更紧急（涉阅卷污染）②收敛跨模块写入 = 提前削掉部分循环耦合 ③与已完成的安全修复同源同分支。
> 完整背景见 `83d04fd` spec；本节**内联**接口契约 / 写入点映射 / 迁移批次 / 回滚边界，使本计划包**自包含**（回应 GPT F-004：不依赖包外设计事实）。

#### 接口契约（唯一写入门 `core/student_answer_repository.py`）

两个语义明确的入口，归属校验焊在内部，物理上绕不过：

```python
async def create_answer_checked(db, *, exam_id, subject_id, student_id,
        question_id, school_id, image_path=None, detected_answer=None,
        score=None, is_absent=False, is_anomaly=False,
        fill_ratios=None, question_type=None) -> StudentAnswer:
    # 外部传入 question_id → verify_exam_subject_question_chain（查库 1 次）
    # 失败 → HTTPException(404)；通过 → db.add()，不 commit。用于写入点 1,4,5,7

async def create_answers_for_subject(db, *, exam_id, subject_id, school_id,
        rows: list[StudentAnswerRow]) -> list[StudentAnswer]:
    # 入口先 verify_exam_subject_chain(exam_id, subject_id, school_id) 校验 school→exam→subject 自洽（1 次查库）
    # 再逐行内存断言 row.question.subject_id == subject_id（零额外查询）→ 合起来覆盖完整归属链
    # 断言违反 → ValueError；通过 → 逐条 db.add()，不 commit。用于写入点 2,3,6,8,9,10,11
```

`StudentAnswerRow`：轻量 dataclass，携带 `question`（Question 对象，断言依据）+ student_id + 可选字段。**批量入口的 row 必须携带 Question 对象**（非 question_id 字符串），否则无法内存断言。

#### 11 写入点 → 两入口映射

| 入口 | 写入点 | 场景 |
|---|---|---|
| `create_answer_checked`（外部输入→查库）| 1,4,5,7 | scan/compat 单条 HTTP 上传 |
| `create_answers_for_subject`（已持 Question→内存断言）| 2,3,6,8,9,10,11 | 批量 / 缺考自产 / pipeline 闭包 / 导入 |

> **写入点 8 hazard**（`pipeline_router.py` 主观题 `region_map`）：当前只映射 `region_id→question_id` 字符串、**未校验属本 subject**。闭包**装配阶段**用 `verify_questions_belong_to_subject` 把 region 的 question_id 批量校验并解析成 `region_id→Question` 缓存——**顺带消除写入点 8 跨 subject 隐患**（GPT 审查未覆盖，设计阶段新发现）。

#### 错误与回滚边界

- 外部输入跨归属 → `HTTPException(404)`（合法拒绝）；内部断言违反 → `ValueError`（编程错误，测试期暴露）。
- repository **不 commit**，由调用方维持原事务语义（请求 / pipeline 独立 session / 批量事务）→ **回滚边界不变**。
- 唯一约束冲突（重复答案）**不吞 IntegrityError**，交调用方按现有逻辑（409 / skip / rollback）。

#### 6 批迁移（子代理隔离 worktree，每批独立验证后再下一批）

| 批次 | 文件 | 写入点 | 验证 |
|---|---|---|---|
| B1 | `scan/router.py` | 1,2,3,4 | test_scan_* + ownership_chain |
| B2 | `compat_router.py` | 5,6,7 | test_compat* + ownership_chain |
| B3 | `scan/pipeline_router.py` | 8,9 | test_scan_pipeline_api + **新增主观题 region 跨 subject 被拒测试** |
| B4 | `marking/importer.py` | 10 | test_marking_import_isolation |
| B5 | `exam_import/service.py` | 11 | test_exam_import* |
| B6 | 启用静态守卫 | — | test_student_answer_write_guard |

#### 静态守卫（收敛的机器验收）

`tests/governance/test_student_answer_write_guard.py`：扫描 `src/edu_cloud/**.py`（仅生产代码，tests/ fixture 不受限），检测三种形态（与 §3.1 C1 一致）——① 字面 `StudentAnswer(` ② `session.add(StudentAnswer(...))` ③ 别名构造（先扫 `import StudentAnswer as <别名>` 建别名表，再扫该别名构造）；实现用 AST（`ast.Call` 解析被调名 + 别名表）确保别名 / 间接构造不漏。allowlist 仅 `core/student_answer_repository.py` / `modules/scan/models.py` / `data/seed_demo.py`，断言 allowlist 外三种形态零匹配。

> **scope 边界（R5 F-002 WONTFIX）**：本次收敛限 `StudentAnswer` **create（INSERT）写入**（11 处皆构造写入）；`update / delete / bulk / table-level` 写路径**不在本收敛范围**，列为独立后续项（另开 spec），不在此 plan 包内扩 scope。

#### 验收

- 11 处散写全部改道两入口，零裸写守卫通过（基线 2314 passed 量级，无新增 fail）。
- 写入点 8 hazard 关闭（主观题 region 跨 subject 被拒，B3 新增测试为证）。
- 归属链 + 路径安全回归测试持续绿（`test_student_answer_ownership_chain.py` / `test_path_safety.py`）。
- 对应 §3.1 契约 C1（零裸写）/ C2（归属链）的反例矩阵全部落地。

---

### Phase 4：依赖循环拆解（30→0）

沿用原计划四批。补一条关联：

- **StudentAnswer 收敛与第二批（切 `pipeline→analytics/profile/bank/knowledge/student`）强相关**——多数 pipeline 外发循环源于跨模块派生写入。收敛后该批难度下降，应在收敛完成后重新评估剩余循环数。

里程碑沿用原计划：30→≤10→pipeline 外发≤3→归零；`check_module_dependencies.py --check` 从"禁止新增债"升级为"要求债务下降或归零"。

---

### Phase 5：门户能力吸收准备

完全沿用原计划。前置条件：Phase 0.5–4 全部完成。

---

## 5. 风险控制

沿用原计划风险 1–5，新增两条：

### 风险 6：工作区有未提交的 governance 工作

- 现状：`feat/module-governance-repair` 分支有约 50 个未提交变更（module governance 工作，停笔于 06:49，**非实时写入**）；另有两个 idle 的 `claude` 进程（07:17 经 SSH 启动后睡眠，未在写）。
- 控制方式：本总纲为纯新文档不提交；落地执行前先把这批未提交工作按主题拆分收口提交，再进入分批执行，避免把早间/他人未提交工作混入提交。

### 风险 7：T3 计划无 plan gate

- 现状：地基计划与本总纲均有 plan 无 `gates.json`，`completion_guard` 会持续 CONFLICT。
- 控制方式：本总纲定稿后走 `codex-review plan`，生成 gates.json，再进入分批执行。

---

## 6. 执行顺序与 gate 要求

```
[Phase -1] 收口未提交 governance 工作 → 工作区 clean
   ↓
本总纲 codex-review plan → gates.json
   ↓
Phase 0   冻结治理基线（固定基线文件 + 设门槛，不含提交动作）
   ↓
Phase 0.5 模块语义统一（映射真源 + 四方一致性守卫）   ← 新增硬前置
   ↓
Phase 1   Portal 聚合合同
   ↓
Phase 2   统一入口目录（依赖 0.5）
   ↓
Phase 3   AI 工具归属（首批已完成，继续推进）
   ↓
Phase 4前置  StudentAnswer 写入收敛（零裸写 + 写入点8 hazard）
   ↓
Phase 4   依赖循环拆解 30→0
   ↓
Phase 5   门户吸收
```

每个 Phase 按子代理隔离执行（worktree + manifest + diff_hash 绑定 `codex-review code`），merge 前 `completion_guard` 校验 needs_review 已消费。

**通用回滚边界（采纳 R5 F-004）**：每个 Phase 的 worktree + 独立 commit 即天然回滚单元——中间阶段失败时回退该 Phase 的 commit 集即可，不影响已合并的前序 Phase；涉及映射 / 导航 / 工具可见性 / 依赖声明的变更，回退范围 = 该 Phase 的 commit 集。各 Phase 落地 writing-plans 时细化本 Phase 的具体回退步骤。

---

## 附：本文档自身的治理状态

- 本文档为纯新增，路径独立于并发窗口的 47 个在途文件，未触碰任何在途代码。
- 落地前置：①未提交 governance 工作收口 ②`codex-review plan` gate。
- **治理真源激活（GPT F-004）**：本总纲定稿（plan-review PASS）后，须登记 `docs/context/ACTIVE_INDEX.md`，否则不构成 active truth。登记动作待定稿 + 工作区 clean 后执行（涉及在途文件，需用户确认时机）。
- 与四份源文档的对账见 §0；审查报告 §2 的错误推断在 §4.0.5 订正。
- **plan-review 收敛记录（5 轮，engine 机器 verdict）**：R1=4 → R2=4 → R3=3 → R4=2 → R5=4（反弹）。R5 为最终轮（R6+ `gates_lib` 硬拒绝）。**定稿于 R5 处置态**——总纲定位为战略编排层，plan-review engine 用"单一可执行规格"尺子无法在此层自然 PASS（R5 反弹为证）；颗粒度收敛留给各 Phase 各自 plan-review。
- **R5 处置**：
  - F-001（fail-closed）✅ 采纳入 §3.1 C3。
  - F-004（通用回滚边界）✅ 采纳入 §6。
  - F-002（update/delete 写路径）⛔ WONTFIX——本收敛限 create 写入，越界项另开 spec（见 §4 前置 scope 边界）。
  - F-003（字面同名 design 文档）⛔ WONTFIX——StudentAnswer 设计已内联 §4 前置 + 引用 `83d04fd`，证据链已闭合，不重复造文档（依 L017 全局优先于 GPT 模板要求）。
- **gate 状态**：本总纲不写 `plan_review` PASS receipt（engine R5 verdict=FINDINGS，不捏造）；各 Phase 落地执行时各自走正式 `codex-review plan` gate。
