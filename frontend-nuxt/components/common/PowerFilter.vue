<template>
  <div class="filter-bar">
    <el-select
      v-if="grades.length"
      v-model="gradeModel"
      placeholder="年级"
      size="default"
      style="width: 120px"
    >
      <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
    </el-select>
    <el-select
      v-if="classes.length"
      v-model="classModel"
      placeholder="班级"
      size="default"
      style="width: 140px"
    >
      <el-option v-for="c in classes" :key="c" :label="c" :value="c" />
    </el-select>
    <el-select
      v-if="subjects.length"
      v-model="subjectModel"
      placeholder="学科"
      size="default"
      style="width: 120px"
    >
      <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
    </el-select>
    <el-select
      v-if="exams.length"
      v-model="examModel"
      placeholder="考试"
      size="default"
      style="width: 200px"
    >
      <el-option
        v-for="e in exams"
        :key="e.id"
        :label="e.name"
        :value="e.id"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  grades: string[]
  classes: string[]
  subjects: string[]
  exams: { id: string; name: string }[]
}>()

const gradeModel = defineModel<string>('grade')
const classModel = defineModel<string>('class')
const subjectModel = defineModel<string>('subject')
const examModel = defineModel<string>('exam')
</script>
