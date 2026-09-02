<!-- AI 人才档案 - 人才档案管理
     功能：多维查询（关键词/学历/技能/年限/等级/标签）、
           四种导入（Excel/Word/PDF/图片智能解析）、
           一键导出/打印/备份、附件简历预览下载 -->
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, ArrowDown, Download, Plus, UploadFilled } from '@element-plus/icons-vue'
import {
  deleteTalent, downloadResume, fetchResumeBlob, previewResume, listTalents,
  semanticSearchTalent, importExcel, importWord, parseResume,
  exportTalents, talentStats,
} from '@/api/talent'

const router = useRouter()
const route = useRoute()
const rows = ref([])
const total = ref(0)
const loading = ref(false)

// ========== 多维查询条件 ==========
const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  education: '',
  skill: '',
  years_min: null,
  level: '',
  tag: route.query.tag || '',
  status: null,
  source: null,
})

const degreeOptions = [
  { label: '博士', value: '博士' },
  { label: '硕士', value: '硕士' },
  { label: '本科', value: '本科' },
  { label: '大专', value: '大专' },
  { label: '高中及以下', value: '高中' },
]
const levelOptions = [
  { label: 'P5 初级', value: 'P5' },
  { label: 'P6 中级', value: 'P6' },
  { label: 'P7 高级', value: 'P7' },
  { label: 'P8 专家', value: 'P8' },
]
const yearOptions = [
  { label: '1年以上', value: 1 },
  { label: '3年以上', value: 3 },
  { label: '5年以上', value: 5 },
  { label: '10年以上', value: 10 },
]
const sourceOptions = [
  { label: '人工录入', value: 'manual' },
  { label: 'Excel导入', value: 'excel' },
  { label: 'Word导入', value: 'word' },
  { label: 'AI解析', value: 'agent_parsed' },
  { label: 'PDF解析', value: 'pdf' },
  { label: '文本解析', value: 'text' },
]

async function load() {
  loading.value = true
  try {
    const params = { ...query }
    // 空值过滤
    Object.keys(params).forEach(k => {
      if (params[k] === '' || params[k] === null || params[k] === undefined) {
        delete params[k]
      }
    })
    const res = await listTalents(params)
    rows.value = res.data.items || res.data?.items || []
    total.value = res.data.meta?.total || res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  Object.assign(query, {
    page: 1, page_size: 10, keyword: '', degree: '', skill: '',
    years_min: null, level: '', tag: '', status: null, source: null,
  })
  load()
}

function clearTag() { query.tag = ''; query.page = 1; load() }

// ========== 多维统计面板 ==========
const stats = reactive({
  loading: false,
  total: 0,
  by_education: {},
  by_level: {},
  by_skill: {},
  by_source: {},
  expiring_count: 0,
})
async function loadStats() {
  stats.loading = true
  try {
    const res = await talentStats()
    const d = res.data || {}
    stats.total = d.total || 0
    stats.by_education = d.by_education || {}
    stats.by_level = d.by_level || {}
    stats.by_skill = d.by_skill || {}
    stats.by_source = d.by_source || {}
    stats.expiring_count = d.expiring_count || 0
  } catch (e) {
    // 统计失败不阻塞主流程
  } finally {
    stats.loading = false
  }
}
// ========== 附件简历预览 / 下载 ==========
// 修改人：袁文武  修改时间：2026-09-02
// 优化：支持多格式预览（PDF/图片/不支持格式降级下载）、blob 错误不双重弹窗
const preview = reactive({ visible: false, url: '', mime: '', name: '', busy: false, error: '' })

function hasResume(row) {
  return !!(row.object_key || row.resume_file || row.resume_id)
}

function isPreviewable(mime) {
  if (!mime) return false
  return mime.startsWith('application/pdf') || mime.startsWith('image/')
}

async function openPreview(row) {
  if (!hasResume(row)) {
    ElMessage.warning('该档案没有附件简历')
    return
  }
  preview.busy = true
  preview.visible = true
  preview.name = `${row.name || '未命名'}-简历`
  preview.url = ''
  preview.mime = ''
  preview.error = ''
  try {
    const result = await previewResume(row.id)
    preview.url = result.url
    preview.mime = result.mime
  } catch (e) {
    // 拦截器不再弹全局错误，这里统一提示
    const msg = e._blobMessage || e.message || '附件读取异常'
    ElMessage.error('预览失败：' + msg)
    preview.visible = false
  } finally {
    preview.busy = false
  }
}
function closePreview() {
  if (preview.url) {
    try { URL.revokeObjectURL(preview.url) } catch {}
  }
  preview.url = ''
  preview.mime = ''
  preview.error = ''
  preview.visible = false
}
async function doDownload(row) {
  if (!hasResume(row)) {
    ElMessage.warning('该档案没有附件简历')
    return
  }
  try {
    await downloadResume(row.id, `${row.name || '未命名'}-简历`)
    ElMessage.success('已开始下载')
  } catch (e) {
    const msg = e._blobMessage || e.message || ''
    ElMessage.error('下载失败：' + msg)
  }
}
// 从预览弹窗直接下载当前文件
function downloadFromPreview() {
  if (!preview.url) return
  const a = document.createElement('a')
  a.href = preview.url
  a.download = preview.name
  document.body.appendChild(a)
  a.click()
  a.remove()
  ElMessage.success('已开始下载')
}

// ========== 四种导入方式 ==========
const importDlg = reactive({ visible: false, type: 'excel', loading: false })
const pickedFile = ref(null)

function openImport(type) {
  importDlg.type = type
  importDlg.visible = true
  pickedFile.value = null
}
function onFileChange(file) {
  pickedFile.value = file.raw || file
}
const acceptMap = {
  excel: '.xlsx,.xls',
  word: '.docx,.doc',
  pdf: '.pdf',
  image: '.jpg,.jpeg,.png,.bmp,.webp,.gif',
}
const typeLabels = {
  excel: 'Excel 批量导入',
  word: 'Word 批量导入',
  pdf: 'PDF 简历智能解析',
  image: '图片简历智能解析',
}
async function doImport() {
  if (!pickedFile.value) { ElMessage.warning('请先选择文件'); return }
  importDlg.loading = true
  try {
    let res
    if (importDlg.type === 'excel') {
      res = await importExcel(pickedFile.value)
    } else if (importDlg.type === 'word') {
      res = await importWord(pickedFile.value)
    } else {
      // PDF / 图片走 AI 智能解析
      res = await parseResume(pickedFile.value)
    }
    const d = res.data || {}
    if (d.imported !== undefined) {
      ElMessage.success(`导入成功 ${d.imported} 条，跳过 ${d.skipped || 0} 条` +
        (d.errors?.length ? `，错误 ${d.errors.length} 条` : ''))
    } else if (d.id || d.talent?.id) {
      ElMessage.success('解析成功，已入库')
      // 跳到编辑页
      const tid = d.id || d.talent?.id
      if (tid) router.push(`/talent/edit/${tid}`)
    } else {
      ElMessage.success('处理完成')
    }
    importDlg.visible = false
    load()
  } catch (e) {
    // 拦截器已提示
  } finally {
    importDlg.loading = false
  }
}

// ========== 导出 / 打印 / 备份 ==========
const exporting = ref(false)
// 构建当前筛选条件（导出/打印复用）
function buildFilterParams() {
  const params = {}
  const fields = ['keyword', 'education', 'skill', 'years_min', 'level', 'tag', 'status', 'source']
  fields.forEach(k => {
    const v = query[k]
    if (v !== '' && v !== null && v !== undefined) params[k] = v
  })
  return params
}

async function doExport() {
  exporting.value = true
  try {
    const params = buildFilterParams()
    const blob = await exportTalents(params)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const filterTag = Object.keys(params).length ? '筛选结果' : '全量'
    a.download = `人才档案_${filterTag}_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    const msg = e._blobMessage || e.message || ''
    ElMessage.error('导出失败：' + msg)
  } finally {
    exporting.value = false
  }
}

const printing = ref(false)
async function doPrint() {
  if (total.value === 0) {
    ElMessage.warning('当前没有可打印的数据')
    return
  }
  printing.value = true
  try {
    // 按筛选条件拉取全部数据（分页拉取，最多 2000 条）
    const params = buildFilterParams()
    const allRows = []
    let page = 1
    const pageSize = 100
    while (true) {
      const res = await listTalents({ ...params, page, page_size: pageSize })
      const items = res.data?.items || []
      allRows.push(...items)
      if (items.length < pageSize) break
      if (allRows.length >= 2000) break  // 打印上限
      page++
    }

    const printWin = window.open('', '_blank')
    if (!printWin) {
      ElMessage.warning('请允许弹出窗口以进行打印')
      return
    }
    const headerHtml = `
      <tr>
        <th>ID</th><th>姓名</th><th>性别</th><th>学历</th><th>职位</th>
        <th>公司</th><th>年限</th><th>技能</th><th>来源</th><th>状态</th>
      </tr>`
    const rowsHtml = allRows.map(r => `
      <tr>
        <td>${r.id}</td>
        <td>${r.name || ''}</td>
        <td>${r.gender || ''}</td>
        <td>${r.highest_education || ''}</td>
        <td>${r.current_title || ''}</td>
        <td>${r.current_company || ''}</td>
        <td>${r.years_experience || 0}</td>
        <td>${r.skills || ''}</td>
        <td>${sourceLabel(r.resume_source)}</td>
        <td>${r.status === 1 ? '在档' : '失效'}</td>
      </tr>`).join('')
    const filterDesc = Object.keys(params).length
      ? `（筛选结果，共 ${allRows.length} 条）`
      : `（全量，共 ${allRows.length} 条）`
    printWin.document.write(`
      <!DOCTYPE html><html><head><meta charset="utf-8">
      <title>人才档案列表</title>
      <style>
        body { font-family: "Microsoft YaHei", sans-serif; margin: 20px; }
        h1 { text-align: center; font-size: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 12px; }
        th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }
        th { background: #f5f7fa; }
        @media print { @page { size: A4 landscape; } }
      </style></head><body>
      <h1>人才档案列表 ${filterDesc}</h1>
      <div style="color:#666;font-size:12px;margin:10px 0">
        打印时间：${new Date().toLocaleString()}
      </div>
      <table>${headerHtml}${rowsHtml}</table>
      <script>window.onload = function(){ setTimeout(function(){ window.print(); }, 500); }<' + '/script>
      </body></html>
    `)
    printWin.document.close()
  } catch (e) {
    ElMessage.error('打印失败：' + (e.message || ''))
  } finally {
    printing.value = false
  }
}

async function doBackup() {
  // 全量备份：忽略筛选条件，导出所有在档人才
  const confirmed = await ElMessageBox.confirm(
    '将导出全量在档人才档案（Excel 格式），确认执行备份？',
    '数据备份确认',
    { type: 'info', confirmButtonText: '开始备份', cancelButtonText: '取消' }
  ).catch(() => null)
  if (!confirmed) return
  exporting.value = true
  try {
    const blob = await exportTalents()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `人才档案全量备份_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('全量备份导出成功')
  } catch (e) {
    const msg = e._blobMessage || e.message || ''
    ElMessage.error('备份失败：' + msg)
  } finally {
    exporting.value = false
  }
}

// ========== 语义搜索 ==========
const semanticOpen = ref(false)
const semanticQ = ref('')
const semanticHits = ref([])
const semanticBusy = ref(false)
async function doSemanticSearch() {
  const q = semanticQ.value.trim()
  if (!q) { ElMessage.warning('请输入问题'); return }
  semanticBusy.value = true
  try {
    const res = await semanticSearchTalent(q, 10)
    const arr = Array.isArray(res.data) ? res.data : (res.data?.hits || [])
    semanticHits.value = arr
    if (!semanticHits.value.length) ElMessage.info('没有召回结果，试试更宽泛的描述')
  } catch (e) {
    ElMessage.error('语义搜索失败：' + (e.message || ''))
  } finally {
    semanticBusy.value = false
  }
}
function toggleSemantic() {
  semanticOpen.value = !semanticOpen.value
  if (!semanticOpen.value) { semanticHits.value = []; semanticQ.value = '' }
}
function jumpToTalent(tid) {
  if (tid) router.push(`/talent/detail/${tid}`)
}

// ========== 列表操作 ==========
function openDetail(row) {
  router.push(`/talent/detail/${row.id}`)
}
function openEdit(row) {
  if (row) router.push(`/talent/edit/${row.id}`)
  else router.push('/talent/new')
}
async function del(row) {
  await ElMessageBox.confirm(`确定删除人才「${row.name}」？该操作为软删除。`, '提示', { type: 'warning' })
  await deleteTalent(row.id)
  ElMessage.success('已删除')
  if (rows.value.length === 1 && query.page > 1) query.page -= 1
  load()
}

const sourceLabel = (s) => ({ manual: '人工录入', import: '批量导入', excel: 'Excel导入',
  word: 'Word导入', agent_parsed: 'AI解析', text: '文本解析' }[s] || s || '-')
const sourceTag = (s) => ({ manual: 'info', import: 'success', excel: 'success',
  word: 'success', agent_parsed: 'primary', text: 'warning' }[s] || '')

onMounted(() => {
  load()
  loadStats()
})
</script>

<template>
  <el-card>
    <!-- 标题 + 操作栏 -->
    <div class="page-head">
      <div class="title">人才档案管理</div>
      <div class="actions">
        <el-dropdown trigger="click">
          <el-button type="primary">
            <el-icon style="margin-right:4px"><Upload /></el-icon>
            导入档案
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="openImport('excel')">📊 Excel 批量导入</el-dropdown-item>
              <el-dropdown-item @click="openImport('word')">📄 Word 批量导入</el-dropdown-item>
              <el-dropdown-item @click="openImport('pdf')">📑 PDF 简历智能解析</el-dropdown-item>
              <el-dropdown-item @click="openImport('image')">🖼️ 图片简历智能解析</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-dropdown trigger="click">
          <el-button type="success">
            <el-icon style="margin-right:4px"><Download /></el-icon>
            导出 / 打印
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="doExport">📥 导出 Excel</el-dropdown-item>
              <el-dropdown-item @click="doPrint">🖨️ 打印列表</el-dropdown-item>
              <el-dropdown-item @click="doBackup">💾 数据备份（全量导出）</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" plain @click="router.push('/talent/new')">
          <el-icon><Plus /></el-icon>新增人才
        </el-button>
      </div>
    </div>

    <!-- 多维筛选条 -->
    <div class="filter-bar">
      <el-input v-model="query.keyword" placeholder="关键词（姓名/技能/经历）" style="width:200px"
        clearable @keyup.enter="query.page=1;load()" />
      <el-select v-model="query.education" placeholder="学历" clearable style="width:110px" @change="query.page=1;load()">
        <el-option v-for="o in degreeOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-input v-model="query.skill" placeholder="技能关键词" style="width:140px"
        clearable @keyup.enter="query.page=1;load()" />
      <el-select v-model="query.years_min" placeholder="从业年限" clearable style="width:120px" @change="query.page=1;load()">
        <el-option v-for="o in yearOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-model="query.level" placeholder="能力等级" clearable style="width:120px" @change="query.page=1;load()">
        <el-option v-for="o in levelOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable style="width:100px" @change="query.page=1;load()">
        <el-option label="在档" :value="1" />
        <el-option label="失效" :value="0" />
      </el-select>
      <el-select v-model="query.source" placeholder="来源" clearable style="width:130px" @change="query.page=1;load()">
        <el-option v-for="o in sourceOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <el-tag v-if="query.tag" type="warning" closable @close="clearTag" style="margin-left:6px">
        标签：{{ query.tag }}
      </el-tag>
      <el-button :type="semanticOpen ? 'success' : 'warning'" plain @click="toggleSemantic" style="margin-left:auto">
        {{ semanticOpen ? '关闭语义搜索' : '🔍 语义搜索' }}
      </el-button>
    </div>

    <!-- 语义搜索面板 -->
    <div v-if="semanticOpen" class="semantic">
      <el-input v-model="semanticQ" type="textarea" :rows="2"
        placeholder="例如：擅长数字化转型、有3年以上AI项目经验的骨干人才"
        @keydown.ctrl.enter.prevent="doSemanticSearch" />
      <div class="semantic-actions">
        <el-button type="primary" :loading="semanticBusy" :disabled="!semanticQ.trim()" @click="doSemanticSearch">
          语义召回
        </el-button>
        <span class="hint">Ctrl + Enter 提交；基于向量召回 + 候选人画像</span>
      </div>
      <el-table v-if="semanticHits.length" :data="semanticHits" stripe size="small" style="margin-top:10px">
        <el-table-column label="姓名" min-width="120">
          <template #default="{ row }">
            <el-link v-if="row.talent_id" type="primary" :underline="false" @click="jumpToTalent(row.talent_id)">
              {{ row.name || row.talent?.name || `#${row.talent_id}` }}
            </el-link>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="相似度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="Math.min(100, Math.round((row.score || 0) * 100))" />
          </template>
        </el-table-column>
        <el-table-column label="命中说明" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ row.match_reason || row.snippet || row.preview || '—' }}</template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 列表 -->
    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="64" />
      <el-table-column prop="name" label="姓名" min-width="90" />
      <el-table-column prop="gender" label="性别" width="60" />
      <el-table-column prop="highest_education" label="学历" width="80" />
      <el-table-column prop="current_title" label="职位" min-width="120" show-overflow-tooltip />
      <el-table-column prop="current_company" label="公司" min-width="120" show-overflow-tooltip />
      <el-table-column prop="years_experience" label="年限" width="60" />
      <el-table-column prop="skills" label="技能" min-width="160" show-overflow-tooltip />
      <el-table-column label="附件" width="110">
        <template #default="{ row }">
          <template v-if="row.object_key || row.resume_file || row.resume_id">
            <el-button link type="primary" size="small" @click="openPreview(row)">预览</el-button>
            <el-button link type="success" size="small" @click="doDownload(row)">下载</el-button>
          </template>
          <span v-else style="color:#9ca3af;font-size:12px">—</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="90">
        <template #default="{ row }">
          <el-tag :type="sourceTag(row.resume_source)" size="small">{{ sourceLabel(row.resume_source) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="70">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '在档' : '失效' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">查看</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination style="margin-top:14px"
      layout="total, prev, pager, next, jumper"
      :total="total"
      v-model:current-page="query.page"
      :page-size="query.page_size"
      @current-change="load"
    />
  </el-card>

  <!-- 导入 dialog -->
  <el-dialog v-model="importDlg.visible" :title="typeLabels[importDlg.type]" width="480" append-to-body>
    <el-upload drag :auto-upload="false" :limit="1" :accept="acceptMap[importDlg.type]"
      :on-change="onFileChange" style="margin-bottom:10px">
      <el-icon style="font-size:40px;color:#9ca3af"><UploadFilled /></el-icon>
      <div>拖拽或点击上传文件</div>
      <template #tip>
        <div class="el-upload__tip">
          <template v-if="importDlg.type === 'excel'">支持 .xlsx / .xls 格式，批量录入人才信息</template>
          <template v-else-if="importDlg.type === 'word'">支持 .docx 格式，表格或键值对</template>
          <template v-else-if="importDlg.type === 'pdf'">支持 .pdf 格式，AI 智能解析抽取结构化字段</template>
          <template v-else>支持 .jpg / .png / .bmp / .webp 格式，OCR + AI 智能解析</template>
        </div>
      </template>
    </el-upload>
    <el-alert v-if="importDlg.type === 'pdf' || importDlg.type === 'image'"
      type="info" :closable="false" style="margin-bottom:10px">
      AI 智能解析需要调用本地大模型，单份简历约需 1-3 分钟，请耐心等待
    </el-alert>
    <template #footer>
      <el-button @click="importDlg.visible = false">取消</el-button>
      <el-button type="primary" :loading="importDlg.loading" :disabled="!pickedFile" @click="doImport">
        开始{{ importDlg.type === 'excel' || importDlg.type === 'word' ? '导入' : '解析' }}
      </el-button>
    </template>
  </el-dialog>

  <!-- 附件预览 dialog -->
  <el-dialog v-model="preview.visible" :title="`附件预览 · ${preview.name}`" width="70%" top="4vh"
    destroy-on-close @closed="closePreview">
    <div v-loading="preview.busy" class="preview-box">
      <!-- PDF 预览 -->
      <iframe v-if="preview.url && !preview.busy && preview.mime.startsWith('application/pdf')"
        :src="preview.url" class="preview-frame" title="简历预览" />
      <!-- 图片预览 -->
      <div v-else-if="preview.url && !preview.busy && preview.mime.startsWith('image/')" class="img-preview">
        <img :src="preview.url" :alt="preview.name" style="max-width:100%;max-height:70vh;object-fit:contain" />
      </div>
      <!-- 不支持预览的格式（doc/docx 等）提示下载 -->
      <div v-else-if="preview.url && !preview.busy" class="unsupported-preview">
        <div class="unsupported-icon">📄</div>
        <p>该格式不支持在线预览（{{ preview.mime || '未知格式' }}）</p>
        <p class="hint">请点击下方按钮下载后用本地软件打开</p>
        <el-button type="primary" @click="downloadFromPreview">下载文件</el-button>
      </div>
    </div>
    <template #footer>
      <el-button v-if="preview.url && preview.mime.startsWith('application/pdf')" type="primary" @click="downloadFromPreview">下载</el-button>
      <el-button @click="preview.visible=false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.title { font-size: 18px; font-weight: 600; color: #1f2937; }
.actions { display: flex; gap: 10px; }
.filter-bar { display: flex; gap: 10px; margin-bottom: 14px; align-items: center; flex-wrap: wrap; }
.stats-panel { margin-bottom: 16px; }
.stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
.stat-card { border-radius: 10px; padding: 18px 20px; color: #fff; text-align: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06); transition: transform 0.2s; }
.stat-card:hover { transform: translateY(-2px); }
.stat-card-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.stat-card-purple { background: linear-gradient(135deg, #a855f7 0%, #ec4899 100%); }
.stat-card-green { background: linear-gradient(135deg, #10b981 0%, #06b6d4 100%); }
.stat-card-orange { background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); }
.stat-card-num { font-size: 30px; font-weight: 700; line-height: 1.2; }
.stat-card-label { font-size: 13px; opacity: 0.9; margin-top: 6px; }

.semantic { background: #fffbe6; border: 1px solid #fde58e; border-radius: 6px; padding: 12px 14px; margin-bottom: 14px; }
.semantic-actions { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.semantic-actions .hint { color: #9ca3af; font-size: 12px; }
.preview-box { min-height: 70vh; }
.preview-frame { width: 100%; height: 70vh; border: 1px solid #eef1f5; border-radius: 6px; background: #fff; }
.img-preview { display: flex; justify-content: center; align-items: center; min-height: 50vh; background: #f5f5f5; border-radius: 6px; }
.unsupported-preview { display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 50vh; background: #fafafa; border-radius: 6px; border: 1px dashed #ddd; }
.unsupported-icon { font-size: 64px; margin-bottom: 16px; opacity: 0.6; }
.unsupported-preview p { color: #666; margin: 4px 0; }
.unsupported-preview .hint { font-size: 12px; color: #999; margin-bottom: 16px; }
</style>
