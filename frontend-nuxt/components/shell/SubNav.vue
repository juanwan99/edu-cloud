<template>
  <nav v-if="subMenus.length > 0" class="sub-nav">
    <NuxtLink
      v-for="item in subMenus"
      :key="item.path"
      :to="item.path"
      class="sub-nav-item"
      :class="{ active: route.path === item.path }"
    >
      <el-icon v-if="item.icon" :size="14" style="margin-right: 4px">
        <component :is="iconMap[item.icon] || 'Document'" />
      </el-icon>
      {{ item.name }}
    </NuxtLink>
  </nav>
</template>

<script setup lang="ts">
import {
  Document, List, EditPen, Finished, Postcard, DataLine,
  DataAnalysis, Histogram, SetUp, Grid, Medal, Setting,
  TrendCharts, Odometer, School, User, Operation,
  Notebook, Edit, Camera, Refresh,
  Reading, Monitor, DocumentChecked, FolderOpened, Box,
  Collection, Search, DocumentAdd, ChatDotRound, Connection,
  Calendar, Aim, Files,
  Avatar, Checked, Trophy,
  OfficeBuilding, Menu,
} from '@element-plus/icons-vue'

const iconMap: Record<string, any> = {
  document: Document, list: List, 'edit-pen': EditPen, finished: Finished,
  postcard: Postcard, 'data-line': DataLine, 'data-analysis': DataAnalysis,
  histogram: Histogram, 'set-up': SetUp, grid: Grid, medal: Medal,
  setting: Setting, 'trend-charts': TrendCharts, odometer: Odometer,
  school: School, user: User, operation: Operation, notebook: Notebook,
  edit: Edit, camera: Camera, refresh: Refresh, reading: Reading,
  monitor: Monitor, 'document-checked': DocumentChecked,
  'folder-opened': FolderOpened, box: Box, collection: Collection,
  search: Search, 'document-add': DocumentAdd,
  'chat-dot-round': ChatDotRound, connection: Connection,
  calendar: Calendar, aim: Aim, files: Files, avatar: Avatar,
  checked: Checked, trophy: Trophy,
  'office-building': OfficeBuilding, menu: Menu,
}

const route = useRoute()
const { currentSubMenus: subMenus } = useMenus()
</script>

<style scoped lang="scss">
.sub-nav {
  height: var(--hfs-subnav-height);
  background: var(--el-color-primary-light-9);
  border-bottom: 1px solid var(--el-color-primary-light-7);
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 24px;
  position: fixed;
  top: var(--hfs-header-height);
  left: 0;
  right: 0;
  z-index: 99;
}

.sub-nav-item {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: #606266;
  text-decoration: none;
  padding: 8px 0;
  cursor: pointer;
  transition: color 0.2s;

  &:hover {
    color: var(--hfs-primary);
  }

  &.active {
    color: var(--hfs-primary);
    font-weight: 500;
    border-bottom: 2px solid var(--hfs-primary);
  }
}
</style>
