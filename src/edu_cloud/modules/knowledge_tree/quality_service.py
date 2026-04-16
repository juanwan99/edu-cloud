"""知识图谱质量巡检服务。"""
from collections import defaultdict
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge


async def run_quality_check(db: AsyncSession, module: str = "all") -> dict:
    """执行 6 条质量巡检规则，返回 issues 列表。"""
    module_filter = None if module == "all" else module

    # 查 concept 节点
    node_q = sa.select(ConceptGraphNode).where(ConceptGraphNode.node_type == "concept")
    if module_filter:
        node_q = node_q.where(ConceptGraphNode.primary_module == module_filter)
    nodes = list((await db.execute(node_q)).scalars())
    node_ids = {n.id for n in nodes}

    # 查 edge（两端都在当前范围内）
    edge_q = sa.select(ConceptGraphEdge)
    if module_filter:
        subq = sa.select(ConceptGraphNode.id).where(
            ConceptGraphNode.primary_module == module_filter,
            ConceptGraphNode.node_type == "concept",
        )
        edge_q = edge_q.where(
            ConceptGraphEdge.source_id.in_(subq),
            ConceptGraphEdge.target_id.in_(subq),
        )
    edges = list((await db.execute(edge_q)).scalars())

    # 所有 edge（含跨模块，用于 Q1 和 Q4）
    all_edges = list((await db.execute(sa.select(ConceptGraphEdge))).scalars())

    issues: list[dict[str, Any]] = []

    # --- Q1: 孤立概念（无 hard 边）---
    hard_connected = set()
    for e in all_edges:
        if e.relation_type == "prerequisite_hard":
            hard_connected.add(e.source_id)
            hard_connected.add(e.target_id)
    orphans = [n.id for n in nodes if n.id not in hard_connected]
    if orphans:
        issues.append({
            "rule_id": "Q1", "severity": "HIGH",
            "message": f"孤立概念（无硬前置关系）：{len(orphans)} 个",
            "node_ids": orphans, "edge_ids": [],
        })

    # --- Q2: 弱连通分量（prerequisite_hard 无向图）---
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        if e.relation_type == "prerequisite_hard":
            adj[e.source_id].add(e.target_id)
            adj[e.target_id].add(e.source_id)
    # 只看有 hard 边的节点
    hard_node_ids = node_ids & set(adj.keys())
    visited: set[str] = set()
    components: list[list[str]] = []
    for nid in hard_node_ids:
        if nid in visited:
            continue
        # BFS
        component = []
        queue = [nid]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            component.append(curr)
            for neighbor in adj.get(curr, set()):
                if neighbor not in visited and neighbor in hard_node_ids:
                    queue.append(neighbor)
        components.append(component)
    if len(components) > 1:
        comp_desc = "; ".join(
            f"[{', '.join(c[:3])}{'...' if len(c) > 3 else ''}]({len(c)})"
            for c in components
        )
        issues.append({
            "rule_id": "Q2", "severity": "MED",
            "message": f"硬前置子图有 {len(components)} 个弱连通分量：{comp_desc}",
            "node_ids": [nid for comp in components for nid in comp],
            "edge_ids": [],
        })

    # --- Q3: 低置信度关系（<0.7 且 ai_draft）---
    low_conf_edges = [
        e for e in edges
        if e.confidence < 0.7 and (e.review_status or "ai_draft") == "ai_draft"
    ]
    if low_conf_edges:
        issues.append({
            "rule_id": "Q3", "severity": "MED",
            "message": f"低置信度未审核关系：{len(low_conf_edges)} 条（confidence < 0.7）",
            "node_ids": [], "edge_ids": [e.id for e in low_conf_edges],
        })

    # --- Q4: 跨模块硬前置（列出供确认）---
    if module_filter:
        cross_module = [
            e for e in all_edges
            if e.relation_type == "prerequisite_hard"
            and ((e.source_id in node_ids) != (e.target_id in node_ids))
        ]
        if cross_module:
            issues.append({
                "rule_id": "Q4", "severity": "LOW",
                "message": f"跨模块硬前置关系：{len(cross_module)} 条",
                "node_ids": [], "edge_ids": [e.id for e in cross_module],
            })

    # --- Q5: 无描述概念 ---
    no_desc = [n.id for n in nodes if not n.description]
    if no_desc:
        issues.append({
            "rule_id": "Q5", "severity": "MED",
            "message": f"无描述概念：{len(no_desc)} 个",
            "node_ids": no_desc, "edge_ids": [],
        })

    # --- Q6: rejected 堆积（>20%）---
    rejected_count = sum(1 for e in edges if (e.review_status or "ai_draft") == "rejected")
    if edges and rejected_count / len(edges) > 0.2:
        issues.append({
            "rule_id": "Q6", "severity": "LOW",
            "message": f"被驳回关系占比 {rejected_count}/{len(edges)}（>20%），建议清理",
            "node_ids": [],
            "edge_ids": [e.id for e in edges if (e.review_status or "ai_draft") == "rejected"],
        })

    # Summary
    severity_count: dict[str, int] = defaultdict(int)
    for issue in issues:
        severity_count[issue["severity"]] += 1

    return {
        "module": module,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "issues_by_severity": dict(severity_count),
        },
        "issues": issues,
    }
