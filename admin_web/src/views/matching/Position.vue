<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listPositions, createPosition, updatePosition, deletePosition, vectorizePosition,
} from '@/api/matching'

// ===== 列表与查询 =====
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 10, keyword: '', status: '' })

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.keyword) params.keyword = query.keyword
    if (query.status !== '' && query.status !== null) params.status = query.status
    const res = await listPositions(params)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally {
    loading.value = false
  }
}

// ===== 新增/编辑 =====
const dialog = reactive({ visible: false, editing: false })
const formRef = ref()
const form = reactive({
  id: null, name: '', code: '', dept_id: null,
  headcount: 0, filled: 0, status: 1, description: '',
})
const rules = {
  name: [{ required: true, message: '请输入岗位名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入岗位编码', trigger: 'blur' }],
}

function openCreate() {
  Object.assign(form, {
    id: null, name: '', code: '', dept_id: null,
    headcount: 0, filled: 0, status: 1, description: '',
  })
  dialog.editing = false
  dialog.visible = true
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id, name: row.name, code: row.code, dept_id: row.dept_id,
    headcount: row.headcount, filled: row.filled, status: row.status, description: row.description || '',
  })
  dialog.editing = true
  dialog.visible = true
}

async function save() {
  await formRef.value.validate()
  if (form.id) await updatePosition(form.id, form)
  else await createPosition(form)
  ElMessage.success('已保存')
  dialog.visible = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除岗位「${row.name}」？存在匹配结果的岗位不可删除（可改为停用）。`, '提示', { type: 'warning' })
  await deletePosition(row.id)
  ElMessage.success('已删除')
  load()
}

// ===== 岗位画像向量化（M-2，依赖 Ollama/Milvus） =====
async function vectorize(row) {
  try {
    await ElMessageBox.confirm(`对岗位「${row.name}」执行画像向量化？将调用 bge-m3 生成向量并写入 Milvus。`, '向量化确认', { type: 'info' })
  } catch {
    return
  }
  loading.value = true
  try {
    const res = await vectorizePosition(row.id)
    ElMessage.success(`向量化成功（维度 ${res.data.vector_dim}）`)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar">
      <el-input v-model="query.keyword" placeholder="按名称/编码搜索" style="width:240px" clearable
        @keyup.enter="query.page = 1; load()" />
      <el-select v-model="query.status" placeholder="状态" style="width:120px" clearable @change="query.page = 1; load()">
        <el-option label="启用" :value="1" />
        <el-option label="停用" :value="0" />
      </el-select>
      <el-button type="primary" @click="query.page = 1; load()">查询</el-button>
      <el-button type="primary" plain @click="openCreate">新增岗位</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="code" label="岗位编码" width="140" />
      <el-table-column prop="name" label="岗位名称" min-width="120" />
      <el-table-column prop="dept_id" label="部门ID" width="90" />
      <el-table-column prop="headcount" label="编制" width="80" />
      <el-table-column prop="filled" label="到岗" width="80" />
      <el-table-column label="空缺" width="80">
        <template #default="{ row }">
          <el-tag :type="(row.headcount - row.filled) > 0 ? 'warning' : 'success'" size="small">
            {{ row.headcount - row.filled }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="vectorize(row)">向量化</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination style="margin-top:14px" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑岗位' : '新增岗位'" width="520px">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="岗位名称" prop="name"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="岗位编码" prop="code"><el-input v-model="form.code" /></el-form-item>
      <el-form-item label="部门ID"><el-input-number v-model="form.dept_id" :min="0" controls-position="right" /></el-form-item>
      <el-form-item label="编制人数"><el-input-number v-model="form.headcount" :min="0" controls-position="right" /></el-form-item>
      <el-form-item label="已到岗"><el-input-number v-model="form.filled" :min="0" controls-position="right" /></el-form-item>
      <el-form-item label="状态">
        <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
      </el-form-item>
      <el-form-item label="岗位说明书">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="岗位职责/能力要求，作为画像向量化的输入源" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; align-items: center; }
</style>
