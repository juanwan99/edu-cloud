<template>
  <div class="login-container">
    <n-card style="max-width: 400px; width: 100%;">
      <template #header>
        <span style="font-size: 20px; font-weight: 600;">家长登录</span>
      </template>
      <n-form ref="formRef" :model="form" :rules="rules">
          <n-form-item label="手机号" path="phone">
            <n-input v-model:value="form.phone" placeholder="请输入手机号" />
          </n-form-item>
          <n-form-item label="密码" path="password">
            <n-input v-model:value="form.password" type="password" placeholder="请输入密码" show-password-on="click" />
          </n-form-item>
          <n-button type="primary" block :loading="loading" @click="handleLogin">
            登录
          </n-button>
        </n-form>
        <div style="margin-top: 16px; text-align: center;">
          <router-link to="/parent/register" style="color: #63e2b7;">还没有账号？立即注册</router-link>
        </div>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NForm, NFormItem, NInput, NButton } from 'naive-ui'
import { parentLogin } from '../../api/conduct'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = ref({
  phone: '',
  password: '',
})

const rules = {
  phone: { required: true, message: '请输入手机号', trigger: 'blur' },
  password: { required: true, message: '请输入密码', trigger: 'blur' },
}

async function handleLogin() {
  try {
    await formRef.value?.validate()
  } catch { return }

  loading.value = true
  try {
    const res = await parentLogin(form.value)
    localStorage.setItem('cp_token', res.data.access_token)
    router.push('/parent')
  } catch (err) {
    window.$message?.error(err.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: #18181c;
}
</style>
