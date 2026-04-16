<template>
  <div>
    <n-page-header title="积分排行" style="margin-bottom: 16px;">
      <template #extra>
        <n-space>
          <n-select
            v-model:value="semesterId"
            :options="semesterOptions"
            placeholder="选择学期"
            clearable
            style="width: 180px;"
          />
        </n-space>
      </template>
    </n-page-header>

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: 16px;">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <n-tabs v-if="classId" v-model:value="activeTab" type="line" @update:value="handleTabChange">
      <n-tab-pane name="students" tab="学生排行">
        <n-spin :show="loadingStudents">
          <n-data-table
            :columns="studentColumns"
            :data="studentRankings"
            :pagination="false"
            size="small"
            :row-class-name="(row) => row.rank <= 3 ? 'top-rank' : ''"
          />
        </n-spin>
      </n-tab-pane>
      <n-tab-pane name="groups" tab="小组排行">
        <n-spin :show="loadingGroups">
          <n-data-table
            :columns="groupColumns"
            :data="groupRankings"
            :pagination="false"
            size="small"
          />
        </n-spin>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h, watch } from 'vue'
import {
  NPageHeader, NTabs, NTabPane, NDataTable, NSelect, NSpace,
  NSpin, NTag, NAlert,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import {
  getStudentRankings, getGroupRankings, getSemesters,
} from '../../api/conduct'

const auth = useAuthStore()
const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const activeTab = ref('students')
const semesterId = ref(null)
const semesterOptions = ref([])

const studentRankings = ref([])
const loadingStudents = ref(false)
const groupRankings = ref([])
const loadingGroups = ref(false)

const studentColumns = [
  {
    title: '排名',
    key: 'rank',
    width: 70,
    render: (row) => {
      if (row.rank <= 3) {
        const medals = { 1: '🥇', 2: '🥈', 3: '🥉' }
        return h('span', {}, medals[row.rank] || row.rank)
      }
      return row.rank
    },
  },
  { title: '姓名', key: 'student_name' },
  {
    title: '总积分',
    key: 'total_points',
    width: 100,
    render: (row) => h(NTag, {
      type: row.total_points >= 0 ? 'success' : 'error',
      size: 'small',
    }, () => row.total_points),
  },
]

const groupColumns = [
  { title: '排名', key: 'rank', width: 70 },
  { title: '小组', key: 'group_name' },
  {
    title: '总积分',
    key: 'total_points',
    width: 100,
    render: (row) => h(NTag, {
      type: row.total_points >= 0 ? 'success' : 'error',
      size: 'small',
    }, () => row.total_points),
  },
]

async function loadSemesters() {
  if (!classId.value) return
  try {
    const res = await getSemesters(classId.value)
    const list = res.data.semesters || res.data || []
    semesterOptions.value = list.map((s) => ({
      label: s.name + (s.is_active ? '（当前）' : ''),
      value: s.id,
    }))
  } catch {
    semesterOptions.value = []
  }
}

async function loadStudentRankings() {
  if (!classId.value) return
  loadingStudents.value = true
  try {
    const params = semesterId.value ? { semester_id: semesterId.value } : {}
    const res = await getStudentRankings(classId.value, params)
    studentRankings.value = res.data.rankings || res.data || []
  } catch {
    studentRankings.value = []
  } finally {
    loadingStudents.value = false
  }
}

async function loadGroupRankings() {
  if (!classId.value) return
  loadingGroups.value = true
  try {
    const params = semesterId.value ? { semester_id: semesterId.value } : {}
    const res = await getGroupRankings(classId.value, params)
    groupRankings.value = res.data.rankings || res.data || []
  } catch {
    groupRankings.value = []
  } finally {
    loadingGroups.value = false
  }
}

function handleTabChange(tab) {
  if (tab === 'students') loadStudentRankings()
  else loadGroupRankings()
}

watch(semesterId, () => {
  if (activeTab.value === 'students') loadStudentRankings()
  else loadGroupRankings()
})

onMounted(() => {
  if (classId.value) {
    loadSemesters()
    loadStudentRankings()
  }
})
</script>

<style scoped>
:deep(.top-rank td) {
  font-weight: 600;
}
</style>
