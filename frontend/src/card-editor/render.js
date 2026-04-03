// render.js — 根据 layout JSON 渲染答题卡 DOM
// 从 layout.sides[].columns[].regions[] 驱动渲染

const WARNING = '请在各题目的答题区域内作答，超出黑色矩形边框限定区域的答案无效';

export function applyCSSToPage(el, v) {
  const s = el.style;
  s.setProperty('--title-size', v.titleSize + 'pt');
  s.setProperty('--subtitle-size', v.subtitleSize + 'pt');
  s.setProperty('--title-spacing', v.titleSpacing + 'px');
  s.setProperty('--subtitle-spacing', v.subtitleSpacing + 'px');
  s.setProperty('--title-gap', v.titleGap + 'mm');
  s.setProperty('--subtitle-gap', v.subtitleGap + 'mm');
  s.setProperty('--info-height', v.infoHeight + 'mm');
  s.setProperty('--info-padding', v.infoPadding + 'mm');
  s.setProperty('--info-row-gap', v.infoRowGap + 'mm');
  s.setProperty('--info-font-size', v.infoFontSize + 'pt');
  s.setProperty('--info-border-width', v.infoBorderWidth + 'px');
  s.setProperty('--name-line-width', v.nameLineWidth + '%');
  s.setProperty('--digit-box-size', v.digitBoxSize + 'mm');
  s.setProperty('--digit-gap', v.digitGap + 'mm');
  s.setProperty('--barcode-width-pct', v.barcodeWidthPct + '%');
  s.setProperty('--barcode-title-size', v.barcodeTitleSize + 'pt');
  s.setProperty('--notice-height', v.noticeHeight + 'mm');
  s.setProperty('--notice-label-width', v.noticeLabelWidth + 'mm');
  s.setProperty('--notice-label-size', v.noticeLabelSize + 'pt');
  s.setProperty('--notice-font-size', v.noticeFontSize + 'pt');
  s.setProperty('--example-width', v.exampleWidth + 'mm');
  s.setProperty('--notice-border-width', v.noticeBorderWidth + 'px');
  s.setProperty('--absent-padding', v.absentPadding + 'mm 2mm');
  el.dataset.paper = v.paperSize;
  const zoom = v.zoom / 100;
  el.style.transform = `scale(${zoom})`;
  // 补偿缩放后的多余布局空间
  const h = 297; // mm — A3 横向和 A4 纵向都是 297mm 高
  const hPx = h * 3.78; // mm→px
  el.style.marginBottom = `${-(hPx * (1 - zoom))}px`;
}

function buildChoiceGroupsHTML(v) {
  const symbols = 'ABCDEFGH';
  const perRow = Math.max(v.choicePerRow || 16, 16);
  const configGroups = v.choiceGroups || [];
  const choices = window._choices || [];

  // 构建渲染组：_choices 提供数据，configGroups 提供分组边界和坐标
  let groups;
  if (choices.length > 0 && configGroups.length > 0) {
    groups = configGroups.map(cg => {
      const gqs = choices.filter(c => c.qno >= cg.start && c.qno < cg.start + cg.count);
      return { options: cg.options, questions: gqs, x: cg.x, y: cg.y, w: cg.w };
    }).filter(g => g.questions.length > 0);
  } else if (choices.length > 0) {
    groups = [];
    let cur = [choices[0]];
    for (let i = 1; i < choices.length; i++) {
      if (choices[i].options === cur[0].options) { cur.push(choices[i]); }
      else { groups.push({ options: cur[0].options, questions: cur }); cur = [choices[i]]; }
    }
    groups.push({ options: cur[0].options, questions: cur });
  } else if (configGroups.length > 0) {
    groups = configGroups.map(cg => ({
      options: cg.options,
      questions: Array.from({length: cg.count}, (_, i) => ({qno: cg.start + i, options: cg.options})),
      x: cg.x, y: cg.y, w: cg.w,
    }));
  } else {
    return '';
  }

  // 渲染单个组
  function renderGroup(g) {
    const opts = g.options;
    const qs = g.questions;
    const vertical = qs.length >= 4 && qs.length <= opts;

    if (vertical) {
      const colTemplate = `3mm auto repeat(${opts}, 5mm) 3mm`;
      const rowCount = qs.length + 1;
      let cells = '<div class="omr-left"></div><div class="choice-cell"></div>';
      for (let o = 0; o < opts; o++) cells += `<div class="choice-cell choice-header">${symbols[o]}</div>`;
      cells += '<div class="omr-right"></div>';
      for (const q of qs) {
        cells += `<div class="omr-left"><div class="omr-dot"></div></div>`;
        cells += `<div class="choice-cell choice-header">${q.qno}</div>`;
        for (let o = 0; o < opts; o++) cells += `<div class="choice-cell"><span class="bracket">${symbols[o]}</span></div>`;
        cells += `<div class="omr-right"><div class="omr-dot"></div></div>`;
      }
      return `<div class="choice-group"><div class="choice-grid-inner" style="grid-template-columns: ${colTemplate}; grid-template-rows: repeat(${rowCount}, auto);">${cells}</div></div>`;
    } else {
      let html = '';
      // 固定列宽：始终按 perRow 列计算，不足的用空单元格填充，左对齐
      const colW = `${Math.floor(100 / perRow * 0.95)}%`;
      const colTemplate = `4mm repeat(${perRow}, ${colW}) 4mm`;
      for (let start = 0; start < qs.length; start += perRow) {
        const batch = qs.slice(start, start + perRow);
        const count = batch.length;
        const rows = opts + 1;
        let cells = '<div class="omr-left"></div>';
        for (const q of batch) cells += `<div class="choice-cell choice-header">${q.qno}</div>`;
        for (let e = count; e < perRow; e++) cells += '<div class="choice-cell"></div>';
        cells += '<div class="omr-right"></div>';
        for (let o = 0; o < opts; o++) {
          cells += '<div class="omr-left"><div class="omr-dot"></div></div>';
          for (let q = 0; q < count; q++) cells += `<div class="choice-cell"><span class="bracket">${symbols[o]}</span></div>`;
          for (let e = count; e < perRow; e++) cells += '<div class="choice-cell"></div>';
          cells += '<div class="omr-right"><div class="omr-dot"></div></div>';
        }
        html += `<div class="choice-group"><div class="choice-grid-inner" style="grid-template-columns: ${colTemplate}; grid-template-rows: repeat(${rows}, auto);">${cells}</div></div>`;
      }
      return html;
    }
  }

  // 编辑器统一网格：所有题目合并，固定 perRow 列，左对齐（忽略 TQL 坐标）
  const allQs = groups.flatMap(g => g.questions.map(q => ({ ...q, options: q.options || g.options })));
  const maxOpts = Math.max(...allQs.map(q => q.options));
  let html = '';
  const colTemplate = `4mm repeat(${perRow}, 1fr) 4mm`;
  for (let start = 0; start < allQs.length; start += perRow) {
    const batch = allQs.slice(start, start + perRow);
    const count = batch.length;
    const rows = maxOpts + 1;
    let cells = '<div class="omr-left"></div>';
    for (const q of batch) cells += `<div class="choice-cell choice-header">${q.qno}</div>`;
    for (let e = count; e < perRow; e++) cells += '<div class="choice-cell"></div>';
    cells += '<div class="omr-right"></div>';
    for (let o = 0; o < maxOpts; o++) {
      cells += '<div class="omr-left"><div class="omr-dot"></div></div>';
      for (const q of batch) {
        if (o < q.options) {
          cells += `<div class="choice-cell"><span class="bracket">${symbols[o]}</span></div>`;
        } else {
          cells += '<div class="choice-cell"></div>';
        }
      }
      for (let e = count; e < perRow; e++) cells += '<div class="choice-cell"></div>';
      cells += '<div class="omr-right"><div class="omr-dot"></div></div>';
    }
    html += `<div class="choice-group"><div class="choice-grid-inner" style="grid-template-columns: ${colTemplate}; grid-template-rows: repeat(${rows}, auto);">${cells}</div></div>`;
  }
  return html;
}

function buildFillHTML(v) {
  const fillCount = v.fillCount || 0;
  if (fillCount === 0) return '';
  const fillPerRow = v.fillPerRow || 2;
  const fillStart = v.fillStart || ((v.choiceCount || 0) + 1);
  const fillColTemplate = `repeat(${fillPerRow}, 1fr)`;
  let fillCells = '';
  for (let i = 0; i < fillCount; i++) {
    const qno = fillStart + i;
    fillCells += `<div class="fill-cell" data-region-id="fill-${qno}" data-region-type="fill" data-qno="${qno}"><span class="fill-label">${qno}.</span><span class="fill-line"></span></div>`;
  }
  const remainder = fillCount % fillPerRow;
  if (remainder > 0) for (let i = 0; i < fillPerRow - remainder; i++) fillCells += '<div class="fill-cell"></div>';
  return `<div class="fill-section"><div class="fill-grid" style="grid-template-columns: ${fillColTemplate};">${fillCells}</div></div>`;
}

function renderSingleBlank(b, regionId, si, bi) {
  const label = b.label || '';
  if (label) {
    return `<div class="essay-line has-label" data-region="${regionId}" data-sub="${si}" data-blank="${bi}" style="width:${b.w}">` +
           `<span class="blank-label">${label}</span><span class="blank-underline"></span></div>`;
  }
  return `<div class="essay-line" data-region="${regionId}" data-sub="${si}" data-blank="${bi}" style="width:${b.w}"></div>`;
}

function renderSubsHTML(subs, regionId, cuts) {
  let html = '';

  // 没有小问：空白答题区，只显示添加按钮
  if (!subs || subs.length === 0) {
    html += `<div class="add-sub-hint" data-region="${regionId}" data-edit="add-sub">+ 添加小问</div>`;
    return html;
  }

  // 收集分割线位置（afterSub 值的 Map）
  const cutPositions = new Map();
  if (cuts && cuts.length > 0) {
    cuts.forEach((c, ci) => {
      // 防护：跳过无效或旧格式的 cut（没有 afterSub 字段）
      if (typeof c.afterSub === 'number' && c.afterSub >= 0 && c.afterSub < subs.length - 1) {
        cutPositions.set(c.afterSub, ci);
      }
    });
  }

  for (let si = 0; si < subs.length; si++) {
    const s = subs[si];
    const blanks = s.blanks || Array.from({length: s.spaces || 3}, () => ({w: s.spaceWidth || '100%'}));
    const subLabel = `（${s.sub}）`;

    const img = s.image;
    let imgHTML = '';
    if (img && img.src) {
      const x = img.x || 60; // 默认右侧 60%
      const y = img.y || 5;  // 默认顶部 5%
      const w = img.w || 35; // 默认宽 35%
      imgHTML = `<div class="sub-img-wrap" data-region="${regionId}" data-sub="${si}"
        style="left:${x}%;top:${y}%;width:${w}%;">
        <img src="${img.src}">
        <div class="img-resize-handle"></div>
        <div class="img-del-btn" data-region="${regionId}" data-sub="${si}">×</div>
      </div>`;
    }

    const blanksHTML = `<div class="essay-blanks" data-region="${regionId}" data-sub="${si}">` +
      `<div class="essay-first-line">` +
        `<span class="essay-sub-label" contenteditable="true" data-region="${regionId}" data-sub="${si}" data-edit="sub">${subLabel}</span>` +
        (blanks[0] ? renderSingleBlank(blanks[0], regionId, si, 0) : '') +
      `</div>` +
      blanks.slice(1).map((b, i) => renderSingleBlank(b, regionId, si, i + 1)).join('') +
    `</div>`;

    html += `<div class="essay-sub-block" data-region="${regionId}" data-sub="${si}">` +
              `<span class="sub-del-btn" data-region="${regionId}" data-sub="${si}">×</span>` +
              blanksHTML + imgHTML +
            `</div>`;

    // 在第 si 个小问后面插入分割线（如果有）
    if (cutPositions.has(si) && si < subs.length - 1) {
      const ci = cutPositions.get(si);
      html += `<div class="essay-cut-line" data-region="${regionId}" data-cut="${ci}" data-after-sub="${si}"><span class="cut-del-btn" data-region="${regionId}" data-cut="${ci}">×</span></div>`;
    }
  }
  html += `<div class="add-sub-hint" data-region="${regionId}" data-edit="add-sub">+ 添加小问</div>`;
  return html;
}

function renderEssayRegion(region, fillColumn) {
  const qno = region.qno || 0;
  const score = region.score || 0;
  const subs = region.subs || [];
  const flex = region.heightRatio || 1;

  // 填空题：简洁横线格式
  if (region.type === 'fill') {
    return `<div class="fill-cell" style="flex:${flex} 1 0;" data-region-id="${region.id}" data-region-type="fill" data-qno="${qno}"><span class="fill-label">${qno}.</span><span class="fill-line"></span></div>`;
  }

  // 语文作文：标题行 + 方格纸 + 每100字标注
  if (region.qtype === 'essay_cn') {
    const totalChars = region.charCount || 800;
    const perRow = 20;
    const totalRows = Math.ceil(totalChars / perRow);
    let gridHTML = '';
    for (let row = 0; row < totalRows; row++) {
      const charNum = (row + 1) * perRow;
      const isMarker = charNum % 100 === 0 && charNum <= totalChars;
      let rowHTML = '';
      for (let c = 0; c < perRow; c++) rowHTML += '<div class="cn-grid-cell"></div>';
      if (isMarker) {
        rowHTML += `<span class="cn-grid-marker">${charNum}</span>`;
      }
      gridHTML += `<div class="cn-grid-row">${rowHTML}</div>`;
    }
    return `<div class="essay-item essay-cn" style="flex:${flex} 1 0;" data-region-id="${region.id}" data-region-type="essay" data-qno="${qno}">
      <div class="essay-item-header" contenteditable="true" data-region="${region.id}">${qno}.（本小题满分 ${score} 分）</div>
      <div class="cn-title-line">题目：<span class="cn-title-underline"></span></div>
      <div class="cn-grid" data-chars="${totalChars}">${gridHTML}</div>
    </div>`;
  }

  const label = region.displayLabel || qno;
  const headerText = region.continuation ? `${label}.（续）` : `${label}.（本小题满分 ${score} 分）`;
  const header = `<div class="essay-item-header" contenteditable="true" data-region="${region.id}">${headerText}</div>`;

  // 题目文本（题干、提示信息等）
  let textsHTML = '';
  if (region.texts && region.texts.length > 0) {
    textsHTML = region.texts.map((t, ti) => {
      const obj = typeof t === 'string' ? { content: t, x: 0, y: 10, align: 'left' } : t;
      const x = obj.x || 0;
      const y = obj.y || 10;
      return `<div class="essay-text-wrap" data-region="${region.id}" data-text-idx="${ti}"
        style="left:${x}%;top:${y}%;">
        <div class="essay-item-text" contenteditable="true"
          data-region="${region.id}" data-text-idx="${ti}">${obj.content || t}</div>
        <div class="text-del-btn" data-region="${region.id}" data-text-idx="${ti}">×</div>
      </div>`;
    }).join('');
  }

  return `<div class="essay-item" style="flex:${flex} 1 0;" data-region-id="${region.id}" data-region-type="essay" data-qno="${qno}">
    ${header}
    ${textsHTML}
    ${renderSubsHTML(subs, region.id, region.cuts)}
  </div>`;
}

function renderCompositionCol(charStart, totalChars, perRow, rows, isFirst, region, cellH) {
  const charEnd = Math.min(charStart + rows * perRow, totalChars);
  let html = '';
  if (isFirst && region) {
    html += `<div class="essay-item-header" contenteditable="true" data-region="${region.id}">${region.qno}.（本小题满分 ${region.score || 60} 分）</div>`;
    html += '<div class="cn-title-line">题目：<span class="cn-title-underline"></span></div>';
  }
  html += '<div class="cn-grid">';
  let charPos = charStart;
  while (charPos < charEnd) {
    const rowEnd = Math.min(charPos + perRow, charEnd);
    const cellCount = rowEnd - charPos;
    let rowHTML = '';
    for (let c = 0; c < cellCount; c++) {
      const charNum = charPos + c + 1;
      const isMarker = charNum % 200 === 0;
      rowHTML += `<div class="cn-grid-cell${isMarker ? ' cn-marker-cell' : ''}" style="width:${cellH}mm;height:${cellH}mm">${isMarker ? `<span class="cn-cell-marker">${charNum}</span>` : ''}</div>`;
    }
    for (let c = cellCount; c < perRow; c++) rowHTML += `<div class="cn-grid-cell empty" style="width:${cellH}mm;height:${cellH}mm"></div>`;
    html += `<div class="cn-grid-row">${rowHTML}</div>`;
    charPos = rowEnd;
  }
  html += '</div>';
  return html;
}

function renderA3Col(contentHTML) {
  return `<div class="a3-col">
    <div class="omr-corner tl"></div>
    <div class="omr-corner tr"></div>
    ${contentHTML}
    <div class="col-warning-bottom">${WARNING}</div>
    <div class="omr-corner bl"></div>
    <div class="omr-corner br"></div>
  </div>`;
}

function renderFixedRegions(config, digitBoxes, choiceGroupsHTML, fillHTML) {
  return `
    <div class="title-area">
      <div class="exam-title">${config.examTitle || ''}</div>
      <div class="subject-title">${config.subjectTitle || ''} 答 题 卡</div>
    </div>
    <div class="info-box">
      <div class="info-left">
        <div class="info-row"><span class="info-label">姓\u3000名</span><span class="info-line"></span></div>
        <div class="info-row"><span class="info-label">准考证号</span><span class="info-boxes">${digitBoxes}</span></div>
      </div>
      <div class="info-right"><div class="barcode-area">
        <span class="barcode-title">贴条形码区</span>
        <span class="barcode-hint">（正面朝上，切勿贴出虚线方框）</span>
      </div></div>
    </div>
    <div class="notice-box">
      <div class="notice-label-col"><span>注意事项</span></div>
      <div class="notice-middle">
        <div class="notice-content">
          <p>1.答题前，考生先将自己的姓名、准考证号填写清楚，并认真核对条形码上的姓名、准考证号和科目；</p>
          <p>2.选择题部分请用2B铅笔填涂方格，修改时用橡皮擦擦干净，不要留痕迹；</p>
          <p>3.非选择题部分请用0.5毫米黑色墨水签字笔书写，字体工整、笔迹清楚；</p>
          <p>4.在草稿纸、试题卷上答题无效；</p>
          <p>5.请勿折叠答题卡，保持字体工整、笔迹清晰、卡面清洁。</p>
        </div>
        <div class="absent-in-notice">
          <div class="absent-checkbox"></div>
          <div class="absent-line"></div>
          <span class="absent-hint">此方框为缺考考生标记，由监考员用2B铅笔填涂。</span>
        </div>
      </div>
      <div class="notice-example">
        <span>正确</span><span>填涂</span><span>示例</span>
        <div class="example-marks"><span class="filled"></span></div>
      </div>
    </div>
    <div class="section-bar">选 择 题（请用2B铅笔填涂）</div>
    <div class="choice-box">
      <div class="choice-groups">${choiceGroupsHTML}</div>
    </div>
    <div class="section-bar">非选择题（请用0.5毫米黑色墨水签字笔书写）</div>
    ${fillHTML}`;
}

function renderColumnRegions(regions, isLeftCol, sideIdx = 0, colIdx = 0) {
  if (!regions || regions.length === 0) {
    return `<div class="col-warning">${WARNING}</div><div class="empty-col-slot" data-empty-side="${sideIdx}" data-empty-col="${colIdx}">右键添加题目</div>`;
  }

  let html = `<div class="col-warning">${WARNING}</div>`;
  const editableRegions = regions.filter(r => r.type !== 'fixed');

  let i = 0;
  while (i < editableRegions.length) {
    const region = editableRegions[i];
    if (i > 0 && region.type !== 'fill') {
      html += `<div class="divider-gap"><div class="divider-handle" data-side="${region._side || 'A'}" data-col="${region._col || 0}" data-divider="${i - 1}"></div></div>`;
    }
    // 连续 fill 合并为 2 列网格
    if (region.type === 'fill') {
      let fillHtml = '';
      const fillStart = i;
      while (i < editableRegions.length && editableRegions[i].type === 'fill') {
        fillHtml += renderEssayRegion(editableRegions[i], true);
        i++;
      }
      const count = i - fillStart;
      const perRow = count <= 2 ? count : 2;
      html += `<div class="fill-section"><div class="fill-grid" style="grid-template-columns: repeat(${perRow}, 1fr);">${fillHtml}</div></div>`;
    } else {
      html += renderEssayRegion(region, true);
      i++;
    }
  }
  return html;
}

export function renderFromLayout(previewWrap, layout, v) {
  const config = layout.config || v;
  const digitBoxes = Array.from({length: config.digitCount || 9}, () => '<div class="digit-box"></div>').join('');
  const choiceGroupsHTML = buildChoiceGroupsHTML(config);
  const fillHTML = buildFillHTML(config);

  if ((layout.paper || config.paperSize) === 'A3') {
    const sideA = layout.sides[0];
    const sideB = layout.sides[1];

    // A面左栏：固定区域（复用 renderFixedRegions）
    const leftCol = renderFixedRegions(config, digitBoxes, choiceGroupsHTML, fillHTML);

    // 为 regions 注入 _side/_col 用于 data attributes（必须在渲染前）
    function tagRegions(side, sideIdx) {
      for (const col of side.columns) {
        for (const r of col.regions) {
          r._side = side.side;
          r._col = col.col;
          r._sideIdx = sideIdx;
        }
      }
    }
    tagRegions(sideA, 0);
    tagRegions(sideB, 1);

    // leftCol 追加 col0 非 fixed 区域（tagRegions 后渲染，确保 _side/_col 正确）
    const leftColFull = leftCol + renderColumnRegions(sideA.columns[0]?.regions?.filter(r => r.type !== 'fixed') || [], false, 0, 0);

    const foldGuide = '<div class="fold-guide"></div>';
    const colGap = '<div class="a3-col-gap"></div>';

    // 合并超出 3 栏的 regions 到最后一栏
    function mergedRegions(side, colIdx) {
      const cols = side.columns;
      if (colIdx < 2) return cols[colIdx]?.regions || [];
      // 最后一栏：合并 col 2 及之后所有列的 regions
      let merged = [];
      for (let c = colIdx; c < cols.length; c++) {
        merged = merged.concat(cols[c]?.regions || []);
      }
      return merged;
    }

    const pageA = `<div class="a3-layout">
      ${renderA3Col(foldGuide + leftColFull)}
      ${colGap}
      ${renderA3Col(renderColumnRegions(sideA.columns[1]?.regions || [], false, 0, 1))}
      ${colGap}
      ${renderA3Col(renderColumnRegions(mergedRegions(sideA, 2), false, 0, 2))}
    </div>`;

    // B面：检测是否有语文作文，有则渲染为统一方格纸
    const allBRegions = sideB.columns.flatMap(c => c.regions || []);
    const cnRegion = allBRegions.find(r => r.qtype === 'essay_cn');
    let pageB;
    if (cnRegion) {
      // 正方形格子，自动计算尺寸填满三栏且总数≈1200
      const colW = 138; // mm（(420-6)/3）
      const colH = 270; // mm（297 减上下 warning/margin）
      const headerH = 18; // mm（题号+标题行）
      const target = cnRegion.charCount || 1200;
      // cellSize² = 3 × colW × colH / target（近似，col0 扣 header）
      const cellSize = Math.floor(Math.sqrt(3 * colW * colH / target) * 10) / 10;
      const perRow = Math.floor(colW / cellSize);
      const rowsCol0 = Math.floor((colH - headerH) / cellSize);
      const rowsOther = Math.floor(colH / cellSize);
      const totalChars = perRow * (rowsCol0 + rowsOther * 2);
      const c0End = rowsCol0 * perRow;
      const c1End = c0End + rowsOther * perRow;
      pageB = `<div class="a3-layout">
        ${renderA3Col(`<div class="col-warning">${WARNING}</div>` + renderCompositionCol(0, totalChars, perRow, rowsCol0, true, cnRegion, cellSize))}
        ${colGap}
        ${renderA3Col(`<div class="col-warning">${WARNING}</div>` + renderCompositionCol(c0End, totalChars, perRow, rowsOther, false, null, cellSize))}
        ${colGap}
        ${renderA3Col(`<div class="col-warning">${WARNING}</div>` + renderCompositionCol(c1End, totalChars, perRow, rowsOther, false, null, cellSize))}
      </div>`;
    } else {
      pageB = `<div class="a3-layout">
        ${renderA3Col(renderColumnRegions(sideB.columns[0]?.regions || [], false, 1, 0))}
        ${colGap}
        ${renderA3Col(renderColumnRegions(sideB.columns[1]?.regions || [], false, 1, 1))}
        ${colGap}
        ${renderA3Col(renderColumnRegions(mergedRegions(sideB, 2), false, 1, 2))}
      </div>`;
    }

    previewWrap.innerHTML = `
      <div class="page-label">A 面（正面）</div>
      <div class="page" data-paper="A3" id="pageA">${pageA}</div>
      <div class="page-label">B 面（背面）</div>
      <div class="page" data-paper="A3" id="pageB">${pageB}</div>
    `;

    applyCSSToPage(previewWrap.querySelector('#pageA'), config);
    applyCSSToPage(previewWrap.querySelector('#pageB'), config);
  } else {
    // A4 布局保留兼容（简化，不展开）
    _renderA4(previewWrap, layout, config, digitBoxes, choiceGroupsHTML, fillHTML);
  }
}

function _renderA4(previewWrap, layout, config, digitBoxes, choiceGroupsHTML, fillHTML) {
  const sideA = layout.sides[0];
  const sideB = layout.sides[1];

  // 为 regions 注入 _side/_col（交互模块需要）
  function tagRegions(side, sideIdx) {
    for (const col of side.columns) {
      for (const r of col.regions) {
        r._side = side.side;
        r._col = col.col;
        r._sideIdx = sideIdx;
      }
    }
  }
  tagRegions(sideA, 0);
  if (sideB) tagRegions(sideB, 1);

  // A 面 col 0 的非 fixed regions
  const aEssayRegions = sideA.columns[0]?.regions?.filter(r => r.type !== 'fixed') || [];

  const pageAContent = `
    <div class="a4-content">
      ${renderFixedRegions(config, digitBoxes, choiceGroupsHTML, fillHTML)}
      <div class="a4-col">
        ${renderColumnRegions(aEssayRegions, false, 0, 0)}
      </div>
    </div>`;

  // B 面：有 regions 时渲染，无 regions 时不渲染 B 面 page [F05 修复]
  let pageBHTML = '';
  if (sideB && sideB.columns) {
    const bRegions = sideB.columns[0]?.regions || [];
    if (bRegions.length > 0) {
      pageBHTML = `
        <div class="page-label">B 面（背面）</div>
        <div class="page" data-paper="A4" id="pageB">
          <div class="a4-content">
            <div class="a4-col a4-col--full">
              ${renderColumnRegions(bRegions, false, 1, 0)}
            </div>
          </div>
        </div>`;
    }
  }

  previewWrap.innerHTML = `
    <div class="page-label">A 面（正面）</div>
    <div class="page" data-paper="A4" id="pageA">${pageAContent}</div>
    ${pageBHTML}`;

  applyCSSToPage(previewWrap.querySelector('#pageA'), config);
  const pageBEl = previewWrap.querySelector('#pageB');
  if (pageBEl) applyCSSToPage(pageBEl, config);
}
