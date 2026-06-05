# 地基治理计划 全局深度审查（2026-06-05）

> 审查对象：`docs/plans/2026-06-05-foundation-governance-plan.md`
> 审查视角：全局架构高度 + 与在途任务（安全修复 / StudentAnswer 写入收敛）的合并定位
> 审查人：Claude（会话续接 da78ddb4 → 安全修复线）
> 性质：只读审查，不改任何代码/在途文件
> ⚠ 审查期间工作区存在未提交的 governance 工作（停笔于 06:49，非实时写入；详见 §0 含订正说明）

---

## 0. 工作区状态发现（最高优先级）

> ⚠ **2026-06-05 订正**：本节初稿断言"另一个 Claude 窗口正在并行写入"，经进程核验该判断**错误**，已改写为下方事实。错误根因：仅凭"工作区 dirty + 存在 claude 进程"即推断"实时并行写"，未核实进程状态（实为 sleeping）与文件修改时间（实为 2 小时前停笔）。

审查时 `git status` + 文件时间戳 + 进程状态核验，真实状态如下：

证据：
- 工作区约 50 个未提交变更，其中真正的 governance 代码（`src/edu_cloud/modules/portal/`、各 `MODULE.md`、`check_*.py` 治理脚本）**最新修改时间停在 06:46–06:49**，此后无人改动（过去 60 分钟零修改）。
- 本审查会话上一次 commit（`83d04fd` design doc）为 06-04 22:55。
- 进程 PID 4026243 / 4026313（`claude --effort max`，07:17 经 SSH 启动）状态为 **`S` (sleeping)**，命令行无任务参数——**闲置睡眠，未在写入**。
- 因此**不存在"实时并行写入"**：那批 governance 变更是约 2 小时前停笔的静态未提交工作。

**结论与影响**：
1. 计划「当前事实基线 → 已经具备的地基」（治理脚本可通过、portal API 已存在、权限镜像已对齐、Phase 0 产物文件齐全）——**实为一批尚未提交的在途工作区状态，不是已冻结的稳定基线**。这印证计划 Phase 0 第一条「整理当前分支未提交变更」尚未完成。
2. 风险不是"实时撞车"，而是：这批未提交工作非本审查会话所写，**本审查不应将其混入自身提交，也不擅自改动**。本审查只新增独立路径文档。

---

## 1. 计划事实基线核对（数字属实）

| 计划断言 | 核实命令 | 结果 |
|---------|---------|------|
| 模块合同 23 | `ls modules/*/MODULE.md` | ✅ 23 |
| 55 边 / 30 循环 | `check_module_dependencies.py --check` | ✅ `55 edges, 30 cycles` |
| 67 工具 / 46 挂 exam | grep `module_code=` | ✅ 46 exam + 9 conduct + 6 homework + 3 research + 3 grading |
| 4 个治理脚本可通过 | 逐一存在性 + baseline clean | ✅（但脚本本身未提交，见 §0）|

数字层面计划准确、调查扎实。问题在概念层与衔接层。

---

## 2. 核心发现：计划建立在「一套模块语义」的假设上，实际有两套且互不映射

代码库存在**两套独立的模块概念**：

| | 数量 | 用途 | 真源 |
|---|------|------|------|
| 架构模块 | 23 | `modules/*/MODULE.md`，依赖图 / AI 工具治理 | `modules/` 目录 |
| 学校开关模块 `MODULE_CODES` | 9 | 学校功能开关，权限 / 模块开关 | `models/school_settings.py:20` |

`MODULE_CODES` = {exam, grading, homework, study_analytics, research, teaching, calendar, studio, conduct}

**两套命名对不上**（实测）：
- **17 个架构模块不在 MODULE_CODES**（无法被学校开关控制）：academic, adaptive, analytics, bank, card, exam_import, knowledge, knowledge_tree, marking, menu, paper, pipeline, **portal**, profile, scan, school, student
- **3 个 MODULE_CODES 无对应架构模块目录**：research, study_analytics, teaching

### 由此打穿的计划验收

1. **Phase 3 自相矛盾**：要把工具迁到 `study_analytics`/`research`（开关码），又在「不做」声明「不把工具归属和实际读写数据源分离」。但工具读写的是 `analytics`/`profile`/`bank`/`knowledge`（架构模块），归属设成 `study_analytics`/`research`（开关码）——名字不是一回事，照做即违反自己的「不做」。
2. **Phase 1 验收落空**：要求「关闭学校模块后 Portal 项消失」，但要聚合的 `analytics`、`marking` 不在 MODULE_CODES，**没有开关可关**。
3. **Phase 2 验收「入口 moduleCode ∈ MODULE_CODES」**：当前大量入口语义模块（analytics/profile…）不在这 9 个里，计划未给出扩展或映射方案。

**建议**：计划缺一个前置 Phase（建议 Phase 0.5「模块语义统一」）——建立 `23 架构模块 ↔ 9 学校开关模块` 映射表，或显式扩展 MODULE_CODES。否则 Phase 2/3 落地即卡。

---

## 3. 与在途任务的关系：不冲突，是互补的两层

| | 在途任务（安全修复线，已 R3 PASS + design 已提交）| 本地基计划 |
|---|---|---|
| 层次 | 数据写入不变量（StudentAnswer 归属链焊死在唯一写入门）| 模块边界 / 依赖 / 入口聚合 |
| 状态 | 安全修复+module_code 已 commit；写入收敛设计已 commit | Phase 0/1 在途未提交（停笔于 06:49）|

### 两个正面衔接点（计划未承认，但已发生）
1. **06-04 的 `knowledge→research` module_code 改动，正是 Phase 3 首批预演**——方向一致，应记为「Phase 3 已起步」。
2. **StudentAnswer 写入收敛（11 处散写 → core/ 唯一门）直接服务 Phase 4**：5 个写入点（scan/compat/pipeline/marking/exam_import）横跨 Phase 4 要拆的循环簇（exam/pipeline/scan/grading）。收敛跨模块写入 = 提前削掉部分循环耦合。

### 合并定位建议
StudentAnswer 写入收敛不是独立任务，应作为地基计划的**横切前置项**，排在 Phase 4 之前：①数据正确性比模块美学更紧急（涉阅卷污染）②为 Phase 4 去循环铺路 ③与已完成的安全修复同源同分支。

---

## 4. 其他全局风险
- **Phase 4「循环归零」(30→0) 是全场最高难度**，且多数循环源于 pipeline 跨模块派生写入与 AI 工具 import；StudentAnswer 收敛能削一部分，计划未把二者关联。
- **计划未做「已完成项对账」**：写于 06-05，却未纳入 06-04 安全修复 / module_code 对齐 / 写入收敛设计，存在重复劳动或冲突风险。
- **`teaching` 是空壳开关码**：MODULE_CODES 有，但无架构模块、无工具、不在 DEFAULT_ENABLED，计划全程未提。

---

## 5. 合并落地建议（待并发理清后执行）
合并成一份统一治理总纲，关键改动：
1. 新增 **Phase 0.5「模块语义统一」**（23↔9 映射），作为 Phase 2/3 硬前置。
2. **StudentAnswer 写入收敛**编入计划，定位 Phase 4 前置横切项。
3. 增「**已完成项对账**」段：标注安全修复 / knowledge→research / 写入收敛设计状态。
4. 修正 **Phase 3 内在矛盾**（明确 module_code 用哪套语义）。

⚠ 落地前置条件：解决 §0 并发冲突（等另一窗口收尾提交，或本审查方换 worktree），且本 T3 计划需补走 `codex-review plan` gate（当前有 plan 无 gates.json）。

---

## 6. 给未提交 governance 工作的衔接提示
- 工作区中 Phase 0/1 的 governance 工作（脚本 / portal / MODULE.md）尚未提交——`completion_guard` 会因「未审查代码 + 有 plan 无 gates.json」持续 CONFLICT。需按主题拆分提交并走 `codex-review plan` + `code`。
- 提交前请注意：本审查 §2 的「两套模块语义鸿沟」会直接影响 Phase 2/3 的实现路径，建议先确认映射方案。
- 本审查只新增了 `docs/reviews/` 下这一个文件，未触碰工作区任何在途文件。
