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

  it('contains review-done state', () => {
    expect(content).toContain('class="review-done"')
    expect(content).toContain('全部批改完成')
    expect(content).toContain('该题所有答卷已确认')
  })

  it('contains image panel and score panel', () => {
    expect(content).toContain('class="image-panel"')
    expect(content).toContain('class="score-panel"')
  })

  it('contains hotkey hint section', () => {
    expect(content).toContain('class="hotkey-hint"')
    expect(content).toContain('<kbd>0</kbd>')
    expect(content).toContain('<kbd>Enter</kbd>')
    expect(content).toContain('<kbd>Esc</kbd>')
  })
})

describe('ReviewPage AI prediction card', () => {
  it('conditionally shows AI card when ai data exists', () => {
    expect(content).toContain('v-if="ai"')
    expect(content).toContain('class="ai-result-card"')
  })

  it('shows AI title and confidence tag', () => {
    expect(content).toContain('class="ai-title"')
    expect(content).toContain('AI 预测')
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

  it('has adopt AI score button', () => {
    expect(content).toContain('@click="currentScore = ai.score"')
    expect(content).toContain('采纳 AI 分数 (A)')
  })

  it('changes title based on AI presence', () => {
    expect(content).toContain("{{ ai ? '校对' : '评分' }}")
  })

  it('changes submit button text based on AI presence', () => {
    expect(content).toContain("ai ? '确认并下一份 (Enter)' : '提交并下一份 (Enter)'")
  })
})

describe('ReviewPage score input', () => {
  it('contains score input number component', () => {
    expect(content).toContain('v-model:value="currentScore"')
    expect(content).toContain(':min="0"')
    expect(content).toContain(':max="maxScore"')
    expect(content).toContain(':step="0.5"')
  })

  it('has quick score buttons generated from maxScore', () => {
    expect(content).toContain('class="score-buttons"')
    expect(content).toContain('v-for="s in scoreButtons"')
    expect(content).toContain("{ active: currentScore === s }")
  })

  it('computes scoreButtons from 0 to maxScore', () => {
    expect(content).toContain('const max = Math.floor(maxScore.value)')
    expect(content).toContain('for (let i = 0; i <= max; i++) buttons.push(i)')
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
  it('computes image transform style', () => {
    expect(content).toContain('const imageTransform = computed')
    expect(content).toContain('translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value})')
  })

  it('handles wheel event for zoom', () => {
    expect(content).toContain('@wheel.prevent="handleWheel"')
    expect(content).toContain('function handleWheel(e)')
    expect(content).toContain('Math.max(0.3, Math.min(5, scale.value + delta))')
  })

  it('supports mouse drag for panning', () => {
    expect(content).toContain('@mousedown="startDrag"')
    expect(content).toContain('function startDrag(e)')
    expect(content).toContain('function onDrag(e)')
    expect(content).toContain('function stopDrag()')
  })

  it('double-click resets zoom', () => {
    expect(content).toContain('@dblclick="resetZoom"')
    expect(content).toContain('function resetZoom()')
  })

  it('resetZoom restores defaults', () => {
    const fnBlock = content.slice(
      content.indexOf('function resetZoom()'),
      content.indexOf('function startDrag')
    )
    expect(fnBlock).toContain('scale.value = 1')
    expect(fnBlock).toContain('translateX.value = 0')
    expect(fnBlock).toContain('translateY.value = 0')
  })
})

describe('ReviewPage keyboard shortcuts', () => {
  it('defines handleKeydown function', () => {
    expect(content).toContain('function handleKeydown(e)')
  })

  it('skips shortcuts when in textarea', () => {
    expect(content).toContain("if (e.target.tagName === 'TEXTAREA') return")
  })

  it('Escape key navigates back', () => {
    expect(content).toContain("if (e.key === 'Escape')")
    expect(content).toContain('router.back()')
  })

  it('Enter key triggers submit', () => {
    expect(content).toContain("if (e.key === 'Enter'")
    expect(content).toContain('handleSubmit()')
  })

  it('A key adopts AI score', () => {
    expect(content).toContain("(e.key === 'a' || e.key === 'A')")
    expect(content).toContain('currentScore.value = ai.value.score')
  })

  it('number keys set score directly', () => {
    expect(content).toContain("e.key >= '0' && e.key <= '9'")
    expect(content).toContain('currentScore.value = num')
  })
})

describe('ReviewPage API calls', () => {
  it('imports getNext and submitScore from marking API', () => {
    expect(content).toContain("import { getNext, submitScore, flagAnswer, getAnswerAt } from '../api/marking'")
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

  it('pre-fills score from AI prediction', () => {
    expect(content).toContain('currentScore.value = ai.value ? ai.value.score : null')
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
      content.indexOf('function handleWheel')
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

  it('removes mousemove and mouseup listeners', () => {
    expect(content).toContain("window.removeEventListener('mousemove', onDrag)")
    expect(content).toContain("window.removeEventListener('mouseup', stopDrag)")
  })

  it('revokes object URL on unmount', () => {
    const unmountBlock = content.slice(
      content.indexOf('onUnmounted('),
      content.indexOf('</script>')
    )
    expect(unmountBlock).toContain('URL.revokeObjectURL(imageUrl.value)')
  })
})
