from collections import defaultdict, deque


def topological_sort_dag(
    nodes: list[str],
    prerequisites: dict[str, list[str]],
) -> list[str]:
    """对 DAG 节点做拓扑排序。

    Args:
        nodes: 所有节点 ID
        prerequisites: {node_id: [prerequisite_ids]}

    Returns: 拓扑排序后的节点列表（前置在前）
    """
    in_degree = defaultdict(int)
    graph = defaultdict(list)
    node_set = set(nodes)

    for node in nodes:
        in_degree.setdefault(node, 0)

    for node, prereqs in prerequisites.items():
        if node not in node_set:
            continue
        for prereq in prereqs:
            if prereq in node_set:
                graph[prereq].append(node)
                in_degree[node] += 1

    queue = deque(n for n in nodes if in_degree[n] == 0)
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return result


def _layered_topo_sort(
    nodes: list[str],
    prerequisites: dict[str, list[str]],
    sort_key: dict[str, float] | None = None,
) -> list[str]:
    """分层拓扑排序：同层按 sort_key 降序。

    Args:
        sort_key: {node_id: score}，同层内按 score 降序排列
    """
    in_degree = defaultdict(int)
    graph = defaultdict(list)
    node_set = set(nodes)

    for node in nodes:
        in_degree.setdefault(node, 0)

    for node, prereqs in prerequisites.items():
        if node not in node_set:
            continue
        for prereq in prereqs:
            if prereq in node_set:
                graph[prereq].append(node)
                in_degree[node] += 1

    # 收集同层节点
    current_layer = [n for n in nodes if in_degree[n] == 0]
    result = []

    while current_layer:
        # 同层按 sort_key 降序
        if sort_key:
            current_layer.sort(key=lambda n: -sort_key.get(n, 0))
        result.extend(current_layer)

        next_layer = []
        for node in current_layer:
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_layer.append(neighbor)
        current_layer = next_layer

    return result


def compute_gap_scores(
    mastery_map: dict[str, dict],
    gaokao_weight: float = 1.0,
) -> dict[str, float]:
    """计算每个 DA 的差距分。solid 的 DA score=0。"""
    scores = {}
    for da_id, info in mastery_map.items():
        if info["state"] == "solid":
            scores[da_id] = 0.0
        else:
            scores[da_id] = (1.0 - info["mastery"]) * gaokao_weight
    return scores


def plan_learning_path(
    mastery_map: dict[str, dict],
    da_to_su: dict[str, str],
    su_prerequisites: dict[str, list[str]],
) -> list[dict]:
    """规划学习路径。

    1. 过滤 solid DA
    2. 映射到 StudyUnit
    3. 拓扑排序（前置优先）
    4. 同层按 gap_score 降序

    Returns: [{study_unit_id, da_ids, gap_score, state}]
    """
    su_das: dict[str, list[dict]] = defaultdict(list)
    gap_scores = compute_gap_scores(mastery_map)

    for da_id, info in mastery_map.items():
        if info["state"] == "solid":
            continue
        su_id = da_to_su.get(da_id)
        if su_id:
            su_das[su_id].append({
                "da_id": da_id,
                "mastery": info["mastery"],
                "state": info["state"],
                "gap_score": gap_scores.get(da_id, 0),
            })

    if not su_das:
        return []

    su_ids = list(su_das.keys())
    # 计算每个 SU 的 max gap_score 用于同层排序
    su_gap = {}
    for su_id in su_ids:
        das = su_das[su_id]
        su_gap[su_id] = max(d["gap_score"] for d in das)
    sorted_su_ids = _layered_topo_sort(su_ids, su_prerequisites, sort_key=su_gap)

    result = []
    for su_id in sorted_su_ids:
        das = su_das[su_id]
        max_gap = max(d["gap_score"] for d in das)
        worst_state = min(das, key=lambda d: d["mastery"])["state"]
        result.append({
            "study_unit_id": su_id,
            "da_ids": [d["da_id"] for d in das],
            "gap_score": round(max_gap, 4),
            "state": worst_state,
        })

    return result
