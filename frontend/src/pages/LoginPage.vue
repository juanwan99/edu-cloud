<template>
  <div class="login-container">
    <!-- 装饰圆（实心、有边界感） -->
    <div class="decor decor--mint" />
    <div class="decor decor--cream" />
    <div class="decor decor--pink-ring" />
    <div class="decor decor--lavender" />

    <div class="login-content">
      <!-- 品牌区 -->
      <div class="brand-area">
        <div class="brand-icon">
          <svg viewBox="0 0 48 48" width="48" height="48" fill="none">
            <path d="M24 6L4 16l20 10 20-10L24 6z" fill="#2d5a3d" opacity="0.3"/>
            <path d="M24 12L4 22l20 10 20-10L24 12z" fill="#2d5a3d" opacity="0.6"/>
            <path d="M24 18L4 28l20 10 20-10L24 18z" fill="#1a2e1f"/>
          </svg>
        </div>
        <h1 class="brand-name">edu-cloud</h1>
        <p class="brand-subtitle">智能教育云平台</p>
      </div>

      <!-- 表单区（无卡片包裹） -->
      <div class="login-form-area">
        <n-tabs v-model:value="activeTab" type="segment" animated class="login-tabs">
          <n-tab-pane name="teacher" tab="教师登录" />
          <n-tab-pane name="admin" tab="管理员登录" />
        </n-tabs>

        <n-alert v-if="error" type="error" :show-icon="true" closable style="margin-bottom: 16px;" @close="error = ''">
          {{ error }}
        </n-alert>

        <n-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin" :show-label="false">
          <n-form-item path="username">
            <n-input v-model:value="form.username" placeholder="请输入用户名…" size="large" :input-props="{ autocomplete: 'username' }">
              <template #prefix>
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#8a9a8e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              </template>
            </n-input>
          </n-form-item>
          <n-form-item path="password">
            <n-input v-model:value="form.password" type="password" placeholder="请输入密码…" size="large" show-password-on="click" :input-props="{ autocomplete: 'current-password' }" @keyup.enter="handleLogin">
              <template #prefix>
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#8a9a8e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              </template>
            </n-input>
          </n-form-item>

          <div style="margin-bottom: 20px;">
            <n-checkbox v-model:checked="rememberUsername">记住用户名</n-checkbox>
          </div>

          <n-button type="primary" block :loading="loading" @click="handleLogin" class="login-btn" size="large">
            {{ loading ? '登录中...' : '登 录' }}
          </n-button>
        </n-form>

        <div class="login-hint">
          忘记密码？请联系管理员重置
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
  min-height: 100dvh;
  position: relative;
  overflow: hidden;
  background: var(--color-bg);
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

/* 装饰圆 — 实心、有边界感 */
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
  background: var(--macaron-mint-light);
}

.decor--cream {
  width: 480px;
  height: 480px;
  bottom: -160px;
  left: -120px;
  background: var(--macaron-yellow);
  opacity: 0.6;
  animation-delay: -8s;
}

.decor--pink-ring {
  width: 80px;
  height: 80px;
  bottom: 30%;
  right: 8%;
  background: transparent;
  border: 3px solid var(--macaron-coral);
  animation-delay: -16s;
}

.decor--lavender {
  width: 60px;
  height: 60px;
  top: 18%;
  left: 6%;
  background: transparent;
  border: 3px solid var(--macaron-purple);
  border-radius: 8px;
  animation-delay: -12s;
}

@keyframes floatSlow {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(12px, -18px); }
  66% { transform: translate(-8px, 12px); }
}

/* 品牌区 */
.brand-area {
  text-align: center;
  margin-bottom: 40px;
}

.brand-icon {
  margin-bottom: 16px;
}

.brand-name {
  font-size: var(--fs-display);
  font-weight: var(--fw-semibold);
  color: var(--color-primary);
  letter-spacing: -0.02em;
  margin: 0;
}

.brand-subtitle {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  margin-top: 6px;
  letter-spacing: 0.04em;
}

/* 表单区 */
.login-form-area {
  max-width: 400px;
  width: 100%;
}

.login-tabs {
  margin-bottom: 32px;
}

.login-btn {
  height: 50px;
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  letter-spacing: 3px;
  border-radius: var(--r-lg) !important;
  margin-top: 4px;
  background: linear-gradient(135deg, var(--color-success) 0%, #059669 100%) !important;
  box-shadow: 0 4px 14px rgba(16,185,129,0.3);
}

.login-hint {
  margin-top: 20px;
  text-align: center;
  font-size: var(--fs-base);
  color: var(--color-text-muted);
}

.login-footer {
  margin-top: 56px;
  font-size: var(--fs-base);
  color: var(--color-text-muted);
}

/* 成功遮罩 */
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
  background: var(--color-primary);
  color: var(--color-bg, #fff);
  font-size: var(--fs-display);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.success-text {
  font-size: var(--fs-xl);
  font-weight: var(--fw-semibold);
  color: var(--color-primary);
}

.login-success-enter-active { transition: opacity 0.3s ease; }
.login-success-enter-from { opacity: 0; }
.login-success-leave-active { transition: opacity 0.2s ease; }
.login-success-leave-to { opacity: 0; }
</style>
