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

const role = computed(() => auth.user?.role || 'teacher')

// 角色可见菜单矩阵
function canSee(section) {
  const r = role.value
  if (r === 'admin') return true
  if (section === 'exams') return ['admin', 'principal'].includes(r)
  if (section === 'analytics') return ['admin', 'principal', 'subject_leader', 'head_teacher'].includes(r)
  return false
}

const allGradingMenu = [
  { label: '人工阅卷', key: '/marking', roles: ['admin', 'teacher', 'subject_leader', 'head_teacher'] },
  { label: '任务分配', key: '/marking/assign', roles: ['admin', 'principal'] },
  { label: '阅卷进度', key: '/marking/progress', roles: ['admin', 'principal', 'subject_leader', 'head_teacher', 'teacher'] },
  { type: 'divider' },
  { label: 'AI 批改任务', key: '/grading/tasks', roles: ['admin'] },
  { label: '教师复核', key: '/grading/review', roles: ['admin', 'teacher'] },
]

const filteredGradingMenu = computed(() =>
  allGradingMenu.filter(item =>
    item.type === 'divider' || !item.roles || item.roles.includes(role.value)
  )
)

const userMenuOptions = [
  {
    key: 'info',
    type: 'render',
    render: () =>
      h('div', { style: 'padding: 8px 16px; border-bottom: 1px solid var(--color-border-light);' }, [
        h('div', { style: 'font-weight: 700; font-size: 14px;' }, auth.user?.display_name),
        h(NTag, { size: 'small', round: true, type: auth.isAdmin ? 'warning' : 'info', style: 'margin-top: 4px;' },
          { default: () => ({ admin: '管理员', principal: '校长', subject_leader: '学科组长', head_teacher: '班主任', teacher: '教师' }[auth.user?.role] || auth.user?.role) }),
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
