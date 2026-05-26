import { normalizeRole } from './roles.js'

export const OVERVIEW_NAV_ITEM = { label: '概览', route: '/', exact: true }

export const ROLE_ENTRY_MATRIX = {
  school_admin: {
    primaryRoutes: ['/school-settings', '/teachers', '/assignments', '/exam-import', '/analytics/report'],
    secondaryRoutes: ['/academic/semesters', '/academic/timetable', '/calendar', '/exams', '/grading/tasks', '/students'],
    hiddenRoutes: ['/ai-grading', '/marking', '/homework', '/question-bank', '/knowledge-tree', '/error-book'],
    header: [
      { label: '学校配置', route: '/school-settings', match: '/school-settings' },
      { label: '教师与职务', route: '/teachers', match: '/teachers' },
      { label: '组织关系', route: '/assignments', match: '/assignments' },
      { label: '数据导入', route: '/exam-import', match: '/exam-import' },
      { label: '数据报告', route: '/analytics/report', match: '/analytics' },
    ],
    sidebar: {
      groups: ['school', 'academic', 'exam', 'student'],
      groupLabels: {
        school: '学校基础',
        academic: '人员组织',
        exam: '数据与流程',
        student: '学生数据',
      },
      routeLabels: {
        '/teachers': '教师与职务',
        '/school-settings': '学校配置',
        '/assignments': '任课关系',
        '/selections': '选科关系',
        '/academic/semesters': '学期管理',
        '/academic/timetable': '课程表',
        '/exam-import': '数据导入',
        '/exams': '考试流程',
        '/grading/tasks': '阅卷流程',
        '/analytics/report': '数据报告',
      },
    },
  },
  principal: {
    primaryRoutes: ['/analytics/report', '/exams', '/analytics/ai-report', '/conduct', '/joint-exams'],
    secondaryRoutes: ['/students', '/grading/tasks', '/calendar'],
    hiddenRoutes: [
      '/school-settings', '/teachers', '/assignments', '/selections',
      '/academic/semesters', '/academic/timetable', '/academic/teaching-plans',
      '/exam-import', '/ai-grading', '/marking',
      '/homework', '/question-bank', '/knowledge-tree', '/error-book',
    ],
    header: [
      { label: '质量总览', route: '/analytics/report', match: '/analytics' },
      { label: '考试结果', route: '/exams', match: '/exams' },
      { label: '审批查看', route: '/analytics/ai-report', match: '/analytics/ai-report' },
      { label: '年级德育', route: '/conduct', match: '/conduct' },
      { label: '联考复盘', route: '/joint-exams', match: '/joint-exams' },
    ],
    sidebar: {
      groups: ['exam', 'student', 'school'],
      groupLabels: {
        exam: '质量治理',
        student: '学生与德育',
        school: '协同复盘',
      },
      routeLabels: {
        '/exams': '考试结果',
        '/grading/tasks': '阅卷风险',
        '/analytics/report': '质量总览',
        '/analytics/ai-report': '质量报告',
        '/students': '学生明细',
        '/conduct': '德育概览',
        '/joint-exams': '联考复盘',
        '/calendar': '校历事件',
      },
    },
  },
  academic_director: {
    primaryRoutes: ['/assignments', '/exams', '/grading/tasks', '/analytics/report'],
    secondaryRoutes: [
      '/academic/timetable', '/academic/semesters', '/exam-import', '/students',
      '/teachers', '/calendar', '/question-bank', '/knowledge-tree', '/homework',
      '/conduct', '/conduct/settings', '/analytics/ai-report', '/joint-exams',
      '/academic/teaching-plans', '/selections',
    ],
    hiddenRoutes: ['/marking', '/error-book'],
    header: [
      { label: '教学运行', route: '/assignments', match: '/assignments' },
      { label: '考试管理', route: '/exams', match: '/exams' },
      { label: '阅卷调度', route: '/grading/tasks', match: '/grading' },
      { label: '数据报告', route: '/analytics/report', match: '/analytics' },
    ],
    sidebar: {
      groups: ['academic', 'exam', 'student', 'school', 'research'],
      groupLabels: {
        academic: '教学运行',
        exam: '考试质量',
        student: '学生数据',
        school: '学校基础',
        research: '教研资源',
      },
      routeLabels: {
        '/assignments': '任课关系',
        '/selections': '选科管理',
        '/academic/semesters': '学期管理',
        '/academic/timetable': '课程表',
        '/exams': '考试管理',
        '/exam-import': '成绩导入',
        '/grading/tasks': '阅卷流程',
        '/analytics/report': '数据报告',
        '/analytics/ai-report': '质量报告',
        '/students': '学生档案',
        '/conduct': '德育协同',
        '/conduct/settings': '德育规则',
        '/teachers': '教师与职务',
        '/joint-exams': '联考复盘',
        '/calendar': '校历管理',
        '/knowledge-tree': '知识图谱',
        '/homework': '作业管理',
        '/question-bank': '题库建设',
        '/academic/teaching-plans': '教学计划',
      },
    },
  },
  grade_leader: {
    primaryRoutes: ['/students', '/analytics/report', '/conduct', '/joint-exams'],
    secondaryRoutes: ['/exams', '/analytics/ai-report', '/calendar', '/homework', '/conduct/settings'],
    hiddenRoutes: ['/marking', '/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/question-bank', '/knowledge-tree'],
    header: [
      { label: '年级学生', route: '/students', match: '/students' },
      { label: '年级考试', route: '/exams', match: '/exams' },
      { label: '数据报告', route: '/analytics/report', match: '/analytics' },
      { label: '德育协同', route: '/conduct', match: '/conduct' },
    ],
    sidebar: {
      groups: ['student', 'exam', 'school'],
      groupLabels: {
        student: '年级学生',
        exam: '年级考试',
        school: '年级协同',
      },
      routeLabels: {
        '/students': '重点学生',
        '/conduct': '德育协同',
        '/conduct/settings': '德育规则',
        '/exams': '考试管理',
        '/analytics/report': '数据报告',
        '/analytics/ai-report': '质量报告',
        '/joint-exams': '联考复盘',
        '/calendar': '年级校历',
      },
    },
  },
  homeroom_teacher: {
    primaryRoutes: ['/students', '/conduct', '/analytics/report', '/homework'],
    secondaryRoutes: ['/exams', '/marking', '/analytics/ai-report', '/question-bank', '/knowledge-tree', '/error-book', '/conduct/settings'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/academic/timetable', '/academic/semesters'],
    header: [
      { label: '班级学生', route: '/students', match: '/students' },
      { label: '德育记录', route: '/conduct', match: '/conduct' },
      { label: '班级报告', route: '/analytics/report', match: '/analytics' },
      { label: '作业跟进', route: '/homework', match: '/homework' },
    ],
    sidebar: {
      groups: ['student', 'exam', 'research'],
      groupLabels: {
        student: '班级学生',
        exam: '班级考试',
        research: '教学巩固',
      },
      routeLabels: {
        '/students': '学生档案',
        '/conduct': '德育记录',
        '/conduct/settings': '德育规则',
        '/exams': '考试管理',
        '/marking': '人工阅卷',
        '/analytics/report': '班级报告',
        '/analytics/ai-report': '质量报告',
        '/knowledge-tree': '知识图谱',
        '/homework': '作业跟进',
        '/question-bank': '题库管理',
        '/error-book': '错题本',
      },
    },
  },
  lesson_prep_leader: {
    primaryRoutes: ['/exams', '/grading/tasks', '/ai-grading', '/analytics/report'],
    secondaryRoutes: ['/marking', '/analytics/ai-report', '/question-bank', '/knowledge-tree', '/homework', '/error-book'],
    hiddenRoutes: ['/school-settings', '/assignments', '/teachers', '/students', '/conduct', '/academic/timetable', '/academic/semesters'],
    header: [
      { label: '学科考试', route: '/exams', match: '/exams' },
      { label: '阅卷分工', route: '/grading/tasks', match: '/grading' },
      { label: '学科报告', route: '/analytics/report', match: '/analytics' },
      { label: '题库沉淀', route: '/question-bank', match: '/question-bank' },
    ],
    sidebar: {
      groups: ['exam', 'research'],
      groupLabels: {
        exam: '学科考试',
        research: '资源沉淀',
      },
      routeLabels: {
        '/exams': '学科考试',
        '/grading/tasks': '阅卷分工',
        '/ai-grading': '阅卷控制',
        '/marking': '人工阅卷',
        '/analytics/report': '学科报告',
        '/analytics/ai-report': '质量报告',
        '/knowledge-tree': '知识图谱',
        '/homework': '作业巩固',
        '/question-bank': '题库沉淀',
        '/error-book': '错题本',
      },
    },
  },
  teaching_research_leader: {
    primaryRoutes: ['/knowledge-tree', '/question-bank', '/analytics/report', '/exams'],
    secondaryRoutes: ['/analytics/ai-report', '/homework', '/error-book', '/academic/teaching-plans', '/marking'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/students', '/conduct'],
    header: [
      { label: '知识图谱', route: '/knowledge-tree', match: '/knowledge-tree' },
      { label: '题库建设', route: '/question-bank', match: '/question-bank' },
      { label: '学科趋势', route: '/analytics/report', match: '/analytics' },
      { label: '考试证据', route: '/exams', match: '/exams' },
    ],
    sidebar: {
      groups: ['research', 'exam'],
      groupLabels: {
        research: '教研资源',
        exam: '质量证据',
      },
      routeLabels: {
        '/knowledge-tree': '知识图谱',
        '/homework': '作业观察',
        '/question-bank': '题库建设',
        '/error-book': '错题追踪',
        '/exams': '考试证据',
        '/marking': '人工阅卷',
        '/analytics/report': '学科趋势',
        '/analytics/ai-report': '质量报告',
      },
    },
  },
  subject_teacher: {
    primaryRoutes: ['/exams', '/marking', '/analytics/report', '/homework'],
    secondaryRoutes: ['/question-bank', '/knowledge-tree', '/error-book', '/analytics/ai-report'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/students', '/conduct', '/academic/timetable', '/academic/semesters'],
    header: [
      { label: '相关考试', route: '/exams', match: '/exams' },
      { label: '我的阅卷', route: '/marking', match: '/marking' },
      { label: '成绩分析', route: '/analytics/report', match: '/analytics' },
      { label: '作业管理', route: '/homework', match: '/homework' },
    ],
    sidebar: {
      groups: ['exam', 'research'],
      groupLabels: {},
      routeLabels: {},
    },
  },
  parent: {
    primaryRoutes: ['/analytics/report', '/homework'],
    secondaryRoutes: ['/conduct', '/knowledge-tree'],
    hiddenRoutes: ['/exams', '/exam-import', '/grading/tasks', '/ai-grading', '/marking', '/school-settings', '/assignments', '/teachers'],
    header: [
      { label: '成绩查看', route: '/analytics/report', match: '/analytics' },
      { label: '作业查看', route: '/homework', match: '/homework' },
    ],
    sidebar: {
      groups: ['student', 'research'],
      groupLabels: {},
      routeLabels: {},
    },
  },
}

const ROLE_ENTRY_ALIASES = {
  platform_admin: 'school_admin',
  district_admin: 'school_admin',
}

export function getRoleEntryPolicy(role) {
  const normalized = normalizeRole(role)
  const key = ROLE_ENTRY_MATRIX[normalized] ? normalized : ROLE_ENTRY_ALIASES[normalized]
  return ROLE_ENTRY_MATRIX[key] || ROLE_ENTRY_MATRIX.subject_teacher
}

export function getRoleHeaderNav(role) {
  return getRoleEntryPolicy(role).header
}

export function getRoleSidebarPolicy(role) {
  const policy = getRoleEntryPolicy(role)
  return {
    groups: policy.sidebar.groups,
    hiddenRoutes: policy.hiddenRoutes,
    labels: {
      groups: policy.sidebar.groupLabels || {},
      routes: policy.sidebar.routeLabels || {},
    },
  }
}

const ROLE_DASHBOARD_KPIS = {
  school_admin: [
    { id: 'total_exams', label: '考试流程', color: 'mint', source: 'dashboard_summary' },
    { id: 'total_students', label: '学生数据', color: 'yellow', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '流程待办', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_staff', label: '教职工', color: 'purple', source: 'dashboard_summary' },
  ],
  principal: [
    { id: 'total_exams', label: '考试结果', color: 'mint', source: 'dashboard_summary' },
    { id: 'total_students', label: '覆盖学生', color: 'yellow', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '质量风险', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_classes', label: '覆盖班级', color: 'purple', source: 'dashboard_summary' },
  ],
  academic_director: [
    { id: 'total_classes', label: '运行班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '阅卷风险', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_exams', label: '考试组织', color: 'yellow', source: 'dashboard_summary' },
    { id: 'total_staff', label: '教师关系', color: 'purple', source: 'dashboard_summary' },
  ],
  grade_leader: [
    { id: 'total_classes', label: '年级班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'total_exams', label: '年级考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '待关注项', color: 'coral', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '年级表现', color: 'purple', source: 'dashboard_summary' },
  ],
  homeroom_teacher: [
    { id: 'total_classes', label: '负责班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '待处理项', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_exams', label: '班级考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '班级表现', color: 'purple', source: 'dashboard_summary' },
  ],
  lesson_prep_leader: [
    { id: 'total_classes', label: '覆盖班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '待统筹阅卷', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_exams', label: '组内考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '学科表现', color: 'purple', source: 'dashboard_summary' },
  ],
  teaching_research_leader: [
    { id: 'total_classes', label: '覆盖班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'total_exams', label: '相关考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '学科表现', color: 'purple', source: 'dashboard_summary' },
  ],
  subject_teacher: [
    { id: 'total_classes', label: '教授班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '待处理阅卷', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_exams', label: '相关考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '学科表现', color: 'purple', source: 'dashboard_summary' },
  ],
  parent: [],
}

export function getRoleDashboardKpis(role) {
  const normalized = normalizeRole(role)
  const key = ROLE_DASHBOARD_KPIS[normalized] ? normalized : ROLE_ENTRY_ALIASES[normalized]
  return ROLE_DASHBOARD_KPIS[key] || ROLE_DASHBOARD_KPIS.subject_teacher
}

function toPositiveInteger(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) && numeric > 0 ? Math.round(numeric) : 0
}

function metric(value, unit, fallback = '待核对') {
  const count = toPositiveInteger(value)
  return count > 0 ? `${count} ${unit}` : fallback
}

function pendingGradingCount(summary = {}, todoItems = []) {
  const directCount = toPositiveInteger(summary.pending_grading ?? summary.pending_subjects)
  if (directCount > 0) return directCount

  return todoItems.reduce((total, item) => total + toPositiveInteger(item.count), 0)
}

function activeExamCount(summary = {}, recentExams = []) {
  const activeStatuses = new Set(['draft', 'published', 'grading'])
  const recentActiveCount = recentExams.filter(exam => activeStatuses.has(exam.status)).length
  if (recentActiveCount > 0) return recentActiveCount
  return toPositiveInteger(summary.total_exams)
}

function todoCount(todoItems = []) {
  return todoItems.reduce((total, item) => total + toPositiveInteger(item.count), 0)
}

function actionTagType(tone) {
  if (tone === 'orange') return 'warning'
  if (tone === 'yellow') return 'success'
  return 'default'
}

export function buildRolePriorityActions(role, { profile, summary = {}, recentExams = [], todoItems = [] } = {}) {
  const normalized = normalizeRole(role)
  const roleKey = ROLE_ENTRY_ALIASES[normalized] || normalized
  if (roleKey === 'school_admin') {
    return buildSchoolAdminPriorityActions({ summary, recentExams, todoItems })
  }

  return (profile?.priorities || []).map(action => ({
    ...action,
    tag: action.meta,
    tagType: actionTagType(action.tone),
  }))
}

function buildSchoolAdminPriorityActions({ summary = {}, recentExams = [], todoItems = [] } = {}) {
  const pending = pendingGradingCount(summary, todoItems)
  const activeExams = activeExamCount(summary, recentExams)

  return [
    {
      title: '核对学校基础配置',
      desc: '先确认学校资料、学期、校历和模块开关，避免后续流程缺少基础条件。',
      route: '/school-settings',
      tag: '待核对',
      tagType: 'warning',
      tone: 'yellow',
    },
    {
      title: '核对人员与任课关系',
      desc: '教师、班级、学科关系是考试、成绩和作业能否正确流转的前提。',
      route: '/assignments',
      tag: metric(summary.total_staff, '人'),
      tagType: 'default',
      tone: 'purple',
    },
    {
      title: '监控考试与阅卷流程',
      desc: pending > 0
        ? '阅卷流程存在待处理事项，优先确认是否阻塞报告发布。'
        : '没有阅卷阻塞时，关注近期考试创建、导入和发布状态。',
      route: '/exams',
      tag: pending > 0 ? `${pending} 项` : metric(activeExams, '场', '待确认'),
      tagType: pending > 0 ? 'warning' : 'info',
      tone: 'orange',
    },
    {
      title: '核查学生数据和权限范围',
      desc: '学生归属、教师可见范围和报告发布范围需要保持一致。',
      route: '/students',
      tag: metric(summary.total_students, '人'),
      tagType: 'default',
      tone: 'coral',
    },
  ]
}

function buildSchoolAdminPanel({ summary = {}, recentExams = [], todoItems = [] } = {}) {
  const pending = pendingGradingCount(summary, todoItems)
  const activeExams = activeExamCount(summary, recentExams)

  return {
    title: '运行治理中心',
    sub: '学校配置、人员关系、考试流程和数据权限',
    actionLabel: '进入学校配置',
    actionRoute: '/school-settings',
    items: [
      {
        label: '配置',
        title: '学校配置',
        desc: '从学校资料、学期、校历和模块开关开始校验运行基础。',
        route: '/school-settings',
        tone: 'yellow',
      },
      {
        label: '组织',
        title: '任课关系',
        desc: `${metric(summary.total_staff, '人')} 教职工，重点核对教师身份、班级和学科关系。`,
        route: '/assignments',
        tone: 'purple',
      },
      {
        label: '流程',
        title: '考试流程',
        desc: pending > 0
          ? `${pending} 项阅卷或流程待办，先确认是否阻塞报告发布。`
          : `${metric(activeExams, '场', '考试待确认')}，关注创建、导入、阅卷和发布状态。`,
        route: '/exams',
        tone: 'coral',
      },
      {
        label: '数据',
        title: '学生数据',
        desc: `${metric(summary.total_students, '人')} 学生，核查归属、权限和报告可见范围。`,
        route: '/students',
        tone: 'mint',
      },
    ],
  }
}

function buildPrincipalPanel({ summary = {}, recentExams = [], todoItems = [] } = {}) {
  const activeExams = activeExamCount(summary, recentExams)
  const pending = pendingGradingCount(summary, todoItems)

  return {
    title: '学校治理中心',
    sub: '质量总览、考试结果、审批查看和联考复盘',
    actionLabel: '查看质量总览',
    actionRoute: '/analytics/report',
    items: [
      {
        label: '总览',
        title: '质量总览',
        desc: `${metric(summary.total_students, '人', '学生范围待确认')}，先看学校、年级、班级和学科态势。`,
        route: '/analytics/report',
        tone: 'yellow',
      },
      {
        label: '考试',
        title: '考试结果',
        desc: `${metric(activeExams, '场', '近期考试待确认')}，关注发布状态和异常波动。`,
        route: '/exams',
        tone: 'purple',
      },
      {
        label: '审批',
        title: '审批查看',
        desc: pending > 0 ? `${pending} 项质量或发布事项待确认。` : '成绩发布、通知和风险报告集中查看。',
        route: '/analytics/ai-report',
        tone: 'coral',
      },
      {
        label: '复盘',
        title: '联考复盘',
        desc: '把联考、阶段考和德育态势汇总为治理动作。',
        route: '/joint-exams',
        tone: 'mint',
      },
    ],
  }
}

function buildAcademicDirectorPanel({ summary = {}, recentExams = [], todoItems = [] } = {}) {
  const pending = pendingGradingCount(summary, todoItems)
  const activeExams = activeExamCount(summary, recentExams)

  return {
    title: '教学运行中心',
    sub: '课表、学期、教师关系、考试流程和质量风险',
    actionLabel: '查看教学运行',
    actionRoute: '/assignments',
    items: [
      {
        label: '运行',
        title: '教学运行',
        desc: `课表、学期和教师关系先集中核对，当前 ${metric(summary.total_staff, '人')} 教职工。`,
        route: '/assignments',
        tone: 'yellow',
      },
      {
        label: '考试',
        title: '考试流程',
        desc: `${metric(activeExams, '场', '近期考试待确认')}，关注创建、导入、阅卷和发布状态。`,
        route: '/exams',
        tone: 'purple',
      },
      {
        label: '质量',
        title: '阅卷质量',
        desc: pending > 0 ? `${pending} 项阅卷风险，优先确认是否阻塞报告发布。` : '无阅卷阻塞时，重点看报告发布和质量异常。',
        route: '/grading/tasks',
        tone: 'coral',
      },
      {
        label: '报告',
        title: '质量报告',
        desc: '将考试、阅卷和班级差异汇总为教学运行复盘。',
        route: '/analytics/report',
        tone: 'mint',
      },
    ],
  }
}

function buildGradeLeaderPanel({ summary = {}, recentExams = [], todoItems = [] } = {}) {
  const activeExams = activeExamCount(summary, recentExams)
  const todos = todoCount(todoItems)

  return {
    title: '年级协同中心',
    sub: '班级差异、重点学生、德育协同和联考复盘',
    actionLabel: '查看年级态势',
    actionRoute: '/analytics/report',
    items: [
      {
        label: '态势',
        title: '年级态势',
        desc: `${metric(activeExams, '场', '近期考试待确认')}，先看班级差异和学科短板。`,
        route: '/analytics/report',
        tone: 'yellow',
      },
      {
        label: '学生',
        title: '重点学生',
        desc: `${metric(summary.total_students, '人')} 学生中筛出成绩、德育、出勤风险。`,
        route: '/students',
        tone: 'coral',
      },
      {
        label: '协同',
        title: '德育协同',
        desc: todos > 0 ? `${todos} 项跨班级事项，安排班主任跟进。` : '跨班级记录、通知和导出集中处理。',
        route: '/conduct',
        tone: 'purple',
      },
      {
        label: '复盘',
        title: '联考复盘',
        desc: '联考和阶段考沉淀为年级复盘结论。',
        route: '/joint-exams',
        tone: 'mint',
      },
    ],
  }
}

function buildHomeroomPanel({ summary = {}, todoItems = [] } = {}) {
  const todos = todoCount(todoItems)

  return {
    title: '班级跟进中心',
    sub: '学生风险、德育记录、班级考试和巩固动作',
    actionLabel: '查看班级学生',
    actionRoute: '/students',
    items: [
      {
        label: '学生',
        title: '学生风险',
        desc: `${metric(summary.total_students, '人')} 学生，按成绩波动、缺交和德育异常筛查。`,
        route: '/students',
        tone: 'yellow',
      },
      {
        label: '德育',
        title: '德育记录',
        desc: todos > 0 ? `${todos} 条记录或通知待确认。` : '班级记录、通知、家长确认形成闭环。',
        route: '/conduct',
        tone: 'coral',
      },
      {
        label: '班级',
        title: '班级报告',
        desc: '从班级考试状态进入学生分层和跟进建议。',
        route: '/analytics/report',
        tone: 'purple',
      },
      {
        label: '巩固',
        title: '作业跟进',
        desc: '把报告结论转成班级作业和错题跟进。',
        route: '/homework',
        tone: 'mint',
      },
    ],
  }
}

function buildLessonPrepPanel({ summary = {}, recentExams = [], todoItems = [] } = {}) {
  const pending = pendingGradingCount(summary, todoItems)
  const activeExams = activeExamCount(summary, recentExams)

  return {
    title: '学科组织中心',
    sub: '本学科考试、阅卷分工、质量报告和资源沉淀',
    actionLabel: '管理学科考试',
    actionRoute: '/exams',
    items: [
      {
        label: '考试',
        title: '学科考试',
        desc: `${metric(activeExams, '场', '近期考试待确认')}，先确认试卷、题目标签和发布状态。`,
        route: '/exams',
        tone: 'yellow',
      },
      {
        label: '阅卷',
        title: '阅卷分工',
        desc: pending > 0 ? `${pending} 项进度或质量异常。` : '按题目和老师查看本学科阅卷状态。',
        route: '/grading/tasks',
        tone: 'coral',
      },
      {
        label: '报告',
        title: '学科报告',
        desc: '跨班级看共性薄弱点和讲评顺序。',
        route: '/analytics/report',
        tone: 'purple',
      },
      {
        label: '资源',
        title: '题库沉淀',
        desc: '把高频错题和讲评资料沉淀成组内资源。',
        route: '/question-bank',
        tone: 'mint',
      },
    ],
  }
}

function buildTeachingResearchPanel() {
  return {
    title: '教研质量中心',
    sub: '学科趋势、共性错因、教研动作和资源体系',
    actionLabel: '查看学科质量',
    actionRoute: '/analytics/report',
    items: [
      {
        label: '趋势',
        title: '学科趋势',
        desc: '跨年级、跨考试观察质量变化。',
        route: '/analytics/report',
        tone: 'yellow',
      },
      {
        label: '错因',
        title: '共性错因',
        desc: '从题目质量和学生错因提取教研主题。',
        route: '/analytics/ai-report',
        tone: 'coral',
      },
      {
        label: '共研',
        title: '教研动作',
        desc: '把共性问题转成讲评资料和备课共识。',
        route: '/question-bank',
        tone: 'purple',
      },
      {
        label: '资产',
        title: '知识体系',
        desc: '题库、图谱、教学计划同步沉淀。',
        route: '/knowledge-tree',
        tone: 'mint',
      },
    ],
  }
}

const ROLE_PANEL_BUILDERS = {
  school_admin: buildSchoolAdminPanel,
  principal: buildPrincipalPanel,
  academic_director: buildAcademicDirectorPanel,
  grade_leader: buildGradeLeaderPanel,
  homeroom_teacher: buildHomeroomPanel,
  lesson_prep_leader: buildLessonPrepPanel,
  teaching_research_leader: buildTeachingResearchPanel,
}

export function buildRoleActionPanel(role, context = {}) {
  const normalized = normalizeRole(role)
  const roleKey = ROLE_ENTRY_ALIASES[normalized] || normalized
  const builder = ROLE_PANEL_BUILDERS[roleKey]
  return builder ? builder(context) : null
}
