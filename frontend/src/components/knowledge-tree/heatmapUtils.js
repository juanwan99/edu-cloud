// 节点视觉编码工具函数（Phase 1 Task 9）
// 考频→颜色映射使用对数尺度（考频分布偏斜，max≈1313, median≈11）
// 重要度→节点大小 线性映射到 [20, 60] 像素

const clamp = (v, min, max) => Math.max(min, Math.min(max, v))
const toHex = (v) => Math.round(v).toString(16).padStart(2, '0')

const HEATMAP_LIGHT = [237, 233, 254]
const HEATMAP_DEEP = [100, 76, 240]

export function heatmapColor(freq, maxFreq) {
  if (!Number.isFinite(maxFreq) || maxFreq <= 0) {
    return `#${toHex(HEATMAP_LIGHT[0])}${toHex(HEATMAP_LIGHT[1])}${toHex(HEATMAP_LIGHT[2])}`
  }
  const clamped = clamp(freq, 0, maxFreq)
  const ratio = Math.log(clamped + 1) / Math.log(maxFreq + 1)
  const r = HEATMAP_LIGHT[0] - (HEATMAP_LIGHT[0] - HEATMAP_DEEP[0]) * ratio
  const g = HEATMAP_LIGHT[1] - (HEATMAP_LIGHT[1] - HEATMAP_DEEP[1]) * ratio
  const b = HEATMAP_LIGHT[2] - (HEATMAP_LIGHT[2] - HEATMAP_DEEP[2]) * ratio
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

const MASTERY_COLORS = {
  solid:   '#22C55E',
  fragile: '#ED9A51',
  weak:    '#dc2626',
  unseen:  '#E8E8EF',
}

export function masteryColor(state) {
  return MASTERY_COLORS[state] || MASTERY_COLORS.unseen
}

const REVIEW_COLORS = {
  ai_draft:         '#E8E8EF',
  teacher_reviewed: '#644CF0',
  published:        '#22C55E',
}

export function reviewStatusColor(status) {
  return REVIEW_COLORS[status] || REVIEW_COLORS.ai_draft
}

const SIZE_MIN = 20
const SIZE_MAX = 60

export function nodeSizeFromImportance(score) {
  const safeScore = Number.isFinite(score) ? score : 0
  const clamped = clamp(safeScore, 0, 10)
  return Math.round(SIZE_MIN + (clamped / 10) * (SIZE_MAX - SIZE_MIN))
}
