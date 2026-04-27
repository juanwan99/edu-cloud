/**
 * CardMakerTab.vue source-text smoke tests.
 *
 * Covers:
 *   1. Smoke import
 *   2. Template structure (card config form, upload, preview, barcode)
 *   3. API imports (updateExam, generateBarcode, parseAnswers, etc.)
 *   4. Props and emits
 *   5. Reactive state and computed properties
 *   6. Error handling
 *   7. KaTeX math rendering
 *   8. Fullscreen toggle and ESC handler
 *   9. Answer columns definition
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const vuePath = resolve(__dirname, '../CardMakerTab.vue')
const src = readFileSync(vuePath, 'utf-8')

describe('CardMakerTab smoke', () => {
  it('can be imported without errors', async () => {
    const mod = await import('../CardMakerTab.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('CardMakerTab template - card config form', () => {
  it('has card title input', () => {
    expect(src).toContain('v-model:value="cardForm.cardTitle"')
    expect(src).toContain('答题卡标题')
  })

  it('has save card title button', () => {
    expect(src).toContain('handleSaveCardTitle')
    expect(src).toContain(':loading="cardTitleSaving"')
    expect(src).toContain('保存')
  })

  it('has subject select', () => {
    expect(src).toContain('v-model:value="cardForm.subjectId"')
    expect(src).toContain('onSubjectSelect')
  })

  it('has total score input', () => {
    expect(src).toContain('v-model:value="cardForm.totalScore"')
    expect(src).toContain(':min="10"')
    expect(src).toContain(':max="300"')
  })

  it('has paper size select', () => {
    expect(src).toContain('v-model:value="cardForm.paperSize"')
    expect(src).toContain('paperSizeOptions')
  })

  it('has sides select', () => {
    expect(src).toContain('v-model:value="cardForm.sides"')
    expect(src).toContain('sidesOptions')
  })
})

describe('CardMakerTab template - two entry paths', () => {
  it('has direct editor entry card', () => {
    expect(src).toContain('直接编辑答题卡')
    expect(src).toContain('goToEditor')
    expect(src).toContain('使用学科默认模板，手动调整题型结构')
  })

  it('has upload answer entry', () => {
    expect(src).toContain('上传答案自动识别')
    expect(src).toContain('handleAnswerUpload')
    expect(src).toContain('.docx,.pdf')
  })

  it('shows parsing spinner', () => {
    expect(src).toContain('正在解析答案并识别题型')
    expect(src).toContain(':disabled="cardLoading"')
  })
})

describe('CardMakerTab template - answer preview', () => {
  it('shows answer preview table', () => {
    expect(src).toContain('答案预览')
    expect(src).toContain('answerColumns')
    expect(src).toContain('parsedStandardized')
  })

  it('shows recognition count tag', () => {
    expect(src).toContain('已识别')
    expect(src).toContain('totalQuestions')
  })

  it('shows parse method tag', () => {
    expect(src).toContain('parse_method')
    expect(src).toContain('Vision AI')
    expect(src).toContain('文本解析')
  })

  it('shows score sum and mismatch warning', () => {
    expect(src).toContain('scoreSum')
    expect(src).toContain('分值不一致')
  })

  it('has reset and confirm buttons', () => {
    expect(src).toContain('重新上传')
    expect(src).toContain('resetToUpload')
    expect(src).toContain('确认答案')
    expect(src).toContain('confirmAnswers')
  })
})

describe('CardMakerTab template - barcode section', () => {
  it('has barcode sticker generation section', () => {
    expect(src).toContain('条码贴纸生成')
    expect(src).toContain('.xlsx,.xls')
    expect(src).toContain('上传学生名单 Excel')
  })

  it('has barcode generate button', () => {
    expect(src).toContain('下载条码贴纸 PDF')
    expect(src).toContain('handleBarcodeGenerate')
    expect(src).toContain(':loading="barcodeLoading"')
  })
})

describe('CardMakerTab template - PDF preview', () => {
  it('has preview iframe', () => {
    expect(src).toContain('previewIframe')
    expect(src).toContain(':src="cardPreviewUrl"')
  })

  it('has fullscreen toggle', () => {
    expect(src).toContain('toggleFullscreen')
    expect(src).toContain('退出全屏')
    expect(src).toContain('全屏查看')
  })

  it('has fullscreen overlay via teleport', () => {
    expect(src).toContain('<teleport to="body">')
    expect(src).toContain('isFullscreen')
    expect(src).toContain('关闭全屏 (ESC)')
  })
})

describe('CardMakerTab API imports', () => {
  it('imports updateExam from exams API', () => {
    expect(src).toContain("import { updateExam } from '../../api/exams'")
  })

  it('imports card API functions', () => {
    expect(src).toContain("import { generateBarcode, parseAnswers, previewByWeights, generateCardV2 } from '../../api/cards'")
  })

  it('imports katex for math rendering', () => {
    expect(src).toContain("import katex from 'katex'")
    expect(src).toContain("import 'katex/dist/katex.min.css'")
  })
})

describe('CardMakerTab props and emits', () => {
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

  it('declares emits for update, go-to-editor, confirm-answers', () => {
    expect(src).toContain("'update:exam'")
    expect(src).toContain("'go-to-editor'")
    expect(src).toContain("'confirm-answers'")
  })
})

describe('CardMakerTab reactive state', () => {
  it('has cardForm reactive with all fields', () => {
    expect(src).toContain('const cardForm = reactive({')
    expect(src).toContain('subjectId: null')
    expect(src).toContain("cardTitle: ''")
    expect(src).toContain('totalScore: 100')
    expect(src).toContain("paperSize: 'A3'")
    expect(src).toContain("sides: 'duplex'")
  })

  it('has paper size options (A3, A4)', () => {
    expect(src).toContain("{ label: 'A3', value: 'A3' }")
    expect(src).toContain("{ label: 'A4', value: 'A4' }")
  })

  it('has sides options (duplex, simplex)', () => {
    expect(src).toContain("{ label: '双面', value: 'duplex' }")
    expect(src).toContain("{ label: '单面', value: 'simplex' }")
  })

  it('has parseStep state machine', () => {
    expect(src).toContain("const parseStep = ref('upload')")
  })

  it('has parsedStandardized, parsedQuestions, parsedWeights refs', () => {
    expect(src).toContain('const parsedStandardized = ref([])')
    expect(src).toContain('const parsedQuestions = ref([])')
    expect(src).toContain('const parsedWeights = ref([])')
  })
})

describe('CardMakerTab scoreSum computed', () => {
  it('sums scores from parsedStandardized', () => {
    expect(src).toContain('const scoreSum = computed(')
    expect(src).toContain('.reduce((s, q) => s + (q.score || 0), 0)')
  })
})

describe('CardMakerTab answerRowClass', () => {
  it('returns row-danger for low confidence', () => {
    expect(src).toContain('row-danger')
    expect(src).toContain('row.confidence < 0.5')
  })

  it('returns row-warning for medium confidence', () => {
    expect(src).toContain('row-warning')
    expect(src).toContain('row.confidence < 0.8')
  })
})

describe('CardMakerTab renderMath', () => {
  it('defines renderMath function using katex', () => {
    expect(src).toContain('function renderMath(text)')
    expect(src).toContain('katex.renderToString')
  })

  it('handles display mode ($$) and inline ($) math', () => {
    expect(src).toContain('displayMode: true')
    expect(src).toContain('displayMode: false')
  })

  it('escapes HTML entities', () => {
    expect(src).toContain("'&amp;'")
    expect(src).toContain("'&lt;'")
    expect(src).toContain("'&gt;'")
  })
})

describe('CardMakerTab ESC handler', () => {
  it('registers keydown listener on mount', () => {
    expect(src).toContain("window.addEventListener('keydown', _escHandler)")
  })

  it('removes keydown listener on unmount', () => {
    expect(src).toContain("window.removeEventListener('keydown', _escHandler)")
  })

  it('checks for Escape key', () => {
    expect(src).toContain("e.key === 'Escape'")
  })

  it('revokes preview URL on unmount', () => {
    expect(src).toContain('URL.revokeObjectURL(cardPreviewUrl.value)')
  })
})

describe('CardMakerTab handleSaveCardTitle', () => {
  it('validates non-empty title', () => {
    expect(src).toContain('请输入答题卡标题')
  })

  it('calls updateExam with card_title', () => {
    expect(src).toContain("await updateExam(props.examId, { card_title: cardForm.cardTitle })")
  })

  it('emits update:exam on success', () => {
    expect(src).toContain("emit('update:exam', data)")
    expect(src).toContain('答题卡标题已保存')
  })

  it('shows error detail on failure', () => {
    expect(src).toContain("e.response?.data?.detail || '保存失败'")
  })
})

describe('CardMakerTab handleAnswerUpload', () => {
  it('calls parseAnswers with file and config', () => {
    expect(src).toContain('await parseAnswers(file.file, cardForm.subjectId, props.examId')
  })

  it('transitions to answers step on success', () => {
    expect(src).toContain("parseStep.value = 'answers'")
    expect(src).toContain('已识别')
    expect(src).toContain('题答案，请检查后确认')
  })

  it('handles upload error', () => {
    expect(src).toContain("detail || '解析失败: '")
  })
})

describe('CardMakerTab confirmAnswers', () => {
  it('emits confirm-answers with questions data', () => {
    expect(src).toContain("emit('confirm-answers', { subjectId: cardForm.subjectId, questions })")
  })
})

describe('CardMakerTab handleBarcodeGenerate', () => {
  it('calls generateBarcode API', () => {
    expect(src).toContain('await generateBarcode(barcodeFile.value)')
  })

  it('saves blob as PDF', () => {
    expect(src).toContain("saveBlob(resp.data, '条码贴纸.pdf')")
    expect(src).toContain('条码贴纸已生成')
  })
})

describe('CardMakerTab answerColumns', () => {
  it('defines columns for answer table', () => {
    expect(src).toContain('const answerColumns = [')
  })

  it('has number, section, type, answer, score, options, sub_count, confidence columns', () => {
    expect(src).toContain("title: '#'")
    expect(src).toContain("title: '大题'")
    expect(src).toContain("title: '题型'")
    expect(src).toContain("title: '答案'")
    expect(src).toContain("title: '分值'")
    expect(src).toContain("title: '选项'")
    expect(src).toContain("title: '小问'")
    expect(src).toContain("title: '置信度'")
  })

  it('has type options including single/multi choice and short answer', () => {
    expect(src).toContain("{ label: '单选', value: 'single_choice' }")
    expect(src).toContain("{ label: '多选', value: 'multi_choice' }")
    expect(src).toContain("{ label: '填空', value: 'fill_in_blank' }")
    expect(src).toContain("{ label: '解答', value: 'short_answer' }")
  })
})

describe('CardMakerTab resetToUpload', () => {
  it('clears all parsed data', () => {
    expect(src).toContain('function resetToUpload()')
    expect(src).toContain("parseStep.value = 'upload'")
    expect(src).toContain('parsedQuestions.value = []')
    expect(src).toContain('parsedWeights.value = []')
  })
})

describe('CardMakerTab onSubjectSelect', () => {
  it('resets state on subject change', () => {
    expect(src).toContain('function onSubjectSelect(subjectId)')
    expect(src).toContain('answerFileList.value = []')
    expect(src).toContain('uploadKey.value++')
  })
})

describe('CardMakerTab saveBlob', () => {
  it('creates download link from blob', () => {
    expect(src).toContain('function saveBlob(blob, filename)')
    expect(src).toContain("document.createElement('a')")
    expect(src).toContain('a.download = filename')
  })
})
