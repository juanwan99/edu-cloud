export function useAcademic() {
  const api = useApi()
  const semesters = ref<any[]>([])
  const currentSemester = ref<any>(null)
  const periods = ref<any[]>([])
  const timetable = ref<any[]>([])
  const timetableStats = ref<any[]>([])
  const loading = ref(false)

  async function loadSemesters(schoolYear?: string) {
    loading.value = true
    try {
      semesters.value = await api.getSemesters(schoolYear ? { school_year: schoolYear } : undefined)
    } finally {
      loading.value = false
    }
  }

  async function loadCurrentSemester() {
    currentSemester.value = await api.getCurrentSemester()
  }

  async function loadPeriods(semesterId: string) {
    periods.value = await api.getPeriods({ semester_id: semesterId })
  }

  async function loadTimetable(semesterId: string, classId?: string, teacherId?: string) {
    loading.value = true
    try {
      const params: Record<string, any> = { semester_id: semesterId }
      if (classId) params.class_id = classId
      if (teacherId) params.teacher_id = teacherId
      timetable.value = await api.getTimetable(params)
    } finally {
      loading.value = false
    }
  }

  async function loadTimetableStats(semesterId: string, classId: string) {
    timetableStats.value = await api.getTimetableStats({ semester_id: semesterId, class_id: classId })
  }

  function semesterProgress(semester: any): { percent: number; week: number } {
    if (!semester?.start_date || !semester?.end_date) return { percent: 0, week: 0 }
    const start = new Date(semester.start_date).getTime()
    const end = new Date(semester.end_date).getTime()
    const now = Date.now()
    const total = end - start
    const elapsed = Math.min(Math.max(now - start, 0), total)
    const percent = Math.round((elapsed / total) * 100)
    const week = Math.ceil(elapsed / (7 * 24 * 60 * 60 * 1000))
    return { percent, week }
  }

  return {
    semesters, currentSemester, periods, timetable, timetableStats, loading,
    loadSemesters, loadCurrentSemester, loadPeriods, loadTimetable, loadTimetableStats,
    semesterProgress,
  }
}
