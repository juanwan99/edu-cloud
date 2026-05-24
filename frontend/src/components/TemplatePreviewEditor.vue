<template>
  <n-modal :show="show" @update:show="$emit('update:show', $event)" preset="card"
           title="模板区域编辑" style="width:92vw;max-width:1400px" :mask-closable="false">
    <div class="tpl-editor">
      <div class="tpl-toolbar">
        <n-button-group size="small" v-if="hasSideB">
          <n-button :type="activeSide === 'A' ? 'primary' : 'default'" @click="activeSide = 'A'">A 面</n-button>
          <n-button :type="activeSide === 'B' ? 'primary' : 'default'" @click="activeSide = 'B'">B 面</n-button>
        </n-button-group>
        <n-divider vertical v-if="hasSideB" />

        <n-button-group size="small">
          <n-button @click="zoom = Math.max(0.1, zoom - 0.1)">−</n-button>
          <n-button disabled style="min-width:56px">{{ pct }}%</n-button>
          <n-button @click="zoom = Math.min(3, zoom + 0.1)">+</n-button>
          <n-button @click="fitZoom">适应</n-button>
        </n-button-group>

        <n-divider vertical />

        <n-button size="small" @click="addRegion">+ 区域</n-button>
        <n-button size="small" :disabled="!selectedId" :type="splitMode ? 'warning' : 'default'"
                  @click="toggleSplitMode">{{ splitMode ? '取消分割' : '✂ 分割' }}</n-button>
        <n-button size="small" :disabled="!selectedId" type="error" @click="deleteSelected">删除</n-button>

        <template v-if="selectedRegion">
          <n-divider vertical />
          <n-select size="small" :value="selectedRegion.type" @update:value="changeType"
                    :options="typeOptions" style="width:130px" />
          <template v-if="selectedRegion.type === 'subjective'">
            <span class="toolbar-label">题号</span>
            <n-input size="small" :value="String(selectedRegion.qno || '')" @update:value="v => selectedRegion.qno = v"
                     placeholder="如 18、19" style="width:90px" />
            <span class="toolbar-label">分值</span>
            <n-input-number size="small" :value="selectedRegion.score" @update:value="v => selectedRegion.score = v"
                            :min="0" :show-button="false" style="width:70px" />
          </template>
          <template v-if="selectedRegion.type === 'choice_group'">
            <span class="toolbar-label">起始题号</span>
            <n-input-number size="small" :value="selectedRegion.start_no" @update:value="v => selectedRegion.start_no = v"
                            :min="1" :show-button="false" style="width:60px" />
            <span class="toolbar-label">行数</span>
            <n-input-number size="small" :value="selectedRegion.rows" @update:value="v => selectedRegion.rows = v"
                            :min="1" :show-button="false" style="width:60px" />
            <span class="toolbar-label">列数</span>
            <n-input-number size="small" :value="selectedRegion.cols" @update:value="v => selectedRegion.cols = v"
                            :min="3" :max="6" :show-button="false" style="width:60px" />
            <span class="toolbar-label">每题分值</span>
            <n-input-number size="small" :value="selectedRegion.score" @update:value="v => selectedRegion.score = v"
                            :min="0" :show-button="false" style="width:60px" />
          </template>
        </template>

        <div style="flex:1" />
        <n-button size="small" quaternary @click="$emit('cancel')">取消</n-button>
        <n-button size="small" type="primary" @click="handleConfirm">确认保存</n-button>
      </div>

      <div class="tpl-viewport" ref="viewport" :class="{ 'split-active': splitMode }"
           @mousedown="onViewportMouseDown"
           @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseUp"
           @wheel.prevent="onWheel">
        <div class="tpl-canvas" :style="canvasStyle">
          <img v-if="currentBlobUrl" :src="currentBlobUrl" class="tpl-bg" draggable="false"
               @load="onImgLoad" />

          <div v-for="(r, idx) in currentRegions" :key="r.id"
               class="tpl-region" :class="{ active: selectedId === r.id }"
               :style="rStyle(r, idx)" @mousedown.stop="startDrag($event, r)">
            <span class="tpl-rid" :style="{ color: regionColor(idx) }">{{ r.id }}</span>
            <span class="tpl-rtype">{{ typeLabel(r.type) }}</span>
            <template v-if="r.type === 'subjective' && r.qno">
              <span class="tpl-rqno">Q{{ r.qno }}</span>
            </template>
            <div class="h h-nw" @mousedown.stop="startResize($event, r, 'nw')"/>
            <div class="h h-ne" @mousedown.stop="startResize($event, r, 'ne')"/>
            <div class="h h-sw" @mousedown.stop="startResize($event, r, 'sw')"/>
            <div class="h h-se" @mousedown.stop="startResize($event, r, 'se')"/>
            <div class="h h-n"  @mousedown.stop="startResize($event, r, 'n')"/>
            <div class="h h-s"  @mousedown.stop="startResize($event, r, 's')"/>
            <div class="h h-w"  @mousedown.stop="startResize($event, r, 'w')"/>
            <div class="h h-e"  @mousedown.stop="startResize($event, r, 'e')"/>
          </div>

          <div v-if="drawing" class="tpl-region drawing" :style="drawStyle" />

          <!-- 分割预览线 -->
          <div v-if="splitPreview" class="split-line" :style="splitLineStyle" />
        </div>
      </div>

      <div class="tpl-sidebar">
        <div class="sidebar-title">{{ hasSideB ? (activeSide + ' 面 ') : '' }}区域 ({{ currentRegions.length }})</div>
        <div v-for="(r, idx) in sortedRegions" :key="r.id"
             class="sidebar-item" :class="{ active: selectedId === r.id }"
             @click="selectedId = r.id">
          <span class="dot" :style="{ background: regionColor(currentRegions.indexOf(r)) }" />
          <span>{{ r.id }}</span>
          <span class="stype">{{ typeLabel(r.type) }}</span>
          <span v-if="r.qno" class="sqno">Q{{ r.qno }}</span>
        </div>
      </div>
    </div>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { NModal, NButton, NButtonGroup, NSelect, NDivider, NInputNumber, NInput } from 'naive-ui'

const props = defineProps({
  show: Boolean,
  blobUrl: String,
  blobUrlB: { type: String, default: null },
  regions: Array,
  regionsB: { type: Array, default: null },
  imageWidth: Number,
  imageHeight: Number,
  imageWidthB: { type: Number, default: 0 },
  imageHeightB: { type: Number, default: 0 },
})
const emit = defineEmits(['update:show', 'confirm', 'cancel'])

// --- 8 色交替，相邻区域一定不同色 ---
const PALETTE = [
  { border: 'rgba(64,158,255,0.8)',  bg: 'rgba(64,158,255,0.10)',  bgA: 'rgba(64,158,255,0.20)',  solid: '#409eff' },
  { border: 'rgba(245,108,108,0.8)', bg: 'rgba(245,108,108,0.10)', bgA: 'rgba(245,108,108,0.20)', solid: '#f56c6c' },
  { border: 'rgba(103,194,58,0.8)',  bg: 'rgba(103,194,58,0.10)',  bgA: 'rgba(103,194,58,0.20)',  solid: '#67c23a' },
  { border: 'rgba(230,162,60,0.8)',  bg: 'rgba(230,162,60,0.10)',  bgA: 'rgba(230,162,60,0.20)',  solid: '#e6a23c' },
  { border: 'rgba(144,147,255,0.8)', bg: 'rgba(144,147,255,0.10)', bgA: 'rgba(144,147,255,0.20)', solid: '#9093ff' },
  { border: 'rgba(56,203,187,0.8)',  bg: 'rgba(56,203,187,0.10)',  bgA: 'rgba(56,203,187,0.20)',  solid: '#38cbbb' },
  { border: 'rgba(237,106,188,0.8)', bg: 'rgba(237,106,188,0.10)', bgA: 'rgba(237,106,188,0.20)', solid: '#ed6abc' },
  { border: 'rgba(180,180,80,0.8)',  bg: 'rgba(180,180,80,0.10)',  bgA: 'rgba(180,180,80,0.20)',  solid: '#b4b450' },
]

function regionColor(idx) { return PALETTE[idx % PALETTE.length].solid }

// --- A/B 面 ---
const activeSide = ref('A')
const hasSideB = computed(() => !!props.blobUrlB)
const regionsA = ref([])
const regionsB = ref([])
const currentRegions = computed(() => activeSide.value === 'A' ? regionsA.value : regionsB.value)
const currentBlobUrl = computed(() => activeSide.value === 'A' ? props.blobUrl : props.blobUrlB)
const currentWidth = computed(() => activeSide.value === 'A' ? props.imageWidth : (props.imageWidthB || props.imageWidth))
const currentHeight = computed(() => activeSide.value === 'A' ? props.imageHeight : (props.imageHeightB || props.imageHeight))

const viewport = ref(null)
const zoom = ref(0.4)
const pct = computed(() => Math.round(zoom.value * 100))
const selectedId = ref(null)
const selectedRegion = computed(() => currentRegions.value.find(r => r.id === selectedId.value))

const sortedRegions = computed(() =>
  [...currentRegions.value].sort((a, b) => a.rect.y1 - b.rect.y1 || a.rect.x1 - b.rect.x1)
)

const typeOptions = [
  { label: '主观题', value: 'subjective' },
  { label: '选择题组', value: 'choice_group' },
  { label: '条码区', value: 'barcode' },
]

function typeLabel(t) {
  return { subjective: '主观', choice_group: '选择', barcode: '条码' }[t] || t
}

watch(() => props.regions, (v) => {
  if (v) regionsA.value = JSON.parse(JSON.stringify(v))
}, { immediate: true })

watch(() => props.regionsB, (v) => {
  if (v) regionsB.value = JSON.parse(JSON.stringify(v))
}, { immediate: true })

watch(() => props.show, (v) => {
  if (v) { activeSide.value = 'A'; nextTick(fitZoom) }
})

watch(activeSide, () => { selectedId.value = null; splitMode.value = false; splitPreview.value = null; nextTick(fitZoom) })

function fitZoom() {
  if (!viewport.value || !currentWidth.value) return
  const vw = viewport.value.clientWidth - 20
  const vh = viewport.value.clientHeight
  zoom.value = Math.min(vw / currentWidth.value, vh / currentHeight.value, 1)
}

const canvasStyle = computed(() => ({
  width: currentWidth.value + 'px',
  height: currentHeight.value + 'px',
  transform: `scale(${zoom.value})`,
  transformOrigin: '0 0',
}))

function rStyle(r, idx) {
  const { x1, y1, x2, y2 } = r.rect
  const p = PALETTE[idx % PALETTE.length]
  const isActive = selectedId.value === r.id
  return {
    left: x1 + 'px', top: y1 + 'px', width: (x2 - x1) + 'px', height: (y2 - y1) + 'px',
    borderColor: isActive ? p.solid : p.border,
    background: isActive ? p.bgA : p.bg,
  }
}

// --- Image load ---
function onImgLoad() { nextTick(fitZoom) }

// --- Zoom via wheel ---
function onWheel(e) {
  const delta = e.deltaY > 0 ? -0.05 : 0.05
  zoom.value = Math.min(3, Math.max(0.1, zoom.value + delta))
}

// --- 分割模式 ---
const splitMode = ref(false)
const splitPreview = ref(null)

function toggleSplitMode() {
  splitMode.value = !splitMode.value
  splitPreview.value = null
}

const splitLineStyle = computed(() => {
  if (!splitPreview.value) return { display: 'none' }
  const s = splitPreview.value
  return {
    left: s.x1 + 'px', top: s.y + 'px',
    width: (s.x2 - s.x1) + 'px',
  }
})

function doSplit(region, splitY) {
  const arr = currentRegions.value
  const idx = arr.indexOf(region)
  if (idx < 0) return

  const r = region.rect
  const minH = 30
  if (splitY - r.y1 < minH || r.y2 - splitY < minH) return

  const topId = region.id
  const bottomId = _nextId(arr)

  const top = { ...JSON.parse(JSON.stringify(region)), id: topId, rect: { x1: r.x1, y1: r.y1, x2: r.x2, y2: Math.round(splitY) } }
  const bottom = { ...JSON.parse(JSON.stringify(region)), id: bottomId, rect: { x1: r.x1, y1: Math.round(splitY), x2: r.x2, y2: r.y2 }, qno: nextQno() }

  arr.splice(idx, 1, top, bottom)
  selectedId.value = bottomId
  splitMode.value = false
  splitPreview.value = null
}

// --- Drag / resize state ---
const dragState = ref(null)
const drawing = ref(null)

function toImageCoords(e) {
  if (!viewport.value) return { x: 0, y: 0 }
  const vr = viewport.value.getBoundingClientRect()
  return {
    x: (e.clientX - vr.left + viewport.value.scrollLeft) / zoom.value,
    y: (e.clientY - vr.top + viewport.value.scrollTop) / zoom.value,
  }
}

function startDrag(e, region) {
  if (splitMode.value) {
    const p = toImageCoords(e)
    doSplit(region, p.y)
    return
  }
  selectedId.value = region.id
  const p = toImageCoords(e)
  dragState.value = {
    mode: 'move', region, startX: p.x, startY: p.y,
    origRect: { ...region.rect },
  }
}

function startResize(e, region, handle) {
  selectedId.value = region.id
  const p = toImageCoords(e)
  dragState.value = {
    mode: 'resize', region, handle, startX: p.x, startY: p.y,
    origRect: { ...region.rect },
  }
}

function onViewportMouseDown(e) {
  if (e.target !== viewport.value && !e.target.classList.contains('tpl-canvas') && !e.target.classList.contains('tpl-bg')) {
    return
  }
  selectedId.value = null
  const p = toImageCoords(e)
  drawing.value = { x1: p.x, y1: p.y, x2: p.x, y2: p.y }
}

const drawStyle = computed(() => {
  if (!drawing.value) return {}
  const d = drawing.value
  const x = Math.min(d.x1, d.x2), y = Math.min(d.y1, d.y2)
  const w = Math.abs(d.x2 - d.x1), h = Math.abs(d.y2 - d.y1)
  return { left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px' }
})

function onMouseMove(e) {
  const p = toImageCoords(e)

  // 分割模式：在选中区域内显示水平预览线
  if (splitMode.value && selectedRegion.value) {
    const r = selectedRegion.value.rect
    if (p.x >= r.x1 && p.x <= r.x2 && p.y >= r.y1 + 30 && p.y <= r.y2 - 30) {
      splitPreview.value = { x1: r.x1, x2: r.x2, y: p.y }
    } else {
      splitPreview.value = null
    }
  }

  if (drawing.value) {
    drawing.value.x2 = clamp(p.x, 0, currentWidth.value)
    drawing.value.y2 = clamp(p.y, 0, currentHeight.value)
    return
  }
  if (!dragState.value) return
  const s = dragState.value
  const dx = p.x - s.startX, dy = p.y - s.startY
  const W = currentWidth.value, H = currentHeight.value

  if (s.mode === 'move') {
    const w = s.origRect.x2 - s.origRect.x1, h = s.origRect.y2 - s.origRect.y1
    const nx1 = clamp(s.origRect.x1 + dx, 0, W - w)
    const ny1 = clamp(s.origRect.y1 + dy, 0, H - h)
    s.region.rect = { x1: Math.round(nx1), y1: Math.round(ny1), x2: Math.round(nx1 + w), y2: Math.round(ny1 + h) }
  } else if (s.mode === 'resize') {
    const r = { ...s.origRect }
    const h = s.handle
    if (h.includes('n')) r.y1 = clamp(r.y1 + dy, 0, r.y2 - 20)
    if (h.includes('s')) r.y2 = clamp(r.y2 + dy, r.y1 + 20, H)
    if (h.includes('w')) r.x1 = clamp(r.x1 + dx, 0, r.x2 - 20)
    if (h.includes('e')) r.x2 = clamp(r.x2 + dx, r.x1 + 20, W)
    s.region.rect = { x1: Math.round(r.x1), y1: Math.round(r.y1), x2: Math.round(r.x2), y2: Math.round(r.y2) }
  }
}

function onMouseUp() {
  if (drawing.value) {
    const d = drawing.value
    const w = Math.abs(d.x2 - d.x1), h = Math.abs(d.y2 - d.y1)
    if (w > 30 && h > 30) {
      const id = _nextId(currentRegions.value)
      const nr = {
        id,
        type: 'subjective',
        question_type: 'essay',
        qno: nextQno(),
        score: 0,
        rect: {
          x1: Math.round(Math.min(d.x1, d.x2)),
          y1: Math.round(Math.min(d.y1, d.y2)),
          x2: Math.round(Math.max(d.x1, d.x2)),
          y2: Math.round(Math.max(d.y1, d.y2)),
        },
      }
      currentRegions.value.push(nr)
      selectedId.value = nr.id
    }
    drawing.value = null
  }
  dragState.value = null
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

function nextQno() {
  const all = [...regionsA.value, ...regionsB.value]
  const nums = []
  for (const r of all) {
    if (!r.qno) continue
    const parts = String(r.qno).split(/[、,，]/)
    for (const p of parts) { const n = parseInt(p); if (n) nums.push(n) }
  }
  return nums.length ? Math.max(...nums) + 1 : 1
}

function _nextId(arr) {
  let max = 0
  for (const r of arr) {
    const m = r.id && r.id.match(/^R(\d+)$/)
    if (m) max = Math.max(max, parseInt(m[1]))
  }
  return 'R' + String(max + 1).padStart(2, '0')
}

// --- Toolbar actions ---
function addRegion() {
  const cx = currentWidth.value / 2, cy = currentHeight.value / 2
  const arr = currentRegions.value
  const id = _nextId(arr)
  const nr = {
    id, type: 'subjective', question_type: 'essay',
    qno: nextQno(), score: 0,
    rect: { x1: Math.round(cx - 150), y1: Math.round(cy - 75), x2: Math.round(cx + 150), y2: Math.round(cy + 75) },
  }
  arr.push(nr)
  selectedId.value = nr.id
}

function deleteSelected() {
  if (activeSide.value === 'A') regionsA.value = regionsA.value.filter(r => r.id !== selectedId.value)
  else regionsB.value = regionsB.value.filter(r => r.id !== selectedId.value)
  selectedId.value = null
}

function changeType(t) {
  if (!selectedRegion.value) return
  selectedRegion.value.type = t
  if (t === 'choice_group') {
    if (!selectedRegion.value.rows) selectedRegion.value.rows = 10
    if (!selectedRegion.value.cols) selectedRegion.value.cols = 4
    if (!selectedRegion.value.start_no) selectedRegion.value.start_no = 1
    if (!selectedRegion.value.score) selectedRegion.value.score = 3
  }
}

function handleConfirm() {
  emit('confirm', {
    A: JSON.parse(JSON.stringify(regionsA.value)),
    B: hasSideB.value ? JSON.parse(JSON.stringify(regionsB.value)) : null,
  })
}

// keyboard
function onKey(e) {
  if (!props.show) return
  if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId.value) {
    if (document.activeElement?.tagName === 'INPUT') return
    deleteSelected()
  }
  if (e.key === 'Escape') {
    if (splitMode.value) { splitMode.value = false; splitPreview.value = null; return }
    emit('cancel')
  }
}
if (typeof window !== 'undefined') window.addEventListener('keydown', onKey)
onBeforeUnmount(() => { if (typeof window !== 'undefined') window.removeEventListener('keydown', onKey) })
</script>

<style scoped>
.tpl-editor {
  display: flex;
  flex-direction: column;
  height: 78vh;
}
.tpl-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--n-border-color);
  flex-shrink: 0;
}
.toolbar-label { font-size: var(--fs-base); color: var(--color-text-muted); margin-left: 4px; }

.tpl-editor > :last-child {
  display: flex;
  flex: 1;
  overflow: hidden;
}
/* viewport + sidebar side by side */
.tpl-viewport {
  flex: 1;
  overflow: auto;
  position: relative;
  background: #09061B;
  cursor: crosshair;
}
.tpl-viewport.split-active, .tpl-viewport.split-active .tpl-region {
  cursor: row-resize;
}
.tpl-sidebar {
  width: 190px;
  overflow-y: auto;
  border-left: 1px solid var(--n-border-color);
  background: var(--n-card-color);
  flex-shrink: 0;
}
/* wrap viewport + sidebar */
.tpl-editor {
  display: grid;
  grid-template-rows: auto 1fr;
  grid-template-columns: 1fr 190px;
  height: 78vh;
}
.tpl-toolbar { grid-column: 1 / -1; }
.tpl-viewport { grid-column: 1; grid-row: 2; }
.tpl-sidebar { grid-column: 2; grid-row: 2; }

.split-line {
  position: absolute;
  height: 0;
  border-top: 2px dashed #ff4040;
  pointer-events: none;
  z-index: 20;
  box-shadow: 0 0 6px rgba(255, 64, 64, 0.5);
}

.tpl-canvas {
  position: relative;
  user-select: none;
}
.tpl-bg {
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* region overlay — border/bg 由 inline style 按索引交替着色 */
.tpl-region {
  position: absolute;
  border: 2px solid;
  cursor: move;
  box-sizing: border-box;
  transition: border-color 0.1s, background 0.1s;
}
.tpl-region.active { z-index: 10; }
.tpl-region.drawing {
  border: 2px dashed #409eff;
  background: rgba(64, 158, 255, 0.12);
  pointer-events: none;
}

.tpl-rid {
  position: absolute; top: 2px; left: 4px;
  font-size: var(--fs-base); font-weight: var(--fw-semibold);
  text-shadow: 0 0 3px rgba(0,0,0,0.8);
  white-space: nowrap;
}
.tpl-rtype {
  position: absolute; top: 2px; right: 4px;
  font-size: var(--fs-base); color: var(--color-border); background: rgba(0,0,0,0.5);
  padding: 0 4px; border-radius: 2px;
  white-space: nowrap;
}
.tpl-rqno {
  position: absolute; bottom: 2px; left: 4px;
  font-size: var(--fs-base); font-weight: var(--fw-semibold); color: #f0c040;
  text-shadow: 0 0 3px rgba(0,0,0,0.8);
}
/* resize handles */
.h {
  position: absolute;
  width: 14px; height: 14px;
  background: #409eff;
  border: 2px solid #fff;
  border-radius: 2px;
  z-index: 2;
  display: none;
  box-shadow: 0 0 4px rgba(0,0,0,0.4);
}
.h:hover { background: #66b1ff; transform: scale(1.2); }
.tpl-region.active .h { display: block; }
.h-nw { top: -7px; left: -7px; cursor: nw-resize; }
.h-ne { top: -7px; right: -7px; cursor: ne-resize; }
.h-sw { bottom: -7px; left: -7px; cursor: sw-resize; }
.h-se { bottom: -7px; right: -7px; cursor: se-resize; }
.h-n { top: -7px; left: 50%; margin-left: -7px; cursor: n-resize; }
.h-s { bottom: -7px; left: 50%; margin-left: -7px; cursor: s-resize; }
.h-w { top: 50%; left: -7px; margin-top: -7px; cursor: w-resize; }
.h-e { top: 50%; right: -7px; margin-top: -7px; cursor: e-resize; }

/* sidebar */
.sidebar-title {
  padding: var(--space-2) 10px;
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  border-bottom: 1px solid var(--n-border-color);
}
.sidebar-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  font-size: var(--fs-base);
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.sidebar-item:hover { background: rgba(255,255,255,0.05); }
.sidebar-item.active { background: rgba(64,158,255,0.12); }
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.stype { color: var(--color-text-muted); margin-left: auto; }
.sqno { color: #f0c040; font-weight: var(--fw-semibold); }
</style>
