<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createDept, deleteDept, listDepts, updateDept } from '@/api/dept'

const treeData = ref([])
const loading = ref(false)
const dialog = reactive({ visible: false, editing: false })
const formRef = ref()
const form = reactive({ id: null, parent_id: 0, name: '', leader: '', sort: 0, status: 1 })
const rules = {
  name: [{ required: true, message: '请输入部门名称', trigger: 'blur' }]
}

function buildTree(list, pid = 0) {
  return list.filter((d) => d.parent_id === pid).map((d) => ({
    ...d, children: buildTree(list, d.id)
  }))
}

async function load() {
  loading.value = true
  try {
    const res = await listDepts()
    treeData.value = buildTree(res.data)
  } finally {
    loading.value = false
  }
}

function openCreate(parent) {
  Object.assign(form, { id: null, parent_id: parent?.id || 0, name: '', leader: '', sort: 0, status: 1 })
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
  if (form.id) await updateDept(form.id, form)
  else await createDept(form)
  ElMessage.success('已保存')
  dialog.visible = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除部门「${row.name}」？`, '提示', { type: 'warning' })
  await deleteDept(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar">
      <el-button type="primary" @click="openCreate()">新增根部门</el-button>
    </div>

    <el-table :data="treeData" v-loading="loading" row-key="id" default-expand-all stripe>
      <el-table-column prop="name" label="部门名称" min-width="200" />
      <el-table-column prop="leader" label="负责人" width="140" />
      <el-table-column prop="sort" label="排序" width="80" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'">{{ row.status === 1 ? '正常' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button link type="primary" @click="openCreate(row)">加子部门</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑部门' : '新增部门'" width="480px">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="父级ID"><el-input-number v-model="form.parent_id" :min="0" /></el-form-item>
      <el-form-item label="部门名称" prop="name"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="负责人"><el-input v-model="form.leader" /></el-form-item>
      <el-form-item label="排序"><el-input-number v-model="form.sort" :min="0" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible=false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; }
</style>
