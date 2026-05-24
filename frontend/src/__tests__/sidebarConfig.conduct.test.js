/**
 * sidebarConfig conduct role-policy sidebar tests
 *
 * Post-restructure: 10 flat items → 2 entries (德育工作台 + 德育设置)
 */
import { describe, it, expect } from 'vitest'
import { getSidebarItems, SIDEBAR_GROUPS } from '../config/sidebarConfig.js'
import { ROLE_PERMISSIONS } from '../config/permissions.js'

describe('sidebar conduct 条目按角色权限派生', () => {
  const getConductItems = (role) => {
    const items = getSidebarItems(role)
    return items.filter(it => it.moduleCode === 'conduct').map(it => it.route)
  }

  it('platform_admin 看到 2 项 conduct', () => {
    expect(getConductItems('platform_admin')).toHaveLength(2)
  })

  it('district_admin 看到 2 项 conduct', () => {
    expect(getConductItems('district_admin')).toHaveLength(2)
  })

  it('academic_director 看到 2 项', () => {
    expect(getConductItems('academic_director')).toHaveLength(2)
  })

  it('homeroom_teacher 看到 2 项', () => {
    expect(getConductItems('homeroom_teacher')).toHaveLength(2)
  })

  it('principal 看到 1 项（仅工作台）', () => {
    const routes = getConductItems('principal')
    expect(routes).toHaveLength(1)
    expect(routes[0]).toBe('/conduct')
  })

  it('grade_leader 看到 1 项（仅工作台）', () => {
    expect(getConductItems('grade_leader')).toHaveLength(1)
  })

  it('subject_teacher 默认无 conduct 入口', () => {
    expect(getConductItems('subject_teacher')).toHaveLength(0)
  })

  it('parent 看到 1 项（仅工作台）', () => {
    expect(getConductItems('parent')).toHaveLength(1)
  })

  it('lesson_prep_leader 无 conduct 入口', () => {
    expect(getConductItems('lesson_prep_leader')).toHaveLength(0)
  })

  it('teaching_research_leader 无 conduct 入口', () => {
    expect(getConductItems('teaching_research_leader')).toHaveLength(0)
  })
})

describe('conduct items perm 合法性治理', () => {
  it('每个 perm 字段都在合法 permission 集', () => {
    const allPerms = new Set()
    for (const perms of Object.values(ROLE_PERMISSIONS)) {
      for (const p of perms) allPerms.add(p)
    }
    const studentGroup = SIDEBAR_GROUPS.find(g => g.key === 'student')
    const conductItems = studentGroup.children.filter(item => item.moduleCode === 'conduct')
    for (const item of conductItems) {
      expect(allPerms.has(item.perm), `perm "${item.perm}" for "${item.label}" not in ROLE_PERMISSIONS`).toBe(true)
    }
  })
})
