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

