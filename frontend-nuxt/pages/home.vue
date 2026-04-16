<template>
  <div class="home-page">
    <div class="welcome">
      <h2>{{ greeting }}，{{ authStore.userName }}</h2>
      <p>{{ authStore.roleName }} · {{ authStore.schoolName }}</p>
    </div>
    <div class="module-grid">
      <div
        v-for="menu in authStore.menus"
        :key="menu.code"
        class="module-card"
        @click="navigateToModule(menu)"
      >
        <div class="module-icon">
          <el-icon :size="32">
            <component :is="iconMap[menu.icon] || 'Document'" />
          </el-icon>
        </div>
        <div class="module-info">
          <h3>{{ menu.name }}</h3>
          <p>{{ menu.children.length }} 个功能</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Document, DataAnalysis, TrendCharts, Notebook, Reading,
  Collection, User, OfficeBuilding,
} from '@element-plus/icons-vue'

const iconMap: Record<string, any> = {
  document: Document, 'data-analysis': DataAnalysis,
  'trend-charts': TrendCharts, notebook: Notebook,
  reading: Reading, collection: Collection,
  user: User, 'office-building': OfficeBuilding,
}

const authStore = useAuthStore()
const { navigateToModule } = useMenus()

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 12) return '上午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})
</script>

<style scoped lang="scss">
.home-page {
  max-width: 1200px;
  margin: 0 auto;
}

.welcome {
  margin-bottom: 30px;

  h2 {
    font-size: 22px;
    margin-bottom: 4px;
  }

  p {
    color: #909399;
    font-size: 14px;
  }
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.module-card {
  background: #fff;
  border-radius: var(--hfs-card-radius);
  box-shadow: var(--hfs-card-shadow);
  padding: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: box-shadow 0.2s, transform 0.2s;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
  }

  .module-icon {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    background: var(--el-color-primary-light-9);
    color: var(--hfs-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .module-info {
    h3 {
      font-size: 16px;
      margin-bottom: 4px;
    }

    p {
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>
