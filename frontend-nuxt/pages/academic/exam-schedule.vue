<template>
  <div class="p-6">
    <h2 class="text-xl font-bold mb-4">考试安排</h2>

    <!-- Filters -->
    <div class="flex gap-4 mb-6">
      <el-select v-model="selectedSemesterId" placeholder="学期" class="w-60">
        <el-option v-for="s in academic.semesters.value" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <el-select v-model="selectedType" placeholder="考试类型" class="w-32" clearable>
        <el-option label="全部" value="" />
        <el-option label="月考" value="monthly" />
        <el-option label="期中" value="midterm" />
        <el-option label="期末" value="final" />
        <el-option label="测验" value="quiz" />
      </el-select>
    </div>

    <!-- Timeline -->
    <el-timeline>
      <el-timeline-item
        v-for="exam in filteredExams" :key="exam.id"
        :type="examStatus(exam) === 'ongoing' ? 'primary' : examStatus(exam) === 'completed' ? 'success' : 'info'"
        :hollow="examStatus(exam) === 'upcoming'"
        :style="examStatus(exam) === 'ongoing' ? { borderLeft: '3px solid var(--el-color-primary)' } : examStatus(exam) === 'completed' ? { opacity: 0.8 } : {}"
      >
        <div class="flex items-center gap-2 mb-2">
          <span class="font-bold">{{ exam.exam_name }}</span>
          <el-tag size="small" :type="examStatus(exam) === 'ongoing' ? 'success' : examStatus(exam) === 'completed' ? 'info' : 'primary'">
            {{ { upcoming: '待考', ongoing: '进行中', completed: '已完成' }[examStatus(exam)] }}
          </el-tag>
        </div>
        <div class="text-sm text-gray-500 mb-2">{{ exam.subjects.length }} 科</div>
        <div v-for="sub in exam.subjects.filter((s: any) => s.exam_start)" :key="sub.id" class="text-sm mb-1">
          <el-tag size="small" class="mr-2">{{ sub.name }}</el-tag>
          <span class="text-gray-600">{{ formatTime(sub.exam_start) }} - {{ formatTime(sub.exam_end) }}</span>
          <span v-if="sub.exam_room" class="text-gray-400 ml-2">{{ sub.exam_room }}</span>
        </div>
        <div v-if="!exam.subjects.some((s: any) => s.exam_start)" class="text-sm text-gray-400">暂未安排时间</div>
      </el-timeline-item>
    </el-timeline>

    <el-empty v-if="!filteredExams.length" description="暂无考试" />
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const academic = useAcademic()

const selectedSemesterId = ref('')
const selectedType = ref('')
const exams = ref<any[]>([])

const filteredExams = computed(() => {
  let list = exams.value
  if (selectedType.value) {
    list = list.filter((e: any) => e.exam_type === selectedType.value)
  }
  return list
})

function examStatus(exam: any): string {
  const now = new Date()
  const subjects = exam.subjects || []
  const scheduled = subjects.filter((s: any) => s.exam_start && s.exam_end)
  if (!scheduled.length) return 'upcoming'
  if (scheduled.every((s: any) => new Date(s.exam_end) < now)) return 'completed'
  if (scheduled.some((s: any) => new Date(s.exam_start) <= now && now <= new Date(s.exam_end))) return 'ongoing'
  return 'upcoming'
}

function formatTime(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

async function loadExams() {
  const params: Record<string, any> = {}
  if (selectedSemesterId.value) {
    const sem = academic.semesters.value.find((s: any) => s.id === selectedSemesterId.value)
    if (sem) params.semester = sem.school_year
  }
  const examList = await api.getExams(params)
  const items = Array.isArray(examList) ? examList : examList?.items || []

  const results = []
  for (const e of items) {
    try {
      const schedule = await api.getExamSchedule(e.id)
      results.push({ ...e, ...schedule })
    } catch {
      results.push({ ...e, subjects: [] })
    }
  }
  exams.value = results
}

watch(selectedSemesterId, () => { if (selectedSemesterId.value) loadExams() })

onMounted(async () => {
  await academic.loadSemesters()
  if (academic.semesters.value.length) {
    const current = academic.semesters.value.find((s: any) => s.is_current)
    selectedSemesterId.value = current?.id || academic.semesters.value[0].id
  }
})
</script>
