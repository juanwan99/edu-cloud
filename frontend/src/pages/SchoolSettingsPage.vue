<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">学校配置</h1>
        <p class="page-subtitle">管理功能模块和学校设置</p>
      </div>
    </div>

    <!-- Module summary -->
    <n-text v-if="modules.length" depth="2" style="display: block; margin-bottom: var(--space-4);">
      已启用 {{ enabledCount }} / {{ modules.length }} 个模块
    </n-text>

    <n-tabs type="line" animated>
      <n-tab-pane name="modules" tab="功能模块">
        <n-card title="功能模块管理" style="margin-top: var(--space-4)">
          <p style="color: var(--color-text-muted); margin-bottom: var(--space-4)">启用或禁用学校可用的功能模块。禁用后，对应的导航菜单、API 和 AI 助手工具将不可用。</p>
          <n-space vertical>
            <div v-for="m in modules" :key="m.code" class="module-row">
              <div class="module-info">
                <n-icon :size="20" style="margin-right: 10px; color: var(--color-text-secondary);">
                  <component :is="getModuleIcon(m.code)" />
                </n-icon>
                <div>
                  <n-text strong>{{ m.name }}</n-text>
                  <n-text depth="3" style="margin-left: var(--space-2)">{{ m.code }}</n-text>
                  <div v-if="MODULE_DESCRIPTIONS[m.code]" style="margin-top: 2px;">
                    <n-text depth="3" style="font-size: var(--fs-base);">{{ MODULE_DESCRIPTIONS[m.code] }}</n-text>
                  </div>
                </div>
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

      <n-tab-pane name="settings" tab="学校设置">
        <n-card title="配置项" style="margin-top: var(--space-4)">
          <n-data-table :columns="settingsColumns" :data="settings" :loading="loadingSettings" />
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="capabilities" tab="能力矩阵">
        <n-card title="角色能力矩阵" style="margin-top: var(--space-4)">
          <template #header-extra>
            <n-button size="small" class="btn-pill" @click="handleInitCapabilities">初始化默认</n-button>
          </template>
          <div style="margin-bottom: var(--space-3); display: flex; align-items: center; gap: var(--space-3);">
            <n-text>按角色筛选：</n-text>
            <n-select
              v-model:value="capRoleFilter"
              :options="capRoleOptions"
              placeholder="全部角色"
              clearable
              style="width: 200px"
            />
          </div>
          <div v-if="loadingCaps" style="text-align: center; padding: var(--space-6);">
            <n-spin />
          </div>
          <div v-else-if="capMatrix.length === 0" style="text-align: center; padding: var(--space-6);">
            <n-text depth="3">暂无能力配置，请点击"初始化默认"</n-text>
          </div>
          <div v-else class="cap-matrix-wrapper">
            <table class="cap-matrix">
              <thead>
                <tr>
                  <th style="min-width: 100px;">域 / 操作</th>
                  <th v-for="role in capRoles" :key="role" style="min-width: 90px; text-align: center;">{{ ROLE_LABELS[role] || role }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="da in capDomainActions" :key="da.key">
                  <td>
                    <n-text depth="2" style="font-size: var(--fs-base);">{{ DOMAIN_LABELS[da.domain] || da.domain }}</n-text>
                    <n-text depth="3" style="font-size: var(--fs-base); margin-left: var(--space-1);">/ {{ ACTION_LABELS[da.action] || da.action }}</n-text>
                  </td>
                  <td v-for="role in capRoles" :key="role" style="text-align: center;">
                    <n-checkbox
                      :checked="getCapValue(role, da.domain, da.action)"
                      @update:checked="(v) => handleSetCapability(role, da.domain, da.action, v)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </n-card>
      </n-tab-pane>
    </n-tabs>

    <!-- Inline edit modal for settings -->
    <n-modal v-model:show="showEditSetting" preset="dialog" title="编辑配置值" positive-text="保存"
      negative-text="取消" :positive-button-props="{ class: 'btn-pill' }"
      :negative-button-props="{ class: 'btn-pill' }" @positive-click="handleSaveSetting">
      <n-form label-placement="top">
        <n-form-item :label="`${editingSettingRow?.category} / ${editingSettingRow?.key}`">
          <n-input v-model:value="editingSettingValue" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { NText, NIcon } from 'naive-ui'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { ROLE_LABELS } from '../config/roles.js'
import {
  getSchoolModules, toggleModule, getSchoolSettings, updateSchoolSetting,
  getCapabilities, setCapability, initCapabilities,
} from '../api/schoolSettings.js'
import {
  FileText, School, PenTool, BarChart3,
  FlaskConical, Calendar, FileEdit, Users,
  CheckSquare,
} from 'lucide-vue-next'

const MODULE_DESCRIPTIONS = {
  exam: '考试创建、科目管理、题目编辑、答题卡设计',
  grading: 'AI 阅卷、评分细则、教师复核、阅卷调度',
  homework: '作业布置、提交批改、统计分析',
  study_analytics: '成绩分析、趋势对比、分层学情',
  research: '教研协作、集体备课、课题管理',
  teaching: '排课、选考组合、课表管理',
  calendar: '校历事件、通知规则、学期管理',
  studio: '文档生成、报告模板、论文协作',
  conduct: '操行管理、积分记录、班规、家长端',
}

const MODULE_ICONS = {
  exam: FileText,
  grading: PenTool,
  homework: FileEdit,
  study_analytics: BarChart3,
  research: FlaskConical,
  teaching: School,
  calendar: Calendar,
  studio: FileEdit,
  conduct: Users,
}

function getModuleIcon(code) {
  return MODULE_ICONS[code] || CheckSquare
}

const auth = useAuthStore()
const message = useMessage()
const modules = ref([])
const settings = ref([])
const toggling = ref(null)
const loadingSettings = ref(false)

// Capabilities state
const capabilities = ref([])
const loadingCaps = ref(false)
const capRoleFilter = ref(null)

const DOMAIN_LABELS = {
  exam: '考试管理', grading: '阅卷系统', homework: '作业管理',
  study_analytics: '学情分析', research: '教研题库', teaching: '教学管理',
  calendar: '校历日程', studio: '文档中心', system: '系统管理',
}
const ACTION_LABELS = { read: '读', write: '写' }

const capRoleOptions = [
  'school_admin', 'principal', 'academic_director',
  'teaching_research_leader', 'grade_leader', 'lesson_prep_leader',
  'homeroom_teacher', 'subject_teacher',
].map(r => ({ label: ROLE_LABELS[r] || r, value: r }))

// Inline settings editing state
const showEditSetting = ref(false)
const editingSettingRow = ref(null)
const editingSettingValue = ref('')

const schoolId = () => auth.currentRole?.school_id

const enabledCount = computed(() => modules.value.filter((m) => m.enabled).length)

const capMatrix = computed(() => {
  if (capRoleFilter.value) {
    return capabilities.value.filter((c) => c.role === capRoleFilter.value)
  }
  return capabilities.value
})

const capRoles = computed(() => {
  const set = new Set(capMatrix.value.map((c) => c.role))
  return [...set].sort()
})

const capDomainActions = computed(() => {
  const map = new Map()
  for (const c of capMatrix.value) {
    const key = `${c.domain}::${c.action}`
    if (!map.has(key)) map.set(key, { domain: c.domain, action: c.action, key })
  }
  return [...map.values()].sort((a, b) => a.key.localeCompare(b.key))
})

function getCapValue(role, domain, action) {
  const cap = capMatrix.value.find((c) => c.role === role && c.domain === domain && c.action === action)
  return cap ? cap.enabled : false
}

const settingsColumns = [
  { title: '分类', key: 'category', width: 120 },
  { title: '键', key: 'key', width: 200 },
  {
    title: '值', key: 'value',
    render: (row) => h(
      NText,
      {
        style: 'cursor: pointer; border-bottom: 1px dashed rgba(255,255,255,0.2); padding-bottom: 1px;',
        onClick: () => startEditSetting(row),
      },
      () => row.value || '(空)'
    ),
  },
]

function startEditSetting(row) {
  editingSettingRow.value = row
  editingSettingValue.value = row.value || ''
  showEditSetting.value = true
}

async function handleSaveSetting() {
  if (!editingSettingRow.value) return
  try {
    await updateSchoolSetting(schoolId(), {
      category: editingSettingRow.value.category,
      key: editingSettingRow.value.key,
      value: editingSettingValue.value,
    })
    message.success('配置已保存')
    showEditSetting.value = false
    await loadSettings()
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
    return false
  }
}

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

async function loadCapabilities() {
  if (!schoolId()) return
  loadingCaps.value = true
  try {
    const { data } = await getCapabilities(schoolId(), capRoleFilter.value || undefined)
    capabilities.value = data
  } catch { /* */ }
  loadingCaps.value = false
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

async function handleSetCapability(role, domain, action, enabled) {
  try {
    await setCapability(schoolId(), { role, domain, action, enabled })
    // Update local state optimistically
    const idx = capabilities.value.findIndex((c) => c.role === role && c.domain === domain && c.action === action)
    if (idx !== -1) capabilities.value[idx].enabled = enabled
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
    await loadCapabilities()
  }
}

async function handleInitCapabilities() {
  try {
    await initCapabilities(schoolId())
    message.success('能力矩阵已初始化')
    await loadCapabilities()
  } catch (e) {
    message.error(e.response?.data?.detail || '初始化失败')
  }
}

onMounted(() => {
  loadModules()
  loadSettings()
  loadCapabilities()
})
</script>

<style scoped>
.module-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.09);
}
.module-info {
  display: flex;
  align-items: flex-start;
}
.cap-matrix-wrapper {
  overflow-x: auto;
}
.cap-matrix {
  width: 100%;
  border-collapse: collapse;
}
.cap-matrix th,
.cap-matrix td {
  padding: 8px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  font-size: var(--fs-base);
}
.cap-matrix th {
  text-align: left;
  color: rgba(255, 255, 255, 0.6);
  font-weight: var(--fw-medium);
}
.cap-matrix tbody tr:hover {
  background: rgba(255, 255, 255, 0.04);
}
</style>
