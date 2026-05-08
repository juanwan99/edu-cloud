/**
 * VisualEditorTab.vue source-text smoke tests.
 *
 * Covers:
 *   1. Smoke import
 *   2. Template structure (toolbar buttons, CardEditor, empty state)
 *   3. Props and emits
 *   4. CardEditor component usage
 *   5. Auto layout, reset, publish, batch export functions
 *   6. Error handling
 *   7. Expose definition
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const vuePath = resolve(__dirname, '../VisualEditorTab.vue')
const src = readFileSync(vuePath, 'utf-8')

describe('VisualEditorTab smoke', () => {
  it('can be imported without errors', async () => {
    const mod = await import('../VisualEditorTab.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('VisualEditorTab template - toolbar buttons', () => {
  it('has subject select with computed v-model', () => {
    expect(src).toContain('v-model:value="localSubjectId"')
    expect(src).toContain(':options="subjectOptions"')
  })

  it('has save button', () => {
    expect(src).toContain("cardEditorRef?.save()")
    expect(src).toContain('保存')
  })

  it('has reset layout button', () => {
    expect(src).toContain('handleResetLayout')
    expect(src).toContain('恢复默认')
  })

  it('has auto layout button', () => {
    expect(src).toContain('handleAutoLayout')
    expect(src).toContain(':loading="autoLayouting"')
    expect(src).toContain('小微排版')
  })

  it('has export PDF button', () => {
    expect(src).toContain("cardEditorRef?.exportPdf()")
    expect(src).toContain('导出 PDF')
  })

  it('has batch export PDF button', () => {
    expect(src).toContain('handleBatchExportPdf')
    expect(src).toContain(':loading="batchExporting"')
    expect(src).toContain('导出全部 PDF')
  })

  it('has publish card button with data-testid', () => {
    expect(src).toContain('data-testid="publish-card-btn"')
    expect(src).toContain('handlePublishCard')
    expect(src).toContain('发布答题卡')
  })

  it('disables buttons when no subject or not draft', () => {
    expect(src).toContain("!localSubjectId || exam?.status !== 'draft'")
  })
})

describe('VisualEditorTab template - CardEditor', () => {
  it('renders CardEditor when subject is selected', () => {
    expect(src).toContain('<CardEditor')
    expect(src).toContain('ref="cardEditorRef"')
    expect(src).toContain(':exam-id="examId"')
    expect(src).toContain(':subject-id="localSubjectId"')
    expect(src).toContain(':subject-name="localSubjectName"')
    expect(src).toContain(':card-title="exam?.card_title || \'\'"')
    expect(src).toContain(':readonly="exam?.status !== \'draft\'"')
    expect(src).toContain(':pending-questions="pendingQuestions"')
  })

  it('has empty state when no subject', () => {
    expect(src).toContain('n-empty')
    expect(src).toContain('请先选择科目')
  })
})

describe('VisualEditorTab imports', () => {
  it('imports CardEditor component', () => {
    expect(src).toContain("import CardEditor from '../../components/CardEditor.vue'")
  })

  it('imports Axios client', () => {
    expect(src).toContain("import client from '../../api/client'")
  })

  it('uses useMessage and useDialog', () => {
    expect(src).toContain('useMessage')
    expect(src).toContain('useDialog')
  })
})

describe('VisualEditorTab props', () => {
  it('defines examId as required String', () => {
    expect(src).toContain('examId: { type: String, required: true }')
  })

  it('defines exam as optional Object', () => {
    expect(src).toContain('exam: { type: Object, default: null }')
  })

  it('defines subjects as required Array', () => {
    expect(src).toContain('subjects: { type: Array, required: true }')
  })

  it('defines subjectOptions as required Array', () => {
    expect(src).toContain('subjectOptions: { type: Array, required: true }')
  })

  it('defines visualEditorSubjectId as optional String', () => {
    expect(src).toContain('visualEditorSubjectId')
  })

  it('defines pendingQuestions as optional Array', () => {
    expect(src).toContain('pendingQuestions: { type: [Array, null], default: null }')
  })
})

describe('VisualEditorTab emits', () => {
  it('emits update:visualEditorSubjectId and reload-exam', () => {
    expect(src).toContain("'update:visualEditorSubjectId'")
    expect(src).toContain("'reload-exam'")
  })
})

describe('VisualEditorTab computed properties', () => {
  it('has localSubjectId computed with get/set', () => {
    expect(src).toContain('const localSubjectId = computed({')
    expect(src).toContain('get: () => props.visualEditorSubjectId')
    expect(src).toContain("emit('update:visualEditorSubjectId', v)")
  })

  it('has localSubjectName computed', () => {
    expect(src).toContain('const localSubjectName = computed(')
    expect(src).toContain('props.subjects.find(s => s.id === localSubjectId.value)')
  })
})

describe('VisualEditorTab handleAutoLayout', () => {
  it('creates file input for .docx', () => {
    expect(src).toContain("input.type = 'file'")
    expect(src).toContain("input.accept = '.docx'")
  })

  it('uploads file via Axios client to upload-answer endpoint', () => {
    expect(src).toContain("'/card/upload-answer'")
    expect(src).toContain("client.post")
  })

  it('calls auto-layout endpoint with subject ID', () => {
    expect(src).toContain('`/card/auto-layout/${localSubjectId.value}`')
  })

  it('applies layout result via cardEditorRef', () => {
    expect(src).toContain('cardEditorRef.value.applyAutoLayout(result)')
  })

  it('shows success message with question count', () => {
    expect(src).toContain('小微已为')
    expect(src).toContain('道题完成排版')
  })

  it('shows error on failure', () => {
    expect(src).toContain("'小微排版失败: ' + e.message")
  })
})

describe('VisualEditorTab handleResetLayout', () => {
  it('shows confirmation dialog', () => {
    expect(src).toContain('恢复默认模板')
    expect(src).toContain('当前编辑内容将丢失，确定恢复为系统默认模板？')
  })

  it('calls resetToDefault on confirmation', () => {
    expect(src).toContain('cardEditorRef.value.resetToDefault()')
    expect(src).toContain('已恢复默认模板')
  })
})

describe('VisualEditorTab handlePublishCard', () => {
  it('warns if no subject selected', () => {
    expect(src).toContain('请先选择科目')
  })

  it('shows publish confirmation dialog', () => {
    expect(src).toContain('确认发布')
    expect(src).toContain('发布后答题卡将锁定为只读，扫描端可开始拉取模板')
  })

  it('dynamically imports export module', () => {
    expect(src).toContain("import('@/card-editor/export.js')")
    expect(src).toContain('exportModule.publishCard')
  })

  it('emits reload-exam on success', () => {
    expect(src).toContain("emit('reload-exam')")
    expect(src).toContain('答题卡已发布，扫描端可拉取模板')
  })

  it('shows error on failure', () => {
    expect(src).toContain("'发布失败: '")
  })
})

describe('VisualEditorTab handleBatchExportPdf', () => {
  it('warns when no subjects', () => {
    expect(src).toContain('无科目可导出')
  })

  it('dynamically imports batchExportPdf', () => {
    expect(src).toContain("import('@/card-editor/export.js')")
    expect(src).toContain('batchExportPdf')
  })

  it('tracks progress during export', () => {
    expect(src).toContain('batchExportProgress')
    expect(src).toContain('准备中...')
  })

  it('reports success and failure counts', () => {
    expect(src).toContain('科导出成功')
    expect(src).toContain('科失败')
  })

  it('shows error on complete failure', () => {
    expect(src).toContain("'批量导出失败: ' + e.message")
  })
})

describe('VisualEditorTab saveBlob', () => {
  it('creates download link from blob', () => {
    expect(src).toContain('function saveBlob(blob, filename)')
    expect(src).toContain("document.createElement('a')")
    expect(src).toContain('a.download = filename')
  })
})

describe('VisualEditorTab defineExpose', () => {
  it('exposes handlePublishCard and cardEditorRef', () => {
    expect(src).toContain('defineExpose({')
    expect(src).toContain('handlePublishCard')
    expect(src).toContain('cardEditorRef')
  })
})
