<template>
  <n-config-provider :theme="darkTheme">
    <div class="bind-container">
      <n-card title="绑定孩子" style="max-width: 400px; width: 100%;">
        <n-form :model="form" :rules="rules" ref="formRef">
          <n-form-item label="学生姓名" path="student_name">
            <n-input v-model:value="form.student_name" placeholder="请输入孩子姓名" />
          </n-form-item>
          <n-form-item :label="verifyLabel" path="verify_code">
            <n-input v-model:value="form.verify_code" :placeholder="verifyPlaceholder" />
          </n-form-item>
          <n-form-item label="与学生关系" path="relationship">
            <n-select
              v-model:value="form.relationship"
              :options="relationshipOptions"
              placeholder="请选择关系"
            />
          </n-form-item>
          <n-button type="primary" block :loading="loading" @click="handleBind">
            绑定
          </n-button>
        </n-form>
      </n-card>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { darkTheme } from 'naive-ui'
import {
  NConfigProvider, NCard, NForm, NFormItem, NInput, NButton, NSelect
} from 'naive-ui'
import { bindChild } from '../../api/conduct'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

// verify_code_type could be passed via query or default
const verifyCodeType = ref('id_last6')

const verifyLabel = computed(() => {
  const map = {
    id_last6: '身份证后6位',
    phone: '手机号',
    code: '验证码',
  }
  return map[verifyCodeType.value] || '验证码'
})

const verifyPlaceholder = computed(() => {
  const map = {
    id_last6: '请输入孩子身份证后6位',
    phone: '请输入家长手机号',
    code: '请输入验证码',
  }
  return map[verifyCodeType.value] || '请输入验证信息'
})

const form = ref({
  student_name: '',
  verify_code: '',
  relationship: null,
})

const rules = {
  student_name: { required: true, message: '请输入学生姓名', trigger: 'blur' },
  verify_code: { required: true, message: '请输入验证信息', trigger: 'blur' },
  relationship: { required: true, message: '请选择关系', trigger: 'change' },
}

const relationshipOptions = [
  { label: '父亲', value: 'father' },
  { label: '母亲', value: 'mother' },
  { label: '祖父', value: 'grandfather' },
  { label: '祖母', value: 'grandmother' },
  { label: '其他', value: 'other' },
]

async function handleBind() {
  try {
    await formRef.value?.validate()
  } catch { return }

  loading.value = true
  try {
    await bindChild(form.value)
    window.$message?.success('绑定成功')
    router.push('/parent')
  } catch (err) {
    window.$message?.error(err.response?.data?.detail || '绑定失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.bind-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: #18181c;
}
</style>
