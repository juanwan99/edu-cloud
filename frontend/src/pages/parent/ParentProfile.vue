<template>
  <div>
    <!-- Avatar header -->
    <div class="profile-header">
      <div class="profile-avatar" :style="{ background: avatarColor }">
        {{ avatarLetter }}
      </div>
      <div class="profile-name">{{ parentInfo?.display_name || '家长' }}</div>
      <div class="profile-phone">{{ maskedPhone }}</div>
    </div>

    <!-- Bound children -->
    <div class="p-card">
      <div class="p-card__header">
        <span class="p-card__title">已绑定孩子</span>
      </div>
      <div v-for="child in childrenList" :key="child.student_id" class="child-row">
        <div class="child-row__avatar" :style="{ background: childColor(child.student_name) }">
          {{ child.student_name?.charAt(0) || '?' }}
        </div>
        <div class="child-row__info">
          <div class="child-row__name">{{ child.student_name }}</div>
          <div class="child-row__class">{{ child.class_name || '未分配班级' }}</div>
        </div>
      </div>
      <n-button block dashed style="margin-top: 12px;" @click="$router.push('/parent/bind')">
        <template #icon><UserPlus :size="16" /></template>
        绑定孩子
      </n-button>
    </div>

    <!-- Settings -->
    <div class="p-card">
      <div class="settings-item" @click="showThemeModal = true">
        <Palette :size="20" class="settings-item__icon" />
        <span class="settings-item__label">外观模式</span>
        <span class="settings-item__value">{{ themeLabel }}</span>
        <ChevronRight :size="16" class="settings-item__arrow" />
      </div>
      <div class="settings-item" @click="showPasswordForm = !showPasswordForm">
        <Key :size="20" class="settings-item__icon" />
        <span class="settings-item__label">修改密码</span>
        <ChevronRight :size="16" class="settings-item__arrow" />
      </div>
    </div>

    <!-- Password form (collapsible) -->
    <div class="p-card" v-if="showPasswordForm">
      <n-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules">
        <n-form-item label="旧密码" path="old_password">
          <n-input v-model:value="pwdForm.old_password" type="password" show-password-on="click" placeholder="输入旧密码" />
        </n-form-item>
        <n-form-item label="新密码" path="new_password">
          <n-input v-model:value="pwdForm.new_password" type="password" show-password-on="click" placeholder="至少6位" />
        </n-form-item>
        <n-form-item label="确认密码" path="confirm_password">
          <n-input v-model:value="pwdForm.confirm_password" type="password" show-password-on="click" placeholder="再次输入" />
        </n-form-item>
        <n-button type="primary" block :loading="pwdLoading" @click="handleChangePassword">
          确认修改
        </n-button>
      </n-form>
    </div>

    <!-- Theme selector modal -->
    <n-modal v-model:show="showThemeModal" preset="card" title="外观模式" style="max-width: 320px;">
      <n-radio-group v-model:value="themeValue" class="theme-options">
        <n-radio value="dark" label="深色" />
        <n-radio value="light" label="浅色" />
        <n-radio value="system" label="跟随系统" />
      </n-radio-group>
    </n-modal>

    <!-- Logout -->
    <div class="p-card" style="margin-top: var(--p-space-5);">
      <n-popconfirm @positive-click="handleLogout">
        <template #trigger>
          <div class="settings-item settings-item--danger">
            <LogOut :size="20" class="settings-item__icon" />
            <span class="settings-item__label">退出登录</span>
          </div>
        </template>
        确定退出登录？
      </n-popconfirm>
    </div>

    <!-- Version -->
    <div class="profile-version">家校互通 v1.0</div>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton, NForm, NFormItem, NInput, NRadioGroup, NRadio,
  NPopconfirm, NModal, useMessage
} from 'naive-ui'
import { ChevronRight, Key, LogOut, UserPlus, Palette } from 'lucide-vue-next'
import { changeParentPassword, getParentMe } from '../../api/conduct'

const router = useRouter()
const message = useMessage()

const children = inject('children', ref([]))
const parentTheme = inject('parentTheme', ref('dark'))
const setParentTheme = inject('setParentTheme', () => {})

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const parentInfo = ref(null)
const childrenList = computed(() => children.value || [])
const showPasswordForm = ref(false)
const showThemeModal = ref(false)
const pwdLoading = ref(false)

const themeValue = computed({
  get: () => parentTheme.value,
  set: (v) => { setParentTheme(v); showThemeModal.value = false },
})

const themeLabel = computed(() => {
  const map = { dark: '深色', light: '浅色', system: '跟随系统' }
  return map[parentTheme.value] || '深色'
})

const avatarLetter = computed(() => parentInfo.value?.display_name?.charAt(0) || '家')
const avatarColor = computed(() => {
  const name = parentInfo.value?.display_name || ''
  const colors = ['#F4DA4C', '#644CF0', '#ED9A51', '#22C55E', '#8B7AF5']
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
})

const maskedPhone = computed(() => {
  const phone = parentInfo.value?.phone || ''
  if (phone.length >= 7) return phone.slice(0, 3) + '****' + phone.slice(-4)
  return '***'
})

function childColor(name) {
  const colors = ['#F4DA4C', '#644CF0', '#ED9A51', '#22C55E', '#8B7AF5']
  let hash = 0
  for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
}

const pwdForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const pwdRules = {
  old_password: { required: true, message: '请输入旧密码' },
  new_password: { required: true, message: '请输入新密码', min: 6 },
  confirm_password: {
    required: true,
    validator: (_, v) => v === pwdForm.value.new_password ? true : new Error('两次密码不一致'),
  },
}

async function handleChangePassword() {
  pwdLoading.value = true
  try {
    await changeParentPassword({
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })
    message.success('密码修改成功')
    showPasswordForm.value = false
    pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
  } catch (err) {
    message.error(err.response?.data?.detail || '修改失败')
  } finally {
    pwdLoading.value = false
  }
}

function handleLogout() {
  localStorage.removeItem('cp_token')
  router.replace('/parent/login')
}

onMounted(async () => {
  try {
    const res = await getParentMe()
    parentInfo.value = res.data
  } catch {}
})
</script>

<style scoped>
.profile-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--p-space-6) 0 var(--p-space-5);
}
.profile-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 700;
  color: #09061B;
}
.profile-name { font-size: var(--p-fs-page-title); font-weight: 700; color: var(--p-text-1); margin-top: var(--p-space-3); }
.profile-phone { font-size: var(--p-fs-label); color: var(--p-text-3); margin-top: var(--p-space-1); }

.p-card {
  background: var(--p-card-bg);
  border: var(--p-card-border);
  box-shadow: var(--p-card-shadow);
  border-radius: var(--p-card-radius);
  padding: var(--p-card-padding);
  margin-bottom: var(--p-space-5);
}
.p-card__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--p-space-3); }
.p-card__title { font-size: var(--p-fs-section); font-weight: 600; color: var(--p-text-1); }

.child-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--p-border); }
.child-row:last-of-type { border-bottom: none; }
.child-row__avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 600; color: #09061B; flex-shrink: 0; }
.child-row__info { flex: 1; }
.child-row__name { font-size: var(--p-fs-body); color: var(--p-text-1); }
.child-row__class { font-size: var(--p-fs-label); color: var(--p-text-3); margin-top: 2px; }

.settings-item { display: flex; align-items: center; gap: 12px; padding: 14px 0; cursor: pointer; border-bottom: 1px solid var(--p-border); min-height: 56px; }
.settings-item:last-child { border-bottom: none; }
.settings-item__icon { color: var(--p-text-3); flex-shrink: 0; }
.settings-item__label { flex: 1; font-size: var(--p-fs-body); color: var(--p-text-1); }
.settings-item__value { font-size: var(--p-fs-label); color: var(--p-text-3); }
.settings-item__arrow { color: var(--p-text-3); flex-shrink: 0; }
.settings-item--danger .settings-item__label { color: var(--p-color-error); }
.settings-item--danger .settings-item__icon { color: var(--p-color-error); }

.theme-options { display: flex; flex-direction: column; gap: 12px; }

.profile-version { text-align: center; font-size: var(--p-fs-label); color: var(--p-text-disabled); padding: var(--p-space-6) 0; }
</style>
