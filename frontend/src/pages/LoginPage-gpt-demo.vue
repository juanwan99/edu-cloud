<template>
  <div class="login-container">
    <div class="aurora aurora--mint" />
    <div class="aurora aurora--sun" />
    <div class="aurora aurora--blue" />
    <div class="mesh-grid" />

    <div class="decor decor--mint" />
    <div class="decor decor--cream" />
    <div class="decor decor--pink-ring" />
    <div class="decor decor--lavender" />
    <div class="decor decor--blue-dot" />
    <div class="decor decor--spark" />

    <main class="login-shell">
      <section class="hero-panel" aria-label="平台介绍">
        <div class="hero-glass">
          <div class="brand-area">
            <div class="brand-icon">
              <svg viewBox="0 0 72 72" width="72" height="72" fill="none" aria-hidden="true">
                <rect x="10" y="11" width="52" height="52" rx="18" fill="url(#brandGlow)" />
                <path d="M36 15L14 25.4l22 10.4 22-10.4L36 15z" fill="white" opacity="0.82" />
                <path d="M20 34.2l16 7.6 16-7.6v12.1c0 2.4-1.4 4.6-3.6 5.6l-9.8 4.6a6.2 6.2 0 0 1-5.2 0l-9.8-4.6a6.2 6.2 0 0 1-3.6-5.6V34.2z" fill="var(--color-primary)" opacity="0.9" />
                <path d="M58 27v15" stroke="white" stroke-width="3" stroke-linecap="round" opacity="0.86" />
                <circle cx="58" cy="47" r="4" fill="var(--macaron-yellow)" />
                <defs>
                  <linearGradient id="brandGlow" x1="13" y1="13" x2="61" y2="61" gradientUnits="userSpaceOnUse">
                    <stop stop-color="var(--color-accent)" />
                    <stop offset="0.56" stop-color="var(--color-primary-light)" />
                    <stop offset="1" stop-color="var(--color-primary)" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <div>
              <p class="brand-kicker">AI Powered Learning Cloud</p>
              <h1 class="brand-name">edu-cloud</h1>
              <p class="brand-subtitle">智能教育云平台</p>
            </div>
          </div>

          <div class="hero-copy">
            <div class="eyebrow">让教学数据像晨光一样清晰</div>
            <h2>连接课堂、测评与成长轨迹的一站式教育工作台</h2>
            <p>
              聚合班级管理、智能批改、学情洞察与家校协同，帮助老师把更多时间留给真正重要的教学陪伴。
            </p>
          </div>

          <div class="feature-board">
            <div class="feature-card feature-card--active">
              <span class="feature-icon">✦</span>
              <div>
                <strong>智能学情</strong>
                <small>实时汇总作业、考试与课堂表现</small>
              </div>
            </div>
            <div class="feature-card">
              <span class="feature-icon">⌁</span>
              <div>
                <strong>云端批改</strong>
                <small>AI 辅助评阅，过程全程可追溯</small>
              </div>
            </div>
            <div class="feature-card">
              <span class="feature-icon">◌</span>
              <div>
                <strong>成长档案</strong>
                <small>沉淀每位学生的个性化路径</small>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="login-panel" aria-label="登录表单">
        <n-card :bordered="false" class="login-card" content-style="padding: 0;">
          <div class="card-shine" />
          <div class="login-form-area">
            <div class="form-heading">
              <span class="status-pill">
                <span class="status-dot" />
                安全登录
              </span>
              <h2>欢迎回来</h2>
              <p>请选择身份并登录 edu-cloud 工作台</p>
            </div>

            <n-tabs v-model:value="activeTab" type="segment" animated class="login-tabs">
              <n-tab-pane name="teacher" tab="教师登录" />
              <n-tab-pane name="admin" tab="管理员登录" />
            </n-tabs>

            <n-alert v-if="error" type="error" :show-icon="true" closable class="error-alert" @close="error = ''">
              {{ error }}
            </n-alert>

            <n-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin" :show-label="false">
              <n-form-item path="username" class="form-item">
                <n-input v-model:value="form.username" placeholder="请输入用户名" size="large" :input-props="{ autocomplete: 'username' }" class="soft-input">
                  <template #prefix>
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  </template>
                </n-input>
              </n-form-item>

              <n-form-item path="password" class="form-item">
                <n-input v-model:value="form.password" type="password" placeholder="请输入密码" size="large" show-password-on="click" :input-props="{ autocomplete: 'current-password' }" class="soft-input" @keyup.enter="handleLogin">
                  <template #prefix>
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  </template>
                </n-input>
              </n-form-item>

              <div class="form-options">
                <n-checkbox v-model:checked="rememberUsername">记住用户名</n-checkbox>
                <span class="role-hint">{{ activeTab === 'teacher' ? '教师端入口' : '管理端入口' }}</span>
              </div>

              <n-button type="primary" block :loading="loading" @click="handleLogin" class="login-btn" size="large">
                <span>{{ loading ? '登录中...' : '登 录' }}</span>
              </n-button>
            </n-form>

            <div class="login-hint">
              忘记密码？请联系管理员重置
            </div>
          </div>
        </n-card>

        <div class="login-footer">
          &copy; {{ new Date().getFullYear() }} edu-cloud · 教育云平台
        </div>
      </section>
    </main>

    <Transition name="login-success">
      <div v-if="showSuccess" class="success-overlay">
        <div class="success-bloom" />
        <div class="success-card">
          <div class="success-check">&#10003;</div>
          <div class="success-text">登录成功</div>
          <p>正在进入智能教育云平台</p>
        </div>
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
  color: var(--color-text, #0f1a12);
  background:
    radial-gradient(circle at 10% 10%, rgba(200, 240, 212, 0.72), transparent 32%),
    radial-gradient(circle at 88% 18%, rgba(224, 242, 254, 0.85), transparent 30%),
    radial-gradient(circle at 48% 92%, rgba(254, 243, 199, 0.72), transparent 36%),
    linear-gradient(135deg, #fbfffc 0%, var(--color-bg, #ffffff) 42%, #f6fbf8 100%);
  isolation: isolate;
}

.login-container::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -3;
  background-image:
    linear-gradient(rgba(26, 46, 31, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(26, 46, 31, 0.035) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(circle at center, black 0%, transparent 72%);
}

.login-container::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -2;
  pointer-events: none;
  background: linear-gradient(120deg, rgba(255, 255, 255, 0.72), transparent 34%, rgba(255, 255, 255, 0.42));
}

.login-shell {
  position: relative;
  z-index: 2;
  width: min(1180px, calc(100% - 48px));
  min-height: 100dvh;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(390px, 0.72fr);
  align-items: center;
  gap: 56px;
  padding: 48px 0;
}

.hero-panel,
.login-panel {
  position: relative;
}

.hero-glass {
  position: relative;
  min-height: 640px;
  padding: 42px;
  border: 1px solid rgba(255, 255, 255, 0.74);
  border-radius: 36px;
  overflow: hidden;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.42)),
    linear-gradient(135deg, rgba(200, 240, 212, 0.46), rgba(237, 233, 254, 0.3));
  box-shadow: 0 32px 90px rgba(26, 46, 31, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(24px);
}

.hero-glass::before {
  content: "";
  position: absolute;
  width: 380px;
  height: 380px;
  right: -110px;
  top: -120px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(16, 185, 129, 0.22), transparent 66%);
}

.hero-glass::after {
  content: "";
  position: absolute;
  width: 260px;
  height: 260px;
  left: -90px;
  bottom: -80px;
  border-radius: 46px;
  transform: rotate(18deg);
  background: linear-gradient(135deg, rgba(254, 243, 199, 0.74), rgba(253, 232, 232, 0.56));
}

.brand-area {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 18px;
}

.brand-icon {
  width: 78px;
  height: 78px;
  display: grid;
  place-items: center;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 18px 45px rgba(16, 185, 129, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.brand-kicker {
  margin: 0 0 4px;
  font-size: var(--fs-xs, 12px);
  font-weight: var(--fw-semibold, 600);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-accent, #10b981);
}

.brand-name {
  margin: 0;
  font-size: clamp(36px, 5vw, 58px);
  line-height: 0.95;
  font-weight: 800;
  letter-spacing: -0.055em;
  color: var(--color-primary, #1a2e1f);
}

.brand-subtitle {
  margin: 10px 0 0;
  font-size: var(--fs-lg, 18px);
  color: var(--color-text-secondary, #3d4f42);
  letter-spacing: 0.08em;
}

.hero-copy {
  position: relative;
  z-index: 1;
  max-width: 620px;
  margin-top: 90px;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid rgba(16, 185, 129, 0.18);
  border-radius: var(--r-full, 999px);
  background: rgba(255, 255, 255, 0.66);
  color: var(--color-accent-hover, #059669);
  font-size: var(--fs-sm, 14px);
  font-weight: var(--fw-semibold, 600);
  box-shadow: 0 12px 30px rgba(26, 46, 31, 0.08);
}

.eyebrow::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-accent, #10b981);
  box-shadow: 0 0 0 6px rgba(16, 185, 129, 0.12);
}

.hero-copy h2 {
  margin: 22px 0 18px;
  font-size: clamp(34px, 5.2vw, 64px);
  line-height: 1.04;
  letter-spacing: -0.065em;
  color: var(--color-primary, #1a2e1f);
}

.hero-copy p {
  max-width: 540px;
  margin: 0;
  font-size: var(--fs-lg, 18px);
  line-height: 1.85;
  color: var(--color-text-secondary, #3d4f42);
}

.feature-board {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 78px;
}

.feature-card {
  min-height: 138px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border: 1px solid rgba(255, 255, 255, 0.68);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.54);
  box-shadow: 0 18px 38px rgba(26, 46, 31, 0.08);
  backdrop-filter: blur(18px);
  transition: transform 0.28s ease, box-shadow 0.28s ease;
}

.feature-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 24px 48px rgba(26, 46, 31, 0.12);
}

.feature-card--active {
  background: linear-gradient(145deg, rgba(26, 46, 31, 0.92), rgba(45, 90, 61, 0.86));
  color: white;
}

.feature-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: var(--macaron-mint, #c8f0d4);
  color: var(--color-primary, #1a2e1f);
  font-size: 20px;
}

.feature-card strong {
  display: block;
  margin-bottom: 6px;
  font-size: var(--fs-base, 16px);
}

.feature-card small {
  display: block;
  line-height: 1.55;
  color: var(--color-text-muted, #6b7d70);
}

.feature-card--active small {
  color: rgba(255, 255, 255, 0.72);
}

.login-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.login-card {
  position: relative;
  width: min(100%, 450px);
  overflow: hidden;
  border-radius: 34px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 34px 92px rgba(26, 46, 31, 0.18), 0 1px 0 rgba(255, 255, 255, 0.9) inset;
  backdrop-filter: blur(28px);
}

.login-card :deep(.n-card) {
  background: transparent;
}

.card-shine {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 18% 8%, rgba(200, 240, 212, 0.78), transparent 32%),
    radial-gradient(circle at 92% 18%, rgba(237, 233, 254, 0.62), transparent 30%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.42));
}

.login-form-area {
  position: relative;
  z-index: 1;
  padding: 34px;
}

.form-heading {
  margin-bottom: 26px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--r-full, 999px);
  background: rgba(236, 253, 245, 0.86);
  color: var(--color-success-text, #047857);
  font-size: var(--fs-sm, 14px);
  font-weight: var(--fw-semibold, 600);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-accent, #10b981);
  box-shadow: 0 0 0 6px rgba(16, 185, 129, 0.14);
}

.form-heading h2 {
  margin: 18px 0 8px;
  font-size: var(--fs-display, 32px);
  line-height: 1.12;
  font-weight: 780;
  letter-spacing: -0.04em;
  color: var(--color-primary, #1a2e1f);
}

.form-heading p {
  margin: 0;
  color: var(--color-text-muted, #6b7d70);
  font-size: var(--fs-base, 16px);
}

.login-tabs {
  margin-bottom: 24px;
}

.login-tabs :deep(.n-tabs-rail) {
  padding: 6px;
  border-radius: 18px;
  background: rgba(245, 248, 246, 0.84);
  box-shadow: inset 0 0 0 1px rgba(212, 221, 215, 0.58);
}

.login-tabs :deep(.n-tabs-capsule) {
  border-radius: 14px;
  background: linear-gradient(135deg, var(--color-primary, #1a2e1f), var(--color-primary-light, #2d5a3d));
  box-shadow: 0 12px 28px rgba(26, 46, 31, 0.18);
}

.login-tabs :deep(.n-tabs-tab) {
  height: 42px;
  border-radius: 14px;
  font-weight: var(--fw-semibold, 600);
}

.error-alert {
  margin-bottom: 18px;
  border-radius: 16px;
  overflow: hidden;
}

.form-item {
  margin-bottom: 18px;
}

.soft-input {
  color: var(--color-text-muted, #6b7d70);
}

.soft-input :deep(.n-input-wrapper) {
  min-height: 54px;
  padding: 0 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: inset 0 0 0 1px rgba(212, 221, 215, 0.68), 0 12px 28px rgba(26, 46, 31, 0.06);
  transition: box-shadow 0.22s ease, background 0.22s ease, transform 0.22s ease;
}

.soft-input :deep(.n-input-wrapper:hover),
.soft-input :deep(.n-input-wrapper--focus) {
  background: rgba(255, 255, 255, 0.94);
  box-shadow: inset 0 0 0 1px rgba(16, 185, 129, 0.48), 0 16px 34px rgba(16, 185, 129, 0.12);
  transform: translateY(-1px);
}

.soft-input :deep(.n-input__input-el) {
  color: var(--color-text, #0f1a12);
}

.form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 4px 0 22px;
  color: var(--color-text-secondary, #3d4f42);
}

.role-hint {
  padding: 6px 10px;
  border-radius: var(--r-full, 999px);
  background: var(--macaron-blue, #e0f2fe);
  color: var(--color-primary-light, #2d5a3d);
  font-size: var(--fs-sm, 14px);
  font-weight: var(--fw-semibold, 600);
}

.login-btn {
  position: relative;
  height: 54px;
  overflow: hidden;
  border: none !important;
  border-radius: 20px !important;
  font-size: var(--fs-base, 16px);
  font-weight: var(--fw-semibold, 600);
  letter-spacing: 0.24em;
  background: linear-gradient(135deg, var(--color-primary, #1a2e1f) 0%, var(--color-accent-hover, #059669) 58%, var(--color-accent, #10b981) 100%) !important;
  box-shadow: 0 18px 36px rgba(16, 185, 129, 0.28), 0 6px 16px rgba(26, 46, 31, 0.16);
  transition: transform 0.24s ease, box-shadow 0.24s ease, filter 0.24s ease;
}

.login-btn::before {
  content: "";
  position: absolute;
  inset: -60% auto -60% -30%;
  width: 38%;
  transform: rotate(18deg);
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.46), transparent);
  animation: buttonSheen 3.8s ease-in-out infinite;
}

.login-btn:hover {
  transform: translateY(-2px);
  filter: saturate(1.05);
  box-shadow: 0 24px 46px rgba(16, 185, 129, 0.34), 0 10px 22px rgba(26, 46, 31, 0.18);
}

.login-hint {
  margin-top: 22px;
  text-align: center;
  color: var(--color-text-muted, #6b7d70);
  font-size: var(--fs-sm, 14px);
}

.login-footer {
  margin-top: 24px;
  color: var(--color-text-muted, #6b7d70);
  font-size: var(--fs-sm, 14px);
}

.aurora,
.decor,
.mesh-grid {
  position: absolute;
  pointer-events: none;
}

.aurora {
  z-index: -4;
  border-radius: 50%;
  filter: blur(26px);
  opacity: 0.78;
  animation: auroraFloat 18s ease-in-out infinite;
}

.aurora--mint {
  width: 520px;
  height: 520px;
  left: -180px;
  top: -160px;
  background: rgba(200, 240, 212, 0.86);
}

.aurora--sun {
  width: 430px;
  height: 430px;
  right: 18%;
  bottom: -190px;
  background: rgba(254, 243, 199, 0.78);
  animation-delay: -7s;
}

.aurora--blue {
  width: 460px;
  height: 460px;
  right: -180px;
  top: 8%;
  background: rgba(224, 242, 254, 0.86);
  animation-delay: -12s;
}

.mesh-grid {
  z-index: -1;
  width: 560px;
  height: 560px;
  right: -220px;
  bottom: -220px;
  border-radius: 50%;
  background: repeating-conic-gradient(from 18deg, rgba(26, 46, 31, 0.07) 0deg 8deg, transparent 8deg 18deg);
  mask-image: radial-gradient(circle, black 0%, transparent 68%);
  animation: slowSpin 34s linear infinite;
}

.decor {
  z-index: 1;
  animation: floatSlow 24s ease-in-out infinite;
}

.decor--mint {
  width: 124px;
  height: 124px;
  top: 12%;
  left: 5%;
  border-radius: 38px;
  background: linear-gradient(145deg, var(--macaron-mint, #c8f0d4), rgba(255, 255, 255, 0.62));
  box-shadow: 0 24px 46px rgba(16, 185, 129, 0.14);
  transform: rotate(16deg);
}

.decor--cream {
  width: 96px;
  height: 96px;
  right: 7%;
  top: 10%;
  border-radius: 50%;
  background: var(--macaron-yellow, #fef3c7);
  box-shadow: 0 18px 34px rgba(245, 158, 11, 0.12);
  animation-delay: -8s;
}

.decor--pink-ring {
  width: 108px;
  height: 108px;
  right: 10%;
  bottom: 18%;
  border: 16px solid rgba(253, 232, 232, 0.9);
  border-radius: 50%;
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.06), 0 20px 38px rgba(239, 68, 68, 0.08);
  animation-delay: -15s;
}

.decor--lavender {
  width: 72px;
  height: 72px;
  left: 46%;
  top: 8%;
  border-radius: 22px;
  background: var(--macaron-purple, #ede9fe);
  transform: rotate(24deg);
  animation-delay: -12s;
}

.decor--blue-dot {
  width: 58px;
  height: 58px;
  left: 14%;
  bottom: 14%;
  border-radius: 50%;
  background: var(--macaron-blue, #e0f2fe);
  animation-delay: -4s;
}

.decor--spark {
  width: 26px;
  height: 26px;
  left: 54%;
  bottom: 20%;
  background: var(--color-accent, #10b981);
  clip-path: polygon(50% 0, 62% 36%, 100% 50%, 62% 64%, 50% 100%, 38% 64%, 0 50%, 38% 36%);
  box-shadow: 0 0 38px rgba(16, 185, 129, 0.5);
  animation-delay: -18s;
}

.success-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-overlay, 200);
  display: grid;
  place-items: center;
  overflow: hidden;
  background: rgba(251, 255, 252, 0.82);
  backdrop-filter: blur(22px);
}

.success-bloom {
  position: absolute;
  width: 420px;
  height: 420px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(16, 185, 129, 0.2), transparent 68%);
  animation: bloomPulse 1.8s ease-in-out infinite;
}

.success-card {
  position: relative;
  width: min(320px, calc(100vw - 48px));
  padding: 38px 28px;
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 1px solid rgba(255, 255, 255, 0.78);
  border-radius: 32px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 28px 82px rgba(26, 46, 31, 0.18);
}

.success-check {
  width: 76px;
  height: 76px;
  display: grid;
  place-items: center;
  margin-bottom: 18px;
  border-radius: 50%;
  color: white;
  font-size: 38px;
  font-weight: 800;
  background: linear-gradient(135deg, var(--color-primary, #1a2e1f), var(--color-accent, #10b981));
  box-shadow: 0 18px 42px rgba(16, 185, 129, 0.32);
  animation: successPop 0.52s cubic-bezier(.17, .89, .32, 1.28) both;
}

.success-text {
  color: var(--color-primary, #1a2e1f);
  font-size: var(--fs-2xl, 24px);
  font-weight: 800;
  letter-spacing: -0.02em;
}

.success-card p {
  margin: 8px 0 0;
  color: var(--color-text-muted, #6b7d70);
}

.login-success-enter-active { transition: opacity 0.32s ease; }
.login-success-enter-from { opacity: 0; }
.login-success-leave-active { transition: opacity 0.22s ease; }
.login-success-leave-to { opacity: 0; }

@keyframes floatSlow {
  0%, 100% { transform: translate3d(0, 0, 0) rotate(var(--rotate, 0deg)); }
  33% { transform: translate3d(12px, -18px, 0) rotate(calc(var(--rotate, 0deg) + 4deg)); }
  66% { transform: translate3d(-10px, 12px, 0) rotate(calc(var(--rotate, 0deg) - 3deg)); }
}

@keyframes auroraFloat {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  50% { transform: translate3d(28px, -22px, 0) scale(1.08); }
}

@keyframes slowSpin {
  to { transform: rotate(1turn); }
}

@keyframes buttonSheen {
  0%, 42% { transform: translateX(0) rotate(18deg); }
  72%, 100% { transform: translateX(420%) rotate(18deg); }
}

@keyframes bloomPulse {
  0%, 100% { transform: scale(0.92); opacity: 0.72; }
  50% { transform: scale(1.08); opacity: 1; }
}

@keyframes successPop {
  from { transform: scale(0.62) rotate(-10deg); opacity: 0; }
  to { transform: scale(1) rotate(0); opacity: 1; }
}

@media (max-width: 1024px) {
  .login-shell {
    grid-template-columns: 1fr;
    gap: 28px;
    width: min(720px, calc(100% - 36px));
  }

  .hero-glass {
    min-height: auto;
    padding: 32px;
  }

  .hero-copy {
    margin-top: 46px;
  }

  .feature-board {
    margin-top: 38px;
  }
}

@media (max-width: 720px) {
  .login-shell {
    width: min(100% - 28px, 480px);
    padding: 28px 0;
  }

  .hero-panel {
    display: none;
  }

  .login-card {
    border-radius: 28px;
  }

  .login-form-area {
    padding: 28px 22px;
  }

  .form-options {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }

  .decor--mint,
  .decor--lavender,
  .decor--spark {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
}
</style>
