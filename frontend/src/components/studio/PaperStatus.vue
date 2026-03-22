<template>
  <n-card size="small" v-if="paperId">
    <template #header>
      <n-text>论文进度</n-text>
    </template>
    <n-space vertical>
      <n-text>阶段: {{ status?.stage || '加载中...' }}</n-text>
      <n-text>状态: {{ status?.status || '-' }}</n-text>
      <n-text v-if="status?.cost_yuan">费用: ¥{{ status.cost_yuan }}</n-text>
      <n-progress
        :percentage="stagePercent"
        :status="status?.stage === 'completed' ? 'success' : 'default'"
      />
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useStudioStore } from '../../stores/studio.js'

const props = defineProps({ paperId: String })
const studioStore = useStudioStore()
const status = ref(null)
let timer = null

const STAGES = ['intake', 'brainstorm', 'literature', 'outline', 'writing', 'review', 'format', 'output', 'completed']
const stagePercent = computed(() => {
  if (!status.value?.stage) return 0
  const idx = STAGES.indexOf(status.value.stage)
  return Math.round(((idx + 1) / STAGES.length) * 100)
})

async function poll() {
  if (props.paperId) {
    status.value = await studioStore.getPaperStatus(props.paperId)
    if (status.value?.stage === 'completed') {
      clearInterval(timer)
    }
  }
}

onMounted(() => {
  poll()
  timer = setInterval(poll, 15000)
})
onUnmounted(() => clearInterval(timer))
</script>
