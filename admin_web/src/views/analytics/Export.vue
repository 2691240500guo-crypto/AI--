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

    <el-card title="已生成报表" style="margin-top:16px">
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
import { ref } from 'vue'
import { exportReport } from '@/api/analytics'
import { ElMessage } from 'element-plus'

const reportTypes = [
  { value: 'talent', label: '人才报表' },
  { value: 'assess', label: '测评报表' },
  { value: 'match', label: '匹配报表' },
  { value: 'training', label: '培训报表' },
]
const deptOptions = [{ value: 1, label: '研发部' }, { value: 2, label: '产品部' }]
const levelOptions = [{ value: 'S', label: 'S' }, { value: 'A', label: 'A' }, { value: 'B', label: 'B' }, { value: 'C', label: 'C' }]

const loading = ref(false)
const reports = ref([])
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
    ElMessage.success('导出成功，点击下载')
  } catch (e) { ElMessage.error('导出失败：' + (e?.message || '请重试')) } finally { loading.value = false }
}

function download(row) {
  if (row.file_url) window.open(row.file_url, '_blank')
}
</script>

<style scoped>.export-page { padding: 16px; }</style>
