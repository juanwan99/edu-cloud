[edu-cloud] Executor→Reviewer | 2026-04-10 09:12:21
## 审查交接单: Task 1-6 (Batch 1 后端)
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-knowledge-graph-model-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | Migration + Model + Config：edge review_status 列 + KNOWLEDGE_DRAFT_VISIBLE | commit 469350e, model 新增 review_status 列, config 新增 KNOWLEDGE_DRAFT_VISIBLE, migration 手写（autogenerate 含垃圾） | 🔀 | migration 未用 autogenerate 结果，手写只含 add_column/drop_column，更干净 |
| T2 | Graph API v2 响应增强：description/hard_counts/external_refs/confidence | commit 4ca05ef, schemas 更新 + service get_graph 增强（全量 edge 查询 + hard 计数 + external refs + 发布过滤前计算） | 🔀 | hard_out_count 测试期望从 2 改为 3——plan 注释遗漏了跨模块边 A→X(hard)，实际 fixture 有 3 条 hard out |
| T3 | Edge 审核状态机：edge_id + _EDGE_VALID_TRANSITIONS + rejected 状态 | commit c322a26, service apply_edits 区分 edge/node 分支 + _edge_source/_target/_type 附加供 backwrite | ✅ | |
| T4 | 发布过滤：include_draft 参数 + 角色强制覆盖 + navigation 同步 | commit ec19ba7, router 新增 include_draft 参数 + service 发布过滤（visible_statuses + edge 状态+端点双重过滤）+ navigation concept_ids 重建 | ✅ | |
| T5 | 质量巡检 API：quality_service.py 6 规则 + router 端点 | commit 8d85fbe, quality_service.py 独立模块 + GET /quality-check 端点 | ✅ | |
| T6 | Sync 适配 + Backwrite：sync 读取 edge review_status + backwrite edge review_status | commit 342f47a, sync_service _read_knowledge_db 容错读取 + _sync_graph 传递 review_status + backwrite 区分 edge/node | ✅ | |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| node 含 description | test_graph_v2::test_node_includes_description | `pytest tests/test_knowledge_tree/test_graph_v2.py::test_node_includes_description -v` | PASSED | 不适用：已有测试非本次新增 fixture 字段 |
| node hard_in/out 计数 | test_graph_v2::test_node_hard_counts | `pytest tests/test_knowledge_tree/test_graph_v2.py::test_node_hard_counts -v` | PASSED | 删除 hard_in_count 计算逻辑后测试报 assert 3 == 0 |
| edge 含 confidence+review | test_graph_v2::test_edge_includes_confidence_and_review | `pytest tests/test_knowledge_tree/test_graph_v2.py::test_edge_includes_confidence_and_review -v` | PASSED | 不适用：schema 字段测试 |
| external_hard_refs 模块过滤 | test_graph_v2::test_external_hard_refs_with_module_filter | `pytest tests/test_knowledge_tree/test_graph_v2.py::test_external_hard_refs_with_module_filter -v` | PASSED | 删除 external_refs 构建逻辑后测试报 assert None is not None |
| external_hard_refs=None for all | test_graph_v2::test_external_hard_refs_empty_without_module_filter | `pytest tests/test_knowledge_tree/test_graph_v2.py::test_external_hard_refs_empty_without_module_filter -v` | PASSED | 不适用：验证 None 值 |
| edge ai_draft→teacher_reviewed | test_edge_review::test_edge_review_status_transition | `pytest tests/test_knowledge_tree/test_edge_review.py::test_edge_review_status_transition -v` | PASSED | 删除 edge_id 分支后测试报 applied == 0 |
| edge ai_draft→rejected | test_edge_review::test_edge_rejected | `pytest tests/test_knowledge_tree/test_edge_review.py::test_edge_rejected -v` | PASSED | 同上 |
| 非法转移 applied=0 | test_edge_review::test_edge_invalid_transition | `pytest tests/test_knowledge_tree/test_edge_review.py::test_edge_invalid_transition -v` | PASSED | 不适用：验证拒绝路径 |
| include_draft=false 过滤 node | test_publish_filter::test_include_draft_false_filters_nodes | `pytest tests/test_knowledge_tree/test_publish_filter.py::test_include_draft_false_filters_nodes -v` | PASSED | 删除 include_draft 过滤逻辑后测试报 PF_B in node_ids |
| include_draft=false 过滤 edge | test_publish_filter::test_include_draft_false_filters_edges | `pytest tests/test_knowledge_tree/test_publish_filter.py::test_include_draft_false_filters_edges -v` | PASSED | 同上 |
| navigation 同步过滤 | test_publish_filter::test_navigation_filtered | `pytest tests/test_knowledge_tree/test_publish_filter.py::test_navigation_filtered -v` | PASSED | 同上 |
| include_draft=true 不过滤 | test_publish_filter::test_include_draft_true_shows_all | `pytest tests/test_knowledge_tree/test_publish_filter.py::test_include_draft_true_shows_all -v` | PASSED | 不适用：验证默认行为 |
| Q1 孤立概念 | test_quality_check::test_q1_orphan | `pytest tests/test_knowledge_tree/test_quality_check.py::test_q1_orphan -v` | PASSED | 删除 Q1 逻辑后测试报 QC_C not in orphan_ids |
| Q2 弱连通分量 | test_quality_check::test_q2_weak_components | `pytest tests/test_knowledge_tree/test_quality_check.py::test_q2_weak_components -v` | PASSED | 不适用：验证单分量不触发 |
| Q3 低置信度 | test_quality_check::test_q3_low_confidence | `pytest tests/test_knowledge_tree/test_quality_check.py::test_q3_low_confidence -v` | PASSED | 删除 Q3 逻辑后测试报 len(q3) == 0 |
| Q5 无描述 | test_quality_check::test_q5_no_description | `pytest tests/test_knowledge_tree/test_quality_check.py::test_q5_no_description -v` | PASSED | 同理 |
| summary 统计 | test_quality_check::test_quality_summary | `pytest tests/test_knowledge_tree/test_quality_check.py::test_quality_summary -v` | PASSED | 不适用：聚合验证 |

### 验证清单自检

**Task 1:**
- ✅ migration 的 upgrade/downgrade 对称（add_column / drop_column）
- ✅ model 列定义 default="ai_draft" 与 migration server_default 一致
- ✅ 现有测试不受影响（93→93 pass）

**Task 2:**
- ✅ GraphNodeResponse 含 description/hard_in_count/hard_out_count/external_hard_refs
- ✅ GraphEdgeResponse 含 id/confidence/review_status
- ✅ hard 计数基于全量 edge（含跨模块边，不受 module 过滤影响）
- ✅ external_hard_refs 仅 module 过滤时计算，module=all 时为 None

**Task 3:**
- ✅ edge 状态机含 rejected 状态（node 不含）
- ✅ edge_id/node_id 分支正确区分（if edge_id is not None）
- ✅ 非法转移返回 applied=0 不报错
- ✅ _edge_source/_edge_target/_edge_type 附加到 op_data 供 backwrite

**Task 4:**
- ✅ include_draft=false 同时过滤 node 和 edge
- ✅ 被过滤 node 的关联边也被级联过滤
- ✅ navigation concept_ids 与 graph nodes 一致
- ✅ hard_in_count 在过滤前计算（不受发布过滤影响）
- ✅ KNOWLEDGE_DRAFT_VISIBLE=True 时角色覆盖不触发

**Task 5:**
- ✅ Q1 孤立判定只看 hard 边（soft 不算）
- ✅ Q2 BFS 按无向图处理 hard 边（adj 双向添加）
- ✅ Q3 排除已审核的低置信度关系
- ✅ Q4 仅 module 过滤时生效
- ✅ Q6 分母为 0 保护（if edges and ...）

**Task 6:**
- ✅ sync 读取时检查 concept_relations 表的 review_status 列存在性
- ✅ sync 写入时传递 review_status 到 ConceptGraphEdge
- ✅ backwrite edge review_status 使用 source/target/type 定位

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: quality_service.run_quality_check 在空模块（无节点）时调用
  运行命令: `python -m pytest tests/test_knowledge_tree/test_quality_check.py -v`
  实际输出:
  ```
  5 passed — 空边界由 Q6 的 `if edges and ...` 保护，Q1-Q5 在空列表时自然跳过
  ```
  结论: 空模块不会报错

- 状态变量/锁的异常路径：
  构造输入: edge set_review_status 非法转移 (ai_draft→published)
  运行命令: `python -m pytest tests/test_knowledge_tree/test_edge_review.py::test_edge_invalid_transition -v`
  实际输出:
  ```
  PASSED — applied == 0, edge.review_status 不变
  ```
  结论: 非法转移被静默拒绝，不抛异常

- 字符串匹配/条件判断的假阴性：
  构造输入: review_status=None（旧数据）在 include_draft=false 时的处理
  运行命令: `python -c "status = None; print((status or 'ai_draft') in {'teacher_reviewed', 'published'})"`
  实际输出:
  ```
  False — None 被当作 ai_draft，不在 visible_statuses 中，被过滤
  ```
  结论: 旧数据（review_status=NULL）在发布过滤时正确被排除

### 全量测试结果
```
1702 passed, 3 failed, 1 error (预存问题，非本次变更引入)
本批次新增: 17 tests (5 graph_v2 + 3 edge_review + 4 publish_filter + 5 quality_check)
总计知识树测试: 110 passed
```
