import { describe, expect, it } from 'vitest'
import { getSidebarGroups, getSidebarItems } from '../config/sidebarConfig.js'

// Phase 0.7D：academic 入口（学期管理/课程表/教学计划）接 teaching 门控。role-policy 测试验证「角色」过滤，
// 以「全模块开启的校」为基准，故 fullModules 含 teaching，使既有角色断言行为不变；teaching 关闭的 fail-closed
// 行为由下方 'role-aware sidebar module gating' 的专项用例显式构造验证（不改生产 DEFAULT_ENABLED）。
const fullModules = ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'research', 'conduct', 'teaching']
const routesFor = role => getSidebarItems(role, fullModules).map(item => item.route)
const groupLabelsFor = role => getSidebarGroups(role, fullModules).map(group => group.label)
const childLabelsFor = (role, groupKey) =>
  getSidebarGroups(role, fullModules)
    .find(group => group.key === groupKey)
    .children.map(item => item.label)

describe('role-aware sidebar policy', () => {
  it('school admin starts from school operation and hides personal teaching entries', () => {
    const groups = getSidebarGroups('school_admin', fullModules)
    expect(groups.map(group => group.key).slice(0, 2)).toEqual(['school', 'academic'])
    expect(groups.map(group => group.label)).toEqual(['学校基础', '人员组织', '数据与流程', '学生数据'])
    const routes = routesFor('school_admin')
    expect(routes).toContain('/school-settings')
    expect(routes).toContain('/assignments')
    expect(routes).toContain('/grading/tasks')
    expect(routes).not.toContain('/ai-grading')
    expect(routes).not.toContain('/marking')
    expect(routes).not.toContain('/homework')
    expect(routes).not.toContain('/question-bank')
    expect(routes).not.toContain('/knowledge-tree')
  })

  it('school admin sidebar labels match the school operation workflow', () => {
    const groups = getSidebarGroups('school_admin', fullModules)
    const schoolItems = groups.find(group => group.key === 'school').children
    const academicItems = groups.find(group => group.key === 'academic').children
    const examItems = groups.find(group => group.key === 'exam').children

    expect(schoolItems.map(item => item.label)).toContain('学校配置')
    expect(schoolItems.map(item => item.label)).toContain('校历管理')
    expect(academicItems.map(item => item.label)).toContain('任课关系')
    expect(examItems.map(item => item.label)).toContain('考试流程')
    expect(examItems.map(item => item.label)).toContain('数据导入')
    expect(examItems.map(item => item.label)).toContain('阅卷流程')
    expect(examItems.map(item => item.label)).toContain('数据报告')
  })

  it('principal sees governance overview instead of system administration', () => {
    const routes = routesFor('principal')
    expect(groupLabelsFor('principal')).toEqual(['质量治理', '学生与德育', '协同复盘'])
    expect(routes).toContain('/analytics/report')
    expect(routes).toContain('/exams')
    expect(routes).toContain('/students')
    expect(routes).toContain('/conduct')
    expect(routes).not.toContain('/school-settings')
    expect(routes).not.toContain('/teachers')
    expect(routes).not.toContain('/assignments')
  })

  it('lesson prep leader sees subject organization but not school administration', () => {
    const routes = routesFor('lesson_prep_leader')
    expect(routes).toContain('/exams')
    expect(routes).toContain('/grading/tasks')
    expect(routes).toContain('/analytics/report')
    expect(routes).toContain('/question-bank')
    expect(routes).not.toContain('/school-settings')
    expect(routes).not.toContain('/assignments')
    expect(routes).not.toContain('/conduct')
  })

  it('lesson prep leader navigation is framed around subject exam and resource work', () => {
    expect(groupLabelsFor('lesson_prep_leader')).toEqual(['学科考试', '资源沉淀'])
    expect(childLabelsFor('lesson_prep_leader', 'exam')).toEqual(
      expect.arrayContaining(['学科考试', '阅卷分工', '学科报告', '质量报告'])
    )
    expect(childLabelsFor('lesson_prep_leader', 'research')).toEqual(
      expect.arrayContaining(['作业巩固', '题库沉淀', '知识图谱'])
    )
  })

  it('homeroom teacher sees class and conduct work but not school configuration', () => {
    const routes = routesFor('homeroom_teacher')
    expect(routes).toContain('/students')
    expect(routes).toContain('/conduct')
    expect(routes).toContain('/homework')
    expect(routes).not.toContain('/school-settings')
    expect(routes).not.toContain('/academic/timetable')
  })

  it('homeroom teacher navigation is framed around class follow-up', () => {
    expect(groupLabelsFor('homeroom_teacher')).toEqual(['班级学生', '班级考试', '教学巩固'])
    expect(childLabelsFor('homeroom_teacher', 'student')).toEqual(
      expect.arrayContaining(['学生档案', '德育记录', '德育规则'])
    )
    expect(childLabelsFor('homeroom_teacher', 'exam')).toEqual(
      expect.arrayContaining(['考试管理', '人工阅卷', '班级报告'])
    )
    expect(childLabelsFor('homeroom_teacher', 'research')).toEqual(
      expect.arrayContaining(['作业跟进', '题库管理', '错题本'])
    )
    expect(routesFor('homeroom_teacher')).not.toContain('/grading/tasks')
  })

  it('academic director navigation is framed around teaching operation', () => {
    expect(groupLabelsFor('academic_director')).toEqual(['教学运行', '考试质量', '学生数据', '学校基础', '教研资源'])
    expect(childLabelsFor('academic_director', 'academic')).toEqual(
      expect.arrayContaining(['任课关系', '选科管理', '学期管理', '课程表'])
    )
    expect(childLabelsFor('academic_director', 'exam')).toEqual(
      expect.arrayContaining(['考试管理', '成绩导入', '阅卷流程', '数据报告'])
    )
    expect(routesFor('academic_director')).not.toContain('/marking')
  })

  it('grade leader navigation is framed around grade coordination', () => {
    expect(groupLabelsFor('grade_leader')).toEqual(['年级学生', '年级考试', '年级协同'])
    expect(childLabelsFor('grade_leader', 'student')).toEqual(
      expect.arrayContaining(['重点学生', '德育协同'])
    )
    expect(childLabelsFor('grade_leader', 'exam')).toEqual(
      expect.arrayContaining(['考试管理', '数据报告'])
    )
    expect(childLabelsFor('grade_leader', 'school')).toEqual(
      expect.arrayContaining(['联考复盘', '年级校历'])
    )
    expect(routesFor('grade_leader')).not.toContain('/grading/tasks')
    expect(routesFor('grade_leader')).not.toContain('/teachers')
  })

  it('teaching research leader navigation is framed around teaching research quality', () => {
    expect(groupLabelsFor('teaching_research_leader')).toEqual(['教研资源', '质量证据'])
    expect(childLabelsFor('teaching_research_leader', 'research')).toEqual(
      expect.arrayContaining(['知识图谱', '题库建设', '作业观察'])
    )
    expect(childLabelsFor('teaching_research_leader', 'exam')).toEqual(
      expect.arrayContaining(['考试证据', '学科趋势', '质量报告'])
    )
  })

  it('subject teacher sees personal teaching flow and no dispatch entry', () => {
    const routes = routesFor('subject_teacher')
    expect(routes).toContain('/exams')
    expect(routes).toContain('/marking')
    expect(routes).toContain('/analytics/report')
    expect(routes).toContain('/homework')
    expect(routes).not.toContain('/grading/tasks')
    expect(routes).not.toContain('/school-settings')
  })
})


describe('role-aware sidebar route access alignment', () => {
  it('follows central route access requirements for teacher and research entries', () => {
    const withoutResearch = ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'conduct']
    const academicRoutes = getSidebarItems('academic_director', fullModules).map(item => item.route)
    const hiddenResearchRoutes = getSidebarItems('academic_director', withoutResearch).map(item => item.route)

    expect(academicRoutes).toContain('/teachers')
    expect(academicRoutes).toContain('/question-bank')
    expect(hiddenResearchRoutes).not.toContain('/question-bank')
    expect(hiddenResearchRoutes).not.toContain('/knowledge-tree')
  })
})

describe('role-aware sidebar module gating', () => {
  it('hides research navigation when the research module is disabled', () => {
    const routes = getSidebarItems('subject_teacher', ['exam', 'grading', 'homework', 'study_analytics']).map(item => item.route)
    expect(routes).not.toContain('/question-bank')
    expect(routes).not.toContain('/knowledge-tree')
    expect(routes).not.toContain('/error-book')
  })

  // Phase 0.7D：academic 入口接 teaching 门控。teaching 默认未开启 → 有 manage_scheduling 的 academic_director
  // 在 teaching 关闭时也看不到学期管理/课程表/教学计划（fail-closed），与 authGuard 直达拦截 + 后端 403 双面对齐。
  it('hides academic teaching entries when the teaching module is disabled (0.7D fail-closed)', () => {
    const withoutTeaching = ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'research', 'conduct']
    const routes = getSidebarItems('academic_director', withoutTeaching).map(item => item.route)
    expect(routes).not.toContain('/academic/semesters')
    expect(routes).not.toContain('/academic/timetable')
    expect(routes).not.toContain('/academic/teaching-plans')
    // 同 academic 组的 permission-only 项（无 moduleCode）不受 teaching 门控影响，仍可见
    expect(routes).toContain('/assignments')
    expect(routes).toContain('/selections')
  })

  it('shows academic teaching entries when the teaching module is enabled', () => {
    const withTeaching = ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'research', 'conduct', 'teaching']
    const routes = getSidebarItems('academic_director', withTeaching).map(item => item.route)
    expect(routes).toContain('/academic/semesters')
    expect(routes).toContain('/academic/timetable')
    expect(routes).toContain('/academic/teaching-plans')
  })
})
