// panel.js — 题目列表 + 选中区域属性编辑面板
import { renderFromLayout } from './render.js';
import { renumberAll } from './model.js';

let currentRegion = null;
let currentEl = null;

export function initPanel() {
  const propsDiv = document.getElementById('regionProps');
  if (!propsDiv) return;

  // 渲染题目列表
  renderQuestionList();

  // 添加题目按钮
  document.getElementById('btnAddQuestion')?.addEventListener('click', () => {
    const layout = window._cardLayout;
    if (!layout) return;
    // 找最后一个有空间的栏，添加新题目
    for (let si = layout.sides.length - 1; si >= 0; si--) {
      const side = layout.sides[si];
      for (let ci = side.columns.length - 1; ci >= 0; ci--) {
        const col = side.columns[ci];
        const editables = col.regions.filter(r => r.type !== 'fixed');
        if (editables.length > 0) {
          // 在最后一栏的最后一个区域后分割
          const lastIdx = col.regions.indexOf(editables[editables.length - 1]);
          const lastRegion = col.regions[lastIdx];
          const newRatio = lastRegion.heightRatio / 2;
          lastRegion.heightRatio = newRatio;
          col.regions.push({
            id: `essay-new-${Date.now()}`,
            type: 'essay',
            qno: 0,
            score: 10,
            subs: [{ sub: 1, blanks: [{w:'100%'},{w:'100%'},{w:'100%'}] }],
            heightRatio: newRatio,
          });
          renumberAll(layout);
          rerender();
          renderQuestionList();
          return;
        }
      }
    }
  });

  // 监听区域选中
  window._onRegionSelect = (region, el) => {
    currentRegion = region;
    currentEl = el;
    renderPanel(propsDiv, region);
    highlightQuestionItem(region?.id);
  };
}

let expandedId = null; // 当前展开的题目

function renderQuestionList() {
  const listDiv = document.getElementById('questionList');
  if (!listDiv) return;
  const layout = window._cardLayout;
  if (!layout) { listDiv.innerHTML = '<div class="hint">未加载布局</div>'; return; }

  let html = '';
  let lastType = '';

  for (const side of layout.sides) {
    for (const col of side.columns) {
      for (const r of col.regions) {
        if (r.type === 'fixed') continue;
        if (r.type !== lastType && lastType) html += '<div class="q-separator"></div>';
        lastType = r.type;

        const qtype = r.qtype || (r.type === 'fill' ? 'fill' : 'essay');
        const isExpanded = r.id === expandedId;
        const subCount = r.subs ? r.subs.length : 0;
        const scoreMeta = r.score ? `${r.score}分` : '';
        const subMeta = subCount > 0 ? `${subCount}问` : '';
        const meta = [scoreMeta, subMeta].filter(Boolean).join(' · ');

        html += `<div class="q-item ${isExpanded ? 'selected' : ''}" data-q-id="${r.id}">
          <span class="q-label">${r.qno}.</span>
          <select class="q-type-sel" data-q-id="${r.id}">
            <option value="fill" ${qtype === 'fill' ? 'selected' : ''}>填空题</option>
            <option value="essay" ${qtype === 'essay' ? 'selected' : ''}>解答题</option>
            <option value="essay_en" ${qtype === 'essay_en' ? 'selected' : ''}>英语作文</option>
            <option value="essay_cn" ${qtype === 'essay_cn' ? 'selected' : ''}>语文作文</option>
            <option value="proof" ${qtype === 'proof' ? 'selected' : ''}>证明题</option>
            <option value="experiment" ${qtype === 'experiment' ? 'selected' : ''}>实验题</option>
          </select>
          <input type="number" class="q-score-inline" data-q-id="${r.id}" value="${r.score || 0}" min="0" max="99" title="分值"><span class="q-unit">分</span>
          <span class="q-meta">${subMeta}</span>
          <span class="q-del" data-q-del="${r.id}" title="删除">×</span>
        </div>`;

        // 展开区域：编辑小问和空
        if (isExpanded) {
          html += renderQuestionDetail(r);
        }
      }
    }
  }
  listDiv.innerHTML = html;
  bindQuestionListEvents(listDiv);
}

function renderQuestionDetail(region) {
  const subs = region.subs || [];
  let html = '<div class="q-detail">';

  // 小问列表（无分值行、无插入图片）
  for (let si = 0; si < subs.length; si++) {
    const s = subs[si];
    const blanks = s.blanks || [{w:'100%'}];

    html += `<div class="q-sub">
      <div class="q-sub-header">
        <span>第${si + 1}问</span>
        <span class="q-sub-del" data-rid="${region.id}" data-si="${si}" title="删除小问">×</span>
      </div>
      <div class="q-blanks">`;

    for (let bi = 0; bi < blanks.length; bi++) {
      const b = blanks[bi];
      const size = blankWidthToSize(b.w);
      const label = b.label || '';
      html += `<div class="q-blank-row">
        <span class="q-blank-label">空${bi + 1}</span>
        <select class="q-blank-size" data-rid="${region.id}" data-si="${si}" data-bi="${bi}">
          <option value="short" ${size === 'short' ? 'selected' : ''}>短(⅓)</option>
          <option value="medium" ${size === 'medium' ? 'selected' : ''}>中(½)</option>
          <option value="long" ${size === 'long' ? 'selected' : ''}>长(整行)</option>
        </select>
        <select class="q-blank-marker" data-rid="${region.id}" data-si="${si}" data-bi="${bi}">
          <option value="" ${!label ? 'selected' : ''}>无标</option>
          <option value="①" ${label === '①' ? 'selected' : ''}>①</option>
          <option value="②" ${label === '②' ? 'selected' : ''}>②</option>
          <option value="③" ${label === '③' ? 'selected' : ''}>③</option>
          <option value="④" ${label === '④' ? 'selected' : ''}>④</option>
          <option value="⑤" ${label === '⑤' ? 'selected' : ''}>⑤</option>
          <option value="⑥" ${label === '⑥' ? 'selected' : ''}>⑥</option>
        </select>
        <span class="q-blank-del" data-rid="${region.id}" data-si="${si}" data-bi="${bi}" title="删除空">×</span>
      </div>`;
    }

    html += `<button class="q-add-blank" data-rid="${region.id}" data-si="${si}">+ 添加空</button>`;
    html += `</div>
    </div>`;
  }

  html += `<button class="q-add-sub" data-rid="${region.id}">+ 添加小问</button>`;
  html += '</div>';
  return html;
}

function blankWidthToSize(w) {
  const pct = parseInt(w) || 100;
  if (pct <= 35) return 'short';
  if (pct <= 55) return 'medium';
  return 'long';
}

function sizeToBlankWidth(size) {
  if (size === 'short') return '30%';
  if (size === 'medium') return '48%';
  return '100%';
}

function findRegionById(layout, id) {
  for (const side of layout.sides) {
    for (const col of side.columns) {
      for (const r of col.regions) {
        if (r.id === id) return r;
      }
    }
  }
  return null;
}

function bindQuestionListEvents(listDiv) {
  // 点击题目 → 展开/折叠 + 高亮预览
  listDiv.querySelectorAll('.q-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.closest('.q-del')) return;
      const id = item.dataset.qId;
      expandedId = (expandedId === id) ? null : id;
      renderQuestionList();
      // 高亮预览
      document.querySelectorAll('.region-selected').forEach(el => el.classList.remove('region-selected'));
      const previewEl = document.querySelector(`[data-region-id="${id}"]`);
      if (previewEl) {
        previewEl.classList.add('region-selected');
        previewEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  });

  // 删除题目
  listDiv.querySelectorAll('.q-del').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteQuestion(btn.dataset.qDel);
    });
  });

  // 题型下拉框
  listDiv.querySelectorAll('.q-type-sel').forEach(sel => {
    sel.addEventListener('change', (e) => {
      e.stopPropagation();
      const r = findRegionById(window._cardLayout, e.target.dataset.qId);
      if (r) { r.qtype = e.target.value; rerender(); }
    });
    sel.addEventListener('click', (e) => e.stopPropagation());
  });

  // 行内分值修改
  listDiv.querySelectorAll('.q-score-inline').forEach(input => {
    input.addEventListener('input', (e) => {
      e.stopPropagation();
      const r = findRegionById(window._cardLayout, e.target.dataset.qId);
      if (r) { r.score = parseInt(e.target.value) || 0; rerender(); }
    });
    input.addEventListener('click', (e) => e.stopPropagation());
  });

  // 空大小修改
  listDiv.querySelectorAll('.q-blank-size').forEach(sel => {
    sel.addEventListener('change', (e) => {
      const { rid, si, bi } = e.target.dataset;
      const r = findRegionById(window._cardLayout, rid);
      if (r && r.subs[si] && r.subs[si].blanks[bi]) {
        r.subs[si].blanks[bi].w = sizeToBlankWidth(e.target.value);
        rerender();
      }
    });
  });

  // 圈号标记
  listDiv.querySelectorAll('.q-blank-marker').forEach(sel => {
    sel.addEventListener('change', (e) => {
      const { rid, si, bi } = e.target.dataset;
      const r = findRegionById(window._cardLayout, rid);
      if (r && r.subs[si] && r.subs[si].blanks[bi]) {
        r.subs[si].blanks[bi].label = e.target.value;
        rerender();
      }
    });
  });

  // 删除空
  listDiv.querySelectorAll('.q-blank-del').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const { rid, si, bi } = btn.dataset;
      const r = findRegionById(window._cardLayout, rid);
      if (r && r.subs[si] && r.subs[si].blanks.length > 1) {
        r.subs[si].blanks.splice(parseInt(bi), 1);
        rerender();
        renderQuestionList();
      }
    });
  });

  // 添加空
  listDiv.querySelectorAll('.q-add-blank').forEach(btn => {
    btn.addEventListener('click', () => {
      const { rid, si } = btn.dataset;
      const r = findRegionById(window._cardLayout, rid);
      if (r && r.subs[si]) {
        r.subs[si].blanks.push({w: '100%'});
        rerender();
        renderQuestionList();
      }
    });
  });

  // 添加小问
  listDiv.querySelectorAll('.q-add-sub').forEach(btn => {
    btn.addEventListener('click', () => {
      const r = findRegionById(window._cardLayout, btn.dataset.rid);
      if (r) {
        if (!r.subs) r.subs = [];
        r.subs.push({ sub: r.subs.length + 1, blanks: [{w:'100%'},{w:'100%'},{w:'100%'}] });
        rerender();
        renderQuestionList();
      }
    });
  });

  // 删除小问
  listDiv.querySelectorAll('.q-sub-del').forEach(btn => {
    btn.addEventListener('click', () => {
      const { rid, si } = btn.dataset;
      const r = findRegionById(window._cardLayout, rid);
      if (r && r.subs) {
        r.subs.splice(parseInt(si), 1);
        r.subs.forEach((s, i) => s.sub = i + 1);
        rerender();
        renderQuestionList();
      }
    });
  });

}

function highlightQuestionItem(id) {
  document.querySelectorAll('.q-item').forEach(el => {
    el.classList.toggle('selected', el.dataset.qId === id);
  });
}

function deleteQuestion(id) {
  const layout = window._cardLayout;
  if (!layout) return;
  for (const side of layout.sides) {
    for (const col of side.columns) {
      const idx = col.regions.findIndex(r => r.id === id);
      if (idx >= 0 && col.regions[idx].type !== 'fixed') {
        const editables = col.regions.filter(r => r.type !== 'fixed');
        if (editables.length <= 1) return; // 至少保留1个可编辑区域
        // 把高度还给相邻区域
        const removed = col.regions[idx];
        col.regions.splice(idx, 1);
        const neighbor = col.regions.find(r => r.type !== 'fixed');
        if (neighbor) neighbor.heightRatio += removed.heightRatio;
        renumberAll(layout);
        rerender();
        renderQuestionList();
        renderPanel(document.getElementById('regionProps'), null);
        return;
      }
    }
  }
}

// 暴露给外部刷新
window._renderQuestionList = renderQuestionList;

function renderPanel(container, region) {
  if (!region) {
    container.innerHTML = '<div class="hint">点击答题区域进行编辑</div>';
    return;
  }

  if (region.type === 'fixed') {
    container.innerHTML = '<div class="hint">此区域不可编辑</div>';
    return;
  }

  const subs = region.subs || [{ sub: 1, blanks: [{w:'100%'},{w:'100%'},{w:'100%'}] }];

  let subsHTML = '';
  for (let i = 0; i < subs.length; i++) {
    const s = subs[i];
    const blanks = s.blanks || [{w:'100%'}];
    const blanksDesc = blanks.map((b,j) => `${j+1}:${parseInt(b.w)}%`).join(' ');
    subsHTML += `
      <div class="sub-row">
        <label>小问${i + 1}</label>
        <label>空数 ${blanks.length}</label>
        <span style="font-size:10px;color:#888;">${blanksDesc}</span>
      </div>
    `;
  }

  container.innerHTML = `
    <div class="ctrl">
      <label>题号</label>
      <input type="number" id="propQno" value="${region.qno || 0}" min="0" max="99" style="width:50px">
    </div>
    <div class="ctrl">
      <label>分值</label>
      <input type="number" id="propScore" value="${region.score || 0}" min="0" max="99" style="width:50px">
    </div>
    <div class="ctrl">
      <label>小问数</label>
      <input type="number" id="propSubCount" value="${subs.length}" min="1" max="10" style="width:50px">
    </div>
    <div id="subRows">${subsHTML}</div>
  `;

  // 绑定事件
  document.getElementById('propQno').addEventListener('input', (e) => {
    region.qno = parseInt(e.target.value) || 0;
    rerender();
  });

  document.getElementById('propScore').addEventListener('input', (e) => {
    region.score = parseInt(e.target.value) || 0;
    rerender();
  });

  document.getElementById('propSubCount').addEventListener('input', (e) => {
    const count = parseInt(e.target.value) || 1;
    while (region.subs.length < count) {
      region.subs.push({ sub: region.subs.length + 1, blanks: [{w:'100%'},{w:'100%'},{w:'100%'}] });
    }
    while (region.subs.length > count) {
      region.subs.pop();
    }
    rerender();
    renderPanel(container, region);
  });

  // 空的编辑通过可视化操作完成：
  // 双击横线=添加 | 右键横线=删除 | 拖右边缘=改宽度
}

function rerender() {
  const layout = window._cardLayout;
  if (!layout) return;
  const v = window._getValues();
  renderFromLayout(window._previewWrap, layout, v);
  if (window._initInteraction) window._initInteraction();
  updateScoreCheck();
}

function updateScoreCheck() {
  const el = document.getElementById('totalScoreCheck');
  if (!el) return;
  const layout = window._cardLayout;
  if (!layout) return;

  let total = 0;
  let details = [];
  for (const side of layout.sides) {
    for (const col of side.columns) {
      for (const r of col.regions) {
        if (r.type === 'essay' && r.score) {
          total += r.score;
          details.push(`${r.qno}题${r.score}分`);
        }
      }
    }
  }

  // 常见满分: 150(语文/数学), 100(理综单科), 120(英语)
  const common = [100, 120, 150];
  const isCommon = common.includes(total);

  el.className = 'score-check ' + (isCommon ? 'ok' : 'warn');
  el.textContent = `解答题合计: ${total}分` + (isCommon ? ' ✓' : ' ⚠ 请确认是否正确');
}

// 暴露
window._initPanel = initPanel;
