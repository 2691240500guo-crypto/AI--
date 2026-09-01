<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createBank, deleteBank, listBanks, updateBank } from '@/api/assessment'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 10, keyword: '' })
const dialog = reactive({ visible: false, editing: false })
const formRef = ref()
const form = reactive({ id: null, name: '', description: '', status: 1 })

async function load() {
  loading.value = true
  try {
    const res = await listBanks(query)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally { loading.value = false }
}

function openCreate() {
  Object.assign(form, { id: null, name: '', description: '', status: 1 })
  dialog.editing = false
  dialog.visible = true
}
function openEdit(row) {
  Object.assign(form, { id: row.id, name: row.name, description: row.description, status: row.status })
  dialog.editing = true
  dialog.visible = true
}

async function save() {
  if (!form.name) return ElMessage.warning('请输入题库名称')
  if (form.id) await updateBank(form.id, form)
  else await createBank(form)
  ElMessage.success('已保存')
  dialog.visible = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除题库「${row.name}」？其下题目将一并删除。`, '提示', { type: 'warning' })
  await deleteBank(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar">
      <el-input v-model="query.keyword" placeholder="按题库名搜索" style="width:240px" clearable @keyup.enter="query.page=1;load()" />
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button type="primary" plain @click="openCreate">新增题库</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="题库名称" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column prop="question_count" label="题目数" width="90" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'">{{ row.status === 1 ? '启用' : '停用' }}</el-tag></template>
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

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑题库' : '新增题库'" width="460px">
    <el-form ref="formRef" :model="form" label-width="80px">
      <el-form-item label="题库名称"><el-input v-model="form.name" placeholder="如：技术能力题库" /></el-form-item>
      <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="状态">
        <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
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
