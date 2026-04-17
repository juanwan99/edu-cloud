interface PowerOption {
  grade: string
  classes: {
    class: string
    subjects: {
      subject: string
      examids: string[]
    }[]
  }[]
}

interface ExamInfo {
  name: string
  event_time: string
  type: number
}

interface AnalysisParams {
  clazz: string
  subject: string
  examids: string[]
  isTeach: boolean
}

export function usePowerOptions() {
  const api = useApi()

  const tree = ref<PowerOption[]>([])
  const examInfoMap = ref<Record<string, ExamInfo>>({})

  const selectedGrade = ref('')
  const selectedClass = ref('')
  const selectedSubject = ref('')
  const selectedExamIds = ref<string[]>([])

  const gradeOptions = computed(() => tree.value.map((g) => g.grade))

  const classOptions = computed(() => {
    const grade = tree.value.find((g) => g.grade === selectedGrade.value)
    return grade?.classes.map((c) => c.class) || []
  })

  const subjectOptions = computed(() => {
    const grade = tree.value.find((g) => g.grade === selectedGrade.value)
    const cls = grade?.classes.find((c) => c.class === selectedClass.value)
    return cls?.subjects.map((s) => s.subject) || []
  })

  const examOptions = computed(() => {
    const grade = tree.value.find((g) => g.grade === selectedGrade.value)
    const cls = grade?.classes.find((c) => c.class === selectedClass.value)
    const subj = cls?.subjects.find((s) => s.subject === selectedSubject.value)
    return (subj?.examids || []).map((id) => ({
      id,
      ...(examInfoMap.value[id] || { name: id, event_time: '', type: 0 }),
    }))
  })

  const analysisParams = computed<AnalysisParams>(() => ({
    clazz: selectedClass.value,
    subject: selectedSubject.value,
    examids: selectedExamIds.value,
    isTeach: false,
  }))

  watch(selectedGrade, () => {
    selectedClass.value = classOptions.value[0] || ''
  })
  watch(selectedClass, () => {
    selectedSubject.value = subjectOptions.value[0] || ''
  })
  watch(selectedSubject, () => {
    const exams = examOptions.value
    selectedExamIds.value = exams.length ? [exams[0].id] : []
  })

  async function load(examType?: number, year?: number) {
    try {
      const res = await api.getPowerOptions({ exam_type: examType, year })
      tree.value = res.powerOptions || []
      examInfoMap.value = res.examInfoMap || {}
      if (tree.value.length) {
        selectedGrade.value = tree.value[0].grade
      }
    } catch {
      tree.value = []
      examInfoMap.value = {}
    }
  }

  return {
    load,
    tree,
    examInfoMap,
    selectedGrade,
    selectedClass,
    selectedSubject,
    selectedExamIds,
    gradeOptions,
    classOptions,
    subjectOptions,
    examOptions,
    analysisParams,
  }
}
