<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="authThemeOverrides">
    <div class="auth-page" data-theme="dark">
      <div class="auth-brand">
        <h1 class="auth-brand__title">家校互通</h1>
        <p class="auth-brand__sub">edu-cloud 教育云平台</p>
      </div>

      <div class="auth-card">
        <n-alert v-if="loginError" type="error" :show-icon="true" closable style="margin-bottom: var(--p-space-4);" @close="loginError = ''">
          {{ loginError }}
        </n-alert>

        <n-form ref="formRef" :model="form" :rules="rules" :show-label="false">
          <n-form-item path="phone">
            <n-input v-model:value="form.phone" placeholder="请输入手机号" maxlength="11" size="large">
              <template #prefix>
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--p-text-3)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
              </template>
            </n-input>
          </n-form-item>
          <n-form-item path="password">
            <n-input v-model:value="form.password" type="password" placeholder="请输入密码" size="large" show-password-on="click" @keyup.enter="handleLogin">
              <template #prefix>
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--p-text-3)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              </template>
            </n-input>
          </n-form-item>

          <div style="margin-bottom: var(--p-space-5);">
            <n-checkbox v-model:checked="rememberPhone">记住手机号</n-checkbox>
          </div>

          <n-button type="primary" block :loading="loading" @click="handleLogin" class="login-btn" size="large">
            {{ loading ? '登录中...' : '登 录' }}
          </n-button>
        </n-form>

        <div style="margin-top: var(--p-space-5); text-align: center;">
          <router-link to="/parent/register" class="register-link">还没有账号？立即注册</router-link>
        </div>
        <div class="login-hint">
          忘记密码？请联系班主任重置
        </div>
      </div>

      <div class="auth-footer">
        &copy; {{ new Date().getFullYear() }} edu-cloud · 教育云平台
      </div>

      <Transition name="login-success">
        <div v-if="showSuccess" class="success-overlay">
          <div class="success-check">&#10003;</div>
          <div class="success-text">登录成功</div>
        </div>
      </Transition>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { darkTheme } from 'naive-ui'
import { NConfigProvider, NForm, NFormItem, NInput, NButton, NCheckbox, NAlert } from 'naive-ui'
import { parentLogin } from '../../api/conduct'

const REMEMBER_KEY = 'parent_remembered_phone'

const authThemeOverrides = {
  common: {
    primaryColor: '#F4DA4C',
    primaryColorHover: '#E8CF40',
    primaryColorPressed: '#D4B830',
    primaryColorSuppl: '#F4DA4C',
    bodyColor: '#09061B',
    cardColor: '#181433',
    textColor1: '#F6F3FF',
    textColor2: '#C9C2DD',
    textColor3: '#9B93B5',
    borderColor: 'rgba(255,255,255,0.08)',
    inputColor: '#121026',
  },
}

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
.auth-page {
  min-height: 100dvh;
  background: var(--p-bg-base);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--p-space-6);
  font-family: var(--p-font);
}

.auth-brand {
  text-align: center;
  padding: 60px 0 40px;
}

.auth-brand__title {
  font-size: var(--p-fs-page-title);
  font-weight: 700;
  color: var(--p-text-1);
  margin: 0;
}

.auth-brand__sub {
  font-size: var(--p-fs-body);
  color: var(--p-text-3);
  margin-top: var(--p-space-2);
}

.auth-card {
  width: 100%;
  max-width: 400px;
  background: var(--p-card-bg);
  border: var(--p-card-border);
  border-radius: var(--p-card-radius);
  padding: var(--p-space-6);
}

.login-btn {
  height: 48px;
  font-size: var(--p-fs-body);
  font-weight: 600;
  letter-spacing: 3px;
  border-radius: var(--p-card-radius) !important;
  margin-top: 4px;
}

.register-link {
  color: var(--p-color-accent);
  font-weight: 500;
  transition: color 0.2s;
}

.register-link:hover {
  color: var(--p-color-accent-hover);
}

.login-hint {
  margin-top: 12px;
  text-align: center;
  font-size: var(--p-fs-body);
  color: var(--p-text-3);
}

.auth-footer {
  margin-top: 56px;
  font-size: var(--p-fs-body);
  color: var(--p-text-disabled);
}

.success-overlay {
  position: fixed;
  inset: 0;
  background: rgba(9, 6, 27, 0.96);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.success-check {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--p-color-accent-surface);
  color: var(--p-color-accent);
  font-size: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.success-text {
  font-size: var(--p-fs-section);
  font-weight: 600;
  color: var(--p-text-1);
}

.login-success-enter-active { transition: opacity 0.3s ease; }
.login-success-enter-from { opacity: 0; }
.login-success-leave-active { transition: opacity 0.2s ease; }
.login-success-leave-to { opacity: 0; }
</style>
