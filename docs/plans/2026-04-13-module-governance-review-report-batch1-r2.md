[edu-cloud] GPT Reviewer | 2026-04-13 20:42:04
# 审查报告: Task 1-7（单批次全量） — Round 2

结论: **PASS**

审查输入:
- Round 1 FAIL 报告: `docs/plans/2026-04-13-module-governance-review-report-batch1.md`
- Round 2 修复 commits: edu-cloud `213f503` + ~/.claude `29913bd`
- GPT 原始输出 SHA256: `f7505a2da9c7b882009ef1bd1f09ec26f8ff1807a9d167dcf4d5ce023a95df6f`
- 原始日志: `docs/plans/.codex-raw-code_review-mg-batch1-r2-20260413-204203.log`

> 注: Round 1 与 Round 2 的 PASS 报告锚定规则（review-templates.md）要求 `gates.json.report_path` 指向本 Round 2 PASS 报告文件，而非 Round 1 FAIL 报告。

---

## 第一段：测试充分性

- `python -m pytest tests/governance/ -q` → 34 passed（新增 6 个反退化测试，从 28 增至 34）
- GPT 独立做"删除核心逻辑"反证：
  - 将 `_checkout_staged_index` 强制退化为"读 worktree" → 前 3 个 staged 测试 FAIL
  - 将 `NESTED_REQUIRED = {}` → 后 3 个嵌套 schema 测试 FAIL
  - 新增测试不是 tautology
- 全量测试 1976 passed / 5 failed（5 failed 与 governance 零交集，pre-existing）

## 第二段：行为正确性

### 变更理解

Round 2 修复对 Round 1 四条 finding 的对齐实现：
- **G2-01 (staged-index 读取)**: `check()` 入口用 `git checkout-index --all --prefix=<tmp>/` 把整个 staged index 导出到临时 snapshot，`check_new_module` / `check_derived_products_fresh` / `check_touched_legacy` 三处从 snap 读数据；HEAD 查询与 `_import_aggregate_module` 仍走 real_repo。子 check 签名新增 `real_repo` 可选参数（默认 None fallback 至 repo，保持旧测试向后兼容）。
- **G2-02 (嵌套 schema 校验)**: `aggregate_modules.parse_module_md` 新增 `NESTED_REQUIRED = {exposes: [services], depends_on: [modules, services, ai_tools]}` + "父节点不是 mapping 则 raise" 两层校验。
- **G2-03 (反退化测试)**: 新增 6 个测试（3 个 hook snapshot + 3 个 parser 嵌套）+ 将原 `test_check_entry_blocks_on_invalid_existing_module_md` 重构为 staged 坏版本路径（符合 G2-01 语义）。
- **G2-04 (baseline 总括声明)**: 撤回"每条 3 类证据齐备"blanket claim，改为"HIGH/MED 完整；LOW/结构观察类仅部分证据"分层表述。

### Executor 自审抽检（GPT 独立验证）

- **G2-01**: GPT 独立构造三组场景 — `staged 合法/worktree 改坏 → allow`、`staged 坏/worktree 好 → block`、`staged MODULE 新版 + staged 派生产物旧版 + worktree 派生产物新版 → block "派生产物过期"` — 全部符合预期。
- **G2-02**: 独立构造 `exposes: {}`、`depends_on` 缺 `modules`、`exposes: []` 均 raise；grading/pipeline MODULE.md 仍通过；`exposes.events` 未被误收紧为必填。
- **G2-03**: 独立做"删除核心逻辑"反证 — 前 3 个 staged 测试和后 3 个 parser 测试均能在退化时 FAIL（非 tautology）。

### 对抗性审查

- 红旗模式：未触发（snap 仅改"信任源"，不改状态机/fallback/阈值/时序/策略）
- 边界条件：`md_abs.exists()` 缺失分支按 missing 正确 block
- 向后兼容：子 check `real_repo or repo` fallback 语义正确，既有 28 tests 全部兼容
- 并发安全：`tempfile.TemporaryDirectory()` context 独立
- Windows/Unix 路径：`str(tmp_path).replace(os.sep, "/")` prefix 适配 POSIX，git for Windows 可接受
- Round 1 遗漏 finding：无（见"新增 finding"段）

## 第三段：未测试风险

- Round 2 同时发现 2 个 LOW 非阻塞问题（R2-NEW-01 / R2-NEW-02），记录在下方 finding 清单。

---

## 发现清单

### Round 1 Finding 终态（4 条 — 全部 resolved-correct）

### G2-01
- **Status**: verified
- **Terminal**: **resolved-correct**
- 证据: `module_governance_guard.py:65` (_checkout_staged_index), `:370/378/380/381` (check() 传 snap + real_repo); 测试 `test_module_governance_guard.py:322/349/375`

### G2-02
- **Status**: verified
- **Terminal**: **resolved-correct**
- 证据: `aggregate_modules.py:27-29` (NESTED_REQUIRED), `:73/77` (校验逻辑); 测试 `test_aggregate_modules.py:59/74/88`

### G2-03
- **Status**: verified
- **Terminal**: **resolved-correct**
- 证据: 6 新增测试 + GPT 反证验证（删除核心逻辑会 FAIL）

### G2-04
- **Status**: verified
- **Terminal**: **resolved-correct**
- 证据: baseline.md:5 + :222 表述已收敛，明确"不适合作为机械完备证据包"

---

### Round 2 新增 Finding（2 条 — 均 LOW 不阻塞）

### R2-NEW-01
- **ID**: R2-NEW-01
- **Severity**: LOW
- **Category**: code-bug
- **Type**: defect_fix
- **Before-behavior**: 注释描述 `_checkout_staged_index` 在"非 git 目录 fail-safe 返回 False"。
- **After-behavior**: 非 git 目录应显式识别失败并 fallback，而不是把空目录当成功 snapshot。
- **Inv-conflict**: none
- **Evidence**: `~/.claude/hooks/module_governance_guard.py:69,75,81`。独立实测：非 git 目录里 `git checkout-index --all --prefix ...` 返回 0，helper 返回 True；随后 check() 会在"长得像 edu-cloud"的普通目录上给出治理 block。
- **Impact**: 仅影响错误使用场景（非 git 目录且路径满足 `_is_edu_cloud` 启发式）；真实 commit 不受此问题阻断；**不构成本轮 FAIL**。
- **Repair hypothesis**（建议方向，非权威）: 先做 `git rev-parse --is-inside-work-tree` 或校验 snapshot 非空/`.git` 存在，再认定 checkout 成功。
- **Status**: verified
- **Terminal**: **resolved-correct**（方案 B — 已修复，commit 见 ~/.claude）
- **修复说明**: 采用 `(repo / ".git").exists()` 校验（`rev-parse --is-inside-work-tree` 会向上查找父目录，Windows 下 temp 目录在 `C:/Users/Administrator` git 仓库内被误判为 true）。新增 2 个反退化测试 (`test_checkout_staged_index_returns_false_in_non_git_dir` / `test_checkout_staged_index_returns_true_in_git_dir`)。

### R2-NEW-02
- **ID**: R2-NEW-02
- **Severity**: LOW
- **Category**: design-concern
- **Type**: defect_fix
- **Before-behavior**: 旧实现无 repo-wide snapshot 开销。
- **After-behavior**: 每次 `git commit` 都执行 `checkout-index --all` 全仓导出。edu-cloud 实测约 2750ms。
- **Inv-conflict**: none
- **Evidence**: `~/.claude/hooks/module_governance_guard.py:75`。GPT 实测单次导出约 2750ms。
- **Impact**: 正确性 OK；性能成本与仓库规模线性相关；**不阻塞通过**，但是可感知的 commit 时延回归。
- **Repair hypothesis**（建议方向，非权威）: 后续可只导出 `staged_info.files` 所在模块与 `docs/governance`，不必整仓 `--all`。
- **Status**: verified
- **Terminal**: **deferred**
- **Deadline**: 2026-05-15（下月后续改进批次）
- **Reason**: 当前 edu-cloud 规模下 2.7s/commit 可接受，优化路径清晰但属"重构非修 bug"。记入 debt，后续独立批次处置，不扩大本批次 scope。

---

## PASS/FAIL 判定

- Round 1 G2-01/G2-02/G2-03/G2-04 全部 resolved-correct（code-bug/test-gap MED 已修复）
- Round 2 新增 R2-NEW-01/R2-NEW-02 均 LOW，不阻塞
- **Round 2 结论：PASS**

## 行为变更审批记录

Round 2 全部 finding type=`defect_fix`，**无 behavior_change**。红旗检查：
- G2-01 修复（读 index 替代工作区）：实现与 handoff 声明对齐，不改状态机/策略
- G2-02 修复（嵌套校验收紧）：完善已声明的必填契约
- G2-04 修复（文档表述撤回）：纯文档修正
- R2-NEW-01 (若修复)：仅加 fail-safe 校验
- R2-NEW-02 (若修复)：性能优化，可 deferred

所有 finding 按批量 defect_fix 常规处置（LOW 非阻塞项用户可选 accepted-risk / deferred / 快速修复）。

---

## 下一步

Gate 2 Code Review **PASS**。Planner 对 R2-NEW-01/R2-NEW-02 做处置决定：
- **R2-NEW-01 (LOW code-bug)**: (a) 快速修复（加 `git rev-parse --is-inside-work-tree` 校验） (b) accepted-risk（只影响错误使用场景） (c) deferred
- **R2-NEW-02 (LOW design-concern)**: (a) accepted-risk（edu-cloud 规模下可接受） (b) deferred（后续优化）

Gate 2 PASS 后按 plan Task 8：CLAUDE.md 回写 + design.md `[实现完成]` 标记。
