<template>
  <div class="p-6">
    <h2 class="text-xl font-bold mb-4">课程表</h2>

    <!-- Filters -->
    <div class="flex gap-4 mb-4">
      <el-select v-model="selectedGrade" placeholder="年级" class="w-32">
        <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
      </el-select>
      <el-select v-model="selectedClassId" placeholder="班级" class="w-40">
        <el-option v-for="c in filteredClasses" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-radio-group v-model="viewMode">
        <el-radio-button value="class">按班级</el-radio-button>
        <el-radio-button value="teacher">按教师</el-radio-button>
      </el-radio-group>
    </div>

    <div class="flex gap-4">
      <!-- Timetable grid -->
      <el-card class="flex-1">
        <el-table :data="gridRows" border stripe :cell-class-name="cellClassName">
          <el-table-column prop="period_label" label="节次" width="100" fixed />
          <el-table-column v-for="d in 5" :key="d" :label="weekdayLabels[d-1]" min-width="140">
            <template #default="{ row }">
              <div v-if="row.slots[d]" class="text-center text-xs leading-5"
                   :style="{ backgroundColor: subjectColor(row.slots[d].subject_code) + '20' }">
                <div class="font-medium" :style="{ color: subjectColor(row.slots[d].subject_code) }">
                  {{ row.slots[d].subject_code }}
                </div>
                <div class="text-gray-500">{{ row.slots[d].teacher_id?.slice(0,6) }}</div>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Stats sidebar -->
      <el-card class="w-48" v-if="academic.timetableStats.value.length">
        <template #header><span class="font-bold text-sm">课时统计</span></template>
        <div v-for="s in academic.timetableStats.value" :key="s.subject_code" class="flex justify-between text-sm mb-2">
          <el-tag size="small" :color="subjectColor(s.subject_code) + '20'"
                  :style="{ color: subjectColor(s.subject_code), borderColor: subjectColor(s.subject_code) }">
            {{ s.subject_code }}
          </el-tag>
          <span>{{ s.count }}节</span>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const academic = useAcademic()

const selectedGrade = ref('')
const selectedClassId = ref('')
const viewMode = ref('class')
const classes = ref<any[]>([])

const grades = computed(() => [...new Set(classes.value.map((c: any) => c.grade))])
const filteredClasses = computed(() =>
  selectedGrade.value ? classes.value.filter((c: any) => c.grade === selectedGrade.value) : classes.value
)

const weekdayLabels = ['周一', '周二', '周三', '周四', '周五']
const todayWeekday = new Date().getDay()

const SUBJECT_COLORS: Record<string, string> = {
  chinese: '#E74C3C', math: '#3498DB', english: '#2ECC71',
  physics: '#9B59B6', chemistry: '#E67E22', biology: '#1ABC9C',
  history: '#F39C12', geography: '#16A085', politics: '#8E44AD',
}

function subjectColor(code: string) {
  return SUBJECT_COLORS[code] || '#95A5A6'
}

function cellClassName({ columnIndex }: any) {
  if (columnIndex > 0 && columnIndex === todayWeekday) return 'bg-blue-50'
  return ''
}

const gridRows = computed(() => {
  const periods = academic.periods.value.filter((p: any) => p.period_type !== 'break')
  return periods.map((p: any) => {
    const slotsMap: Record<number, any> = {}
    for (const s of academic.timetable.value) {
      if (s.period_id === p.id) slotsMap[s.weekday] = s
    }
    return { period_label: `${p.name}\n${p.start_time}-${p.end_time}`, slots: slotsMap }
  })
})

watch([selectedClassId], async () => {
  if (!selectedClassId.value || !academic.currentSemester.value?.id) return
  const semId = academic.currentSemester.value.id
  await academic.loadTimetable(semId, selectedClassId.value)
  await academic.loadTimetableStats(semId, selectedClassId.value)
})

onMounted(async () => {
  await academic.loadCurrentSemester()
  const resp = await api.getClasses()
  classes.value = Array.isArray(resp) ? resp : resp?.items || []
  if (academic.currentSemester.value?.id) {
    await academic.loadPeriods(academic.currentSemester.value.id)
  }
})
</script>
