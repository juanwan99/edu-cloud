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
          <img src="../assets/images/logo.svg" alt="微与积" width="64" height="64" />
        </div>
        <h1 class="brand-name">微与积</h1>
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
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#6B7A90" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              </template>
            </n-input>
          </n-form-item>
          <n-form-item path="password">
            <n-input v-model:value="form.password" type="password" placeholder="请输入密码…" size="large" show-password-on="click" :input-props="{ autocomplete: 'current-password' }" @keyup.enter="handleLogin">
              <template #prefix>
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#6B7A90" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
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
        &copy; {{ new Date().getFullYear() }} 微与积 · 智能教育云平台
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
  background:
    radial-gradient(900px 500px at 12% -10%, #ffffff 0%, #F3F7FF 55%, transparent 70%),
    linear-gradient(165deg, #F7F9FD 0%, #EEF3FF 100%);
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

/* 装饰 — 柔和几何，不花哨 */
.decor {
  position: absolute;
  border-radius: 50%;
  animation: floatSlow 24s ease-in-out infinite;
}

.decor--mint {
  width: 520px;
  height: 520px;
  top: -200px;
  right: -180px;
  background: radial-gradient(circle, rgba(31,91,215,0.06) 0%, transparent 70%);
}

.decor--cream {
  width: 400px;
  height: 400px;
  bottom: -180px;
  left: -140px;
  background: radial-gradient(circle, rgba(31,91,215,0.04) 0%, transparent 70%);
  animation-delay: -8s;
}

.decor--pink-ring {
  width: 60px;
  height: 60px;
  bottom: 30%;
  right: 10%;
  background: transparent;
  border: 2px solid rgba(31,91,215,0.1);
  animation-delay: -16s;
}

.decor--lavender {
  width: 48px;
  height: 48px;
  top: 18%;
  left: 8%;
  background: transparent;
  border: 2px solid rgba(31,91,215,0.08);
  border-radius: 12px;
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
  font-size: 48px;
  font-weight: 800;
  color: #111C33;
  letter-spacing: -0.035em;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.brand-subtitle {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #6B7A90;
  margin-top: 6px;
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
  border-radius: 12px !important;
  margin-top: 4px;
  background: #1F5BD7 !important;
  border-color: #1F5BD7 !important;
  box-shadow: 0 8px 24px rgba(31, 91, 215, 0.25);
}

.login-btn:hover {
  background: #1849B0 !important;
  border-color: #1849B0 !important;
  box-shadow: 0 8px 24px rgba(31, 91, 215, 0.35);
}

.login-hint {
  margin-top: 20px;
  text-align: center;
  font-size: var(--fs-base);
  color: #6B7A90;
}

.login-footer {
  margin-top: 56px;
  font-size: var(--fs-base);
  color: #6B7A90;
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
  background: #1F5BD7;
  color: #fff;
  font-size: var(--fs-display);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.success-text {
  font-size: var(--fs-xl);
  font-weight: var(--fw-semibold);
  color: #1F5BD7;
}

.login-success-enter-active { transition: opacity 0.3s ease; }
.login-success-enter-from { opacity: 0; }
.login-success-leave-active { transition: opacity 0.2s ease; }
.login-success-leave-to { opacity: 0; }
</style>
