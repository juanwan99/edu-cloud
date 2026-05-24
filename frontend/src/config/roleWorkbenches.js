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

export function buildAdminPriorityActions({ summary = {}, recentExams = [], todoItems = [] } = {}) {
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

function buildAdminRoleActionItems({ summary = {}, recentExams = [], todoItems = [] } = {}) {
  const pending = pendingGradingCount(summary, todoItems)
  const activeExams = activeExamCount(summary, recentExams)

  return [
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
  ]
}

function buildSchoolAdminPanel(context) {
  return {
    title: '运行治理中心',
    sub: '学校配置、人员关系、考试流程和数据权限',
    actionLabel: '进入学校配置 →',
    actionRoute: '/school-settings',
    items: buildAdminRoleActionItems(context),
  }
}

function buildAcademicDirectorPanel({ summary = {}, recentExams = [], todoItems = [] } = {}) {
  const pending = pendingGradingCount(summary, todoItems)
  const activeExams = activeExamCount(summary, recentExams)

  return {
    title: '教学运行中心',
    sub: '课表、学期、教师关系、考试流程和质量风险',
    actionLabel: '查看教学运行 →',
    actionRoute: '/academic/timetable',
    items: [
      {
        label: '运行',
        title: '教学运行',
        desc: `课表、学期和教师关系先集中核对，当前 ${metric(summary.total_staff, '人')} 教职工。`,
        route: '/academic/timetable',
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
        label: '配置',
        title: '任课配置',
        desc: '教师、班级、学科、选科关系保持一致，避免运行数据错位。',
        route: '/assignments',
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
    actionLabel: '查看年级态势 →',
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
    actionLabel: '查看班级学生 →',
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
    actionLabel: '管理学科考试 →',
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
    actionLabel: '查看学科质量 →',
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

const ROLE_PANEL_ALIASES = {
  platform_admin: 'school_admin',
  district_admin: 'school_admin',
  principal: 'school_admin',
}

const ROLE_PANEL_BUILDERS = {
  school_admin: buildSchoolAdminPanel,
  academic_director: buildAcademicDirectorPanel,
  grade_leader: buildGradeLeaderPanel,
  homeroom_teacher: buildHomeroomPanel,
  lesson_prep_leader: buildLessonPrepPanel,
  teaching_research_leader: buildTeachingResearchPanel,
}

export function buildRoleActionPanel(role, context = {}) {
  const roleKey = ROLE_PANEL_ALIASES[role] || role
  const builder = ROLE_PANEL_BUILDERS[roleKey]
  return builder ? builder(context) : null
}
