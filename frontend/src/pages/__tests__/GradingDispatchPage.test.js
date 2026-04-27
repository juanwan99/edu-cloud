/**
 * GradingDispatchPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key sections (top-bar, summary-bar, scan, batch-ops, subject-list, editor)
 *  3. API calls (listExams, getDispatchStatus, createTask, scan/pipeline APIs)
 *  4. State/data processing (stageGroups, STAGE_LABELS, canDetect, canCut, subjects filter, concurrency)
 *  5. Error handling (try-catch in multiple async functions)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../GradingDispatchPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('GradingDispatchPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../GradingDispatchPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('GradingDispatchPage template sections', () => {
  it('contains top-bar with exam selector', () => {
    expect(content).toContain('class="top-bar"')
    expect(content).toContain('v-model:value="selectedExamId"')
    expect(content).toContain(':options="examOptions"')
    expect(content).toContain('@update:value="onExamChange"')
  })

  it('contains summary-bar', () => {
    expect(content).toContain('class="summary-bar"')
    expect(content).toContain('v-for="g in stageGroups"')
    expect(content).toContain('g.count')
    expect(content).toContain('g.label')
  })

  it('contains ScanSection component', () => {
    expect(content).toContain('<ScanSection')
    expect(content).toContain(':scan-root-dir="scanRootDir"')
    expect(content).toContain('@scan-dir="handleScanDir"')
  })

  it('contains BatchOperationsBar component', () => {
    expect(content).toContain('<BatchOperationsBar')
    expect(content).toContain('@batch-detect="handleBatchDetect"')
    expect(content).toContain('@batch-cut="handleBatchCut"')
    expect(content).toContain('@batch-grade="handleBatchGrade"')
  })

  it('contains SubjectStatusCard list', () => {
    expect(content).toContain('class="subject-list"')
    expect(content).toContain('<SubjectStatusCard')
    expect(content).toContain('v-for="s in subjects"')
  })

  it('contains TemplatePreviewEditor', () => {
    expect(content).toContain('<TemplatePreviewEditor')
    expect(content).toContain('v-model:show="editorShow"')
    expect(content).toContain('@confirm="onEditorConfirm"')
  })

  it('contains hidden folder input for upload', () => {
    expect(content).toContain('ref="folderInput"')
    expect(content).toContain('type="file"')
    expect(content).toContain('webkitdirectory')
    expect(content).toContain('@change="handleFolderSelected"')
  })

  it('shows empty state when no exam selected or no subjects', () => {
    expect(content).toContain('请先选择一个考试')
    expect(content).toContain('暂无科目数据')
  })
})

describe('GradingDispatchPage page header', () => {
  it('has correct title and subtitle', () => {
    expect(content).toContain('扫描调度')
    expect(content).toContain('扫描切割 → 选择题判分 → AI 阅卷 → 教师校对')
  })
})

describe('GradingDispatchPage API imports', () => {
  it('imports exam and grading APIs', () => {
    expect(content).toContain("import { listExams } from '../api/exams'")
    expect(content).toContain("import { getDispatchStatus, createTask } from '../api/grading'")
  })

  it('imports scan/pipeline APIs', () => {
    expect(content).toContain('uploadScanFolder')
    expect(content).toContain('scanDirectory')
    expect(content).toContain('startPipeline')
    expect(content).toContain('getPipelineProgress')
    expect(content).toContain('stopPipeline')
    expect(content).toContain('autoDetectCV')
    expect(content).toContain('saveCVTemplate')
    expect(content).toContain('getCVTemplate')
    expect(content).toContain('fetchScanImageBlob')
  })

  it('imports role config for permission check', () => {
    expect(content).toContain("import { SCHOOL_ADMIN_ROLES } from '../config/roles.js'")
    expect(content).toContain("import { useAuthStore } from '../stores/auth'")
  })
})

describe('GradingDispatchPage stageGroups computed', () => {
  it('defines 7 stage group definitions', () => {
    expect(content).toContain("{ key: 'done', label: '已完成' }")
    expect(content).toContain("{ key: 'active', label: '阅卷中'")
    expect(content).toContain("{ key: 'ready', label: '待阅卷' }")
    expect(content).toContain("{ key: 'pending_cut', label: '待切割' }")
    expect(content).toContain("{ key: 'pending_detect', label: '待检测' }")
    expect(content).toContain("{ key: 'idle', label: '待上传' }")
    expect(content).toContain("{ key: 'failed', label: '失败' }")
  })

  it('combines ai_grading and reviewing stages for active count', () => {
    expect(content).toContain("stages: ['ai_grading', 'reviewing']")
  })

  it('filters out groups with zero count', () => {
    expect(content).toContain('.filter(g => g.count > 0)')
  })
})

describe('GradingDispatchPage STAGE_LABELS', () => {
  it('defines 9 stage labels', () => {
    expect(content).toContain("idle: '待上传'")
    expect(content).toContain("pending_detect: '待检测'")
    expect(content).toContain("pending_cut: '待切割'")
    expect(content).toContain("cutting: '切割中'")
    expect(content).toContain("ready: '待阅卷'")
    expect(content).toContain("ai_grading: 'AI 阅卷'")
    expect(content).toContain("reviewing: '校对中'")
    expect(content).toContain("failed: '失败'")
    expect(content).toContain("done: '已完成'")
  })
})

describe('GradingDispatchPage subject filtering', () => {
  it('filters subjects by role and subject codes', () => {
    expect(content).toContain('canManageAll.value || !mySubjectCodes.value')
    expect(content).toContain('mySubjectCodes.value.includes(s.subject_code)')
  })

  it('computes canManageAll from SCHOOL_ADMIN_ROLES', () => {
    expect(content).toContain('SCHOOL_ADMIN_ROLES.includes(auth.roleName)')
  })
})

describe('GradingDispatchPage canDetect and canCut logic', () => {
  it('canDetect checks pending_detect stage and permission', () => {
    const fnBlock = content.slice(
      content.indexOf('function canDetect(s)'),
      content.indexOf('function canCut(s)')
    )
    expect(fnBlock).toContain("s.stage !== 'pending_detect'")
    expect(fnBlock).toContain('canManageAll.value')
    expect(fnBlock).toContain('mySubjectCodes.value.includes(s.subject_code)')
  })

  it('canCut checks pending_cut stage', () => {
    expect(content).toContain("return s.stage === 'pending_cut'")
  })
})

describe('GradingDispatchPage batch detect with concurrency', () => {
  it('uses concurrency limit of 3', () => {
    expect(content).toContain('const CONCURRENCY = 3')
  })

  it('tracks detect status per subject', () => {
    expect(content).toContain("detectStatus.value[s.subject_id] = 'pending'")
    expect(content).toContain("detectStatus.value[s.subject_id] = 'running'")
    expect(content).toContain("detectStatus.value[s.subject_id] = 'done'")
    expect(content).toContain("detectStatus.value[s.subject_id] = 'failed'")
  })

  it('updates progress text during batch detect', () => {
    expect(content).toContain('batchProgressText.value = `${ok + fail}/${total}`')
  })

  it('shows different messages for full success vs partial failure', () => {
    expect(content).toContain("message.success(`全科检测完成：${ok} 科成功`)")
    expect(content).toContain("message.warning(`检测完成：${ok} 成功，${fail} 失败")
  })
})

describe('GradingDispatchPage template detect with A/B sides', () => {
  it('detects A side and optionally B side', () => {
    const detectBlock = content.slice(
      content.indexOf('async function handleDetectTemplate'),
      content.indexOf('async function handlePreviewTemplate')
    )
    expect(detectBlock).toContain('autoDetectCV(fileA)')
    expect(detectBlock).toContain('fetchScanImageBlob(fileA)')
    expect(detectBlock).toContain("autoDetectCV(fileB, { priorRegions: dataA.regions })")
  })

  it('handles missing B side gracefully', () => {
    expect(content).toContain("} catch (_) { /* 无 B 面 */ }")
  })
})

describe('GradingDispatchPage pipeline polling', () => {
  it('polls every 2 seconds', () => {
    expect(content).toContain('}, 2000)')
  })

  it('handles pending B side after A side completes', () => {
    expect(content).toContain('pendingBSide.value')
    expect(content).toContain("message.info('A 面切割完成，自动开始 B 面切割')")
  })

  it('stops polling on unmount', () => {
    expect(content).toContain('onUnmounted(() => {')
    expect(content).toContain('stopPolling()')
  })

  it('computes progressPct from pipeline data', () => {
    expect(content).toContain('progressPct.value = Math.round((p.processed / p.total) * 100)')
  })
})

describe('GradingDispatchPage onEditorConfirm', () => {
  it('saves A side and optionally B side template', () => {
    expect(content).toContain("saveCVTemplate(editorSubjectId.value, 'A', A, editorWidth.value, editorHeight.value)")
    expect(content).toContain("saveCVTemplate(editorSubjectId.value, 'B', B, editorWidthB.value, editorHeightB.value)")
  })

  it('revokes blob URLs after save', () => {
    expect(content).toContain('URL.revokeObjectURL(editorBlobUrl.value)')
    expect(content).toContain('URL.revokeObjectURL(editorBlobUrlB.value)')
  })
})

describe('GradingDispatchPage grading actions', () => {
  it('creates grading task for single subject', () => {
    const gradeBlock = content.slice(
      content.indexOf('async function handleStartGrade'),
      content.indexOf('const canBatchGrade')
    )
    expect(gradeBlock).toContain('await createTask({ subject_id: s.subject_id })')
  })

  it('batch grade checks ready stage', () => {
    expect(content).toContain("s.stage === 'ready'")
  })

  it('navigates to AI grading page', () => {
    expect(content).toContain("router.push(`/exams/${selectedExamId.value}/ai-grading/${s.subject_id}`)")
  })
})

describe('GradingDispatchPage error handling', () => {
  it('wraps onMounted exam list fetch in try-catch', () => {
    expect(content).toContain('onMounted(async () => {')
    const mountStart = content.indexOf('onMounted(async () => {')
    const mountEnd = content.indexOf('onUnmounted(() =>')
    const mountBlock = content.slice(mountStart, mountEnd)
    expect(mountBlock).toContain('try {')
    expect(mountBlock).toContain('} catch (e) {')
    expect(mountBlock).toContain("message.error('加载考试列表失败')")
  })

  it('wraps loadStatus in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadStatus'),
      content.indexOf('function pickFolder')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain("message.error('加载阅卷状态失败')")
  })

  it('wraps handleScanDir in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleScanDir'),
      content.indexOf('function getScanDir')
    )
    expect(fnBlock).toContain('} catch (e) {')
  })

  it('wraps handleStartCut in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleStartCut'),
      content.indexOf('async function handleStopCut')
    )
    expect(fnBlock).toContain("message.error('启动切割失败:")
  })

  it('wraps handleFolderSelected in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleFolderSelected'),
      content.indexOf('function canDetect')
    )
    expect(fnBlock).toContain('} catch (err) {')
    expect(fnBlock).toContain("message.error('上传失败:")
  })

  it('wraps handleDetectTemplate in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleDetectTemplate'),
      content.indexOf('async function handlePreviewTemplate')
    )
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('detectLoading.value = null')
  })
})

describe('GradingDispatchPage file upload', () => {
  it('filters for image file extensions', () => {
    expect(content).toContain('/\\.(png|jpg|jpeg|bmp)$/i')
  })

  it('warns when no image files found', () => {
    expect(content).toContain("message.warning('未找到图片文件（支持 png/jpg/bmp）')")
  })

  it('tracks upload progress', () => {
    expect(content).toContain('uploadProgress.value = `${done}/${total}`')
  })
})

describe('GradingDispatchPage onExamChange resets state', () => {
  it('resets subjects, selection, and scan results', () => {
    const fnBlock = content.slice(
      content.indexOf('async function onExamChange'),
      content.indexOf('async function tryAutoDetectScanDir')
    )
    expect(fnBlock).toContain('selectedSubjects.value = []')
    expect(fnBlock).toContain('scanResults.value = []')
    expect(fnBlock).toContain("scanRootDir.value = ''")
  })
})
