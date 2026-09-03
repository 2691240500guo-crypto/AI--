<template>
  <div class="ask-page">
    <el-card>
      <el-form inline @submit.prevent="run">
        <el-form-item label="问题" style="width:60%">
          <el-input v-model="question" placeholder="如：统计各部门硕士人数" clearable
            @keyup.enter="run" :disabled="loading" />
        </el-form-item>
        <el-form-item label="图表">
          <el-select v-model="chartType" style="width:110px">
            <el-option value="bar" label="柱状" />
            <el-option value="line" label="折线" />
            <el-option value="pie" label="饼图" />
          </el-select>
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="run">问数</el-button>
      </el-form>
    </el-card>

    <!-- SQL 展示（可折叠） -->
    <el-card v-if="sql" style="margin-top:12px">
      <template #header>生成的 SQL <el-button link type="primary" @click="copySql">复制</el-button></template>
      <pre class="sql-box">{{ sql }}</pre>
    </el-card>

    <!-- 图表：chart_json 是简化结构，需转 ECharts option -->
    <el-card v-if="hasChart" style="margin-top:12px">
      <EChart :option="chartOption" height="360px" />
    </el-card>

    <!-- 数据表格 -->
    <el-card v-if="rows.length" style="margin-top:12px">
      <el-table :data="tableRows" border max-height="400">
        <el-table-column v-for="c in columns" :key="c" :prop="c" :label="c" />
      </el-table>
    </el-card>

    <!-- 拒答提示 -->
    <el-alert v-if="rejected" type="warning" :title="rejectMsg" style="margin-top:12px" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import EChart from '@/components/EChart.vue'
import { askNL2SQL } from '@/api/analytics'
import { ElMessage } from 'element-plus'

const question = ref('')
const chartType = ref('bar')
const loading = ref(false)
const sql = ref('')
const columns = ref([])
const rows = ref([])
const chartJson = ref(null)
const rejected = ref(false)
const rejectMsg = ref('')

// hasChart：bar/line 需 series，pie 需 data；保证图表区不渲染空图（不再显示虚线）
const hasChart = computed(() => {
  const cj = chartJson.value
  if (!cj || !cj.type) return false
  if (cj.type === 'pie') return !!(cj.data?.length)
  return !!(cj.series?.length)
})

// —— chart_json(简化结构) → ECharts option（后端不是完整 option，需转换）——
const chartOption = computed(() => {
  const cj = chartJson.value
  if (!cj || !cj.type) return {}
  if (cj.type === 'pie') {
    return {
      tooltip: { trigger: 'item' }, legend: { bottom: 0 },
      series: [{ type: 'pie', radius: '55%', data: cj.data || [] }]
    }
  }
  // bar / line：labels 当 X 轴，series 数组生成数据序列
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: cj.labels || [] },
    yAxis: { type: 'value' },
    series: (cj.series || []).map(s => ({ name: s.name, type: cj.type, data: s.data }))
  }
})

// —— 表格：columns 转 prop，rows 转 [{col:val}] ——
const tableRows = computed(() =>
  rows.value.map(r => {
    const o = {}
    columns.value.forEach((c, i) => { o[c] = r[i] })
    return o
  })
)

async function run() {
  if (!question.value.trim()) return ElMessage.warning('请输入问题')
  loading.value = true
  rejected.value = false; sql.value = ''; columns.value = []; rows.value = []; chartJson.value = null
  try {
    // 拦截器返回整个 body，业务字段在 res.data
    const d = (await askNL2SQL({ question: question.value.trim(), chart_type: chartType.value })).data || {}
    sql.value = d.sql || ''
    columns.value = d.columns || []
    rows.value = d.rows || []
    chartJson.value = d.chart_json || null
    // 关键：后端实际 status 是 'done' / 'failed'（不是 ok/rejected）
    if (d.status !== 'done' || !d.sql) {
      rejected.value = true
      rejectMsg.value = d.error_msg || '该问题超出问数范围（已拦截）或生成失败，请换种问法'
    }
  } catch { ElMessage.error('问数失败，请重试') } finally { loading.value = false }
}

function copySql() {
  navigator.clipboard?.writeText(sql.value)
  ElMessage.success('SQL 已复制')
}
</script>

<style scoped>
.ask-page { padding: 16px; }
.sql-box { background:#f5f7fa; padding:12px; border-radius:4px; white-space:pre-wrap; word-break:break-all; margin:0; }
</style>
