<template>
  <div class="login-card">
    <h2>edu-cloud</h2>
    <p class="subtitle">教育云平台</p>
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
      <el-form-item prop="username">
        <el-input v-model="form.username" placeholder="手机号 / 用户名" size="large" />
      </el-form-item>
      <el-form-item prop="password">
        <el-input
          v-model="form.password"
          type="password"
          placeholder="密码"
          size="large"
          show-password
          @keyup.enter="handleLogin"
        />
      </el-form-item>
      <el-button
        type="primary"
        size="large"
        :loading="loading"
        style="width: 100%"
        @click="handleLogin"
      >
        登录
      </el-button>
    </el-form>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const api = useApi()
const authStore = useAuthStore()
const { loadMenus } = useMenus()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

interface LoginResponse {
  access_token: string
  token_type: string
  user: { id: string; username: string; display_name: string; role: string }
  roles: any[]
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    const res = await api.login(form.username, form.password) as LoginResponse
    api.token.value = res.access_token
    authStore.applyLoginResponse(res)
    await loadMenus()
    navigateTo('/home')
  } catch (e: any) {
    ElMessage.error(e?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  width: 400px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

h2 {
  text-align: center;
  font-size: 24px;
  margin-bottom: 4px;
}

.subtitle {
  text-align: center;
  color: #909399;
  margin-bottom: 30px;
}
</style>
