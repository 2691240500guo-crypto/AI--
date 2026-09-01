<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { exportOperationLogs, listOperationLogs } from '@/api/audit'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 20, action: '', username: '' })
const timeRange = ref([])

const methodTag = {
  GET: 'info', POST: 'success', PUT: 'warning', DELETE: 'danger', PATCH: 'primary'
}

async function load() {
  loading.value = true
  try {
    const res = await listOperationLogs({ ...query, ...timeParams() })
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally {
    loading.value = false
  }
}

async function doExport() {
  try {
    const blob = await exportOperationLogs({ action: query.action || undefined, username: query.username || undefined, ...timeParams() })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `操作日志_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出')
  } catch (e) {
    ElMessage.error('导出失败：' + (e?.message || e))
  }
}

function timeParams() {
  return {
    begin: timeRange.value?.[0] || undefined,
    end: timeRange.value?.[1] || undefined
  }
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar">
      <el-input v-model="query.action" placeholder="按动作筛选，如 user / 创建" style="width:240px" clearable @keyup.enter="query.page=1;load()" />
      <el-input v-model="query.username" placeholder="按操作人筛选" style="width:200px" clearable @keyup.enter="query.page=1;load()" />
      <el-date-picker v-model="timeRange" type="datetimerange" value-format="YYYY-MM-DD HH:mm:ss" start-placeholder="开始时间" end-placeholder="结束时间" range-separator="至" style="width:380px" @change="query.page=1" />
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button type="primary" plain @click="doExport">导出 CSV</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="操作人" width="120">
        <template #default="{ row }">{{ row.username || '—' }}</template>
      </el-table-column>
      <el-table-column label="方法" width="90">
        <template #default="{ row }">
          <el-tag :type="methodTag[row.method] || 'info'" size="small">{{ row.method }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
      <el-table-column prop="action" label="动作" width="180" show-overflow-tooltip />
      <el-table-column prop="status_code" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status_code < 400 ? 'success' : 'danger'" size="small">{{ row.status_code }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="ip" label="IP" width="120" />
      <el-table-column prop="duration_ms" label="耗时(ms)" width="90" />
      <el-table-column prop="request_body" label="请求内容" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.request_body || '—' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="170" />
    </el-table>

    <el-pagination style="margin-top:14px;justify-content:flex-end" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; }
</style>
