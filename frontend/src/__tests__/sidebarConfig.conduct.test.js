/**
 * sidebarConfig conduct T3 permission-based sidebar tests
 *
 * Replaces frozen-mode tests (2026-04-18).
 * CONDUCT_ITEMS + filterConductByRole now derive sidebar entries from permissions.js.
 */
import { describe, it, expect } from 'vitest'
import { getSidebarItems, SIDEBAR_GROUPS } from '../config/sidebarConfig.js'
import { ROLE_PERMISSIONS } from '../config/permissions.js'

const CONDUCT_ROUTE_PREFIX = '/conduct'

describe('T3 — sidebar 按 permissions 派生（conduct 矩阵）', () => {
  const getConductItems = (role) => {
    const items = getSidebarItems(role)
    return items.filter(it => it.moduleCode === 'conduct').map(it => it.route)
  }

  it('platform_admin 看到 9 项 conduct', () => {
    expect(getConductItems('platform_admin')).toHaveLength(9)
  })

  it('academic_director 看到 8 项', () => {
    const routes = getConductItems('academic_director')
    expect(routes).toHaveLength(8)
  })

  it('grade_leader 看到 6 项', () => {
    expect(getConductItems('grade_leader')).toHaveLength(6)
  })

  it('lesson_prep_leader 无 conduct 入口', () => {
    expect(getConductItems('lesson_prep_leader')).toHaveLength(0)
  })

  it('principal 4 项', () => {
    expect(getConductItems('principal')).toHaveLength(4)
  })

  it('homeroom_teacher 9 项', () => {
    expect(getConductItems('homeroom_teacher')).toHaveLength(9)
  })

  it('subject_teacher 5 项', () => {
    expect(getConductItems('subject_teacher')).toHaveLength(5)
  })

  it('teaching_research_leader 0 项', () => {
    expect(getConductItems('teaching_research_leader')).toHaveLength(0)
  })

  it('parent 3 项', () => {
    expect(getConductItems('parent')).toHaveLength(3)
  })

  it('district_admin 看到 9 项 conduct', () => {
    expect(getConductItems('district_admin')).toHaveLength(9)
  })
})

describe('T3 (R1-F007) — conduct items perm 合法性治理', () => {
  it('每个 perm 字段都在合法 permission 集', () => {
    const allPerms = new Set()
    for (const perms of Object.values(ROLE_PERMISSIONS)) {
      for (const p of perms) allPerms.add(p)
    }
    // Extract conduct items from SIDEBAR_GROUPS instead of non-existent CONDUCT_ITEMS export
    const studentGroup = SIDEBAR_GROUPS.find(g => g.key === 'student')
    const conductItems = studentGroup.children.filter(item => item.moduleCode === 'conduct')
    for (const item of conductItems) {
      expect(allPerms.has(item.perm), `perm "${item.perm}" for "${item.label}" not in ROLE_PERMISSIONS`).toBe(true)
    }
  })
})
