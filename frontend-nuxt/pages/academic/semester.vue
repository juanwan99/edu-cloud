<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-bold">学期管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">新建学期</el-button>
    </div>

    <!-- Current semester card -->
    <el-card v-if="currentSem" class="mb-6">
      <template #header><span class="font-bold">当前学期</span></template>
      <div class="flex items-center gap-4">
        <div>
          <div class="text-lg font-medium">{{ currentSem.name }}</div>
          <div class="text-sm text-gray-500">{{ currentSem.start_date }} ~ {{ currentSem.end_date }}</div>
        </div>
        <div class="flex-1">
          <el-progress :percentage="progress.percent" :format="() => `已过 ${progress.percent}%（第 ${progress.week} 周）`" />
        </div>
      </div>
    </el-card>

    <!-- Semesters table -->
    <el-card class="mb-6">
      <template #header><span class="font-bold">历史学期</span></template>
      <el-table :data="academic.semesters.value" stripe>
        <el-table-column prop="name" label="学期名" />
        <el-table-column prop="school_year" label="学年" width="120" />
        <el-table-column label="起止日期" width="220">
          <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_current ? 'success' : 'info'" size="small">
              {{ row.is_current ? '当前' : '历史' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button v-if="!row.is_current" size="small" @click="doActivate(row.id)">激活</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Periods card -->
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span class="font-bold">作息时间表</span>
          <el-button size="small" @click="showPeriodDialog = true">编辑作息</el-button>
        </div>
      </template>
      <el-table :data="academic.periods.value" stripe size="small">
        <el-table-column prop="period_number" label="节次" width="60" />
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column label="时间" width="140">
          <template #default="{ row }">{{ row.start_time }} - {{ row.end_time }}</template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.period_type === 'class' ? 'primary' : 'info'">
              {{ { class: '正课', self_study: '自习', break: '课间', activity: '活动' }[row.period_type] || row.period_type }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create dialog -->
    <el-dialog v-model="showCreateDialog" title="新建学期" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="学期名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="学年"><el-input v-model="form.school_year" placeholder="2025-2026" /></el-form-item>
        <el-form-item label="学期">
          <el-radio-group v-model="form.term">
            <el-radio :value="1">第一学期</el-radio>
            <el-radio :value="2">第二学期</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="doCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- Period edit dialog (simplified) -->
    <el-dialog v-model="showPeriodDialog" title="编辑作息时间" width="600px">
      <p class="text-sm text-gray-500 mb-2">编辑作息时间表功能开发中</p>
      <template #footer>
        <el-button @click="showPeriodDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const academic = useAcademic()

const showCreateDialog = ref(false)
const showPeriodDialog = ref(false)
const form = reactive({ name: '', school_year: '', term: 1, start_date: '', end_date: '' })

const currentSem = computed(() =>
  academic.semesters.value.find((s: any) => s.is_current) || null
)
const progress = computed(() => academic.semesterProgress(currentSem.value))

async function doCreate() {
  await api.createSemester(form)
  showCreateDialog.value = false
  await academic.loadSemesters()
}

async function doActivate(id: string) {
  await api.activateSemester(id)
  await academic.loadSemesters()
}

function openEdit(row: any) {
  ElMessage.info('编辑功能开发中')
}

onMounted(async () => {
  await academic.loadSemesters()
  if (currentSem.value) {
    await academic.loadPeriods(currentSem.value.id)
  }
})
</script>
