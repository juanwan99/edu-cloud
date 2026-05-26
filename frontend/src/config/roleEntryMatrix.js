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
