<template>
  <nav class="navbar">
    <div class="navbar-inner">
      <div class="navbar-brand" @click="$router.push('/')">
        <span class="brand-icon">📝</span>
        <span class="brand-text">智能阅卷</span>
      </div>

      <div class="navbar-links">
        <router-link v-if="canSee('exams')" to="/exams" class="nav-link">考试管理</router-link>

        <n-dropdown :options="filteredGradingMenu" @select="handleGradingMenu">
          <span class="nav-link nav-link-dropdown">
            批改中心
            <span class="dropdown-arrow">▾</span>
          </span>
        </n-dropdown>

        <router-link v-if="canSee('analytics')" to="/" class="nav-link">数据分析</router-link>
        <router-link v-if="auth.isAdmin" to="/schools" class="nav-link">学校管理</router-link>
      </div>

      <div class="navbar-user">
        <n-dropdown :options="userMenuOptions" @select="handleUserMenu">
          <div class="user-avatar">
            {{ auth.user?.display_name?.[0] || 'U' }}
          </div>
        </n-dropdown>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { h, computed } from 'vue'
import { useRouter } from 'vue-router'
import { NTag } from 'naive-ui'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const role = computed(() => auth.currentRole?.role || '')

// 角色可见菜单矩阵（canonical + legacy 别名）
function canSee(section) {
  if (auth.isAdmin) return true
  const r = role.value
  if (section === 'exams') return true  // all authenticated users can see exams
  if (section === 'analytics') return [
    'grade_leader', 'homeroom_teacher', 'subject_teacher',
    'head_teacher', 'teacher',  // legacy aliases
  ].includes(r)
  return false
}

const allGradingMenu = [
  { label: '人工阅卷', key: '/marking', roles: ['platform_admin', 'admin', 'subject_teacher', 'teacher', 'homeroom_teacher', 'head_teacher'] },
  { label: '任务分配', key: '/marking/assign', adminOnly: true },
  { label: '阅卷进度', key: '/marking/progress', roles: ['platform_admin', 'admin', 'principal', 'academic_director', 'homeroom_teacher', 'head_teacher', 'subject_teacher', 'teacher'] },
  { type: 'divider' },
  { label: 'AI 批改任务', key: '/grading/tasks', adminOnly: true },
  { label: '教师复核', key: '/grading/review', roles: ['platform_admin', 'admin', 'subject_teacher', 'teacher'] },
]

const filteredGradingMenu = computed(() =>
  allGradingMenu.filter(item => {
    if (item.type === 'divider') return true
    if (item.adminOnly) return auth.isAdmin
    return !item.roles || item.roles.includes(role.value)
  })
)

const userMenuOptions = [
  {
    key: 'info',
    type: 'render',
    render: () =>
      h('div', { style: 'padding: 8px 16px; border-bottom: 1px solid var(--color-border-light);' }, [
        h('div', { style: 'font-weight: 700; font-size: 14px;' }, auth.user?.display_name),
        h(NTag, { size: 'small', round: true, type: auth.isAdmin ? 'warning' : 'info', style: 'margin-top: 4px;' },
          { default: () => ({
            platform_admin: '平台管理员', district_admin: '区管理员', principal: '校长',
            academic_director: '教务主任', grade_leader: '年级组长',
            homeroom_teacher: '班主任', subject_teacher: '科任教师', parent: '家长',
            admin: '管理员', teacher: '教师', head_teacher: '班主任',  // legacy
          }[auth.currentRole?.role] || auth.currentRole?.role) }),
      ]),
  },
  { label: '退出登录', key: 'logout' },
]

function handleGradingMenu(key) {
  router.push(key)
}

function handleUserMenu(key) {
  if (key === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 68px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border-light);
  z-index: 1000;
}

.navbar-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.navbar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.brand-icon {
  font-size: 24px;
}

.brand-text {
  font-size: 18px;
  font-weight: 800;
  color: var(--color-primary);
  letter-spacing: -0.02em;
}

.navbar-links {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-link {
  padding: 8px 16px;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-secondary);
  border-radius: var(--radius-sm);
  transition: var(--transition);
  cursor: pointer;
  text-decoration: none;
}

.nav-link:hover {
  color: var(--color-primary);
  background: var(--color-bg-alt);
}

.nav-link.router-link-active {
  color: var(--color-primary);
  font-weight: 700;
}

.nav-link-dropdown {
  display: flex;
  align-items: center;
  gap: 4px;
}

.dropdown-arrow {
  font-size: 12px;
}

.navbar-user {
  display: flex;
  align-items: center;
}

.user-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--macaron-mint-light);
  border: 2px solid var(--macaron-mint);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 15px;
  color: var(--color-primary);
  cursor: pointer;
  transition: var(--transition);
}

.user-avatar:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}
</style>
