// interact.js — 交互层：分割线拖拽、区域选中、右键菜单
import { splitRegion, mergeRegions, resizeDivider, renumberAll } from './model.js';
import { renderFromLayout } from './render.js';

let selectedRegion = null;
let selectedEl = null;
let abortCtrl = null;

export function initInteraction() {
  // HMR 安全：先清理旧监听器再注册新的
  if (abortCtrl) abortCtrl.abort();
  abortCtrl = new AbortController();
  const signal = abortCtrl.signal;

  initDividerDrag(signal);
  initCutLineDrag(signal);
  initRegionSelection(signal);
  initContextMenu(signal);
  initInlineEdit(signal);
}

// 将可编辑区域的 divider 索引映射到 col.regions 的实际索引
function editableToRealIndex(col, editableIdx) {
  let count = -1;
  for (let i = 0; i < col.regions.length; i++) {
    if (col.regions[i].type !== 'fixed') {
      count++;
      if (count === editableIdx) return i;
    }
  }
  return -1;
}

// ── 分割线拖拽（事件委托到 document） ──
function initDividerDrag(signal) {
  document.addEventListener('mousedown', (e) => {
    const handle = e.target.closest('.divider-handle');
    if (!handle) return;
    e.preventDefault();

    const layout = window._cardLayout;
    if (!layout) return;

    const sideStr = handle.dataset.side;
    const colIdx = parseInt(handle.dataset.col);
    const editableDividerIdx = parseInt(handle.dataset.divider);
    const sideIdx = sideStr === 'B' ? 1 : 0;

    const col = layout.sides[sideIdx].columns[colIdx];
    if (!col) return;
    const upperRealIdx = editableToRealIndex(col, editableDividerIdx);
    const lowerRealIdx = editableToRealIndex(col, editableDividerIdx + 1);
    if (upperRealIdx < 0 || lowerRealIdx < 0) return;

    let lastY = e.clientY;
    const colEl = handle.closest('.a3-col');
    const colHeight = colEl ? colEl.getBoundingClientRect().height : 800;
    const LINE_H_PX = 28; // 一行高度 ≈ 7.5mm @96dpi
    let accumDelta = 0; // 累积像素，达到一行才触发

    handle.classList.add('dragging');

    const onMouseMove = (moveEvt) => {
      accumDelta += moveEvt.clientY - lastY;
      lastY = moveEvt.clientY;
      // snap 到行：累积到整行才触发一次 resize
      const lines = Math.trunc(accumDelta / LINE_H_PX);
      if (lines !== 0) {
        accumDelta -= lines * LINE_H_PX;
        const deltaRatio = (lines * LINE_H_PX) / colHeight;
        resizeDivider(layout, sideIdx, colIdx, upperRealIdx, deltaRatio);
        updateFlexValues(colEl, col);
      }
    };

    const onMouseUp = () => {
      handle.classList.remove('dragging');
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      const v = window._getValues();
      renderFromLayout(window._previewWrap, layout, v);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, { signal });
}

// ── 题内分割线拖拽（在小问之间 snap） ──
function initCutLineDrag(signal) {
  document.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return; // 只响应左键
    const cutEl = e.target.closest('.essay-cut-line');
    if (!cutEl) return;
    e.preventDefault();

    const layout = window._cardLayout;
    if (!layout) return;

    const regionId = cutEl.dataset.region;
    const cutIdx = parseInt(cutEl.dataset.cut);
    const region = findRegion(layout, regionId);
    if (!region || !region.cuts || !region.subs || region.subs.length < 2) return;

    const essayEl = cutEl.closest('.essay-item');
    if (!essayEl) return;

    // 收集所有小问 block 的中点 Y 坐标（用于 snap）
    const subBlocks = essayEl.querySelectorAll('.essay-sub-block');
    const gaps = []; // 小问间隙：{ afterSub, y } — y 是两个小问之间的中点
    for (let i = 0; i < subBlocks.length - 1; i++) {
      const rect1 = subBlocks[i].getBoundingClientRect();
      const rect2 = subBlocks[i + 1].getBoundingClientRect();
      gaps.push({ afterSub: i, y: (rect1.bottom + rect2.top) / 2 });
    }

    cutEl.classList.add('cut-dragging');
    const usedPositions = new Set(region.cuts.filter((_, i) => i !== cutIdx).map(c => c.afterSub));

    const onMove = (moveEvt) => {
      const mouseY = moveEvt.clientY;
      let closest = null;
      let minDist = Infinity;
      for (const gap of gaps) {
        if (usedPositions.has(gap.afterSub)) continue;
        const dist = Math.abs(mouseY - gap.y);
        if (dist < minDist) { minDist = dist; closest = gap; }
      }
      if (closest && closest.afterSub !== region.cuts[cutIdx].afterSub) {
        region.cuts[cutIdx].afterSub = closest.afterSub;
        const targetBlock = subBlocks[closest.afterSub];
        if (targetBlock && targetBlock.nextSibling !== cutEl) {
          targetBlock.after(cutEl);
        }
        cutEl.dataset.afterSub = closest.afterSub;
      }
    };

    const onUp = () => {
      cutEl.classList.remove('cut-dragging');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      const v = window._getValues();
      renderFromLayout(window._previewWrap, layout, v);
      if (window._renderQuestionList) window._renderQuestionList();
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, { signal });
}

// 拖拽中轻量更新：只改 flex 比例，不重建 DOM
function updateFlexValues(colEl, col) {
  if (!colEl) return;
  const regionEls = colEl.querySelectorAll('[data-region-id]');
  const editableRegions = col.regions.filter(r => r.type !== 'fixed');
  for (let i = 0; i < regionEls.length && i < editableRegions.length; i++) {
    regionEls[i].style.flex = `${editableRegions[i].heightRatio} 1 0`;
  }
}

// ── 区域选中（事件委托） ──
function initRegionSelection(signal) {
  document.addEventListener('click', (e) => {
    if (e.target.closest('.ctx-menu')) return;
    if (e.target.closest('.region-props') || e.target.closest('#regionProps')) return;
    if (e.target.closest('.divider-handle')) return;

    // 点击分割线删除按钮
    const cutDelBtn = e.target.closest('.cut-del-btn');
    if (cutDelBtn && cutDelBtn.dataset.region && cutDelBtn.dataset.cut != null) {
      const layout = window._cardLayout;
      if (!layout) return;
      const r = findRegion(layout, cutDelBtn.dataset.region);
      if (r && r.cuts) {
        const cutIdx = parseInt(cutDelBtn.dataset.cut);
        if (cutIdx >= 0 && cutIdx < r.cuts.length) {
          r.cuts.splice(cutIdx, 1);
        }
        if (r.subs) {
          r.cuts = r.cuts.filter(c => typeof c.afterSub === 'number' && c.afterSub >= 0 && c.afterSub < r.subs.length - 1);
        }
        const v = window._getValues();
        renderFromLayout(window._previewWrap, layout, v);
        if (window._renderQuestionList) window._renderQuestionList();
      }
      return;
    }

    // 点击小问删除按钮：整体删除该小问
    const subDelBtn = e.target.closest('.sub-del-btn');
    if (subDelBtn && subDelBtn.dataset.region && subDelBtn.dataset.sub != null) {
      const layout = window._cardLayout;
      if (!layout) return;
      const r = findRegion(layout, subDelBtn.dataset.region);
      const si = parseInt(subDelBtn.dataset.sub);
      if (r && r.subs && si >= 0 && si < r.subs.length) {
        r.subs.splice(si, 1);
        r.subs.forEach((s, i) => { s.sub = i + 1; });
        // 同步分割线
        if (r.cuts) {
          r.cuts = r.cuts
            .filter(c => c.afterSub !== si)
            .map(c => ({ ...c, afterSub: c.afterSub > si ? c.afterSub - 1 : c.afterSub }))
            .filter(c => typeof c.afterSub === 'number' && c.afterSub >= 0 && c.afterSub < r.subs.length - 1);
        }
        const v = window._getValues();
        renderFromLayout(window._previewWrap, layout, v);
        if (window._renderQuestionList) window._renderQuestionList();
      }
      return;
    }

    const regionEl = e.target.closest('[data-region-id]');
    if (regionEl) {
      if (selectedEl) selectedEl.classList.remove('region-selected');
      selectedEl = regionEl;
      regionEl.classList.add('region-selected');
      const layout = window._cardLayout;
      selectedRegion = layout ? findRegion(layout, regionEl.dataset.regionId) : null;
      if (window._onRegionSelect) window._onRegionSelect(selectedRegion, regionEl);
    } else {
      if (selectedEl) selectedEl.classList.remove('region-selected');
      selectedEl = null;
      selectedRegion = null;
      if (window._onRegionSelect) window._onRegionSelect(null, null);
    }
  }, { signal });
}

// ── 右键菜单（事件委托） ──
function initContextMenu(signal) {
  document.addEventListener('contextmenu', (e) => {
    // 空栏占位：右键添加题目
    const emptySlot = e.target.closest('.empty-col-slot');
    if (emptySlot) {
      e.preventDefault();
      document.querySelectorAll('.ctx-menu').forEach(m => m.remove());
      const layout = window._cardLayout;
      if (!layout) return;
      const si = parseInt(emptySlot.dataset.emptySide);
      const ci = parseInt(emptySlot.dataset.emptyCol);
      const targetCol = layout.sides[si]?.columns[ci];
      if (!targetCol) return;
      const menu = document.createElement('div');
      menu.className = 'ctx-menu';
      menu.style.left = e.clientX + 'px';
      menu.style.top = e.clientY + 'px';
      const addItem = document.createElement('div');
      addItem.className = 'ctx-menu-item';
      addItem.textContent = '在此处添加题目';
      addItem.onclick = () => {
        targetCol.regions.push({ id: `essay-new-${Date.now()}`, type: 'essay', qno: 0, score: 12, subs: [], heightRatio: 1.0 });
        renumberAll(layout);
        const v = window._getValues();
        renderFromLayout(window._previewWrap, layout, v);
        if (window._renderQuestionList) window._renderQuestionList();
        menu.remove();
      };
      menu.appendChild(addItem);
      document.body.appendChild(menu);
      return;
    }

    const regionEl = e.target.closest('[data-region-id]');
    if (!regionEl) return;
    e.preventDefault();

    document.querySelectorAll('.ctx-menu').forEach(m => m.remove());

    const layout = window._cardLayout;
    if (!layout) return;

    // 右键下划线：直接删除
    const blankEl = e.target.closest('.essay-line');
    if (blankEl && blankEl.dataset.sub != null && blankEl.dataset.blank != null) {
      const rid = blankEl.dataset.region;
      const si = parseInt(blankEl.dataset.sub);
      const bi = parseInt(blankEl.dataset.blank);
      const r = findRegion(layout, rid);
      if (r && r.subs && r.subs[si] && r.subs[si].blanks && r.subs[si].blanks.length > 0) {
        r.subs[si].blanks.splice(bi, 1);
        const v = window._getValues();
        renderFromLayout(window._previewWrap, layout, v);
        if (window._renderQuestionList) window._renderQuestionList();
      }
      return;
    }

    // 右键小问标签（括号区）：删除整个小问
    const subLabel = e.target.closest('.essay-sub-label');
    if (subLabel && subLabel.dataset.sub != null) {
      const rid = subLabel.dataset.region;
      const si = parseInt(subLabel.dataset.sub);
      const r = findRegion(layout, rid);
      if (r && r.subs && r.subs.length > 0) {
        r.subs.splice(si, 1);
        // 重编小问序号
        r.subs.forEach((s, i) => { s.sub = i + 1; });
        // 同步分割线：删除引用被删小问的分割线，调整后续位置
        if (r.cuts) {
          r.cuts = r.cuts
            .filter(c => c.afterSub !== si) // 删除恰好在被删小问后面的分割线
            .map(c => ({ ...c, afterSub: c.afterSub > si ? c.afterSub - 1 : c.afterSub }))
            .filter(c => c.afterSub >= 0 && c.afterSub < r.subs.length - 1); // 去掉越界的
        }
        const v = window._getValues();
        renderFromLayout(window._previewWrap, layout, v);
        if (window._renderQuestionList) window._renderQuestionList();
      }
      return;
    }

    // 右键题内分割线：直接删除
    const cutEl = e.target.closest('.essay-cut-line');
    if (cutEl && cutEl.dataset.region && cutEl.dataset.cut != null) {
      const r = findRegion(layout, cutEl.dataset.region);
      if (r && r.cuts) {
        const cutIdx = parseInt(cutEl.dataset.cut);
        if (cutIdx >= 0 && cutIdx < r.cuts.length) {
          r.cuts.splice(cutIdx, 1);
        }
        // 清理无效 cuts（旧格式或越界）
        if (r.subs) {
          r.cuts = r.cuts.filter(c => typeof c.afterSub === 'number' && c.afterSub >= 0 && c.afterSub < r.subs.length - 1);
        }
        const v = window._getValues();
        renderFromLayout(window._previewWrap, layout, v);
        if (window._renderQuestionList) window._renderQuestionList();
      }
      return;
    }

    const regionId = regionEl.dataset.regionId;
    const region = findRegion(layout, regionId);

    // 空占位区域：解析 __empty_s{N}c{N} 添加题目到正确的列
    const emptyMatch = regionId.match(/^__empty_s(\d+)c(\d+)$/);
    if (!region && emptyMatch) {
      const si = parseInt(emptyMatch[1]);
      const ci = parseInt(emptyMatch[2]);
      const targetCol = layout.sides[si]?.columns[ci];
      if (!targetCol) return;
      const menu = document.createElement('div');
      menu.className = 'ctx-menu';
      menu.style.left = e.clientX + 'px';
      menu.style.top = e.clientY + 'px';
      const addItem = document.createElement('div');
      addItem.className = 'ctx-menu-item';
      addItem.textContent = '在此处添加题目';
      addItem.onclick = () => {
        targetCol.regions.push({
          id: `essay-new-${Date.now()}`, type: 'essay', qno: 0, score: 12, subs: [],
          heightRatio: 1.0,
        });
        renumberAll(layout);
        const v = window._getValues();
        renderFromLayout(window._previewWrap, layout, v);
        if (window._renderQuestionList) window._renderQuestionList();
        menu.remove();
      };
      menu.appendChild(addItem);
      document.body.appendChild(menu);
      return;
    }

    if (!region || region.type === 'fixed') return;

    const menu = document.createElement('div');
    menu.className = 'ctx-menu';
    menu.style.left = e.clientX + 'px';
    menu.style.top = e.clientY + 'px';

    // 添加题目分割线
    const addSplitItem = document.createElement('div');
    addSplitItem.className = 'ctx-menu-item';
    addSplitItem.textContent = '添加题目分割线（拆为两道题）';
    addSplitItem.onclick = () => {
      const loc = findRegionLocation(layout, regionId);
      if (loc) {
        splitRegion(layout, loc.sideIdx, loc.colIdx, loc.regionIdx);
        const v = window._getValues();
        renderFromLayout(window._previewWrap, layout, v);
        if (window._renderQuestionList) window._renderQuestionList();
      }
      menu.remove();
    };
    menu.appendChild(addSplitItem);

    // 题内分割线（同题号，按小问切割答题区域供阅卷分配）
    if (region.type === 'essay' && region.subs && region.subs.length >= 2) {
      const addCutItem = document.createElement('div');
      addCutItem.className = 'ctx-menu-item';
      addCutItem.textContent = '添加题内分割线（阅卷切割）';
      addCutItem.onclick = () => {
        if (!region.cuts) region.cuts = [];
        // 找一个尚未被占用的小问间隙，默认放中间
        const usedPositions = new Set(region.cuts.map(c => c.afterSub));
        const maxPos = region.subs.length - 1; // 最后一个小问后面不放
        let pos = Math.floor(maxPos / 2);
        // 如果中间已占用，向后找空位
        for (let i = 0; i < maxPos; i++) {
          const candidate = (pos + i) % maxPos;
          if (!usedPositions.has(candidate)) { pos = candidate; break; }
        }
        if (!usedPositions.has(pos)) {
          region.cuts.push({ afterSub: pos });
          const v = window._getValues();
          renderFromLayout(window._previewWrap, layout, v);
          if (window._renderQuestionList) window._renderQuestionList();
        }
        menu.remove();
      };
      menu.appendChild(addCutItem);
    }

    // 删除分割线
    const loc = findRegionLocation(layout, regionId);
    if (loc) {
      const col = layout.sides[loc.sideIdx].columns[loc.colIdx];
      const editablesBefore = col.regions.slice(0, loc.regionIdx + 1).filter(r => r.type !== 'fixed').length;
      if (editablesBefore > 1) {
        const delItem = document.createElement('div');
        delItem.className = 'ctx-menu-item';
        delItem.textContent = '删除此分割线';
        delItem.onclick = () => {
          mergeRegions(layout, loc.sideIdx, loc.colIdx, loc.regionIdx - 1);
          const v = window._getValues();
          renderFromLayout(window._previewWrap, layout, v);
          menu.remove();
        };
        menu.appendChild(delItem);
      }
    }

    // 编辑属性
    const editItem = document.createElement('div');
    editItem.className = 'ctx-menu-item';
    editItem.textContent = '编辑属性';
    editItem.onclick = () => {
      if (selectedEl) selectedEl.classList.remove('region-selected');
      selectedEl = regionEl;
      regionEl.classList.add('region-selected');
      selectedRegion = region;
      if (window._onRegionSelect) window._onRegionSelect(region, regionEl);
      menu.remove();
    };
    menu.appendChild(editItem);

    document.body.appendChild(menu);
  }, { signal });

  document.addEventListener('click', () => {
    document.querySelectorAll('.ctx-menu').forEach(m => m.remove());
  }, { signal });
}

// ── 辅助函数 ──
function findRegion(layout, regionId) {
  for (const side of layout.sides) {
    for (const col of side.columns) {
      for (const r of col.regions) {
        if (r.id === regionId) return r;
      }
    }
  }
  return null;
}

function findRegionLocation(layout, regionId) {
  for (let si = 0; si < layout.sides.length; si++) {
    const side = layout.sides[si];
    for (let ci = 0; ci < side.columns.length; ci++) {
      const col = side.columns[ci];
      for (let ri = 0; ri < col.regions.length; ri++) {
        if (col.regions[ri].id === regionId) {
          return { sideIdx: si, colIdx: ci, regionIdx: ri };
        }
      }
    }
  }
  return null;
}

// ── 内联编辑（双击题号/分值/答题线） ──
function initInlineEdit(signal) {
  // 双击答题区 → 弹出粘贴框或插入横线
  document.addEventListener('dblclick', (e) => {
    const regionEl = e.target.closest('[data-region-id]');
    const lineEl = e.target.closest('.essay-line[data-region]');
    const imgEl = e.target.closest('.sub-img');
    const editableEl = e.target.closest('[contenteditable]');

    // 双击空白答题区（非横线、非图片、非可编辑文字）→ 弹出粘贴框
    if (regionEl && !lineEl && !imgEl && !editableEl) {
      e.preventDefault();
      showPasteDialog(regionEl.dataset.regionId);
      return;
    }

    // 双击横线 → 添加一条线
    if (lineEl) {
      e.preventDefault();
      const regionId = lineEl.dataset.region;
      const subIdx = parseInt(lineEl.dataset.sub) || 0;
      const blankIdx = parseInt(lineEl.dataset.blank) || 0;
      const layout = window._cardLayout;
      if (!layout) return;
      const region = findRegion(layout, regionId);
      if (!region || !region.subs[subIdx]) return;
      const blanks = region.subs[subIdx].blanks;
      if (!blanks) return;
      const currentW = blanks[blankIdx]?.w || '100%';
      blanks.splice(blankIdx + 1, 0, {w: currentW});
      rerender();
      return;
    }
  }, { signal });

  // contenteditable 失焦时同步数据回 model
  document.addEventListener('focusout', (e) => {
    const el = e.target;
    if (!el.hasAttribute('contenteditable')) return;

    const layout = window._cardLayout;
    if (!layout) return;

    const regionId = el.dataset.region;
    if (!regionId) return;
    const region = findRegion(layout, regionId);
    if (!region) return;

    // 题头：解析 "15.（本小题满分 10 分）" 格式
    if (el.classList.contains('essay-item-header')) {
      const text = el.textContent.trim();
      const m = text.match(/^(\d+)/);
      if (m) region.qno = parseInt(m[1]);
      const sm = text.match(/满分\s*(\d+)/);
      if (sm) region.score = parseInt(sm[1]);
    }

    // 小问标题：内容自由编辑，存为自定义文本
    if (el.dataset.edit === 'sub') {
      const subIdx = parseInt(el.dataset.sub) || 0;
      if (region.subs && region.subs[subIdx]) {
        region.subs[subIdx].label = el.textContent.trim();
      }
    }

    // 题目文本：编辑后同步回数据
    if (el.classList.contains('essay-item-text')) {
      const textIdx = parseInt(el.dataset.textIdx) || 0;
      if (region.texts && region.texts[textIdx] !== undefined) {
        const newText = el.textContent.trim();
        if (newText) {
          const obj = region.texts[textIdx];
          if (typeof obj === 'string') {
            region.texts[textIdx] = { content: newText, row: 0, align: 'left' };
          } else {
            obj.content = newText;
          }
        } else {
          region.texts.splice(textIdx, 1);
          rerender();
        }
      }
    }
  }, { signal });

  // 文本块拖拽（和图片一样的自由定位）
  document.addEventListener('mousedown', (e) => {
    const wrap = e.target.closest('.essay-text-wrap');
    if (!wrap) return;
    const delBtn = e.target.closest('.text-del-btn');
    if (delBtn) return;
    // 如果点击在 contenteditable 文字上，不启动拖拽（留给编辑）
    if (e.target.closest('[contenteditable]') && !e.target.closest('.essay-text-wrap > :first-child') === false) {
      // 只在边框区域拖拽，文字区域编辑
    }

    const regionId = wrap.dataset.region;
    const textIdx = parseInt(wrap.dataset.textIdx) || 0;
    const container = wrap.closest('[data-region-id]');
    if (!container) return;
    const containerRect = container.getBoundingClientRect();
    const zoom = (parseFloat(document.getElementById('zoom')?.value) || 60) / 100;

    const startLeft = parseFloat(wrap.style.left) || 0;
    const startTop = parseFloat(wrap.style.top) || 0;
    const startX = e.clientX;
    const startY = e.clientY;
    let moved = false;
    let rafId = null;

    // 行格吸附：11.25mm 一行 (7.5mm高 + 3.75mm间距)
    const containerCSSH = containerRect.height / zoom;
    const lineHeightMM = 11.25;
    const containerHeightMM = containerCSSH / 3.78; // px → mm (96dpi)
    const lineStepPct = (lineHeightMM / containerHeightMM) * 100;

    const snapToLine = (pct) => Math.round(pct / lineStepPct) * lineStepPct;

    const onMove = (me) => {
      if (!moved && Math.abs(me.clientX - startX) < 3 && Math.abs(me.clientY - startY) < 3) return;
      moved = true;
      wrap.classList.add('dragging');
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const dx = ((me.clientX - startX) / containerRect.width) * 100;
        const dy = ((me.clientY - startY) / containerRect.height) * 100;
        const rawX = startLeft + dx;
        const rawY = startTop + dy;
        wrap.style.left = Math.max(0, Math.min(95, rawX)) + '%';
        // Y 吸附到行格
        wrap.style.top = Math.max(0, Math.min(95, snapToLine(rawY))) + '%';
      });
    };
    const onUp = () => {
      if (rafId) cancelAnimationFrame(rafId);
      wrap.classList.remove('dragging');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (!moved) return;
      const layout = window._cardLayout;
      if (layout) {
        const region = findRegion(layout, regionId);
        if (region && region.texts && region.texts[textIdx]) {
          const obj = region.texts[textIdx];
          if (typeof obj === 'object') {
            obj.x = parseFloat(wrap.style.left);
            obj.y = parseFloat(wrap.style.top);
          }
        }
      }
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, { signal });

  // 文本块删除
  document.addEventListener('click', (e) => {
    const delBtn = e.target.closest('.text-del-btn');
    if (!delBtn) return;
    e.stopPropagation();
    const regionId = delBtn.dataset.region;
    const textIdx = parseInt(delBtn.dataset.textIdx) || 0;
    const layout = window._cardLayout;
    if (!layout) return;
    const region = findRegion(layout, regionId);
    if (region && region.texts) {
      region.texts.splice(textIdx, 1);
      rerender();
    }
  }, { signal });

  // 点击「+ 添加小问」— 统一走 panel 的逻辑，预览区按钮只转发
  document.addEventListener('click', (e) => {
    const addBtn = e.target.closest('[data-edit="add-sub"]');
    if (!addBtn) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const regionId = addBtn.dataset.region;
    const layout = window._cardLayout;
    if (!layout) return;
    const region = findRegion(layout, regionId);
    if (!region) return;
    if (!region.subs) region.subs = [];
    region.subs.push({ sub: region.subs.length + 1, blanks: [] });
    const v = window._getValues();
    renderFromLayout(window._previewWrap, layout, v);
    if (window._renderQuestionList) window._renderQuestionList();
  }, { signal });

  // 旧的右键删除逻辑已合并到上方统一 contextmenu 处理器

  // 横线宽度拖拽（拖右边缘）— 三档吸附：30%（短）/ 48%（中）/ 100%（长）
  const WIDTH_STOPS = [30, 48, 100];
  function snapToStop(pct) {
    let closest = WIDTH_STOPS[0], minDist = Infinity;
    for (const s of WIDTH_STOPS) {
      const d = Math.abs(pct - s);
      if (d < minDist) { minDist = d; closest = s; }
    }
    return closest;
  }

  document.addEventListener('mousedown', (e) => {
    const lineEl = e.target.closest('.essay-line[data-region]');
    if (!lineEl) return;
    const rect = lineEl.getBoundingClientRect();
    if (e.clientX < rect.right - 8) return;
    e.preventDefault();

    const regionId = lineEl.dataset.region;
    const subIdx = parseInt(lineEl.dataset.sub) || 0;
    const blankIdx = parseInt(lineEl.dataset.blank) || 0;
    const parentWidth = lineEl.parentElement.getBoundingClientRect().width;

    const onMove = (me) => {
      const rawPct = Math.max(15, Math.min(100, ((me.clientX - rect.left) / parentWidth) * 100));
      const snapped = snapToStop(rawPct);
      lineEl.style.width = snapped + '%';
    };
    const onUp = (me) => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      const rawPct = Math.max(15, Math.min(100, ((me.clientX - rect.left) / parentWidth) * 100));
      const snapped = snapToStop(rawPct);
      lineEl.style.width = snapped + '%';
      const layout = window._cardLayout;
      if (layout) {
        const region = findRegion(layout, regionId);
        if (region && region.subs[subIdx] && region.subs[subIdx].blanks) {
          region.subs[subIdx].blanks[blankIdx] = {w: snapped + '%'};
        }
      }
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, { signal });

  // 图片自由拖拽定位
  document.addEventListener('mousedown', (e) => {
    const wrap = e.target.closest('.sub-img-wrap');
    if (!wrap) return;
    const resizeHandle = e.target.closest('.img-resize-handle');
    const delBtn = e.target.closest('.img-del-btn');
    if (delBtn) return; // 删除按钮单独处理

    e.preventDefault();
    const regionId = wrap.dataset.region;
    const si = parseInt(wrap.dataset.sub) || 0;
    const container = wrap.closest('[data-region-id]');
    if (!container) return;
    const containerRect = container.getBoundingClientRect();

    let rafId = null;
    // 获取 zoom 缩放比，补偿缩放对鼠标位移的影响
    const zoom = (parseFloat(document.getElementById('zoom')?.value) || 60) / 100;

    if (resizeHandle) {
      // 缩放模式：记录初始宽度，用鼠标水平位移直接映射
      const startWpct = parseFloat(wrap.style.width) || 35;
      const startMouseX = e.clientX;
      // 容器的 CSS 原始宽度（未缩放）= 实际像素宽 / zoom
      const containerCSSWidth = containerRect.width / zoom;
      wrap.style.transition = 'none';

      const onMove = (me) => {
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(() => {
          const dx = me.clientX - startMouseX;
          // 补偿 zoom：鼠标位移 / zoom = CSS 空间位移
          const cssDx = dx / zoom;
          const pctDelta = (cssDx / containerCSSWidth) * 100;
          const newW = startWpct + pctDelta;
          wrap.style.width = Math.max(5, Math.min(95, newW)) + '%';
        });
      };
      const onUp = () => {
        if (rafId) cancelAnimationFrame(rafId);
        wrap.style.transition = '';
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        const layout = window._cardLayout;
        if (layout) {
          const region = findRegion(layout, regionId);
          if (region && region.subs[si] && region.subs[si].image) {
            region.subs[si].image.w = parseFloat(wrap.style.width);
          }
        }
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    } else {
      // 拖拽移动模式：RAF 节流 + zoom 补偿
      wrap.classList.add('dragging');
      wrap.style.transition = 'none';
      const startLeft = parseFloat(wrap.style.left) || 0;
      const startTop = parseFloat(wrap.style.top) || 0;
      const startX = e.clientX;
      const startY = e.clientY;
      const containerCSSW = containerRect.width / zoom;
      const containerCSSH = containerRect.height / zoom;

      const onMove = (me) => {
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(() => {
          const dx = ((me.clientX - startX) / zoom / containerCSSW) * 100;
          const dy = ((me.clientY - startY) / zoom / containerCSSH) * 100;
          wrap.style.left = Math.max(0, Math.min(85, startLeft + dx)) + '%';
          wrap.style.top = Math.max(0, Math.min(95, startTop + dy)) + '%';
        });
      };
      const onUp = () => {
        if (rafId) cancelAnimationFrame(rafId);
        wrap.classList.remove('dragging');
        wrap.style.transition = '';
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        const layout = window._cardLayout;
        if (layout) {
          const region = findRegion(layout, regionId);
          if (region && region.subs[si] && region.subs[si].image) {
            region.subs[si].image.x = parseFloat(wrap.style.left);
            region.subs[si].image.y = parseFloat(wrap.style.top);
          }
        }
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    }
  }, { signal });

  // 图片删除按钮
  document.addEventListener('click', (e) => {
    const delBtn = e.target.closest('.img-del-btn');
    if (!delBtn) return;
    e.stopPropagation();
    const regionId = delBtn.dataset.region;
    const si = parseInt(delBtn.dataset.sub) || 0;
    const layout = window._cardLayout;
    if (!layout) return;
    const region = findRegion(layout, regionId);
    if (region && region.subs[si]) {
      delete region.subs[si].image;
      rerender();
      if (window._renderQuestionList) window._renderQuestionList();
    }
  }, { signal });
}

// ── 粘贴图片对话框 ──
function showPasteDialog(regionId) {
  // 移除已有对话框
  document.querySelectorAll('.paste-dialog').forEach(d => d.remove());

  const layout = window._cardLayout;
  if (!layout) return;
  const region = findRegion(layout, regionId);
  if (!region || region.type === 'fixed') return;

  const dialog = document.createElement('div');
  dialog.className = 'paste-dialog';
  dialog.innerHTML = `
    <div class="paste-dialog-inner">
      <div class="paste-dialog-title">插入内容</div>
      <div class="paste-area" contenteditable="true" data-placeholder="Ctrl+V 粘贴图片或文字"></div>
      <div class="paste-btns">
        <label class="paste-file-label">
          <input type="file" class="paste-file-input" accept="image/*" hidden>
          选择图片文件
        </label>
        <button class="paste-cancel">取消</button>
      </div>
    </div>
  `;
  document.body.appendChild(dialog);

  const pasteArea = dialog.querySelector('.paste-area');
  const fileInput = dialog.querySelector('.paste-file-input');

  // contenteditable div 自动获焦，可以直接 Ctrl+V
  requestAnimationFrame(() => {
    pasteArea.focus();
  });

  function insertImage(dataUrl) {
    if (!region.subs || region.subs.length === 0) {
      region.subs = [{ sub: 1, blanks: [{w:'100%'}] }];
    }
    region.subs[0].image = { src: dataUrl, x: 60, y: 5, w: 35 };
    rerender();
    if (window._renderQuestionList) window._renderQuestionList();
    dialog.remove();
  }

  // Ctrl+V 粘贴（图片或文本）
  pasteArea.addEventListener('paste', (e) => {
    e.preventDefault();
    const items = e.clipboardData?.items;
    if (!items) return;

    // 优先检查图片
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        const reader = new FileReader();
        reader.onload = () => insertImage(reader.result);
        reader.readAsDataURL(file);
        return;
      }
    }

    // 其次检查文本
    const text = e.clipboardData.getData('text/plain');
    if (text) {
      insertText(text);
      return;
    }
  });

  function insertText(text) {
    if (!region.texts) region.texts = [];
    region.texts.push({ content: text, row: 0, align: 'left' });
    rerender();
    if (window._renderQuestionList) window._renderQuestionList();
    dialog.remove();
  }

  // 选择文件按钮（独立，不和 paste area 冲突）
  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => insertImage(reader.result);
    reader.readAsDataURL(file);
  });

  // 取消
  dialog.querySelector('.paste-cancel').addEventListener('click', () => dialog.remove());
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.remove();
  });
  // ESC 关闭
  const onKey = (e) => {
    if (e.key === 'Escape') { dialog.remove(); document.removeEventListener('keydown', onKey); }
  };
  document.addEventListener('keydown', onKey);
}

function rerender() {
  const layout = window._cardLayout;
  if (!layout) return;
  const v = window._getValues();
  renderFromLayout(window._previewWrap, layout, v);
}

// 暴露给主页面
window._initInteraction = initInteraction;
