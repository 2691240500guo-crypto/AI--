<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, deleteUser, listUsers, updateUser } from '@/api/user'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 10, keyword: '' })
const dialog = reactive({ visible: false, editing: false })
const formRef = ref()
const form = reactive({ id: null, username: '', nickname: '', password: '', status: 1 })
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入初始密码', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const res = await listUsers(query)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally { loading.value = false }
}

function openCreate() {
  Object.assign(form, { id: null, username: '', nickname: '', password: '', status: 1 })
  dialog.editing = false
  dialog.visible = true
}
function openEdit(row) {
  Object.assign(form, { id: row.id, username: row.username, nickname: row.nickname, password: '', status: row.status })
  dialog.editing = true
  dialog.visible = true
}

async function save() {
  await formRef.value.validate()
  if (form.id) await updateUser(form.id, form)
  else await createUser(form)
  ElMessage.success('已保存')
  dialog.visible = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除用户「${row.username}」？`, '提示', { type: 'warning' })
  await deleteUser(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar">
      <el-input v-model="query.keyword" placeholder="按账号/昵称搜索" style="width:240px" clearable @keyup.enter="query.page=1;load()" />
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button type="primary" plain @click="openCreate">新增用户</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="账号" />
      <el-table-column prop="nickname" label="姓名" />
      <el-table-column prop="dept_id" label="部门ID" width="90" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'">{{ row.status === 1 ? '正常' : '禁用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination style="margin-top:14px" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑用户' : '新增用户'" width="460px">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="账号" prop="username"><el-input v-model="form.username" :disabled="dialog.editing" /></el-form-item>
      <el-form-item label="姓名"><el-input v-model="form.nickname" /></el-form-item>
      <el-form-item label="密码" prop="password">
        <el-input v-model="form.password" type="password" :placeholder="dialog.editing ? '留空则不修改' : '初始密码'" />
      </el-form-item>
      <el-form-item label="状态">
        <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="正常" inactive-text="禁用" />
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