import { ref, computed } from 'vue'
import { useMessage } from 'naive-ui'
import { flagAnswer } from '../../api/marking'

export function useScoring() {
  const message = useMessage()

  const currentScore = ref(null)
  const comment = ref('')
  const isGraded = ref(false)
  const currentAnomaly = ref(null)
  const selectedAnomalyType = ref(null)

  const anomalyOptions = [
    { label: '扫描错误', value: 'scan_error' },
    { label: '空白卷', value: 'blank' },
    { label: '字迹模糊', value: 'illegible' },
    { label: '答非所问', value: 'wrong_question' },
    { label: '疑似作弊', value: 'suspected_cheating' },
    { label: '其他', value: 'other' },
  ]
  const anomalyLabelMap = Object.fromEntries(anomalyOptions.map(o => [o.value, o.label]))
  const anomalyLabel = computed(() => anomalyLabelMap[currentAnomaly.value] || currentAnomaly.value)

  function setScore(s) {
    currentScore.value = s
  }

  function applyScoring(answerPayload, aiValue) {
    if (answerPayload.graded_score != null) {
      currentScore.value = answerPayload.graded_score
      comment.value = answerPayload.graded_comment || ''
      isGraded.value = true
    } else {
      currentScore.value = aiValue ? aiValue.score : null
      comment.value = ''
      isGraded.value = false
    }
    currentAnomaly.value = answerPayload.anomaly_type || null
    selectedAnomalyType.value = null
  }

  async function handleFlag(value, answerId) {
    if (!answerId) return
    try {
      await flagAnswer(answerId, value)
      currentAnomaly.value = value
      message.success('已标记异常')
    } catch {
      message.error('标记失败')
    }
  }

  async function handleClearFlag(answerId) {
    if (!answerId) return
    try {
      await flagAnswer(answerId, null)
      currentAnomaly.value = null
      selectedAnomalyType.value = null
      message.success('已取消标记')
    } catch {
      message.error('取消标记失败')
    }
  }

  return {
    currentScore, comment, isGraded,
    currentAnomaly, selectedAnomalyType,
    anomalyOptions, anomalyLabel,
    setScore, applyScoring,
    handleFlag, handleClearFlag,
  }
}
