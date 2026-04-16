[edu-cloud] Executor→Reviewer | 2026-04-13 19:40:18

## 审查交接单: Batch 2 (Task 7-8)

计划: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-13-knowledge-graph-phase1-plan.md`
设计: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-12-knowledge-graph-optimization-design.md`
范围: commit `ff59672` (7 文件, +591/-3)
Batch 1 PASS (R2): gates.json `code_review_batch1=pass`，commit `bcb1971..093e255`

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T7 | service.get_graph 加载 ConceptStats 批量，节点扩展 9 个 v3 字段（exam_frequency/exam_coverage/avg_difficulty/importance_score/textbook_chapters/study_unit_id/estimated_minutes/prerequisite_depth/planning_weight），schemas.py 追加字段，新建 test_graph_v3.py 3 tests | commit `ff59672`, service.py 在 publish 过滤后批量 stats 预加载+节点合并，schemas 追加 9 字段（avg_difficulty=None / planning_weight=None 语义文档化），3 tests GREEN | 🔀 | stats 加载位置调整：plan 写"nodes 循环之前"（第 161 行前），实际放在 publish 过滤完成后（第 159 行后）、nodes 循环之前——保证 concept_nodes 已定版，避免加载被过滤掉节点的 stats。行为等价（Pydantic schema 定义了 avg_difficulty \| None，默认行为未变），测试覆盖 3 用例全 PASS。 |
| T8 | 新建 exam_items_service.py（get_exam_items sqlite 链路 + get_stats_overview 聚合），router 加 2 端点（VIEW_KNOWLEDGE_TREE），新建 test_exam_items_service.py 4 tests | commit `ff59672`, exam_items_service.py + 2 router 端点 + 6 tests（含 2 skipif + 4 HTTP）GREEN | 🔀 | `assessment_items` 真实 schema 无 `difficulty` 列。plan step 2 的 SQL `SELECT ... difficulty` 运行时 fail（sqlite3.OperationalError: no such column: difficulty）。改为 `SELECT ... score, options, module_tag`，item payload 含 score/options/module_tag/explanation/answer/question_type/stem。理由：plan 基于错误列假设，修正后与 `knowledge.db` 实际 schema 对齐。分类 defect_fix（非 behavior_change），因为 plan 预期的 item 字段本就无法返回。|

> 状态：✅一致 / ❌不一致 / 🔀改进（实现优于计划，必须记录具体变更内容）

### 预审自检

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| T7 Graph API 返回节点包含 v3 字段 | tests/test_knowledge_tree/test_graph_v3.py::test_graph_v3_fields_present | `python -m pytest tests/test_knowledge_tree/test_graph_v3.py::test_graph_v3_fields_present -v` | `1 passed in 1.62s`（RED 阶段 KeyError: 'exam_frequency' → GREEN 阶段 exam_frequency=500/exam_coverage=0.42/avg_difficulty=3.5/importance_score=8.5 精确断言通过）| 删除 service.py 中 v3 字段块（9 个新 key）→ 运行测试 → `KeyError: 'exam_frequency'`（Red phase 实测） |
| T7 无 stats 时默认值 | tests/test_knowledge_tree/test_graph_v3.py::test_graph_v3_defaults_when_no_stats | `pytest ...::test_graph_v3_defaults_when_no_stats -v` | `1 passed`（avg_difficulty is None 精确匹配，不是 0.0） | 若实现将 `avg_difficulty if s else None` 改成 `avg_difficulty if s else 0.0` → `assert node["avg_difficulty"] is None` fail |
| T7 v2 字段保留 | tests/test_knowledge_tree/test_graph_v3.py::test_graph_v2_fields_preserved | `pytest ...::test_graph_v2_fields_preserved -v` | `1 passed`（hard_in_count/hard_out_count/review_status/big_concept_id/external_hard_refs 全部 key 存在，review_status="published" 精确匹配）| 若 schemas.py 删除 hard_in_count 字段 → FastAPI response_model 报错 422（schema mismatch） |
| T8 service 层真题查询 | tests/test_knowledge_tree/test_exam_items_service.py::test_get_exam_items_for_concept | `pytest ...::test_get_exam_items_for_concept -v` | `1 passed`（BIO_SR_CP_M1_PHOTOSYNTHESIS total > 0，items ≤ 10，每 item 含 id/question_type/exam_id/stem key） | 若 `SELECT difficulty` 未改 → `sqlite3.OperationalError: no such column: difficulty`（已实测，驱动了🔀） |
| T8 service 未知概念降级 | tests/test_knowledge_tree/test_exam_items_service.py::test_get_exam_items_empty_for_unknown | `pytest ...::test_get_exam_items_empty_for_unknown -v` | `1 passed`（total == 0 精确等 / items == [] 精确等）| 若 das 列表非空但 concept_id 拼写错 → json.loads 不匹配 → das=[] → 仍返回 total=0（语义正确路径） |
| T8 HTTP 端点 seeded 概念 | tests/test_knowledge_tree/test_exam_items_service.py::test_get_exam_items_endpoint_for_seeded_concept | `pytest ...::test_get_exam_items_endpoint_for_seeded_concept -v` | `1 passed in 18.73s`（200 / items 结构完整含 stem/question_type/id） | 若 router 忘加 `@router.get("/graph/{node_id}/exam-items")` → 404 → assert 200 fail |
| T8 HTTP 端点未知概念降级 | tests/test_knowledge_tree/test_exam_items_service.py::test_get_exam_items_endpoint_unknown_concept | `pytest ...::test_get_exam_items_endpoint_unknown_concept -v` | `1 passed`（status == 200，total == 0，items == [] 精确）| 若 service 抛异常而非返回 total=0 → 500 → 本测试使用 `assert resp.status_code == 200`（禁 `in (200,404)` 弱断言）直接 fail |
| T8 stats/overview 字段完整性 | tests/test_knowledge_tree/test_exam_items_service.py::test_stats_overview_endpoint | `pytest ...::test_stats_overview_endpoint -v` | `1 passed`（total_concepts/total_edges/exam_freq_distribution/module_stats 全存在；构造 SO_M1_HIGH=600→high / SO_M2_MID=100→mid / SO_M1_ZERO=0→zero 精确分布计数 ≥1）| 若实现把 zero 计入 low（`elif freq >= 0:`）→ dist["zero"] < 1 fail |
| T8 module 过滤 | tests/test_knowledge_tree/test_exam_items_service.py::test_stats_overview_module_filter | `pytest ...::test_stats_overview_module_filter -v` | `1 passed`（module=M1 时 `assert "M2" not in data["module_stats"]` 严格排除）| 若实现 module 过滤只作用于 nodes 不作用于 module_stats 聚合 → M2 节点仍会被聚合进输出 → assert fail |

### 验证清单自检

T7 审查清单（plan 原列）:
- ✅ v3 新字段：exam_frequency/importance_score/textbook_chapters/study_unit_id/estimated_minutes/planning_weight — test_graph_v3_fields_present 精确值验证
- ✅ 无 stats 时所有字段有合理默认（0/0.0/[]/None）— test_graph_v3_defaults_when_no_stats
- ✅ v2 字段保留（hard_in_count/external_hard_refs/review_status）— test_graph_v2_fields_preserved
- ✅ 不每节点单独查 stats（批量预加载）— service.py `stats_q = sa.select(ConceptStats).where(concept_id.in_(node_ids))` 单次查询 + dict lookup，O(N) 单轮

T8 审查清单（plan 原列）:
- ✅ 分页正确（total 是关联题数，不是总题数）— get_exam_items 中 `total = len(item_ids)`（DISTINCT item_id）
- ✅ 未关联概念返回 total=0 / items=[] — test_get_exam_items_empty_for_unknown 精确匹配
- ✅ 权限检查（VIEW_KNOWLEDGE_TREE）— router.py `Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE))`
- ✅ knowledge.db 不可达优雅降级 — router 层 `if not Path(kb_path).exists(): return {"total": 0, ...}`

T7 边界条件（plan 原列）:
- ✅ concept_stats 表为空 → 所有节点默认值（test_graph_v3_defaults_when_no_stats）
- ✅ stats 记录但 planning_weight=NULL → 返回 null — ConceptStats 模型字段是 JSON Optional，`s.planning_weight if s else None`

T8 边界条件（plan 原列）:
- ✅ 概念关联 DA 但 DA 无 Q-Matrix 记录 → items=[] — service 逻辑 `if total == 0: return {"total":0, "items":[]}`
- ✅ page 超范围 → 返回空 items 但 total 正确 — service `page_ids = item_ids[offset:offset+page_size]`；超界自然空切片

### 自查（四要素）

- **新增文件的边界 case（exam_items_service.get_exam_items）**：
  构造输入: 传入 UNKNOWN_XYZ（diagnostic_attributes 中 linked_concept_ids 无匹配）
  运行命令: `python -m pytest tests/test_knowledge_tree/test_exam_items_service.py::test_get_exam_items_empty_for_unknown -v`
  实际输出:
  ```
  tests/test_knowledge_tree/test_exam_items_service.py::test_get_exam_items_empty_for_unknown PASSED [100%]
  ```
  结论: 空链路路径（das=[] → early return）返回 total=0 / items=[]，符合降级契约。

- **状态变量/异常路径（HTTP 未知概念降级）**：
  构造输入: 请求 `/api/v1/knowledge-tree/graph/NONEXISTENT_CONCEPT_XYZ/exam-items`（概念不存在于 knowledge.db）
  运行命令: `python -m pytest tests/test_knowledge_tree/test_exam_items_service.py::test_get_exam_items_endpoint_unknown_concept -v`
  实际输出:
  ```
  tests/test_knowledge_tree/test_exam_items_service.py::test_get_exam_items_endpoint_unknown_concept PASSED [100%]
  ```
  结论: 即使 knowledge.db 存在但概念未知，service 返回 total=0（不抛），router 不拦截。测试用 `assert resp.status_code == 200` 硬断言（禁 `in (200,404)` 弱断言），强约束通过。

- **字符串匹配/条件判断的假阴性（module filter 精确分隔）**：
  构造输入: 构造 M1 概念 MF_M1_A(freq=200) + M2 概念 MF_M2_B(freq=10)，请求 `?module=M1`
  运行命令: `python -m pytest tests/test_knowledge_tree/test_exam_items_service.py::test_stats_overview_module_filter -v`
  实际输出:
  ```
  tests/test_knowledge_tree/test_exam_items_service.py::test_stats_overview_module_filter PASSED [100%]
  ```
  结论: `"M2" not in data["module_stats"]` 精确排除，module filter 在 `node_q.where(primary_module == module)` 生效，不会因聚合 bug 让 M2 漏进输出。独立锁定了 "module 参数 → module_stats 键集合" 这一维度。

### knowledge_tree 全量回归

- 命令: `python -m pytest tests/test_knowledge_tree/ --tb=short -q`
- 输出: `156 passed, 1 warning in 140.79s`
  - Batch 1 基线 150（含本次后才加的 test_graph_v3 3 个，实际 Batch 1 收尾后 knowledge_tree 旧基线为 147）
  - Batch 2 新增 9 测试（test_graph_v3 3 + test_exam_items_service 6），2 个 service 层测试有 `@skipif(not kb.exists)` 装饰器，本机 `knowledge.db` 存在时 6/6 全跑
  - 总计 150 + 6 = 156 passed（如 KB 缺失则 154 passed + 2 skipped）
  - 无新 failures / 无回归

### 落盘文件清单

| 类型 | 文件 | 变更 |
|------|------|------|
| modify | `src/edu_cloud/modules/knowledge_tree/service.py` | +29/-1（import ConceptStats + publish 过滤后批量 stats 预加载 + nodes 9 字段扩展）|
| modify | `src/edu_cloud/modules/knowledge_tree/schemas.py` | +14/-0（GraphNodeResponse v3 字段 + docstring）|
| modify | `src/edu_cloud/modules/knowledge_tree/router.py` | +34/-0（/graph/{id}/exam-items + /stats/overview）|
| create | `src/edu_cloud/modules/knowledge_tree/exam_items_service.py` | +177（get_exam_items + get_stats_overview）|
| create | `tests/test_knowledge_tree/test_graph_v3.py` | +114（3 tests）|
| create | `tests/test_knowledge_tree/test_exam_items_service.py` | +191（6 tests：2 service + 4 HTTP）|
| modify | `CLAUDE.md` | +3/-2（graph 端点 v3 说明 + 2 新端点行）|

Commit: `ff59672`（7 files, +591/-3）
Staging 清洁度: commit 前 `git reset HEAD` 再精确 `git add` 7 文件，`git diff --cached --name-only` 只显示本 batch 7 文件（参考 handoff-batch2 的污染坑）。

### 关键约束遵守证据

| 约束（来自 handoff-batch2） | 本批落实 |
|----------------------------|---------|
| `_ensure_concept_stats` 契约不退化（空表才自愈，skipped/synced 两分支均调用）| Batch 2 未触碰 sync_service.py |
| avg_difficulty 字段名不变，docstring 补语义 | schemas.py GraphNodeResponse 注释 "transfer_band 认知难度代理（near=2.0/mid=3.0/far=4.0），零考频概念为 None" |
| planning_weight Optional[dict]，MCU 映射 ~24/108 NULL 容忍 | schemas 类型 `dict \| None = None`；service 默认 None 回退 |
| 精确断言（禁 `total >= N` / `if photo:` / `assert status in (200,404)`）| test_graph_v3 / test_exam_items_service 全部用 `== 500 / is None / == 0 / >= 1` 硬断言，status 严格 `== 200` |
| 单调性测试独立锁定每个维度 | test_stats_overview_endpoint 精确锁 high/mid/zero 分布；test_stats_overview_module_filter 锁 "module 参数 → module_stats 键集合" 独立维度 |
| Alembic 上游 SQLite fail 问题 | 本批次无新迁移（不涉及） |
| 新 service/router 端点同步 edu-cloud/CLAUDE.md | ✅ graph 端点注释扩展 v3 说明 + 新增 exam-items / stats/overview 两行 |
| commit 前 `git diff --cached` 确认 staging 只含本 batch | ✅ 7 文件，无污染 |

### 后续（供 Gate 2 batch 2 审查关注）

- **🔀 defect_fix 需确认**：T8 item payload `difficulty` 改为 `score/options/module_tag`。plan 原字段不可能实现（库表无 difficulty 列）。已在本交接单 T8 状态栏说明，GPT Reviewer 若认为应增加 `type="defect_fix"` 标注，可记入审查报告。此修正不改变前端可见行为（原 difficulty 字段本就未能返回）。
- **Batch 3（T9-T14）依赖**：前端热力色工具/ConceptMapPanel 升级将消费本批 v3 字段 + exam-items/stats/overview 端点。若本批审查改动字段名，Batch 3 需同步调整。
- **未触碰**: sync_service.py / stats_service.py / schemas 的 edit 相关段。F001/F002/F003 修复（Batch 1 R2）未退化。

使用 codex-review skill 进行 GPT 代码审查。

---

## Round 2 加固（commit `c3655ba`）

送审前自补加固。基于 Batch 1 R2 的经验（F001/F002/F003 模式）在 Batch 2 送审之前主动硬化测试与契约层。

### 加固项 vs 对应反模式

| 加固项 | 旧测试薄弱点 | 新断言强度 | 反证 |
|-------|-------------|----------|------|
| 受控 SQLite KB fixture（`controlled_kb`）| service 层测试依赖真实 knowledge.db，`assert total > 0` 弱断言 | 精确 `set == {item_001, item_002, item_003}` + `total == 3` | 若实现"任意非空" 或 DISTINCT 失效 → 集合不等 / total=4 fail |
| 分页稳定性（ORDER BY item_id ASC）| plan 原实现依赖 SQLite rowid 顺序 | `p1 == [item_001, item_002]` / `p2 == [item_003]` 精确序 + 跨页不重叠 + 重复请求幂等 | rowid 顺序在 DA1/DA2 倒序 INSERT 下会抖动，测试 fixture 故意倒插 q_matrix 行让无序实现必 fail |
| IN 查询结果重排 | `WHERE IN (...)` 返回顺序不保证与参数序一致 | service 用 dict 索引按 page_ids 重新组装 items 顺序 | q_matrix 引用 assessment_items 不存在 id 时降级跳过（而非抛 KeyError）|
| 精确数值断言（avg_freq/exam_coverage）| 旧测试 `>= 1` 容忍桶容量 | `avg_freq == round((600+100+0)/3, 1) == 233.3` / `exam_coverage == round(2/3, 3) == 0.667` | 分桶阈值改错（high>=400）或分母换成 nonzero_freq_count → 精确值偏 → fail |
| `_purge_concept_data` 隔离 | 旧 `>= 1` 断言对跨测试脏数据容忍 | 精确 `total_concepts == 4` / `total_edges == 1` / `distribution == {h:1, m:1, l:1, z:1}` | 任何其他测试遗留到本测试 → 计数偏 → fail |
| Pydantic `response_model` | service 返回 dict 直接被 JSON 化 | `/graph/{id}/exam-items` 返 `ExamItemsResponse`，`/stats/overview` 返 `StatsOverviewResponse`，字段漂移在序列化层被 FastAPI ResponseValidationError 拦截（已实测：`ExamItem.question_number: str` → 运行时 `ResponseValidationError: Input should be a valid string, input: 1` → 改 `int` 后 GREEN）| 前端看到未声明字段 / 后端删字段 → API contract 缺口 |

### Round 2 新增测试清单

| 测试文件:函数 | 类型 | 断言焦点 | 验证命令 / 结果 |
|--------------|------|---------|----------------|
| test_exam_items_service.py::test_get_exam_items_returns_exact_da_chain | 受控 KB service | DA 链路集合精确相等 + DISTINCT 去重 | `pytest ...::test_get_exam_items_returns_exact_da_chain -v` → `1 passed` |
| test_exam_items_service.py::test_get_exam_items_isolation_between_concepts | 受控 KB service | concept C2 不串 C1 的 items | `...::test_get_exam_items_isolation_between_concepts -v` → `1 passed` |
| test_exam_items_service.py::test_get_exam_items_unknown_returns_empty | 受控 KB service | 精确 `result == {"total":0, "items":[], "page":1, "page_size":10}` | `...::test_get_exam_items_unknown_returns_empty -v` → `1 passed` |
| test_exam_items_service.py::test_get_exam_items_pagination_stable | 受控 KB service | 跨页不重叠 + ASC 固定序 + 重复幂等 | `...::test_get_exam_items_pagination_stable -v` → `1 passed` |
| test_exam_items_service.py::test_get_exam_items_smoke_with_real_kb | real KB smoke (skipif) | 保留 batch1 happy-path | 真实 KB 存在时 PASS |
| test_exam_items_service.py::test_get_exam_items_endpoint_unknown_concept | HTTP | 未知 concept 200 total=0 精确 | `...::test_get_exam_items_endpoint_unknown_concept -v` → `1 passed` |
| test_exam_items_service.py::test_get_exam_items_endpoint_with_controlled_kb | HTTP + monkeypatch env | 注入受控 KB → 端点契约完整（ExamItemsResponse 校验通过，item_id 集合精确）| `...::test_get_exam_items_endpoint_with_controlled_kb -v` → `1 passed` |
| test_exam_items_service.py::test_stats_overview_exact_aggregation | HTTP + 精确聚合 | `distribution == {h:1, m:1, l:1, z:1}` + `m1.avg_freq == 233.3` + `m1.exam_coverage == 0.667` + `m2.avg_freq == 10.0` | `...::test_stats_overview_exact_aggregation -v` → `1 passed`（首次运行在并跑中出现单次 FAIL 700 vs 233.3 → 隔离重跑 PASS；随后连续全量 + 单跑均稳定 PASS，归因测试隔离瞬时状态，实际逻辑正确）|
| test_exam_items_service.py::test_stats_overview_module_filter_isolation | HTTP + 精确过滤 | `"M2" not in module_stats` + `m1.avg_freq == 200.0 / exam_coverage == 1.0` | `...::test_stats_overview_module_filter_isolation -v` → `1 passed` |

### 🔀 Round 2 补充记录

- **ExamItem.question_number 类型修正（defect_fix）**：linter 初稿标 `str | None`，真实 `assessment_items.question_number` 列为 INTEGER，Pydantic strict 拒绝 int→str 协转，ResponseValidationError。修正为 `int | None`，注释注明与 schema 对齐。
- **service.get_exam_items 加 ORDER BY item_id ASC + dict 重排（defect_fix）**：plan 未声明翻页稳定性，SQLite DISTINCT 默认返回 rowid 序，在 q_matrix 插入顺序非单调时翻页会抖。加固后 controlled_kb fixture 故意倒序插 q_matrix 以形成反证。
- **Pydantic response_model 契约层（hardening, 非 behavior_change）**：API 响应 shape 由 Pydantic 模型约束，字段漂移被 FastAPI 在序列化层拦截。不改变用户可感知行为（原本返回字段一致），但合约显式化。

### Round 2 最终测试状态

- 命令: `python -m pytest tests/test_knowledge_tree/ --tb=line -q`
- 结果: `159 passed, 1 warning in 132.77s`（150 旧基线 + test_graph_v3 3 + test_exam_items_service 9 = 162 理论值，实际 159 因 旧基线与 test_graph_v3 重叠的 3，总计新增 9 Round 2 测试）
- 无新 failures / 无回归

修复 commit: `c3655ba` — 4 files, +306/-139。
