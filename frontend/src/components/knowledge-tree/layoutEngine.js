// 知识图谱骨架布局算法（Phase 2）
//
// 纯函数：输入 { nodes, edges, bigConceptOrder } → 输出 { positions, bands, warnings }
// - nodes: [{ id, big_concept_id, module, ... }]
// - edges: [{ source, target, type }]（只关心 prerequisite_hard）
// - bigConceptOrder: [{ id, name }]（按 display_order 排列）
//
// 算法：Kahn toposort 计算 rank → 按 bigConceptOrder 分配 band Y → band 内按 rank 排 X

const CANVAS_WIDTH = 1200
const CANVAS_HEIGHT = 720
const LEFT_PADDING = 80
const RIGHT_PADDING = 80
const TOP_PADDING = 40
const BOTTOM_PADDING = 40
const BAND_GAP = 16
const COLUMN_WIDTH = 140
const NODE_HEIGHT = 44

export function computeLayout({ nodes, edges, bigConceptOrder }) {
  const positions = {}
  const bands = {}
  const warnings = []

  if (!nodes || nodes.length === 0) {
    return { positions, bands, warnings }
  }

  // Step 1: 构建 hard DAG adjacency（仅包含输入节点集合）
  const nodeIds = new Set(nodes.map(n => n.id))
  const adj = new Map()
  const inDegree = new Map()
  for (const n of nodes) {
    adj.set(n.id, [])
    inDegree.set(n.id, 0)
  }
  for (const e of edges || []) {
    if (e.type !== 'prerequisite_hard') continue
    if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) continue
    adj.get(e.source).push(e.target)
    inDegree.set(e.target, inDegree.get(e.target) + 1)
  }

  // Step 2: Kahn toposort 计算 rank（按 id 字母序保证确定性）
  const rank = new Map()
  const queue = []
  const sortedIds = [...nodeIds].sort()
  for (const id of sortedIds) {
    if (inDegree.get(id) === 0) {
      queue.push(id)
      rank.set(id, 0)
    }
  }
  let head = 0
  while (head < queue.length) {
    const u = queue[head++]
    const succs = adj.get(u).slice().sort()
    for (const v of succs) {
      const newRank = rank.get(u) + 1
      if (!rank.has(v) || rank.get(v) < newRank) {
        rank.set(v, newRank)
      }
      inDegree.set(v, inDegree.get(v) - 1)
      if (inDegree.get(v) === 0) {
        queue.push(v)
      }
    }
  }

  // 环检测：未分配 rank 的节点 = 有环
  const cyclicNodes = nodes.filter(n => !rank.has(n.id))
  if (cyclicNodes.length > 0) {
    warnings.push('cycle_detected')
    const maxExistingRank = rank.size > 0 ? Math.max(...Array.from(rank.values())) : -1
    const fallbackRank = maxExistingRank + 1
    for (const n of cyclicNodes) {
      rank.set(n.id, fallbackRank)
    }
  }

  // Step 3: 按 BigConcept 分组节点
  const nodesByBC = new Map()
  for (const bc of bigConceptOrder) {
    nodesByBC.set(bc.id, [])
  }
  for (const n of nodes) {
    if (nodesByBC.has(n.big_concept_id)) {
      nodesByBC.get(n.big_concept_id).push(n)
    } else {
      if (!nodesByBC.has('__unknown__')) nodesByBC.set('__unknown__', [])
      nodesByBC.get('__unknown__').push(n)
    }
  }

  // 按 bigConceptOrder 顺序收集非空 band
  const activeBcs = bigConceptOrder.filter(bc => (nodesByBC.get(bc.id) || []).length > 0)
  if ((nodesByBC.get('__unknown__') || []).length > 0) {
    activeBcs.push({ id: '__unknown__', name: '未分类' })
  }

  if (activeBcs.length === 0) {
    return { positions, bands, warnings }
  }

  // Step 4: 分配 band Y 范围
  const usableHeight = CANVAS_HEIGHT - TOP_PADDING - BOTTOM_PADDING - BAND_GAP * (activeBcs.length - 1)
  const bandHeight = usableHeight / activeBcs.length
  let yCursor = TOP_PADDING
  for (const bc of activeBcs) {
    bands[bc.id] = {
      yMin: yCursor,
      yMax: yCursor + bandHeight,
      label: bc.name,
    }
    yCursor += bandHeight + BAND_GAP
  }

  // Step 5: band 内分配坐标
  const maxRank = Math.max(0, ...Array.from(rank.values()))
  const usableWidth = CANVAS_WIDTH - LEFT_PADDING - RIGHT_PADDING
  const effectiveCols = Math.max(1, maxRank + 1)
  const colWidth = maxRank === 0 ? COLUMN_WIDTH : Math.min(COLUMN_WIDTH, usableWidth / effectiveCols)

  for (const bc of activeBcs) {
    const bandNodes = nodesByBC.get(bc.id) || []
    // 按 rank 分桶
    const rankBuckets = new Map()
    for (const n of bandNodes) {
      const r = rank.get(n.id) ?? 0
      if (!rankBuckets.has(r)) rankBuckets.set(r, [])
      rankBuckets.get(r).push(n)
    }
    const band = bands[bc.id]
    const bandMidY = (band.yMin + band.yMax) / 2
    const availableVerticalSpread = Math.min(bandHeight * 0.7, NODE_HEIGHT * 3)

    // rank 顺序确定性：按数字排
    const sortedRanks = [...rankBuckets.keys()].sort((a, b) => a - b)
    for (const r of sortedRanks) {
      const bucket = rankBuckets.get(r)
      const x = LEFT_PADDING + r * colWidth + colWidth / 2
      // 同 rank 同 band 多节点 → Y 均匀分布在 band 中部（按 id 排序保证确定性）
      const sorted = bucket.slice().sort((a, b) => a.id.localeCompare(b.id))
      const count = sorted.length
      if (count === 1) {
        positions[sorted[0].id] = { x, y: bandMidY }
      } else {
        const step = availableVerticalSpread / (count - 1)
        const yStart = bandMidY - availableVerticalSpread / 2
        for (let i = 0; i < count; i++) {
          positions[sorted[i].id] = { x, y: yStart + i * step }
        }
      }
    }
  }

  return { positions, bands, warnings }
}
