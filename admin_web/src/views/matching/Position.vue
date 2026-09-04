<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Edit, Delete, Loading } from '@element-plus/icons-vue'
import {
  listPositions, createPosition, updatePosition, deletePosition, importPositionJd,
} from '@/api/matching'
import { listDepts } from '@/api/dept'

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
// hq+ 2026-09-04：部门下拉（避免 FK 报错 1452）
const deptList = ref([])
const deptMap = computed(() => {
  const m = {}
  deptList.value.forEach((d) => (m[d.id] = d.name))
  return m
})
async function loadDepts() {
  try {
    const r = await listDepts()
    deptList.value = r.data?.items || r.data || []
  } catch { /* 取不到就空下拉，岗位可继续创建（选不选都行） */ }
}

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

// hq+ 2026-09-04：保存时 loading + 锁弹窗（后端会自动跑 LLM 解析 + 向量化，约 5~15 秒）
const saving = ref(false)
async function save() {
  try {
    await formRef.value.validate()
  } catch { return }  // 校验失败别走 saving
  saving.value = true
  try {
    if (form.id) await updatePosition(form.id, form)
    else await createPosition(form)
    ElMessage.success('已保存，已自动完成「需求解析 + 画像向量化」')
    dialog.visible = false
    load()
  } finally {
    saving.value = false
  }
}

async function del(row) {
  // hq+ 2026-09-04：删除改为级联式（后端会清 match_result + Milvus 向量），文案明确告知
  await ElMessageBox.confirm(
    `确定删除岗位「${row.name}」吗？\n` +
    `将同时清理该岗位的匹配结果（含 Milvus 岗位向量），操作不可恢复。`,
    '删除岗位',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  await deletePosition(row.id)
  ElMessage.success('已删除岗位并清理关联数据')
  load()
}

// hq+ 2026-09-04：岗位画像向量化已改为「新增/编辑岗位后自动触发」，前端不再需要手动按钮。
// 如需批量重建/历史岗位灌库，仍可使用 scripts/vectorize_talents.py

// ===== 岗位说明书文件导入（M-2，解析文本填入 description） =====
import { previewPositionJd } from '@/api/matching'
const jdImporting = ref(false)
const jdFileInput = ref(null)

function openJdImport() {
  // 无论新增/编辑模式，都允许触发文件选择；form.id 区分落地方式
  jdFileInput.value && jdFileInput.value.click()
}

async function onJdFileChange(e) {
  const file = e.target.files && e.target.files[0]
  e.target.value = '' // 允许重复选择同一文件
  if (!file) return
  // hq+ 2026-09-04：分支：有 pid 走"追加到后端 description"；无 pid 走"preview接口填本地表单"
  if (!form.id) {
    jdImporting.value = true
    try {
      const res = await previewPositionJd(file)
      const txt = res.data?.text || ''
      form.description = form.description
        ? `${form.description}\n\n【以下为导入的岗位说明书：${res.data.filename}】\n${txt}`
        : txt
      ElMessage.success(`已解析 ${txt.length} 字符（新增预览模式），请填名称编码后保存`)
    } catch (err) {
      ElMessage.error(`解析失败：${err.response?.data?.message || err.message}`)
    } finally {
      jdImporting.value = false
    }
    return
  }
  // 编辑模式：调用原导入接口，追加到后端 description
  jdImporting.value = true
  try {
    const res = await importPositionJd(form.id, file)
    const txt = res.data.text || ''
    form.description = form.description
      ? `${form.description}\n\n【以下为导入的岗位说明书：${res.data.filename}】\n${txt}`
      : txt
    ElMessage.success(`已解析 ${res.data.length} 字符，可确认后保存`)
  } finally {
    jdImporting.value = false
  }
}

onMounted(() => { load(); loadDepts() })
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
      <el-table-column label="部门" min-width="120">
        <template #default="{ row }">{{ deptMap[row.dept_id] || ('#' + (row.dept_id ?? '')) }}</template>
      </el-table-column>
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
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-tooltip content="编辑岗位（说明保存后自动重新解析+向量化）" placement="top">
            <el-button link type="primary" size="small" @click="openEdit(row)">
              <el-icon style="vertical-align:-2px;margin-right:2px"><Edit /></el-icon>编辑
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

  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑岗位' : '新增岗位'" width="520px" :close-on-click-modal="!saving" :show-close="!saving">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="岗位名称" prop="name"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="岗位编码" prop="code"><el-input v-model="form.code" /></el-form-item>
      <el-form-item label="部门">
        <el-select v-model="form.dept_id" placeholder="选择部门（可选）" clearable filterable style="width:240px">
          <el-option v-for="d in deptList" :key="d.id" :label="`${d.name}（#${d.id}）`" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="编制人数"><el-input-number v-model="form.headcount" :min="0" controls-position="right" /></el-form-item>
      <el-form-item label="已到岗"><el-input-number v-model="form.filled" :min="0" controls-position="right" /></el-form-item>
      <el-form-item label="状态">
        <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
      </el-form-item>
      <el-form-item label="岗位说明书">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="岗位职责/能力要求，作为画像向量化的输入源" />
        <div style="margin-top:6px">
          <!-- hq+ 2026-09-04：上传按钮在新增/编辑模式都可见，按 form.id 自动选择落地方式 -->
          <el-button size="small" :loading="jdImporting" @click="openJdImport">
            上传说明书文件
          </el-button>
          <span style="margin-left:8px;color:#999;font-size:12px">支持 PDF / DOCX / TXT / MD / 图片；新增时先解析填到文本框，编辑时追加到岗位描述</span>
        </div>
        <input ref="jdFileInput" type="file" accept=".pdf,.docx,.txt,.md,.jpg,.jpeg,.png" style="display:none" @change="onJdFileChange" />
      </el-form-item>
    </el-form>
    <!-- hq+ 2026-09-04：保存过程全屏遮罩，提示用户"AI 正在解析+向量化" -->
    <el-overlay :show="saving" :z-index="3000">
      <div class="saving-mask">
        <div class="saving-spinner">
          <el-icon :size="42" color="#fff"><Loading /></el-icon>
        </div>
        <div class="saving-title">AI 正在解析与向量化</div>
        <div class="saving-sub">首次约需 5~15 秒（LLM 拆解岗位标签 + bge-m 向 嵌入 Milvus）</div>
      </div>
    </el-overlay>
    <template #footer>
      <el-button @click="dialog.visible = false" :disabled="saving">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">
        {{ saving ? 'AI 正在解析...' : '保存' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; align-items: center; }
.bar-spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 13px; color: #2563eb; }
.staff-cell { display: inline-flex; align-items: center; gap: 8px; }
.staff-num { color: #4b5563; font-size: 13px; }

/* hq+ 2026-09-04：保存岗位时的全屏遮罩 + 旋转图标，告知用户 AI 正在解析+向量化 */
.saving-mask {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: rgba(15, 23, 42, 0.72); color: #fff; gap: 14px; padding: 24px;
  text-align: center;
}
.saving-spinner {
  width: 72px; height: 72px; border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #38bdf8);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 12px 30px rgba(37, 99, 235, 0.35);
  animation: pulse 1.4s ease-in-out infinite;
}
.saving-title { font-size: 18px; font-weight: 600; letter-spacing: 0.5px; }
.saving-sub { font-size: 13px; color: rgba(255,255,255,0.78); max-width: 320px; line-height: 1.6; }
@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}
.staff-num b { color: #1f2937; margin: 0 2px; }
/* 缺编岗位整行浅红高亮 */
.el-table .row-shortage td { background: #fef2f2 !important; }
.el-table .row-shortage:hover td { background: #fee2e2 !important; }
</style>
