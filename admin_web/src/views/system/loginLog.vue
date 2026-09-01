<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { exportLoginLogs, listLoginLogs } from '@/api/audit'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 20, username: '' })

async function load() {
  loading.value = true
  try {
    const res = await listLoginLogs(query)
    rows.value = res.data.items
    total.value = res.data.meta.total
  } finally {
    loading.value = false
  }
}

async function doExport() {
  try {
    const blob = await exportLoginLogs({ username: query.username || undefined })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `登录日志_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出')
  } catch (e) {
    ElMessage.error('导出失败：' + (e?.message || e))
  }
}

onMounted(load)
</script>

<template>
  <el-card>
    <div class="bar">
      <el-input v-model="query.username" placeholder="按账号筛选" style="width:240px" clearable @keyup.enter="query.page=1;load()" />
      <el-button type="primary" @click="query.page=1;load()">查询</el-button>
      <el-button type="primary" plain @click="doExport">导出 CSV</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="账号" width="150" />
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.success === 1 ? 'success' : 'danger'" size="small">
            {{ row.success === 1 ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="message" label="说明" min-width="160" show-overflow-tooltip />
      <el-table-column prop="ip" label="IP" width="140" />
      <el-table-column prop="created_at" label="时间" width="180" />
    </el-table>

    <el-pagination style="margin-top:14px;justify-content:flex-end" layout="total, prev, pager, next" :total="total"
      v-model:current-page="query.page" :page-size="query.page_size" @current-change="load" />
  </el-card>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; }
</style>
