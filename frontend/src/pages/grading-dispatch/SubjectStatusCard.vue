<template>
  <div
    class="subject-card"
    :class="{ selected: isSelected }"
  >
    <div class="card-left">
      <n-checkbox
        :checked="isSelected"
        @update:checked="(v) => $emit('toggle', subject.subject_id, v)"
      />
      <span class="card-name">{{ subject.subject_name }}</span>
      <span class="stage-tag" :class="stageClass(subject.stage)">{{ stageLabel(subject.stage) }}</span>
      <span v-if="detectStatus === 'running'" class="detect-tag running">检测中…</span>
      <span v-else-if="detectStatus === 'done'" class="detect-tag done">检测完成</span>
      <span v-else-if="detectStatus === 'failed'" class="detect-tag failed">检测失败</span>
    </div>

    <div class="card-mid">
      <template v-if="subject.stage === 'cutting'">
        <div class="prog-row">
          <div class="prog-bar"><div class="prog-fill" :style="{ width: progressPct + '%' }"></div></div>
          <span class="prog-text">{{ progressPct }}%</span>
        </div>
      </template>
      <template v-else-if="subject.stage === 'idle'">
        <span class="card-detail muted">等待上传扫描图</span>
      </template>
      <template v-else-if="subject.stage === 'pending_detect'">
        <span class="card-detail">已上传 <b>{{ subject.scan_images }}</b> 份，等待模板检测</span>
      </template>
      <template v-else-if="subject.stage === 'pending_cut'">
        <span class="card-detail">模板就绪，<b>{{ subject.scan_images }}</b> 份待切割</span>
      </template>
      <template v-else-if="subject.answer_count > 0">
        <span class="card-detail ok">已切割 <b>{{ subject.answer_count }}</b> 份</span>
      </template>
    </div>

    <div class="card-stats">
      <span v-if="subject.scan_images" title="扫描份数">{{ subject.scan_images }} 份</span>
      <span v-if="subject.answer_count" title="已切割">{{ subject.answer_count }} 切</span>
    </div>

    <div class="card-actions">
      <n-button v-if="showDetect" size="small" @click="$emit('detect', subject)" :loading="isDetectLoading">模板检测</n-button>
      <n-button v-if="showCut" size="small" @click="$emit('preview', subject)" :loading="isDetectLoading">预览模板</n-button>
      <n-button v-if="showCut" size="small" type="primary" @click="$emit('cut', subject)" :loading="isCutLoading">切割</n-button>
      <n-button v-if="subject.stage === 'cutting'" size="small" type="error" @click="$emit('stop-cut')">停止</n-button>
      <n-button size="small" type="tertiary" @click="$emit('verify', subject)">校对配置</n-button>
    </div>
  </div>
</template>

<script setup>
import { NButton, NCheckbox } from 'naive-ui'

const props = defineProps({
  subject: { type: Object, required: true },
  isSelected: { type: Boolean, default: false },
  progressPct: { type: Number, default: 0 },
  detectStatus: { type: String, default: null },
  showDetect: { type: Boolean, default: false },
  showCut: { type: Boolean, default: false },
  isDetectLoading: { type: Boolean, default: false },
  isCutLoading: { type: Boolean, default: false },
})

defineEmits(['toggle', 'detect', 'preview', 'cut', 'stop-cut', 'verify'])

const STAGE_LABELS = {
  idle: '待上传', pending_detect: '待检测', pending_cut: '待切割',
  cutting: '切割中', ready: '已切割', done: '已切割',
  ai_grading: '已切割', reviewing: '已切割', failed: '已切割',
}
function stageLabel(stage) { return STAGE_LABELS[stage] || stage }
function stageClass(stage) {
  if (['ready', 'done', 'ai_grading', 'reviewing', 'failed'].includes(stage)) return 'tag-ready'
  return `tag-${stage}`
}
</script>

<style scoped>
.subject-card { display: grid; grid-template-columns: 200px 1fr 140px 180px; align-items: center; gap: 12px; padding: 12px 16px; background: var(--card-color, #fff); border: 1px solid var(--border-color, #e2e8e4); border-radius: 12px; transition: transform 0.15s ease-out, box-shadow 0.15s ease-out; }
.subject-card:hover { border-color: #c0d0c4; }
.subject-card.selected { background: #f8fdf9; border-color: #a0d0a8; }

.card-left { display: flex; align-items: center; gap: 10px; }
.card-name { font-weight: 700; font-size: 16px; }
.stage-tag { display: inline-block; padding: 1px 10px; border-radius: 50px; font-size: 16px; font-weight: 500; white-space: nowrap; }
.tag-idle { background: #f3f4f6; color: #6b7280; }
.tag-pending_detect { background: #fef3c7; color: #92400e; }
.tag-pending_cut { background: #e0f2fe; color: #0369a1; }
.tag-cutting { background: #dbeafe; color: #1e40af; }
.tag-ready { background: #dcfce7; color: #166534; }

.detect-tag { display: inline-block; padding: 1px 8px; border-radius: 50px; font-size: 16px; font-weight: 500; }
.detect-tag.running { background: #fef3c7; color: #92400e; }
.detect-tag.done { background: #dcfce7; color: #166534; }
.detect-tag.failed { background: #fee2e2; color: #dc2626; }

.card-mid { min-width: 0; }
.card-detail { font-size: 16px; color: #555; }
.card-detail b { font-weight: 600; }
.card-detail.muted { color: #aaa; }
.card-detail.ok { color: #16a34a; font-weight: 600; }

.prog-row { display: flex; align-items: center; gap: 10px; }
.prog-bar { flex: 1; height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }
.prog-fill { height: 100%; background: #3b82f6; border-radius: 3px; transition: width 0.3s; }
.prog-text { font-size: 16px; color: #666; white-space: nowrap; }

.card-stats { display: flex; gap: 6px; font-size: 16px; color: #999; }
.card-stats span { padding: 2px 6px; background: #f5f5f5; border-radius: 4px; }

.card-actions { display: flex; gap: 6px; justify-content: flex-end; }
</style>
