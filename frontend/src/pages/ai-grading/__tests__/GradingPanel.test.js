/**
 * GradingPanel.vue source-text smoke tests.
 *
 * Covers:
 *   1. Smoke import
 *   2. Template structure (question content, answer, rubric, grading ops)
 *   3. Props definition (8 props)
 *   4. Emits definition (6 emits)
 *   5. RubricEditor component usage
 *   6. Task progress display
 *   7. Empty state
 *   8. Computed taskProgressPct
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const vuePath = resolve(__dirname, '../GradingPanel.vue')
const src = readFileSync(vuePath, 'utf-8')

describe('GradingPanel smoke', () => {
  it('can be imported without errors', async () => {
    const mod = await import('../GradingPanel.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('GradingPanel template - empty state', () => {
  it('shows empty message when no question', () => {
    expect(src).toContain('请从左侧选择一道题')
    expect(src).toContain('v-if="!question"')
  })
})

describe('GradingPanel template - question content card', () => {
  it('has question content card with title', () => {
    expect(src).toContain('title="原题"')
  })

  it('has edit content button', () => {
    expect(src).toContain("$emit('edit-content', 'content')")
    expect(src).toContain('编辑')
  })

  it('displays question content text', () => {
    expect(src).toContain('question.content')
    expect(src).toContain('content-text')
  })

  it('shows empty tip when no content', () => {
    expect(src).toContain('暂无题干')
  })

  it('displays content images with sequence numbers', () => {
    expect(src).toContain('question.content_images')
    expect(src).toContain('content-img')
    expect(src).toContain('img-seq')
  })

  it('has image delete button', () => {
    expect(src).toContain('img-delete')
    expect(src).toContain("$emit('remove-image', 'content', i)")
  })
})

describe('GradingPanel template - reference answer card', () => {
  it('has reference answer card with title', () => {
    expect(src).toContain('title="参考答案"')
  })

  it('has edit answer button', () => {
    expect(src).toContain("$emit('edit-content', 'answer')")
  })

  it('displays reference answer text', () => {
    expect(src).toContain('question.reference_answer')
  })

  it('shows empty tip when no answer', () => {
    expect(src).toContain('暂无参考答案')
  })

  it('displays answer images', () => {
    expect(src).toContain('question.reference_answer_images')
    expect(src).toContain("$emit('remove-image', 'answer', i)")
  })
})

describe('GradingPanel template - rubric card', () => {
  it('has rubric card with title', () => {
    expect(src).toContain('title="评分细则"')
  })

  it('has AI generate button', () => {
    expect(src).toContain('AI 生成')
    expect(src).toContain(':loading="rubricGenerating"')
    expect(src).toContain("$emit('generate-rubric')")
  })

  it('has save rubric button', () => {
    expect(src).toContain(':loading="rubricSaving"')
    expect(src).toContain("$emit('save-rubric')")
  })

  it('uses RubricEditor component', () => {
    expect(src).toContain('<RubricEditor')
    expect(src).toContain(':modelValue="rubricItems"')
    expect(src).toContain("$emit('update:rubricItems', $event)")
    expect(src).toContain(':max-score="question.max_score || 0"')
    expect(src).toContain(':loading="rubricLoading"')
  })
})

describe('GradingPanel template - grading operations card', () => {
  it('has grading operations card', () => {
    expect(src).toContain('title="阅卷操作"')
  })

  it('shows task progress when available', () => {
    expect(src).toContain('taskProgress !== null')
    expect(src).toContain('progress-area')
    expect(src).toContain('taskProgress.graded')
    expect(src).toContain('taskProgress.total')
  })

  it('has progress bar', () => {
    expect(src).toContain('n-progress')
    expect(src).toContain(':percentage="taskProgressPct"')
  })

  it('shows completed status', () => {
    expect(src).toContain("taskProgress.status === 'completed'")
    expect(src).toContain('阅卷完成')
    expect(src).toContain('done-text')
  })

  it('shows failed status', () => {
    expect(src).toContain("taskProgress.status === 'failed'")
    expect(src).toContain('阅卷失败')
    expect(src).toContain('fail-text')
  })

  it('has start grading button', () => {
    expect(src).toContain('开始阅卷')
    expect(src).toContain(':loading="gradingStarting"')
    expect(src).toContain("$emit('start-grading', limitValue, modeValue, useVision)")
    expect(src).toContain("taskProgress?.status === 'processing'")
  })
})

describe('GradingPanel imports', () => {
  it('imports NCard, NButton, NSpace, NProgress from naive-ui', () => {
    expect(src).toContain('import { NCard, NButton, NSpace, NProgress, NImage, NInputNumber, NRadioGroup, NRadioButton, NCheckbox }')
  })

  it('imports RubricEditor component', () => {
    expect(src).toContain("import RubricEditor from '../../components/RubricEditor.vue'")
  })
})

describe('GradingPanel props', () => {
  it('defines question prop as optional Object', () => {
    expect(src).toContain('question: { type: Object, default: null }')
  })

  it('defines rubricItems as Array', () => {
    expect(src).toContain('rubricItems: { type: Array, default: () => [] }')
  })

  it('defines rubricLoading as Boolean', () => {
    expect(src).toContain('rubricLoading: { type: Boolean, default: false }')
  })

  it('defines rubricGenerating as Boolean', () => {
    expect(src).toContain('rubricGenerating: { type: Boolean, default: false }')
  })

  it('defines rubricSaving as Boolean', () => {
    expect(src).toContain('rubricSaving: { type: Boolean, default: false }')
  })

  it('defines taskProgress as optional Object', () => {
    expect(src).toContain('taskProgress: { type: Object, default: null }')
  })

  it('defines gradingStarting as Boolean', () => {
    expect(src).toContain('gradingStarting: { type: Boolean, default: false }')
  })
})

describe('GradingPanel emits', () => {
  it('declares all 6 emits', () => {
    expect(src).toContain("'edit-content'")
    expect(src).toContain("'remove-image'")
    expect(src).toContain("'generate-rubric'")
    expect(src).toContain("'save-rubric'")
    expect(src).toContain("'update:rubricItems'")
    expect(src).toContain("'start-grading'")
  })
})

describe('GradingPanel taskProgressPct computed', () => {
  it('computes percentage from graded/total', () => {
    expect(src).toContain('const taskProgressPct = computed(')
    expect(src).toContain('props.taskProgress.graded / props.taskProgress.total')
    expect(src).toContain('Math.round')
    expect(src).toContain('* 100')
  })

  it('returns 0 when no progress data', () => {
    expect(src).toContain('!props.taskProgress || !props.taskProgress.total')
    expect(src).toContain('return 0')
  })
})
