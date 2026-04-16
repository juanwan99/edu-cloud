import { describe, it, expect } from 'vitest'
import {
  heatmapColor,
  masteryColor,
  reviewStatusColor,
  nodeSizeFromImportance,
} from '../../components/knowledge-tree/heatmapUtils'

const HEX6_RE = /^#[0-9a-fA-F]{6}$/

describe('heatmapColor', () => {
  it('returns well-formed #RRGGBB string', () => {
    expect(heatmapColor(0, 1000)).toMatch(HEX6_RE)
    expect(heatmapColor(500, 1000)).toMatch(HEX6_RE)
    expect(heatmapColor(1000, 1000)).toMatch(HEX6_RE)
  })

  it('freq=0 returns light gray (all channels >= 0xCC)', () => {
    const c = heatmapColor(0, 1000)
    const r = parseInt(c.slice(1, 3), 16)
    const g = parseInt(c.slice(3, 5), 16)
    const b = parseInt(c.slice(5, 7), 16)
    expect(r).toBeGreaterThanOrEqual(0xCC)
    expect(g).toBeGreaterThanOrEqual(0xCC)
    expect(b).toBeGreaterThanOrEqual(0xCC)
  })

  it('freq=maxFreq returns deep color (R < 100)', () => {
    const c = heatmapColor(1000, 1000)
    const r = parseInt(c.slice(1, 3), 16)
    expect(r).toBeLessThan(100)
  })

  it('handles freq > maxFreq by clamping (equal to freq=maxFreq)', () => {
    const c = heatmapColor(2000, 1000)
    const max = heatmapColor(1000, 1000)
    expect(c).toBe(max)
  })

  it('handles maxFreq <= 0 with safe fallback', () => {
    const c = heatmapColor(10, 0)
    expect(c).toMatch(HEX6_RE)
  })

  it('uses log scale — freq=100 lies between freq=1 and freq=1000, not near linear midpoint', () => {
    // 反例: 线性映射 (freq/maxFreq) 会让 freq=100 与 freq=1000 颜色极近，几乎无区分
    //       log 尺度下 log(101)/log(1001) ≈ 0.668, 而线性是 0.1
    const c1 = heatmapColor(1, 1000)
    const c100 = heatmapColor(100, 1000)
    const c1000 = heatmapColor(1000, 1000)
    expect(c1).not.toBe(c100)
    expect(c100).not.toBe(c1000)

    const r1 = parseInt(c1.slice(1, 3), 16)
    const r100 = parseInt(c100.slice(1, 3), 16)
    const r1000 = parseInt(c1000.slice(1, 3), 16)
    // 单调递减（freq 增加 → R 通道减小，颜色变深）
    expect(r1).toBeGreaterThan(r100)
    expect(r100).toBeGreaterThan(r1000)
    // log 尺度下 freq=100 的 R 应该比线性插值(90% of r1+10% of r1000=~223)更接近中深色
    // r100 应该离 r1000 更近（log(101)/log(1001)=0.668 → R 距离 r1000 的 33%）
    const linearExpected = r1 - (r1 - r1000) * 0.1 // 线性 freq=100 时 R 的近似值
    expect(r100).toBeLessThan(linearExpected - 20) // log 尺度下明显更深
  })
})

describe('masteryColor', () => {
  it('returns well-formed hex for all 4 states', () => {
    expect(masteryColor('solid')).toMatch(HEX6_RE)
    expect(masteryColor('fragile')).toMatch(HEX6_RE)
    expect(masteryColor('weak')).toMatch(HEX6_RE)
    expect(masteryColor('unseen')).toMatch(HEX6_RE)
  })

  it('unseen returns gray (R≈G≈B)', () => {
    const c = masteryColor('unseen')
    const r = parseInt(c.slice(1, 3), 16)
    const g = parseInt(c.slice(3, 5), 16)
    const b = parseInt(c.slice(5, 7), 16)
    expect(Math.abs(r - g)).toBeLessThan(20)
    expect(Math.abs(g - b)).toBeLessThan(20)
  })

  it('solid returns green (G > R)', () => {
    const c = masteryColor('solid')
    const r = parseInt(c.slice(1, 3), 16)
    const g = parseInt(c.slice(3, 5), 16)
    expect(g).toBeGreaterThan(r)
  })

  it('weak returns red (R > G)', () => {
    // 反例: 若 weak 走错分支返回绿色/灰色，R>G 不成立
    const c = masteryColor('weak')
    const r = parseInt(c.slice(1, 3), 16)
    const g = parseInt(c.slice(3, 5), 16)
    expect(r).toBeGreaterThan(g)
  })

  it('fragile returns yellow/orange (R > B)', () => {
    const c = masteryColor('fragile')
    const r = parseInt(c.slice(1, 3), 16)
    const b = parseInt(c.slice(5, 7), 16)
    expect(r).toBeGreaterThan(b)
  })

  it('unknown state falls back to unseen color', () => {
    expect(masteryColor('bogus')).toBe(masteryColor('unseen'))
    expect(masteryColor(undefined)).toBe(masteryColor('unseen'))
  })
})

describe('reviewStatusColor', () => {
  it('returns well-formed hex for 3 known states', () => {
    expect(reviewStatusColor('ai_draft')).toMatch(HEX6_RE)
    expect(reviewStatusColor('teacher_reviewed')).toMatch(HEX6_RE)
    expect(reviewStatusColor('published')).toMatch(HEX6_RE)
  })

  it('three states produce three distinct colors', () => {
    const a = reviewStatusColor('ai_draft')
    const b = reviewStatusColor('teacher_reviewed')
    const c = reviewStatusColor('published')
    expect(a).not.toBe(b)
    expect(b).not.toBe(c)
    expect(a).not.toBe(c)
  })

  it('unknown state falls back to ai_draft', () => {
    expect(reviewStatusColor('bogus')).toBe(reviewStatusColor('ai_draft'))
  })
})

describe('nodeSizeFromImportance', () => {
  it('importance=0 returns [20, 30]', () => {
    const s = nodeSizeFromImportance(0)
    expect(s).toBeGreaterThanOrEqual(20)
    expect(s).toBeLessThanOrEqual(30)
  })

  it('importance=10 returns [50, 70]', () => {
    const s = nodeSizeFromImportance(10)
    expect(s).toBeGreaterThanOrEqual(50)
    expect(s).toBeLessThanOrEqual(70)
  })

  it('is strictly monotonic increasing on [0, 10]', () => {
    // 反例: 若硬编码常量（所有 size 相等），则 size(5) === size(2) 不满足 >
    const prev = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    for (const v of prev) {
      expect(nodeSizeFromImportance(v + 1)).toBeGreaterThan(nodeSizeFromImportance(v))
    }
  })

  it('clamps importance > 10 to the size for 10', () => {
    expect(nodeSizeFromImportance(100)).toBe(nodeSizeFromImportance(10))
  })

  it('clamps importance < 0 to the size for 0', () => {
    expect(nodeSizeFromImportance(-5)).toBe(nodeSizeFromImportance(0))
  })
})
