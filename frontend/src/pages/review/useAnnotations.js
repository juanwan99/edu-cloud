import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import client from '../../api/client'

export function useAnnotations() {
  const message = useMessage()

  const annotations = ref([])
  const annEditing = ref(null)
  const annTarget = ref('score')
  const annComment = ref('')
  const annSuggestedScore = ref(null)

  function getAnnotation(blankNo) {
    const key = blankNo ?? '_overall'
    return annotations.value.find(a => (a.blankNo ?? '_overall') === key)
  }

  function startAnnotation(blankNo) {
    annEditing.value = blankNo ?? '_overall'
    annComment.value = ''
    annTarget.value = 'score'
    annSuggestedScore.value = null
  }

  function removeAnnotation(blankNo, resultId) {
    const key = blankNo ?? '_overall'
    annotations.value = annotations.value.filter(a => (a.blankNo ?? '_overall') !== key)
    saveAnnotations(resultId)
  }

  function submitAnnotation(blankNo, resultId, itemMaxScore) {
    if (!annComment.value.trim()) return
    const key = blankNo ?? '_overall'
    annotations.value = annotations.value.filter(a => (a.blankNo ?? '_overall') !== key)
    const item = { target: annTarget.value, blankNo: blankNo || null, comment: annComment.value.trim() }
    if (annTarget.value === 'score' && annSuggestedScore.value != null) {
      item.suggested_score = annSuggestedScore.value
    }
    annotations.value.push(item)
    annEditing.value = null
    saveAnnotations(resultId)
  }

  async function saveAnnotations(resultId) {
    if (!resultId) return
    try {
      await client.patch(`/grading/results/${resultId}/annotations`, annotations.value)
    } catch {
      message.error('标注保存失败')
    }
  }

  function resetAnnotations(newAnnotations) {
    annotations.value = newAnnotations || []
    annEditing.value = null
  }

  return {
    annotations, annEditing, annTarget, annComment, annSuggestedScore,
    getAnnotation, startAnnotation, removeAnnotation, submitAnnotation,
    resetAnnotations,
  }
}
