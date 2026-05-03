/**
 * AiGradingPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key sections (selector, question-list, grading-panel, content-modal, doc-crop)
 *  3. API calls (grading, exams, subjects, questions)
 *  4. State/data processing (hasRouteParams, question sorting, rubric, polling, content modal)
 *  5. Error handling (try-catch in async functions)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../AiGradingPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('AiGradingPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../AiGradingPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('AiGradingPage template sections', () => {
  it('contains page header with back button and title', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('返回')
    expect(content).toContain('AI 阅卷配置')
  })

  it('contains ExamSubjectSelector for non-route-params mode', () => {
    expect(content).toContain('<ExamSubjectSelector')
    expect(content).toContain('v-if="!hasRouteParams"')
    expect(content).toContain('@update:examId="onExamSelected"')
    expect(content).toContain('@update:subjectId="onSubjectSelected"')
  })

  it('contains main layout with QuestionList and GradingPanel', () => {
    expect(content).toContain('class="main-layout"')
    expect(content).toContain('<QuestionList')
    expect(content).toContain('<GradingPanel')
  })

  it('contains QuestionContentModal', () => {
    expect(content).toContain('<QuestionContentModal')
    expect(content).toContain('v-model:show="contentModalShow"')
    expect(content).toContain('@save="handleContentSave"')
  })

  it('contains DocCropPanel', () => {
    expect(content).toContain('<DocCropPanel')
    expect(content).toContain('v-model:show="showDocCrop"')
    expect(content).toContain('@save="handleDocCropSave"')
  })

  it('contains batch generate button', () => {
    expect(content).toContain(':loading="batchGenerating"')
    expect(content).toContain('@click="handleBatchGenerate"')
    expect(content).toContain('批量生成细则')
  })

  it('contains doc crop upload button', () => {
    expect(content).toContain('@click="showDocCrop = true"')
    expect(content).toContain('上传文档裁剪')
  })

  it('shows empty tip when no exam or subject selected', () => {
    expect(content).toContain('请先选择考试')
    expect(content).toContain('请选择科目')
  })
})

describe('AiGradingPage API imports', () => {
  it('imports grading API functions', () => {
    expect(content).toContain('getDispatchStatus')
    expect(content).toContain('generateRubric')
    expect(content).toContain('getRubric')
    expect(content).toContain('saveRubric')
    expect(content).toContain('createTask')
    expect(content).toContain('getTask')
    expect(content).toContain('getQuestion')
    expect(content).toContain('updateQuestionContent')
    expect(content).toContain('uploadQuestionImage')
  })

  it('imports exam and subject APIs', () => {
    expect(content).toContain("import { listExams } from '../api/exams'")
    expect(content).toContain('updateQuestion')
    expect(content).toContain("import { listSubjects } from '../api/subjects'")
  })
})

describe('AiGradingPage hasRouteParams logic', () => {
  it('computes hasRouteParams from route params', () => {
    expect(content).toContain('!!route.params.examId && !!route.params.subjectId')
  })

  it('derives examId from route or selection', () => {
    expect(content).toContain('route.params.examId || selectedExamId.value')
  })

  it('derives subjectId from route or selection', () => {
    expect(content).toContain('route.params.subjectId || selectedSubjectId.value')
  })

  it('loads questions directly when route params exist', () => {
    const mountBlock = content.slice(
      content.indexOf('onMounted(async'),
      content.indexOf('async function loadExamList')
    )
    expect(mountBlock).toContain('hasRouteParams.value')
    expect(mountBlock).toContain('await loadQuestions()')
  })

  it('loads exam list when no route params', () => {
    const mountBlock = content.slice(
      content.indexOf('onMounted(async'),
      content.indexOf('async function loadExamList')
    )
    expect(mountBlock).toContain('await loadExamList()')
  })
})

describe('AiGradingPage question loading and sorting', () => {
  it('loads questions from dispatch status endpoint', () => {
    expect(content).toContain('await getDispatchStatus(examId.value)')
  })

  it('finds subject by matching subject_id', () => {
    expect(content).toContain("String(s.subject_id) === String(subjectId.value)")
  })

  it('sorts questions by numeric name', () => {
    expect(content).toContain("parseInt(a.name, 10) || 0")
    expect(content).toContain("parseInt(b.name, 10) || 0")
    expect(content).toContain('return na - nb')
  })
})

describe('AiGradingPage rubric operations', () => {
  it('loads rubric for selected question', () => {
    expect(content).toContain('await getRubric(questionId)')
    expect(content).toContain("rubricItems.value = res.data?.criteria || []")
  })

  it('handles 404 when loading rubric', () => {
    expect(content).toContain("if (e.response?.status !== 404)")
    expect(content).toContain("message.error('加载评分细则失败')")
  })

  it('generates rubric with question_id and max_score', () => {
    expect(content).toContain('await generateRubric(')
    expect(content).toContain('selectedQuestion.value.question_id')
    expect(content).toContain('selectedQuestion.value.max_score || 0')
  })

  it('saves rubric with question_id and criteria', () => {
    expect(content).toContain('await saveRubric({')
    expect(content).toContain('question_id: selectedQuestion.value.question_id')
    expect(content).toContain('criteria: rubricItems.value')
  })

  it('refreshes question list after saving rubric', () => {
    const saveBlock = content.slice(
      content.indexOf('async function handleSaveRubric'),
      content.indexOf('async function handleStartGrading')
    )
    expect(saveBlock).toContain('await loadQuestions()')
  })
})

describe('AiGradingPage score editing', () => {
  it('tracks editing state with editingScoreId', () => {
    expect(content).toContain('editingScoreId.value = q.question_id')
  })

  it('saves score via updateQuestion', () => {
    expect(content).toContain('await updateQuestion(q.question_id, { max_score: q.max_score })')
  })

  it('shows confirmation message after score update', () => {
    expect(content).toContain("message.success(`第${q.name}题分值已更新为 ${q.max_score}`)")
  })
})

describe('AiGradingPage grading task with polling', () => {
  it('creates task with subject_id and question_id', () => {
    expect(content).toContain('await createTask(payload)')
    expect(content).toContain('subject_id: subjectId.value')
    expect(content).toContain('question_id: selectedQuestion.value.question_id')
  })

  it('extracts task_id from response', () => {
    expect(content).toContain("const taskId = res.data?.task_id || res.data?.id")
  })

  it('polls task progress every 3 seconds', () => {
    expect(content).toContain('}, 3000)')
  })

  it('tracks grading progress with status/graded/total', () => {
    expect(content).toContain("status: allDone ? (anyFailed ? 'failed' : 'completed') : 'processing'")
    expect(content).toContain('graded: totalGraded')
    expect(content).toContain('total: totalCount')
  })

  it('stops polling when task completes or fails', () => {
    expect(content).toContain("if (t.status === 'failed') anyFailed = true")
    expect(content).toContain("if (t.status !== 'completed' && t.status !== 'failed') allDone = false")
    const pollBlock = content.slice(
      content.indexOf('function startPolling()'),
      content.indexOf('function stopPolling()')
    )
    expect(pollBlock).toContain('if (allDone)')
    expect(pollBlock).toContain('stopPolling()')
  })

  it('cleans up polling on unmount', () => {
    expect(content).toContain('onUnmounted(() => {')
    expect(content).toContain('stopPolling()')
  })
})

describe('AiGradingPage content modal', () => {
  it('supports content and answer editing modes', () => {
    expect(content).toContain("contentModalType.value = type")
    expect(content).toContain("contentModalTitle.value = '编辑题干'")
    expect(content).toContain("contentModalTitle.value = '编辑参考答案'")
  })

  it('loads content or reference_answer based on type', () => {
    expect(content).toContain("selectedQuestion.value?.content || ''")
    expect(content).toContain("selectedQuestion.value?.reference_answer || ''")
  })

  it('loads images for content or reference_answer', () => {
    expect(content).toContain("selectedQuestion.value?.content_images || []")
    expect(content).toContain("selectedQuestion.value?.reference_answer_images || []")
  })

  it('uploads images before saving content', () => {
    expect(content).toContain('await uploadQuestionImage(qid, file)')
    expect(content).toContain("res.data?.path")
  })

  it('updates local state after saving', () => {
    expect(content).toContain('selectedQuestion.value.content = content')
    expect(content).toContain('selectedQuestion.value.reference_answer = content')
  })
})

describe('AiGradingPage remove image', () => {
  it('splices image array and updates backend', () => {
    expect(content).toContain('imgs.splice(idx, 1)')
    expect(content).toContain('await updateQuestionContent(q.question_id, { [key]: imgs })')
  })

  it('refreshes questions after removal', () => {
    const removeBlock = content.slice(
      content.indexOf('async function removeImage'),
      content.indexOf('async function handleDocCropSave')
    )
    expect(removeBlock).toContain('await loadQuestions()')
  })
})

describe('AiGradingPage doc crop save', () => {
  it('groups results by questionNum and field', () => {
    expect(content).toContain('const key = `${r.questionNum}::${r.field}`')
  })

  it('warns when question number not found', () => {
    expect(content).toContain('题号 ${questionNum} 未找到对应题目')
  })

  it('handles parent blob uploads for hierarchical questions', () => {
    expect(content).toContain('items.filter(it => it.parentBlob)')
    expect(content).toContain("type: 'image/png'")
  })

  it('syncs score from crop if provided', () => {
    expect(content).toContain('items.find(it => it.score != null)')
    expect(content).toContain('await updateQuestion(q.question_id, { max_score: scoreItem.score })')
  })
})

describe('AiGradingPage batch generate rubrics', () => {
  it('iterates over all questions', () => {
    const batchBlock = content.slice(
      content.indexOf('async function handleBatchGenerate'),
      content.indexOf('</script>')
    )
    expect(batchBlock).toContain('for (const q of questions.value)')
    expect(batchBlock).toContain('await generateRubric(q.question_id, q.max_score || 0)')
  })

  it('tracks ok and fail counts', () => {
    expect(content).toContain('let ok = 0, fail = 0')
  })

  it('skips 400 errors during batch', () => {
    expect(content).toContain("if (e.response?.status !== 400) fail++")
  })

  it('shows completion message with counts', () => {
    expect(content).toContain("message.success(`批量生成完成: ${ok} 成功${fail ? ', ' + fail + ' 失败' : ''}`)")
  })
})

describe('AiGradingPage exam/subject selection', () => {
  it('auto-selects single subject', () => {
    expect(content).toContain('if (opts.length === 1)')
    expect(content).toContain('selectedSubjectId.value = opts[0].value')
  })

  it('resets state on exam change', () => {
    const fnBlock = content.slice(
      content.indexOf('async function onExamSelected'),
      content.indexOf('async function onSubjectSelected')
    )
    expect(fnBlock).toContain('selectedSubjectId.value = null')
    expect(fnBlock).toContain('subjectOptions.value = []')
    expect(fnBlock).toContain('questions.value = []')
    expect(fnBlock).toContain('selectedQuestion.value = null')
  })

  it('resets state on subject change', () => {
    const fnBlock = content.slice(
      content.indexOf('async function onSubjectSelected'),
      content.indexOf('async function loadQuestions')
    )
    expect(fnBlock).toContain('questions.value = []')
    expect(fnBlock).toContain('selectedQuestion.value = null')
    expect(fnBlock).toContain('taskProgress.value = null')
    expect(fnBlock).toContain('stopPolling()')
  })
})

describe('AiGradingPage error handling', () => {
  it('wraps loadExamList in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadExamList'),
      content.indexOf('async function onExamSelected')
    )
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain("message.error('加载考试列表失败')")
  })

  it('wraps onExamSelected in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function onExamSelected'),
      content.indexOf('async function onSubjectSelected')
    )
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain("message.error('加载科目列表失败')")
  })

  it('wraps loadQuestions in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadQuestions'),
      content.indexOf('const editingScoreId')
    )
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain("message.error('加载题目失败')")
  })

  it('wraps handleGenerateRubric in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleGenerateRubric'),
      content.indexOf('async function handleSaveRubric')
    )
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain("题生成失败: ")
  })

  it('wraps handleStartGrading in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleStartGrading'),
      content.indexOf('function startPolling()')
    )
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('gradingStarting.value = false')
  })

  it('wraps handleContentSave in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleContentSave'),
      content.indexOf('async function removeImage')
    )
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain("message.error('保存失败:")
  })
})

describe('AiGradingPage selectQuestion fetches full details', () => {
  it('fetches full question details from backend', () => {
    expect(content).toContain('await getQuestion(q.question_id)')
    expect(content).toContain('selectedQuestion.value = { ...selectedQuestion.value, ...res.data }')
  })

  it('loads rubric after selecting question', () => {
    const selectBlock = content.slice(
      content.indexOf('async function selectQuestion'),
      content.indexOf('async function loadRubric')
    )
    expect(selectBlock).toContain('await loadRubric(q.question_id)')
  })

  it('resets rubric and loads details when selecting new question', () => {
    const selectBlock = content.slice(
      content.indexOf('async function selectQuestion'),
      content.indexOf('async function loadRubric')
    )
    expect(selectBlock).toContain('selectedQuestion.value = { ...q }')
    expect(selectBlock).toContain('rubricItems.value = []')
    expect(selectBlock).toContain('await getQuestion(q.question_id)')
    expect(selectBlock).toContain('selectedQuestion.value = { ...selectedQuestion.value, ...res.data }')
  })
})
