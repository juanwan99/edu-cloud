// model.js — 答题卡布局数据模型
// 定义 layout JSON schema 和 CRUD 操作函数

function _buildSubs(subCount) {
  if (!subCount || subCount <= 0) return []
  return Array.from({ length: subCount }, (_, i) => ({
    sub: i + 1,
    blanks: [{ w: '100%' }, { w: '100%' }, { w: '100%' }],
  }))
}

export function createDefaultLayout(config) {
  const choiceCount = config.choiceCount || 11;
  const fillCount = config.fillCount || 3;
  const essayConfig = config.essayConfig || [];
  const fillStart = choiceCount + 1;
  const essayStart = choiceCount + fillCount + 1;

  // 构建所有 essay regions
  const essayRegions = essayConfig.map((ec, i) => ({
    id: `essay-${essayStart + i}`,
    type: 'essay',
    qno: essayStart + i,
    score: (ec || {}).score || 10,
    subs: _buildSubs((ec || {}).sub_count || 0),
    heightRatio: 1.0,
  }));

  // 6 个槽位：A面 col0/1/2 + B面 col0/1/2，从 col0 开始依次填充
  const slots = [[], [], [], [], [], []];
  let slotIdx = 0;
  for (const r of essayRegions) {
    slots[slotIdx].push(r);
    slotIdx = Math.min(slotIdx + 1, 5);
  }

  const paperSize = config.paperSize || 'A3'
  const isA4 = paperSize === 'A4'

  const col0Regions = [
    { id: 'header', type: 'fixed', role: 'header' },
    { id: 'info', type: 'fixed', role: 'info' },
    { id: 'notice', type: 'fixed', role: 'notice' },
    { id: 'choices', type: 'fixed', role: 'choices',
      count: choiceCount, options: config.optionCount || 4,
      perRow: config.choicePerRow || 20 },
    ...Array.from({length: fillCount}, (_, i) => ({
      id: `fill-${fillStart + i}`,
      type: 'fill',
      qno: fillStart + i,
      spaces: 1,
      spaceWidth: '100%',
      heightRatio: 1 / fillCount,
    })),
  ]

  if (isA4) {
    // A4: 单栏，A/B 双面
    const aEssays = essayRegions.filter((_, i) => i < Math.ceil(essayRegions.length / 2))
    const bEssays = essayRegions.filter((_, i) => i >= Math.ceil(essayRegions.length / 2))
    return {
      paper: 'A4',
      config,
      sides: [
        { side: 'A', columns: [{ col: 0, regions: [...col0Regions, ...aEssays] }] },
        { side: 'B', columns: [{ col: 0, regions: [...bEssays] }] },
      ],
    }
  }

  return {
    paper: 'A3',
    config,
    sides: [
      {
        side: 'A',
        columns: [
          { col: 0, regions: [...col0Regions, ...slots[0]] },
          { col: 1, regions: [...slots[1]] },
          { col: 2, regions: [...slots[2]] },
        ],
      },
      {
        side: 'B',
        columns: [
          { col: 0, regions: [...slots[3]] },
          { col: 1, regions: [...slots[4]] },
          { col: 2, regions: [...slots[5]] },
        ],
      },
    ],
  };
}

/**
 * 将 LLM 解析的题目数据应用到编辑器 config，保留视觉样式参数。
 * @param {object} config - 现有编辑器 config（含视觉样式）
 * @param {Array} questions - LLM standardized: [{number, type, answer, score, sub_count, options_count}]
 * @returns {{ config: object, choices: Array }} 更新后的 config 和 choices 数据
 */
export function applyQuestions(config, questions) {
  const choices = questions.filter(q => ['single_choice', 'multi_choice'].includes(q.type))
  const fills = questions.filter(q => q.type === 'fill_in_blank')
  const essays = questions.filter(q => q.type === 'short_answer')

  // 更新题目结构参数（保留所有视觉样式参数不变）
  const updated = { ...config }
  updated.choiceCount = choices.length
  updated.optionCount = choices.length > 0 ? Math.max(...choices.map(q => q.options_count || 4)) : 4
  updated.fillCount = fills.length
  updated.fillScore = fills.length > 0 ? fills[0].score || 5 : 5
  updated.essayCount = essays.length
  updated.essayConfig = essays.map(q => ({ score: q.score || 10, sub_count: q.sub_count || 0 }))

  // 构建 choices 数组（选择题涂卡数据）
  const choicesData = choices.map(q => ({
    qno: q.number,
    options: q.options_count || 4,
  }))

  return { config: updated, choices: choicesData }
}

// 获取所有已用题号，返回下一个可用题号
function nextQno(layout) {
  let max = 0;
  for (const side of layout.sides) {
    for (const col of side.columns) {
      for (const r of col.regions) {
        if (r.qno && r.qno > max) max = r.qno;
      }
    }
  }
  return max + 1;
}

// 重新编排所有可编辑区域的题号（按 A面→B面、栏从左到右、区域从上到下）
export function renumberAll(layout) {
  // 找到最小的 essay/fill 题号作为起始
  let startQno = Infinity;
  for (const side of layout.sides) {
    for (const col of side.columns) {
      for (const r of col.regions) {
        if ((r.type === 'essay' || r.type === 'fill') && r.qno > 0 && r.qno < startQno) {
          startQno = r.qno;
        }
      }
    }
  }
  if (startQno === Infinity) startQno = 1;

  let qno = startQno;
  for (const side of layout.sides) {
    for (const col of side.columns) {
      for (const r of col.regions) {
        if (r.type === 'essay' || r.type === 'fill') {
          r.qno = qno++;
        }
      }
    }
  }
}

// 分割操作：在指定栏的指定位置插入分割线
export function splitRegion(layout, sideIdx, colIdx, regionIdx, splitRatio = 0.5) {
  const col = layout.sides[sideIdx].columns[colIdx];
  const region = col.regions[regionIdx];
  const originalRatio = region.heightRatio;

  region.heightRatio = originalRatio * splitRatio;

  const newRegion = {
    id: `essay-new-${Date.now()}`,
    type: 'essay',
    qno: 0, // 临时，renumberAll 会修正
    score: region.score || 10,
    subs: [{ sub: 1, blanks: [{w:'100%'},{w:'100%'},{w:'100%'}] }],
    heightRatio: originalRatio * (1 - splitRatio),
  };
  col.regions.splice(regionIdx + 1, 0, newRegion);
  renumberAll(layout);
  return layout;
}

// 删除分割线：合并两个相邻区域
export function mergeRegions(layout, sideIdx, colIdx, regionIdx) {
  const col = layout.sides[sideIdx].columns[colIdx];
  if (regionIdx >= col.regions.length - 1) return layout;
  const upper = col.regions[regionIdx];
  const lower = col.regions[regionIdx + 1];
  upper.heightRatio += lower.heightRatio;
  col.regions.splice(regionIdx + 1, 1);
  renumberAll(layout);
  return layout;
}

// 调整分割线位置
export function resizeDivider(layout, sideIdx, colIdx, dividerIdx, delta) {
  const col = layout.sides[sideIdx].columns[dividerIdx >= 0 ? colIdx : 0];
  const upper = col.regions[dividerIdx];
  const lower = col.regions[dividerIdx + 1];
  if (!upper || !lower) return layout;

  const minRatio = 0.05;
  const newUpper = upper.heightRatio + delta;
  const newLower = lower.heightRatio - delta;
  if (newUpper >= minRatio && newLower >= minRatio) {
    upper.heightRatio = newUpper;
    lower.heightRatio = newLower;
  }
  return layout;
}
