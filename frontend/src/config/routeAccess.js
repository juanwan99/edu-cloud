import { hasPermission } from './permissions.js'
import { normalizeRole } from './roles.js'
import { OVERVIEW_NAV_ITEM, getRoleHeaderNav } from './roleEntryMatrix.js'

export const ROUTE_ACCESS_REQUIREMENTS = {
  '/exams': { permission: 'view_exams', moduleCode: 'exam' },
  '/exam-import': { permission: 'import_exams', moduleCode: 'exam' },
  '/marking': { permission: 'view_grading', moduleCode: 'grading' },
  '/grading/tasks': { permission: 'manage_grading', moduleCode: 'grading' },
  '/ai-grading': { permission: 'manage_grading', moduleCode: 'grading' },
  '/analytics/report': { permission: 'view_scores', moduleCode: 'study_analytics' },
  '/analytics/ai-report': { permission: 'view_scores', moduleCode: 'study_analytics' },
  '/homework': { permission: ['view_homework', 'manage_homework'], moduleCode: 'homework' },
  '/question-bank': { permission: 'view_question_bank', moduleCode: 'research' },
  '/knowledge-tree': { permission: 'view_knowledge_tree', moduleCode: 'research' },
  '/error-book': { permission: 'view_scores', moduleCode: 'research' },
  '/students': { permission: ['view_students', 'manage_scheduling'] },
  '/conduct': { permission: 'view_conduct', moduleCode: 'conduct' },
  '/conduct/settings': { permission: 'manage_conduct_rules', moduleCode: 'conduct' },
  '/joint-exams': { permission: 'view_joint_exam' },
  '/school-settings': { permission: 'manage_school_config' },
  '/academic/teaching-plans': { permission: 'manage_scheduling' },
  '/academic/timetable': { permission: 'manage_scheduling' },
  '/academic/semesters': { permission: 'manage_scheduling' },
  '/assignments': { permission: 'manage_scheduling' },
  '/selections': { permission: 'manage_scheduling' },
  '/teachers': { permission: 'manage_teachers' },
  '/schools': { permission: 'manage_schools' },
  '/admin/impersonate': { permission: 'impersonate_roles' },
  '/calendar': { moduleCode: 'calendar' },
}

export function getRouteAccessRequirement(route) {
  return ROUTE_ACCESS_REQUIREMENTS[route] || null
}

export function permissionMatches(role, permission) {
  if (!permission) return true
  const normalized = normalizeRole(role)
  const required = Array.isArray(permission) ? permission : [permission]
  return required.some(perm => hasPermission(normalized, perm))
}

// ── 模块门控上下文（Phase 0.7A · R5 F-001 MED security_design）─────────────────
// 历史缺陷：空数组 `[]` 同时表达「未加载 / 加载失败 / 学校无模块 / admin 豁免」四态，
// 各前端 surface 把空数组当「不过滤」放行 → 模块接口失败或无模块时，被禁用模块入口仍对
// 学校用户可见（视觉 fail-open）。修复：用显式门控上下文区分豁免与 fail-closed，并与
// authGuard（router/index.js:187-188）的直达 URL 拦截语义严格对齐——
//   允许 IFF  exempt(无 school_id, admin/平台 → 豁免)  OR  (modulesLoaded && enabledModules.includes(code))
// 即学校用户在「未加载 / 加载失败 / 空列表」时一律 fail-closed 隐藏模块入口。
export function createModuleGate({ schoolScoped = false, modulesLoaded = false, enabledModules = [] } = {}) {
  return {
    exempt: !schoolScoped,
    modulesLoaded: !!modulesLoaded,
    enabledModules: Array.isArray(enabledModules) ? enabledModules : [],
  }
}

// surface 统一入口：从 auth store 派生门控上下文。school 维度对齐 authGuard 的 !!currentRole?.school_id
//（不是 isAdmin —— principal/校管等有 school_id 的角色仍受学校模块限制）。
export function moduleGateFromAuth(auth) {
  return createModuleGate({
    schoolScoped: !!auth?.currentRole?.school_id,
    modulesLoaded: !!auth?.modulesLoaded,
    enabledModules: auth?.enabledModules,
  })
}

// 归一「门控上下文 | 旧版 enabledModules 数组」。门控上下文（surface 传入）按显式字段判定；
// 旧版数组（历史调用点/单测）= 学校用户、已加载、这些模块 → 走 fail-closed 成员判定，
// 空数组即「学校无模块」一律隐藏。admin 豁免必须经 createModuleGate 显式声明
// schoolScoped:false，不能再用空数组隐式表达。
function normalizeGate(gate) {
  if (gate && typeof gate === 'object' && !Array.isArray(gate) && 'exempt' in gate) {
    return {
      exempt: !!gate.exempt,
      modulesLoaded: !!gate.modulesLoaded,
      enabledModules: Array.isArray(gate.enabledModules) ? gate.enabledModules : [],
    }
  }
  return { exempt: false, modulesLoaded: true, enabledModules: Array.isArray(gate) ? gate : [] }
}

export function moduleMatches(moduleCode, gate) {
  if (!moduleCode) return true
  const g = normalizeGate(gate)
  if (g.exempt) return true
  return g.modulesLoaded && g.enabledModules.includes(moduleCode)
}

export function canAccessRequirementForRole(role, requirement, gate) {
  if (!requirement) return true
  return permissionMatches(role, requirement.permission) && moduleMatches(requirement.moduleCode, gate)
}

export function canAccessRouteForRole(role, route, gate) {
  return canAccessRequirementForRole(role, getRouteAccessRequirement(route), gate)
}

// 综合「当前已匹配路由」可达性判定（供 RoleSwitcher 等对**当前路由**判定可达性的 surface）。
// 与 authGuard(router/index.js) 同源覆盖静态精确表 ∪ 动态 route.meta：
//   权限 = 精确表 requirement.permission（permissionMatches）∧ route.meta.permissions（OR-any 命中其一）
//   模块 = 精确表 requirement.moduleCode ∪ route.meta.moduleCode，走门控上下文 fail-closed
// 动态子路由（/exams/:id、/exams/:examId/ai-grading/:subjectId 等）getRouteAccessRequirement 精确 key
// 匹配不到 → 权限与模块均靠 meta 兜底，堵 RoleSwitcher 切换路径上的 perm/module fail-open（R6/R7 F-001）。
export function canAccessMatchedRoute(role, path, meta, gate) {
  const requirement = getRouteAccessRequirement(path)
  const tablePermOk = permissionMatches(role, requirement?.permission)
  const metaPerms = meta?.permissions
  const metaPermOk = Array.isArray(metaPerms) && metaPerms.length
    ? metaPerms.some(perm => hasPermission(normalizeRole(role), perm))
    : true
  const moduleCode = requirement?.moduleCode || meta?.moduleCode
  return tablePermOk && metaPermOk && moduleMatches(moduleCode, gate)
}


export function getHeaderNavItems(role, gate) {
  const normalized = normalizeRole(role)
  const configuredItems = getRoleHeaderNav(normalized)
  const visibleItems = configuredItems.filter(item => canAccessRouteForRole(normalized, item.route, gate))
  return [OVERVIEW_NAV_ITEM, ...visibleItems]
}
