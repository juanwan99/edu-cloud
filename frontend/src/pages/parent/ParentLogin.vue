<template>
  <div class="login-container">
    <!-- Brand area -->
    <div class="brand-area">
      <div class="brand-logo">
        <div class="logo-circle">
          <span class="logo-icon">E</span>
        </div>
      </div>
      <div class="brand-name">教育云平台</div>
      <div class="brand-subtitle">家校互通</div>
    </div>

    <n-card style="max-width: 400px; width: 100%;" :bordered="false" class="login-card">
      <!-- Error alert -->
      <n-alert v-if="loginError" type="error" :show-icon="true" closable style="margin-bottom: 16px;" @close="loginError = ''">
        {{ loginError }}
      </n-alert>

      <n-form ref="formRef" :model="form" :rules="rules">
        <n-form-item label="手机号" path="phone">
          <n-input v-model:value="form.phone" placeholder="请输入手机号" maxlength="11" />
        </n-form-item>
        <n-form-item label="密码" path="password">
          <n-input v-model:value="form.password" type="password" placeholder="请输入密码" show-password-on="click" @keyup.enter="handleLogin" />
        </n-form-item>

        <div style="margin-bottom: 16px;">
          <n-checkbox v-model:checked="rememberPhone">记住手机号</n-checkbox>
        </div>

        <n-button type="primary" block :loading="loading" @click="handleLogin">
          {{ loading ? '登录中...' : '登录' }}
        </n-button>
      </n-form>

      <div style="margin-top: 16px; text-align: center;">
        <router-link to="/parent/register" style="color: #63e2b7;">还没有账号？立即注册</router-link>
      </div>
      <div style="margin-top: 12px; text-align: center; font-size: 13px; color: rgba(255,255,255,0.35);">
        忘记密码？请联系班主任重置
      </div>
    </n-card>

    <!-- Footer -->
    <div class="login-footer">
      &copy; {{ new Date().getFullYear() }} 教育云平台
    </div>

    <!-- Success overlay -->
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
import { useRouter } from 'vue-router'
import { NCard, NForm, NFormItem, NInput, NButton, NCheckbox, NAlert } from 'naive-ui'
import { parentLogin } from '../../api/conduct'

const REMEMBER_KEY = 'parent_remembered_phone'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const loginError = ref('')
const rememberPhone = ref(false)
const showSuccess = ref(false)

const form = ref({
  phone: '',
  password: '',
})

const rules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' },
  ],
  password: { required: true, message: '请输入密码', trigger: 'blur' },
}

onMounted(() => {
  const saved = localStorage.getItem(REMEMBER_KEY)
  if (saved) {
    form.value.phone = saved
    rememberPhone.value = true
  }
})

async function handleLogin() {
  loginError.value = ''
  try {
    await formRef.value?.validate()
  } catch { return }

  loading.value = true
  try {
    const res = await parentLogin(form.value)
    localStorage.setItem('cp_token', res.data.access_token)

    // Handle remember phone
    if (rememberPhone.value) {
      localStorage.setItem(REMEMBER_KEY, form.value.phone)
    } else {
      localStorage.removeItem(REMEMBER_KEY)
    }

    // Show success animation then navigate
    showSuccess.value = true
    setTimeout(() => {
      router.push('/parent')
    }, 300)
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 401 || err.response?.status === 400) {
      loginError.value = detail || '手机号或密码错误，请重试'
    } else {
      loginError.value = detail || '登录失败，请稍后重试'
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
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #63e2b7, #36d1a0);
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-icon {
  font-size: 32px;
  font-weight: 800;
  color: #1a1a2e;
}

.brand-name {
  font-size: 24px;
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

.login-success-enter-active {
  transition: opacity 0.3s ease;
}

.login-success-enter-from {
  opacity: 0;
}

.login-success-leave-active {
  transition: opacity 0.2s ease;
}

.login-success-leave-to {
  opacity: 0;
}
</style>
