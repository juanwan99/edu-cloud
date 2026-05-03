<template>
  <div>
    <!-- No child bound: guide card -->
    <n-card v-if="!currentChild && !loading" class="guide-card">
      <div style="text-align: center; padding: var(--space-6) 0;">
        <div class="guide-icon">&#128100;</div>
        <n-h4 style="margin: var(--space-3) 0 var(--space-2);">尚未绑定孩子</n-h4>
        <p style="color: var(--color-text-muted); font-size: var(--fs-base); margin-bottom: var(--space-4);">
          请先绑定孩子信息，才能查看学习数据
        </p>
        <n-button type="primary" @click="$router.push('/parent/bind')">
          去绑定孩子
        </n-button>
      </div>
    </n-card>

    <template v-if="currentChild">
      <!-- Student info card -->
      <n-card class="info-card" style="margin-bottom: var(--space-4);">
        <div class="student-header">
          <div class="avatar-circle" :style="{ background: avatarBg }">
            {{ avatarLetter }}
          </div>
          <div class="student-info">
            <div class="student-name">{{ currentChild.student_name }}</div>
            <div class="student-class">{{ currentChild.class_name || '未分配班级' }}</div>
          </div>
          <div class="student-stats">
            <div class="stat-item stat-item--primary">
              <div class="stat-value">{{ totalPoints }}</div>
              <div class="stat-label">总积分</div>
            </div>
            <div class="stat-item" v-if="ranking">
              <div class="stat-value">{{ ranking }}</div>
              <div class="stat-label">排名</div>
            </div>
          </div>
        </div>
      </n-card>

      <!-- Score summary card -->
      <n-card v-if="latestScore" class="score-brief" style="margin-bottom: var(--space-4);">
        <div class="score-brief-header">
          <span style="font-size: var(--fs-base); font-weight: var(--fw-semibold);">最近考试</span>
          <n-tag size="small" type="info">{{ latestScore.exam_name || '考试' }}</n-tag>
        </div>
        <div class="score-brief-body">
          <div class="score-brief-item">
            <div class="score-brief-value" style="color: #F4DA4C;">{{ latestScore.total_score ?? '-' }}</div>
            <div class="score-brief-label">总分</div>
          </div>
          <div class="score-brief-item" v-if="latestScore.class_rank">
            <div class="score-brief-value">{{ latestScore.class_rank }}</div>
            <div class="score-brief-label">班名次</div>
          </div>
          <div class="score-brief-item" v-if="latestScore.grade_rank">
            <div class="score-brief-value">{{ latestScore.grade_rank }}</div>
            <div class="score-brief-label">年名次</div>
          </div>
        </div>
      </n-card>

      <!-- Quick entry buttons -->
      <div class="quick-entries" style="margin-bottom: var(--space-4);">
        <div class="quick-entry" @click="$router.push('/parent/scores')">
          <div class="quick-entry-icon" style="background: rgba(244,218,76,0.15); color: #F4DA4C;">&#128202;</div>
          <div class="quick-entry-label">成绩查询</div>
        </div>
        <div class="quick-entry" @click="$router.push('/parent/rankings')">
          <div class="quick-entry-icon" style="background: rgba(255,183,77,0.15); color: #ffb74d;">&#127942;</div>
          <div class="quick-entry-label">排行榜</div>
        </div>
        <div class="quick-entry" @click="$router.push('/parent/rules')">
          <div class="quick-entry-icon" style="background: rgba(100,181,246,0.15); color: #64b5f6;">&#128203;</div>
          <div class="quick-entry-label">班规</div>
        </div>
        <div class="quick-entry" @click="$router.push('/parent/details')">
          <div class="quick-entry-icon" style="background: rgba(206,147,216,0.15); color: #ce93d8;">&#128221;</div>
          <div class="quick-entry-label">操行记录</div>
        </div>
      </div>

      <!-- Recent records -->
      <n-card title="最近记录" style="margin-bottom: var(--space-4);">
        <n-spin :show="loading">
          <n-list v-if="records.length > 0" bordered>
            <n-list-item v-for="r in records" :key="r.id">
              <div class="record-item">
                <div class="record-icon" :class="r.points >= 0 ? 'record-icon--up' : 'record-icon--down'">
                  {{ r.points >= 0 ? '↑' : '↓' }}
                </div>
                <div class="record-content">
                  <div class="record-name">{{ r.rule_name || r.note || '操行记录' }}</div>
                  <div class="record-time">
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

      <n-button block secondary @click="$router.push('/parent/details')">
        查看详细记录
      </n-button>
    </template>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { NCard, NStatistic, NList, NListItem, NTag, NButton, NEmpty, NSpin, NH4 } from 'naive-ui'
import { getChildRecords, getChildScores, getChildRankings } from '../../api/conduct'

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const records = ref([])
const totalPoints = ref(0)
const ranking = ref(null)
const latestScore = ref(null)
const loading = ref(false)

const avatarLetter = computed(() => {
  const name = props.currentChild?.student_name || ''
  return name.charAt(0) || '?'
})

const avatarBg = computed(() => {
  const name = props.currentChild?.student_name || ''
  const colors = ['#F4DA4C', '#64b5f6', '#ffb74d', '#ce93d8', '#ef9a9a', '#80cbc4']
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
})

watch(() => props.currentChild, async (child) => {
  if (!child) return
  loading.value = true
  try {
    totalPoints.value = child.total_points ?? 0

    // Fetch records
    const recordsRes = await getChildRecords(child.student_id, { page: 1, page_size: 10 })
    records.value = recordsRes.data.items || recordsRes.data || []

    // Fetch latest score
    try {
      const scoreRes = await getChildScores(child.student_id, { limit: 1 })
      const scoreData = scoreRes.data
      if (Array.isArray(scoreData) && scoreData.length > 0) {
        latestScore.value = scoreData[0]
      } else {
        latestScore.value = null
      }
    } catch {
      latestScore.value = null
    }

    // Fetch ranking
    try {
      const rankRes = await getChildRankings(child.student_id)
      const rankData = rankRes.data
      if (rankData && rankData.rank) {
        ranking.value = rankData.rank
      } else if (Array.isArray(rankData) && rankData.length > 0) {
        // Find current child in rankings list
        const myRank = rankData.find(r => r.student_id === child.student_id)
        ranking.value = myRank?.rank ?? null
      } else {
        ranking.value = null
      }
    } catch {
      ranking.value = null
    }
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}, { immediate: true })
</script>

<style scoped>
.guide-card {
  margin-top: 60px;
}

.guide-icon {
  font-size: 48px;
  line-height: 1;
  margin-bottom: 8px;
}

.info-card {
  border-radius: var(--r-lg);
}

.student-header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.avatar-circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: var(--fw-semibold);
  color: #1a1a2e;
  flex-shrink: 0;
}

.student-info {
  flex: 1;
  min-width: 0;
}

.student-name {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  color: rgba(255, 255, 255, 0.95);
}

.student-class {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.45);
  margin-top: 2px;
}

.student-stats {
  display: flex;
  gap: 16px;
  text-align: center;
}

.stat-item {
  min-width: 48px;
}

.stat-value {
  font-size: var(--fs-xl);
  font-weight: var(--fw-semibold);
  color: rgba(255, 255, 255, 0.85);
}

.stat-item--primary .stat-value {
  color: #F4DA4C;
}

.stat-label {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.4);
  margin-top: 2px;
}

.score-brief-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.score-brief-body {
  display: flex;
  gap: 24px;
}

.score-brief-item {
  text-align: center;
}

.score-brief-value {
  font-size: 22px;
  font-weight: var(--fw-semibold);
  color: rgba(255, 255, 255, 0.85);
}

.score-brief-label {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.4);
  margin-top: 2px;
}

.quick-entries {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.quick-entry {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  padding: 12px 4px;
  border-radius: var(--r-md);
  transition: background 0.2s;
}

.quick-entry:hover {
  background: rgba(255, 255, 255, 0.05);
}

.quick-entry-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  margin-bottom: 6px;
}

.quick-entry-label {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.65);
}

.record-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.record-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  flex-shrink: 0;
}

.record-icon--up {
  background: rgba(244, 218, 76, 0.15);
  color: #F4DA4C;
}

.record-icon--down {
  background: rgba(230, 57, 70, 0.15);
  color: #e63946;
}

.record-content {
  flex: 1;
  min-width: 0;
}

.record-name {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.record-time {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.35);
  margin-top: 2px;
}
</style>
