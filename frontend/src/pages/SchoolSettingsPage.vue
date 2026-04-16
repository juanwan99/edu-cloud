<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">学校配置</h1>
        <p class="page-subtitle">管理功能模块和学校设置</p>
      </div>
    </div>

    <n-tabs type="line" animated>
      <n-tab-pane name="modules" tab="功能模块">
        <n-card title="功能模块管理" style="margin-top: 16px">
          <p style="color: #999; margin-bottom: 16px">启用或禁用学校可用的功能模块。禁用后，对应的导航菜单、API 和 AI 助手工具将不可用。</p>
          <n-space vertical>
            <div v-for="m in modules" :key="m.code" class="module-row">
              <div class="module-info">
                <n-text strong>{{ m.name }}</n-text>
                <n-text depth="3" style="margin-left: 8px">{{ m.code }}</n-text>
              </div>
              <n-switch
                :value="m.enabled"
                :loading="toggling === m.code"
                @update:value="(v) => handleToggle(m.code, v)"
              />
            </div>
          </n-space>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="segments" tab="分数段">
        <ScoreSegmentSettings />
      </n-tab-pane>

      <n-tab-pane name="settings" tab="学校设置">
        <n-card title="配置项" style="margin-top: 16px">
          <n-data-table :columns="settingsColumns" :data="settings" :loading="loadingSettings" />
        </n-card>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import ScoreSegmentSettings from '../components/analytics/ScoreSegmentSettings.vue'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { getSchoolModules, toggleModule, getSchoolSettings } from '../api/schoolSettings.js'

const auth = useAuthStore()
const message = useMessage()
const modules = ref([])
const settings = ref([])
const toggling = ref(null)
const loadingSettings = ref(false)

const schoolId = () => auth.currentRole?.school_id

const settingsColumns = [
  { title: '分类', key: 'category', width: 120 },
  { title: '键', key: 'key', width: 200 },
  { title: '值', key: 'value' },
]

async function loadModules() {
  if (!schoolId()) return
  try {
    const { data } = await getSchoolModules(schoolId())
    modules.value = data
  } catch (e) {
    message.error('加载模块失败')
  }
}

async function loadSettings() {
  if (!schoolId()) return
  loadingSettings.value = true
  try {
    const { data } = await getSchoolSettings(schoolId())
    settings.value = data
  } catch { /* */ }
  loadingSettings.value = false
}

async function handleToggle(code, enabled) {
  toggling.value = code
  try {
    await toggleModule(schoolId(), code, enabled)
    await loadModules()
    await auth.loadModules()
    message.success(`模块「${code}」已${enabled ? '启用' : '禁用'}`)
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  }
  toggling.value = null
}

onMounted(() => {
  loadModules()
  loadSettings()
})
</script>

<style scoped>
.module-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
}
.module-info {
  display: flex;
  align-items: center;
}
</style>
