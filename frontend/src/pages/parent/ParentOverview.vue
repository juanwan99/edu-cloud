<template>
  <PullRefresh :loading="refreshing" :last-update="lastUpdate" @refresh="loadData">
    <ParentSkeleton v-if="loading && !hasLoaded" :rows="3" />

    <template v-else>
      <div v-if="!currentChild" class="p-empty-guide">
        <ParentEmpty message="绑定孩子后即可查看">
          <template #action>
            <n-button type="primary" @click="$router.push('/parent/bind')">绑定孩子</n-button>
          </template>
        </ParentEmpty>
      </div>

      <template v-if="currentChild">
        <!-- Tonight's focus card -->
        <div class="focus-card" :class="{ 'focus-card--calm': !focusItems.length }">
          <template v-if="focusItems.length">
            <div class="focus-card__header">
              <Zap :size="18" />
              <span>今晚需关注 {{ focusItems.length }} 项</span>
            </div>
            <div v-for="(item, idx) in focusItems" :key="idx" class="focus-card__item" @click="item.action?.()">
              <span>{{ item.text }}</span>
              <ChevronRight :size="16" />
            </div>
          </template>
          <template v-else>
            <div class="focus-card__header focus-card__header--calm">
              <CircleCheck :size="18" />
              <span>今日无需关注事项</span>
            </div>
          </template>
        </div>

        <!-- Academic trend card -->
        <div class="p-card" v-if="examTrend.length || latestScore">
          <div class="p-card__header">
            <span class="p-card__title">学业趋势</span>
            <span class="p-card__action" @click="$router.push('/parent/scores')">详情 <ChevronRight :size="14" /></span>
          </div>
          <div class="trend-row">
            <div class="trend-chart" v-if="examTrend.length >= 2">
              <v-chart :option="sparklineOption" autoresize style="height: 80px;" />
            </div>
            <div class="trend-stats">
              <div class="trend-stat">
                <div class="trend-stat__label">班级位置</div>
                <div class="trend-stat__value">
                  前 <NumberRoll :value="classPercentile" size="var(--p-fs-section)" />%
                </div>
              </div>
              <div v-if="rankChange !== null" class="trend-stat">
                <div class="trend-stat__label">较上次</div>
                <div class="trend-stat__value" :class="rankChangeClass">
                  <component :is="rankChange < 0 ? TrendingDown : TrendingUp" :size="14" />
                  {{ Math.abs(rankChange) }} 位
                </div>
              </div>
            </div>
          </div>
          <div v-if="latestScore" class="trend-latest">
            最近：{{ latestScore.exam_name || '考试' }}
            <span class="trend-latest__score">总分 <NumberRoll :value="latestScore.total_score" /></span>
          </div>
          <div class="p-card__source">{{ dataSource }}</div>
        </div>

        <!-- Weekly behavior card -->
        <div class="p-card" v-if="behaviorSummary">
          <div class="p-card__header">
            <span class="p-card__title">本周表现</span>
            <span class="p-card__action" @click="$router.push('/parent/conduct')">详情 <ChevronRight :size="14" /></span>
          </div>
          <div class="behavior-summary">
            <span class="behavior-tag behavior-tag--good">加分 {{ behaviorSummary.positive_count || 0 }} 次</span>
            <span class="behavior-sep">·</span>
            <span class="behavior-tag behavior-tag--warn">待改善 {{ behaviorSummary.negative_count || 0 }} 项</span>
          </div>
          <div v-if="recentRecords.length" class="behavior-recent">
            <div v-for="r in recentRecords.slice(0, 3)" :key="r.id" class="behavior-item">
              <n-tag :type="r.points >= 0 ? 'success' : 'warning'" size="small" round>
                {{ r.points >= 0 ? '+' : '' }}{{ r.points }}
              </n-tag>
              <span class="behavior-item__text">{{ r.rule_name || r.note || '操行记录' }}</span>
            </div>
          </div>
          <div class="behavior-total">
            本学期累计 <NumberRoll :value="totalPoints" /> 分
          </div>
          <div class="p-card__source">{{ dataSource }}</div>
        </div>

        <!-- Latest updates -->
        <div class="p-card" v-if="updates.length">
          <div class="p-card__header">
            <span class="p-card__title">最新动态</span>
          </div>
          <div v-for="u in updates" :key="u.id" class="update-item">
            <span class="update-item__dot" />
            <span class="update-item__text">{{ u.text }}</span>
            <span class="update-item__time">{{ u.time }}</span>
          </div>
        </div>
      </template>
    </template>
  </PullRefresh>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NTag } from 'naive-ui'
import { Zap, CircleCheck, ChevronRight, TrendingUp, TrendingDown } from 'lucide-vue-next'
import VChart from 'vue-echarts'
import PullRefresh from '../../components/parent/PullRefresh.vue'
import ParentSkeleton from '../../components/parent/ParentSkeleton.vue'
import ParentEmpty from '../../components/parent/ParentEmpty.vue'
import NumberRoll from '../../components/parent/NumberRoll.vue'
import {
  getChildRecords, getChildScores, getChildRankings,
  getChildBehaviorSummary, getChildExams
} from '../../api/conduct'

const router = useRouter()

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const loading = ref(false)
const refreshing = ref(false)
const hasLoaded = ref(false)
const lastUpdate = ref('')

const examTrend = ref([])
const latestScore = ref(null)
const classPercentile = ref(0)
const rankChange = ref(null)
const behaviorSummary = ref(null)
const recentRecords = ref([])
const totalPoints = ref(0)
const updates = ref([])

const focusItems = computed(() => {
  const items = []
  if (behaviorSummary.value?.negative_count > 0) {
    items.push({
      text: `有 ${behaviorSummary.value.negative_count} 项待改善行为，建议今晚沟通`,
      action: () => router.push('/parent/conduct'),
    })
  }
  if (rankChange.value !== null && rankChange.value < -3) {
    items.push({
      text: `排名下降 ${Math.abs(rankChange.value)} 位，建议关注薄弱学科`,
      action: () => router.push('/parent/scores'),
    })
  }
  return items
})

const rankChangeClass = computed(() => {
  if (rankChange.value == null) return ''
  return rankChange.value < 0 ? 'trend-stat__value--down' : 'trend-stat__value--up'
})

const dataSource = computed(() => {
  const cls = props.currentChild?.class_name || ''
  return cls ? `来自 ${cls} · ${lastUpdate.value || ''} 更新` : ''
})

const sparklineOption = computed(() => ({
  grid: { top: 8, right: 8, bottom: 8, left: 8, containLabel: false },
  xAxis: { type: 'category', show: false, data: examTrend.value.map((_, i) => i) },
  yAxis: { type: 'value', show: false },
  series: [{
    type: 'line',
    data: examTrend.value,
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { color: '#F4DA4C', width: 2 },
    itemStyle: { color: '#F4DA4C' },
    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
      { offset: 0, color: 'rgba(244,218,76,0.25)' },
      { offset: 1, color: 'rgba(244,218,76,0)' },
    ] } },
  }],
}))

async function loadData() {
  const child = props.currentChild
  if (!child) return

  if (hasLoaded.value) refreshing.value = true
  else loading.value = true

  try {
    const [recordsRes, examsRes, rankRes, behaviorRes] = await Promise.allSettled([
      getChildRecords(child.student_id, { page: 1, size: 10 }),
      getChildExams(child.student_id),
      getChildRankings(child.student_id),
      getChildBehaviorSummary(child.student_id),
    ])

    if (recordsRes.status === 'fulfilled') {
      const data = recordsRes.value.data
      recentRecords.value = data.items || data || []
    }

    if (examsRes.status === 'fulfilled') {
      const exams = examsRes.value.data || []
      examTrend.value = exams.slice(0, 5).map(e => e.total_score).reverse()
      latestScore.value = exams[0] || null
    }

    if (rankRes.status === 'fulfilled') {
      const data = rankRes.value.data
      const rankings = Array.isArray(data) ? data : []
      const myEntry = rankings.find(r => r.student_id === child.student_id)
      if (myEntry && rankings.length > 0) {
        classPercentile.value = Math.round((myEntry.rank / rankings.length) * 100)
        rankChange.value = myEntry.previous_rank ? myEntry.previous_rank - myEntry.rank : null
        totalPoints.value = myEntry.total_points ?? 0
      }
    }

    if (behaviorRes.status === 'fulfilled') {
      behaviorSummary.value = behaviorRes.value.data
    }

    const buildUpdates = []
    if (latestScore.value) {
      buildUpdates.push({
        id: 'score',
        text: `${latestScore.value.exam_name || '考试'}成绩已发布`,
        time: formatRelative(latestScore.value.created_at),
      })
    }
    if (recentRecords.value.length > 0) {
      const latest = recentRecords.value[0]
      buildUpdates.push({
        id: 'record',
        text: latest.rule_name || latest.note || '操行记录',
        time: formatRelative(latest.created_at),
      })
    }
    updates.value = buildUpdates

    lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    hasLoaded.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function formatRelative(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  return days === 1 ? '昨天' : `${days}天前`
}

watch(() => props.currentChild, (child) => {
  examTrend.value = []
  latestScore.value = null
  classPercentile.value = 0
  rankChange.value = null
  behaviorSummary.value = null
  recentRecords.value = []
  totalPoints.value = 0
  updates.value = []
  hasLoaded.value = false
  if (child) loadData()
}, { immediate: true })
</script>

<style scoped>
.focus-card {
  background: var(--p-color-accent-surface);
  border: 1px solid rgba(244, 218, 76, 0.2);
  border-radius: var(--p-card-radius);
  padding: var(--p-card-padding);
  margin-bottom: var(--p-space-5);
}
.focus-card--calm {
  background: var(--p-color-success-surface);
  border-color: rgba(34, 197, 94, 0.2);
}
.focus-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--p-fs-body);
  font-weight: 600;
  color: var(--p-color-accent);
  margin-bottom: 8px;
}
.focus-card__header--calm {
  color: var(--p-color-success);
  margin-bottom: 0;
}
.focus-card__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  font-size: var(--p-fs-body);
  color: var(--p-text-2);
  cursor: pointer;
  border-top: 1px solid var(--p-border);
}

.p-card {
  background: var(--p-card-bg);
  border: var(--p-card-border);
  box-shadow: var(--p-card-shadow);
  border-radius: var(--p-card-radius);
  padding: var(--p-card-padding);
  margin-bottom: var(--p-space-5);
}
.p-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--p-space-3);
}
.p-card__title {
  font-size: var(--p-fs-section);
  font-weight: 600;
  color: var(--p-text-1);
}
.p-card__action {
  font-size: var(--p-fs-label);
  color: var(--p-text-3);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 2px;
}
.p-card__source {
  font-size: var(--p-fs-label);
  color: var(--p-text-3);
  margin-top: var(--p-space-3);
}

.trend-row { display: flex; gap: var(--p-space-4); align-items: center; }
.trend-chart { flex: 1; min-width: 0; }
.trend-stats { display: flex; flex-direction: column; gap: var(--p-space-2); }
.trend-stat__label { font-size: var(--p-fs-label); color: var(--p-text-3); }
.trend-stat__value {
  font-size: var(--p-fs-body);
  font-weight: 600;
  color: var(--p-text-1);
  display: flex;
  align-items: center;
  gap: 4px;
  font-variant-numeric: tabular-nums;
}
.trend-stat__value--up { color: var(--p-color-success); }
.trend-stat__value--down { color: var(--p-color-warning); }
.trend-latest {
  font-size: var(--p-fs-body);
  color: var(--p-text-2);
  margin-top: var(--p-space-3);
  padding-top: var(--p-space-3);
  border-top: 1px solid var(--p-border);
}
.trend-latest__score { font-weight: 600; color: var(--p-text-1); font-variant-numeric: tabular-nums; }

.behavior-summary { display: flex; align-items: center; gap: 8px; margin-bottom: var(--p-space-3); }
.behavior-tag { font-size: var(--p-fs-body); font-weight: 500; }
.behavior-tag--good { color: var(--p-color-success); }
.behavior-tag--warn { color: var(--p-color-warning); }
.behavior-sep { color: var(--p-text-3); }
.behavior-recent { display: flex; flex-direction: column; gap: 8px; margin-bottom: var(--p-space-3); }
.behavior-item { display: flex; align-items: center; gap: 8px; }
.behavior-item__text { font-size: var(--p-fs-body); color: var(--p-text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.behavior-total { font-size: var(--p-fs-body); color: var(--p-text-2); padding-top: var(--p-space-3); border-top: 1px solid var(--p-border); }

.update-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; }
.update-item__dot { width: 6px; height: 6px; border-radius: 50%; background: var(--p-color-accent); flex-shrink: 0; }
.update-item__text { flex: 1; font-size: var(--p-fs-body); color: var(--p-text-2); }
.update-item__time { font-size: var(--p-fs-label); color: var(--p-text-3); flex-shrink: 0; }

.p-empty-guide { padding-top: 60px; }
</style>
