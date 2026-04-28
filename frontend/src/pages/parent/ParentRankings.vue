<template>
  <div>
    <!-- Ranking Info Card -->
    <n-card v-if="myRanking" style="margin-bottom: 16px;">
      <div style="display: flex; align-items: center; gap: 16px;">
        <div style="font-size: 36px; line-height: 1;">
          {{ trophyIcon }}
        </div>
        <div style="flex: 1;">
          <div style="font-size: 22px; font-weight: 700; color: rgba(255,255,255,0.9);">
            第 {{ myRanking.rank }} 名
            <span style="font-size: 16px; font-weight: 400; color: rgba(255,255,255,0.45);">
              / 共 {{ rankings.length }} 人
            </span>
          </div>
          <div v-if="rankChange !== null" style="margin-top: 4px; font-size: 16px;">
            <span v-if="rankChange > 0" style="color: #63e2b7;">
              ↑ 上升 {{ rankChange }} 名
            </span>
            <span v-else-if="rankChange < 0" style="color: #e88080;">
              ↓ 下降 {{ Math.abs(rankChange) }} 名
            </span>
            <span v-else style="color: rgba(255,255,255,0.45);">
              — 排名不变
            </span>
          </div>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 28px; font-weight: 700; color: #63e2b7;">
            {{ myRanking.total_points }}
          </div>
          <div style="font-size: 16px; color: rgba(255,255,255,0.45);">总积分</div>
        </div>
      </div>
    </n-card>

    <!-- Score Distribution Bar -->
    <n-card v-if="rankings.length > 0" size="small" style="margin-bottom: 16px;">
      <div style="font-size: 16px; color: rgba(255,255,255,0.6); margin-bottom: 8px;">积分分布</div>
      <div style="position: relative; height: 28px; border-radius: 6px; overflow: hidden; display: flex;">
        <div
          :style="{
            width: distBands.top10 + '%',
            background: 'rgba(99, 226, 183, 0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '11px', color: 'rgba(255,255,255,0.8)',
            minWidth: distBands.top10 > 8 ? 'auto' : '0',
          }"
        >
          <span v-if="distBands.top10 > 8">前10%</span>
        </div>
        <div
          :style="{
            width: distBands.mid50 + '%',
            background: 'rgba(112, 161, 255, 0.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '11px', color: 'rgba(255,255,255,0.7)',
          }"
        >
          中间50%
        </div>
        <div
          :style="{
            width: distBands.bot40 + '%',
            background: 'rgba(255,255,255,0.08)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '11px', color: 'rgba(255,255,255,0.5)',
          }"
        >
          后40%
        </div>
      </div>
      <!-- Position marker -->
      <div v-if="myRanking" style="position: relative; height: 18px; margin-top: 2px;">
        <div
          :style="{
            position: 'absolute',
            left: myPositionPct + '%',
            transform: 'translateX(-50%)',
            fontSize: '11px',
            color: '#63e2b7',
            fontWeight: 600,
            whiteSpace: 'nowrap',
          }"
        >
          ▲ 我在这
        </div>
      </div>
    </n-card>

    <!-- Rankings Table -->
    <n-card title="班级排行榜">
      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="rankings"
          :row-class-name="rowClassName"
          :row-props="rowProps"
          size="small"
        />
      </n-spin>
    </n-card>
  </div>
</template>

<script setup>
import { ref, watch, computed, h } from 'vue'
import { NCard, NDataTable, NSpin, NTag } from 'naive-ui'
import { getChildRankings } from '../../api/conduct'

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const rankings = ref([])
const loading = ref(false)

// Find current child's ranking entry
const myRanking = computed(() => {
  if (!props.currentChild) return null
  return rankings.value.find(r => r.student_id === props.currentChild.student_id) || null
})

// Rank change (positive = improved, negative = dropped)
const rankChange = computed(() => {
  if (!myRanking.value || myRanking.value.previous_rank == null) return null
  return myRanking.value.previous_rank - myRanking.value.rank
})

// Trophy icon based on rank
const trophyIcon = computed(() => {
  if (!myRanking.value) return ''
  const rank = myRanking.value.rank
  if (rank === 1) return '🥇'
  if (rank === 2) return '🥈'
  if (rank === 3) return '🥉'
  return '🏆'
})

// Distribution bands (approximate)
const distBands = computed(() => {
  const n = rankings.length ? rankings.value.length : 0
  if (n === 0) return { top10: 10, mid50: 50, bot40: 40 }
  const top10Count = Math.max(1, Math.ceil(n * 0.1))
  const mid50Count = Math.max(1, Math.ceil(n * 0.5))
  const bot40Count = Math.max(0, n - top10Count - mid50Count)
  const total = top10Count + mid50Count + bot40Count
  return {
    top10: Math.round((top10Count / total) * 100),
    mid50: Math.round((mid50Count / total) * 100),
    bot40: Math.round((bot40Count / total) * 100),
  }
})

// Current child position percentage in the ranking
const myPositionPct = computed(() => {
  if (!myRanking.value || rankings.value.length === 0) return 50
  return Math.round(((myRanking.value.rank - 0.5) / rankings.value.length) * 100)
})

const columns = [
  {
    title: '排名',
    key: 'rank',
    width: 55,
    render(row) {
      const rank = row.rank
      let medal = ''
      if (rank === 1) medal = '🥇 '
      else if (rank === 2) medal = '🥈 '
      else if (rank === 3) medal = '🥉 '
      return medal + rank
    },
  },
  { title: '姓名', key: 'student_name' },
  { title: '总积分', key: 'total_points', width: 80 },
  {
    title: '积分变化',
    key: 'points_change',
    width: 80,
    render(row) {
      if (row.points_change == null) return '-'
      if (row.points_change > 0) {
        return h(NTag, { type: 'success', size: 'small', bordered: false }, () => `+${row.points_change}`)
      }
      if (row.points_change < 0) {
        return h(NTag, { type: 'error', size: 'small', bordered: false }, () => `${row.points_change}`)
      }
      return h(NTag, { size: 'small', bordered: false }, () => '0')
    },
  },
  {
    title: '排名变化',
    key: 'rank_change',
    width: 80,
    render(row) {
      if (row.previous_rank == null) return '-'
      const change = row.previous_rank - row.rank
      if (change > 0) {
        return h(NTag, { type: 'success', size: 'small', bordered: false }, () => `↑${change}`)
      }
      if (change < 0) {
        return h(NTag, { type: 'error', size: 'small', bordered: false }, () => `↓${Math.abs(change)}`)
      }
      return h(NTag, { size: 'small', bordered: false }, () => '-')
    },
  },
]

function rowClassName(row) {
  if (props.currentChild && row.student_id === props.currentChild.student_id) {
    return 'highlight-row'
  }
  return ''
}

function rowProps(row) {
  if (props.currentChild && row.student_id === props.currentChild.student_id) {
    return { style: 'border-left: 3px solid #63e2b7;' }
  }
  return {}
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
