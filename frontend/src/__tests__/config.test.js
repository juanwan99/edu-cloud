import { describe, it, expect } from 'vitest'
import { CANONICAL_ROLES, ROLE_LABELS, normalizeRole, SCHOOL_ADMIN_ROLES } from '../config/roles.js'
import { hasPermission, ROLE_PERMISSIONS } from '../config/permissions.js'
import { getSidebarItems } from '../config/sidebarConfig.js'
import { getDashboardConfig } from '../config/dashboardConfig.js'

describe('roles config', () => {
  it('has 10 canonical roles', () => {
    expect(CANONICAL_ROLES).toHaveLength(10)
  })
  it('normalizes legacy aliases', () => {
    expect(normalizeRole('admin')).toBe('platform_admin')
    expect(normalizeRole('teacher')).toBe('subject_teacher')
    expect(normalizeRole('head_teacher')).toBe('homeroom_teacher')
    expect(normalizeRole('principal')).toBe('principal')
  })
  it('SCHOOL_ADMIN_ROLES includes platform_admin and principal', () => {
    expect(SCHOOL_ADMIN_ROLES).toContain('platform_admin')
    expect(SCHOOL_ADMIN_ROLES).toContain('principal')
    expect(SCHOOL_ADMIN_ROLES).not.toContain('parent')
  })
})

describe('permissions config', () => {
  it('hasPermission checks role→permission mapping', () => {
    expect(hasPermission('platform_admin', 'manage_schools')).toBe(true)
    expect(hasPermission('parent', 'manage_schools')).toBe(false)
    expect(hasPermission('subject_teacher', 'use_ai_chat')).toBe(true)
    expect(hasPermission('parent', 'use_ai_chat')).toBe(true)
  })
  it('uses lowercase values matching backend enum', () => {
    for (const perms of Object.values(ROLE_PERMISSIONS)) {
      for (const p of perms) {
        expect(p).toBe(p.toLowerCase())
      }
    }
  })
})

describe('sidebar config', () => {
  it('returns items for every canonical role', () => {
    for (const role of CANONICAL_ROLES) {
      const items = getSidebarItems(role)
      expect(items.length, `${role} should have sidebar items`).toBeGreaterThan(0)
    }
  })
  it('parent has minimal items', () => {
    const items = getSidebarItems('parent')
    expect(items.length).toBeLessThanOrEqual(3)
  })
})

describe('dashboard config', () => {
  it('returns config for every canonical role', () => {
    for (const role of CANONICAL_ROLES) {
      const config = getDashboardConfig(role)
      expect(config, `${role} should have dashboard config`).toBeTruthy()
      expect(config.kpis?.length).toBeGreaterThan(0)
    }
  })

  it('different roles have different titles', () => {
    const titles = new Set()
    for (const role of CANONICAL_ROLES) {
      const config = getDashboardConfig(role)
      if (config.title) titles.add(config.title)
    }
    // At least 4 distinct titles (admin/school/teacher/parent have different views)
    expect(titles.size).toBeGreaterThanOrEqual(4)
  })

  it('platform_admin has schools widget, parent does not', () => {
    const admin = getDashboardConfig('platform_admin')
    const parent = getDashboardConfig('parent')
    expect(admin.widgets.some(w => w.id === 'schools')).toBe(true)
    expect(parent.widgets?.some(w => w.id === 'schools') ?? false).toBe(false)
  })

  it('each kpi has required fields', () => {
    for (const role of CANONICAL_ROLES) {
      const config = getDashboardConfig(role)
      for (const kpi of config.kpis) {
        expect(kpi.id, `${role} kpi missing id`).toBeTruthy()
        expect(kpi.label, `${role} kpi missing label`).toBeTruthy()
        expect(kpi.color, `${role} kpi missing color`).toBeTruthy()
      }
    }
  })
})
