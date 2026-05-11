<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="authThemeOverrides">
    <div class="auth-page" data-theme="dark">
      <div class="auth-brand">
        <h1 class="auth-brand__title">家长注册</h1>
        <p class="auth-brand__sub">edu-cloud 教育云平台</p>
      </div>

      <div class="auth-card">
        <!-- Step indicator -->
        <div class="step-indicator">
          <div class="step-dot" :class="{ active: step === 1, done: step > 1 }">1</div>
          <div class="step-line" :class="{ done: step > 1 }"></div>
          <div class="step-dot" :class="{ active: step === 2 }">2</div>
        </div>

        <!-- Step 1: Invite code -->
        <template v-if="step === 1">
          <n-form :model="inviteForm" :rules="inviteRules" ref="inviteFormRef">
            <n-form-item label="邀请码" path="code">
              <n-input v-model:value="inviteForm.code" placeholder="请输入班级邀请码" size="large" />
            </n-form-item>
            <n-button type="primary" block :loading="loading" size="large" @click="validateInvite">
              验证邀请码
            </n-button>
          </n-form>
          <div style="margin-top: var(--p-space-4); text-align: center;">
            <router-link to="/parent/login" class="register-link">已有账号？去登录</router-link>
          </div>
        </template>

        <!-- Step 2: Registration form -->
        <template v-if="step === 2">
          <n-alert type="success" style="margin-bottom: var(--p-space-4);">
            班级: {{ classInfo.school_name }} - {{ classInfo.class_name }}
          </n-alert>
          <n-form :model="regForm" :rules="regRules" ref="regFormRef">
            <n-form-item label="姓名" path="name">
              <n-input v-model:value="regForm.name" placeholder="请输入您的姓名" size="large" />
            </n-form-item>
            <n-form-item label="手机号" path="phone">
              <n-input v-model:value="regForm.phone" placeholder="请输入手机号" size="large" />
            </n-form-item>
            <n-form-item label="密码" path="password">
              <n-input v-model:value="regForm.password" type="password" placeholder="请设置密码（至少6位）" size="large" show-password-on="click" />
            </n-form-item>
            <n-form-item label="与学生关系" path="relationship">
              <n-select
                v-model:value="regForm.relationship"
                :options="relationshipOptions"
                placeholder="请选择关系"
                size="large"
              />
            </n-form-item>
            <n-button type="primary" block :loading="loading" size="large" @click="handleRegister">
              注册
            </n-button>
          </n-form>
        </template>
      </div>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { darkTheme } from 'naive-ui'
import {
  NConfigProvider, NForm, NFormItem, NInput, NButton, NSelect, NAlert
} from 'naive-ui'
import { getInviteInfo, parentRegister } from '../../api/conduct'

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
const route = useRoute()

const step = ref(1)
const loading = ref(false)
const classInfo = ref({})

const inviteFormRef = ref(null)
const regFormRef = ref(null)

const inviteForm = ref({ code: '' })
const inviteRules = {
  code: { required: true, message: '请输入邀请码', trigger: 'blur' },
}

const regForm = ref({
  name: '',
  phone: '',
  password: '',
  relationship: null,
})
const regRules = {
  name: { required: true, message: '请输入姓名', trigger: 'blur' },
  phone: { required: true, message: '请输入手机号', trigger: 'blur' },
  password: { required: true, message: '请输入密码', trigger: 'blur', min: 6 },
  relationship: { required: true, message: '请选择关系', trigger: 'change' },
}

const relationshipOptions = [
  { label: '父亲', value: 'father' },
  { label: '母亲', value: 'mother' },
  { label: '祖父', value: 'grandfather' },
  { label: '祖母', value: 'grandmother' },
  { label: '其他', value: 'other' },
]

onMounted(() => {
  const code = route.query.code
  if (code) {
    inviteForm.value.code = code
    validateInvite()
  }
})

async function validateInvite() {
  try {
    await inviteFormRef.value?.validate()
  } catch { return }

  loading.value = true
  try {
    const res = await getInviteInfo(inviteForm.value.code)
    classInfo.value = res.data
    step.value = 2
  } catch (err) {
    window.$message?.error(err.response?.data?.detail || '邀请码无效')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  try {
    await regFormRef.value?.validate()
  } catch { return }

  loading.value = true
  try {
    const res = await parentRegister({
      ...regForm.value,
      invite_code: inviteForm.value.code,
    })
    localStorage.setItem('cp_token', res.data.access_token)
    router.push('/parent/bind')
  } catch (err) {
    window.$message?.error(err.response?.data?.detail || '注册失败')
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

.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--p-space-5);
}

.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--p-surface-3);
  color: var(--p-text-3);
  font-size: var(--p-fs-label);
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, color 0.2s;
}

.step-dot.active {
  background: var(--p-color-accent);
  color: #09061B;
}

.step-dot.done {
  background: var(--p-color-accent-surface);
  color: var(--p-color-accent);
}

.step-line {
  flex: 1;
  height: 2px;
  background: var(--p-border);
  margin: 0 var(--p-space-2);
  max-width: 60px;
  transition: background 0.2s;
}

.step-line.done {
  background: var(--p-color-accent);
}

.register-link {
  color: var(--p-color-accent);
  font-weight: 500;
  transition: color 0.2s;
}

.register-link:hover {
  color: var(--p-color-accent-hover);
}
</style>
