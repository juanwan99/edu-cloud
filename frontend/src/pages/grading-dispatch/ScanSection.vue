<template>
  <div class="scan-section">
    <div class="scan-header" @click="expanded = !expanded">
      <span class="scan-toggle">{{ expanded ? '▾' : '▸' }}</span>
      <span class="scan-title">扫描目录</span>
      <span class="scan-hint" v-if="scanResults.length > 0">已识别 {{ scanResults.length }} 个科目</span>
    </div>
    <div class="scan-body" v-if="expanded">
      <div class="scan-row">
        <n-button size="small" type="primary" @click="$emit('pick-folder')" :loading="uploadLoading">
          {{ uploadLoading ? `上传中 ${uploadProgress}` : '选择扫描文件夹' }}
        </n-button>
        <span class="scan-status" v-if="scanRootDir">{{ scanRootDir }}</span>
        <n-button v-if="scanRootDir" size="small" @click="$emit('scan-dir')" :loading="scanLoading">识别科目</n-button>
      </div>
      <div class="upload-hint" v-if="!scanRootDir">选择包含扫描图片的文件夹，按科目子文件夹组织（如 语文/、数学/）</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { NButton } from 'naive-ui'

const props = defineProps({
  scanRootDir: { type: String, default: '' },
  scanLoading: { type: Boolean, default: false },
  scanResults: { type: Array, default: () => [] },
  uploadLoading: { type: Boolean, default: false },
  uploadProgress: { type: String, default: '' },
  initialExpanded: { type: Boolean, default: true },
})

defineEmits(['pick-folder', 'scan-dir'])

const expanded = ref(props.initialExpanded)

// Collapse when scan results arrive from parent
watch(() => props.scanResults, (val) => {
  if (val.length > 0) expanded.value = false
})
</script>

<style scoped>
.scan-section { background: var(--card-color, #fff); border: 1px solid var(--border-color, #e2e8e4); border-radius: 12px; margin-bottom: 12px; overflow: hidden; }
.scan-header { display: flex; align-items: center; gap: 8px; padding: 10px 16px; cursor: pointer; user-select: none; }
.scan-header:hover { background: var(--body-color, #f9fafb); }
.scan-toggle { font-size: 12px; color: #8a9a8e; width: 14px; }
.scan-title { font-weight: 600; font-size: 13px; }
.scan-hint { font-size: 12px; color: #16a34a; margin-left: auto; }
.scan-body { padding: 0 16px 12px; }
.scan-row { display: flex; gap: 8px; }
.scan-status { font-size: 12px; color: #16a34a; font-family: monospace; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.upload-hint { font-size: 12px; color: #aaa; margin-top: 6px; }
</style>
