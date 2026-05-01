<template>
  <n-modal :show="show" @update:show="$emit('update:show', $event)" preset="card"
           title="文档裁剪 — 框选题目和答案区域" style="width:94vw;max-width:1500px" :mask-closable="false">
    <div class="dc-editor">
      <div class="dc-toolbar">
        <n-upload v-if="!pages.length" :show-file-list="false" accept=".pdf,.docx"
                  :custom-request="handleUpload">
          <n-button size="small" type="primary" :loading="uploading">上传文档 (PDF/Word)</n-button>
        </n-upload>

        <template v-if="pages.length">
          <n-button-group size="small">
            <n-button :disabled="currentPage <= 0" @click="currentPage--">上一页</n-button>
            <n-button disabled style="min-width:80px">{{ currentPage + 1 }} / {{ pages.length }}</n-button>
            <n-button :disabled="currentPage >= pages.length - 1" @click="currentPage++">下一页</n-button>
          </n-button-group>

          <n-divider vertical />

          <n-button-group size="small">
            <n-button @click="zoom = Math.max(0.1, zoom - 0.1)">−</n-button>
            <n-button disabled style="min-width:56px">{{ pct }}%</n-button>
            <n-button @click="zoom = Math.min(3, zoom + 0.1)">+</n-button>
            <n-button @click="fitZoom">适应</n-button>
          </n-button-group>

          <n-divider vertical />
          <span class="toolbar-hint">在图片上拖拽画框选区域</span>
        </template>

        <div style="flex:1" />
        <n-button size="small" quaternary @click="$emit('update:show', false)">取消</n-button>
        <n-button size="small" type="primary" :disabled="!crops.length" :loading="saving"
                  @click="handleSave">保存裁剪</n-button>
      </div>

      <div class="dc-body" v-if="pages.length">
        <div class="dc-viewport" ref="viewport"
             @mousedown="onViewportMouseDown"
             @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseUp"
             @wheel.prevent="onWheel">
          <div class="dc-canvas" :style="canvasStyle">
            <img :src="pages[currentPage].image_url" class="dc-bg" draggable="false" @load="onImgLoad" />

            <div v-for="(c, idx) in pageCrops" :key="c.id"
                 class="dc-region" :class="{ active: selectedId === c.id }"
                 :style="rStyle(c, idx)" @mousedown.stop="startDrag($event, c)">
              <span class="dc-label" :style="{ color: palette(idx).solid }">
                {{ c.questionNum ? '第' + c.questionNum + '题' : '未标号' }} {{ c.field === 'content' ? '题干' : '答案' }}{{ c.score ? ' ' + c.score + '分' : '' }}
              </span>
              <div class="h h-nw" @mousedown.stop="startResize($event, c, 'nw')"/>
              <div class="h h-ne" @mousedown.stop="startResize($event, c, 'ne')"/>
              <div class="h h-sw" @mousedown.stop="startResize($event, c, 'sw')"/>
              <div class="h h-se" @mousedown.stop="startResize($event, c, 'se')"/>
              <div class="h h-n"  @mousedown.stop="startResize($event, c, 'n')"/>
              <div class="h h-s"  @mousedown.stop="startResize($event, c, 's')"/>
              <div class="h h-w"  @mousedown.stop="startResize($event, c, 'w')"/>
              <div class="h h-e"  @mousedown.stop="startResize($event, c, 'e')"/>
            </div>

            <div v-if="drawing" class="dc-region drawing" :style="drawStyle" />
          </div>
        </div>

        <div class="dc-sidebar" @mousedown.stop>
          <div v-if="savedHistory.length" class="saved-section">
            <div class="sidebar-title">已保存</div>
            <div v-for="s in savedHistory" :key="s.key" class="saved-item">
              <span class="saved-dot">&#10003;</span>
              {{ s.label }}
            </div>
            <n-divider />
          </div>

          <div class="sidebar-title">待保存 ({{ crops.length }})</div>
          <template v-for="c in cropTree" :key="c.id">
            <div class="dc-item" :class="{ active: selectedId === c.id }"
                 @click="goToCrop(c)">
              <span class="item-color" :style="{ background: palette(cropIdx(c)).solid }" />
              <div class="item-info">
                <n-input size="tiny" v-model:value="c.questionNum" placeholder="题号"
                         style="width:50px" @click.stop />
                <n-input-number size="tiny" v-model:value="c.score" :min="0" :max="200"
                         placeholder="分" style="width:60px" @click.stop />
                <n-select size="tiny" :value="c.field" @update:value="v => c.field = v"
                          :options="fieldOptions" style="width:60px" @click.stop />
              </div>
              <n-button size="tiny" text type="error" @click.stop="deleteCrop(c.id)">✕</n-button>
            </div>
            <!-- 子题 -->
            <div v-for="child in c.children" :key="child.id"
                 class="dc-item dc-child" :class="{ active: selectedId === child.id }"
                 @click="goToCrop(child)">
              <span class="child-indent">└</span>
              <span class="item-color small" :style="{ background: palette(cropIdx(child)).solid }" />
              <div class="item-info">
                <n-input size="tiny" v-model:value="child.questionNum" placeholder="题号"
                         style="width:50px" @click.stop />
                <n-input-number size="tiny" v-model:value="child.score" :min="0" :max="200"
                         placeholder="分" style="width:60px" @click.stop />
                <n-select size="tiny" :value="child.field" @update:value="v => child.field = v"
                          :options="fieldOptions" style="width:60px" @click.stop />
              </div>
              <n-button size="tiny" text @click.stop="unindentCrop(child)" title="取消缩进">↑</n-button>
              <n-button size="tiny" text type="error" @click.stop="deleteCrop(child.id)">✕</n-button>
            </div>
          </template>

          <n-divider v-if="crops.length" />
          <div v-if="crops.length" class="sidebar-hint">
            填写题号和分值。选中两个区域后点"设为子题"建立层级，父题题干会自动包含在子题的细则生成中。
          </div>
          <div v-if="crops.length > 1" style="margin-top:6px">
            <n-button size="tiny" :disabled="!canSetChild" @click="setAsChild">
              设为子题（选中项→归入上方）
            </n-button>
          </div>
        </div>
      </div>

      <div v-else-if="!uploading" class="dc-empty">
        请上传 PDF 或 Word 文档
      </div>
    </div>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useMessage, NModal, NButton, NButtonGroup, NSelect, NInput, NInputNumber, NUpload, NDivider } from 'naive-ui'
import { renderDocPages, getDocPages } from '../api/cards'
import client from '../api/client'

const props = defineProps({
  show: Boolean,
  questions: { type: Array, default: () => [] },
  subjectId: { type: String, default: '' },
})
const emit = defineEmits(['update:show', 'save'])
const message = useMessage()

const COLORS = [
  { border: 'rgba(64,158,255,0.8)',  bg: 'rgba(64,158,255,0.12)', bgA: 'rgba(64,158,255,0.25)', solid: '#409eff' },
  { border: 'rgba(245,108,108,0.8)', bg: 'rgba(245,108,108,0.12)', bgA: 'rgba(245,108,108,0.25)', solid: '#f56c6c' },
  { border: 'rgba(103,194,58,0.8)',  bg: 'rgba(103,194,58,0.12)', bgA: 'rgba(103,194,58,0.25)', solid: '#67c23a' },
  { border: 'rgba(230,162,60,0.8)',  bg: 'rgba(230,162,60,0.12)', bgA: 'rgba(230,162,60,0.25)', solid: '#e6a23c' },
  { border: 'rgba(144,147,255,0.8)', bg: 'rgba(144,147,255,0.12)', bgA: 'rgba(144,147,255,0.25)', solid: '#9093ff' },
  { border: 'rgba(56,203,187,0.8)',  bg: 'rgba(56,203,187,0.12)', bgA: 'rgba(56,203,187,0.25)', solid: '#38cbbb' },
]
function palette(idx) { return COLORS[idx % COLORS.length] }

const fieldOptions = [
  { label: '题干', value: 'content' },
  { label: '答案', value: 'answer' },
]


const pages = ref([])
const currentPage = ref(0)
const uploading = ref(false)
const saving = ref(false)
const crops = ref([])
const selectedId = ref(null)
const viewport = ref(null)
const zoom = ref(0.4)
const pct = computed(() => Math.round(zoom.value * 100))
const dragState = ref(null)
const drawing = ref(null)
const savedHistory = ref([])

const curPageData = computed(() => pages.value[currentPage.value] || {})
const pageCrops = computed(() => crops.value.filter(c => c.page === currentPage.value))

watch(() => props.show, async (v) => {
  if (v) {
    loadSavedHistory()
    restoreCrops()
    if (!pages.value.length && props.subjectId) await loadExistingPages()
    nextTick(fitZoom)
  }
  if (!v) { saveCropsToStorage(); selectedId.value = null }
})

function loadSavedHistory() {
  if (!props.questions || !props.questions.length) return
  savedHistory.value = []
  for (const q of props.questions) {
    const name = q.name || q.question_name || ''
    const contentCount = q.content_image_count || (q.content_images || []).length || 0
    const answerCount = q.answer_image_count || (q.reference_answer_images || []).length || 0
    if (contentCount) {
      savedHistory.value.push({ key: `${name}-content`, label: `第${name}题 题干 ${contentCount}图` })
    }
    if (answerCount) {
      savedHistory.value.push({ key: `${name}-answer`, label: `第${name}题 答案 ${answerCount}图` })
    }
  }
}

async function loadExistingPages() {
  try {
    const res = await getDocPages(props.subjectId)
    const rawPages = res.data.pages || []
    if (!rawPages.length) return
    for (const pg of rawPages) {
      try {
        const resp = await client.get('/card/doc-page-image', {
          params: { path: pg.image_url }, responseType: 'blob', timeout: 30000,
        })
        pg.image_url = URL.createObjectURL(resp.data)
      } catch {}
    }
    pages.value = rawPages
    currentPage.value = 0
  } catch {}
}

const storageKey = computed(() => props.subjectId ? `doc-crop-${props.subjectId}` : '')

function saveCropsToStorage() {
  if (!storageKey.value || !crops.value.length) return
  const data = crops.value.map(c => ({
    id: c.id, page: c.page, questionNum: c.questionNum,
    score: c.score, parentId: c.parentId, seq: c.seq, field: c.field, rect: c.rect,
  }))
  try { localStorage.setItem(storageKey.value, JSON.stringify(data)) } catch {}
}

function restoreCrops() {
  if (!storageKey.value) return
  try {
    const raw = localStorage.getItem(storageKey.value)
    if (raw) crops.value = JSON.parse(raw)
  } catch {}
}

async function handleUpload({ file }) {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file.file)
    if (props.subjectId) formData.append('subject_id', props.subjectId)
    const res = await renderDocPages(formData)
    const rawPages = res.data.pages || []
    for (const pg of rawPages) {
      try {
        const resp = await client.get('/card/doc-page-image', {
          params: { path: pg.image_url },
          responseType: 'blob',
          timeout: 30000,
        })
        pg.image_url = URL.createObjectURL(resp.data)
      } catch { /* keep original url as fallback */ }
    }
    pages.value = rawPages
    currentPage.value = 0
    if (!pages.value.length) message.warning('文档无法渲染为图片')
    else nextTick(fitZoom)
  } catch (e) {
    message.error('上传失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    uploading.value = false
  }
}

function fitZoom() {
  if (!viewport.value || !curPageData.value.width) return
  const vw = viewport.value.clientWidth - 20
  const vh = viewport.value.clientHeight
  zoom.value = Math.min(vw / curPageData.value.width, vh / curPageData.value.height, 1)
}

const canvasStyle = computed(() => {
  const pg = curPageData.value
  if (!pg.width) return {}
  return {
    width: pg.width + 'px',
    height: pg.height + 'px',
    transform: `scale(${zoom.value})`,
    transformOrigin: '0 0',
  }
})

function onImgLoad() {}
function onWheel(e) {
  const delta = e.deltaY > 0 ? -0.05 : 0.05
  zoom.value = Math.min(3, Math.max(0.1, zoom.value + delta))
}

function toImageCoords(e) {
  if (!viewport.value) return { x: 0, y: 0 }
  const vr = viewport.value.getBoundingClientRect()
  return {
    x: (e.clientX - vr.left + viewport.value.scrollLeft) / zoom.value,
    y: (e.clientY - vr.top + viewport.value.scrollTop) / zoom.value,
  }
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

function rStyle(c, idx) {
  const globalIdx = crops.value.indexOf(c)
  const { x1, y1, x2, y2 } = c.rect
  const p = COLORS[globalIdx % COLORS.length]
  const isActive = selectedId.value === c.id
  return {
    left: x1 + 'px', top: y1 + 'px', width: (x2 - x1) + 'px', height: (y2 - y1) + 'px',
    borderColor: isActive ? p.solid : p.border,
    background: isActive ? p.bgA : p.bg,
  }
}

function startDrag(e, crop) {
  selectedId.value = crop.id
  const p = toImageCoords(e)
  dragState.value = { mode: 'move', crop, startX: p.x, startY: p.y, origRect: { ...crop.rect } }
}

function startResize(e, crop, handle) {
  selectedId.value = crop.id
  const p = toImageCoords(e)
  dragState.value = { mode: 'resize', crop, handle, startX: p.x, startY: p.y, origRect: { ...crop.rect } }
}

function onViewportMouseDown(e) {
  if (e.target !== viewport.value && !e.target.classList.contains('dc-canvas') && !e.target.classList.contains('dc-bg')) return
  e.preventDefault()
  selectedId.value = null
  const p = toImageCoords(e)
  drawing.value = { x1: p.x, y1: p.y, x2: p.x, y2: p.y }
}

const drawStyle = computed(() => {
  if (!drawing.value) return {}
  const d = drawing.value
  const x = Math.min(d.x1, d.x2), y = Math.min(d.y1, d.y2)
  return { left: x + 'px', top: y + 'px', width: Math.abs(d.x2 - d.x1) + 'px', height: Math.abs(d.y2 - d.y1) + 'px' }
})

function onMouseMove(e) {
  const p = toImageCoords(e)
  const pg = curPageData.value
  if (drawing.value) {
    drawing.value.x2 = clamp(p.x, 0, pg.width)
    drawing.value.y2 = clamp(p.y, 0, pg.height)
    return
  }
  if (!dragState.value) return
  const s = dragState.value
  const dx = p.x - s.startX, dy = p.y - s.startY
  const W = pg.width, H = pg.height
  if (s.mode === 'move') {
    const w = s.origRect.x2 - s.origRect.x1, h = s.origRect.y2 - s.origRect.y1
    const nx1 = clamp(s.origRect.x1 + dx, 0, W - w)
    const ny1 = clamp(s.origRect.y1 + dy, 0, H - h)
    s.crop.rect = { x1: Math.round(nx1), y1: Math.round(ny1), x2: Math.round(nx1 + w), y2: Math.round(ny1 + h) }
  } else if (s.mode === 'resize') {
    const r = { ...s.origRect }
    const h = s.handle
    if (h.includes('n')) r.y1 = clamp(r.y1 + dy, 0, r.y2 - 20)
    if (h.includes('s')) r.y2 = clamp(r.y2 + dy, r.y1 + 20, H)
    if (h.includes('w')) r.x1 = clamp(r.x1 + dx, 0, r.x2 - 20)
    if (h.includes('e')) r.x2 = clamp(r.x2 + dx, r.x1 + 20, W)
    s.crop.rect = { x1: Math.round(r.x1), y1: Math.round(r.y1), x2: Math.round(r.x2), y2: Math.round(r.y2) }
  }
}

function onMouseUp() {
  if (drawing.value) {
    const d = drawing.value
    const w = Math.abs(d.x2 - d.x1), h = Math.abs(d.y2 - d.y1)
    if (w > 20 && h > 20) {
      const crop = {
        id: 'C' + Date.now(),
        page: currentPage.value,
        questionNum: '',
        score: null,
        parentId: null,
        seq: '1',
        field: 'content',
        rect: {
          x1: Math.round(Math.min(d.x1, d.x2)),
          y1: Math.round(Math.min(d.y1, d.y2)),
          x2: Math.round(Math.max(d.x1, d.x2)),
          y2: Math.round(Math.max(d.y1, d.y2)),
        },
      }
      crops.value.push(crop)
      selectedId.value = crop.id
    }
    drawing.value = null
  }
  dragState.value = null
}

function deleteCrop(id) {
  crops.value = crops.value.filter(c => c.id !== id)
  if (selectedId.value === id) selectedId.value = null
}

function goToCrop(c) {
  selectedId.value = c.id
  if (c.page !== currentPage.value) currentPage.value = c.page
}

// 层级相关
const cropTree = computed(() => {
  const topLevel = crops.value.filter(c => !c.parentId)
  return topLevel.map(c => ({
    ...c,
    children: crops.value.filter(ch => ch.parentId === c.id),
  }))
})

function cropIdx(c) { return Math.max(0, crops.value.findIndex(x => x.id === c.id)) }

const canSetChild = computed(() => {
  if (!selectedId.value) return false
  const sel = crops.value.find(c => c.id === selectedId.value)
  if (!sel || sel.parentId) return false
  const idx = crops.value.indexOf(sel)
  const above = crops.value.slice(0, idx).filter(c => !c.parentId)
  return above.length > 0
})

function setAsChild() {
  const sel = crops.value.find(c => c.id === selectedId.value)
  if (!sel) return
  const idx = crops.value.indexOf(sel)
  const above = crops.value.slice(0, idx).filter(c => !c.parentId)
  if (!above.length) return
  sel.parentId = above[above.length - 1].id
}

function unindentCrop(c) { c.parentId = null }

async function cropToBlob(c) {
  const pg = pages.value[c.page]
  const img = new Image()
  await new Promise((resolve, reject) => { img.onload = resolve; img.onerror = reject; img.src = pg.image_url })
  const canvas = document.createElement('canvas')
  const { x1, y1, x2, y2 } = c.rect
  canvas.width = x2 - x1; canvas.height = y2 - y1
  canvas.getContext('2d').drawImage(img, x1, y1, x2 - x1, y2 - y1, 0, 0, x2 - x1, y2 - y1)
  return new Promise(r => canvas.toBlob(r, 'image/png'))
}

async function handleSave() {
  const incomplete = crops.value.filter(c => !c.questionNum)
  if (incomplete.length) {
    message.warning('有区域未填写题号')
    return
  }
  saving.value = true
  try {
    const blobMap = {}
    for (const c of crops.value) {
      blobMap[c.id] = await cropToBlob(c)
    }

    const results = []
    for (const node of cropTree.value) {
      const seq = parseInt(node.seq, 10) || 1
      if (node.children.length === 0) {
        results.push({ questionNum: node.questionNum, field: node.field, seq, blob: blobMap[node.id], score: node.score })
      } else {
        const parentBlob = blobMap[node.id]
        for (const child of node.children) {
          const childSeq = parseInt(child.seq, 10) || 1
          results.push({ questionNum: child.questionNum, field: child.field, seq: childSeq, blob: blobMap[child.id], score: child.score,
            parentBlob, parentQuestionNum: node.questionNum })
        }
      }
    }

    results.sort((a, b) => a.seq - b.seq)
    emit('save', results)

    for (const c of crops.value) {
      const parent = c.parentId ? crops.value.find(p => p.id === c.parentId) : null
      savedHistory.value.push({
        key: `${c.questionNum}-${c.field}-${Date.now()}`,
        label: `${parent ? '  └ ' : ''}第${c.questionNum}题 ${c.field === 'content' ? '题干' : '答案'}${c.score ? ' ' + c.score + '分' : ''}`,
      })
    }
    crops.value = []
    selectedId.value = null
    if (storageKey.value) try { localStorage.removeItem(storageKey.value) } catch {}
    message.success(`已保存 ${results.length} 个区域，可继续标注`)
  } catch (e) {
    message.error('裁剪保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.dc-editor { display: flex; flex-direction: column; height: 75vh; }
.dc-toolbar {
  display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-color, #2e3e34);
  flex-shrink: 0;
}
.toolbar-hint { font-size: var(--fs-base); color: #8a9a8e; }
.dc-body { display: flex; flex: 1; min-height: 0; }
.dc-viewport {
  flex: 1; overflow: auto; position: relative; cursor: crosshair;
  background: #1a1a1a; user-select: none; -webkit-user-select: none;
}
.dc-canvas { position: relative; }
.dc-bg { display: block; width: 100%; height: 100%; pointer-events: none; }
.dc-region {
  position: absolute; border: 2px solid; cursor: move; box-sizing: border-box;
}
.dc-region.drawing { border: 2px dashed rgba(64,158,255,0.8); background: rgba(64,158,255,0.1); pointer-events: none; }
.dc-region.active { z-index: 2; }
.dc-label {
  position: absolute; top: 2px; left: 4px; font-size: var(--fs-base); font-weight: var(--fw-semibold);
  text-shadow: 0 0 3px rgba(0,0,0,0.8);
  white-space: nowrap; pointer-events: none;
}
.h {
  position: absolute; width: 8px; height: 8px; background: #fff;
  border: 1px solid #409eff; border-radius: 2px; z-index: 3;
}
.h-nw { top: -4px; left: -4px; cursor: nw-resize; }
.h-ne { top: -4px; right: -4px; cursor: ne-resize; }
.h-sw { bottom: -4px; left: -4px; cursor: sw-resize; }
.h-se { bottom: -4px; right: -4px; cursor: se-resize; }
.h-n { top: -4px; left: calc(50% - 4px); cursor: n-resize; }
.h-s { bottom: -4px; left: calc(50% - 4px); cursor: s-resize; }
.h-w { top: calc(50% - 4px); left: -4px; cursor: w-resize; }
.h-e { top: calc(50% - 4px); right: -4px; cursor: e-resize; }

.dc-sidebar {
  width: 260px; border-left: 1px solid var(--border-color, #2e3e34);
  padding: 10px; overflow-y: auto; flex-shrink: 0;
}
.sidebar-title { font-size: var(--fs-base); font-weight: var(--fw-bold); color: #8a9a8e; margin-bottom: 8px; }
.sidebar-hint { font-size: var(--fs-base); color: var(--color-text-secondary); line-height: 1.5; }
.saved-section { margin-bottom: var(--space-1); }
.saved-item {
  font-size: var(--fs-base); color: #8a9a8e; padding: 3px 4px;
  display: flex; align-items: center; gap: var(--space-1);
}
.saved-dot { color: #67c23a; font-size: var(--fs-base); }
.dc-item {
  display: flex; align-items: center; gap: 6px; padding: 6px var(--space-1);
  border-radius: 6px; cursor: pointer; margin-bottom: 4px;
}
.dc-item:hover { background: var(--body-color, #242e28); }
.dc-item.active { background: #1a3020; border: 1px solid #3a6040; }
.item-color { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.item-info { display: flex; gap: 4px; flex: 1; min-width: 0; align-items: center; flex-wrap: wrap; }
.dc-child { padding-left: var(--space-4); }
.child-indent { color: var(--color-text-secondary); font-size: var(--fs-base); margin-right: 2px; flex-shrink: 0; }
.item-color.small { width: 7px; height: 7px; }

.dc-empty { display: flex; align-items: center; justify-content: center; flex: 1; color: #8a9a8e; font-size: var(--fs-base); }
</style>
