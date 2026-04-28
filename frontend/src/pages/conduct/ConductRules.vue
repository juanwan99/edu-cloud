<template>
  <div>
    <n-page-header title="班规管理" subtitle="管理积分规则分类和条目" style="margin-bottom: 16px;">
      <template #extra>
        <n-button type="primary" @click="showAddCategory = true">添加分类</n-button>
      </template>
    </n-page-header>

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: 16px;">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <n-spin :show="loading" v-if="classId">
      <n-collapse v-if="categories.length > 0" accordion>
        <n-collapse-item
          v-for="cat in categories"
          :key="cat.id"
          :name="cat.id"
        >
          <template #header>
            <n-space align="center" :size="8">
              <span style="font-weight: 500;">{{ cat.name }}</span>
              <n-tag size="tiny" :bordered="false">{{ (cat.items || []).length }} 条</n-tag>
            </n-space>
          </template>
          <template #header-extra>
            <n-space :size="4" @click.stop>
              <n-button size="tiny" quaternary @click="openEditCategory(cat)">编辑</n-button>
              <n-popconfirm @positive-click="handleDeleteCategory(cat.id)">
                <template #trigger>
                  <n-button size="tiny" quaternary type="error">删除</n-button>
                </template>
                确定删除分类「{{ cat.name }}」及其所有规则？
              </n-popconfirm>
              <n-button size="tiny" type="primary" quaternary @click="openAddItem(cat)">添加规则</n-button>
            </n-space>
          </template>

          <n-list v-if="cat.items && cat.items.length > 0" bordered size="small">
            <n-list-item v-for="item in cat.items" :key="item.id">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                  <span>{{ item.name }}</span>
                  <div v-if="item.description" style="font-size: 12px; color: rgba(255,255,255,0.4); margin-top: 2px;">
                    {{ item.description }}
                  </div>
                </div>
                <n-space :size="8" align="center">
                  <n-tag
                    :type="item.default_points >= 0 ? 'success' : 'error'"
                    size="small"
                  >
                    {{ item.default_points >= 0 ? '+' : '' }}{{ item.default_points }}
                  </n-tag>
                  <n-button size="tiny" quaternary @click="openEditItem(cat, item)">编辑</n-button>
                  <n-popconfirm @positive-click="handleDeleteItem(cat.id, item.id)">
                    <template #trigger>
                      <n-button size="tiny" quaternary type="error">删除</n-button>
                    </template>
                    确定删除规则「{{ item.name }}」？
                  </n-popconfirm>
                </n-space>
              </div>
            </n-list-item>
          </n-list>
          <n-empty v-else description="该分类暂无规则">
            <template #extra>
              <n-button size="small" type="primary" quaternary @click="openAddItem(cat)">添加规则</n-button>
            </template>
          </n-empty>
        </n-collapse-item>
      </n-collapse>
      <n-empty v-else description="暂无班规，点击上方按钮添加分类" />
    </n-spin>

    <!-- Add/Edit Category Modal -->
    <n-modal v-model:show="showCategoryModal" preset="card" :title="editingCategory ? '编辑分类' : '添加分类'" style="width: 420px;">
      <n-form ref="catFormRef" :model="categoryForm" :rules="catRules">
        <n-form-item label="分类名称" path="name">
          <n-input v-model:value="categoryForm.name" placeholder="例：课堂表现" />
        </n-form-item>
        <n-form-item label="排序" path="sort_order">
          <n-input-number v-model:value="categoryForm.sort_order" :min="0" style="width: 100%;" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button type="primary" :loading="savingCategory" @click="saveCategory">保存</n-button>
      </template>
    </n-modal>

    <!-- Add/Edit Rule Item Modal -->
    <n-modal v-model:show="showItemModal" preset="card" :title="editingItem ? '编辑规则' : '添加规则'" style="width: 480px;">
      <n-form ref="itemFormRef" :model="itemForm" :rules="itemRules">
        <n-form-item label="规则名称" path="name">
          <n-input v-model:value="itemForm.name" placeholder="例：课堂积极发言" />
        </n-form-item>
        <n-form-item label="默认积分" path="default_points">
          <n-input-number v-model:value="itemForm.default_points" :min="-100" :max="100" style="width: 100%;" />
        </n-form-item>
        <n-form-item label="描述" path="description">
          <n-input v-model:value="itemForm.description" type="textarea" placeholder="可选：规则详细说明" :rows="2" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button type="primary" :loading="savingItem" @click="saveItem">保存</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  NPageHeader, NCard, NCollapse, NCollapseItem, NList, NListItem,
  NTag, NButton, NSpace, NModal, NForm, NFormItem, NInput,
  NInputNumber, NEmpty, NSpin, NPopconfirm, NAlert, useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import {
  getRules, createCategory, updateCategory, deleteCategory,
  createRuleItem, updateRuleItem, deleteRuleItem,
} from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const categories = ref([])
const loading = ref(false)

// Category modal state
const showAddCategory = ref(false)
const showCategoryModal = computed({
  get: () => showAddCategory.value || !!editingCategory.value,
  set: (v) => { if (!v) { showAddCategory.value = false; editingCategory.value = null } },
})
const editingCategory = ref(null)
const categoryForm = ref({ name: '', sort_order: 0 })
const savingCategory = ref(false)
const catFormRef = ref(null)
const catRules = { name: { required: true, message: '请输入分类名称', trigger: 'blur' } }

// Item modal state
const showItemModal = ref(false)
const editingItem = ref(null)
const itemCategoryId = ref(null)
const itemForm = ref({ name: '', default_points: 1, description: '' })
const savingItem = ref(false)
const itemFormRef = ref(null)
const itemRules = {
  name: { required: true, message: '请输入规则名称', trigger: 'blur' },
  default_points: { required: true, type: 'number', message: '请输入积分值', trigger: 'blur' },
}

async function loadRules() {
  if (!classId.value) return
  loading.value = true
  try {
    const res = await getRules(classId.value)
    categories.value = res.data.categories || res.data || []
  } catch {
    categories.value = []
  } finally {
    loading.value = false
  }
}

function openEditCategory(cat) {
  editingCategory.value = cat
  categoryForm.value = { name: cat.name, sort_order: cat.sort_order || 0 }
}

function openAddItem(cat) {
  itemCategoryId.value = cat.id
  editingItem.value = null
  itemForm.value = { name: '', default_points: 1, description: '' }
  showItemModal.value = true
}

function openEditItem(cat, item) {
  itemCategoryId.value = cat.id
  editingItem.value = item
  itemForm.value = {
    name: item.name,
    default_points: item.default_points,
    description: item.description || '',
  }
  showItemModal.value = true
}

async function saveCategory() {
  savingCategory.value = true
  try {
    if (editingCategory.value) {
      await updateCategory(classId.value, editingCategory.value.id, categoryForm.value)
      message.success('分类已更新')
    } else {
      await createCategory(classId.value, categoryForm.value)
      message.success('分类已创建')
    }
    showCategoryModal.value = false
    categoryForm.value = { name: '', sort_order: 0 }
    await loadRules()
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    savingCategory.value = false
  }
}

async function handleDeleteCategory(catId) {
  try {
    await deleteCategory(classId.value, catId)
    message.success('分类已删除')
    await loadRules()
  } catch (e) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

async function saveItem() {
  savingItem.value = true
  try {
    if (editingItem.value) {
      await updateRuleItem(classId.value, itemCategoryId.value, editingItem.value.id, itemForm.value)
      message.success('规则已更新')
    } else {
      await createRuleItem(classId.value, itemCategoryId.value, itemForm.value)
      message.success('规则已创建')
    }
    showItemModal.value = false
    await loadRules()
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    savingItem.value = false
  }
}

async function handleDeleteItem(catId, itemId) {
  try {
    await deleteRuleItem(classId.value, catId, itemId)
    message.success('规则已删除')
    await loadRules()
  } catch (e) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(() => {
  if (classId.value) loadRules()
})
</script>
