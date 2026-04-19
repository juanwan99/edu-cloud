/**
 * sidebarConfig conduct 挂载契约测试
 *
 * 2026-04-13：R3 收尾发现 principal/platform_admin/district_admin 三个管理角色
 * 没挂 CONDUCT_ITEMS_*，即使 school_modules.conduct.enabled=True
 * 侧栏也不会渲染任何德育项（王建国事故）。
 *
 * 本测试锁定挂载契约，未来任何角色的 conduct 入口丢失都会立即失败。
 */
import { describe, it, expect } from 'vitest'
import { getSidebarItems } from '../config/sidebarConfig.js'
import { ROLE_PERMISSIONS } from '../config/permissions.js'

const HAS_VIEW_CONDUCT = (role) =>
  (ROLE_PERMISSIONS[role] || []).includes('view_conduct')

const CONDUCT_ROUTE_PREFIX = '/conduct'

describe('sidebarConfig conduct 挂载契约', () => {
  it.each([
    ['platform_admin', 9, 'FULL'],
    ['district_admin', 9, 'FULL'],
    ['homeroom_teacher', 9, 'FULL'],
    ['principal', 3, 'VIEWER (view + export only)'],
    ['academic_director', 3, 'VIEWER'],
    ['grade_leader', 3, 'VIEWER'],
    ['subject_teacher', 2, 'TEACHER'],
  ])('%s sidebar 含 %d 个 conduct 入口（%s）', (role, expectedCount) => {
    const items = getSidebarItems(role)
    const conductItems = items.filter(i => i.route?.startsWith(CONDUCT_ROUTE_PREFIX))
    expect(conductItems.length).toBe(expectedCount)
    // 所有 conduct 项必须标 moduleCode='conduct'，否则模块过滤失效
    for (const it of conductItems) {
      expect(it.moduleCode).toBe('conduct')
    }
  })

  it('有 conduct sidebar 入口的角色必须有 view_conduct 权限（防点击 403）', () => {
    // 单向契约：入口 → 权限（真 bug 防护）
    // 反向（权限 → 入口）是产品决策，不强制，见 lesson_prep_leader
    for (const role of Object.keys(ROLE_PERMISSIONS)) {
      const items = getSidebarItems(role)
      const hasConductItem = items.some(i => i.route?.startsWith(CONDUCT_ROUTE_PREFIX))
      if (hasConductItem) {
        expect(
          HAS_VIEW_CONDUCT(role),
          `${role} sidebar 有 conduct 入口但 permissions.js 缺 view_conduct — 点击会 403`,
        ).toBe(true)
      }
    }
  })
})
