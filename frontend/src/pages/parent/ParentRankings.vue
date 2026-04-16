<template>
  <div>
    <n-card title="班级排行榜">
      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="rankings"
          :row-class-name="rowClassName"
          size="small"
        />
      </n-spin>
    </n-card>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { NCard, NDataTable, NSpin } from 'naive-ui'
import { getChildRankings } from '../../api/conduct'

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const rankings = ref([])
const loading = ref(false)

const columns = [
  { title: '排名', key: 'rank', width: 60 },
  { title: '姓名', key: 'student_name' },
  { title: '总积分', key: 'total_points', width: 100 },
]

function rowClassName(row) {
  if (props.currentChild && row.student_id === props.currentChild.student_id) {
    return 'highlight-row'
  }
  return ''
}

watch(() => props.currentChild, async (child) => {
  if (!child) return
  loading.value = true
  try {
    const res = await getChildRankings(child.student_id)
    rankings.value = res.data.rankings || res.data || []
  } catch {
    rankings.value = []
  } finally {
    loading.value = false
  }
}, { immediate: true })
</script>

<style scoped>
:deep(.highlight-row td) {
  background-color: rgba(99, 226, 183, 0.1) !important;
  font-weight: 600;
}
</style>
