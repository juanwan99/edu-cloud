/**
 * GradingPanel.vue source-text smoke tests.
 *
 * Covers:
 *   1. Smoke import
 *   2. Template structure (question content, answer, rubric, grading ops)
 *   3. Props definition (5 props)
 *   4. Emits definition (5 emits)
 *   5. RubricEditor component usage
 *   6. Essay anchor rubric controls
 *   7. Empty state
 *   8. Computed essay anchor helpers
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

describe('GradingPanel template - essay anchor controls', () => {
  it('has essay anchor section', () => {
    expect(src).toContain('v-if="isEssay"')
    expect(src).toContain('class="anchor-section"')
    expect(src).toContain('评分锚定范文（作文校准用，可选）')
  })

  it('shows anchor tiers and ranges', () => {
    expect(src).toContain('高分档')
    expect(src).toContain('中分档')
    expect(src).toContain('低分档')
    expect(src).toContain('一/二类文 40-50分')
  })

  it('has anchor score input', () => {
    expect(src).toContain('class="anchor-score-label"')
    expect(src).toContain(':max="question.max_score || 50"')
    expect(src).toContain("@update:value=\"v => updateAnchor(i, 'score', v)\"")
  })

  it('has anchor summary editor', () => {
    expect(src).toContain('作文原文')
    expect(src).toContain('summaryPlaceholder')
    expect(src).toContain("@update:value=\"v => updateAnchor(i, 'summary', v)\"")
  })

  it('has anchor reason editor', () => {
    expect(src).toContain('评分理由')
    expect(src).toContain('reasonPlaceholder')
    expect(src).toContain("@update:value=\"v => updateAnchor(i, 'reason', v)\"")
  })

  it('has computed essay detection', () => {
    expect(src).toContain('const isEssay = computed(() => {')
    expect(src).toContain('items.length === 1')
    expect(src).toContain('(items[0]?.score || 0) >= 40')
  })
})

describe('GradingPanel imports', () => {
  it('imports NCard, NButton, NSpace, NImage, NInputNumber from naive-ui', () => {
    expect(src).toContain('import { NCard, NButton, NSpace, NImage, NInputNumber }')
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

  it('defines props with defineProps', () => {
    expect(src).toContain('const props = defineProps({')
  })

  it('uses question max score for rubric editing', () => {
    expect(src).toContain(':max-score="question.max_score || 0"')
  })
})

describe('GradingPanel emits', () => {
  it('declares all 5 emits', () => {
    expect(src).toContain("'edit-content'")
    expect(src).toContain("'remove-image'")
    expect(src).toContain("'generate-rubric'")
    expect(src).toContain("'save-rubric'")
    expect(src).toContain("'update:rubricItems'")
  })
})

describe('GradingPanel computed helpers', () => {
  it('computes essay mode from rubric score', () => {
    expect(src).toContain('const isEssay = computed(() => {')
    expect(src).toContain('const items = props.rubricItems || []')
    expect(src).toContain('return items.length === 1 && (items[0]?.score || 0) >= 40')
  })

  it('builds anchor rows from saved essayAnchors', () => {
    expect(src).toContain('const anchors = computed(() => {')
    expect(src).toContain('const saved = (props.rubricItems?.[0]?.essayAnchors) || []')
    expect(src).toContain('return ANCHOR_TIERS.map((t, i) => ({')
    expect(src).toContain('score: saved[i]?.score ?? null')
  })
})
