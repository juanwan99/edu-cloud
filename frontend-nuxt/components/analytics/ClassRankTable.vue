<template>
  <el-card>
    <template #header>班级排名</template>
    <el-table :data="rankings" stripe>
      <el-table-column prop="class_name" label="班级" min-width="120" />
      <el-table-column prop="student_count" label="人数" width="80" align="center" />
      <el-table-column label="均分" width="90" align="center">
        <template #default="{ row }">
          <span :class="{ 'below-avg': row.avg_score < gradeAvg }">
            {{ row.avg_score?.toFixed(1) ?? '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="及格率" width="90" align="center">
        <template #default="{ row }">
          {{ row.pass_rate != null ? (row.pass_rate * 100).toFixed(1) + '%' : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="优秀率" width="90" align="center">
        <template #default="{ row }">
          {{ row.excellent_rate != null ? (row.excellent_rate * 100).toFixed(1) + '%' : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="rank" label="排名" width="80" align="center" sortable />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
const props = defineProps<{
  rankings: any[]
  gradeAvg?: number
}>()
</script>

<style scoped>
.below-avg { color: var(--el-color-danger); font-weight: 600; }
</style>
