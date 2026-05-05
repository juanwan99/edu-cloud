<template>
  <div class="login-container">
    <div class="login-content">
      <!-- 左侧品牌面板 -->
      <div class="login-brand">
        <div class="brand-inner">
          <div class="brand-icon">
            <img src="../assets/images/logo.png" alt="微与积" width="72" height="72" />
          </div>
          <h1 class="brand-name">微与积</h1>
          <p class="brand-subtitle">智能教育云平台</p>
          <div class="brand-features">
            <div class="feature-item">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
              <span>AI 智能阅卷</span>
            </div>
            <div class="feature-item">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/></svg>
              <span>多维成绩分析</span>
            </div>
            <div class="feature-item">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
              <span>多校协同管理</span>
            </div>
          </div>
        </div>
        <div class="brand-footer">&copy; {{ new Date().getFullYear() }} 微与积</div>
      </div>

      <!-- 右侧表单 -->
      <div class="login-form-panel">
        <div class="form-inner">
          <h2 class="form-title">欢迎回来</h2>
          <p class="form-desc">登录你的账户以继续</p>

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
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#A0A0A8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                </template>
              </n-input>
            </n-form-item>
            <n-form-item path="password">
              <n-input v-model:value="form.password" type="password" placeholder="请输入密码…" size="large" show-password-on="click" :input-props="{ autocomplete: 'current-password' }" @keyup.enter="handleLogin">
                <template #prefix>
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#A0A0A8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
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
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(900px 500px at 12% -10%, #ffffff 0%, #F3F7FF 55%, transparent 70%),
    linear-gradient(165deg, #F7F9FD 0%, #EEF3FF 100%);
  padding: 24px;
}

.login-content {
  display: flex;
  width: min(960px, 100%);
  min-height: 580px;
  border-radius: 24px;
  overflow: hidden;
  box-shadow:
    0 28px 70px rgba(100, 76, 240, 0.10),
    0 8px 20px rgba(100, 76, 240, 0.06);
}

/* 左侧品牌面板 */
.login-brand {
  width: 380px;
  flex-shrink: 0;
  background: linear-gradient(160deg, #09061B 0%, #12102a 50%, #1A1540 100%);
  color: #fff;
  padding: 48px 40px 32px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.login-brand::before {
  content: '';
  position: absolute;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(100, 76, 240, 0.2) 0%, transparent 70%);
  top: -80px;
  right: -80px;
}

.login-brand::after {
  content: '';
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(244, 218, 76, 0.08) 0%, transparent 70%);
  bottom: -60px;
  left: -40px;
}

.brand-inner {
  position: relative;
  z-index: 1;
}

.brand-icon {
  margin-bottom: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 96px;
  height: 96px;
  border-radius: 22px;
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.brand-name {
  font-size: 36px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.03em;
  margin: 0 0 8px;
}

.brand-subtitle {
  font-size: 14px;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 48px;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
}

.feature-item svg {
  opacity: 0.5;
  flex-shrink: 0;
}

.brand-footer {
  position: relative;
  z-index: 1;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
}

/* 右侧表单面板 */
.login-form-panel {
  flex: 1;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.form-inner {
  width: 100%;
  max-width: 360px;
}

.form-title {
  font-size: 26px;
  font-weight: 800;
  color: var(--color-text);
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}

.form-desc {
  font-size: 14px;
  color: var(--color-text-muted);
  margin-bottom: 32px;
}

.login-tabs {
  margin-bottom: 28px;
}

.login-btn {
  height: 50px;
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  letter-spacing: 3px;
  border-radius: 12px !important;
  margin-top: 4px;
  background: #644CF0 !important;
  border-color: #644CF0 !important;
  box-shadow: 0 8px 24px rgba(100, 76, 240, 0.25);
  transition: all 0.2s;
}

.login-btn:hover {
  background: #4F3EC9 !important;
  border-color: #4F3EC9 !important;
  box-shadow: 0 8px 24px rgba(100, 76, 240, 0.35);
  transform: translateY(-1px);
}

.login-hint {
  margin-top: 24px;
  text-align: center;
  font-size: 14px;
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
  z-index: var(--z-overlay, 200);
}

.success-check {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #644CF0;
  color: #fff;
  font-size: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.success-text {
  font-size: 20px;
  font-weight: 600;
  color: #644CF0;
}

.login-success-enter-active { transition: opacity 0.3s ease; }
.login-success-enter-from { opacity: 0; }
.login-success-leave-active { transition: opacity 0.2s ease; }
.login-success-leave-to { opacity: 0; }

@media (max-width: 768px) {
  .login-content { flex-direction: column; min-height: auto; }
  .login-brand { width: 100%; padding: 32px 28px 24px; }
  .brand-features { display: none; }
  .login-form-panel { padding: 32px 24px; }
}
</style>
