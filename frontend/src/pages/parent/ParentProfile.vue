<template>
  <div>
    <!-- Avatar + basic info header -->
    <n-card style="margin-bottom: var(--space-4);">
      <div class="profile-header">
        <div class="avatar-circle">
          {{ avatarLetter }}
        </div>
        <div class="profile-info">
          <div class="profile-name">{{ profileForm.display_name || '未设置姓名' }}</div>
          <div class="profile-phone">{{ maskedPhone }}</div>
        </div>
      </div>
    </n-card>

    <!-- Profile info -->
    <n-card title="个人信息" style="margin-bottom: var(--space-4);">
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
    <n-card title="修改密码" style="margin-bottom: var(--space-4);">
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
      <!-- Security hint after password change -->
      <n-alert
        v-if="showSecurityHint"
        type="warning"
        title="账号安全提示"
        style="margin-top: var(--space-3);"
        closable
        @close="showSecurityHint = false"
      >
        密码修改成功，所有设备已退出登录，请重新登录。
      </n-alert>
    </n-card>

    <!-- Bound children -->
    <n-card title="已绑定孩子">
      <n-list v-if="children.length > 0" bordered size="small">
        <n-list-item v-for="child in children" :key="child.student_id">
          <div class="child-card">
            <div class="child-main">
              <div class="child-name">{{ child.student_name }}</div>
              <div class="child-meta">
                {{ child.class_name || '' }} | {{ child.relationship || '' }}
              </div>
            </div>
            <div class="child-stats">
              <n-tag :type="(child.total_points ?? 0) >= 0 ? 'success' : 'error'" size="small">
                {{ child.total_points ?? 0 }} 分
              </n-tag>
              <div v-if="child.recent_change != null" class="child-change" :class="child.recent_change >= 0 ? 'positive' : 'negative'">
                {{ child.recent_change >= 0 ? '+' : '' }}{{ child.recent_change }}
              </div>
              <div v-if="child.last_exam_score != null" class="child-exam">
                最近考试: {{ child.last_exam_score }}
              </div>
            </div>
          </div>
        </n-list-item>
      </n-list>
      <n-empty v-else description="暂未绑定孩子" />
      <n-button style="margin-top: var(--space-3);" block secondary @click="$router.push('/parent/bind')">
        绑定新孩子
      </n-button>
    </n-card>

    <!-- Logout with confirmation -->
    <n-popconfirm
      @positive-click="handleLogout"
      positive-text="确认退出"
      negative-text="取消"
    >
      <template #trigger>
        <n-button style="margin-top: var(--space-4);" block type="error" secondary>
          退出登录
        </n-button>
      </template>
      确定要退出登录吗？
    </n-popconfirm>

    <!-- Version info -->
    <div class="version-info">v1.0 · 家校互通</div>
  </div>
</template>

<script setup>
import { ref, inject, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  NCard, NForm, NFormItem, NInput, NButton, NList, NListItem,
  NTag, NEmpty, NPopconfirm, NAlert
} from 'naive-ui'
import { getParentMe, updateParentProfile, changeParentPassword } from '../../api/conduct'

const router = useRouter()
const childrenInjected = inject('children')
const children = childrenInjected

const profileFormRef = ref(null)
const pwdFormRef = ref(null)
const profileLoading = ref(false)
const pwdLoading = ref(false)
const showSecurityHint = ref(false)

const profileForm = ref({
  display_name: '',
  phone: '',
})

const avatarLetter = computed(() => {
  const name = profileForm.value.display_name
  return name ? name.charAt(0) : '?'
})

const maskedPhone = computed(() => {
  const phone = profileForm.value.phone || ''
  if (phone.length >= 7) {
    return phone.substring(0, 3) + '****' + phone.substring(7)
  }
  return phone || '未设置'
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
    showSecurityHint.value = true
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

<style scoped>
.profile-header {
  display: flex;
  align-items: center;
  gap: 16px;
}
.avatar-circle {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(99,226,183,0.15);
  color: #63e2b7;
  font-size: var(--fs-2xl);
  font-weight: var(--fw-semibold);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.profile-info {
  flex: 1;
  min-width: 0;
}
.profile-name {
  font-size: var(--fs-lg);
  font-weight: var(--fw-semibold);
}
.profile-phone {
  font-size: var(--fs-base);
  color: rgba(255,255,255,0.45);
  margin-top: 2px;
}
.child-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.child-main {
  flex: 1;
  min-width: 0;
}
.child-name {
  font-size: var(--fs-base);
}
.child-meta {
  font-size: var(--fs-base);
  color: rgba(255,255,255,0.4);
}
.child-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.child-change {
  font-size: var(--fs-base);
  font-weight: var(--fw-medium);
}
.child-change.positive {
  color: var(--color-success-border);
}
.child-change.negative {
  color: var(--color-danger);
}
.child-exam {
  font-size: var(--fs-base);
  color: rgba(255,255,255,0.35);
}
.version-info {
  text-align: center;
  padding: 24px 0 16px;
  font-size: var(--fs-base);
  color: rgba(255,255,255,0.25);
}
</style>
