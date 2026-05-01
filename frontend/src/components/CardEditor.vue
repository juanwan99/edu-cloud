<template>
  <div class="card-editor-wrapper" :class="{ 'tql-mode': viewMode === 'tql' }">
    <button class="panel-toggle" ref="panelToggleRef" title="收起/展开面板" @click="togglePanel">‹</button>
    <div class="panel" ref="panelRef">
      <!-- 选择题 -->
      <h2><i class="ico ico-grid"></i> 选择题</h2>
      <div class="ctrl">
        <label>快速生成</label>
        <input type="number" id="choiceQuickCount" value="11" min="1" max="30" style="width:40px">
        <span style="color:#5a6b5e;font-size: 16px;">题 ×</span>
        <input type="number" id="choiceQuickOptions" value="4" min="2" max="8" style="width:40px">
        <span style="color:#5a6b5e;font-size: 16px;">选项</span>
        <button class="choice-gen-btn" id="choiceGenBtn">生成</button>
      </div>
      <div id="choiceList" class="choice-list"></div>
      <div class="ctrl"><label>每行题数</label><input type="range" id="choicePerRow" min="1" max="20" value="20"><span class="val" id="v_choicePerRow"></span></div>
      <div class="ctrl"><label>选项行距</label><input type="range" id="choiceRowGap" min="0" max="20" value="3" step="1"><span class="val" id="v_choiceRowGap"></span></div>
      <button class="panel-btn" id="btnAddChoice" style="font-size: 16px;padding:5px;">+ 添加选择题</button>

      <!-- 填空题 & 解答题 -->
      <h2><i class="ico ico-layers"></i> 填空题 & 解答题</h2>
      <div id="questionList" class="question-list"></div>
      <button id="btnAddQuestion" class="panel-btn">+ 添加题目</button>
      <div id="totalScoreCheck" class="score-check"></div>

      <!-- 选中题目属性 -->
      <h2><i class="ico ico-edit"></i> 选中题目</h2>
      <div class="region-props" id="regionProps">
        <div class="hint">点击左侧题目或预览区域</div>
      </div>

      <!-- 导出（内部按钮，由外部工具栏触发） -->
      <button id="btnExportPdf" style="display:none"></button>
      <button id="btnExportSkeleton" class="panel-btn" style="font-size: 16px;padding:4px;">导出 Skeleton</button>
      <div id="status" class="status"></div>

      <!-- 缩放 -->
      <div class="ctrl" style="margin-top:8px;"><label>缩放(%)</label><input type="range" id="zoom" min="20" max="100" value="60"><span class="val" id="v_zoom"></span></div>

      <!-- 高级选项 -->
      <details class="advanced-section">
        <summary><i class="ico ico-settings"></i> 高级选项</summary>

        <h2><i class="ico ico-type"></i> 标题区</h2>
        <div class="ctrl"><label>考试名称</label><input type="text" id="examTitle" :value="cardTitle || '考试答题卡'"></div>
        <div class="ctrl"><label>科目</label><input type="text" id="subjectTitle" :value="subjectName || ''"></div>
        <div class="ctrl"><label>标题字号(pt)</label><input type="range" id="titleSize" min="12" max="24" value="16"><span class="val" id="v_titleSize"></span></div>
        <div class="ctrl"><label>副标题字号(pt)</label><input type="range" id="subtitleSize" min="16" max="30" value="22"><span class="val" id="v_subtitleSize"></span></div>
        <div class="ctrl"><label>标题字距(px)</label><input type="range" id="titleSpacing" min="0" max="8" value="1"><span class="val" id="v_titleSpacing"></span></div>
        <div class="ctrl"><label>副标题字距(px)</label><input type="range" id="subtitleSpacing" min="0" max="12" value="6"><span class="val" id="v_subtitleSpacing"></span></div>
        <div class="ctrl"><label>标题下间距(mm)</label><input type="range" id="titleGap" min="0" max="8" value="2" step="0.5"><span class="val" id="v_titleGap"></span></div>
        <div class="ctrl"><label>副标题下间距(mm)</label><input type="range" id="subtitleGap" min="0" max="8" value="3" step="0.5"><span class="val" id="v_subtitleGap"></span></div>

        <h2><i class="ico ico-user"></i> 学生信息区</h2>
        <div class="ctrl"><label>信息区高度(mm)</label><input type="range" id="infoHeight" min="16" max="36" value="24" step="0.5"><span class="val" id="v_infoHeight"></span></div>
        <div class="ctrl"><label>信息区内边距(mm)</label><input type="range" id="infoPadding" min="1" max="6" value="4" step="0.5"><span class="val" id="v_infoPadding"></span></div>
        <div class="ctrl"><label>行间距(mm)</label><input type="range" id="infoRowGap" min="1" max="8" value="4" step="0.5"><span class="val" id="v_infoRowGap"></span></div>
        <div class="ctrl"><label>字号(pt)</label><input type="range" id="infoFontSize" min="9" max="16" value="12"><span class="val" id="v_infoFontSize"></span></div>
        <div class="ctrl"><label>边框粗细(px)</label><input type="range" id="infoBorderWidth" min="0.5" max="3" value="1" step="0.25"><span class="val" id="v_infoBorderWidth"></span></div>
        <div class="ctrl"><label>姓名横线宽(%)</label><input type="range" id="nameLineWidth" min="20" max="60" value="35" step="1"><span class="val" id="v_nameLineWidth"></span></div>
        <div class="ctrl"><label>准考证号位数</label><input type="range" id="digitCount" min="6" max="15" value="9"><span class="val" id="v_digitCount"></span></div>
        <div class="ctrl"><label>方格大小(mm)</label><input type="range" id="digitBoxSize" min="3" max="6" value="4.5" step="0.25"><span class="val" id="v_digitBoxSize"></span></div>
        <div class="ctrl"><label>方格间距(mm)</label><input type="range" id="digitGap" min="0" max="2" value="0.8" step="0.1"><span class="val" id="v_digitGap"></span></div>
        <div class="ctrl"><label>条形码区宽(%)</label><input type="range" id="barcodeWidthPct" min="25" max="55" value="40"><span class="val" id="v_barcodeWidthPct"></span></div>
        <div class="ctrl"><label>条形码标题字号</label><input type="range" id="barcodeTitleSize" min="8" max="16" value="12"><span class="val" id="v_barcodeTitleSize"></span></div>

        <h2><i class="ico ico-info"></i> 注意事项</h2>
        <div class="ctrl"><label>高度(mm)</label><input type="range" id="noticeHeight" min="18" max="40" value="28" step="0.5"><span class="val" id="v_noticeHeight"></span></div>
        <div class="ctrl"><label>标签列宽(mm)</label><input type="range" id="noticeLabelWidth" min="5" max="12" value="8" step="0.5"><span class="val" id="v_noticeLabelWidth"></span></div>
        <div class="ctrl"><label>标签字号(pt)</label><input type="range" id="noticeLabelSize" min="8" max="14" value="11"><span class="val" id="v_noticeLabelSize"></span></div>
        <div class="ctrl"><label>正文字号(pt)</label><input type="range" id="noticeFontSize" min="6" max="10" value="8" step="0.5"><span class="val" id="v_noticeFontSize"></span></div>
        <div class="ctrl"><label>示例列宽(mm)</label><input type="range" id="exampleWidth" min="8" max="18" value="12" step="0.5"><span class="val" id="v_exampleWidth"></span></div>
        <div class="ctrl"><label>边框粗细(px)</label><input type="range" id="noticeBorderWidth" min="0.5" max="3" value="1" step="0.25"><span class="val" id="v_noticeBorderWidth"></span></div>

        <h2><i class="ico ico-shield"></i> 缺考标记</h2>
        <div class="ctrl"><label>上下间距(mm)</label><input type="range" id="absentPadding" min="0" max="4" value="1.5" step="0.25"><span class="val" id="v_absentPadding"></span></div>

        <h2><i class="ico ico-edit"></i> 填空题</h2>
        <div class="ctrl"><label>题数</label><input type="range" id="fillCount" min="0" max="10" value="3"><span class="val" id="v_fillCount"></span></div>
        <div class="ctrl"><label>每题分值</label><input type="number" id="fillScore" min="1" max="20" value="5" style="width:50px"><span class="val" id="v_fillScore"></span></div>
        <div class="ctrl"><label>每排几题</label><input type="range" id="fillPerRow" min="1" max="4" value="2"><span class="val" id="v_fillPerRow"></span></div>
        <div class="ctrl" style="color:#888;font-size: 16px;">题号自动：选择题1~N → 填空N+1起 → 解答题继续</div>

        <h2><i class="ico ico-file"></i> 解答题</h2>
        <div class="ctrl"><label>题数</label><input type="range" id="essayCount" min="1" max="20" value="5"><span class="val" id="v_essayCount"></span></div>
        <div class="ctrl"><label>题目配置(JSON)</label></div>
        <textarea id="essayConfig" style="width:100%;height:60px;background:#0f3460;color:#eee;border:1px solid #555;font-size: 16px;padding:4px;" spellcheck="false">[{"score":10},{"score":12},{"score":12},{"score":12},{"score":14}]</textarea>

        <h2><i class="ico ico-file"></i> 纸张</h2>
        <div class="ctrl"><label>纸张</label>
          <select id="paperSize" style="background:#0f3460;color:#eee;border:1px solid #555;padding:2px;">
            <option value="A4">A4 (210mm)</option>
            <option value="A3">A3 (420mm)</option>
          </select>
        </div>
      </details>

      <div v-if="readonly" style="margin-top: 12px; padding: 8px; background: #fff3cd; border-radius: 6px; font-size: 16px; color: #856404;">
        答题卡已发布，当前为只读模式
      </div>
    </div>

    <!-- 预览区：编辑器 / TQL 切换 -->
    <div class="preview-area">
      <div v-if="subjectId" class="view-toggle">
        <button :class="{ active: viewMode === 'editor' }" @click="viewMode = 'editor'">编辑器</button>
        <button :class="{ active: viewMode === 'tql' }" @click="switchToTql">TQL 模板</button>
        <button v-if="viewMode === 'editor'" class="fit-zoom-btn" :class="{ active: isFitMode }" @click="toggleFitMode">{{ isFitMode ? '适应' : '1:1' }}</button>
      </div>
      <div v-show="viewMode === 'editor'" class="preview-wrap" id="previewWrap" ref="previewWrapRef"></div>
      <div v-if="viewMode === 'tql'" class="tql-view">
        <div v-if="tqlImages[0]" class="tql-img-wrap">
          <div class="tql-label">A 面</div>
          <img :src="'data:image/png;base64,' + tqlImages[0]">
        </div>
        <div v-if="tqlImages[1]" class="tql-img-wrap">
          <div class="tql-label">B 面</div>
          <img :src="'data:image/png;base64,' + tqlImages[1]">
        </div>
        <div v-if="!tqlImages[0] && !tqlImages[1] && !tqlLoading" style="color:#999;font-size: 16px;padding:40px;text-align:center;">
          该科目无 TQL 模板图
        </div>
        <div v-if="tqlLoading" style="color:#999;font-size: 16px;padding:40px;text-align:center;">
          加载中...
        </div>
      </div>
    </div>

    <input type="file" id="hiddenImgInput" accept="image/*" style="display:none">
    <div class="status" id="status">就绪</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps({
  examId: { type: String, required: true },
  subjectId: { type: String, default: null },
  subjectName: { type: String, default: '' },
  cardTitle: { type: String, default: '' },
  readonly: { type: Boolean, default: false },
  pendingQuestions: { type: Array, default: null },
})

const emit = defineEmits(['publish', 'layout-change'])

const panelRef = ref(null)
const panelToggleRef = ref(null)
const previewWrapRef = ref(null)

// TQL 对照
const viewMode = ref('editor')
const isFitMode = ref(true)

function toggleFitMode() {
  isFitMode.value = !isFitMode.value
  applyFitMode()
}

function applyFitMode() {
  const zoomEl = document.getElementById('zoom')
  if (!zoomEl) return
  if (isFitMode.value) {
    const panel = panelRef.value
    const panelWidth = panel?.classList.contains('collapsed') ? 28 : 260
    const availWidth = window.innerWidth - panelWidth - 20
    const isA4 = window._cardLayout?.paper === 'A4'
    if (isA4) {
      // A4 纵向：按视口高度适配（一页高度 fit 进可用空间）
      const availHeight = window.innerHeight - 160 // 减去顶栏+标签+余量
      const pageHeight = 297 * 3.78
      const zoomByHeight = Math.round((availHeight / pageHeight) * 100)
      const pageWidth = 210 * 3.78
      const zoomByWidth = Math.round((availWidth / pageWidth) * 100)
      zoomEl.value = Math.max(20, Math.min(zoomByWidth, zoomByHeight))
    } else {
      // A3 横向：按宽度适配
      const pageWidth = 420 * 3.78
      zoomEl.value = Math.max(20, Math.round((availWidth / pageWidth) * 100))
    }
  } else {
    zoomEl.value = 100
  }
  zoomEl.dispatchEvent(new Event('input', { bubbles: true }))
}
const tqlImages = ref({})
const tqlLoading = ref(false)

async function switchToTql() {
  viewMode.value = 'tql'
  if (tqlImages.value[0] || tqlImages.value[1]) return // 已加载
  if (!props.subjectId) return
  tqlLoading.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await fetch(`/api/v1/card/tql-reference/${props.subjectId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await res.json()
    tqlImages.value = data.found ? data.images : {}
  } catch (e) {
    console.error('Failed to load TQL reference:', e)
  } finally {
    tqlLoading.value = false
  }
}

// --- Module references (loaded dynamically) ---
let modelModule = null
let renderModule = null
let interactModule = null
let panelModule = null
let exportModule = null
let saveTimer = null

const params = {
  examTitle: 'text', subjectTitle: 'text',
  titleSize: 'range', subtitleSize: 'range', titleSpacing: 'range', subtitleSpacing: 'range',
  titleGap: 'range', subtitleGap: 'range',
  infoHeight: 'range', infoPadding: 'range', infoRowGap: 'range', infoFontSize: 'range',
  infoBorderWidth: 'range', nameLineWidth: 'range',
  digitCount: 'range', digitBoxSize: 'range', digitGap: 'range',
  barcodeWidthPct: 'range', barcodeTitleSize: 'range',
  noticeHeight: 'range', noticeLabelWidth: 'range', noticeLabelSize: 'range',
  noticeFontSize: 'range', exampleWidth: 'range', noticeBorderWidth: 'range',
  absentPadding: 'range',
  choicePerRow: 'range', choiceRowGap: 'range',
  fillCount: 'range', fillScore: 'number', fillPerRow: 'range',
  essayCount: 'range',
  paperSize: 'select', zoom: 'range',
}

const structuralKeys = ['choiceCount', 'optionCount', 'fillCount', 'essayCount', 'paperSize']
let lastStructural = {}
let layoutFromServer = false  // 从 API/TQL 加载的布局，不允许被 needsRebuild 覆盖

function getValues() {
  const base = { ...(window._cardLayout?.config || {}) }
  const vals = { ...base }
  for (const [id, type] of Object.entries(params)) {
    const el = document.getElementById(id)
    if (!el) continue
    vals[id] = type === 'text' ? el.value : (type === 'select' ? el.value : parseFloat(el.value))
  }
  try { vals.essayConfig = JSON.parse(document.getElementById('essayConfig')?.value || '[]') } catch { vals.essayConfig = base.essayConfig || [] }
  vals.choiceCount = window._choices ? window._choices.length : (base.choiceCount || 11)
  vals.optionCount = window._choices && window._choices.length > 0 ? Math.max(...window._choices.map(c => c.options)) : (base.optionCount || 4)
  // 同步 _choices 到 choiceGroups，确保渲染使用最新数据
  if (window._choices && window._choices.length > 0) {
    const groups = []
    let cur = { start: window._choices[0].qno, options: window._choices[0].options, count: 1 }
    for (let i = 1; i < window._choices.length; i++) {
      const c = window._choices[i]
      if (c.options === cur.options && c.qno === cur.start + cur.count) {
        cur.count++
      } else {
        groups.push(cur)
        cur = { start: c.qno, options: c.options, count: 1 }
      }
    }
    groups.push(cur)
    vals.choiceGroups = groups
  }
  return vals
}

function updateLabels(v) {
  for (const [id, type] of Object.entries(params)) {
    const span = document.getElementById('v_' + id)
    if (span) span.textContent = type === 'text' ? '' : v[id]
  }
}

function needsRebuild(v) {
  for (const k of structuralKeys) {
    if (v[k] !== lastStructural[k]) return true
  }
  const ec = JSON.stringify(v.essayConfig || [])
  if (ec !== (lastStructural._essayConfigStr || '')) return true
  return false
}

async function saveToServer(config) {
  const status = document.getElementById('status')
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  try {
    // Save per-subject layout if subjectId is available
    if (props.subjectId && window._cardLayout) {
      await fetch(`/api/v1/card/editor-layout/${props.subjectId}`, {
        method: 'PUT', headers,
        body: JSON.stringify({
          layout: window._cardLayout,
          config: config || window._cardLayout?.config || {},
          choices: window._choices || [],
        }),
      })
    }
    if (status) {
      status.textContent = '已保存 ' + new Date().toLocaleTimeString()
      status.className = 'status'
    }
  } catch (e) {
    if (status) {
      status.textContent = '保存失败: ' + e.message
      status.className = 'status error'
    }
  }
}

function onAnyChange(userEdit = false) {
  if (!modelModule) return
  const previewWrap = previewWrapRef.value
  if (!previewWrap) return

  const v = getValues()
  // 从 API/TQL 加载的布局：只同步样式参数，保护结构性字段（paperSize/sides）
  if (layoutFromServer && window._cardLayout) {
    const protectedPaperSize = window._cardLayout.config?.paperSize
    window._cardLayout.config = { ...window._cardLayout.config, ...v }
    if (protectedPaperSize) window._cardLayout.config.paperSize = protectedPaperSize
  } else if (!window._cardLayout || needsRebuild(v)) {
    window._cardLayout = modelModule.createDefaultLayout(v)
    for (const k of structuralKeys) lastStructural[k] = v[k]
    lastStructural._essayConfigStr = JSON.stringify(v.essayConfig || [])
  } else {
    window._cardLayout.config = { ...window._cardLayout.config, ...v }
  }
  const config = window._cardLayout.config || v
  // 保持 layout.paper 和 config.paperSize 同步
  if (window._cardLayout.paper) config.paperSize = window._cardLayout.paper
  renderModule.renderFromLayout(previewWrap, window._cardLayout, config)
  updateLabels(config)
  if (window._initInteraction) window._initInteraction()

  emit('layout-change', window._cardLayout)

  // 只在用户主动编辑时自动保存，系统事件（resize/autoFitZoom/初始化）不保存
  if (userEdit && !props.readonly) {
    clearTimeout(saveTimer)
    saveTimer = setTimeout(() => saveToServer(config), 500)
  }
}

function renderChoiceList() {
  const list = document.getElementById('choiceList')
  if (!list) return
  let html = ''
  for (let i = 0; i < window._choices.length; i++) {
    const c = window._choices[i]
    html += `<div class="choice-item">
      <input type="number" class="choice-qno" data-idx="${i}" value="${c.qno}" min="1" max="99" title="题号">
      <span class="choice-dot">.</span>
      <select class="choice-opts" data-idx="${i}" title="选项数">
        ${[2,3,4,5,6,7,8].map(n => `<option value="${n}" ${c.options===n?'selected':''}>${n}项${'ABCDEFGH'.slice(0,n)}</option>`).join('')}
      </select>
      <span class="choice-del" data-idx="${i}" title="删除">×</span>
    </div>`
  }
  list.innerHTML = html

  list.querySelectorAll('.choice-qno').forEach(input => {
    input.addEventListener('input', (e) => {
      window._choices[parseInt(e.target.dataset.idx)].qno = parseInt(e.target.value) || 1
      onAnyChange(true)
    })
  })
  list.querySelectorAll('.choice-opts').forEach(sel => {
    sel.addEventListener('change', (e) => {
      window._choices[parseInt(e.target.dataset.idx)].options = parseInt(e.target.value)
      onAnyChange(true)
    })
  })
  list.querySelectorAll('.choice-del').forEach(btn => {
    btn.addEventListener('click', () => {
      window._choices.splice(parseInt(btn.dataset.idx), 1)
      renderChoiceList()
      onAnyChange(true)
    })
  })
}

function autoFitZoom() {
  if (!isFitMode.value) return
  const panel = panelRef.value
  const panelWidth = panel?.classList.contains('collapsed') ? 28 : 260
  const availWidth = window.innerWidth - panelWidth - 20
  const isA4 = window._cardLayout?.paper === 'A4'
  let fitZoom
  if (isA4) {
    const availHeight = window.innerHeight - 160
    const zoomByHeight = Math.round((availHeight / (297 * 3.78)) * 100)
    const zoomByWidth = Math.round((availWidth / (210 * 3.78)) * 100)
    fitZoom = Math.max(20, Math.min(zoomByWidth, zoomByHeight))
  } else {
    fitZoom = Math.max(20, Math.round((availWidth / (420 * 3.78)) * 100))
  }
  const zoomEl = document.getElementById('zoom')
  if (zoomEl) zoomEl.value = fitZoom
}

function togglePanel() {
  const panel = panelRef.value
  const btn = panelToggleRef.value
  if (!panel || !btn) return
  panel.classList.toggle('collapsed')
  btn.classList.toggle('collapsed')
  btn.textContent = panel.classList.contains('collapsed') ? '›' : '‹'
  setTimeout(() => { autoFitZoom(); onAnyChange() }, 320)
}

function initDefaultChoices() {
  if (window._choices && window._choices.length > 0) return
  window._choices = []
  for (let i = 1; i <= 11; i++) {
    window._choices.push({ qno: i, options: 4 })
  }
}

async function loadFromServer() {
  const status = document.getElementById('status')
  const token = localStorage.getItem('token')
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  let loaded = false

  // Try per-subject layout first
  if (props.subjectId) {
    try {
      const resp = await fetch(`/api/v1/card/editor-layout/${props.subjectId}`, { headers })
      if (resp.ok) {
        const data = await resp.json()
        if (data.found && data.layout) {
          // 合并 config：layout.config 为底，saved config 覆盖，避免坏数据遮盖好数据
          const layoutConfig = data.layout?.config || {}
          const savedConfig = data.config || {}
          const mergedConfig = { ...layoutConfig, ...savedConfig }
          window._cardLayout = data.layout
          if (window._cardLayout) {
            window._cardLayout.config = mergedConfig
            // paperSize 单一真值：layout.paper 为权威，同步到 config.paperSize
            if (window._cardLayout.paper) {
              mergedConfig.paperSize = window._cardLayout.paper
            } else if (mergedConfig.paperSize) {
              window._cardLayout.paper = mergedConfig.paperSize
            }
          }
          // 语文 B 面 essay 默认为作文类型
          if (window._cardLayout?.sides && mergedConfig.subjectTitle?.includes('语文')) {
            const sideB = window._cardLayout.sides[1]
            if (sideB) {
              for (const col of sideB.columns) {
                for (const r of (col.regions || [])) {
                  if (r.type === 'essay' && !r.qtype) r.qtype = 'essay_cn'
                }
              }
            }
          }
          // 结构修正：合并 col3+ 到 col2，填充空中间栏（仅 A3 布局）
          const isA4Layout = (mergedConfig.paperSize === 'A4' || window._cardLayout.paper === 'A4')
          if (window._cardLayout?.sides && !isA4Layout) {
            for (const side of window._cardLayout.sides) {
              const cols = side.columns || []
              // 合并 col3+ 到 col2
              if (cols.length > 3) {
                for (let c = 3; c < cols.length; c++) {
                  if (cols[2]) cols[2].regions = (cols[2].regions || []).concat(cols[c].regions || [])
                }
                side.columns = cols.slice(0, 3)
              }
              while (side.columns.length < 3) side.columns.push({ col: side.columns.length, regions: [] })
              // 填充空中间栏（完全空 + 后面有内容）
              for (let c = 0; c < 2; c++) {
                if (side.columns[c].regions.length > 0) continue
                // 找后面第一个有 non-fixed 内容的栏
                for (let nc = c + 1; nc < 3; nc++) {
                  const nfRegs = side.columns[nc].regions.filter(r => r.type !== 'fixed')
                  if (nfRegs.length === 0) continue
                  if (nfRegs.length === 1) {
                    // 只有 1 个：整个移过来
                    side.columns[c].regions = side.columns[nc].regions
                    side.columns[nc].regions = []
                  } else {
                    // ≥2 个：借第一个
                    const idx = side.columns[nc].regions.findIndex(r => r.type !== 'fixed')
                    side.columns[c].regions = side.columns[nc].regions.splice(idx, 1)
                  }
                  break
                }
              }
            }
          }
          if (data.choices && data.choices.length > 0) {
            window._choices = data.choices
          } else {
            // 从 choiceGroups 精确初始化 _choices（保留真实题号和选项数）
            if (mergedConfig.choiceGroups && mergedConfig.choiceGroups.length > 0) {
              window._choices = []
              for (const g of mergedConfig.choiceGroups) {
                for (let i = 0; i < g.count; i++) {
                  window._choices.push({ qno: g.start + i, options: g.options })
                }
              }
            } else if (mergedConfig.choiceCount > 0) {
              // fallback: 无 choiceGroups 时用连续编号
              window._choices = []
              for (let i = 1; i <= mergedConfig.choiceCount; i++) {
                window._choices.push({ qno: i, options: mergedConfig.optionCount || 4 })
              }
            }
          }
          // Restore config values to form controls
          const config = mergedConfig
          for (const [k, v] of Object.entries(config)) {
            if (k === '_layout' || k === 'essayConfig') continue
            const el = document.getElementById(k)
            if (el) el.value = v
          }
          if (config.essayConfig) {
            const el = document.getElementById('essayConfig')
            if (el) el.value = JSON.stringify(config.essayConfig, null, 0)
          }
          const v = getValues()
          for (const k of structuralKeys) lastStructural[k] = v[k]
          lastStructural._essayConfigStr = JSON.stringify(v.essayConfig || [])
          if (status) status.textContent = '已加载科目布局'
          layoutFromServer = true
          loaded = true
        }
      }
    } catch { /* no subject layout */ }
  }

  if (loaded) {
    // 已从 API 加载了完整布局，直接渲染，不走 createDefaultLayout
    const previewWrap = previewWrapRef.value
    if (previewWrap && renderModule) {
      const v = getValues()
      renderModule.renderFromLayout(previewWrap, window._cardLayout, v)
      updateLabels(v)
      if (window._initInteraction) window._initInteraction()
    }
  } else {
    onAnyChange()
  }
}

let resizeHandler = null

onMounted(async () => {
  // Load card-editor stylesheet dynamically (每次强制刷新，避免缓存)
  const oldLink = document.getElementById('card-editor-styles')
  if (oldLink) oldLink.remove()
  const link = document.createElement('link')
  link.id = 'card-editor-styles'
  link.rel = 'stylesheet'
  link.href = '/card-editor/styles.css?v=' + Date.now()
  document.head.appendChild(link)

  // Initialize global state
  window._cardLayout = null
  initDefaultChoices()

  // Dynamically import native JS modules
  modelModule = await import('@/card-editor/model.js')
  renderModule = await import('@/card-editor/render.js')
  interactModule = await import('@/card-editor/interact.js')
  panelModule = await import('@/card-editor/panel.js')
  exportModule = await import('@/card-editor/export.js')

  // Expose globals for inter-module communication
  window._onAnyChange = onAnyChange
  window._getValues = getValues
  window._previewWrap = previewWrapRef.value
  window._autoFitZoom = autoFitZoom

  // Bind input events
  const onUserEdit = () => onAnyChange(true)
  for (const id of Object.keys(params)) {
    const el = document.getElementById(id)
    if (el) el.addEventListener('input', onUserEdit)
  }
  document.getElementById('essayConfig')?.addEventListener('input', onUserEdit)

  // Quick generate button
  document.getElementById('choiceGenBtn')?.addEventListener('click', () => {
    const count = parseInt(document.getElementById('choiceQuickCount')?.value) || 11
    const opts = parseInt(document.getElementById('choiceQuickOptions')?.value) || 4
    window._choices = []
    for (let i = 1; i <= count; i++) window._choices.push({ qno: i, options: opts })
    renderChoiceList()
    onAnyChange(true)
  })

  // Add single choice button
  document.getElementById('btnAddChoice')?.addEventListener('click', () => {
    const lastQno = window._choices.length > 0 ? Math.max(...window._choices.map(c => c.qno)) : 0
    window._choices.push({ qno: lastQno + 1, options: 4 })
    renderChoiceList()
    onAnyChange(true)
  })

  // Load saved config, then init modules
  await loadFromServer()

  // 如果有待应用的题目数据（从答案解析流程传入），合并到模板
  if (props.pendingQuestions && props.pendingQuestions.length > 0) {
    const { applyQuestions } = await import('@/card-editor/model.js')
    const currentConfig = getValues()
    const { config: updatedConfig, choices } = applyQuestions(currentConfig, props.pendingQuestions)
    // 更新 DOM 控件
    for (const [k, v] of Object.entries(updatedConfig)) {
      if (k === 'essayConfig' || k === '_layout') continue
      const el = document.getElementById(k)
      if (el) el.value = v
    }
    if (updatedConfig.essayConfig) {
      const el = document.getElementById('essayConfig')
      if (el) el.value = JSON.stringify(updatedConfig.essayConfig, null, 0)
    }
    // 更新选择题数据
    window._choices = choices
    renderChoiceList()
    // 更新考试标题和科目
    if (props.cardTitle) {
      const el = document.getElementById('examTitle')
      if (el) el.value = props.cardTitle
    }
    if (props.subjectName) {
      const el = document.getElementById('subjectTitle')
      if (el) el.value = props.subjectName
    }
  }

  panelModule.initPanel()
  exportModule.initExport()
  renderChoiceList()
  autoFitZoom()
  // 延迟一帧确保 DOM 完全就绪
  await nextTick()
  // 已从 API 加载 TQL 布局时，只渲染不 rebuild
  if (window._cardLayout) {
    const previewWrap = previewWrapRef.value
    if (previewWrap && renderModule) {
      const v = getValues()
      renderModule.renderFromLayout(previewWrap, window._cardLayout, v)
      updateLabels(v)
      if (window._initInteraction) window._initInteraction()
    }
  } else {
    onAnyChange()
  }
  // 兜底：首次 nextTick 拿不到 ref 时重试
  if (!previewWrapRef.value) {
    await new Promise(r => setTimeout(r, 100))
    if (window._cardLayout) {
      const previewWrap = previewWrapRef.value
      if (previewWrap && renderModule) {
        renderModule.renderFromLayout(previewWrap, window._cardLayout, getValues())
      }
    } else {
      onAnyChange()
    }
  }

  // Handle readonly mode
  if (props.readonly) {
    disableEditing()
  }

  resizeHandler = () => { autoFitZoom(); onAnyChange() }
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  clearTimeout(saveTimer)
  // Clean up globals
  delete window._cardLayout
  delete window._choices
  delete window._onAnyChange
  delete window._getValues
  delete window._previewWrap
  delete window._autoFitZoom
  delete window._initInteraction
  delete window._initPanel
  delete window._renderQuestionList
  delete window._onRegionSelect
})

function disableEditing() {
  // Disable all inputs in the panel
  const panel = panelRef.value
  if (!panel) return
  panel.querySelectorAll('input, select, textarea, button').forEach(el => {
    if (el.id !== 'zoom' && !el.classList.contains('panel-toggle')) {
      el.disabled = true
    }
  })
}

watch(() => props.readonly, (val) => {
  if (val) nextTick(() => disableEditing())
})

// Expose layout getter for parent component
async function save() {
  const v = getValues()
  await saveToServer(v)
}

async function resetToDefault() {
  if (!props.subjectId) return
  const status = document.getElementById('status')
  const token = localStorage.getItem('token')
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  try {
    await fetch(`/api/v1/card/editor-layout/${props.subjectId}`, { method: 'DELETE', headers })
    layoutFromServer = false
    window._cardLayout = null
    window._choices = []
    await loadFromServer()
    if (status) { status.textContent = '已恢复默认模板'; status.className = 'status' }
  } catch (e) {
    if (status) { status.textContent = '恢复失败: ' + e.message; status.className = 'status error' }
  }
}

function exportPdf() {
  document.getElementById('btnExportPdf')?.click()
}

function applyAutoLayout(result) {
  // result = { questions: [{ qno, heightRatio, subs: [{ sub, blanks: [{w}] }] }] }
  const layout = window._cardLayout
  if (!layout || !result.questions) return

  const qmap = {}
  for (const q of result.questions) qmap[q.qno] = q

  for (const side of layout.sides) {
    for (const col of side.columns) {
      for (const region of col.regions) {
        if (region.type !== 'essay') continue
        const q = qmap[region.qno]
        if (!q) continue
        region.heightRatio = q.heightRatio
        if (q.subs && q.subs.length > 0) {
          region.subs = q.subs
        }
      }
    }
  }

  // 重新渲染
  const previewWrap = previewWrapRef.value
  if (previewWrap && renderModule) {
    const v = getValues()
    renderModule.renderFromLayout(previewWrap, layout, v)
    updateLabels(v)
    if (window._initInteraction) window._initInteraction()
  }
  if (window._renderQuestionList) window._renderQuestionList()
}

defineExpose({
  getLayout: () => window._cardLayout,
  getValues,
  save,
  resetToDefault,
  exportPdf,
  applyAutoLayout,
})
</script>

<style scoped>
.card-editor-wrapper {
  position: relative;
  display: flex;
  width: 100%;
  height: calc(100dvh - 200px);
  min-height: 600px;
  overflow: hidden;
}
.card-editor-wrapper.tql-mode {
  height: auto;
  min-height: auto;
  overflow: visible;
}
.save-btn {
  background: #2d5a3d !important;
  color: white !important;
  font-weight: var(--fw-semibold);
}
.save-btn:hover {
  background: #1a2e1f !important;
}
.reset-btn {
  background: #5a3d2d !important;
  color: white !important;
  font-size: var(--fs-base);
}
.reset-btn:hover {
  background: #3d2a1a !important;
}
.publish-btn {
  background: #2d5a3d !important;
  color: white !important;
  font-weight: var(--fw-semibold);
}
.publish-btn:hover {
  background: #1a2e1f !important;
}
.status {
  font-size: var(--fs-base);
  color: #8a9b8e;
  margin-top: var(--space-1);
}
.status.error {
  color: var(--color-danger);
}
/* 预览区域 */
.preview-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
}
/* 编辑器/TQL 切换按钮 */
.view-toggle {
  display: flex;
  gap: 0;
  padding: 2px var(--space-1);
  background: var(--color-bg-alt);
  border-bottom: 1px solid #e2e8e4;
  flex-shrink: 0;
}
.view-toggle button {
  padding: 3px var(--space-3);
  border: 1px solid var(--color-border);
  background: #fff;
  cursor: pointer;
  font-size: var(--fs-base);
  color: var(--color-text-secondary);
}
.view-toggle button:first-child { border-radius: var(--r-xs) 0 0 var(--r-xs); }
.view-toggle button:nth-child(2) { border-radius: 0 var(--r-xs) var(--r-xs) 0; border-left: none; }
.fit-zoom-btn {
  margin-left: 8px; padding: 3px 12px; font-size: var(--fs-base); border: 1px solid var(--color-border);
  border-radius: var(--r-xs); background: #fff; cursor: pointer; color: var(--color-text-secondary);
}
.fit-zoom-btn.active { background: #2d5a3d; color: #fff; border-color: #2d5a3d; }
.view-toggle button.active {
  background: #2d5a3d;
  color: #fff;
  border-color: #2d5a3d;
}
/* TQL 全宽显示 */
.tql-view {
  padding: var(--space-3);
  background: #e8e8e8;
}
.tql-img-wrap {
  margin-bottom: var(--space-4);
}
.tql-label {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  color: var(--color-text);
  margin-bottom: 6px;
}
.tql-img-wrap img {
  width: 100%;
  border: 1px solid var(--color-text-muted);
  border-radius: var(--r-xs);
  background: #fff;
}
</style>
