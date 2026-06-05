---
name: adaptive
status: active
owner: backend
layer: business

owns_tables:
  - answer_logs
  - student_da_mastery
  - da_bkt_params
  - da_knowledge_point_map
  - question_da_override
  - adaptive_cards
  - da_catalog_snapshot

owns_routes: ""
structure_pattern: service-only
max_router_loc: 0
routers: []

exposes:
  services:
    - diagnose_and_recommend
    - process_answer
    - sync_da_catalog
    - sync_da_kp_map
  events: []

depends_on:
  modules: []
  services: []
  ai_tools:
    - diagnose_and_recommend

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs:
  - docs/plans/2026-04-06-adaptive-learning-design.md
---

# adaptive 模块

## 职责

自适应学习系统：基于 BKT（贝叶斯知识追踪）模型维护学生对每个 DA（诊断属性）的掌握概率，规划个性化学习路径，推荐迁移带匹配题目。

## 边界

- **做什么**：
  - BKT 掌握度追踪（作答→后验更新→学习转移）
  - DA 目录快照同步（从 knowledge.db 投影）
  - 题目→DA 映射（策略 C + 人工 override）
  - 学习路径规划（拓扑排序 + gap_score 优先）
  - 选题推荐（near/mid/far 迁移带）
  - FSRS 复习卡片（V1 占位）
- **不做什么**：
  - 知识图谱本体管理 → `knowledge_tree` 模块
  - 考后 pipeline 触发 → `pipeline` 模块（调用本模块 `process_answer`）
  - 前端展示 → 无自有前端页面

## 架构

Template C（纯 service，无 router）。通过 pipeline 模块间接接入数据流，通过 AI Agent 工具 `diagnose_and_recommend` 对外暴露。

## 数据流

```
pipeline.service.update_bkt_mastery
       │
       ▼
adaptive.updater.process_answer
  → da_mapper.resolve_da_ids（题目→DA 映射）
  → bkt_engine.bkt_update（贝叶斯更新）
  → student_da_mastery 表写入

AI Agent tool: diagnose_and_recommend
  → service.diagnose_and_recommend
  → classify_da_state（4 态：unseen/weak/fragile/solid）
  → path_planner.plan_learning_path（拓扑排序）
  → question_selector（迁移带选题）

knowledge_tree.sync_service
  → adaptive.sync.sync_da_catalog（DA 目录投影）
  → adaptive.sync.sync_da_kp_map（DA↔知识点映射）
```

## 使用方式

### 外部调用方

- `ai/tools/adaptive.py`: 导入 `diagnose_and_recommend` 提供 Agent 工具
- `modules/pipeline/service.py`: 导入 `process_answer` + `AnswerLog` 做考后 BKT 更新
- `modules/knowledge_tree/sync_service.py`: 导入 `sync_da_catalog` / `sync_da_kp_map` 做知识库同步
- `modules/knowledge_tree/service.py`: 导入 `StudentDaMastery` / `DaKnowledgePointMap` 读取掌握度
- `models/adaptive.py`: re-export stub

## 变更历史

- 2026-04-06: 从 adaptive-learning-design 实现（BKT + 路径规划 + 选题器 + Agent 工具）
