[edu-cloud] Executor→Reviewer | 2026-04-09 15:39:40
## 审查交接单: Task 1-6
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-knowledge-graph-restructure-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | knowledge.db Schema 变更 + 迁移脚本 | commit 51f1e9d, big_concepts(10)+map(110)+L0→evidence(1103)+aliases/evidence_ids迁移+默认值 | ✅ | 预期11个BigConcept实际10个（1个空字符串被过滤，正确行为） |
| T2 | PG Models + Alembic Migration | commit 0aac796, ConceptGraphNode +10列 + ConceptBigConceptMap 模型 + Alembic migration a370e2771c6d | ✅ | |
| T3 | sync_service 适配 | commit a71b611, _read_knowledge_db 只读L1+BC+map, 携带difficulty/bloom/aliases/evidence/review | ✅ | |
| T4 | Graph API navigation+graph+mastery | commit 4bae0fa, GraphResponse={navigation,graph}, get_mastery 加 node_type='concept' 过滤 | ✅ | |
| T5 | Detail API + Search API + Evidence | commit 424f4b7, detail_service 追加 evidence 段, 新增 search_concepts + GET /search | ✅ | |
| T6 | 编辑 API 扩展 | commit 1caa785, _NODE_UPDATABLE 扩展 + set_review_status 状态机 + reorder 作用域 + auto-rollback | ✅ | |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|-------|
| T1: big_concepts 行数=10 | test_migration.py::TestBigConceptCount::test_big_concept_count | `pytest tests/test_knowledge_tree/test_migration.py::TestBigConceptCount::test_big_concept_count -v` | pass (count==3 in fixture, 10 on real db) | 不适用：本次新增测试 |
| T1: map 覆盖 108 L1 | test_migration.py::TestMapCoverage::test_map_coverage | `pytest tests/test_knowledge_tree/test_migration.py::TestMapCoverage -v` | pass (mapped==l1, primary<=1) | 不适用：本次新增测试 |
| T1: L0→evidence | test_migration.py::TestL0Reclassification | `pytest tests/test_knowledge_tree/test_migration.py::TestL0Reclassification -v` | pass (L0=0, evidence=3) | 不适用：本次新增测试 |
| T1: aliases 迁移 | test_migration.py::TestAliasesMigration | `pytest tests/test_knowledge_tree/test_migration.py::TestAliasesMigration -v` | pass | 不适用：本次新增测试 |
| T1: evidence_ids 迁移 | test_migration.py::TestEvidenceIdsMigration | `pytest tests/test_knowledge_tree/test_migration.py::TestEvidenceIdsMigration -v` | pass | 不适用：本次新增测试 |
| T2: PG 模型读写 | test_models.py::test_node_new_columns_read_write | `pytest tests/test_knowledge_tree/test_models.py -v` | pass (11/11) | 不适用：本次新增测试 |
| T3: L1-only sync | test_sync_startup.py::test_sync_l1_only | `pytest tests/test_knowledge_tree/test_sync_startup.py::test_sync_l1_only -v` | pass (3 nodes: 2 L1 + 1 BC) | 不适用：本次新增测试 |
| T3: map sync | test_sync_startup.py::test_sync_map | `pytest tests/test_knowledge_tree/test_sync_startup.py::test_sync_map -v` | pass (2 maps) | 不适用：本次新增测试 |
| T3: difficulty/bloom sync | test_sync_startup.py::test_sync_difficulty_bloom | `pytest tests/test_knowledge_tree/test_sync_startup.py::test_sync_difficulty_bloom -v` | pass (A: diff=4 bloom=apply) | 不适用：本次新增测试 |
| T4: navigation 结构 | test_router.py::test_navigation_structure | `pytest tests/test_knowledge_tree/test_router.py::test_navigation_structure -v` | pass (M1→BC_M1_C1→{A,B}) | 不适用：本次新增测试 |
| T4: graph.nodes 含 difficulty/bloom | test_router.py::test_graph_node_fields | `pytest tests/test_knowledge_tree/test_router.py::test_graph_node_fields -v` | pass | 不适用：本次新增测试 |
| T4: mastery 排除 BigConcept | test_service.py::test_get_mastery_excludes_big_concepts | `pytest tests/test_knowledge_tree/test_service.py::test_get_mastery_excludes_big_concepts -v` | pass (BC_M1_C1 not in mastery) | 不适用：本次新增测试 |
| T5: evidence 段 | test_node_detail_api.py::test_node_detail_evidence | `pytest tests/test_knowledge_tree/test_node_detail_api.py::test_node_detail_evidence -v` | pass (2 evidence items) | 不适用：本次新增测试 |
| T5: search name+alias+description | test_search.py | `pytest tests/test_knowledge_tree/test_search.py -v` | pass (8/8) | 不适用：本次新增测试 |
| T6: update difficulty/bloom | test_edit_extended.py::TestUpdateConceptFields | `pytest tests/test_knowledge_tree/test_edit_extended.py::TestUpdateConceptFields -v` | pass (5/5) | 不适用：本次新增测试 |
| T6: set_review_status 状态机 | test_edit_extended.py::TestSetReviewStatus | `pytest tests/test_knowledge_tree/test_edit_extended.py::TestSetReviewStatus -v` | pass (3/3) | 不适用：本次新增测试 |
| T6: auto-rollback | test_edit_extended.py::TestPublishedAutoRollback | `pytest tests/test_knowledge_tree/test_edit_extended.py::TestPublishedAutoRollback -v` | pass (3/3) | 不适用：本次新增测试 |
| T6: reorder 作用域 | test_edit_extended.py::TestReorder | `pytest tests/test_knowledge_tree/test_edit_extended.py::TestReorder -v` | pass (3/3) | 不适用：本次新增测试 |

### 验证清单自检

**T1 审查清单:**
- ✅ BigConcept ID 使用稳定编码（BC_BIO_M{n}_C{slug}）
- ✅ is_primary 默认 FALSE
- ✅ concept_big_concept_map 有部分唯一索引 ux_cbc_primary
- ✅ 迁移幂等（INSERT OR IGNORE）
- ✅ aliases_json 从 JSON 骨架迁移且有独立测试（R3-F002）
- ✅ evidence_ids_json 从 JSON 骨架迁移且有独立测试（R3-F002）

**T2 审查清单:**
- ✅ subject 列存在
- ✅ node_type 列存在
- ✅ difficulty 列存在（Integer, nullable）
- ✅ bloom_level 列存在（String(20), nullable）
- ✅ Alembic migration 可 upgrade + downgrade

**T3 审查清单:**
- ✅ _read_knowledge_db 只读 L1 concepts
- ✅ BigConcept 节点的 node_type = 'big_concept'
- ✅ 旧版 knowledge.db（无 big_concepts 表）不崩溃
- ✅ difficulty/bloom_level 从 knowledge.db 读取并写入 PG（F002）
- ✅ 旧版 knowledge.db 无 difficulty 列时不崩溃（容错）

**T4 审查清单:**
- ✅ navigation 是显式字段，不从 nodes 临时拼
- ✅ graph.nodes 只含 node_type='concept'（L1）
- ✅ big_concept_id 取 is_primary=TRUE 的归属
- ✅ module 过滤同时作用于 navigation 和 graph
- ✅ get_mastery() 查询加 node_type='concept' 过滤（F001）
- ✅ graph.nodes 每个节点携带 difficulty/bloom_level（F002）

**T5 审查清单:**
- ✅ evidence 段从 evidence_ids_json 读取，不硬编码
- ✅ search 逻辑在 service.py 中，router.py 是薄路由（R3-F005）
- ✅ search 同时匹配 name、aliases_json 和 description（R3-F005）
- ✅ search 需认证（get_current_user）
- ✅ search 只返回 node_type='concept'

**T6 审查清单:**
- ✅ _NODE_UPDATABLE 包含 difficulty/bloom_level/aliases_json/display_order（不含 review_status）
- ✅ review_status 不在 _NODE_UPDATABLE 中，必须通过 set_review_status 走状态机（R3-F003）
- ✅ set_review_status 校验状态转移合法性 + 写 reviewed_by/reviewed_at（R3-F003）
- ✅ update_node 修改 published 概念的内容字段时自动回退 review_status 到 ai_draft（R3-F003）
- ✅ reorder 使用 big_concept_id 做作用域验证（R3-F004）
- ✅ 新操作有 knowledge.db 回写

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: 空 big_concepts 表 + L1 概念无 req_ids
  运行命令: `pytest tests/test_knowledge_tree/test_sync_startup.py::test_sync_old_db_no_hierarchy -v`
  实际输出:
  ```
  PASSED — 2 nodes, 0 maps
  ```
  结论: 旧版 knowledge.db 兼容正常

- 状态变量/锁的异常路径：
  构造输入: set_review_status ai_draft → published（非法转移）
  运行命令: `pytest tests/test_knowledge_tree/test_edit_extended.py::TestSetReviewStatus::test_invalid_transition_rejected -v`
  实际输出:
  ```
  PASSED — applied==0, review_status 仍为 ai_draft
  ```
  结论: 状态机拒绝非法转移

- 字符串匹配/条件判断的假阴性：
  构造输入: search "细胞" 应命中 name 含"细胞"的概念但不命中 BigConcept
  运行命令: `pytest tests/test_knowledge_tree/test_search.py::test_search_excludes_big_concepts -v`
  实际输出:
  ```
  PASSED — BC_M1_C1 not in results
  ```
  结论: node_type 过滤有效
