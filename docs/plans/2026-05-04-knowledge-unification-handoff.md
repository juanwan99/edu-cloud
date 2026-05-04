---
type: handoff
created: 2026-05-04 07:55:28
project_dir: /home/ops/projects/edu-cloud
design: /home/ops/projects/edu-cloud/docs/superpowers/plans/2026-05-04-knowledge-unification.md
plan: /home/ops/projects/edu-cloud/docs/superpowers/plans/2026-05-04-knowledge-unification.md
---

# Knowledge Unification Handoff

=== 生成块开始 ===
**task_id**: knowledge-unification-cleanup
**topic**: knowledge-unification
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T2
**gate_status**: completed — cleanup + verification done
**last_verified_evidence**: commit:31f9bb1d @ 2026-05-04T07:55+08:00, tag knowledge-unification-v1
**subject_hash**: N/A (projectctl not deployed)
**raw_output_hashes**: N/A
**timestamp**: 2026-05-04 07:55:28
=== 生成块结束 ===

=== 自由备注开始 ===
- Tier: T2

## Goal
清理旧 KnowledgePoint UUID 体系全部残留，统一知识点引用到 ConceptGraphNode 语义 string ID 体系。

## Must Preserve
- QuestionKnowledgePoint 表及 concept_id 字段（已统一，不可回退）
- concept_graph_nodes / concept_graph_edges 表数据（5 module / 99 study_unit / 108 concept 节点）
- alembic migration 链完整性（不可改已有 migration）

## Must Not Change
- knowledge/service.py（已正确使用 concept_id）
- adaptive/ bank/ analytics/ 模块中的 knowledge_point_id 字段（属 DaKnowledgePointMap / BankQuestion 各自字段，非旧 KnowledgePoint model）
- w3_student_profile 现有函数签名

## 完成状态
commit 31f9bb1 @ 2026-05-04T07:55，tag knowledge-unification-v1 已打；核心 imports OK。
下一步：端到端真实扫描图走查（B 端主链路最后一英里）。
=== 自由备注结束 ===
