<template>
  <div class="login-container">
    <div class="login-decor login-decor--1" />
    <div class="login-decor login-decor--2" />
    <div class="login-decor login-decor--3" />

    <div class="login-content">
      <div class="brand-area">
        <div class="logo-circle">
          <span class="logo-icon">E</span>
        </div>
        <div class="brand-name">教育云平台</div>
        <div class="brand-subtitle">家 校 互 通</div>
      </div>

      <n-card class="login-card" :bordered="false">
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

          <div style="margin-bottom: 20px;">
            <n-checkbox v-model:checked="rememberPhone">记住手机号</n-checkbox>
          </div>

          <n-button type="primary" block :loading="loading" @click="handleLogin" class="login-btn">
            {{ loading ? '登录中...' : '登 录' }}
          </n-button>
        </n-form>

        <div style="margin-top: 16px; text-align: center;">
          <router-link to="/parent/register" class="register-link">还没有账号？立即注册</router-link>
        </div>
        <div class="login-hint">
          忘记密码？请联系班主任重置
        </div>
      </n-card>

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
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background: #f9fafb;
}

.login-content {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
}

.login-decor {
  position: absolute;
  border-radius: 50%;
  animation: floatSlow 20s ease-in-out infinite;
}

.login-decor--1 {
  width: 500px;
  height: 500px;
  top: -120px;
  right: -100px;
  background: radial-gradient(circle, #e8f8ee 0%, transparent 70%);
}

.login-decor--2 {
  width: 400px;
  height: 400px;
  bottom: -80px;
  left: -60px;
  background: radial-gradient(circle, #fef3c7 0%, transparent 70%);
  animation-delay: -7s;
}

.login-decor--3 {
  width: 200px;
  height: 200px;
  top: 40%;
  left: 10%;
  background: radial-gradient(circle, #ede9fe 0%, transparent 70%);
  animation-delay: -13s;
}

@keyframes floatSlow {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(15px, -20px); }
  66% { transform: translate(-10px, 15px); }
}

.brand-area {
  text-align: center;
  margin-bottom: 36px;
}

.logo-circle {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1a2e1f, #2d5a3d);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  box-shadow: 0 8px 24px rgba(26, 46, 31, 0.15);
}

.logo-icon {
  font-size: 30px;
  font-weight: 800;
  color: #fff;
}

.brand-name {
  font-size: 24px;
  font-weight: 800;
  color: #1a2e1f;
  letter-spacing: -0.02em;
  margin-bottom: 4px;
}

.brand-subtitle {
  font-size: 13px;
  color: #8a9a8e;
  letter-spacing: 3px;
}

.login-card {
  max-width: 400px;
  width: 100%;
  background: #ffffff !important;
  border-radius: 20px !important;
  box-shadow: 0 4px 24px rgba(26, 46, 31, 0.06);
  padding: 8px 4px;
}

.login-btn {
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
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
  font-size: 13px;
  color: #8a9a8e;
}

.login-footer {
  margin-top: 48px;
  font-size: 12px;
  color: #8a9a8e;
}

.success-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

.success-check {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1a2e1f, #2d5a3d);
  color: #fff;
  font-size: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  box-shadow: 0 8px 24px rgba(26, 46, 31, 0.15);
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
