<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="authThemeOverrides">
    <div class="auth-page" data-theme="dark">
      <div class="auth-brand">
        <h1 class="auth-brand__title">绑定孩子</h1>
        <p class="auth-brand__sub">完成绑定即可查看孩子信息</p>
      </div>

      <div class="auth-card">
        <!-- Already-bound detection -->
        <n-alert
          v-if="existingCount > 0 && step === 1"
          type="info"
          style="margin-bottom: var(--p-space-4);"
          :title="`已绑定 ${existingCount} 个孩子`"
        >
          是否继续绑定新孩子？
        </n-alert>

        <!-- Steps indicator -->
        <div class="step-indicator">
          <div class="step-dot" :class="{ active: step === 1, done: step > 1 }">1</div>
          <div class="step-line" :class="{ done: step > 1 }"></div>
          <div class="step-dot" :class="{ active: step === 2, done: step > 2 }">2</div>
          <div class="step-line" :class="{ done: step > 2 }"></div>
          <div class="step-dot" :class="{ active: step === 3 }">3</div>
        </div>

        <!-- Step 1 & 2: Form -->
        <n-form v-if="step <= 2" :model="form" :rules="rules" ref="formRef">
          <n-form-item label="学生姓名" path="student_name">
            <n-input v-model:value="form.student_name" placeholder="请输入孩子姓名" size="large" />
          </n-form-item>
          <n-form-item :label="verifyLabel" path="verify_code">
            <n-input v-model:value="form.verify_code" :placeholder="verifyPlaceholder" size="large" />
            <template #feedback>
              <span class="verify-hint">{{ verifyHint }}</span>
            </template>
          </n-form-item>
          <n-form-item label="与学生关系" path="relationship">
            <div class="relationship-grid">
              <div
                v-for="opt in relationshipOptions"
                :key="opt.value"
                class="rel-item"
                :class="{ selected: form.relationship === opt.value }"
                @click="form.relationship = opt.value"
              >
                <span class="rel-icon">{{ opt.icon }}</span>
                <span class="rel-label">{{ opt.label }}</span>
              </div>
            </div>
          </n-form-item>
          <n-button
            type="primary"
            block
            :loading="loading"
            size="large"
            @click="step === 1 ? goToStep2() : handleBind()"
          >
            {{ step === 1 ? '下一步' : '确认绑定' }}
          </n-button>
          <n-button
            v-if="step === 2"
            block
            secondary
            style="margin-top: var(--p-space-2);"
            @click="step = 1"
          >
            上一步
          </n-button>
        </n-form>

        <!-- Step 3: Success -->
        <div v-if="step === 3" class="success-area">
          <div class="success-icon">&#10003;</div>
          <div class="success-text">绑定成功</div>
          <div class="success-child">{{ boundChildName }}</div>
          <div class="success-hint">{{ countdown }} 秒后跳转概览...</div>
        </div>
      </div>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { darkTheme } from 'naive-ui'
import {
  NConfigProvider, NForm, NFormItem, NInput, NButton,
  NAlert
} from 'naive-ui'
import { bindChild } from '../../api/conduct'

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
const step = ref(1)
const boundChildName = ref('')
const countdown = ref(3)
let countdownTimer = null

// Detect already-bound children from ParentLayout inject
const childrenInjected = inject('children', ref([]))
const existingCount = computed(() => childrenInjected.value?.length ?? 0)

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

const verifyHint = computed(() => {
  const map = {
    id_last6: '请输入学生身份证号码的最后6位数字用于验证身份',
    phone: '请输入注册时使用的家长手机号码',
    code: '请输入学校或班主任提供的验证码',
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
  { label: '父亲', value: 'father', icon: '👨' },
  { label: '母亲', value: 'mother', icon: '👩' },
  { label: '祖父', value: 'grandfather', icon: '👴' },
  { label: '祖母', value: 'grandmother', icon: '👵' },
  { label: '其他', value: 'other', icon: '👤' },
]

async function goToStep2() {
  try {
    await formRef.value?.validate()
  } catch { return }
  step.value = 2
}

async function handleBind() {
  try {
    await formRef.value?.validate()
  } catch { return }

  loading.value = true
  try {
    await bindChild(form.value)
    boundChildName.value = form.value.student_name
    step.value = 3
    startCountdown()
  } catch (err) {
    window.$message?.error(err.response?.data?.detail || '绑定失败')
  } finally {
    loading.value = false
  }
}

function startCountdown() {
  countdown.value = 3
  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(countdownTimer)
      router.push('/parent')
    }
  }, 1000)
}

onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
})
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

.verify-hint {
  color: var(--p-text-disabled);
  font-size: var(--p-fs-label);
}

.relationship-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  width: 100%;
}

.rel-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 8px;
  border-radius: var(--p-card-radius);
  border: var(--p-card-border);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.rel-item:hover {
  border-color: var(--p-color-accent-hover);
}

.rel-item.selected {
  border-color: var(--p-color-accent);
  background: var(--p-color-accent-surface);
}

.rel-icon {
  font-size: var(--p-fs-section);
  line-height: 1;
  margin-bottom: 4px;
}

.rel-label {
  font-size: var(--p-fs-label);
  color: var(--p-text-3);
}

.rel-item.selected .rel-label {
  color: var(--p-color-accent);
}

.success-area {
  text-align: center;
  padding: 24px 0;
}

.success-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--p-color-success-surface);
  color: var(--p-color-success);
  font-size: 32px;
  line-height: 64px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.success-text {
  font-size: var(--p-fs-section);
  font-weight: 600;
  color: var(--p-text-1);
  margin-bottom: 8px;
}

.success-child {
  font-size: var(--p-fs-body);
  color: var(--p-text-2);
  margin-bottom: 12px;
}

.success-hint {
  font-size: var(--p-fs-body);
  color: var(--p-text-disabled);
}
</style>
