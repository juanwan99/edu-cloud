[edu-cloud] GPT Reviewer | 2026-04-13 19:39:13
# 审查报告: Task 1-7（单批次全量） — Round 1

结论: **FAIL**

审查输入:
- handoff: `docs/plans/2026-04-13-module-governance-review-handoff-batch1.md`
- plan: `docs/plans/2026-04-13-module-governance-plan.md`
- 范围: edu-cloud 6 commits (ced5ea7 / b7d1a66 / 6c3519d / 946b345 / 3088c63 / 34190d6) + ~/.claude 2 commits (5c66b45 / 50d3997)
- GPT 原始输出 SHA256: `793f095e7795a7f9e254bdb81dbcfa7ea465a04e74237e3d48368c3a04fd165e`
- 原始日志: `docs/plans/.codex-raw-code_review-mg-batch1-20260413-193817.log`

---

## 第一段：测试充分性

- `python -m pytest tests/governance -q` → 28 passed（Claude 本地 11.88s）
- 但 GPT 独立复现到两类退化：staged/worktree 分叉 + 嵌套 schema 缺失。handoff 声称「只信 staged」与「frontmatter 必填字段全填」，现状不满足其一。
- F001/F002/F004/KILL_SWITCH 主路径 OK（GPT 独立验证签名一致性、空仓库/非 git 目录 fail-safe、CLI/入口测试）。

## 第二段：行为正确性

### 变更理解

本批次意图：为 edu-cloud 新增模块治理基础设施——通过 `MODULE.md`（人读 frontmatter 契约 / 项目级单一真源）+ `aggregate_modules.py`（机读聚合 → `modules.yaml` / `dependency-graph.md` / `debt-report.md`）+ `module_governance_guard.py`（PreToolUse Bash hook，阻断新建模块缺 MODULE.md / owns_* 跨模块冲突 / 派生产物过期 / 触碰存量 ≥50 行缺 MODULE.md 的 commit）实现"模块边界/职责自证"。

hook 作为 `commit_guards.py` CHECKS 列表第 4 项接入，边界隔离依赖 `_is_edu_cloud(cwd)` 门控与 `EDU_GOVERNANCE_GUARD_DISABLED=1` kill switch，非 edu-cloud 仓库零影响。grading / pipeline 两份 MODULE.md 作为人工试点（Step 1 真实 grep → Step 2 按实情填写 → 禁止预设边界）。

### Executor 自审抽检（抽 3 项独立验证）

- 「F001 hook 契约一致性」：GPT 独立读取 `commit_guards.py:99` 和 `module_governance_guard.py:315-316` 的 `check(data, session_state, staged_info=None)` 签名，确认与 `doc_sync_guard` / `logging_guard` / `refactor_guard` 一致 — ✅ 属实
- 「F004 CLI 入口测试」：`tests/governance/test_aggregate_modules.py::test_cli_entry_produces_outputs` GPT 独立触发 subprocess 运行 `python aggregate_modules.py` 确认 exit 0 + stdout 含 "Aggregated" — ✅ 属实
- 「F008 frontmatter 校验」：handoff 声称 staged MODULE.md 必须通过 `parse_module_md` → GPT 构造 `exposes: {} / depends_on: {}` 的合法顶层 YAML 独立测试 → **`check_new_module` 仍返回 None**（G2-02 根因） — ❌ 不实，handoff 陈述未兑现嵌套字段

### 对抗性审查

- **边界输入构造**: GPT 在独立 tmp 仓库中构造 `staged 合法 / worktree 破坏` 与 `staged 陈旧 / worktree 修好` 两例，独立复现 G2-01（guard 读工作区 ≠ 读 index）
- **异常路径追踪**: 追踪 `_dir_exists_in_head()` 在空仓库 / 非 git 目录的 fail-safe 返回 False，主路径 OK；但下游 `check_new_module` 读 `repo / md_rel` 直接 I/O 磁盘，未走 index
- **假阴性检测**: aggregate_modules.py `REQUIRED_FIELDS` 顶层 8 键集合 vs 模板 `MODULE-template.md:76-80,101` 必填的 `exposes.services` / `depends_on.{modules,services,ai_tools}` 不一致 → 测试集未构造嵌套缺失负例，假阴性得以存在

### 整体判断

- G2-01/G2-02 是真实的行为-声明不一致，GPT 在独立临时仓库中各自复现了两个反例。
- G2-03 是 G2-01/G2-02 的直接推论（测试用 tmp_path 而非 `git add` 流程，无法暴露 index/worktree 语义）。
- baseline 文档存在总括声明不准确的问题（G2-04，非阻塞）。

## 第三段：未测试风险

- 测试用 tmp_path + 直接写 MODULE.md + 不经过 `git add`，因此"staged 与 worktree 分叉"的语义差异无从暴露。
- 嵌套必填未被 `REQUIRED_FIELDS` 覆盖，共享 parser 宽松。

---

## 发现清单

### G2-01
- **ID**: G2-01
- **Severity**: MED
- **Category**: code-bug
- **Type**: defect_fix
- **Before-behavior**: guard 声称基于 staged 结果判断新模块 MODULE.md 合规性和派生产物新鲜度，但实际读取工作区文件。`git add` 后若继续改工作区，判定偏离真实待提交内容。
- **After-behavior**: block/allow 严格基于 index（staged blob），不回退到工作区。
- **Inv-conflict**: none
- **Evidence**:
  - `~/.claude/hooks/commit_guards.py:101` 只传 `{"files","diff"}` 给子 guard
  - `~/.claude/hooks/module_governance_guard.py:140` `agg.parse_module_md(repo / md_rel)` 直接解析工作区
  - `~/.claude/hooks/module_governance_guard.py:294-295` `read_text()` 比较磁盘上的 `docs/governance/*`
  - GPT 复现两例：staged 合法/worktree 破坏 → `check_new_module` 仍 block；staged 陈旧/worktree 修好 → `check_derived_products_fresh` 返回 None
- **Impact**: F007/F009 当前非"只信 staged"。会出现有效提交被误拦或无效治理提交被放过。
- **Repair hypothesis**（建议方向，非权威）: 读取 index blob (`git cat-file blob :<path>` 或 `git show :<path>`) 做校验与比对；禁止 block 级检查回退到工作区。
- **Status**: verified
- **Terminal**: （待处置）

### G2-02
- **ID**: G2-02
- **Severity**: MED
- **Category**: code-bug
- **Type**: defect_fix
- **Before-behavior**: 共享解析器只校验顶层 `exposes` / `depends_on` 存在性，不校验模板声明为必填的嵌套子字段 `exposes.services` / `depends_on.modules` / `depends_on.services` / `depends_on.ai_tools`。
- **After-behavior**: frontmatter 解析器拒绝缺失嵌套必填项的 MODULE.md（保持与模板字段矩阵一致）。
- **Inv-conflict**: none
- **Evidence**:
  - 模板必填矩阵：`MODULE-template.md:76,78,79,80` + `:101`（"frontmatter 必填字段全填"）
  - `scripts/governance/aggregate_modules.py:17-33` `REQUIRED_FIELDS` 仅顶层 8 键
  - `scripts/governance/aggregate_modules.py:55-58` 仅做顶层存在性校验
  - GPT 复现：`exposes: {}` + `depends_on: {}` 被 `parse_module_md()` 接受，`check_new_module()` 返回 None
- **Impact**: F008 允许不完整契约进库，后续 `modules.yaml` / dependency-graph 会静默缺字段，治理数据失真。
- **Repair hypothesis**（建议方向，非权威）: 嵌套 schema 校验在共享解析器中收敛（aggregate + hook 同一套严格契约）。
- **Status**: verified
- **Terminal**: （待处置）

### G2-03
- **ID**: G2-03
- **Severity**: MED
- **Category**: test-gap
- **Type**: defect_fix
- **Before-behavior**: 现有 28 个治理测试全部用 tmp_path 直接写 MODULE.md，不经过 `git add`；也未覆盖嵌套必填缺失负例。G2-01/G2-02 这类退化在全绿测试下漏过。
- **After-behavior**: anti-regression 测试覆盖（a）staged/worktree 分叉；（b）嵌套 schema 缺失。
- **Inv-conflict**: none
- **Evidence**:
  - `tests/governance/test_module_governance_guard.py:128,142,153` 新模块测试仅覆盖"是否有 MODULE.md / 顶层缺字段 / YAML 非法"
  - `tests/governance/test_module_governance_guard.py:284,299` 派生产物测试仅覆盖 fresh/stale on disk
  - `tests/governance/test_aggregate_modules.py:32` 聚合器只测顶层缺 name
- **Impact**: handoff 里对 F007/F009/F008"已加固"的说法目前不成立。
- **Repair hypothesis**（建议方向，非权威）: 补 index vs worktree 分叉场景（实际 `git add` 后改 worktree）+ `exposes.services` / `depends_on.*` 嵌套缺失负例。
- **Status**: verified
- **Terminal**: （待处置）

### G2-04
- **ID**: G2-04
- **Severity**: LOW
- **Category**: design-concern
- **Type**: defect_fix
- **Before-behavior**: baseline 报告自称"每条冲突都有 file:line + 调用方 grep + git log 三类证据"，但实际条目 #2/#6/#8 不达标。
- **After-behavior**: 逐条补齐三类证据，或撤回总括声明。
- **Inv-conflict**: none
- **Evidence**:
  - 总括声明：`docs/governance/edu-cloud-module-baseline-2026-04-13.md:5,222`
  - 条目 #2 缺 git 痕迹：`:68`
  - 条目 #6 缺证据段：`:134`
  - 条目 #8 缺三类证据：`:157`
- **Impact**: 基线报告可用但证据强度不均匀，后续把它当"机械完备证据包"会高估可信度。
- **Repair hypothesis**（建议方向，非权威）: 补齐逐条证据，或撤回 blanket claim。
- **Status**: verified
- **Terminal**: （待处置）

---

## PASS/FAIL 判定

- 阻塞: G2-01 / G2-02 / G2-03（2 code-bug MED + 1 test-gap MED 未修复）
- 非阻塞: G2-04（design-concern LOW）
- **结论: FAIL**（Round 1）

## 行为变更审批记录

本次 4 个 finding 全部 type=`defect_fix`，**无 behavior_change**。红旗模式检查：
- G2-01 "改信任源（工作区→index）": 不命中（不改状态机/fallback/策略/阈值/时序），修复方向是使实现与 handoff 声明一致
- G2-02 "嵌套 schema 校验": 不命中（收紧校验，不改行为）
- G2-03 "补测试": 不命中
- G2-04 "补证据": 不命中

所有 finding 可按批量 defect_fix 常规处置。

---

## 下一步

Round 2 修复方向（待用户批准）:
1. G2-01: `check_new_module` / `check_derived_products_fresh` 改读 index（`git show :<path>`）
2. G2-02: `parse_module_md` 增加嵌套必填校验
3. G2-03: 新增 2 类反退化测试（staged/worktree 分叉 + 嵌套缺失负例）
4. G2-04: 处置选项（a）补齐条目 #2/#6/#8 的 git 痕迹 / 调用方证据；（b）撤回"每条三类证据"总括声明 → LOW 不阻塞，也可 deferred

预期影响:
- 不影响 grading/pipeline/MODULE.md（两份均已含完整嵌套字段）
- 不影响非 edu-cloud 仓库（KILL_SWITCH + `_is_edu_cloud` 门控不变）
- 新增约 2-3 个测试，现有 28 个测试继续 PASS

预计 Round 2 commits: ~2（1 edu-cloud: parser + tests + fix / 1 ~/.claude: guard index-read）
