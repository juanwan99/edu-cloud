<template>
  <div class="register-container">
    <n-card style="max-width: 440px; width: 100%;">
      <template #header>
        <span style="font-size: var(--fs-xl); font-weight: var(--fw-semibold);">家长注册</span>
      </template>
        <!-- Step 1: Invite code -->
        <template v-if="step === 1">
          <n-form :model="inviteForm" :rules="inviteRules" ref="inviteFormRef">
            <n-form-item label="邀请码" path="code">
              <n-input v-model:value="inviteForm.code" placeholder="请输入班级邀请码" />
            </n-form-item>
            <n-button type="primary" block :loading="loading" @click="validateInvite">
              验证邀请码
            </n-button>
          </n-form>
          <div style="margin-top: var(--space-4); text-align: center;">
            <router-link to="/parent/login" style="color: #F4DA4C;">已有账号？去登录</router-link>
          </div>
        </template>

        <!-- Step 2: Registration form -->
        <template v-if="step === 2">
          <n-alert type="success" style="margin-bottom: var(--space-4);">
            班级: {{ classInfo.school_name }} - {{ classInfo.class_name }}
          </n-alert>
          <n-form :model="regForm" :rules="regRules" ref="regFormRef">
            <n-form-item label="姓名" path="name">
              <n-input v-model:value="regForm.name" placeholder="请输入您的姓名" />
            </n-form-item>
            <n-form-item label="手机号" path="phone">
              <n-input v-model:value="regForm.phone" placeholder="请输入手机号" />
            </n-form-item>
            <n-form-item label="密码" path="password">
              <n-input v-model:value="regForm.password" type="password" placeholder="请设置密码（至少6位）" show-password-on="click" />
            </n-form-item>
            <n-form-item label="与学生关系" path="relationship">
              <n-select
                v-model:value="regForm.relationship"
                :options="relationshipOptions"
                placeholder="请选择关系"
              />
            </n-form-item>
            <n-button type="primary" block :loading="loading" @click="handleRegister">
              注册
            </n-button>
          </n-form>
        </template>
    </n-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NCard, NForm, NFormItem, NInput, NButton, NSelect, NAlert
} from 'naive-ui'
import { getInviteInfo, parentRegister } from '../../api/conduct'

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
.register-container {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: #18181c;
}
</style>
