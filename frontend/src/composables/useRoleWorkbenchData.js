import { getRoleEntryPolicy } from '../config/roleEntryMatrix.js'
import { normalizeRole } from '../config/roles.js'

const MARKING_TODO_ROLES = new Set(['subject_teacher', 'homeroom_teacher', 'lesson_prep_leader'])

function toList(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  return []
}

function routeVisibleForRole(roleKey, route) {
  const policy = getRoleEntryPolicy(roleKey)
  return [...policy.primaryRoutes, ...policy.secondaryRoutes].includes(route)
}

function activeHomeworkTasks(tasks = []) {
  return tasks.filter(task => task.stats?.pending > 0 || task.status === 'active')
}

function processingGradingTasks(tasks = []) {
  return tasks.filter(task => task.status === 'processing' || task.status === 'pending')
}

function pendingGradingExams(exams = []) {
  return exams.filter(exam => exam.status === 'grading')
}

export function normalizeRecentExams(exams = []) {
  return toList(exams).slice(0, 3).map(exam => ({
    id: exam.id,
    name: exam.name,
    status: exam.status,
    subject_count: exam.subjects?.length ?? exam.subject_count ?? null,
    created_at: exam.created_at,
    grading_progress: exam.grading_progress ?? null,
  }))
}

export function buildRoleWorkbenchSummary(role, {
  dashboard = {},
  exams = [],
  markingAssignments = [],
  gradingTasks = [],
  homeworkTasks = [],
  conductOverview = null,
} = {}) {
  const roleKey = normalizeRole(role)
  const examList = toList(exams)
  const markingList = toList(markingAssignments)
  const gradingTaskList = toList(gradingTasks)
  const homeworkTaskList = toList(homeworkTasks)
  const todoItems = []

  if (MARKING_TODO_ROLES.has(roleKey) && markingList.length > 0 && routeVisibleForRole(roleKey, '/marking')) {
    todoItems.push({
      label: '我的阅卷任务',
      count: markingList.length,
      route: '/marking',
      color: 'yellow',
      tagType: 'warning',
    })
  }

  const gradingProcessing = processingGradingTasks(gradingTaskList)
  if (gradingProcessing.length > 0 && routeVisibleForRole(roleKey, '/grading/tasks')) {
    todoItems.push({
      label: `${gradingProcessing.length} 个阅卷任务进行中`,
      count: gradingProcessing.length,
      route: '/grading/tasks',
      color: 'coral',
      tagType: 'warning',
    })
  }

  const gradingExams = pendingGradingExams(examList)
  if (gradingExams.length > 0 && routeVisibleForRole(roleKey, '/exams')) {
    todoItems.push({
      label: `${gradingExams.length} 场考试待阅卷`,
      count: gradingExams.length,
      route: '/exams',
      color: 'yellow',
      tagType: 'info',
    })
  }

  const homeworkPending = activeHomeworkTasks(homeworkTaskList)
  if (homeworkPending.length > 0 && routeVisibleForRole(roleKey, '/homework')) {
    todoItems.push({
      label: `${homeworkPending.length} 份作业待批改`,
      count: homeworkPending.length,
      route: '/homework',
      color: 'purple',
      tagType: 'default',
    })
  }

  if (conductOverview?.pending_records > 0 && routeVisibleForRole(roleKey, '/conduct')) {
    todoItems.push({
      label: '德育待处理',
      count: conductOverview.pending_records,
      route: '/conduct',
      color: 'orange',
      tagType: 'warning',
    })
  }

  return {
    kpiData: dashboard || {},
    recentExams: normalizeRecentExams(examList),
    todoItems,
  }
}
