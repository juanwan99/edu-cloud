<template>
  <div>
    <n-page-header title="小组管理" subtitle="创建和管理班级小组" style="margin-bottom: 16px;">
      <template #extra>
        <n-button type="primary" @click="openCreateGroup">创建小组</n-button>
      </template>
    </n-page-header>

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: 16px;">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <n-spin :show="loading" v-if="classId">
      <n-grid v-if="groups.length > 0" :cols="3" :x-gap="16" :y-gap="16">
        <n-gi v-for="group in groups" :key="group.id">
          <n-card :title="group.name" size="small" hoverable>
            <template #header-extra>
              <n-space :size="4">
                <n-button size="tiny" quaternary @click="openGroupDetail(group)">管理成员</n-button>
                <n-popconfirm @positive-click="handleDeleteGroup(group.id)">
                  <template #trigger>
                    <n-button size="tiny" quaternary type="error">删除</n-button>
                  </template>
                  确定删除小组「{{ group.name }}」？
                </n-popconfirm>
              </n-space>
            </template>
            <div style="color: rgba(255,255,255,0.5); font-size: 16px;">
              {{ (group.members || []).length }} 名成员
            </div>
            <n-space v-if="group.members && group.members.length > 0" :size="4" style="margin-top: 8px; flex-wrap: wrap;">
              <n-tag v-for="m in group.members" :key="m.student_id" size="small" :bordered="false">
                {{ m.student_name }}
              </n-tag>
            </n-space>
          </n-card>
        </n-gi>
      </n-grid>
      <n-empty v-else description="暂无小组，点击上方按钮创建" />
    </n-spin>

    <!-- Create Group Modal -->
    <n-modal v-model:show="showCreateModal" preset="card" title="创建小组" style="width: 420px;">
      <n-form :model="createForm">
        <n-form-item label="小组名称">
          <n-input v-model:value="createForm.name" placeholder="例：第一组" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button type="primary" :loading="creating" @click="handleCreateGroup">创建</n-button>
      </template>
    </n-modal>

    <!-- Group Detail Drawer -->
    <n-drawer v-model:show="showDetailDrawer" :width="400" placement="right">
      <n-drawer-content :title="detailGroup?.name || '小组详情'">
        <template #header-extra>
          <n-button size="small" type="primary" @click="showAddMember = true">添加成员</n-button>
        </template>
        <n-list v-if="detailGroup?.members?.length > 0" bordered size="small">
          <n-list-item v-for="m in detailGroup.members" :key="m.student_id">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>{{ m.student_name }}</span>
              <n-popconfirm @positive-click="handleRemoveMember(m.student_id)">
                <template #trigger>
                  <n-button size="tiny" quaternary type="error">移除</n-button>
                </template>
                确定移除「{{ m.student_name }}」？
              </n-popconfirm>
            </div>
          </n-list-item>
        </n-list>
        <n-empty v-else description="暂无成员" />

        <!-- Add member inline -->
        <div v-if="showAddMember" style="margin-top: 16px;">
          <n-divider>添加成员</n-divider>
          <n-select
            v-model:value="newMemberIds"
            :options="availableStudents"
            multiple
            filterable
            placeholder="选择学生"
          />
          <n-button
            type="primary"
            block
            style="margin-top: 8px;"
            :loading="addingMembers"
            :disabled="newMemberIds.length === 0"
            @click="handleAddMembers"
          >
            确认添加
          </n-button>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  NPageHeader, NGrid, NGi, NCard, NButton, NSpace, NTag, NList,
  NListItem, NModal, NForm, NFormItem, NInput, NDrawer, NDrawerContent,
  NSelect, NPopconfirm, NDivider, NEmpty, NSpin, NAlert, useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import {
  getGroups, createGroup, deleteGroup, addGroupMembers,
  removeGroupMember, getStudentRankings,
} from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const groups = ref([])
const loading = ref(false)

// Create modal
const showCreateModal = ref(false)
const createForm = ref({ name: '' })
const creating = ref(false)

// Detail drawer
const showDetailDrawer = ref(false)
const detailGroup = ref(null)
const showAddMember = ref(false)
const newMemberIds = ref([])
const addingMembers = ref(false)
const availableStudents = ref([])

async function loadGroups() {
  if (!classId.value) return
  loading.value = true
  try {
    const res = await getGroups(classId.value)
    groups.value = res.data.groups || res.data || []
  } catch {
    groups.value = []
  } finally {
    loading.value = false
  }
}

async function loadAllStudents() {
  if (!classId.value) return
  try {
    const res = await getStudentRankings(classId.value, {})
    const rankings = res.data.rankings || res.data || []
    availableStudents.value = rankings.map((s) => ({
      label: s.student_name,
      value: s.student_id,
    }))
  } catch {
    availableStudents.value = []
  }
}

function openCreateGroup() {
  createForm.value = { name: '' }
  showCreateModal.value = true
}

async function handleCreateGroup() {
  if (!createForm.value.name.trim()) {
    message.warning('请输入小组名称')
    return
  }
  creating.value = true
  try {
    await createGroup(classId.value, createForm.value)
    message.success('小组已创建')
    showCreateModal.value = false
    await loadGroups()
  } catch (e) {
    message.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleDeleteGroup(groupId) {
  try {
    await deleteGroup(classId.value, groupId)
    message.success('小组已删除')
    await loadGroups()
  } catch (e) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

function openGroupDetail(group) {
  detailGroup.value = group
  showAddMember.value = false
  newMemberIds.value = []
  showDetailDrawer.value = true
}

async function handleAddMembers() {
  if (!detailGroup.value || newMemberIds.value.length === 0) return
  addingMembers.value = true
  try {
    await addGroupMembers(classId.value, detailGroup.value.id, {
      student_ids: newMemberIds.value,
    })
    message.success('成员已添加')
    showAddMember.value = false
    newMemberIds.value = []
    await loadGroups()
    // Refresh detail
    const updated = groups.value.find(g => g.id === detailGroup.value.id)
    if (updated) detailGroup.value = updated
  } catch (e) {
    message.error(e.response?.data?.detail || '添加失败')
  } finally {
    addingMembers.value = false
  }
}

async function handleRemoveMember(studentId) {
  if (!detailGroup.value) return
  try {
    await removeGroupMember(classId.value, detailGroup.value.id, studentId)
    message.success('成员已移除')
    await loadGroups()
    const updated = groups.value.find(g => g.id === detailGroup.value.id)
    if (updated) detailGroup.value = updated
  } catch (e) {
    message.error(e.response?.data?.detail || '移除失败')
  }
}

onMounted(() => {
  if (classId.value) {
    loadGroups()
    loadAllStudents()
  }
})
</script>
