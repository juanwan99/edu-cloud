/**
 * ReviewPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template layout (topbar, image panel, score panel, hotkey hints)
 *  3. AI prediction card and adoption
 *  4. Score input and quick score buttons
 *  5. Image zoom/drag functionality
 *  6. Keyboard shortcuts
 *  7. API calls (getNext, submitScore, loadImage, loadQuestionInfo)
 *  8. State management (done, loading, submitting)
 *  9. Error handling
 * 10. Cleanup on unmount
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ReviewPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ReviewPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ReviewPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ReviewPage template layout', () => {
  it('contains review container root', () => {
    expect(content).toContain('class="review-container"')
  })

  it('contains topbar with back button', () => {
    expect(content).toContain('class="review-topbar"')
    expect(content).toContain('返回上一级')
  })

  it('shows question name and max score in topbar', () => {
    expect(content).toContain('class="topbar-question"')
    expect(content).toContain('class="topbar-info"')
    expect(content).toContain('{{ questionName }}')
    expect(content).toContain('满分 {{ maxScore }}')
  })

  it('shows position counter', () => {
    expect(content).toContain('{{ position.current }} / {{ position.total }}')
  })

  it('places page navigation below the answer image, not in the topbar', () => {
    const topbarBlock = content.slice(
      content.indexOf('class="review-topbar"'),
      content.indexOf('<n-spin')
    )
    const imageBlock = content.slice(
      content.indexOf('class="image-panel"'),
      content.indexOf('<div v-if="ai" class="ai-result-card">')
    )
    expect(topbarBlock).not.toContain('goPrev')
    expect(topbarBlock).not.toContain('goNext')
    expect(imageBlock).toContain('class="review-pager"')
    expect(imageBlock).toContain('@click="goPrev"')
    expect(imageBlock).toContain('@click="goNext"')
  })

  it('contains review-done state', () => {
    expect(content).toContain('class="review-done"')
    expect(content).toContain('全部批改完成')
    expect(content).toContain('该题所有答卷已确认')
  })

  it('contains image panel and score panel', () => {
    expect(content).toContain('class="image-panel"')
    expect(content).toContain('class="score-panel"')
  })

  it('contains floating review overlay with image and score panels', () => {
    expect(content).toContain('class="floating-review-mask"')
    expect(content).toContain('class="floating-image-stage"')
    expect(content).toContain('class="floating-score-panel"')
  })

  it('contains hotkey hint section', () => {
    expect(content).toContain('class="hotkey-hint"')
    expect(content).toContain('<kbd>0</kbd>')
    expect(content).toContain('<kbd>Enter</kbd>')
    expect(content).toContain('<kbd>Esc</kbd>')
  })
})

describe('ReviewPage AI result card', () => {
  it('conditionally shows AI card when ai data exists', () => {
    expect(content).toContain('v-if="ai"')
    expect(content).toContain('class="ai-result-card"')
  })

  it('shows AI title and confidence tag', () => {
    expect(content).toContain('class="ai-title"')
    expect(content).toContain('AI 阅卷结果')
    expect(content).toContain("ai.confidence >= 0.8 ? 'success' : 'warning'")
  })

  it('shows AI score with max score', () => {
    expect(content).toContain('class="ai-score-num"')
    expect(content).toContain('class="ai-score-max"')
    expect(content).toContain('{{ ai.score }}')
  })

  it('shows AI feedback when available', () => {
    expect(content).toContain('class="ai-feedback"')
    expect(content).toContain('v-if="ai.feedback"')
  })

  it('has score title in score panel', () => {
    expect(content).toContain('class="score-title"')
    expect(content).toContain('评分')
  })

  it('changes submit button text based on graded and AI presence', () => {
    expect(content).toContain("isGraded ? '修改评分 (Enter)' : ai ? '确认并下一份 (Enter)' : '提交并下一份 (Enter)'")
  })
})

describe('ReviewPage score input', () => {
  it('contains score input number component', () => {
    expect(content).toContain('v-model:value="currentScore"')
    expect(content).toContain(':min="0"')
    expect(content).toContain(':max="maxScore"')
    expect(content).toContain(':step="scoreStep"')
  })

  it('has quick score buttons generated from maxScore', () => {
    expect(content).toContain('class="score-buttons"')
    expect(content).toContain('v-for="s in scoreButtons"')
    expect(content).toContain("{ active: currentScore === s }")
  })

  it('computes scoreButtons from 0 to maxScore with composition step support', () => {
    expect(content).toContain('const max = Math.floor(maxScore.value)')
    expect(content).toContain('const step = isCompositionQuestion.value ? 2 : 1')
    expect(content).toContain('for (let i = 0; i <= max; i += step) buttons.push(i)')
  })

  it('uses 2 point scoring step for composition questions', () => {
    expect(content).toContain('const isCompositionQuestion = computed')
    expect(content).toContain('maxScore.value >= 40')
    expect(content).toContain('const scoreStep = computed(() => isCompositionQuestion.value ? 2 : 0.5)')
  })

  it('has comment collapse section', () => {
    expect(content).toContain('class="comment-section"')
    expect(content).toContain('添加批注')
    expect(content).toContain('v-model:value="comment"')
  })

  it('submit button disabled when no score', () => {
    expect(content).toContain(':disabled="currentScore === null"')
  })
})

describe('ReviewPage image zoom and drag', () => {
  it('imports useImageZoom composable', () => {
    expect(content).toContain("import { useImageZoom } from './review/useImageZoom'")
    expect(content).toContain('useImageZoom()')
  })

  it('uses imageTransform and wheel handlers from composable', () => {
    expect(content).toContain('@wheel.prevent="handleWheel"')
    expect(content).toContain('imageTransform')
  })

  it('opens floating review from image click without changing submit flow', () => {
    expect(content).toContain('@click.stop="openFloatingReview()"')
    expect(content).toContain('@click.stop="openFloatingReview(true)"')
    expect(content).toContain('const floatingReviewOpen = ref(false)')
    expect(content).toContain('ref="floatingScoreInputRef"')
  })

  it('uses floating wheel and drag handlers in template', () => {
    expect(content).toContain('@wheel="handleFloatingWheel"')
    expect(content).toContain('overflow: hidden;')
    expect(content).toContain('max-height: 100%;')
  })

  it('binds drag and zoom to template', () => {
    expect(content).toContain('@mousedown="startDrag"')
    expect(content).toContain('@dblclick.stop="resetZoom"')
  })
})

describe('ReviewPage keyboard shortcuts', () => {
  it('defines handleKeydown function', () => {
    expect(content).toContain('function handleKeydown(e)')
  })

  it('skips shortcuts when in textarea', () => {
    expect(content).toContain("if (e.target.tagName === 'TEXTAREA') return")
  })

  it('Escape key closes floating mode before navigating back', () => {
    expect(content).toContain("if (e.key === 'Escape')")
    expect(content).toContain('if (floatingReviewOpen.value)')
    expect(content).toContain('closeFloatingReview()')
    expect(content).toContain('router.back()')
  })

  it('Enter key triggers submit', () => {
    expect(content).toContain("if (e.key === 'Enter'")
    expect(content).toContain('handleSubmit()')
  })

  it('Arrow keys navigate prev/next', () => {
    expect(content).toContain("e.key === 'ArrowLeft'")
    expect(content).toContain("e.key === 'ArrowRight'")
    expect(content).toContain('goPrev()')
    expect(content).toContain('goNext()')
  })

  it('number keys set score directly', () => {
    expect(content).toContain("e.key >= '0' && e.key <= '9'")
    expect(content).toContain('currentScore.value = num')
  })
})

describe('ReviewPage API calls', () => {
  it('imports getNext and submitScore from marking API', () => {
    expect(content).toContain("import { getNext, submitScore, getAnswerAt } from '../api/marking'")
  })

  it('loads next answer via getNext', () => {
    expect(content).toContain('const { data } = await getNext(questionId, reviewMode.value)')
  })

  it('submits score with answer_id, score, and optional comment', () => {
    const submitBlock = content.slice(
      content.indexOf('async function handleSubmit'),
      content.indexOf('function handleWheel')
    )
    expect(submitBlock).toContain('submitScore({')
    expect(submitBlock).toContain('answer_id: currentAnswerId.value')
    expect(submitBlock).toContain('score: currentScore.value')
    expect(submitBlock).toContain('comment: comment.value || undefined')
  })

  it('loads answer image via blob response', () => {
    expect(content).toContain("client.get(`/marking/answer/${answerId}/image`, { responseType: 'blob' })")
    expect(content).toContain('URL.createObjectURL(resp.data)')
  })

  it('loads question info for name display', () => {
    expect(content).toContain("client.get(`/questions/${questionId}`)")
    expect(content).toContain('questionName.value = data.name')
  })
})

describe('ReviewPage data flow', () => {
  it('applyAnswer sets all state from answer payload', () => {
    const fnBlock = content.slice(
      content.indexOf('function applyAnswer('),
      content.indexOf('async function loadNext')
    )
    expect(fnBlock).toContain('currentAnswerId.value = answerPayload.answer_id')
    expect(fnBlock).toContain('position.value = answerPayload.position')
    expect(fnBlock).toContain('ai.value = answerPayload.ai || null')
  })

  it('pre-fills score from AI prediction via applyScoring', () => {
    expect(content).toContain('applyScoring(answerPayload, ai.value)')
  })

  it('handles done state when no more answers', () => {
    expect(content).toContain('if (data.done)')
    expect(content).toContain('done.value = true')
  })

  it('handles inline next answer after submit', () => {
    expect(content).toContain('data.next?.done')
    expect(content).toContain('data.next?.answer')
  })
})

describe('ReviewPage error handling', () => {
  it('wraps loadNext in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadNext'),
      content.indexOf('async function handleSubmit')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("message.error('加载失败')")
  })

  it('wraps handleSubmit in try-catch with detailed error', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleSubmit'),
      content.indexOf('async function loadAnswerAt')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("e.response?.data?.detail || '提交失败'")
  })

  it('wraps loadImage in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadImage'),
      content.indexOf('function applyAnswer')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("message.error('图片加载失败')")
  })
})

describe('ReviewPage cleanup on unmount', () => {
  it('removes keydown listener', () => {
    expect(content).toContain("window.removeEventListener('keydown', handleKeydown)")
  })

  it('calls cleanupZoom on unmount', () => {
    expect(content).toContain('cleanupZoom()')
  })

  it('revokes object URL on unmount', () => {
    const unmountBlock = content.slice(
      content.indexOf('onUnmounted('),
      content.indexOf('</script>')
    )
    expect(unmountBlock).toContain('URL.revokeObjectURL(imageUrl.value)')
  })
})
