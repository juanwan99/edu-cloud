<template>
  <n-config-provider :theme="darkTheme">
    <div class="bind-container">
      <n-card title="绑定孩子" style="max-width: 400px; width: 100%;">
        <!-- Already-bound detection -->
        <n-alert
          v-if="existingCount > 0 && step === 1"
          type="info"
          style="margin-bottom: var(--space-4);"
          :title="`已绑定 ${existingCount} 个孩子`"
        >
          是否继续绑定新孩子？
        </n-alert>

        <!-- Steps indicator -->
        <n-steps :current="step" size="small" style="margin-bottom: var(--space-5);">
          <n-step title="填写信息" />
          <n-step title="验证" />
          <n-step title="完成" />
        </n-steps>

        <!-- Step 1 & 2: Form -->
        <n-form v-if="step <= 2" :model="form" :rules="rules" ref="formRef">
          <n-form-item label="学生姓名" path="student_name">
            <n-input v-model:value="form.student_name" placeholder="请输入孩子姓名" />
          </n-form-item>
          <n-form-item :label="verifyLabel" path="verify_code">
            <n-input v-model:value="form.verify_code" :placeholder="verifyPlaceholder" />
            <template #feedback>
              <span style="color: rgba(255,255,255,0.35); font-size: var(--fs-base);">
                {{ verifyHint }}
              </span>
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
            @click="step === 1 ? goToStep2() : handleBind()"
          >
            {{ step === 1 ? '下一步' : '确认绑定' }}
          </n-button>
          <n-button
            v-if="step === 2"
            block
            secondary
            style="margin-top: var(--space-2);"
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
      </n-card>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { darkTheme } from 'naive-ui'
import {
  NConfigProvider, NCard, NForm, NFormItem, NInput, NButton,
  NSteps, NStep, NAlert
} from 'naive-ui'
import { bindChild } from '../../api/conduct'

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
.bind-container {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: #18181c;
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
  border-radius: var(--r-sm);
  border: 1px solid rgba(255,255,255,0.12);
  cursor: pointer;
  transition: transform 0.2s ease-out, box-shadow 0.2s ease-out;
}
.rel-item:hover {
  border-color: rgba(99,226,183,0.4);
}
.rel-item.selected {
  border-color: #63e2b7;
  background: rgba(99,226,183,0.1);
}
.rel-icon {
  font-size: var(--fs-2xl);
  line-height: 1;
  margin-bottom: 4px;
}
.rel-label {
  font-size: var(--fs-base);
  color: rgba(255,255,255,0.7);
}
.rel-item.selected .rel-label {
  color: #63e2b7;
}
.success-area {
  text-align: center;
  padding: 24px 0;
}
.success-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(99,226,183,0.15);
  color: #63e2b7;
  font-size: var(--fs-display);
  line-height: 64px;
  margin: 0 auto 16px;
}
.success-text {
  font-size: var(--fs-xl);
  font-weight: var(--fw-semibold);
  margin-bottom: 8px;
}
.success-child {
  font-size: var(--fs-base);
  color: rgba(255,255,255,0.7);
  margin-bottom: 12px;
}
.success-hint {
  font-size: var(--fs-base);
  color: rgba(255,255,255,0.4);
}
</style>
