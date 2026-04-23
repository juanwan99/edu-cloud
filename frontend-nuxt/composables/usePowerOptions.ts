export interface ExamNode {
  id: string
  exam_id: string
  subject_id: string
  name: string
  exam_date: string | null
  student_count: number
}

export interface SubjectNode {
  id: string
  code: string
  name: string
  exams: ExamNode[]
}

export interface ClassNode {
  id: string
  name: string
  subjects: SubjectNode[]
}

export interface GradeNode {
  id: string
  name: string
  classes: ClassNode[]
}

export function usePowerOptions() {
  const tree = ref<GradeNode[]>([])
  const loading = ref(false)

  const selectedGrade = ref('')
  const selectedClassId = ref('all')
  const selectedSubjectId = ref('')
  const selectedExamId = ref('')

  const gradeOptions = computed(() => tree.value.map(g => g.name))

  const classOptions = computed(() => {
    const grade = tree.value.find(g => g.name === selectedGrade.value)
    return grade?.classes ?? []
  })

  const subjectOptions = computed(() => {
    const cls = classOptions.value.find(c => c.id === selectedClassId.value)
    return cls?.subjects ?? []
  })

  const examOptions = computed(() => {
    const subj = subjectOptions.value.find(s => s.id === selectedSubjectId.value)
    return subj?.exams ?? []
  })

  watch(selectedGrade, () => {
    selectedClassId.value = classOptions.value[0]?.id ?? 'all'
  })
  watch(selectedClassId, () => {
    selectedSubjectId.value = subjectOptions.value[0]?.id ?? ''
  })
  watch(selectedSubjectId, () => {
    selectedExamId.value = examOptions.value[0]?.exam_id ?? ''
  })

  const analysisParams = computed(() => ({
    exam_id: selectedExamId.value,
    subject_id: selectedSubjectId.value,
    class_id: selectedClassId.value === 'all' ? null : selectedClassId.value,
  }))

  const hasSelection = computed(() => !!selectedExamId.value)

  async function load(examType?: string, year?: number) {
    loading.value = true
    try {
      const api = useApi()
      const data = await api.getPowerOptions({
        exam_type: examType,
        year,
      })
      tree.value = data.grades
      if (tree.value.length) {
        selectedGrade.value = tree.value[0].name
      }
    } finally {
      loading.value = false
    }
  }

  return {
    load, tree, loading,
    selectedGrade, selectedClassId, selectedSubjectId, selectedExamId,
    gradeOptions, classOptions, subjectOptions, examOptions,
    analysisParams, hasSelection,
  }
}
