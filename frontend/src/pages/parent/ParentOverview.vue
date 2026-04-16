<template>
  <div>
    <n-card v-if="currentChild" style="margin-bottom: 16px;">
      <n-statistic label="当前总积分" :value="totalPoints" />
      <div style="margin-top: 8px; color: rgba(255,255,255,0.5); font-size: 13px;">
        {{ currentChild.student_name }}
      </div>
    </n-card>

    <n-card title="最近记录" style="margin-bottom: 16px;">
      <n-spin :show="loading">
        <n-list v-if="records.length > 0" bordered>
          <n-list-item v-for="r in records" :key="r.id">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <div>{{ r.rule_name || r.note || '操行记录' }}</div>
                <div style="font-size: 12px; color: rgba(255,255,255,0.4);">
                  {{ r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : '' }}
                </div>
              </div>
              <n-tag :type="r.points >= 0 ? 'success' : 'error'" size="small">
                {{ r.points >= 0 ? '+' : '' }}{{ r.points }}
              </n-tag>
            </div>
          </n-list-item>
        </n-list>
        <n-empty v-else description="暂无记录" />
      </n-spin>
    </n-card>

    <n-button v-if="currentChild" block secondary @click="$router.push('/parent/details')">
      查看详细记录
    </n-button>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { NCard, NStatistic, NList, NListItem, NTag, NButton, NEmpty, NSpin } from 'naive-ui'
import { getChildRecords } from '../../api/conduct'

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const records = ref([])
const totalPoints = ref(0)
const loading = ref(false)

watch(() => props.currentChild, async (child) => {
  if (!child) return
  loading.value = true
  try {
    totalPoints.value = child.total_points ?? 0
    const res = await getChildRecords(child.student_id, { page: 1, page_size: 10 })
    records.value = res.data.items || res.data || []
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}, { immediate: true })
</script>
