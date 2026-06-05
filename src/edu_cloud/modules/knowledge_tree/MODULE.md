---
name: knowledge_tree
status: active
owner: backend
layer: business

owns_tables:
  - concept_graph_nodes
  - concept_graph_edges
  - concept_big_concept_map
  - concept_stats
  - edit_sync_failures

owns_routes:
  - /api/v1/knowledge-tree
structure_pattern: standard
max_router_loc: 200
routers: [router.py]

exposes:
  services:
    - get_graph
    - get_mastery
    - search_concepts
    - apply_edits
    - sync_from_knowledge_db
  events: []

depends_on:
  modules:
    - adaptive
  services:
    - core.permissions
    - api.deps
  ai_tools:
    - edit_knowledge_graph
    - get_knowledge_tree
    - get_question_knowledge_points

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs:
  - docs/plans/2026-04-05-knowledge-tree-design.md
  - docs/plans/2026-04-09-knowledge-graph-restructure-design.md
  - docs/plans/2026-04-09-knowledge-graph-model-design.md
  - docs/plans/2026-04-10-teacher-workbench-design.md
---

# knowledge_tree 模块

## 职责

知识图谱可视化与编辑：从 knowledge.db 同步概念/关系到 PostgreSQL（投影），提供 4 层导航（Module→BigConcept→Concept→Evidence）、学生掌握度聚合（BKT→概念→模块）、搜索、质量巡检（6 规则）、图谱编辑（审核状态机 + 双向回写 knowledge.db）、高考真题关联分页、统计概览、课程地图。

## 边界

- **做什么**：Graph API（节点+边+导航+stats 合并）/ 掌握度聚合（依赖 adaptive.StudentDaMastery）/ 概念搜索 / 质量巡检 / 图谱编辑（8 种 op + 审核状态机 + 内容修改自动回退）/ 回写 knowledge.db / 高考真题分页 / 统计概览 / 课程地图
- **不做什么**：知识库原始数据管理(knowledge.store) / BKT 计算(adaptive) / 考试题目管理(exam) / 前端可视化渲染(frontend G6)

## 使用方式

前端 `KnowledgeTreePage.vue`（AntV G6 力导向图 + TreeNavPanel + ModuleOverviewPanel + ConceptMapPanel）调用 `GET /graph` 获取结构，`GET /mastery` 获取学生掌握度着色，`POST /edit` 教师编辑。AI Agent 通过 `edit_knowledge_graph` 工具调用 `apply_edits`，通过 `get_knowledge_tree` / `get_question_knowledge_points` 工具查询。

## 数据流

```
knowledge.db(SQLite) → sync_service.sync_from_knowledge_db → concept_graph_nodes + edges + map + stats(PostgreSQL)
GET /api/v1/knowledge-tree/graph → service.get_graph → 聚合 nodes+edges+navigation+stats
GET /api/v1/knowledge-tree/mastery → service.get_mastery → DaKnowledgePointMap + StudentDaMastery → 概念/模块聚合
POST /api/v1/knowledge-tree/edit → service.apply_edits → PostgreSQL 写入 + backwrite_to_knowledge_db(SQLite)
GET /api/v1/knowledge-tree/graph/{id}/exam-items → exam_items_service → knowledge.db DA→q_matrix→assessment_items
```
