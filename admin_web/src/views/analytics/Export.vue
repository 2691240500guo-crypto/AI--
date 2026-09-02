<template>
  <div class="export-page">
    <el-card title="报表配置">
      <el-form inline>
        <el-form-item label="报表类型">
          <el-select v-model="form.report_type" style="width:200px">
            <el-option v-for="r in reportTypes" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="form.filters.dept_id" clearable placeholder="全部" style="width:160px">
            <el-option v-for="d in deptOptions" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="等级">
          <el-select v-model="form.filters.level" clearable placeholder="全部" style="width:120px">
            <el-option v-for="l in levelOptions" :key="l.value" :label="l.label" :value="l.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker v-model="form.dateRange" type="daterange" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="doExport">立即导出</el-button>
      </el-form>
    </el-card>

    <el-card style="margin-top:16px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>已生成报表</span>
          <el-button v-if="reports.length" link type="danger" @click="clearHistory">清空历史</el-button>
        </div>
      </template>
      <el-table :data="reports" border>
        <el-table-column prop="name" label="名称" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="download(row)">下载</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { exportReport, downloadReportFile } from '@/api/analytics'
import { listDepts } from '@/api/dept'
import { ElMessage } from 'element-plus'

const reportTypes = [
  { value: 'talent', label: '人才报表' },
  { value: 'assess', label: '测评报表' },
  { value: 'match', label: '匹配报表' },
  { value: 'training', label: '培训报表' },
]
const levelOptions = [{ value: 'S', label: 'S' }, { value: 'A', label: 'A' }, { value: 'B', label: 'B' }, { value: 'C', label: 'C' }]

// 部门下拉：从后端 /depts（sys_dept）动态加载，不再硬编码（2026-09-02）
const deptOptions = ref([])
async function loadDepts() {
  try {
    const list = (await listDepts()).data || []
    deptOptions.value = list.filter(d => d.status !== 0).map(d => ({ value: d.id, label: d.name }))
  } catch { /* 拉取失败留空，导出仍可全量进行 */ }
}
onMounted(loadDepts)

const loading = ref(false)

// 导出历史：localStorage 持久化，刷新后可恢复（最多保留 50 条）
const HISTORY_KEY = 'analytics_export_history'
let savedHistory = []
try { savedHistory = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { savedHistory = [] }
const reports = ref(Array.isArray(savedHistory) ? savedHistory : [])

function saveHistory() {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(reports.value.slice(0, 50)))
}

function clearHistory() {
  reports.value = []
  localStorage.removeItem(HISTORY_KEY)
}

const form = ref({ report_type: 'talent', filters: { dept_id: null, level: null }, dateRange: null })

async function doExport() {
  loading.value = true
  try {
    const filters = { ...form.value.filters }
    if (form.value.dateRange) { filters.start_date = form.value.dateRange[0]; filters.end_date = form.value.dateRange[1] }
    const res = await exportReport({ report_type: form.value.report_type, filters })
    const d = res.data || {}
    if (!d.file_url) throw new Error('未返回下载地址')
    reports.value.unshift({ name: d.file_name || '报表', file_url: d.file_url })
    saveHistory()
    ElMessage.success('导出成功，点击下载')
  } catch (e) { ElMessage.error('导出失败：' + (e?.message || '请重试')) } finally { loading.value = false }
}

async function download(row) {
  if (!row.file_url) return
  try {
    // row.file_url 形如 http://127.0.0.1:8000/api/v1/analytics/export/download?object_name=analytics%2F...
    const qs = row.file_url.split('?')[1] || ''
    const object_name = new URLSearchParams(qs).get('object_name')
    if (!object_name) throw new Error('缺少 object_name')
    const blob = await downloadReportFile(object_name)   // 带 token 下载，不再 401
    const url = URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = row.name || '报表.xlsx'                  // 用导出时的 file_name 当文件名
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch (e) {
    ElMessage.error('下载失败：' + (e?.message || '请重试'))
  }
}

</script>

<style scoped>.export-page { padding: 16px; }</style>
