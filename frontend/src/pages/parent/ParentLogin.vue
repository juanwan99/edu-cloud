<template>
  <div class="login-container">
    <div class="decor decor--mint" />
    <div class="decor decor--cream" />
    <div class="decor decor--pink-ring" />
    <div class="decor decor--lavender" />

    <div class="login-content">
      <div class="brand-area">
        <div class="brand-icon">
          <svg viewBox="0 0 48 48" width="48" height="48" fill="none">
            <path d="M24 6L4 16l20 10 20-10L24 6z" fill="#2d5a3d" opacity="0.3"/>
            <path d="M24 12L4 22l20 10 20-10L24 12z" fill="#2d5a3d" opacity="0.6"/>
            <path d="M24 18L4 28l20 10 20-10L24 18z" fill="#1a2e1f"/>
          </svg>
        </div>
        <h1 class="brand-name">edu-cloud</h1>
        <p class="brand-subtitle">家校互通</p>
      </div>

      <div class="login-form-area">
        <n-alert v-if="loginError" type="error" :show-icon="true" closable style="margin-bottom: 16px;" @close="loginError = ''">
          {{ loginError }}
        </n-alert>

        <n-form ref="formRef" :model="form" :rules="rules" :show-label="false">
          <n-form-item path="phone">
            <n-input v-model:value="form.phone" placeholder="请输入手机号" maxlength="11" size="large">
              <template #prefix>
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#8a9a8e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
              </template>
            </n-input>
          </n-form-item>
          <n-form-item path="password">
            <n-input v-model:value="form.password" type="password" placeholder="请输入密码" size="large" show-password-on="click" @keyup.enter="handleLogin">
              <template #prefix>
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#8a9a8e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              </template>
            </n-input>
          </n-form-item>

          <div style="margin-bottom: 20px;">
            <n-checkbox v-model:checked="rememberPhone">记住手机号</n-checkbox>
          </div>

          <n-button type="primary" block :loading="loading" @click="handleLogin" class="login-btn" size="large">
            {{ loading ? '登录中...' : '登 录' }}
          </n-button>
        </n-form>

        <div style="margin-top: 20px; text-align: center;">
          <router-link to="/parent/register" class="register-link">还没有账号？立即注册</router-link>
        </div>
        <div class="login-hint">
          忘记密码？请联系班主任重置
        </div>
      </div>

      <div class="login-footer">
        &copy; {{ new Date().getFullYear() }} edu-cloud · 教育云平台
      </div>
    </div>

    <Transition name="login-success">
      <div v-if="showSuccess" class="success-overlay">
        <div class="success-check">&#10003;</div>
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
  min-height: 100dvh;
  position: relative;
  overflow: hidden;
  background: #ffffff;
}

.login-content {
  position: relative;
  z-index: 1;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
}

.decor {
  position: absolute;
  border-radius: 50%;
  animation: floatSlow 24s ease-in-out infinite;
}

.decor--mint {
  width: 620px;
  height: 620px;
  top: -180px;
  right: -160px;
  background: #e8f8ee;
}

.decor--cream {
  width: 480px;
  height: 480px;
  bottom: -160px;
  left: -120px;
  background: #fef3c7;
  opacity: 0.6;
  animation-delay: -8s;
}

.decor--pink-ring {
  width: 80px;
  height: 80px;
  bottom: 30%;
  right: 8%;
  background: transparent;
  border: 3px solid #fde8e8;
  animation-delay: -16s;
}

.decor--lavender {
  width: 60px;
  height: 60px;
  top: 18%;
  left: 6%;
  background: transparent;
  border: 3px solid #ede9fe;
  border-radius: 8px;
  animation-delay: -12s;
}

@keyframes floatSlow {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(12px, -18px); }
  66% { transform: translate(-8px, 12px); }
}

.brand-area {
  text-align: center;
  margin-bottom: 40px;
}

.brand-icon {
  margin-bottom: 16px;
}

.brand-name {
  font-size: 28px;
  font-weight: 800;
  color: #1a2e1f;
  letter-spacing: -0.02em;
  margin: 0;
}

.brand-subtitle {
  font-size: 16px;
  color: #8a9a8e;
  margin-top: 6px;
}

.login-form-area {
  max-width: 400px;
  width: 100%;
}

.login-btn {
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 3px;
  border-radius: 12px !important;
  margin-top: 4px;
}

.register-link {
  color: #2d5a3d;
  font-weight: 500;
  transition: color 0.2s;
}

.register-link:hover {
  color: #1a2e1f;
}

.login-hint {
  margin-top: 12px;
  text-align: center;
  font-size: 16px;
  color: #8a9a8e;
}

.login-footer {
  margin-top: 56px;
  font-size: 16px;
  color: #b0b8b2;
}

.success-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.96);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: var(--z-overlay);
}

.success-check {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--color-primary, #1a2e1f);
  color: var(--color-bg, #fff);
  font-size: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.success-text {
  font-size: 18px;
  font-weight: 600;
  color: #1a2e1f;
}

.login-success-enter-active { transition: opacity 0.3s ease; }
.login-success-enter-from { opacity: 0; }
.login-success-leave-active { transition: opacity 0.2s ease; }
.login-success-leave-to { opacity: 0; }
</style>
