[edu-cloud] Executor→Reviewer | 2026-04-13 12:33:22
# 审查交接单: Task 1-7（单批次全量）

计划: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-13-module-governance-plan.md`
设计: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-13-module-governance-design.md`
Gate 1: R1-R4 迭代后 R4 PASS，contested F008-R4/F009-R4 标 false-positive（见 `2026-04-13-module-governance-plan-review.md`）

---

## 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | P0 基线调研产出 baseline.md（每条冲突 3 类证据） | commit ced5ea7, 13 条发现（3 HIGH / 4 MED / 3 LOW / 3 结构观察），机械扫描 + 代码 Read 交叉验证 | ✅ 一致 | 4 批依次完成；未读段落按 plan 「未读（跳过）清单」明列 |
| T2 | MODULE-template.md | commit b7d1a66, 完整 frontmatter 全字段 + 正文 5 段骨架 + 字段说明表 + 填写指引 + 禁止列表 | ✅ 一致 | 参考 grading/pipeline 示例段指向 Task 4/5 |
| T3 | 聚合脚本 + 5 tests（含 CLI 入口测试） | commit 6c3519d, 6 tests 全 PASS（1 CLI 入口 + 5 单元+端到端） | 🔀 改进 | 比计划多 1 test（CLI 入口实测时发现应加 test_cli_entry_produces_outputs），符合 F004 意图 |
| T4 | grading MODULE.md 基于实情填写 | commit 946b345, frontmatter 字段全填（6 表 + /api/v1/grading + 3 service class），事件 `[]`（实读无发出点） | ✅ 一致 | 明示"不做什么"含选择题判分由 scan 完成、人工阅卷由 marking |
| T5 | pipeline MODULE.md + 聚合产物首版 | commit 3088c63, owns_tables=[]（无表），depends_on.modules=8 个模块，aggregate 脚本生成 modules.yaml/dependency-graph.md/debt-report.md | ✅ 一致 | aggregate 退出码 0，无冲突，debt=18（剩余未做 MODULE.md 的模块数）|
| T6 | module_governance_guard.py + 15 tests | `~/.claude` commit 5c66b45 (hook) + edu-cloud commit 34190d6 (22 tests) | 🔀 改进 | 比计划多 7 tests（F008/F009 额外反退化），所有 F001-F009 修正覆盖 |
| T7 | 接入 commit_guards.CHECKS + 手动 3 场景验证 | `~/.claude` commit 50d3997（CHECKS 追加 + CLAUDE.md 事实更新），3 场景 Python 脚本验证全通过，日志 `docs/plans/.module-governance-hook-verify.log` | ✅ 一致 | CHECKS 顺序: doc/logging/refactor/**module_governance** |

> Task 8（CLAUDE.md 回写 + design.md `[实现完成]` 标记）按 F005 前置条件延后到 Gate 2 PASS 后执行，本次不做。

---

## 预审自检（送审前必填）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| Diff 行数解析（T6） | `tests/governance/test_module_governance_guard.py::test_parse_diff_line_counts_basic/multi_file/ignores_headers` | `pytest tests/governance/test_module_governance_guard.py::test_parse_diff_line_counts_basic tests/governance/test_module_governance_guard.py::test_parse_diff_line_counts_multi_file tests/governance/test_module_governance_guard.py::test_parse_diff_line_counts_ignores_headers -v` | 3 passed in 0.05s | 删除 `parse_diff_line_counts` 中 `if line.startswith("+++")...continue` → `test_parse_diff_line_counts_ignores_headers` FAIL（+++ 头行计入 added） |
| 新模块判定 F002+F007+F008（T6） | `tests/governance/test_module_governance_guard.py::test_new_module_without_module_md_blocks/_with_valid_module_md_staged_passes/_module_md_in_workspace_but_not_staged_still_blocks/_with_invalid_module_md_missing_field_blocks/_with_invalid_yaml_blocks/_legacy_module_without_module_md_not_blocked_by_new_check` | `pytest tests/governance/test_module_governance_guard.py -k "new_module or legacy_module" -v` | 6 passed | 删除 `_dir_exists_in_head` 判定 → `test_legacy_module_without_module_md_not_blocked_by_new_check` FAIL（存量模块被误拦 block）|
| owns 冲突检测（T6） | `tests/governance/test_module_governance_guard.py::test_duplicate_owns_tables_blocks/_same_module_duplicate_owns_not_conflict` | `pytest tests/governance/test_module_governance_guard.py::test_duplicate_owns_tables_blocks tests/governance/test_module_governance_guard.py::test_same_module_duplicate_owns_not_conflict -v` | 2 passed | 删除 `prev != name` 判定 → `test_same_module_duplicate_owns_not_conflict` FAIL（同模块内部重复被误报为跨模块冲突）|
| 存量触碰 ≥50 行 ask（T6） | `tests/governance/test_module_governance_guard.py::test_large_modification_without_module_md_asks/_small_modification_does_not_ask` | `pytest tests/governance/test_module_governance_guard.py::test_large_modification_without_module_md_asks tests/governance/test_module_governance_guard.py::test_small_modification_does_not_ask -v` | 2 passed | 将阈值 `LARGE_MODIFY_THRESHOLD` 改为 1 → `test_small_modification_does_not_ask` FAIL（<50 行也被 ask）|
| Hook 入口级 F001+F004+F006（T6） | `tests/governance/test_module_governance_guard.py::test_hook_entry_*` | `pytest tests/governance/test_module_governance_guard.py -k hook_entry -v` | 4 passed | 把 `check` 签名改为只接收 `data` → 测试集体 TypeError |
| F008 frontmatter 校验（T6） | `tests/governance/test_module_governance_guard.py::test_new_module_with_invalid_module_md_missing_field_blocks/_with_invalid_yaml_blocks/_check_entry_blocks_on_invalid_existing_module_md` | `pytest tests/governance/test_module_governance_guard.py -k invalid -v` | 3 passed | 在 `check_new_module` 注释掉 `agg.parse_module_md` 调用 → `test_new_module_with_invalid_module_md_missing_field_blocks` FAIL（非法 frontmatter 被放行）|
| F009 派生产物同步（T6） | `tests/governance/test_module_governance_guard.py::test_derived_products_stale_blocks/_fresh_passes/_check_skipped_when_no_governance_dir` | `pytest tests/governance/test_module_governance_guard.py -k derived -v` | 3 passed | 把 `if fresh != ondisk` 改为 `if False` → `test_derived_products_stale_blocks` FAIL（陈旧产物未拦）|
| Kill switch（T6） | `tests/governance/test_module_governance_guard.py::test_kill_switch_disables_entry` | `pytest tests/governance/test_module_governance_guard.py::test_kill_switch_disables_entry -v` | 1 passed | 删除 `_kill_switch` 检查 → FAIL（env=1 仍 block）|
| 聚合 frontmatter 解析（T3） | `tests/governance/test_aggregate_modules.py::test_parse_module_md_returns_frontmatter/_missing_required_field_raises` | `pytest tests/governance/test_aggregate_modules.py::test_parse_module_md_returns_frontmatter tests/governance/test_aggregate_modules.py::test_parse_module_md_missing_required_field_raises -v` | 2 passed | 把 `REQUIRED_FIELDS` 改为 `[]` → `test_parse_module_md_missing_required_field_raises` FAIL |
| 跨模块 owns 冲突检测（T3） | `tests/governance/test_aggregate_modules.py::test_detect_conflicts_finds_duplicate_owns_tables/_routes` | `pytest tests/governance/test_aggregate_modules.py::test_detect_conflicts_finds_duplicate_owns_tables tests/governance/test_aggregate_modules.py::test_detect_conflicts_finds_duplicate_owns_routes -v` | 2 passed | 把 `route_owner` dict 改为只检测 table → routes test FAIL |
| 端到端聚合（T3） | `tests/governance/test_aggregate_modules.py::test_aggregate_all_writes_yaml_and_debt_report` | `pytest tests/governance/test_aggregate_modules.py::test_aggregate_all_writes_yaml_and_debt_report -v` | 1 passed | 删除 `_render_debt` 中"缺 MODULE.md 子目录"追加 → `assert "beta" in debt` FAIL |
| CLI 入口（T3 F004） | `tests/governance/test_aggregate_modules.py::test_cli_entry_produces_outputs` | `pytest tests/governance/test_aggregate_modules.py::test_cli_entry_produces_outputs -v` | 1 passed | 删除 `_main()` 函数或 `if __name__ == "__main__"` block → FAIL（exit code 非 0 / stdout 无 "Aggregated"）|

**汇总验证命令**:
```
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/governance/ -v
```
**实际输出**: `28 passed in 4.42s`

---

## 验证清单自检（plan 各 Task 审查清单）

### Task 1 审查清单
- ✅ 每条冲突都有 3 类证据（原文 file:line / 调用方 grep / 历史或 git log 痕迹）——baseline.md 每条 #1-#10 均含 file:line + 调用方列表
- ✅ 判定必须三选一（真冲突/职责互补/历史债务/结构观察 4 类，分类明确）
- ✅ 禁止未读下判定——调研覆盖 21 modules + services/ + ai/tools/ + api/
- ✅ 禁止 triage 推给用户——Executor 已做分类，用户仅 approve/reject/defer

### Task 2 审查清单
- ✅ frontmatter 所有字段有说明（字段说明表 16 行）
- ✅ 「禁止」段覆盖多版本并存风险点（含 `owns_*` 重复、"XX 相关功能"空话、预设边界）
- ✅ 禁止 TBD / 参考 xxx（本模板自洽）

### Task 3 审查清单
- ✅ 所有测试在 fresh repo clone 后可独立跑通（测试用 `sys.path.insert` 无外部依赖）
- ✅ ModuleGovernanceError 消息含文件路径（每个 raise 均 `f"{md_path}: ..."`）
- ✅ 禁止 eval/exec 解析 YAML（使用 `yaml.safe_load`）
- ✅ 禁止静默吞异常（`yaml.YAMLError` 被捕获后 `raise ModuleGovernanceError ... from e`）

### Task 4 审查清单
- ✅ frontmatter `owns_tables` 与 `__tablename__` 一致（`rubrics/grading_tasks/ai_grading_results/teacher_reviews/grading_assignments/grading_quality_checks` 均对应 `grading/models.py`）
- ✅ `owns_routes` 与 FastAPI router 实际 prefix 一致（3 个 router 均用 `prefix="/api/v1/grading"`）
- ✅ `depends_on.modules` 覆盖所有 `from edu_cloud.modules.X import`（exam + scan，来源 grading/router.py）
- ✅ 禁止在「职责」段写"与阅卷相关的功能"空话（职责写"AI 阅卷全链路：为主观题..."）

### Task 5 审查清单
- ✅ grading 和 pipeline 的 owns_* 不重叠（aggregate 输出 conflicts=0）
- ✅ grading.depends_on.modules 与 pipeline.depends_on.modules 按真实依赖（pipeline 依赖 grading，grading 不反向依赖 pipeline）
- ✅ 禁止把 grading 的表"窃为己有"（pipeline owns_tables=[]，确实无表）

### Task 6 审查清单
- ✅ staged_info 契约与 `commit_guards.py:99` 完全一致（`{"files", "diff"}`）
- ✅ 行数统计来自 `parse_diff_line_counts(diff)`（非 dispatcher 预聚合）
- ✅ check 签名 `(data, session_state, staged_info=None) -> dict | None`
- ✅ 返回 dict 而非自定义 dataclass
- ✅ 新模块 MODULE.md 合规只认 staged 证据（F007）
- ✅ 新旧判定用 `git ls-tree HEAD`（F002）
- ✅ staged MODULE.md 必须通过 parse_module_md（F008）
- ✅ 存量 MODULE.md 解析失败 → _LoaderError → block（F008）
- ✅ 派生产物过期 → check_derived_products_fresh block（F009）
- ✅ KILL_SWITCH 在 check() 入口统一生效
- ✅ 禁止 sys.exit(1)（hook 用返回 dict）
- ✅ 禁止用"MODULE.md 在工作区"兜底（F007）
- ✅ 禁止假设 staged_info 含 paths/stats 字段（F006）
- ✅ 禁止静默吞 parse/import 异常（F008）
- ✅ 禁止只在手动流程更新派生产物（F009）

### Task 7 审查清单
- ✅ `module_governance_guard.check` 签名与现有子 guard 完全一致
- ✅ CHECKS 列表追加（非重构调度函数）
- ✅ 非 edu-cloud repo 返回 None（手动场景 3 验证）
- ✅ 禁止引入 `run_all` / `additionalContext` / 自定义聚合函数
- ✅ 禁止在 commit_guards.py 主文件写领域逻辑（commit_guards.py diff 仅 2 行追加）

---

## 根因分析
（本次为新增基础设施任务，非 bug fix，跳过）

---

## 自查（四要素格式）

### 新增文件的边界 case
- 构造输入: tmp_path 下无 modules/ 目录 + 调用 `_load_all_module_frontmatters(repo)`
- 运行命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/governance/test_module_governance_guard.py -v`
- 实际输出:
  ```
  22 passed in 3.53s
  ```
- 结论: 空目录不抛错（函数顶部 `if not modules_dir.exists(): return []`），已覆盖

### 状态变量/锁的异常路径
- 构造输入: tmp_path 下 legacy 模块 MODULE.md 文件非法（缺字段）+ 调用 `check(data, ss, staged_info)`
- 运行命令: `pytest tests/governance/test_module_governance_guard.py::test_check_entry_blocks_on_invalid_existing_module_md -v`
- 实际输出:
  ```
  1 passed
  ```
- 结论: `_LoaderError` 被 check() 捕获转为 block，不让解析异常直接抛穿 hook 边界

### 字符串匹配/条件判断的假阴性
- 构造输入: `modules/{name}/MODULE.md` 路径末尾匹配（Windows 反斜杠 / Unix 斜杠混用）
- 运行命令: `pytest tests/governance/test_module_governance_guard.py::test_new_module_with_valid_module_md_staged_passes -v` + `test_hook_entry_allows_non_edu_cloud_repo`
- 实际输出:
  ```
  2 passed
  ```
- 结论: `_module_name_from_path` 用 `Path.as_posix().split("/")`，`check_new_module` 判断 MODULE.md 用 `.replace("\\", "/").endswith(...)` 显式标准化，Windows/Unix 均覆盖

---

## 语义回归自检
semantic_risk = **False** —— 本次为纯新增治理基础设施（新 hook / 新 MODULE.md / 新聚合脚本 / 新模板），未修改任何已有业务逻辑或运行时行为：
- `commit_guards.py` 仅在 CHECKS 追加一项，新子 guard 签名与现有 3 个一致，边界隔离（`_is_edu_cloud` 门控，非 edu-cloud repo 返回 None）
- 不改 fallback/retry/state-machine/阈值/选择策略/时序
- 不引入新模型或 LLM 选择
无需 oracle 校验。

---

## 本次 Commits 清单（按时间顺序）

### edu-cloud 仓库
| SHA | 描述 |
|-----|------|
| ced5ea7 | governance: P0 基线调研完成 — edu-cloud 模块债务清单 |
| b7d1a66 | governance: P1-1 添加 MODULE.md 模板 |
| 6c3519d | governance: P1-2 聚合脚本 aggregate_modules.py + 6 tests |
| 946b345 | governance: P2-1 grading 模块 MODULE.md |
| 3088c63 | governance: P2-2 pipeline 模块 MODULE.md + 聚合产物首版 |
| 34190d6 | governance: P3-1 module_governance_guard 测试（22 tests 含 F001-F009 反退化）|

### ~/.claude 仓库
| SHA | 描述 |
|-----|------|
| 5c66b45 | hook: module_governance_guard 核心实现（P3 Task 6 — edu-cloud 专用）|
| 50d3997 | sync(.claude): module_governance_guard 接入 commit_guards CHECKS（edu-cloud 专用）|

---

## 下一步

使用 **codex-review skill (code review 模式)** 对本批次进行 Gate 2 Code Review。

评审对象:
- **edu-cloud**: `docs/governance/edu-cloud-module-baseline-2026-04-13.md`, `MODULE-template.md`, `scripts/governance/aggregate_modules.py`, `src/edu_cloud/modules/{grading,pipeline}/MODULE.md`, `tests/governance/test_{aggregate_modules,module_governance_guard}.py`
- **~/.claude**: `hooks/module_governance_guard.py`, `hooks/commit_guards.py`（仅 CHECKS 追加）, `CLAUDE.md`（仅 L25 附近的事实性说明追加）

审查关注点:
1. hook 契约/边界是否与其他 3 个子 guard 一致，非 edu-cloud 仓库不误伤
2. F001-F009 反退化是否全部覆盖（GPT R4 曾误判 F008/F009 为 FAIL，本次是 Gate 2 阶段真正复核代码存在性）
3. baseline.md 的 13 条清单证据充分性
4. 聚合脚本的 YAML 解析安全性（禁止 eval / yaml.unsafe_load）
5. MODULE.md 模板是否遗漏关键字段或违反文档字段校验矩阵
