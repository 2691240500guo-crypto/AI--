<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Plus, Edit, Delete, MagicStick,
} from '@element-plus/icons-vue'
import {
  listPositions, createPosition, updatePosition, deletePosition, vectorizePosition, importPositionJd,
} from '@/api/matching'

// ===== 列表与查询 =====
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 10, keyword: '', status: '' })

function fmtShort(t) {
  if (!t) return '—'
  const s = String(t).replace('T', ' ')
  const m = s.match(/(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/)
  return m ? `${m[1]}-${m[2]} ${m[3]}:${m[4]}` : s.slice(5, 16)
}
function rowClass({ row }) {
  // 缺编岗位整行浅红高亮（一眼看出"需要补人"）
  return (row.headcount - row.filled) > 0 ? 'row-shortage' : ''
}
function resetQuery() {
  query.keyword = ''
  query.status = ''
  query.page = 1
  load()
}
// 状态开关：直接调 PATCH 接口，乐观更新
async function toggleStatus(row, v) {
  if (row._switching) return
  row._switching = true
  try {
    await updatePosition(row.id, { status: v })
    row.status = v
    ElMessage.success(v === 1 ? '已启用' : '已停用')
  } catch {
    // 失败回滚
    row.status = v === 1 ? 0 : 1
  } finally {
    row._switching = false
  }
}

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

// ===== 岗位说明书文件导入（M-2，解析文本填入 description） =====
const jdImporting = ref(false)
const jdFileInput = ref(null)

function openJdImport() {
  // 仅新增/编辑弹窗内可用；通过隐藏 input 触发选择
  jdFileInput.value && jdFileInput.value.click()
}

async function onJdFileChange(e) {
  const file = e.target.files && e.target.files[0]
  e.target.value = '' // 允许重复选择同一文件
  if (!file) return
  if (!form.id) return ElMessage.warning('请先保存岗位后再导入岗位说明书')
  jdImporting.value = true
  try {
    const res = await importPositionJd(form.id, file)
    const txt = res.data.text || ''
    // 导入内容追加到现有说明书，避免覆盖已填内容
    form.description = form.description
      ? `${form.description}\n\n【以下为导入的岗位说明书：${res.data.filename}】\n${txt}`
      : txt
    ElMessage.success(`已解析 ${res.data.length} 字符，可确认后保存`)
  } finally {
    jdImporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar bar-filter">
      <el-input v-model="query.keyword" placeholder="按名称/编码搜索" style="width:260px" clearable
        @keyup.enter="query.page = 1; load()">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="query.status" placeholder="状态" style="width:120px" clearable @change="query.page = 1; load()">
        <el-option label="启用" :value="1" />
        <el-option label="停用" :value="0" />
      </el-select>
      <el-button type="primary" @click="query.page = 1; load()">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <div class="bar-spacer" />
      <el-button type="primary" plain @click="openCreate">
        <el-icon style="vertical-align:-2px;margin-right:2px"><Plus /></el-icon>新增岗位
      </el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe :row-class-name="rowClass">
      <el-table-column prop="id" label="岗位ID" width="80" />
      <el-table-column prop="code" label="岗位编码" width="140">
        <template #default="{ row }">
          <span class="mono">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="岗位名称" min-width="130" />
      <el-table-column prop="dept_id" label="部门ID" width="80" />
      <el-table-column prop="headcount" label="编制" width="70" align="center" />
      <el-table-column prop="filled" label="到岗" width="70" align="center" />
      <el-table-column label="空缺" width="70" align="center">
        <template #default="{ row }">
          <el-tag :type="(row.headcount - row.filled) > 0 ? 'danger' : 'success'" size="small" effect="dark">
            {{ row.headcount - row.filled }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.status" :active-value="1" :inactive-value="0"
            :loading="row._switching" inline-prompt active-text="启用" inactive-text="停用"
            @change="(v) => toggleStatus(row, v)" />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="120" show-overflow-tooltip>
        <template #default="{ row }">
          {{ fmtShort(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-tooltip content="编辑岗位" placement="top">
            <el-button link type="primary" size="small" @click="openEdit(row)">
              <el-icon style="vertical-align:-2px;margin-right:2px"><Edit /></el-icon>编辑
            </el-button>
          </el-tooltip>
          <el-tooltip content="写入岗位画像到 Milvus（每次说明书修改后需重新执行）" placement="top">
            <el-button link type="success" size="small" @click="vectorize(row)">
              <el-icon style="vertical-align:-2px;margin-right:2px"><MagicStick /></el-icon>向量化
            </el-button>
          </el-tooltip>
          <el-tooltip content="删除岗位" placement="top">
            <el-button link type="danger" size="small" @click="del(row)">
              <el-icon style="vertical-align:-2px;margin-right:2px"><Delete /></el-icon>删除
            </el-button>
          </el-tooltip>
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
        <div style="margin-top:6px">
          <el-button size="small" :loading="jdImporting" @click="openJdImport">
            导入说明书文件
          </el-button>
          <span style="margin-left:8px;color:#999;font-size:12px">支持 PDF / DOCX / TXT / MD / 图片，解析后追加到说明书文本</span>
        </div>
        <input ref="jdFileInput" type="file" accept=".pdf,.docx,.txt,.md,.jpg,.jpeg,.png" style="display:none" @change="onJdFileChange" />
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
.bar-spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 13px; color: #2563eb; }
.staff-cell { display: inline-flex; align-items: center; gap: 8px; }
.staff-num { color: #4b5563; font-size: 13px; }
.staff-num b { color: #1f2937; margin: 0 2px; }
/* 缺编岗位整行浅红高亮 */
.el-table .row-shortage td { background: #fef2f2 !important; }
.el-table .row-shortage:hover td { background: #fee2e2 !important; }
</style>
