import { describe, it, expect } from 'vitest'
import { CANONICAL_ROLES, normalizeRole, SCHOOL_ADMIN_ROLES } from '../config/roles.js'
import { hasPermission, ROLE_PERMISSIONS } from '../config/permissions.js'
import { getSidebarItems } from '../config/sidebarConfig.js'
import { getRoleDashboardKpis, getRoleEntryPolicy } from '../config/roleEntryMatrix.js'

describe('roles config', () => {
  it('has 11 canonical roles', () => {
    expect(CANONICAL_ROLES).toHaveLength(11)
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
    expect(items.length).toBeLessThanOrEqual(12)
  })
})

describe('role entry dashboard config', () => {
  it('returns dashboard kpis for every canonical role', () => {
    for (const role of CANONICAL_ROLES) {
      const kpis = getRoleDashboardKpis(role)
      expect(Array.isArray(kpis), `${role} should have dashboard kpis`).toBe(true)
    }
  })

  it('keeps principal dashboard separate from school admin operations', () => {
    const principalRoutes = getRoleEntryPolicy('principal').primaryRoutes
    const adminRoutes = getRoleEntryPolicy('platform_admin').primaryRoutes

    expect(principalRoutes).toContain('/analytics/report')
    expect(principalRoutes).not.toContain('/school-settings')
    expect(adminRoutes).toContain('/school-settings')
  })

  it('different roles have different kpi labels', () => {
    const labelSets = new Set()
    for (const role of CANONICAL_ROLES) {
      const labels = getRoleDashboardKpis(role).map(kpi => kpi.label).join('|')
      labelSets.add(labels)
    }
    expect(labelSets.size).toBeGreaterThanOrEqual(4)
  })

  it('each kpi has required fields', () => {
    for (const role of CANONICAL_ROLES) {
      for (const kpi of getRoleDashboardKpis(role)) {
        expect(kpi.id, `${role} kpi missing id`).toBeTruthy()
        expect(kpi.label, `${role} kpi missing label`).toBeTruthy()
        expect(kpi.color, `${role} kpi missing color`).toBeTruthy()
      }
    }
  })
})
