// frontend/src/card-editor/__tests__/render.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { renderFromLayout } from '../render.js'

function makeA4Layout() {
  return {
    paper: 'A4',
    config: { paperSize: 'A4', examTitle: 'Test', subjectTitle: '英语',
      choiceCount: 0, optionCount: 4, choicePerRow: 15, choiceGroups: [],
      fillCount: 0, essayCount: 1, essayConfig: [{ score: 10 }],
      titleSize: 14, subtitleSize: 16, titleSpacing: 1, subtitleSpacing: 4,
      titleGap: 1, subtitleGap: 1.5, infoHeight: 18, infoPadding: 2,
      infoRowGap: 2, infoFontSize: 10, infoBorderWidth: 1, nameLineWidth: 35,
      digitCount: 9, digitBoxSize: 4.5, digitGap: 0.8, barcodeWidthPct: 40,
      barcodeTitleSize: 12, noticeHeight: 20, noticeLabelWidth: 6,
      noticeLabelSize: 10, noticeFontSize: 7, exampleWidth: 10,
      noticeBorderWidth: 1, absentPadding: 1, zoom: 100 },
    sides: [
      { side: 'A', columns: [{ col: 0, regions: [
        { id: 'header', type: 'fixed', role: 'header' },
        { id: 'essay-1', type: 'essay', qno: 1, score: 10, subs: [], heightRatio: 1 },
      ]}]},
      { side: 'B', columns: [{ col: 0, regions: [
        { id: 'essay-2', type: 'essay', qno: 2, score: 10, subs: [], heightRatio: 1 },
      ]}]},
    ],
  }
}

function makeA3Layout() {
  return {
    paper: 'A3',
    config: { paperSize: 'A3', examTitle: 'Test', subjectTitle: '数学',
      choiceCount: 0, optionCount: 4, choicePerRow: 15, choiceGroups: [],
      fillCount: 0, essayCount: 1, essayConfig: [{ score: 10 }],
      titleSize: 14, subtitleSize: 16, titleSpacing: 1, subtitleSpacing: 4,
      titleGap: 1, subtitleGap: 1.5, infoHeight: 18, infoPadding: 2,
      infoRowGap: 2, infoFontSize: 10, infoBorderWidth: 1, nameLineWidth: 35,
      digitCount: 9, digitBoxSize: 4.5, digitGap: 0.8, barcodeWidthPct: 40,
      barcodeTitleSize: 12, noticeHeight: 20, noticeLabelWidth: 6,
      noticeLabelSize: 10, noticeFontSize: 7, exampleWidth: 10,
      noticeBorderWidth: 1, absentPadding: 1, zoom: 100 },
    sides: [
      { side: 'A', columns: [
        { col: 0, regions: [{ id: 'header', type: 'fixed', role: 'header' }] },
        { col: 1, regions: [{ id: 'essay-1', type: 'essay', qno: 1, score: 10, subs: [], heightRatio: 1 }] },
        { col: 2, regions: [] },
      ]},
      { side: 'B', columns: [
        { col: 0, regions: [] }, { col: 1, regions: [] }, { col: 2, regions: [] },
      ]},
    ],
  }
}

describe('renderFromLayout', () => {
  let container

  beforeEach(() => {
    container = document.createElement('div')
    // mock window globals card-editor expects
    window._choices = []
  })

  it('A4 layout generates .a4-content > .a4-col structure', () => {
    const layout = makeA4Layout()
    renderFromLayout(container, layout, layout.config)
    expect(container.querySelector('.a4-content')).not.toBeNull()
    expect(container.querySelector('.a4-col')).not.toBeNull()
    expect(container.querySelector('.a3-layout')).toBeNull()
  })

  it('A4 B-side with regions generates #pageB with .a4-col--full', () => {
    const layout = makeA4Layout()
    renderFromLayout(container, layout, layout.config)
    const pageB = container.querySelector('#pageB')
    expect(pageB).not.toBeNull()
    expect(pageB.querySelector('.a4-col--full')).not.toBeNull()
  })

  it('A4 B-side without regions does not generate #pageB', () => {
    const layout = makeA4Layout()
    layout.sides[1].columns[0].regions = []
    renderFromLayout(container, layout, layout.config)
    expect(container.querySelector('#pageB')).toBeNull()
  })

  it('A3 layout generates .a3-layout > .a3-col structure', () => {
    const layout = makeA3Layout()
    renderFromLayout(container, layout, layout.config)
    expect(container.querySelector('.a3-layout')).not.toBeNull()
    expect(container.querySelectorAll('.a3-col').length).toBe(6)
    expect(container.querySelector('.a4-col')).toBeNull()
  })
})

describe('F001: .page DOM 必须有 data-side 属性', () => {
  let container

  beforeEach(() => {
    container = document.createElement('div')
    window._choices = []
  })

  it('A3 双面布局: pageA data-side="A", pageB data-side="B"', () => {
    const layout = makeA3Layout()
    renderFromLayout(container, layout, layout.config)
    const pageA = container.querySelector('#pageA')
    const pageB = container.querySelector('#pageB')
    expect(pageA).not.toBeNull()
    expect(pageB).not.toBeNull()
    expect(pageA.getAttribute('data-side')).toBe('A')
    expect(pageB.getAttribute('data-side')).toBe('B')
  })

  it('A4 双面布局: pageA data-side="A", pageB data-side="B"', () => {
    const layout = makeA4Layout()
    renderFromLayout(container, layout, layout.config)
    const pageA = container.querySelector('#pageA')
    const pageB = container.querySelector('#pageB')
    expect(pageA.getAttribute('data-side')).toBe('A')
    expect(pageB?.getAttribute('data-side')).toBe('B')
  })
})

// ── canonical 模板渲染覆盖（2026-06-11 cardtpl-pack1）──
// 直接读取后端 canonical 真源 JSON 驱动渲染（非手写复刻），
// 保护：A4 多栏保留视觉列结构（不摊平）、列内题目可定位、纸张分流正确

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __testDir = dirname(fileURLToPath(import.meta.url))
const CANONICAL_DIR = resolve(
  __testDir,
  '../../../../src/edu_cloud/modules/card/rendering/canonical_layouts'
)

function loadCanonical(name) {
  // structuredClone 隔离：renderFromLayout 会注入 _side/_col 等运行时标记
  return structuredClone(JSON.parse(readFileSync(resolve(CANONICAL_DIR, name), 'utf-8')))
}

function essayIdsIn(el) {
  return [...el.querySelectorAll('[data-region-type="essay"]')]
    .map(n => n.getAttribute('data-region-id'))
}

describe('canonical 模板渲染覆盖（真实 canonical JSON）', () => {
  let container

  beforeEach(() => {
    container = document.createElement('div')
    window._choices = []
  })

  it('化学 canonical 源文件本身满足 A4 [3,1] + qcols 契约（真源一致性校验）', () => {
    const layout = loadCanonical('canonical_chemistry.json')
    expect(layout.paper).toBe('A4')
    expect(layout.sides.map(s => s.columns.length)).toEqual([3, 1])
    const qcols = layout.sides[0].columns.map(c =>
      c.regions.filter(r => r.type === 'essay').map(r => r.qno))
    expect(qcols).toEqual([[15], [16], [17, 18]])
    expect(layout.config.choiceCount).toBe(14)
    expect(layout.config.fillCount).toBe(0)
    expect(layout.config.essayCount).toBe(4)
  })

  it('化学 A4 [3,1]: 渲染保留 3 个视觉列，未摊平成单列', () => {
    const layout = loadCanonical('canonical_chemistry.json')
    renderFromLayout(container, layout, layout.config)
    const pageA = container.querySelector('#pageA')
    // 源 A 面 3 columns → 渲染 3 个 .a4-col，且存在多栏 flex 容器
    const aCols = pageA.querySelectorAll('.a4-col')
    expect(aCols.length).toBe(3)
    expect(pageA.querySelector('.a4-cols')).not.toBeNull()
  })

  it('化学 A4 [3,1]: Q15 在第 1 列、Q16 在第 2 列、Q17/Q18 在第 3 列', () => {
    const layout = loadCanonical('canonical_chemistry.json')
    renderFromLayout(container, layout, layout.config)
    const pageA = container.querySelector('#pageA')
    const col0 = pageA.querySelector('.a4-col[data-col="0"]')
    const col1 = pageA.querySelector('.a4-col[data-col="1"]')
    const col2 = pageA.querySelector('.a4-col[data-col="2"]')
    expect(col0).not.toBeNull()
    expect(col1).not.toBeNull()
    expect(col2).not.toBeNull()
    expect(essayIdsIn(col0)).toEqual(['essay-Q15'])
    expect(essayIdsIn(col1)).toEqual(['essay-Q16'])
    expect(essayIdsIn(col2)).toEqual(['essay-Q17', 'essay-Q18'])
    // 摊平回归哨兵：第 1 列绝不能包含全部 4 题
    expect(essayIdsIn(col0)).not.toContain('essay-Q16')
    // B 面源 1 列且空 → 不渲染 pageB
    expect(container.querySelector('#pageB')).toBeNull()
  })

  it('英语 canonical A4 [1,1]: 单列结构（无多余 .a4-cols 包装），fill 56-65 + 写作两节全渲染', () => {
    const layout = loadCanonical('canonical_english.json')
    expect(layout.sides.map(s => s.columns.length)).toEqual([1, 1])
    renderFromLayout(container, layout, layout.config)
    const pageA = container.querySelector('#pageA')
    expect(pageA.querySelectorAll('.a4-col').length).toBe(1)
    expect(pageA.querySelector('.a4-cols')).toBeNull()
    for (let qno = 56; qno <= 65; qno++) {
      expect(pageA.querySelector(`[data-region-id="fill-${qno}"]`), `fill-${qno} 必须渲染`).not.toBeNull()
    }
    expect(pageA.querySelector('[data-region-id="essay-Q_写作第一节"]')).not.toBeNull()
    const pageB = container.querySelector('#pageB')
    expect(pageB).not.toBeNull()
    expect(pageB.querySelector('.a4-col--full')).not.toBeNull()
    expect(pageB.querySelector('[data-region-id="essay-Q_写作第一节-cont"]')).not.toBeNull()
    expect(pageB.querySelector('[data-region-id="essay-Q_写作第二节"]')).not.toBeNull()
  })

  it('生物 provisional canonical A3 [3,3]: Q17-21 按列分布渲染于 6 栏结构', () => {
    const layout = loadCanonical('canonical_biology.json')
    expect(layout.paper).toBe('A3')
    expect(layout.sides.map(s => s.columns.length)).toEqual([3, 3])
    renderFromLayout(container, layout, layout.config)
    const a3cols = container.querySelectorAll('#pageA .a3-col')
    expect(a3cols.length).toBe(3)
    expect(container.querySelectorAll('.a3-col').length).toBe(6)
    // A 面列定位：col0=Q17, col1=Q18+Q19, col2=Q20+Q21
    expect(essayIdsIn(a3cols[0])).toEqual(['essay-Q17'])
    expect(essayIdsIn(a3cols[1])).toEqual(['essay-Q18', 'essay-Q19'])
    expect(essayIdsIn(a3cols[2])).toEqual(['essay-Q20', 'essay-Q21'])
  })

  it('A4 多栏结构由 styles.css 真源保障，render.js 不输出 inline flex（cardtpl-pack2）', () => {
    // CSS 真源：styles.css 必须含 .a4-cols 多栏规则
    const css = readFileSync(
      resolve(__testDir, '../../../public/card-editor/styles.css'), 'utf-8')
    expect(css).toMatch(/\.a4-cols\s*\{[^}]*display:\s*flex/s)
    expect(css).toMatch(/\.a4-cols\s*>\s*\.a4-col\s*\{[^}]*flex:\s*1 1 0/s)
    expect(css).toMatch(/\.a4-cols\s*>\s*\.a4-col\s*\{[^}]*min-width:\s*0/s)
    // 渲染输出只带类名，不再依赖 inline style 作为多栏保障
    const layout = loadCanonical('canonical_chemistry.json')
    renderFromLayout(container, layout, layout.config)
    const colsEl = container.querySelector('#pageA .a4-cols')
    expect(colsEl).not.toBeNull()
    expect(colsEl.getAttribute('style') || '').not.toMatch(/display\s*:\s*flex/)
  })

  it('canonical 真源资产不含 _side/_col/_sideIdx 运行时字段（cardtpl-pack2）', () => {
    for (const name of ['canonical_chemistry.json', 'canonical_english.json', 'canonical_biology.json']) {
      const raw = JSON.parse(readFileSync(resolve(CANONICAL_DIR, name), 'utf-8'))
      const bad = []
      const walk = (x, path) => {
        if (Array.isArray(x)) { x.forEach((v, i) => walk(v, `${path}[${i}]`)); return }
        if (x && typeof x === 'object') {
          for (const [k, v] of Object.entries(x)) {
            if (k.startsWith('_')) bad.push(`${path}/${k}`)
            walk(v, `${path}/${k}`)
          }
        }
      }
      walk(raw, name)
      expect(bad, `${name} 含运行时字段`).toEqual([])
    }
  })

  it('A4 B 面多列: regions 在 col1 时按列渲染（不丢列、不摊平）', () => {
    const layout = loadCanonical('canonical_chemistry.json')
    layout.sides[1].columns = [
      { col: 0, regions: [] },
      { col: 1, regions: [{ id: 'essay-Q19', type: 'essay', qno: 19, score: 10, subs: [], heightRatio: 1.0 }] },
    ]
    renderFromLayout(container, layout, layout.config)
    const pageB = container.querySelector('#pageB')
    expect(pageB).not.toBeNull()
    expect(pageB.querySelectorAll('.a4-col').length).toBe(2)
    const bCol1 = pageB.querySelector('.a4-col[data-col="1"]')
    expect(bCol1).not.toBeNull()
    expect(essayIdsIn(bCol1)).toEqual(['essay-Q19'])
  })
})
