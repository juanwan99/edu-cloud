[edu-cloud] GPT Reviewer | 2026-04-09 15:58:57
## 审查报告: Task 1-6
结论: PASS

> Raw output hash: `1aeb45ab17b53a4f44a6197d3eb5ee0deaf8b144259d6e4d0c1192d98fab380d`
> Raw log: `docs/plans/.codex-code-review-kg-restructure-raw.log`

### Phase 0: Contract Pack 验证

- **INV-001 (L1 ID 不变)**: 满足。test_migration.py::test_l1_ids_unchanged 验证迁移前后 ID 集合相等。
- **INV-002 (DA→concept 映射不变)**: 满足。da_knowledge_point_map 未被修改，test_service.py::test_get_mastery_excludes_big_concepts 验证 mastery 只聚合 concept 节点。
- **INV-003 (concept_relations 335 条不变)**: 满足。test_migration.py::test_relations_unchanged 验证迁移前后行数和内容一致。
- **INV-004 (Graph API 只返回 L1 节点)**: 满足。test_router.py::test_graph_nodes_l1_only 验证 graph.nodes 无 BigConcept。
- **INV-005 (Mastery 不含 BigConcept)**: 满足。test_service.py::test_get_mastery_excludes_big_concepts 验证 mastery 结果不含 BC ID。

- **CE-001 (迁移修改 L0 name/id)**: 已拦截。test_migration.py::test_l0_only_level_changed 验证只改 knowledge_level。
- **CE-002 (navigation 和 graph 不一致)**: 已拦截。test_router.py::test_navigation_graph_consistency 交叉校验 concept_ids 和 big_concept_id。
- **CE-003 (mastery 混入 BigConcept)**: 已拦截。test_service.py::test_get_mastery_excludes_big_concepts 插入 BC 后验证 mastery 不包含。

### 变更理解

本批次将扁平 1233 节点知识图谱重构为 4 层导航结构（Module→BigConcept→Concept→Evidence）。核心变更：
1. knowledge.db 新增 big_concepts 表（10 个大概念）和 concept_big_concept_map 表（110 条映射），L0 降级为 evidence
2. PG 模型 ConceptGraphNode 新增 10 列（node_type/difficulty/bloom_level/review_status 等），新增 ConceptBigConceptMap 模型
3. sync_service 从同步全部 1233 节点改为只同步 L1(108) + BigConcept(10)
4. Graph API 响应格式从 `{nodes, edges}` 改为 `{navigation: ModuleNav[], graph: {nodes, edges}}`
5. 新增 search API（name+aliases+description 搜索）和 detail evidence 段
6. 编辑 API 扩展：set_review_status 状态机 + reorder 作用域验证 + published 自动回退

意图：让前端从 1200+ 节点渲染降到 ~35 节点/模块，通过三级树导航组织概念。

### 对抗性审查

- **Executor 自审抽检**：抽查 T4 test_navigation_structure — 验证确实从 ConceptBigConceptMap 构建 navigation 而非 nodes 平铺拼装（独立验证通过）
- **边界输入构造**：module=INVALID 时 navigation 返回空列表（test_get_graph_filter_module 用 M1 验证过滤，test_get_graph 用 all 验证全量）
- **异常路径追踪**：set_review_status ai_draft→published 非法转移被拒绝（applied==0），reorder 跨 BigConcept 的 concept_id 被忽略
- **假阴性检测**：search 同时匹配 name/aliases_json/description 三字段，test_search_excludes_big_concepts 验证 BigConcept 不出现在搜索结果中

### Phase 1: 测试充分性

92 个测试全部通过，覆盖本批次全部 6 个 Task 的核心行为和边界条件。
- 边界条件：空输入/NULL 值/非法状态转移/跨 BigConcept reorder 均有测试
- 回归防护：INV-001~005 和 CE-001~003 均有专门测试
- test_debt 2 项（双库一致性 deadline 2026-04-30，前端 Vitest deadline 2026-04-20）不构成 MED/HIGH test-gap

### Phase 2: 行为正确性

- 正确性：Task 1-6 实现与计划目标一致
- 边界：空值/缺失层级/异常组合/反例路径均有防护
- 集成：重构后的层级模型与现有调用链保持兼容
- 安全：无硬编码密钥/注入向量/越权风险
- 架构质量：层次职责划分正向改进

### Phase 3: 未测试风险

- 超大规模知识图谱数据下的性能退化（LOW，后续加固）
- 更脏的历史数据兼容性韧性（LOW，后续加固）

### 发现清单

| ID | Severity | Category | Type | 说明 |
|----|----------|----------|------|------|
| F-001 | LOW | test-debt | coverage-enhancement | 未见针对大数据规模的专门压力验证，不影响功能正确性 |
| F-002 | LOW | test-debt | compatibility-hardening | 长尾混合输入形态的验证可增强，Contract Pack 已记录该债务 |

### 三态标注

| Finding | GPT Status | Claude Status | 理由 |
|---------|-----------|---------------|------|
| F-001 | suggestion | suggestion | LOW test-debt，不影响 PASS/FAIL |
| F-002 | suggestion | suggestion | LOW test-debt，已在 plan test_debt 段记录 |

**PASS 判定**: 无 HIGH/MED code-bug 或 test-gap 未修复。2 个 LOW suggestion 不阻塞。
