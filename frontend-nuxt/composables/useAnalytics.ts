export function useAnalytics() {
  const api = useApi()
  const loading = ref(false)
  const advancedLoading = ref(false)

  const summary = ref<any>(null)
  const distribution = ref<any>(null)
  const gradeAggregates = ref<any>(null)
  const questions = ref<any>(null)

  const questionInsights = ref<any>(null)
  const diagnosis = ref<any>(null)

  async function loadBasicData(params: { exam_id: string; subject_id?: string }) {
    loading.value = true
    clearAdvancedData()
    try {
      const [s, d, g, q] = await Promise.all([
        api.getExamSummary(params.exam_id),
        // F003 修复：第二参数是 Record<string,any> 查询对象，不是字符串
        api.getExamDistribution(params.exam_id, { subject_id: params.subject_id }),
        api.getExamGradeAggregates(params.exam_id, { subject_id: params.subject_id }),
        params.subject_id ? api.getSubjectQuestions(params.subject_id) : Promise.resolve(null),
      ])
      summary.value = s
      distribution.value = d
      gradeAggregates.value = g
      questions.value = q
    } finally {
      loading.value = false
    }
  }

  async function loadAdvancedData(params: { exam_id: string; subject_id?: string; class_id?: string }) {
    if (questionInsights.value) return
    advancedLoading.value = true
    try {
      const [qi, diag] = await Promise.all([
        api.getQuestionInsights(params.exam_id, params.subject_id),
        api.getExamDiagnosis(params.exam_id, params.subject_id, params.class_id),
      ])
      questionInsights.value = qi
      diagnosis.value = diag
    } finally {
      advancedLoading.value = false
    }
  }

  function clearAdvancedData() {
    questionInsights.value = null
    diagnosis.value = null
  }

  function clearAll() {
    summary.value = null
    distribution.value = null
    gradeAggregates.value = null
    questions.value = null
    clearAdvancedData()
  }

  return {
    loading, advancedLoading,
    summary, distribution, gradeAggregates, questions,
    questionInsights, diagnosis,
    loadBasicData, loadAdvancedData, clearAll,
  }
}
