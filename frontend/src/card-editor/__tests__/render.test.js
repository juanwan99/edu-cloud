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

describe('TQL choiceGroups sync logic (F005 regression)', () => {
  // 复现 getValues() TQL 分支的核心逻辑（从 CardEditor.vue 提取）
  function syncTqlChoiceGroups(origGroups, choices) {
    const hasTqlCoords = origGroups.some(g => g.x !== undefined)
    if (!hasTqlCoords || choices.length === 0) return origGroups

    return origGroups.map(g => {
      const gChoices = choices.filter(c => c.qno >= g.start && c.qno < g.start + g.count)
      const opts = gChoices.length > 0 ? Math.max(...gChoices.map(c => c.options)) : g.options
      return { ...g, options: opts }
    })
  }

  it('TQL groups preserve structure but sync edited options from choices', () => {
    const origGroups = [
      { start: 1, count: 5, options: 4, x: 10, y: 20, w: 50 },
      { start: 6, count: 5, options: 4, x: 60, y: 20, w: 50 },
    ]
    // 用户把选项数从 4 改成 5
    const choices = Array.from({ length: 10 }, (_, i) => ({ qno: i + 1, options: 5 }))
    const result = syncTqlChoiceGroups(origGroups, choices)

    // 分组结构不变
    expect(result.length).toBe(2)
    expect(result[0].start).toBe(1)
    expect(result[0].count).toBe(5)
    expect(result[0].x).toBe(10)
    expect(result[1].start).toBe(6)
    expect(result[1].x).toBe(60)
    // options 已同步为 5
    expect(result[0].options).toBe(5)
    expect(result[1].options).toBe(5)
  })

  it('TQL groups with no matching choices keep original options', () => {
    const origGroups = [
      { start: 1, count: 3, options: 4, x: 10, y: 20, w: 50 },
      { start: 50, count: 3, options: 6, x: 60, y: 20, w: 50 },
    ]
    // choices 只覆盖第一组
    const choices = [{ qno: 1, options: 5 }, { qno: 2, options: 5 }, { qno: 3, options: 5 }]
    const result = syncTqlChoiceGroups(origGroups, choices)

    expect(result[0].options).toBe(5)  // 同步
    expect(result[1].options).toBe(6)  // 无匹配，保留原值
  })

  it('non-TQL groups are not affected by this logic', () => {
    const origGroups = [{ start: 1, count: 10, options: 4 }]  // 无 x/y/w
    const choices = Array.from({ length: 10 }, (_, i) => ({ qno: i + 1, options: 5 }))
    const result = syncTqlChoiceGroups(origGroups, choices)

    // hasTqlCoords=false → 返回原始组（未修改）
    expect(result[0].options).toBe(4)
  })
})
