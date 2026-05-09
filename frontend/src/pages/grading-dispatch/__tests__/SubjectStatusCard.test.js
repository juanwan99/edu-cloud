/**
 * SubjectStatusCard.vue source-text smoke tests.
 *
 * Covers:
 *   1. Smoke import
 *   2. Template structure (card layout, stages, progress bars, actions)
 *   3. Props definition (8 props)
 *   4. Emits definition (8 emits)
 *   5. Stage labels and classes
 *   6. Detect status display
 *   7. Stats display
 *   8. All stage-specific template sections
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const vuePath = resolve(__dirname, '../SubjectStatusCard.vue')
const src = readFileSync(vuePath, 'utf-8')

describe('SubjectStatusCard smoke', () => {
  it('can be imported without errors', async () => {
    const mod = await import('../SubjectStatusCard.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('SubjectStatusCard template - card layout', () => {
  it('has subject-card with grid layout', () => {
    expect(src).toContain('class="subject-card"')
    expect(src).toContain('grid-template-columns')
  })

  it('highlights selected card', () => {
    expect(src).toContain('{ selected: isSelected }')
  })

  it('has checkbox for selection', () => {
    expect(src).toContain('n-checkbox')
    expect(src).toContain(':checked="isSelected"')
    expect(src).toContain("$emit('toggle', subject.subject_id, v)")
  })

  it('shows subject name', () => {
    expect(src).toContain('card-name')
    expect(src).toContain('subject.subject_name')
  })

  it('shows stage tag', () => {
    expect(src).toContain('stage-tag')
    expect(src).toContain('stageClass(subject.stage)')
    expect(src).toContain('stageLabel(subject.stage)')
  })
})

describe('SubjectStatusCard template - detect status', () => {
  it('shows running detect status', () => {
    expect(src).toContain("detectStatus === 'running'")
    expect(src).toContain('检测中')
    expect(src).toContain('detect-tag running')
  })

  it('shows done detect status', () => {
    expect(src).toContain("detectStatus === 'done'")
    expect(src).toContain('检测完成')
    expect(src).toContain('detect-tag done')
  })

  it('shows failed detect status', () => {
    expect(src).toContain("detectStatus === 'failed'")
    expect(src).toContain('检测失败')
    expect(src).toContain('detect-tag failed')
  })
})

describe('SubjectStatusCard template - stage content', () => {
  it('shows cutting progress bar', () => {
    expect(src).toContain("subject.stage === 'cutting'")
    expect(src).toContain('prog-row')
    expect(src).toContain('prog-bar')
    expect(src).toContain('prog-fill')
    expect(src).toContain("progressPct + '%'")
  })

  it('shows idle state', () => {
    expect(src).toContain("subject.stage === 'idle'")
    expect(src).toContain('等待上传扫描图')
  })

  it('shows pending_detect state', () => {
    expect(src).toContain("subject.stage === 'pending_detect'")
    expect(src).toContain('已上传')
    expect(src).toContain('subject.scan_images')
    expect(src).toContain('等待模板检测')
  })

  it('shows pending_cut state', () => {
    expect(src).toContain("subject.stage === 'pending_cut'")
    expect(src).toContain('模板就绪')
    expect(src).toContain('待切割')
  })

  it('shows cut-complete state when answer_count > 0', () => {
    expect(src).toContain('subject.answer_count > 0')
    expect(src).toContain('已切割')
    expect(src).toContain('subject.answer_count')
  })
})

describe('SubjectStatusCard template - stats', () => {
  it('shows scan images count', () => {
    expect(src).toContain('subject.scan_images')
    expect(src).toContain('份')
  })

  it('shows answer count', () => {
    expect(src).toContain('subject.answer_count')
    expect(src).toContain('切')
  })
})

describe('SubjectStatusCard template - action buttons', () => {
  it('has detect button', () => {
    expect(src).toContain('v-if="showDetect"')
    expect(src).toContain('模板检测')
    expect(src).toContain("$emit('detect', subject)")
  })

  it('has preview button', () => {
    expect(src).toContain('v-if="showCut"')
    expect(src).toContain('预览模板')
    expect(src).toContain("$emit('preview', subject)")
  })

  it('has cut button', () => {
    expect(src).toContain('切割')
    expect(src).toContain("$emit('cut', subject)")
  })

  it('has stop button during cutting', () => {
    expect(src).toContain("subject.stage === 'cutting'")
    expect(src).toContain('停止')
    expect(src).toContain("$emit('stop-cut')")
  })

  it('has verify button', () => {
    expect(src).toContain('校对配置')
    expect(src).toContain("$emit('verify', subject)")
  })
})

describe('SubjectStatusCard imports', () => {
  it('imports NButton and NCheckbox from naive-ui', () => {
    expect(src).toContain("import { NButton, NCheckbox } from 'naive-ui'")
  })
})

describe('SubjectStatusCard props', () => {
  it('defines subject as required Object', () => {
    expect(src).toContain('subject: { type: Object, required: true }')
  })

  it('defines isSelected as Boolean', () => {
    expect(src).toContain('isSelected: { type: Boolean, default: false }')
  })

  it('defines progressPct as Number', () => {
    expect(src).toContain('progressPct: { type: Number, default: 0 }')
  })

  it('defines detectStatus as String', () => {
    expect(src).toContain('detectStatus: { type: String, default: null }')
  })

  it('defines showDetect as Boolean', () => {
    expect(src).toContain('showDetect: { type: Boolean, default: false }')
  })

  it('defines showCut as Boolean', () => {
    expect(src).toContain('showCut: { type: Boolean, default: false }')
  })

  it('defines isDetectLoading as Boolean', () => {
    expect(src).toContain('isDetectLoading: { type: Boolean, default: false }')
  })

  it('defines isCutLoading as Boolean', () => {
    expect(src).toContain('isCutLoading: { type: Boolean, default: false }')
  })
})

describe('SubjectStatusCard emits', () => {
  it('declares all 6 emits', () => {
    expect(src).toContain("'toggle'")
    expect(src).toContain("'detect'")
    expect(src).toContain("'preview'")
    expect(src).toContain("'cut'")
    expect(src).toContain("'stop-cut'")
    expect(src).toContain("'verify'")
  })
})

describe('SubjectStatusCard stage labels', () => {
  it('has STAGE_LABELS mapping for all stages', () => {
    expect(src).toContain('const STAGE_LABELS = {')
    expect(src).toContain("idle: '待上传'")
    expect(src).toContain("pending_detect: '待检测'")
    expect(src).toContain("pending_cut: '待切割'")
    expect(src).toContain("cutting: '切割中'")
    expect(src).toContain("ready: '已切割'")
    expect(src).toContain("done: '已切割'")
    expect(src).toContain("ai_grading: 'AI阅卷中'")
    expect(src).toContain("reviewing: '待复核'")
    expect(src).toContain("failed: '已切割'")
  })

  it('has stageLabel function with fallback', () => {
    expect(src).toContain('function stageLabel(stage)')
    expect(src).toContain('STAGE_LABELS[stage] || stage')
  })

  it('has stageClass function with ai_grading and reviewing specific classes', () => {
    expect(src).toContain('function stageClass(stage)')
    expect(src).toContain("stage === 'ai_grading'")
    expect(src).toContain("'tag-ai-grading'")
    expect(src).toContain("stage === 'reviewing'")
    expect(src).toContain("'tag-reviewing'")
    expect(src).toContain('`tag-${stage}`')
  })

  it('has progress bar for grading progress', () => {
    expect(src).toContain('prog-bar')
    expect(src).toContain('prog-fill')
    expect(src).toContain('progressPct')
  })
})

describe('SubjectStatusCard CSS stage classes', () => {
  it('has CSS classes for base stages', () => {
    expect(src).toContain('.tag-idle')
    expect(src).toContain('.tag-pending_detect')
    expect(src).toContain('.tag-pending_cut')
    expect(src).toContain('.tag-cutting')
    expect(src).toContain('.tag-ready')
  })
})
