<template>
  <PullRefresh :loading="refreshing" :last-update="lastUpdate" @refresh="loadData">
    <ParentSkeleton v-if="loading && !hasLoaded" :rows="3" />

    <template v-else-if="currentChild">
      <n-radio-group v-model:value="segment" :options="segments" size="small" class="segment-control" />

      <!-- Records Timeline -->
      <template v-if="segment === 'records'">
        <ParentEmpty v-if="!records.length && hasLoaded" message="本周还没有记录，继续加油" />
        <div v-for="(group, date) in groupedRecords" :key="date" class="timeline-group">
          <div class="timeline-date">{{ formatDate(date) }}</div>
          <div v-for="r in group" :key="r.id" class="timeline-item" :class="r.points >= 0 ? 'timeline-item--good' : 'timeline-item--warn'">
            <div class="timeline-dot" />
            <div class="timeline-content">
              <div class="timeline-row">
                <span class="timeline-name">{{ r.rule_name || r.note || '操行记录' }}</span>
                <n-tag :type="r.points >= 0 ? 'success' : 'warning'" size="small" round>
                  {{ r.points >= 0 ? '+' : '' }}{{ r.points }}
                </n-tag>
              </div>
              <div class="timeline-meta">
                <span>{{ formatTime(r.created_at) }}</span>
                <span v-if="r.teacher_name"> · {{ r.teacher_name }}</span>
              </div>
              <div v-if="r.points < 0 && r.category_name" class="timeline-rule-link">
                → 班规：{{ r.category_name }}
              </div>
            </div>
          </div>
        </div>
        <!-- Pagination -->
        <div v-if="recordTotal > pageSize" class="pagination">
          <n-button :disabled="recordPage <= 1" size="small" @click="recordPage--; loadRecords()">上一页</n-button>
          <span class="pagination-info">{{ recordPage }} / {{ Math.ceil(recordTotal / pageSize) }}</span>
          <n-button :disabled="recordPage * pageSize >= recordTotal" size="small" @click="recordPage++; loadRecords()">下一页</n-button>
        </div>
      </template>

      <!-- Rankings -->
      <template v-if="segment === 'rankings'">
        <div class="p-card" v-if="myRanking">
          <div class="ranking-hero">
            <div class="ranking-percentile">
              前 <NumberRoll :value="percentile" size="var(--p-fs-hero)" />%
            </div>
            <div class="ranking-detail">
              第 {{ myRanking.rank }} / {{ rankingsTotal }} 名
              <span v-if="myRanking.previous_rank" class="ranking-change" :class="rankChangeClass">
                <component :is="rankChangeIcon" :size="14" />
                {{ Math.abs(myRanking.rank - myRanking.previous_rank) }} 位
              </span>
            </div>
            <div class="ranking-points">累计 <NumberRoll :value="myRanking.total_points" /> 分</div>
          </div>
        </div>

        <div class="p-card" v-if="rankings.length">
          <div class="p-card__header">
            <span class="p-card__title">班级排名</span>
          </div>
          <div v-for="r in rankings" :key="r.student_id" class="rank-row" :class="{ 'rank-row--me': r.student_id === currentChild?.student_id }">
            <span class="rank-num">{{ r.rank }}</span>
            <span class="rank-name">{{ r.student_name }}</span>
            <span class="rank-points">{{ r.total_points }}</span>
          </div>
        </div>
        <ParentEmpty v-if="!rankings.length && hasLoaded" message="暂无排名数据" />
      </template>

      <!-- Class Rules -->
      <template v-if="segment === 'rules'">
        <div class="p-card" v-if="ruleCategories.length">
          <div class="rules-filter">
            <n-radio-group v-model:value="ruleFilter" size="small">
              <n-radio-button value="all">全部</n-radio-button>
              <n-radio-button value="positive">加分项</n-radio-button>
              <n-radio-button value="negative">扣分项</n-radio-button>
            </n-radio-group>
            <n-input v-model:value="ruleSearch" placeholder="搜索班规" size="small" clearable style="margin-top: 8px;">
              <template #prefix><Search :size="14" /></template>
            </n-input>
          </div>

          <n-collapse>
            <n-collapse-item
              v-for="cat in filteredCategories"
              :key="cat.id"
              :title="cat.name"
              :name="cat.id"
            >
              <template #header-extra>
                <n-tag size="small" type="info">{{ cat.items?.length || 0 }}</n-tag>
              </template>
              <div v-for="item in filteredItems(cat)" :key="item.id" class="rule-item">
                <span class="rule-item__name">{{ item.name }}</span>
                <n-tag :type="item.points >= 0 ? 'success' : 'warning'" size="small" :bordered="Math.abs(item.points) >= 5">
                  {{ item.points >= 0 ? '+' : '' }}{{ item.points }}
                </n-tag>
              </div>
              <div v-if="!filteredItems(cat).length" class="rule-item-empty">无匹配条目</div>
            </n-collapse-item>
          </n-collapse>
        </div>
        <ParentEmpty v-if="!ruleCategories.length && hasLoaded" message="暂无班规" />
      </template>
    </template>
  </PullRefresh>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import {
  NTag, NCollapse, NCollapseItem, NButton,
  NRadioGroup, NRadioButton, NInput
} from 'naive-ui'
import { TrendingUp, TrendingDown, Minus, Search } from 'lucide-vue-next'
import PullRefresh from '../../components/parent/PullRefresh.vue'
import ParentSkeleton from '../../components/parent/ParentSkeleton.vue'
import ParentEmpty from '../../components/parent/ParentEmpty.vue'
import NumberRoll from '../../components/parent/NumberRoll.vue'
import { getChildRecords, getChildRankings, getClassRulesParent } from '../../api/conduct'

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const segment = ref('records')
const segments = [
  { label: '记录', value: 'records' },
  { label: '排名', value: 'rankings' },
  { label: '班规', value: 'rules' },
]

const loading = ref(false)
const refreshing = ref(false)
const hasLoaded = ref(false)
const lastUpdate = ref('')

// Records
const records = ref([])
const recordPage = ref(1)
const recordTotal = ref(0)
const pageSize = 20

const groupedRecords = computed(() => {
  const groups = {}
  records.value.forEach(r => {
    const date = r.created_at ? r.created_at.split('T')[0] : 'unknown'
    if (!groups[date]) groups[date] = []
    groups[date].push(r)
  })
  return groups
})

// Rankings
const rankings = ref([])
const myRanking = computed(() => rankings.value.find(r => r.student_id === props.currentChild?.student_id) || null)
const rankingsTotal = computed(() => rankings.value.length)
const percentile = computed(() => {
  if (!myRanking.value || !rankingsTotal.value) return 0
  return Math.round((1 - (myRanking.value.rank - 1) / rankingsTotal.value) * 100)
})
const rankChangeClass = computed(() => {
  if (!myRanking.value?.previous_rank) return ''
  const diff = myRanking.value.previous_rank - myRanking.value.rank
  return diff > 0 ? 'ranking-change--up' : diff < 0 ? 'ranking-change--down' : ''
})
const rankChangeIcon = computed(() => {
  if (!myRanking.value?.previous_rank) return Minus
  const diff = myRanking.value.previous_rank - myRanking.value.rank
  return diff > 0 ? TrendingUp : diff < 0 ? TrendingDown : Minus
})

// Rules
const ruleCategories = ref([])
const ruleFilter = ref('all')
const ruleSearch = ref('')

const filteredCategories = computed(() => {
  return ruleCategories.value.filter(cat => {
    const items = filteredItems(cat)
    return items.length > 0
  })
})

function filteredItems(cat) {
  return (cat.items || []).filter(item => {
    if (ruleFilter.value === 'positive' && item.points < 0) return false
    if (ruleFilter.value === 'negative' && item.points >= 0) return false
    if (ruleSearch.value && !item.name.includes(ruleSearch.value)) return false
    return true
  })
}

async function loadRecords() {
  const child = props.currentChild
  if (!child) return
  try {
    const res = await getChildRecords(child.student_id, { page: recordPage.value, size: pageSize })
    const data = res.data
    records.value = data.items || data || []
    recordTotal.value = data.total || records.value.length
  } catch { records.value = [] }
}

async function loadData() {
  const child = props.currentChild
  if (!child) return

  if (hasLoaded.value) refreshing.value = true
  else loading.value = true

  try {
    const [recordsRes, rankRes, rulesRes] = await Promise.allSettled([
      getChildRecords(child.student_id, { page: 1, size: pageSize }),
      getChildRankings(child.student_id),
      child.class_id ? getClassRulesParent(child.class_id) : Promise.resolve({ data: [] }),
    ])

    if (recordsRes.status === 'fulfilled') {
      const data = recordsRes.value.data
      records.value = data.items || data || []
      recordTotal.value = data.total || records.value.length
      recordPage.value = 1
    }

    if (rankRes.status === 'fulfilled') {
      const data = rankRes.value.data
      rankings.value = Array.isArray(data) ? data : []
    }

    if (rulesRes.status === 'fulfilled') {
      const data = rulesRes.value.data
      ruleCategories.value = Array.isArray(data) ? data : data?.categories || []
    }

    lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    hasLoaded.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function formatDate(dateStr) {
  if (!dateStr || dateStr === 'unknown') return '未知日期'
  const d = new Date(dateStr)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (d.toDateString() === today.toDateString()) return '今天'
  if (d.toDateString() === yesterday.toDateString()) return '昨天'
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

watch(() => props.currentChild, (child) => {
  records.value = []
  rankings.value = []
  ruleCategories.value = []
  hasLoaded.value = false
  ruleSearch.value = ''
  ruleFilter.value = 'all'
  recordPage.value = 1
  if (child) loadData()
}, { immediate: true })
</script>

<style scoped>
.segment-control { margin-bottom: var(--p-space-5); }

.p-card {
  background: var(--p-card-bg);
  border: var(--p-card-border);
  box-shadow: var(--p-card-shadow);
  border-radius: var(--p-card-radius);
  padding: var(--p-card-padding);
  margin-bottom: var(--p-space-5);
}
.p-card__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--p-space-3); }
.p-card__title { font-size: var(--p-fs-section); font-weight: 600; color: var(--p-text-1); }

/* Timeline */
.timeline-group { margin-bottom: var(--p-space-4); }
.timeline-date { font-size: var(--p-fs-label); font-weight: 600; color: var(--p-text-3); margin-bottom: var(--p-space-2); padding-left: 20px; }
.timeline-item { display: flex; gap: 12px; padding: 8px 0; position: relative; }
.timeline-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; flex-shrink: 0; }
.timeline-item--good .timeline-dot { background: var(--p-color-success); }
.timeline-item--warn .timeline-dot { background: var(--p-color-warning); }
.timeline-content { flex: 1; min-width: 0; }
.timeline-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.timeline-name { font-size: var(--p-fs-body); color: var(--p-text-1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.timeline-meta { font-size: var(--p-fs-label); color: var(--p-text-3); margin-top: 2px; }
.timeline-rule-link { font-size: var(--p-fs-label); color: var(--p-color-primary); margin-top: 4px; cursor: pointer; }

.pagination { display: flex; align-items: center; justify-content: center; gap: var(--p-space-3); margin-top: var(--p-space-4); }
.pagination-info { font-size: var(--p-fs-label); color: var(--p-text-3); }

/* Rankings */
.ranking-hero { text-align: center; padding: var(--p-space-4) 0; }
.ranking-percentile { font-size: var(--p-fs-body); color: var(--p-text-1); font-weight: 600; }
.ranking-detail { font-size: var(--p-fs-body); color: var(--p-text-2); margin-top: var(--p-space-2); display: flex; align-items: center; justify-content: center; gap: 8px; }
.ranking-change { display: inline-flex; align-items: center; gap: 2px; font-size: var(--p-fs-label); }
.ranking-change--up { color: var(--p-color-success); }
.ranking-change--down { color: var(--p-color-warning); }
.ranking-points { font-size: var(--p-fs-label); color: var(--p-text-3); margin-top: var(--p-space-1); }

.rank-row { display: flex; align-items: center; gap: 12px; padding: 10px 8px; border-radius: 8px; }
.rank-row--me { background: var(--p-color-accent-surface); }
.rank-num { width: 28px; font-size: var(--p-fs-body); font-weight: 600; color: var(--p-text-1); text-align: center; font-variant-numeric: tabular-nums; }
.rank-name { flex: 1; font-size: var(--p-fs-body); color: var(--p-text-2); }
.rank-points { font-size: var(--p-fs-body); font-weight: 600; color: var(--p-text-1); font-variant-numeric: tabular-nums; }

/* Rules */
.rules-filter { margin-bottom: var(--p-space-4); }
.rule-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--p-border); }
.rule-item:last-child { border-bottom: none; }
.rule-item__name { font-size: var(--p-fs-body); color: var(--p-text-2); }
.rule-item-empty { font-size: var(--p-fs-label); color: var(--p-text-3); text-align: center; padding: 12px; }
</style>
