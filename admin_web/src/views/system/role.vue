<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createRole, deleteRole, listRoles, updateRole } from '@/api/role'
import { listMenus } from '@/api/menu'

const rows = ref([])
const loading = ref(false)
const dialog = reactive({ visible: false, editing: false })
const formRef = ref()
const form = reactive({ id: null, code: '', name: '', remark: '', menu_ids: [], status: 1 })
const rules = {
  code: [{ required: true, message: '请输入角色编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
}

// 菜单树数据
const menuTree = ref([])
const menuTreeRef = ref()
const treeProps = { label: 'title', children: 'children' }

// 后端返回的是平铺列表，转成树
function buildTree(list, pid = 0) {
  return list.filter((m) => m.parent_id === pid).map((m) => ({
    ...m, children: buildTree(list, m.id)
  }))
}

async function load() {
  loading.value = true
  try {
    const res = await listRoles()
    rows.value = res.data
  } finally {
    loading.value = false
  }
}

async function loadMenus() {
  const res = await listMenus()
  menuTree.value = buildTree(res.data)
}

function openCreate() {
  Object.assign(form, { id: null, code: '', name: '', remark: '', menu_ids: [], status: 1 })
  dialog.editing = false
  dialog.visible = true
}
function openEdit(row) {
  Object.assign(form, { id: row.id, code: row.code, name: row.name, remark: row.remark, menu_ids: [], status: row.status })
  dialog.editing = true
  dialog.visible = true
}

async function save() {
  await formRef.value.validate()
  form.menu_ids = menuTreeRef.value?.getCheckedKeys() || []
  if (form.id) await updateRole(form.id, form)
  else await createRole(form)
  ElMessage.success('已保存')
  dialog.visible = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除角色「${row.name}」？`, '提示', { type: 'warning' })
  await deleteRole(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(() => { load(); loadMenus() })
</script>

<template>
  <el-card>
    <div class="bar">
      <el-button type="primary" @click="openCreate">新增角色</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="name" label="名称" width="160" />
      <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'">{{ row.status === 1 ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑角色' : '新增角色'" width="520px">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="编码" prop="code"><el-input v-model="form.code" :disabled="dialog.editing" placeholder="如 admin / hr" /></el-form-item>
      <el-form-item label="名称" prop="name"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
      <el-form-item label="菜单权限">
        <el-tree ref="menuTreeRef" :data="menuTree" :props="treeProps" show-checkbox node-key="id"
          default-expand-all style="max-height:280px;overflow:auto;width:100%" />
      </el-form-item>
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
