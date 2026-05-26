# Role Entry Full Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace scattered role navigation and dashboard logic with one role-entry model so each teacher or manager lands on a page that matches their active identity, while lower-frequency permitted functions remain available as secondary entries.

**Architecture:** Backend RBAC and data scope stay the security truth. Frontend role-entry policy becomes the presentation truth: it decides primary routes, secondary routes, hidden routes, dashboard priorities, action panels, and cross-identity summaries for the active role. Existing files are replaced in place; no `v2`, no parallel dashboard, no duplicate route maps.

**Tech Stack:** Vue 3, Pinia, Vue Router, Naive UI, existing `auth.currentRoleIndex`, existing `UserRole` scope fields, FastAPI permission helpers, Vitest, Vite build.

---

## Current Baseline

- Branch: `codex/role-permission-phase2`
- Current deployed HEAD before this plan: `d9b1c56`
- Truthline: source, frontend build, nginx, and backend are aligned on `d9b1c56`.
- Dirty state before planning: clean.
- Frontend role-entry targeted suite has one existing stale assertion:
  `frontend/src/__tests__/AppHeader.test.js` still expects `教师管理/考试流程`, while current product copy is `教师与职务/数据导入`.
- Guardian is red for schema health, unrelated to the frontend role-entry change:
  `exam_import_sessions` exists in ORM but not DB; `_audit_log` exists in DB but not ORM.

## Product Rules

1. 权限只回答“能不能访问”，入口层回答“当前身份默认该不该展示”。
2. 一级入口只放紧急、重要、常用、符合岗位主线的动作。
3. 二级入口承载权限内但低频的功能，不能消失，也不能抢主线。
4. 多身份不合并成超级首页；当前激活身份决定页面和菜单。
5. 跨身份事项只做摘要和带上下文切换，不在当前身份页展开另一个岗位的完整功能。
6. 校管理员是系统管理员，主线是账号、职务、组织关系、模块配置、导入和数据健康。
7. 校长主线是总览、风险、审批和复盘；可看明细但明细不是一级入口。
8. 年级组长、班主任、校长可看全科和学生明细；不需要额外审批。
9. 备课组长需要本学科考试、答题卡、阅卷分配、阅卷控制。
10. 教研组长对知识图谱应有控制入口。

## Target Role Matrix

| Role | Primary entry model | Secondary entry model | Hidden from primary |
| --- | --- | --- | --- |
| `school_admin` | 学校配置、教师与职务、组织关系、数据导入、数据健康 | 考试流程、阅卷流程、学生数据核查 | 校长审批、个人阅卷、单学科教研、班主任日常 |
| `principal` | 质量总览、考试结果、审批查看、年级德育、联考复盘 | 学生明细、阅卷风险、校历事件 | 账号运维、任课关系维护、个人阅卷、单学科资源 |
| `academic_director` | 教学运行、考试组织、阅卷风险、质量报告 | 教师/学生/选科/校历配置 | 个人阅卷明细、班主任日常 |
| `grade_leader` | 年级质量、班级差异、重点学生、德育协同 | 年级考试、联考复盘、作业跟进 | 单题阅卷、单学科题库建设、学校配置 |
| `homeroom_teacher` | 班级学生、德育记录、班级报告、作业跟进 | 相关考试、个人阅卷、题库/错题 | 全校配置、阅卷调度、排课 |
| `lesson_prep_leader` | 学科考试、答题卡、阅卷分工、阅卷控制、学科报告 | 题库、知识图谱、作业巩固、错题 | 德育、全校人员配置、排课 |
| `teaching_research_leader` | 知识图谱、题库建设、学科趋势、质量证据 | 相关考试、质量报告、教学计划 | 班级德育、阅卷分配、学校配置 |
| `subject_teacher` | 相关考试、我的阅卷、成绩分析、作业管理 | 题库、知识图谱、错题本 | 阅卷调度、学校配置、学生管理、德育管理 |

---

## File Structure

### Create

- `frontend/src/config/roleEntryMatrix.js`
  - Single source for primary routes, secondary groups, hidden routes, header nav, dashboard KPI ids, and role action panels.
- `frontend/src/__tests__/roleEntryMatrix.test.js`
  - Matrix coverage, route validity, no duplicate role policy drift, and primary/secondary separation.
- `frontend/src/composables/useRoleWorkbenchData.js`
  - Frontend-only adapter over existing APIs: `/dashboard/summary`, `/exams`, `/marking/my-assignments`, and conduct/homework summaries where available.
- `frontend/src/composables/__tests__/useRoleWorkbenchData.test.js`
  - Verifies the adapter does not call unavailable endpoints and returns stable empty states.

### Modify

- `frontend/src/config/workbenchProfiles.js`
  - Keep role copy and flow language; remove route policy duplication when route order moves to `roleEntryMatrix.js`.
- `frontend/src/config/routeAccess.js`
  - Keep permission/module requirements; replace `HEADER_NAV_BY_ROLE` with matrix-derived header nav.
- `frontend/src/config/sidebarConfig.js`
  - Replace `ROLE_SIDEBAR_POLICY` and label constants with matrix-derived groups and labels.
- `frontend/src/config/dashboardConfig.js`
  - Remove role-specific widget duplication; either shrink to generic KPI metadata or delete after `DashboardPage.vue` imports the matrix.
- `frontend/src/config/roleWorkbenches.js`
  - Delete after panel builders move into `roleEntryMatrix.js`.
- `frontend/src/pages/DashboardPage.vue`
  - Render one role-aware dashboard structure; remove duplicate generic widgets and entry cards that compete with the role workbench.
- `frontend/src/components/shell/AppHeader.vue`
  - Consume matrix-derived header nav through `routeAccess.js`.
- `frontend/src/components/shell/AppSidebar.vue`
  - Keep layout; verify group expansion with matrix-derived groups.
- `frontend/src/components/shell/RoleSwitcher.vue`
  - Make active identity switching explicit and route-safe; show current, primary, and other roles clearly.
- `frontend/src/stores/auth.js`
  - Add role switching helpers by role key and role id, keeping `switchRole(index)` as the single execution path.
- `frontend/src/router/index.js`
  - Align route guard metadata with `ROUTE_ACCESS_REQUIREMENTS`; stop maintaining separate route-role lists where permission keys already exist.
- `frontend/src/__tests__/AppHeader.test.js`
  - Update stale school-admin copy assertions.
- `frontend/src/__tests__/DashboardPage.test.js`
  - Assert role-specific first screen does not expose hidden primary actions.
- `frontend/src/__tests__/routeAccess.test.js`
  - Add coverage for matrix-derived header nav and route guard consistency.
- `frontend/src/__tests__/sidebarConfig.rolePolicy.test.js`
  - Move policy assertions to the matrix and verify sidebar uses the same source.
- `frontend/src/__tests__/RoleSwitcher.test.js`
  - Add role-key switching and route reset tests.
- `frontend/src/__tests__/auth-store.test.js`
  - Add `switchRoleByKey()` and failed switch rollback tests.
- `src/edu_cloud/api/permissions.py`
  - Fix `get_visible_subject_codes()` so `grade_leader` is all-subject within grade scope.
- `tests/**`
  - Add the smallest backend test that proves grade leader subject visibility is `None`.
- `docs/context/NOW.md`
  - Refresh current facts and note the schema drift that is outside the frontend role-entry batch.

### Delete

- `frontend/src/config/roleWorkbenches.js`
  - Delete only after `buildRoleActionPanel()` callers are migrated to `roleEntryMatrix.js`.
- `frontend/src/config/dashboardConfig.js`
  - Delete if no remaining imports after dashboard migration. If generic KPI metadata is still useful, keep a smaller file with no role policy.

---

## Task 0: Checkpoint and Baseline Repair

**Files:**
- Modify: `frontend/src/__tests__/AppHeader.test.js`
- Modify: `docs/context/NOW.md`

- [ ] **Step 1: Create checkpoint tag**

Run:

```bash
cd /home/ops/projects/edu-cloud
git tag checkpoint-2026-05-26-role-entry-full-optimization -m "stable before: full role-entry optimization"
```

Expected: tag exists and `git status --short` is empty.

- [ ] **Step 2: Update stale AppHeader test**

In `frontend/src/__tests__/AppHeader.test.js`, change the school-admin assertions from:

```js
expect(text).toContain('教师管理')
expect(text).toContain('考试流程')
```

to:

```js
expect(text).toContain('教师与职务')
expect(text).toContain('数据导入')
```

Keep the negative assertions that school admin should not see `我的阅卷` or `作业管理` as primary header entries.

- [ ] **Step 3: Verify header baseline**

Run:

```bash
cd /home/ops/projects/edu-cloud
npm --prefix frontend test -- --run src/__tests__/AppHeader.test.js
```

Expected: `2 passed`.

- [ ] **Step 4: Refresh NOW facts**

Update `docs/context/NOW.md` with:

```markdown
Last refreshed: 2026-05-26 23:16 Asia/Shanghai

## Current Facts

- Branch: `codex/role-permission-phase2`
- Production URL: `https://mcu.asia`
- Current live hash: `d9b1c56`
- Truthline: source, frontend build, nginx, and backend are aligned on `d9b1c56`.
- Known frontend full-suite issue: 3 historical static assertion failures in marking/review tests.
- Guardian schema health is red: `exam_import_sessions` missing in DB, `_audit_log` orphan table.
```

Do not remove artifact warnings from NOW; keep the warning that `.db`/WAL/SHM files are runtime state.

- [ ] **Step 5: Commit baseline repair**

Run:

```bash
cd /home/ops/projects/edu-cloud
git add frontend/src/__tests__/AppHeader.test.js docs/context/NOW.md
git commit -m "test: align role header baseline with focused entries"
```

---

## Task 1: Replace Scattered Role Entry Policy with One Matrix

**Files:**
- Create: `frontend/src/config/roleEntryMatrix.js`
- Create: `frontend/src/__tests__/roleEntryMatrix.test.js`
- Modify: `frontend/src/config/routeAccess.js`
- Modify: `frontend/src/config/sidebarConfig.js`
- Modify: `frontend/src/__tests__/routeAccess.test.js`
- Modify: `frontend/src/__tests__/sidebarConfig.rolePolicy.test.js`

- [ ] **Step 1: Add failing matrix tests**

Create `frontend/src/__tests__/roleEntryMatrix.test.js`:

```js
import { describe, expect, it } from 'vitest'
import { WORKBENCH_PROFILE_KEYS } from '../config/workbenchProfiles.js'
import {
  ROLE_ENTRY_MATRIX,
  getRoleEntryPolicy,
  getRoleHeaderNav,
  getRoleSidebarPolicy,
} from '../config/roleEntryMatrix.js'
import { getRouteAccessRequirement } from '../config/routeAccess.js'

describe('role entry matrix', () => {
  it('covers every workbench profile role', () => {
    for (const role of WORKBENCH_PROFILE_KEYS) {
      expect(ROLE_ENTRY_MATRIX[role], role).toBeTruthy()
    }
  })

  it('keeps principal separate from school admin', () => {
    expect(getRoleEntryPolicy('principal').primaryRoutes).toContain('/analytics/report')
    expect(getRoleEntryPolicy('principal').hiddenRoutes).toContain('/school-settings')
    expect(getRoleEntryPolicy('school_admin').primaryRoutes).toContain('/school-settings')
  })

  it('keeps subject teacher away from grading dispatch primary entries', () => {
    const policy = getRoleEntryPolicy('subject_teacher')
    expect(policy.primaryRoutes).toContain('/marking')
    expect(policy.primaryRoutes).not.toContain('/grading/tasks')
    expect(policy.hiddenRoutes).toContain('/grading/tasks')
  })

  it('keeps lesson prep leader in subject exam and grading control flow', () => {
    const policy = getRoleEntryPolicy('lesson_prep_leader')
    expect(policy.primaryRoutes).toEqual([
      '/exams',
      '/grading/tasks',
      '/ai-grading',
      '/analytics/report',
    ])
  })

  it('only references known routes or explicitly unguarded overview routes', () => {
    for (const policy of Object.values(ROLE_ENTRY_MATRIX)) {
      for (const route of [...policy.primaryRoutes, ...policy.secondaryRoutes]) {
        expect(route === '/' || getRouteAccessRequirement(route), route).toBeTruthy()
      }
    }
  })

  it('derives header and sidebar policy from the same source', () => {
    expect(getRoleHeaderNav('school_admin').map(item => item.label)).toEqual([
      '学校配置',
      '教师与职务',
      '组织关系',
      '数据导入',
      '数据报告',
    ])
    expect(getRoleSidebarPolicy('principal').groups).toEqual(['exam', 'student', 'school'])
  })
})
```

Run:

```bash
cd /home/ops/projects/edu-cloud
npm --prefix frontend test -- --run src/__tests__/roleEntryMatrix.test.js
```

Expected: fail because `roleEntryMatrix.js` does not exist.

- [ ] **Step 2: Create the matrix**

Create `frontend/src/config/roleEntryMatrix.js` with this first implementation:

```js
import { normalizeRole } from './roles.js'

const OVERVIEW = { label: '概览', route: '/', exact: true }

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
      groupLabels: { school: '学校基础', academic: '人员组织', exam: '数据与流程', student: '学生数据' },
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
      groupLabels: { exam: '质量治理', student: '学生与德育', school: '协同复盘' },
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
    secondaryRoutes: ['/academic/timetable', '/academic/semesters', '/exam-import', '/students', '/teachers', '/calendar', '/question-bank', '/knowledge-tree'],
    hiddenRoutes: ['/marking', '/error-book'],
    header: [
      { label: '教学运行', route: '/assignments', match: '/assignments' },
      { label: '考试管理', route: '/exams', match: '/exams' },
      { label: '阅卷调度', route: '/grading/tasks', match: '/grading' },
      { label: '数据报告', route: '/analytics/report', match: '/analytics' },
    ],
    sidebar: {
      groups: ['academic', 'exam', 'student', 'school', 'research'],
      groupLabels: { academic: '教学运行', exam: '考试质量', student: '学生数据', school: '学校基础', research: '教研资源' },
      routeLabels: {},
    },
  },
  grade_leader: {
    primaryRoutes: ['/students', '/analytics/report', '/conduct', '/joint-exams'],
    secondaryRoutes: ['/exams', '/analytics/ai-report', '/calendar', '/homework'],
    hiddenRoutes: ['/marking', '/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/question-bank', '/knowledge-tree'],
    header: [
      { label: '年级学生', route: '/students', match: '/students' },
      { label: '年级考试', route: '/exams', match: '/exams' },
      { label: '数据报告', route: '/analytics/report', match: '/analytics' },
      { label: '德育协同', route: '/conduct', match: '/conduct' },
    ],
    sidebar: {
      groups: ['student', 'exam', 'school'],
      groupLabels: { student: '年级学生', exam: '年级考试', school: '年级协同' },
      routeLabels: { '/students': '重点学生', '/conduct': '德育协同', '/exams': '考试管理', '/analytics/report': '数据报告', '/joint-exams': '联考复盘', '/calendar': '年级校历' },
    },
  },
  homeroom_teacher: {
    primaryRoutes: ['/students', '/conduct', '/analytics/report', '/homework'],
    secondaryRoutes: ['/exams', '/marking', '/analytics/ai-report', '/question-bank', '/knowledge-tree', '/error-book'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/academic/timetable', '/academic/semesters'],
    header: [
      { label: '班级学生', route: '/students', match: '/students' },
      { label: '德育记录', route: '/conduct', match: '/conduct' },
      { label: '班级报告', route: '/analytics/report', match: '/analytics' },
      { label: '作业跟进', route: '/homework', match: '/homework' },
    ],
    sidebar: {
      groups: ['student', 'exam', 'research'],
      groupLabels: { student: '班级学生', exam: '班级考试', research: '教学巩固' },
      routeLabels: { '/students': '学生档案', '/conduct': '德育记录', '/exams': '考试管理', '/marking': '人工阅卷', '/analytics/report': '班级报告', '/homework': '作业跟进' },
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
      groupLabels: { exam: '学科考试', research: '资源沉淀' },
      routeLabels: { '/exams': '学科考试', '/grading/tasks': '阅卷分工', '/ai-grading': '阅卷控制', '/analytics/report': '学科报告', '/question-bank': '题库沉淀', '/knowledge-tree': '知识图谱' },
    },
  },
  teaching_research_leader: {
    primaryRoutes: ['/knowledge-tree', '/question-bank', '/analytics/report', '/exams'],
    secondaryRoutes: ['/analytics/ai-report', '/homework', '/error-book', '/academic/teaching-plans'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/students', '/conduct'],
    header: [
      { label: '知识图谱', route: '/knowledge-tree', match: '/knowledge-tree' },
      { label: '题库建设', route: '/question-bank', match: '/question-bank' },
      { label: '学科趋势', route: '/analytics/report', match: '/analytics' },
      { label: '考试证据', route: '/exams', match: '/exams' },
    ],
    sidebar: {
      groups: ['research', 'exam'],
      groupLabels: { research: '教研资源', exam: '质量证据' },
      routeLabels: { '/knowledge-tree': '知识图谱', '/question-bank': '题库建设', '/analytics/report': '学科趋势', '/exams': '考试证据' },
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
    sidebar: { groups: ['exam', 'research'], groupLabels: {}, routeLabels: {} },
  },
}

const ALIASES = {
  platform_admin: 'school_admin',
  district_admin: 'school_admin',
}

export const DEFAULT_HEADER_NAV = ROLE_ENTRY_MATRIX.subject_teacher.header
export const OVERVIEW_NAV_ITEM = OVERVIEW

export function getRoleEntryPolicy(role) {
  const normalized = normalizeRole(role)
  const key = ROLE_ENTRY_MATRIX[normalized] ? normalized : ALIASES[normalized]
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
```

- [ ] **Step 3: Replace header policy in `routeAccess.js`**

Remove `SCHOOL_ADMIN_HEADER`, `PRINCIPAL_HEADER`, and `HEADER_NAV_BY_ROLE`.

Import:

```js
import { OVERVIEW_NAV_ITEM, getRoleHeaderNav } from './roleEntryMatrix.js'
```

Change `getHeaderNavItems()` to:

```js
export function getHeaderNavItems(role, enabledModules = []) {
  const configuredItems = getRoleHeaderNav(role)
  const visibleItems = configuredItems.filter(item => canAccessRouteForRole(role, item.route, enabledModules))
  return [OVERVIEW_NAV_ITEM, ...visibleItems]
}
```

- [ ] **Step 4: Replace sidebar policy in `sidebarConfig.js`**

Remove all `*_OPERATION_LABELS`, `ROLE_SIDEBAR_POLICY`, and `policyFor()`.

Import:

```js
import { getRoleSidebarPolicy } from './roleEntryMatrix.js'
```

Change `applyRolePolicy()` to:

```js
function applyRolePolicy(role, groups) {
  const policy = getRoleSidebarPolicy(role)
  if (!policy) return groups
  const groupRank = new Map(policy.groups.map((key, index) => [key, index]))
  const hiddenRoutes = new Set(policy.hiddenRoutes || [])
  const groupLabels = policy.labels?.groups || {}
  const routeLabels = policy.labels?.routes || {}
  return groups
    .filter(group => groupRank.has(group.key))
    .map(group => ({
      ...group,
      label: groupLabels[group.key] || group.label,
      children: group.children
        .filter(item => !hiddenRoutes.has(item.route))
        .map(item => ({ ...item, label: routeLabels[item.route] || item.label })),
    }))
    .filter(group => group.children.length > 0)
    .sort((a, b) => groupRank.get(a.key) - groupRank.get(b.key))
}
```

- [ ] **Step 5: Verify matrix replacement**

Run:

```bash
cd /home/ops/projects/edu-cloud
npm --prefix frontend test -- --run \
  src/__tests__/roleEntryMatrix.test.js \
  src/__tests__/routeAccess.test.js \
  src/__tests__/sidebarConfig.rolePolicy.test.js \
  src/__tests__/AppHeader.test.js \
  src/__tests__/AppSidebar.test.js
```

Expected: all listed tests pass.

- [ ] **Step 6: Commit matrix replacement**

Run:

```bash
git add frontend/src/config/roleEntryMatrix.js frontend/src/config/routeAccess.js frontend/src/config/sidebarConfig.js frontend/src/__tests__/roleEntryMatrix.test.js frontend/src/__tests__/routeAccess.test.js frontend/src/__tests__/sidebarConfig.rolePolicy.test.js frontend/src/__tests__/AppHeader.test.js frontend/src/__tests__/AppSidebar.test.js
git commit -m "replace: centralize role entry matrix"
```

---

## Task 2: Replace Dashboard Role Panels with the Same Matrix

**Files:**
- Modify: `frontend/src/config/roleEntryMatrix.js`
- Modify: `frontend/src/pages/DashboardPage.vue`
- Modify: `frontend/src/pages/__tests__/DashboardPage.test.js`
- Delete: `frontend/src/config/roleWorkbenches.js`
- Modify or delete: `frontend/src/config/dashboardConfig.js`
- Modify: `frontend/src/__tests__/roleWorkbenches.test.js`

- [ ] **Step 1: Add matrix panel builders**

Move `buildAdminPriorityActions()`, role panel builders, and `buildRoleActionPanel()` from `roleWorkbenches.js` into `roleEntryMatrix.js`.

While moving, fix the known principal bug by deleting this alias:

```js
principal: 'school_admin',
```

and add a dedicated principal panel:

```js
function buildPrincipalPanel({ recentExams = [], todoItems = [] } = {}) {
  return {
    title: '质量治理中心',
    sub: '学校质量总览、考试结果、审批查看和联考复盘',
    actionLabel: '查看质量总览 →',
    actionRoute: '/analytics/report',
    items: [
      { label: '总览', title: '质量总览', desc: '先看学校、年级、班级和学科波动。', route: '/analytics/report', tone: 'yellow' },
      { label: '结果', title: '考试结果', desc: `${metric(recentExams.length, '场', '近期考试待确认')}，关注发布和异常。`, route: '/exams', tone: 'purple' },
      { label: '审批', title: '审批查看', desc: `${metric(todoCount(todoItems), '项', '暂无待审批')}，集中处理成绩和通知。`, route: '/analytics/ai-report', tone: 'coral' },
      { label: '复盘', title: '联考复盘', desc: '跨校或阶段考试只做治理复盘，不进入日常配置。', route: '/joint-exams', tone: 'mint' },
    ],
  }
}
```

- [ ] **Step 2: Replace Dashboard imports**

In `frontend/src/pages/DashboardPage.vue`, replace:

```js
import { getDashboardConfig } from '../config/dashboardConfig'
import { buildAdminPriorityActions, buildRoleActionPanel } from '../config/roleWorkbenches.js'
```

with:

```js
import {
  buildRoleActionPanel,
  buildRolePriorityActions,
  getRoleDashboardKpis,
} from '../config/roleEntryMatrix.js'
```

Then replace `config` and `dashboardWidgets` usage with matrix-driven values:

```js
const dashboardKpis = computed(() =>
  getRoleDashboardKpis(role.value).map((kpi, index) => ({
    ...kpi,
    tone: statToneSequence[index % statToneSequence.length],
    icon: kpiIconMap[kpi.id] || ['exam', 'people', 'marking', 'chart'][index % 4],
  })),
)
```

Remove the `<WidgetGrid>` section if it repeats the same entries already shown in `secondaryBusinessGroups`.

- [ ] **Step 3: Replace priority logic**

Change `profilePriorityActions` to:

```js
const profilePriorityActions = computed(() =>
  buildRolePriorityActions(role.value, {
    profile: workbenchProfile.value,
    summary: kpiData.value,
    recentExams: recentExams.value,
    todoItems: todoItems.value,
  }).filter(action => canAccessRoute(action.route)),
)
```

- [ ] **Step 4: Update dashboard tests**

In `frontend/src/pages/__tests__/DashboardPage.test.js`, add assertions:

```js
it('keeps principal governance separate from school admin operations', () => {
  expect(content).toContain('质量治理中心')
  expect(content).toContain('buildRoleActionPanel')
  expect(content).not.toContain("principal: 'school_admin'")
})

it('does not render duplicate module grid after role business groups', () => {
  expect(content).not.toContain('<WidgetGrid')
})
```

If the test file is static-source based, keep these assertions as static-source checks.

- [ ] **Step 5: Delete old role panel file**

Run:

```bash
git rm frontend/src/config/roleWorkbenches.js
```

If `frontend/src/config/dashboardConfig.js` has no imports, run:

```bash
git rm frontend/src/config/dashboardConfig.js
```

If generic KPI metadata remains useful, keep it but remove role-specific configs and rename tests accordingly.

- [ ] **Step 6: Verify dashboard replacement**

Run:

```bash
cd /home/ops/projects/edu-cloud
npm --prefix frontend test -- --run \
  src/__tests__/roleEntryMatrix.test.js \
  src/pages/__tests__/DashboardPage.test.js
```

Expected: pass, and `rg "roleWorkbenches|principal: 'school_admin'|getDashboardConfig" frontend/src` returns no production imports.

- [ ] **Step 7: Commit dashboard replacement**

Run:

```bash
git add frontend/src/config/roleEntryMatrix.js frontend/src/pages/DashboardPage.vue frontend/src/pages/__tests__/DashboardPage.test.js
git add -u frontend/src/config/roleWorkbenches.js frontend/src/config/dashboardConfig.js frontend/src/__tests__/roleWorkbenches.test.js
git commit -m "replace: drive dashboard role panels from entry matrix"
```

---

## Task 3: Make Role Switching Explicit and Route-Safe

**Files:**
- Modify: `frontend/src/config/identityRouting.js`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/components/shell/RoleSwitcher.vue`
- Modify: `frontend/src/__tests__/identityRouting.test.js`
- Modify: `frontend/src/__tests__/auth-store.test.js`
- Modify: `frontend/src/__tests__/RoleSwitcher.test.js`

- [ ] **Step 1: Add helper functions**

In `identityRouting.js`, add:

```js
export function findRoleIndexByKey(roles = [], roleKey) {
  return roles.findIndex(role => normalizeRole(role.role) === roleKey)
}

export function routeBelongsToRoleEntry(routePath, roleKey, policy) {
  if (routePath === '/') return true
  const visibleRoutes = new Set([...policy.primaryRoutes, ...policy.secondaryRoutes])
  return visibleRoutes.has(routePath) || [...visibleRoutes].some(route => route !== '/' && routePath.startsWith(`${route}/`))
}
```

- [ ] **Step 2: Add auth store switching by role key**

In `auth.js`, add:

```js
async function switchRoleByKey(roleKey) {
  const index = findRoleIndexByKey(roles.value, roleKey)
  if (index < 0) return false
  return switchRole(index)
}
```

Export it from the store return object.

- [ ] **Step 3: Make RoleSwitcher copy explicit**

In `RoleSwitcher.vue`, render each role option with:

```js
const primaryText = role.is_primary ? '主身份' : '可切换'
```

and include a current tag:

```js
isCurrent ? h('span', { style: 'margin-left:auto;color:var(--color-primary);' }, '当前') : null
```

- [ ] **Step 4: Use matrix route policy after switch**

In `RoleSwitcher.vue`, replace sidebar-derived route ownership with matrix ownership:

```js
import { getRoleEntryPolicy } from '../../config/roleEntryMatrix.js'
import { routeBelongsToRoleEntry } from '../../config/identityRouting.js'

const routeInWorkbench = routeBelongsToRoleEntry(route.path, targetRoleKey, getRoleEntryPolicy(targetRoleKey))
```

Keep the `canAccessRouteForRole()` check.

- [ ] **Step 5: Verify switching**

Run:

```bash
npm --prefix frontend test -- --run \
  src/__tests__/identityRouting.test.js \
  src/__tests__/auth-store.test.js \
  src/__tests__/RoleSwitcher.test.js
```

Expected: pass.

- [ ] **Step 6: Commit role switching**

Run:

```bash
git add frontend/src/config/identityRouting.js frontend/src/stores/auth.js frontend/src/components/shell/RoleSwitcher.vue frontend/src/__tests__/identityRouting.test.js frontend/src/__tests__/auth-store.test.js frontend/src/__tests__/RoleSwitcher.test.js
git commit -m "replace: make role switching matrix-aware"
```

---

## Task 4: Use Real Active-Role Summary Data Without New Backend Complexity

**Files:**
- Create: `frontend/src/composables/useRoleWorkbenchData.js`
- Create: `frontend/src/composables/__tests__/useRoleWorkbenchData.test.js`
- Modify: `frontend/src/pages/DashboardPage.vue`

- [ ] **Step 1: Add composable tests**

Create `frontend/src/composables/__tests__/useRoleWorkbenchData.test.js`:

```js
import { describe, expect, it, vi } from 'vitest'
import { buildRoleWorkbenchSummary } from '../useRoleWorkbenchData.js'

describe('role workbench data adapter', () => {
  it('keeps empty state stable when optional API data is missing', () => {
    const summary = buildRoleWorkbenchSummary('principal', {
      dashboard: {},
      exams: [],
      markingAssignments: [],
      conductOverview: null,
    })
    expect(summary.kpiData).toEqual({})
    expect(summary.recentExams).toEqual([])
    expect(summary.todoItems).toEqual([])
  })

  it('turns marking assignments into teacher todo items', () => {
    const summary = buildRoleWorkbenchSummary('subject_teacher', {
      dashboard: { pending_grading: 0 },
      exams: [],
      markingAssignments: [{ id: 'a1' }, { id: 'a2' }],
      conductOverview: null,
    })
    expect(summary.todoItems).toEqual([
      { label: '我的阅卷任务', count: 2, route: '/marking', color: 'yellow', tagType: 'warning' },
    ])
  })
})
```

- [ ] **Step 2: Create adapter**

Create `frontend/src/composables/useRoleWorkbenchData.js`:

```js
export function buildRoleWorkbenchSummary(role, { dashboard = {}, exams = [], markingAssignments = [], conductOverview = null } = {}) {
  const recentExams = exams.slice(0, 3).map(exam => ({
    id: exam.id,
    name: exam.name,
    status: exam.status,
    subject_count: exam.subjects?.length ?? exam.subject_count ?? null,
    created_at: exam.created_at,
    grading_progress: exam.grading_progress ?? null,
  }))

  const todoItems = []
  if (['subject_teacher', 'homeroom_teacher', 'lesson_prep_leader'].includes(role) && markingAssignments.length > 0) {
    todoItems.push({ label: '我的阅卷任务', count: markingAssignments.length, route: '/marking', color: 'yellow', tagType: 'warning' })
  }
  if (conductOverview?.pending_records) {
    todoItems.push({ label: '德育待处理', count: conductOverview.pending_records, route: '/conduct', color: 'orange', tagType: 'warning' })
  }

  return {
    kpiData: dashboard,
    recentExams,
    todoItems,
  }
}
```

- [ ] **Step 3: Wire Dashboard through adapter**

In `DashboardPage.vue`, call existing endpoints as today, but normalize through `buildRoleWorkbenchSummary()` before assigning `kpiData`, `recentExams`, and `todoItems`.

Do not add a new `/workbench/summary` endpoint in this batch. The existing APIs are enough for a first maintainable slice.

- [ ] **Step 4: Verify adapter**

Run:

```bash
npm --prefix frontend test -- --run \
  src/composables/__tests__/useRoleWorkbenchData.test.js \
  src/pages/__tests__/DashboardPage.test.js
```

Expected: pass.

- [ ] **Step 5: Commit data adapter**

Run:

```bash
git add frontend/src/composables/useRoleWorkbenchData.js frontend/src/composables/__tests__/useRoleWorkbenchData.test.js frontend/src/pages/DashboardPage.vue frontend/src/pages/__tests__/DashboardPage.test.js
git commit -m "replace: normalize dashboard data by active role"
```

---

## Task 5: Correct Backend Subject Scope for Grade Leader

**Files:**
- Modify: `src/edu_cloud/api/permissions.py`
- Add or modify focused backend test under `tests/`

- [ ] **Step 1: Add failing backend test**

Find an existing permissions test:

```bash
find tests -type f -name "*permission*test*.py" -o -name "test_*permission*.py"
```

Add:

```python
from types import SimpleNamespace

from edu_cloud.api.permissions import get_visible_subject_codes


def test_grade_leader_can_see_all_subjects_within_grade_scope():
    role = SimpleNamespace(role="grade_leader", subject_codes=None)
    assert get_visible_subject_codes(role) is None
```

Run the focused test:

```bash
.venv/bin/python -m pytest tests/path/to/test_file.py::test_grade_leader_can_see_all_subjects_within_grade_scope -q
```

Expected: fail because current function returns `[]`.

- [ ] **Step 2: Update subject visibility**

In `src/edu_cloud/api/permissions.py`, change:

```python
if role.role in ("platform_admin", "district_admin", "school_admin", "principal",
                 "academic_director", "homeroom_teacher", "admin",
                 "head_teacher"):
```

to:

```python
if role.role in ("platform_admin", "district_admin", "school_admin", "principal",
                 "academic_director", "grade_leader", "homeroom_teacher", "admin",
                 "head_teacher"):
```

- [ ] **Step 3: Verify backend scope**

Run:

```bash
.venv/bin/python -m pytest tests/path/to/test_file.py::test_grade_leader_can_see_all_subjects_within_grade_scope -q
```

Expected: pass.

- [ ] **Step 4: Commit backend scope fix**

Run:

```bash
git add src/edu_cloud/api/permissions.py tests/path/to/test_file.py
git commit -m "fix: allow grade leaders all-subject visibility within grade scope"
```

---

## Task 6: Align Router Guards with Route Requirements

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/config/routeAccess.js`
- Modify: `frontend/src/__tests__/router.test.js`
- Modify: `frontend/src/__tests__/routeAccess.test.js`

- [ ] **Step 1: Add guard consistency tests**

Add tests that verify:

```js
expect(getRouteAccessRequirement('/grading/tasks')).toEqual({ permission: 'manage_grading', moduleCode: 'grading' })
expect(getRouteAccessRequirement('/marking')).toEqual({ permission: 'view_grading', moduleCode: 'grading' })
expect(getRouteAccessRequirement('/conduct/settings')).toEqual({ permission: 'manage_conduct_rules', moduleCode: 'conduct' })
expect(getRouteAccessRequirement('/selections')).toEqual({ permission: 'manage_scheduling' })
```

- [ ] **Step 2: Fill missing route requirements**

Add these missing requirements to `ROUTE_ACCESS_REQUIREMENTS`:

```js
'/conduct/settings': { permission: 'manage_conduct_rules', moduleCode: 'conduct' },
'/selections': { permission: 'manage_scheduling' },
'/schools': { permission: 'manage_schools' },
'/admin/impersonate': { permission: 'manage_schools' },
```

- [ ] **Step 3: Prefer permission metadata over role lists**

In `router/index.js`, replace role-list-only routes with permissions when permission truth exists:

```js
{ path: 'exams', name: 'ExamList', component: () => import('../pages/ExamListPage.vue'), meta: { permissions: ['view_exams'], moduleCode: 'exam' } },
{ path: 'exams/:id', name: 'ExamDetail', component: () => import('../pages/ExamDetailPage.vue'), meta: { permissions: ['view_exams'], moduleCode: 'exam' } },
{ path: 'marking', name: 'MarkingSelect', component: () => import('../pages/MarkingSelectPage.vue'), meta: { permissions: ['view_grading'], moduleCode: 'grading' } },
```

Do not broaden backend permissions here; this is frontend route consistency only.

- [ ] **Step 4: Verify router**

Run:

```bash
npm --prefix frontend test -- --run src/__tests__/router.test.js src/__tests__/routeAccess.test.js
```

Expected: pass.

- [ ] **Step 5: Commit router alignment**

Run:

```bash
git add frontend/src/router/index.js frontend/src/config/routeAccess.js frontend/src/__tests__/router.test.js frontend/src/__tests__/routeAccess.test.js
git commit -m "replace: align route guards with access requirements"
```

---

## Task 7: Verification, Build, and Deploy

**Files:**
- No manual edits unless verification reveals a scoped bug.

- [ ] **Step 1: Run role-entry targeted frontend suite**

Run:

```bash
npm --prefix frontend test -- --run \
  src/__tests__/roleEntryMatrix.test.js \
  src/__tests__/workbenchProfiles.test.js \
  src/__tests__/routeAccess.test.js \
  src/__tests__/sidebarConfig.rolePolicy.test.js \
  src/__tests__/identityRouting.test.js \
  src/__tests__/auth-store.test.js \
  src/__tests__/AppHeader.test.js \
  src/__tests__/AppSidebar.test.js \
  src/__tests__/RoleSwitcher.test.js \
  src/pages/__tests__/DashboardPage.test.js \
  src/composables/__tests__/useRoleWorkbenchData.test.js
```

Expected: all pass.

- [ ] **Step 2: Run focused backend test**

Run:

```bash
.venv/bin/python -m pytest tests/path/to/test_file.py::test_grade_leader_can_see_all_subjects_within_grade_scope -q
```

Expected: pass.

- [ ] **Step 3: Run frontend verify**

Run:

```bash
scripts/codex-verify frontend
```

Expected: lint and build pass. If backend hash drifts after a backend commit, restart backend services before final truthline.

- [ ] **Step 4: Restart backend if backend source changed**

Run only if Task 5 was committed:

```bash
sudo systemctl restart edu-cloud.service edu-cloud-worker.service
sleep 2
```

- [ ] **Step 5: Verify live delivery**

Run:

```bash
scripts/truth-status.sh
curl -fsS https://mcu.asia/version.json
curl -fsS https://mcu.asia/api/v1/version
```

Expected: source, build, nginx, and backend hashes match.

- [ ] **Step 6: Browser acceptance**

Open these URLs on production:

```text
https://mcu.asia/?_v=<build_id>
https://mcu.asia/workbench-preview?role=school_admin&_v=<build_id>
https://mcu.asia/workbench-preview?role=principal&_v=<build_id>
https://mcu.asia/workbench-preview?role=lesson_prep_leader&_v=<build_id>
https://mcu.asia/workbench-preview?role=teaching_research_leader&_v=<build_id>
```

Check:

- School admin has no personal marking primary entry.
- Principal does not show school config or teacher assignment as primary.
- Lesson prep leader shows subject exam, grading assignment, and grading control.
- Teaching research leader shows knowledge graph and question bank as primary.
- Role switcher returns to `/` when switching into a role whose matrix does not own the current route.

---

## Deferred Items

These are intentionally not in the first full optimization batch:

- New backend `/workbench/summary` endpoint for true cross-identity task aggregation.
- Principal approval domain modeling beyond existing report/notification routes.
- Parent-side redesign.
- Schema drift repair for `exam_import_sessions` unless the batch touches exam import persistence.

Schema drift still blocks a full “all system healthy” claim. If final completion must include Guardian green, run a separate DB investigation plan before claiming all gates are clear.

## Self-Review

- Spec coverage: all confirmed roles are represented, including school admin, principal, academic director, grade leader, homeroom teacher, lesson prep leader, teaching research leader, and subject teacher.
- Maintainability: one matrix replaces scattered role maps; deleted files are removed instead of left as compatibility layers.
- Cognitive load: dashboard primary, sidebar, and header entries derive from the same role-entry policy.
- Backend risk: only one minimal backend scope fix is included; no migration or permission broadening is hidden in frontend work.
- Open risk: Guardian schema drift is known and documented; it must not be silently ignored in completion evidence.
