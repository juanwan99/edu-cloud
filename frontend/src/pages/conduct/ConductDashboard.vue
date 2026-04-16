<template>
  <div>
    <n-page-header title="德育概览" style="margin-bottom: 16px;" />

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: 16px;">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <template v-if="classId">
      <!-- Stats cards -->
      <n-grid :cols="4" :x-gap="16" :y-gap="16" style="margin-bottom: 16px;">
        <n-gi>
          <n-card size="small">
            <n-statistic label="总学生数" :value="stats.totalStudents" />
          </n-card>
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="本周加分" :value="stats.weeklyPlus">
              <template #suffix>分</template>
            </n-statistic>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="本周扣分" :value="stats.weeklyMinus">
              <template #suffix>分</template>
            </n-statistic>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="本周记录数" :value="stats.weeklyCount" />
          </n-card>
        </n-gi>
      </n-grid>

      <!-- Top / Bottom students -->
      <n-grid :cols="2" :x-gap="16" style="margin-bottom: 16px;">
        <n-gi>
          <n-card title="积分最高" size="small">
            <n-spin :show="loadingRankings">
              <n-list v-if="topStudents.length > 0" bordered size="small">
                <n-list-item v-for="s in topStudents" :key="s.student_id">
                  <div style="display: flex; justify-content: space-between;">
                    <span>{{ s.student_name }}</span>
                    <n-tag type="success" size="small">{{ s.total_points }}</n-tag>
                  </div>
                </n-list-item>
              </n-list>
              <n-empty v-else description="暂无数据" />
            </n-spin>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card title="积分最低" size="small">
            <n-spin :show="loadingRankings">
              <n-list v-if="bottomStudents.length > 0" bordered size="small">
                <n-list-item v-for="s in bottomStudents" :key="s.student_id">
                  <div style="display: flex; justify-content: space-between;">
                    <span>{{ s.student_name }}</span>
                    <n-tag type="error" size="small">{{ s.total_points }}</n-tag>
                  </div>
                </n-list-item>
              </n-list>
              <n-empty v-else description="暂无数据" />
            </n-spin>
          </n-card>
        </n-gi>
      </n-grid>

      <!-- Recent records -->
      <n-card title="最近记录">
        <n-spin :show="loadingRecords">
          <n-list v-if="recentRecords.length > 0" bordered size="small">
            <n-list-item v-for="r in recentRecords" :key="r.id">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                  <span style="font-weight: 500;">{{ r.student_name }}</span>
                  <span style="margin-left: 8px; color: rgba(255,255,255,0.5);">{{ r.note || r.rule_name || '' }}</span>
                </div>
                <n-space :size="8" align="center">
                  <n-tag :type="r.points >= 0 ? 'success' : 'error'" size="small">
                    {{ r.points >= 0 ? '+' : '' }}{{ r.points }}
                  </n-tag>
                  <span style="font-size: 12px; color: rgba(255,255,255,0.4);">
                    {{ r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : '' }}
                  </span>
                </n-space>
              </div>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无记录" />
        </n-spin>
      </n-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  NPageHeader, NGrid, NGi, NCard, NStatistic, NList, NListItem,
  NTag, NSpace, NSpin, NEmpty, NAlert,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import { getRecords, getStudentRankings } from '../../api/conduct'

const auth = useAuthStore()
const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const stats = ref({ totalStudents: 0, weeklyPlus: 0, weeklyMinus: 0, weeklyCount: 0 })
const topStudents = ref([])
const bottomStudents = ref([])
const recentRecords = ref([])
const loadingRankings = ref(false)
const loadingRecords = ref(false)

async function loadDashboard() {
  if (!classId.value) return
  loadingRankings.value = true
  loadingRecords.value = true

  // Load rankings for stats + top/bottom
  try {
    const res = await getStudentRankings(classId.value, {})
    const rankings = res.data.rankings || res.data || []
    stats.value.totalStudents = rankings.length
    topStudents.value = rankings.slice(0, 5)
    bottomStudents.value = rankings.length > 5 ? rankings.slice(-5).reverse() : []
  } catch {
    topStudents.value = []
    bottomStudents.value = []
  } finally {
    loadingRankings.value = false
  }

  // Load recent records + compute weekly stats
  try {
    const now = new Date()
    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
    const res = await getRecords(classId.value, {
      page: 1,
      page_size: 50,
      start_date: weekAgo.toISOString().split('T')[0],
    })
    const items = res.data.items || res.data || []
    recentRecords.value = items.slice(0, 10)
    stats.value.weeklyCount = items.length
    stats.value.weeklyPlus = items.filter(r => r.points > 0).reduce((s, r) => s + r.points, 0)
    stats.value.weeklyMinus = Math.abs(items.filter(r => r.points < 0).reduce((s, r) => s + r.points, 0))
  } catch {
    recentRecords.value = []
  } finally {
    loadingRecords.value = false
  }
}

onMounted(() => {
  if (classId.value) loadDashboard()
})
</script>
