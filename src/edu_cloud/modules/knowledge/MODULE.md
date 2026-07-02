---
name: knowledge
status: active
owner: backend
layer: business

owns_tables:
  - question_knowledge_points

owns_routes:
  - /api/v1/knowledge
owns_services:
  - src/edu_cloud/services/knowledge_workflow.py
structure_pattern: standard
max_router_loc: 100
routers: [router.py]

exposes:
  services:
    - list_knowledge_points
    - get_knowledge_point
    - get_children
    - link_question
    - get_question_knowledge_points
    - KnowledgeStore
  events: []

depends_on:
  modules: []
  services:
    - knowledge_workflow
  ai_tools:
    - ai/tools/knowledge.py

created: "2026-05-05"
last_reviewed: "2026-06-22"
design_docs: []
---

# knowledge 模块

## 职责

知识点查询与题目-知识点关联管理。包含两层：(1) DB 层 — 基于 ConceptGraphNode 的知识点 CRUD + QuestionKnowledgePoint 关联表；(2) 内存层 — KnowledgeStore 全局单例（启动时从 JSON 文件加载课标/L0/L1/高考索引，支持关键字搜索）。

## 边界

- **做什么**：知识点列表/详情/子节点查询（基于 ConceptGraphNode + ConceptGraphEdge contains 关系）；题目-知识点关联 CRUD；内存知识库搜索（curriculum/textbook/gaokao）
- **不做什么**：知识图谱编辑/审核/质量巡检由 `knowledge_tree` 模块负责；知识点掌握度由 `profile` 模块管理

## 使用方式

```bash
GET  /api/v1/knowledge/points                    # 列表（course_code + parent_id 过滤）
GET  /api/v1/knowledge/points/{kp_id}            # 详情
GET  /api/v1/knowledge/points/{kp_id}/children   # 子节点
POST /api/v1/knowledge/link                      # 题目-知识点关联
GET  /api/v1/knowledge/question/{question_id}    # 查询题目关联知识点
```

KnowledgeStore 在 app lifespan 启动时加载，AI tools 通过全局单例调用搜索方法。

## 数据流

```
KnowledgeStore.load(base_dir) → 内存索引（curriculum/L0/L1/gaokao JSON）
AI tools (knowledge.py) → search_curriculum/textbook/concept_info/gaokao
API 查询 → ConceptGraphNode（knowledge_tree 模块投影的节点表）
题目关联 → question_knowledge_points 表
pipeline 读取关联 → 用于知识点掌握度计算
```
