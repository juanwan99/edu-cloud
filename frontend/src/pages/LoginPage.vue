<template>
  <div class="login-container">
    <div class="brand-area">
      <div class="brand-logo">
        <div class="logo-circle">
          <span class="logo-icon">E</span>
        </div>
      </div>
      <div class="brand-name">教育云平台</div>
      <div class="brand-subtitle">智慧校园管理系统</div>
    </div>

    <n-card style="max-width: 420px; width: 100%;" :bordered="false" class="login-card">
      <n-tabs v-model:value="activeTab" type="segment" animated style="margin-bottom: 20px;">
        <n-tab-pane name="teacher" tab="教师登录" />
        <n-tab-pane name="admin" tab="管理员登录" />
      </n-tabs>

      <n-alert v-if="error" type="error" :show-icon="true" closable style="margin-bottom: 16px;" @close="error = ''">
        {{ error }}
      </n-alert>

      <n-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
        <n-form-item label="用户名" path="username">
          <n-input v-model:value="form.username" placeholder="请输入用户名" :input-props="{ autocomplete: 'username' }" />
        </n-form-item>
        <n-form-item label="密码" path="password">
          <n-input v-model:value="form.password" type="password" placeholder="请输入密码" show-password-on="click" :input-props="{ autocomplete: 'current-password' }" @keyup.enter="handleLogin" />
        </n-form-item>

        <div style="margin-bottom: 16px;">
          <n-checkbox v-model:checked="rememberUsername">记住用户名</n-checkbox>
        </div>

        <n-button type="primary" block :loading="loading" @click="handleLogin">
          {{ loading ? '登录中...' : '登录' }}
        </n-button>
      </n-form>

      <div style="margin-top: 12px; text-align: center; font-size: 13px; color: rgba(255,255,255,0.35);">
        忘记密码？请联系管理员重置
      </div>
    </n-card>

    <div class="login-footer">
      &copy; {{ new Date().getFullYear() }} 教育云平台
    </div>

    <Transition name="login-success">
      <div v-if="showSuccess" class="success-overlay">
        <div class="success-icon">&#10003;</div>
        <div class="success-text">登录成功</div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { NCard, NForm, NFormItem, NInput, NButton, NCheckbox, NAlert, NTabs, NTabPane } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'

const REMEMBER_KEY = 'edu_remembered_username'

const authStore = useAuthStore()
const formRef = ref(null)
const activeTab = ref('teacher')
const loading = ref(false)
const error = ref('')
const rememberUsername = ref(false)
const showSuccess = ref(false)

const form = ref({
  username: '',
  password: '',
})

const rules = {
  username: { required: true, message: '请输入用户名', trigger: 'blur' },
  password: { required: true, message: '请输入密码', trigger: 'blur' },
}

onMounted(() => {
  const saved = localStorage.getItem(REMEMBER_KEY)
  if (saved) {
    form.value.username = saved
    rememberUsername.value = true
  }
})

async function handleLogin() {
  error.value = ''
  try {
    await formRef.value?.validate()
  } catch { return }

  loading.value = true
  try {
    await authStore.login(form.value.username, form.value.password)

    if (rememberUsername.value) {
      localStorage.setItem(REMEMBER_KEY, form.value.username)
    } else {
      localStorage.removeItem(REMEMBER_KEY)
    }

    showSuccess.value = true
  } catch (e) {
    const detail = e.response?.data?.detail
    if (e.response?.status === 401 || e.response?.status === 400) {
      error.value = detail || '用户名或密码错误'
    } else {
      error.value = detail || '登录失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

.brand-area {
  text-align: center;
  margin-bottom: 32px;
}

.brand-logo {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}

.logo-circle {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #63e2b7, #36d1a0);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 24px rgba(99, 226, 183, 0.3);
}

.logo-icon {
  font-size: 36px;
  font-weight: 800;
  color: #1a1a2e;
}

.brand-name {
  font-size: 28px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.95);
  margin-bottom: 4px;
}

.brand-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.45);
  letter-spacing: 4px;
}

.login-card {
  background: rgba(255, 255, 255, 0.05) !important;
  backdrop-filter: blur(10px);
  border-radius: 16px !important;
}

.login-footer {
  margin-top: 40px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.25);
}

.success-overlay {
  position: fixed;
  inset: 0;
  background: rgba(26, 26, 46, 0.95);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

.success-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #63e2b7;
  color: #1a1a2e;
  font-size: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.success-text {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.9);
}

.login-success-enter-active { transition: opacity 0.3s ease; }
.login-success-enter-from { opacity: 0; }
.login-success-leave-active { transition: opacity 0.2s ease; }
.login-success-leave-to { opacity: 0; }
</style>
