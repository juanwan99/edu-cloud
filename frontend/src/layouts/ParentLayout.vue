<template>
  <n-config-provider :theme="darkTheme">
    <n-message-provider>
      <n-layout style="min-height: 100vh;">
        <!-- Top bar -->
        <n-layout-header bordered style="height: 56px; display: flex; align-items: center; padding: 0 16px; justify-content: space-between;">
          <span style="font-size: 18px; font-weight: 600;">德育积分</span>
          <div style="display: flex; align-items: center; gap: 12px;">
            <n-select
              v-if="children.length > 1"
              v-model:value="currentChildId"
              :options="childOptions"
              size="small"
              style="width: 120px;"
            />
            <n-button quaternary circle @click="$router.push('/parent/profile')">
              <template #icon><n-icon><person-outline /></n-icon></template>
            </n-button>
          </div>
        </n-layout-header>

        <!-- Content -->
        <n-layout-content style="padding: 16px; padding-bottom: 72px;">
          <router-view :current-child="currentChild" />
        </n-layout-content>

        <!-- Bottom tabs -->
        <div class="bottom-tabs">
          <div
            v-for="tab in tabs"
            :key="tab.path"
            class="tab-item"
            :class="{ active: isActive(tab.path) }"
            @click="$router.push(tab.path)"
          >
            <span class="tab-icon">{{ tab.icon }}</span>
            <span class="tab-label">{{ tab.label }}</span>
          </div>
        </div>
      </n-layout>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, computed, onMounted, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { darkTheme } from 'naive-ui'
import {
  NConfigProvider, NLayout, NLayoutHeader, NLayoutContent,
  NButton, NIcon, NSelect, NMessageProvider
} from 'naive-ui'
import { PersonOutline } from '@vicons/ionicons5'
import { getParentMe, getChildren } from '../api/conduct'

const router = useRouter()
const route = useRoute()

const children = ref([])
const currentChildId = ref(null)
const parentInfo = ref(null)

const childOptions = computed(() =>
  children.value.map(c => ({ label: c.student_name, value: c.student_id }))
)

const currentChild = computed(() =>
  children.value.find(c => c.student_id === currentChildId.value) || children.value[0] || null
)

provide('currentChild', currentChild)
provide('children', children)

const tabs = [
  { path: '/parent', label: '概览', icon: '📊' },
  { path: '/parent/rankings', label: '排行', icon: '🏆' },
  { path: '/parent/rules', label: '班规', icon: '📋' },
  { path: '/parent/profile', label: '我的', icon: '👤' },
]

function isActive(path) {
  if (path === '/parent') return route.path === '/parent'
  return route.path.startsWith(path)
}

onMounted(async () => {
  const token = localStorage.getItem('cp_token')
  if (!token) {
    router.replace('/parent/login')
    return
  }
  try {
    const [meRes, childrenRes] = await Promise.all([getParentMe(), getChildren()])
    parentInfo.value = meRes.data
    children.value = childrenRes.data.children || childrenRes.data || []
    if (children.value.length > 0) {
      currentChildId.value = children.value[0].student_id
    } else {
      router.replace('/parent/bind')
    }
  } catch (err) {
    if (err.response?.status === 401) {
      localStorage.removeItem('cp_token')
      router.replace('/parent/login')
    }
  }
})
</script>

<style scoped>
.bottom-tabs {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #1e1e2e;
  border-top: 1px solid rgba(255, 255, 255, 0.09);
  display: flex;
  height: 56px;
  z-index: 100;
}
.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.5);
  transition: color 0.2s;
}
.tab-item.active {
  color: #63e2b7;
}
.tab-icon {
  font-size: 20px;
  line-height: 1;
}
.tab-label {
  font-size: 11px;
  margin-top: 2px;
}
</style>
