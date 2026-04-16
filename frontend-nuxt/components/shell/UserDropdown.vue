<template>
  <el-dropdown trigger="click" @command="handleCommand">
    <span class="user-trigger">
      {{ authStore.userName || '用户' }}
      <el-icon><ArrowDown /></el-icon>
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item disabled>
          {{ authStore.roleName }} · {{ authStore.schoolName }}
        </el-dropdown-item>
        <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { ArrowDown } from '@element-plus/icons-vue'

const authStore = useAuthStore()

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    authStore.logout()
  }
}
</script>

<style scoped>
.user-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-size: 13px;
  color: #fff;
}
</style>
