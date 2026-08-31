<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createMenu, deleteMenu, listMenus, updateMenu } from '@/api/menu'

const treeData = ref([])
const loading = ref(false)
const dialog = reactive({ visible: false, editing: false })
const formRef = ref()
const form = reactive({
  id: null, parent_id: 0, title: '', icon: '', path: '', component: '',
  perm: '', type: 2, sort: 0, status: 1
})
const rules = {
  title: [{ required: true, message: '请输入名称', trigger: 'blur' }]
}
const typeMap = { 1: '目录', 2: '菜单', 3: '按钮' }

function buildTree(list, pid = 0) {
  return list.filter((m) => m.parent_id === pid).map((m) => ({
    ...m, typeLabel: typeMap[m.type] || m.type, children: buildTree(list, m.id)
  }))
}

async function load() {
  loading.value = true
  try {
    const res = await listMenus()
    treeData.value = buildTree(res.data)
  } finally {
    loading.value = false
  }
}

function openCreate(parent) {
  Object.assign(form, {
    id: null, parent_id: parent?.id || 0, title: '', icon: '', path: '',
    component: '', perm: '', type: parent ? (parent.type === 1 ? 2 : 3) : 1, sort: 0, status: 1
  })
  dialog.editing = false
  dialog.visible = true
}
function openEdit(row) {
  Object.assign(form, { ...row })
  dialog.editing = true
  dialog.visible = true
}

async function save() {
  await formRef.value.validate()
  if (form.id) await updateMenu(form.id, form)
  else await createMenu(form)
  ElMessage.success('已保存')
  dialog.visible = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除「${row.title}」？`, '提示', { type: 'warning' })
  await deleteMenu(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar">
      <el-button type="primary" @click="openCreate()">新增根菜单</el-button>
      <span class="tip">新增后刷新页面即可看到（动态路由自动注册）</span>
    </div>

    <el-table :data="treeData" v-loading="loading" row-key="id" default-expand-all stripe>
      <el-table-column prop="title" label="名称" min-width="160" />
      <el-table-column prop="typeLabel" label="类型" width="80" />
      <el-table-column prop="icon" label="图标" width="80" />
      <el-table-column prop="path" label="路由" min-width="150" />
      <el-table-column prop="component" label="组件" min-width="150" />
      <el-table-column prop="perm" label="权限码" min-width="130" />
      <el-table-column prop="sort" label="排序" width="70" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button link type="primary" @click="openCreate(row)">加子级</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑菜单' : '新增菜单'" width="520px">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="父级ID"><el-input-number v-model="form.parent_id" :min="0" /></el-form-item>
      <el-form-item label="名称" prop="title"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="类型">
        <el-select v-model="form.type">
          <el-option :value="1" label="目录" />
          <el-option :value="2" label="菜单" />
          <el-option :value="3" label="按钮(权限码)" />
        </el-select>
      </el-form-item>
      <el-form-item label="图标"><el-input v-model="form.icon" placeholder="如 el-icon-xxx" /></el-form-item>
      <el-form-item label="路由"><el-input v-model="form.path" placeholder="/system/xxx" /></el-form-item>
      <el-form-item label="组件"><el-input v-model="form.component" placeholder="system/Xxx" /></el-form-item>
      <el-form-item label="权限码"><el-input v-model="form.perm" placeholder="如 talent:list" /></el-form-item>
      <el-form-item label="排序"><el-input-number v-model="form.sort" :min="0" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible=false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; align-items: center; }
.tip { color: #9ca3af; font-size: 12px; }
</style>
