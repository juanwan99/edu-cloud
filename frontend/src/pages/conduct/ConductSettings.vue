<template>
  <div>
    <n-page-header title="德育设置" subtitle="班级操行管理配置" style="margin-bottom: 16px;" />

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: 16px;">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <template v-if="classId">
      <n-spin :show="loading">
        <!-- Invite Code Section -->
        <n-card title="邀请码管理" style="margin-bottom: 16px;">
          <n-space vertical :size="12">
            <div style="display: flex; align-items: center; gap: 12px;">
              <n-tag size="large" :bordered="false" style="font-family: monospace; font-size: 18px;">
                {{ config.invite_code || '未生成' }}
              </n-tag>
              <n-button
                size="small"
                :loading="regenerating"
                @click="handleRegenerate"
              >
                刷新邀请码
              </n-button>
            </div>
            <div style="font-size: 13px; color: rgba(255,255,255,0.4);">
              家长使用此邀请码注册并绑定学生
            </div>
          </n-space>
        </n-card>

        <!-- Verification Settings -->
        <n-card title="家长验证方式" style="margin-bottom: 16px;">
          <n-radio-group v-model:value="config.verify_code_type" @update:value="saveConfig">
            <n-space>
              <n-radio value="id_card">身份证后六位</n-radio>
              <n-radio value="phone">手机号后四位</n-radio>
              <n-radio value="custom">自定义验证码</n-radio>
            </n-space>
          </n-radio-group>
        </n-card>

        <!-- Module Switch -->
        <n-card title="模块状态" style="margin-bottom: 16px;">
          <n-space align="center">
            <span>德育模块</span>
            <n-switch
              :value="config.is_active !== false"
              @update:value="(v) => { config.is_active = v; saveConfig() }"
            />
            <span style="color: rgba(255,255,255,0.4); font-size: 13px;">
              {{ config.is_active !== false ? '已启用' : '已停用' }}
            </span>
          </n-space>
        </n-card>

        <!-- Semester Management -->
        <n-card title="学期管理">
          <template #header-extra>
            <n-button type="primary" size="small" @click="showCreateSemester = true">新建学期</n-button>
          </template>

          <n-list v-if="semesters.length > 0" bordered size="small">
            <n-list-item v-for="s in semesters" :key="s.id">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <n-space align="center" :size="8">
                  <span>{{ s.name }}</span>
                  <n-tag v-if="s.is_active" type="success" size="small">当前</n-tag>
                </n-space>
                <n-button
                  v-if="!s.is_active"
                  size="tiny"
                  @click="handleActivate(s.id)"
                  :loading="activating === s.id"
                >
                  设为当前学期
                </n-button>
              </div>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无学期">
            <template #extra>
              <n-button type="primary" size="small" @click="showCreateSemester = true">新建学期</n-button>
            </template>
          </n-empty>
        </n-card>
      </n-spin>

      <!-- Create Semester Modal -->
      <n-modal v-model:show="showCreateSemester" preset="card" title="新建学期" style="width: 400px;">
        <n-form :model="semesterForm">
          <n-form-item label="学期名称">
            <n-input v-model:value="semesterForm.name" placeholder="例：2025-2026 第二学期" />
          </n-form-item>
          <n-form-item label="开始日期">
            <n-date-picker v-model:value="semesterForm.start_date" type="date" style="width: 100%;" />
          </n-form-item>
          <n-form-item label="结束日期">
            <n-date-picker v-model:value="semesterForm.end_date" type="date" style="width: 100%;" />
          </n-form-item>
        </n-form>
        <template #action>
          <n-button type="primary" :loading="creatingSemester" @click="handleCreateSemester">创建</n-button>
        </template>
      </n-modal>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  NPageHeader, NCard, NSpace, NTag, NButton, NRadioGroup, NRadio,
  NSwitch, NList, NListItem, NModal, NForm, NFormItem, NInput,
  NDatePicker, NEmpty, NSpin, NAlert, useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import {
  getConductConfig, updateConductConfig, regenerateInviteCode,
  getSemesters, createSemester, activateSemester,
} from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const config = ref({
  invite_code: '',
  verify_code_type: 'id_card',
  is_active: true,
})
const loading = ref(false)
const regenerating = ref(false)

const semesters = ref([])
const showCreateSemester = ref(false)
const semesterForm = ref({ name: '', start_date: null, end_date: null })
const creatingSemester = ref(false)
const activating = ref(null)

async function loadConfig() {
  if (!classId.value) return
  loading.value = true
  try {
    const res = await getConductConfig(classId.value)
    const data = res.data
    config.value = {
      invite_code: data.invite_code || '',
      verify_code_type: data.verify_code_type || 'id_card',
      is_active: data.is_active !== false,
    }
  } catch {
    // defaults are fine
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!classId.value) return
  try {
    await updateConductConfig(classId.value, {
      verify_code_type: config.value.verify_code_type,
      is_active: config.value.is_active,
    })
    message.success('设置已保存')
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
  }
}

async function handleRegenerate() {
  if (!classId.value) return
  regenerating.value = true
  try {
    const res = await regenerateInviteCode(classId.value)
    config.value.invite_code = res.data.invite_code || res.data.code || config.value.invite_code
    message.success('邀请码已刷新')
    // Reload to get new code if response structure differs
    await loadConfig()
  } catch (e) {
    message.error(e.response?.data?.detail || '刷新失败')
  } finally {
    regenerating.value = false
  }
}

async function loadSemesters() {
  if (!classId.value) return
  try {
    const res = await getSemesters(classId.value)
    semesters.value = res.data.semesters || res.data || []
  } catch {
    semesters.value = []
  }
}

async function handleCreateSemester() {
  if (!semesterForm.value.name.trim()) {
    message.warning('请输入学期名称')
    return
  }
  creatingSemester.value = true
  try {
    const payload = { name: semesterForm.value.name }
    if (semesterForm.value.start_date) {
      payload.start_date = new Date(semesterForm.value.start_date).toISOString().split('T')[0]
    }
    if (semesterForm.value.end_date) {
      payload.end_date = new Date(semesterForm.value.end_date).toISOString().split('T')[0]
    }
    await createSemester(classId.value, payload)
    message.success('学期已创建')
    showCreateSemester.value = false
    semesterForm.value = { name: '', start_date: null, end_date: null }
    await loadSemesters()
  } catch (e) {
    message.error(e.response?.data?.detail || '创建失败')
  } finally {
    creatingSemester.value = false
  }
}

async function handleActivate(semId) {
  activating.value = semId
  try {
    await activateSemester(classId.value, semId)
    message.success('学期已激活')
    await loadSemesters()
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    activating.value = null
  }
}

onMounted(() => {
  if (classId.value) {
    loadConfig()
    loadSemesters()
  }
})
</script>
