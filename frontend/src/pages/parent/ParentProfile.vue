<template>
  <div>
    <!-- Profile info -->
    <n-card title="个人信息" style="margin-bottom: 16px;">
      <n-form :model="profileForm" ref="profileFormRef">
        <n-form-item label="姓名">
          <n-input v-model:value="profileForm.display_name" placeholder="请输入姓名" />
        </n-form-item>
        <n-form-item label="手机号">
          <n-input :value="profileForm.phone" disabled />
        </n-form-item>
        <n-button type="primary" :loading="profileLoading" @click="handleUpdateProfile">
          保存
        </n-button>
      </n-form>
    </n-card>

    <!-- Change password -->
    <n-card title="修改密码" style="margin-bottom: 16px;">
      <n-form :model="pwdForm" :rules="pwdRules" ref="pwdFormRef">
        <n-form-item label="旧密码" path="old_password">
          <n-input v-model:value="pwdForm.old_password" type="password" placeholder="请输入旧密码" show-password-on="click" />
        </n-form-item>
        <n-form-item label="新密码" path="new_password">
          <n-input v-model:value="pwdForm.new_password" type="password" placeholder="请输入新密码（至少6位）" show-password-on="click" />
        </n-form-item>
        <n-form-item label="确认密码" path="confirm_password">
          <n-input v-model:value="pwdForm.confirm_password" type="password" placeholder="请再次输入新密码" show-password-on="click" />
        </n-form-item>
        <n-button type="warning" :loading="pwdLoading" @click="handleChangePassword">
          修改密码
        </n-button>
      </n-form>
    </n-card>

    <!-- Bound children -->
    <n-card title="已绑定孩子">
      <n-list v-if="children.length > 0" bordered size="small">
        <n-list-item v-for="child in children" :key="child.student_id">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div>{{ child.student_name }}</div>
              <div style="font-size: 12px; color: rgba(255,255,255,0.4);">
                {{ child.class_name || '' }} | {{ child.relationship || '' }}
              </div>
            </div>
            <n-tag type="info" size="small">{{ child.total_points ?? 0 }} 分</n-tag>
          </div>
        </n-list-item>
      </n-list>
      <n-empty v-else description="暂未绑定孩子" />
      <n-button style="margin-top: 12px;" block secondary @click="$router.push('/parent/bind')">
        绑定新孩子
      </n-button>
    </n-card>

    <!-- Logout -->
    <n-button style="margin-top: 16px;" block type="error" secondary @click="handleLogout">
      退出登录
    </n-button>
  </div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  NCard, NForm, NFormItem, NInput, NButton, NList, NListItem, NTag, NEmpty
} from 'naive-ui'
import { getParentMe, updateParentProfile, changeParentPassword } from '../../api/conduct'

const router = useRouter()
const childrenInjected = inject('children')
const children = childrenInjected

const profileFormRef = ref(null)
const pwdFormRef = ref(null)
const profileLoading = ref(false)
const pwdLoading = ref(false)

const profileForm = ref({
  display_name: '',
  phone: '',
})

const pwdForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const pwdRules = {
  old_password: { required: true, message: '请输入旧密码', trigger: 'blur' },
  new_password: { required: true, message: '请输入新密码', trigger: 'blur', min: 6 },
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (rule, value) => value === pwdForm.value.new_password,
      message: '两次输入的密码不一致',
      trigger: 'blur',
    },
  ],
}

onMounted(async () => {
  try {
    const res = await getParentMe()
    profileForm.value.display_name = res.data.display_name || ''
    profileForm.value.phone = res.data.phone || ''
  } catch { /* ignore */ }
})

async function handleUpdateProfile() {
  profileLoading.value = true
  try {
    await updateParentProfile({ display_name: profileForm.value.display_name })
    window.$message?.success('保存成功')
  } catch (err) {
    window.$message?.error(err.response?.data?.detail || '保存失败')
  } finally {
    profileLoading.value = false
  }
}

async function handleChangePassword() {
  try {
    await pwdFormRef.value?.validate()
  } catch { return }

  pwdLoading.value = true
  try {
    await changeParentPassword({
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })
    window.$message?.success('密码修改成功')
    pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
  } catch (err) {
    window.$message?.error(err.response?.data?.detail || '修改失败')
  } finally {
    pwdLoading.value = false
  }
}

function handleLogout() {
  localStorage.removeItem('cp_token')
  router.push('/parent/login')
}
</script>
