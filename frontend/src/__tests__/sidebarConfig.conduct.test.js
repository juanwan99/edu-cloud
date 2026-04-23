/**
 * sidebarConfig conduct 挂载契约测试
 *
 * 2026-04-18：系统进入冻结模式，conduct 全部冻结。
 * 原始测试备份在 _frozen/sidebarConfig.conduct.test.js.bak，解冻时恢复。
 */
import { describe, it, expect } from 'vitest'
import { getSidebarItems } from '../config/sidebarConfig.js'

const CONDUCT_ROUTE_PREFIX = '/conduct'

describe('sidebarConfig conduct 冻结契约', () => {
  it.each([
    'platform_admin',
    'district_admin',
    'homeroom_teacher',
    'principal',
    'academic_director',
    'grade_leader',
    'subject_teacher',
  ])('%s sidebar 冻结模式下无 conduct 入口', (role) => {
    const items = getSidebarItems(role)
    const conductItems = items.filter(i => i.route?.startsWith(CONDUCT_ROUTE_PREFIX))
    expect(conductItems.length).toBe(0)
  })

  it('冻结模式下所有角色只有考试+阅卷相关入口', () => {
    const allowedPrefixes = ['/', '/exams', '/grading', '/marking', '/card-dev']
    for (const role of ['platform_admin', 'academic_director', 'subject_teacher']) {
      const items = getSidebarItems(role)
      for (const item of items) {
        const matched = allowedPrefixes.some(p => item.route === p || item.route.startsWith(p))
        expect(matched, `${role} 侧栏项 ${item.route} 不在允许范围`).toBe(true)
      }
    }
  })
})
