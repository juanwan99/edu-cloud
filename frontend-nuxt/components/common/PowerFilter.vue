<template>
  <div class="power-filter">
    <el-select
      v-model="po.selectedGrade.value"
      placeholder="年级"
      :disabled="po.gradeOptions.value.length === 0"
      :loading="po.loading.value"
    >
      <el-option
        v-for="g in po.gradeOptions.value"
        :key="g"
        :label="g"
        :value="g"
      />
    </el-select>

    <el-select
      v-model="po.selectedClassId.value"
      placeholder="班级"
      :disabled="po.classOptions.value.length === 0"
      :loading="po.loading.value"
    >
      <el-option
        v-for="c in po.classOptions.value"
        :key="c.id"
        :label="c.name"
        :value="c.id"
      />
    </el-select>

    <el-select
      v-model="po.selectedSubjectId.value"
      placeholder="科目"
      :disabled="po.subjectOptions.value.length === 0"
      :loading="po.loading.value"
    >
      <el-option
        v-for="s in po.subjectOptions.value"
        :key="s.id"
        :label="s.name"
        :value="s.id"
      />
    </el-select>

    <el-select
      v-model="po.selectedExamId.value"
      placeholder="考试"
      :disabled="po.examOptions.value.length === 0"
      :loading="po.loading.value"
      class="exam-select"
    >
      <el-option
        v-for="e in po.examOptions.value"
        :key="e.exam_id"
        :label="e.exam_date ? `${e.name} ${e.exam_date}` : e.name"
        :value="e.exam_id"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
const po = usePowerOptions()

onMounted(() => {
  po.load()
})

defineExpose({ po })
</script>

<style scoped>
.power-filter {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.power-filter .el-select {
  min-width: 140px;
}
.power-filter .exam-select {
  min-width: 200px;
}
</style>
