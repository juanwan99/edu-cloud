<!-- pre-takeover: archived for history, not active spec -->
[edu-cloud] GPT Reviewer | 2026-04-13 12:28:07

## 审查报告: Batch 1 (T2-T6) — Round 1

**结论: FAIL**

- 代码范围: `1c3c1a2..d0ed76e`（T2-T6）
- 交接单: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch1.md`
- 原始输出: `docs/plans/.codex-code-review-kg-phase1-b1-raw.log`
- 原始 SHA256: `02ad53d091f2d277a55264be99bfddbb89f4ce1cf87b8e7aa4e27c43604a15df`

### 第一段：测试充分性

- plan §Contract Pack INV-005 要求 importance_score **单调随输入分量递增**，现有测试只测 3 个宽区间断言——未验证单调性。GPT 构造 mutant（删除 depth 分量）复跑原测试，3 条断言全部仍 true → 强确认 F002。
- test_compute_all_stats_real 用 `if photo:` 包裹核心断言 + 用 `>= 100` 代替精确 count——漏写/错写光合作用记录时测试仍通过 → F003。
- bug fix 无回归测试（本 batch 无 bug fix，N/A）。
- Contract Pack verification 映射对 INV-002/INV-003/CE-003 基本准确；INV-005 不成立。

### 第二段：行为正确性

**变更理解（GPT 独立复述）：**

本 Batch 把 `knowledge.db` 中的 L1 concept 关联数据（考频 / 难度 / 覆盖率 / 教材章节 / MCU 规划权重 / 前置链深度）投影到 edu-cloud PG 的 `concept_stats` 表。入口有三类：(1) 服务层 `compute_exam_frequency / compute_avg_difficulty / compute_exam_coverage / compute_textbook_chapters / compute_prerequisite_depth` — 纯函数，各算一项指标；(2) 编排函数 `compute_all_stats` — UPSERT 写入全量 L1 节点；(3) 生命周期钩子 — `sync_knowledge_on_startup` 在 commit 后 best-effort 触发 `compute_all_stats`，异常日志后吞掉不阻塞 sync。MCU 导入脚本通过字符 n-gram 余弦匹配 MCU CP → kb concept（阈值 0.5），幂等写入 `planning_weight`。

**对抗性审查：**

- **边界输入构造（每个函数 3 类）**：空集合已覆盖（`concept_items.get(cid, set())`、evidence_ids_json NULL 路径）；单元素已覆盖（test_prerequisite_depth 的 D 孤立节点）；溢出/极值部分缺失（importance_score 未测 percentile=1.0 + depth=100 + planning_weight 极值的同时作用）。
- **异常路径追踪**：sync_service 的 try/except 被 GPT 独立复现证实生效（monkeypatch 失败 → synced 仍返回）；但 **skipped 分支完全绕过 try/except**，这是 F001 的核心发现。
- **假阴性检测（mutant testing）**：GPT 对 `compute_importance_score` 做 mutant 测试——删除 `0.1 * depth_component` 分量后，现有 3 条断言全部仍 true。这**直接证伪** handoff 对 INV-005 的 verification 映射（F002）。
- **数据事实核验**：GPT 独立连接 knowledge.db 验证 `assessment_items` 无 difficulty 列（列数 15，列名已列清单）、`q_matrix.transfer_band` 分布（far=6182 / mid=5992 / near=2698）、`study_units.source_concept_ids` 字段确实存在。T2 🔀 的代理方案可接受，不记 behavior_change。
- **MCU 映射碰撞检测**：GPT 独立复跑 dry-run 发现 3 个 kb concept 被多个 MCU CP 命中（MEIOSIS/TRANSCRIPTION/REFLEX），当前实现"后写覆盖前写"未取最高相似度——但进一步核验带 weight 的映射集合后碰撞消失（weight 只覆盖部分 MCU CP），**未上升为 finding**。

### 第三段：未测试风险

- `skipped` 分支下 stats 自愈未测试 → F001 触及生产升级路径
- compute_all_stats 对 `study_unit_id / estimated_minutes / textbook_chapters` 的完整性未断言 → F003
- importance_score 的分量贡献关系未锁定 → F002

### 发现清单

<!-- anchor: finding-list -->

#### F001 — sync skipped 分支不补算 stats

- **Severity:** HIGH
- **Category:** code-bug
- **Type:** defect_fix
- **Status:** verified
- **Before-behavior:** 已完成图谱/DA 同步的数据库第二次启动时，`sync_knowledge_on_startup` 进入 `skipped` 分支并直接 return，不触发 `compute_all_stats`。首次 stats 计算失败后下次启动也不恢复。
- **After-behavior:** 无论 skipped 还是 synced 路径，启动时都必须保证 `concept_stats` 非空（或可自愈）。建议在 skipped 分支检测 `ConceptStats` 表行数为 0 → 补算。
- **Evidence:**
  - `src/edu_cloud/modules/knowledge_tree/sync_service.py:210-213`：`if node_count > 0 and edge_count > 0 and da_count > 0 and kp_count > 0: return {"status": "skipped"}`（提前返回）
  - `src/edu_cloud/modules/knowledge_tree/sync_service.py:229-242`：stats 触发 try/except 位于 skipped return 之后，不会被执行
  - `tests/test_knowledge_tree/test_sync_startup.py:73-77` test_sync_idempotent 只断言 `status == "skipped"`，未验证 stats 自愈
  - GPT 独立复现：首次 sync `concept_stats=108` → 清空后再启动 `skipped` → `concept_stats=0`
- **Impact:** 生产环境升级到这批代码后大概率永远无 `concept_stats`（图谱和 DA 通常在 Phase 0 时已 synced）。T7+ Graph API v3 依赖 stats 将返回空字段。
- **Inv-conflict:** possible（若"启动时保障 stats"视为隐含 Contract 则 direct）
- **Repair hypothesis:** 将 stats 初始化从"仅 sync 后触发"改为"startup 保障"。具体：①skipped 分支也调用 `compute_all_stats`，或 ②先检查 `ConceptStats` count 为 0 时触发。同时补加 `test_sync_skipped_branch_computes_stats_when_empty` 测试。

#### F002 — test_importance_score_normalization 无法检测 depth 分量删除

- **Severity:** MED
- **Category:** test-gap
- **Type:** defect_fix
- **Status:** verified
- **Before-behavior:** 当前测试只做 3 个宽区间断言：高权重∈[7,10]、全零∈[0,3]、中间值∈(0,10)。
- **After-behavior:** 对 INV-005 要求的"单调随各输入分量递增"必须有 pairwise 单调性测试。
- **Evidence:**
  - `tests/test_knowledge_tree/test_stats_service.py:160-189`：3 个断言全部为宽区间
  - GPT mutant 测试：删除 `0.1 * depth_component` 分量后，`score_high=8.5`（仍 ≥7）、`score_low=2.5`（仍 ≤3）、`score_no_mcu=4.5`（仍 ∈(0,10)）——3 条断言都通过
  - `plan.md` Contract Pack §INV-005 要求"单调随输入分量递增"
- **Impact:** 实现偶然丢失某个分量（如 depth / error_prone / transfer_value）时测试无法捕获，回归风险高。
- **Repair hypothesis:** 增加 4 个 pairwise monotonic 测试，分别固定其他分量，单独提升 `exam_frequency_percentile` / `prerequisite_depth` / `error_prone` / `transfer_value`，断言 `score_after > score_before`。

#### F003 — test_compute_all_stats_real 断言过弱

- **Severity:** MED
- **Category:** test-gap
- **Type:** defect_fix
- **Status:** verified
- **Before-behavior:** 用 `total >= 100` 替代精确 count；对光合作用记录用 `if photo: ...` 包裹，缺失也通过。
- **After-behavior:** 该测试应精确断言"108 个 L1 concept 都有 stats" + 关键派生字段（`study_unit_id / estimated_minutes / textbook_chapters / importance_score`）真的被写入。
- **Evidence:**
  - `tests/test_knowledge_tree/test_stats_service.py:206`：`assert total >= 100` 弱断言
  - `tests/test_knowledge_tree/test_stats_service.py:215`：`if photo:` 让核心断言成为可选
  - `plan.md:1599` 审查清单显式要求 StudyUnit 映射从 knowledge.db 加载
- **Impact:** 少写 concept / 漏写指定 concept / `study_unit_id` 失效 / 派生字段未写入——都不会被这条主回归测试抓到。
- **Repair hypothesis:** 去掉 `if photo:`；断言 `total == <L1 节点 count>`（从 sync 后 ConceptGraphNode 读取）；对至少 1 个已知 concept（BIO_SR_CP_M1_PHOTOSYNTHESIS）同时断言 `study_unit_id is not None / estimated_minutes > 0 / len(textbook_chapters) > 0 / importance_score > 0`。

### PASS/FAIL 判定

按 `~/.claude/rules-t3/review-templates.md` <!-- anchor: pass-fail --> 规则：
- F001 (HIGH code-bug) 未修复 → **FAIL**
- F002 (MED test-gap) 未修复 → **FAIL**
- F003 (MED test-gap) 未修复 → **FAIL**

**结论：FAIL**。Executor 进入 Round 2 修复所有 finding。

### 处置计划（Executor Round 2）

| Finding | 修复内容 | 影响文件 |
|---------|---------|---------|
| F001 | sync_service.py skipped 分支检测 ConceptStats 空时补算；新增 test_sync_skipped_branch_computes_stats_when_empty | src/edu_cloud/modules/knowledge_tree/sync_service.py、tests/test_knowledge_tree/test_sync_startup.py |
| F002 | 新增 4 个 pairwise monotonic 测试 | tests/test_knowledge_tree/test_stats_service.py |
| F003 | 重写 test_compute_all_stats_real：精确 count + 关键字段断言 | tests/test_knowledge_tree/test_stats_service.py |

所有 finding 均为 defect_fix 类型，可批量处置，无 behavior_change 需用户单独批准。

---

## Round 2 — PASS

时间: 2026-04-13 12:42:09
R2 fix commit: `bcb1971`
原始输出: `docs/plans/.codex-code-review-kg-phase1-b1-r2-raw.log`
原始 SHA256: `8551571ebdf502db8854c5ca7e1f2088ef7d5516f722dd367daa65657f42a11f`

### R1 Finding 终态

| Finding | 终态 | GPT 独立验证证据 |
|---------|------|------------------|
| F001 | **resolved-correct** | 真实场景复现：首启 `concept_stats=108` → 手工清空 → 再启 `skipped` 仍恢复到 108；mutant（去掉 `_ensure_concept_stats` 调用）新测试 call_log 从 2 降为 1，测试失败。|
| F002 | **resolved-correct** | 单分量删除矩阵验证：删 exam / depth / error_prone / transfer_value 任一分量，对应的独立测试失败，其余 3 个仍通过——覆盖是独立的。|
| F003 | **resolved-correct** | 对抗验证：删任一行 → `stats=107, concepts=108` assertion 失败；删光合作用 → `scalar_one()` `NoResultFound`；null study_unit / clear chapters → 对应字段断言失败。|

### R2 新增 Finding

无。GPT 未在 R2 修复或既有 diff 中发现新 HIGH/MED code-bug 或 test-gap；无 behavior_change。

### 剩余低风险（不阻断 PASS）

- `_ensure_concept_stats()` 只自愈"空表"，不自愈"非空但不完整"的损坏状态。当前 compute_all_stats 单次提交，缺少现实触发面；GPT 明确标"不升格为 finding"。
- 未重跑全仓 1800+ 测试，基于改动范围不影响 Gate 判定。

### PASS 判定

按 `~/.claude/rules-t3/review-templates.md` <!-- anchor: pass-fail --> 规则：
- R1 3 个 finding 全部 resolved-correct
- R2 无新增 HIGH/MED code-bug / test-gap
- 无 behavior_change 待确认

**结论：Round 2 PASS → Batch 1 Gate 2 通过。**

Batch 1 交付完成。下一步（非本报告范围）：下个会话执行 Batch 2 (T7-T8 Graph API v3 + 高考真题/统计概览 API)，继续 codex-review Gate 2。
